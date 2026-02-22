"""HackerNews scraper using Algolia API"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, extract_urls_from_text, is_linkedin_url
import re


class HackerNewsScraper(BaseScraper):
    """Scraper for HackerNews using Algolia API"""

    def __init__(self, *args, **kwargs):
        super().__init__("hackernews", *args, **kwargs)

        self.algolia_url = "http://hn.algolia.com/api/v1/search"
        self.item_url = "https://hacker-news.firebaseio.com/v0/item/{}.json"
        self.user_url = "https://hacker-news.firebaseio.com/v0/user/{}.json"

        self.search_keywords = [
            "hiring", "founder", "YC", "raised", "we're hiring",
            "SaaS", "B2B", "startup", "looking for", "join us",
            "seed round", "series a", "looking to hire"
        ]

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape HackerNews for leads"""

        # Search for each keyword
        for keyword in self.search_keywords:
            log.info(f"{self.source_name}: Searching for '{keyword}'")

            page = 0
            max_pages = 10  # Limit pages per keyword

            while page < max_pages:
                try:
                    # Fetch search results
                    params = {
                        'query': keyword,
                        'tags': 'story',
                        'hitsPerPage': 50,
                        'page': page
                    }

                    data = await self.fetch_page(
                        self.algolia_url,
                        use_proxy=False,
                        params=params
                    )

                    hits = data.get('hits', [])
                    if not hits:
                        break

                    # Process each hit
                    for hit in hits:
                        try:
                            # Extract data from hit
                            yield {
                                'id': hit.get('objectID'),
                                'title': hit.get('title', ''),
                                'text': hit.get('story_text', ''),
                                'url': hit.get('url', ''),
                                'author': hit.get('author', ''),
                                'created_at': hit.get('created_at', ''),
                                'num_comments': hit.get('num_comments', 0),
                                '_cursor': f"{keyword}_{page}"
                            }

                            # If story has comments, fetch them for emails
                            if hit.get('num_comments', 0) > 0:
                                async for comment_lead in self._scrape_comments(hit['objectID']):
                                    yield comment_lead

                            # Fetch user profile for additional data
                            author = hit.get('author')
                            if author:
                                user_data = await self._fetch_user_profile(author)
                                if user_data:
                                    yield {
                                        'user': author,
                                        'about': user_data.get('about', ''),
                                        'karma': user_data.get('karma', 0),
                                        '_cursor': f"{keyword}_{page}_user_{author}"
                                    }

                        except Exception as e:
                            log.debug(f"Error processing HN hit: {e}")
                            continue

                    page += 1

                except Exception as e:
                    log.error(f"{self.source_name}: Error fetching page {page} for '{keyword}': {e}")
                    break

        # Scrape "Who's Hiring" threads
        async for lead in self._scrape_whos_hiring():
            yield lead

    async def _scrape_comments(self, story_id: str) -> AsyncGenerator[dict, None]:
        """Scrape comments from a story"""
        try:
            story_data = await self.fetch_page(
                self.item_url.format(story_id),
                use_proxy=False
            )

            comment_ids = story_data.get('kids', [])[:20]  # Limit to first 20 comments

            for comment_id in comment_ids:
                try:
                    comment_data = await self.fetch_page(
                        self.item_url.format(comment_id),
                        use_proxy=False
                    )

                    if comment_data and comment_data.get('text'):
                        yield {
                            'comment_id': comment_id,
                            'comment_text': comment_data.get('text', ''),
                            'author': comment_data.get('by', ''),
                            'parent_story': story_id
                        }

                except Exception as e:
                    log.debug(f"Error fetching comment {comment_id}: {e}")
                    continue

        except Exception as e:
            log.debug(f"Error scraping comments for story {story_id}: {e}")

    async def _fetch_user_profile(self, username: str) -> Optional[dict]:
        """Fetch user profile data"""
        try:
            user_data = await self.fetch_page(
                self.user_url.format(username),
                use_proxy=False
            )
            return user_data
        except Exception as e:
            log.debug(f"Error fetching user {username}: {e}")
            return None

    async def _scrape_whos_hiring(self) -> AsyncGenerator[dict, None]:
        """Scrape 'Who's Hiring' threads"""
        # Search for Who's Hiring threads
        params = {
            'query': "Who is hiring",
            'tags': 'story',
            'hitsPerPage': 10
        }

        try:
            data = await self.fetch_page(
                self.algolia_url,
                use_proxy=False,
                params=params
            )

            hits = data.get('hits', [])

            for hit in hits[:3]:  # Process top 3 threads
                story_id = hit.get('objectID')
                if story_id:
                    async for comment in self._scrape_comments(story_id):
                        yield {
                            **comment,
                            'signal_type': 'hiring_thread'
                        }

        except Exception as e:
            log.error(f"Error scraping Who's Hiring threads: {e}")

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from HN raw data"""

        # Combine all text fields
        text_fields = [
            raw_data.get('title', ''),
            raw_data.get('text', ''),
            raw_data.get('about', ''),
            raw_data.get('comment_text', '')
        ]
        combined_text = ' '.join(text_fields)

        # Extract emails
        emails = extract_emails_from_text(combined_text)
        if not emails:
            return None

        # Extract URLs
        urls = extract_urls_from_text(combined_text)

        # Find LinkedIn URL
        linkedin_url = None
        website = None
        for url in urls:
            if is_linkedin_url(url):
                linkedin_url = url
            elif not website:
                website = url

        # Extract company and role from text
        company = self._extract_company(combined_text)
        role = self._extract_role(combined_text)

        # Get name from author or extract from text
        name = raw_data.get('user', '') or raw_data.get('author', '') or self._extract_name(combined_text)

        # Determine signal type
        signal_type = raw_data.get('signal_type', '')
        if not signal_type:
            if any(kw in combined_text.lower() for kw in ['hiring', 'looking for', 'join us']):
                signal_type = 'hiring'
            elif any(kw in combined_text.lower() for kw in ['raised', 'funding', 'series']):
                signal_type = 'funding'
            else:
                signal_type = 'general'

        return {
            'email': emails[0],  # Use first email found
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
        # Look for patterns like "at Company", "@ Company", "CEO of Company"
        patterns = [
            r'(?:at|@)\s+([A-Z][A-Za-z0-9\s]{2,30})',
            r'(?:CEO|CTO|founder)\s+(?:of|at)\s+([A-Z][A-Za-z0-9\s]{2,30})',
            r'(?:working at|employed at)\s+([A-Z][A-Za-z0-9\s]{2,30})'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_role(self, text: str) -> str:
        """Extract role/title from text"""
        # Look for common titles
        titles = [
            'founder', 'co-founder', 'ceo', 'cto', 'cmo', 'vp',
            'head of', 'director', 'engineer', 'developer', 'designer'
        ]

        text_lower = text.lower()
        for title in titles:
            if title in text_lower:
                # Try to get context around title
                idx = text_lower.index(title)
                snippet = text[max(0, idx-20):min(len(text), idx+50)]
                return snippet.strip()

        return "Unknown"

    def _extract_name(self, text: str) -> str:
        """Extract name from text"""
        # Look for patterns like "I'm John Doe" or "My name is John Doe"
        patterns = [
            r"I(?:'m| am)\s+([A-Z][a-z]+\s+[A-Z][a-z]+)",
            r"(?:My name is|I'm)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return "Unknown"
