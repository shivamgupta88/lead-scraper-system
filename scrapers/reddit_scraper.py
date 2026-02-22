"""Reddit scraper using asyncpraw"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, extract_urls_from_text, is_linkedin_url
import asyncpraw
import re


class RedditScraper(BaseScraper):
    """Scraper for Reddit using asyncpraw"""

    def __init__(self, *args, **kwargs):
        super().__init__("reddit", *args, **kwargs)

        self.subreddits = [
            "SaaS", "startups", "entrepreneur", "marketing",
            "forhire", "startupjobs", "b2bmarketing", "digitalnomad",
            "smallbusiness", "Entrepreneur_Ideas"
        ]

        self.search_keywords = [
            "hiring", "founder", "AMA", "launched", "we're hiring",
            "looking for", "join our team", "B2B SaaS", "raised funding"
        ]

        self.reddit_client = None

    async def _initialize_reddit(self):
        """Initialize Reddit client"""
        # Get API key
        api_key = await self.api_key_rotator.get_key('reddit')

        if not api_key:
            log.error("No Reddit API keys available")
            return None

        client_id, client_secret = self.api_key_rotator.get_reddit_credentials(api_key)

        try:
            reddit = asyncpraw.Reddit(
                client_id=client_id,
                client_secret=client_secret,
                user_agent="LeadScraper/1.0"
            )

            # Test authentication
            await reddit.user.me()
            return reddit

        except Exception as e:
            log.error(f"Failed to initialize Reddit client: {e}")
            await self.api_key_rotator.mark_invalid(api_key)
            return None

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape Reddit for leads"""

        # Initialize Reddit client
        self.reddit_client = await self._initialize_reddit()

        if not self.reddit_client:
            log.error("Failed to initialize Reddit client, skipping")
            return

        try:
            # Search each subreddit
            for subreddit_name in self.subreddits:
                log.info(f"{self.source_name}: Scraping r/{subreddit_name}")

                try:
                    subreddit = await self.reddit_client.subreddit(subreddit_name)

                    # Get hot posts
                    async for submission in subreddit.hot(limit=50):
                        yield await self._process_submission(submission)

                    # Search for keywords
                    for keyword in self.search_keywords[:3]:  # Limit keywords to avoid rate limits
                        try:
                            async for submission in subreddit.search(keyword, limit=25):
                                yield await self._process_submission(submission)

                        except Exception as e:
                            log.debug(f"Error searching '{keyword}' in r/{subreddit_name}: {e}")
                            continue

                except Exception as e:
                    log.error(f"Error scraping r/{subreddit_name}: {e}")
                    continue

        finally:
            if self.reddit_client:
                await self.reddit_client.close()

    async def _process_submission(self, submission) -> dict:
        """Process a Reddit submission"""

        # Get submission data
        data = {
            'id': submission.id,
            'title': submission.title,
            'selftext': submission.selftext,
            'author': str(submission.author) if submission.author else None,
            'url': submission.url,
            'created_utc': submission.created_utc,
            'score': submission.score,
            'num_comments': submission.num_comments,
            'link_flair_text': submission.link_flair_text,
            'subreddit': str(submission.subreddit)
        }

        # Fetch top comments for additional data
        try:
            await submission.comments.replace_more(limit=0)
            comments = []

            for comment in submission.comments.list()[:10]:  # Top 10 comments
                if hasattr(comment, 'body'):
                    comments.append({
                        'author': str(comment.author) if comment.author else None,
                        'body': comment.body,
                        'score': comment.score
                    })

            data['comments'] = comments

        except Exception as e:
            log.debug(f"Error fetching comments for {submission.id}: {e}")
            data['comments'] = []

        return data

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from Reddit post"""

        # Combine text fields
        text_parts = [
            raw_data.get('title', ''),
            raw_data.get('selftext', '')
        ]

        # Add comment text
        for comment in raw_data.get('comments', []):
            text_parts.append(comment.get('body', ''))

        combined_text = ' '.join(text_parts)

        # Extract emails
        emails = extract_emails_from_text(combined_text)
        if not emails:
            return None

        # Extract URLs
        urls = extract_urls_from_text(combined_text)
        if raw_data.get('url'):
            urls.insert(0, raw_data['url'])

        # Find LinkedIn URL and website
        linkedin_url = None
        website = None
        for url in urls:
            if is_linkedin_url(url):
                linkedin_url = url
            elif not website and 'reddit.com' not in url:
                website = url

        # Extract company and role
        company = self._extract_company(combined_text)
        role = self._extract_role(combined_text)

        # Get name from author or extract
        author = raw_data.get('author', '')
        name = author if author and author != '[deleted]' else self._extract_name(combined_text)

        # Determine signal type based on flair and content
        signal_type = 'general'
        flair = raw_data.get('link_flair_text', '').lower()

        if 'hiring' in flair or 'hiring' in combined_text.lower():
            signal_type = 'hiring'
        elif 'funding' in combined_text.lower() or 'raised' in combined_text.lower():
            signal_type = 'funding'
        elif 'ama' in combined_text.lower() or 'ask me anything' in combined_text.lower():
            signal_type = 'ama'
        elif 'launch' in combined_text.lower():
            signal_type = 'product_launch'

        return {
            'email': emails[0],
            'name': name,
            'company': company,
            'role': role,
            'linkedin_url': linkedin_url,
            'website': website,
            'location': '',
            'signal_type': signal_type,
            'raw_data': str(raw_data)[:1000]
        }

    def _extract_company(self, text: str) -> str:
        """Extract company name from text"""
        patterns = [
            r'(?:at|@|from)\s+([A-Z][A-Za-z0-9\s&]{2,30})',
            r'(?:founded|started|building)\s+([A-Z][A-Za-z0-9\s&]{2,30})',
            r'(?:CEO|CTO|founder)\s+(?:of|at)\s+([A-Z][A-Za-z0-9\s&]{2,30})',
            r'(?:my company|our company|company called)\s+([A-Z][A-Za-z0-9\s&]{2,30})'
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                company = match.group(1).strip()
                # Filter out common false positives
                if company.lower() not in ['reddit', 'linkedin', 'twitter', 'facebook']:
                    return company

        return "Unknown"

    def _extract_role(self, text: str) -> str:
        """Extract role/title from text"""
        patterns = [
            r'\b(founder|co-founder|CEO|CTO|CMO|VP of [A-Za-z]+)\b',
            r'\b(Head of [A-Za-z]+|Director of [A-Za-z]+)\b',
            r"I'?m a ([A-Za-z\s]{3,30}(?:engineer|developer|designer|manager|lead))",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_name(self, text: str) -> str:
        """Extract name from text"""
        patterns = [
            r"I'?m ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"My name is ([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
            r"(?:Hi|Hey|Hello),?\s+(?:I'm|I am)\s+([A-Z][a-z]+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return "Unknown"
