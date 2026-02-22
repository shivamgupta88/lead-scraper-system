"""TechCrunch scraper using RSS and web scraping"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, extract_urls_from_text
from bs4 import BeautifulSoup
import feedparser
import asyncio
import re


class TechCrunchScraper(BaseScraper):
    """Scraper for TechCrunch articles"""

    def __init__(self, *args, **kwargs):
        super().__init__("techcrunch", *args, **kwargs)

        self.rss_feeds = [
            "https://techcrunch.com/feed/",
            "https://techcrunch.com/category/startups/feed/",
            "https://techcrunch.com/category/venture/feed/"
        ]

        self.funding_keywords = [
            'raises', 'raised', 'funding', 'series a', 'series b',
            'seed round', 'million', 'b2b', 'saas'
        ]

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape TechCrunch RSS feeds"""

        for feed_url in self.rss_feeds:
            log.info(f"{self.source_name}: Fetching feed {feed_url}")

            try:
                # Fetch RSS feed (feedparser is synchronous)
                feed = await asyncio.to_thread(feedparser.parse, feed_url)

                # Process entries
                for entry in feed.entries[:50]:  # Limit to 50 per feed
                    try:
                        # Check if article is relevant
                        title = entry.get('title', '').lower()
                        summary = entry.get('summary', '').lower()
                        content = f"{title} {summary}"

                        # Filter by keywords
                        if any(kw in content for kw in self.funding_keywords):
                            # Fetch full article
                            article_url = entry.get('link')
                            if article_url:
                                article_data = await self._fetch_article(article_url)
                                if article_data:
                                    article_data.update({
                                        'rss_title': entry.get('title'),
                                        'rss_published': entry.get('published'),
                                        'rss_summary': entry.get('summary')
                                    })
                                    yield article_data

                    except Exception as e:
                        log.debug(f"Error processing TechCrunch entry: {e}")
                        continue

            except Exception as e:
                log.error(f"Error fetching TechCrunch feed {feed_url}: {e}")
                continue

    async def _fetch_article(self, url: str) -> Optional[dict]:
        """Fetch and parse TechCrunch article"""

        try:
            response = await self.fetch_page(url, use_proxy=True)
            html = response.get('text', '')

            if not html:
                return None

            # Parse HTML
            soup = BeautifulSoup(html, 'html.parser')

            # Extract article content
            article_body = soup.find('div', {'class': 'article-content'})
            if not article_body:
                article_body = soup.find('article')

            if not article_body:
                return None

            text = article_body.get_text(separator=' ', strip=True)

            # Extract company info
            company_name = self._extract_company_name(text)

            # Extract funding amount
            funding_amount = self._extract_funding_amount(text)

            return {
                'url': url,
                'text': text[:5000],  # Limit text size
                'company_name': company_name,
                'funding_amount': funding_amount
            }

        except Exception as e:
            log.debug(f"Error fetching article {url}: {e}")
            return None

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from TechCrunch article"""

        text = raw_data.get('text', '')
        company_name = raw_data.get('company_name', 'Unknown')
        article_url = raw_data.get('url', '')

        # Try to find company website in article
        website = None
        urls = extract_urls_from_text(text)
        for url in urls:
            if company_name.lower().replace(' ', '') in url.lower():
                website = url
                break

        # If we have a website, scrape it for contact info
        if website:
            try:
                website_data = await self._scrape_company_website(website)
                if website_data:
                    email = website_data.get('email')
                    if email:
                        return {
                            'email': email,
                            'name': website_data.get('name', 'Unknown'),
                            'company': company_name,
                            'role': website_data.get('role', 'Founder'),
                            'linkedin_url': website_data.get('linkedin_url'),
                            'website': website,
                            'location': website_data.get('location', ''),
                            'signal_type': 'funding_announcement',
                            'raw_data': str(raw_data)[:1000]
                        }

            except Exception as e:
                log.debug(f"Error scraping company website {website}: {e}")

        return None

    async def _scrape_company_website(self, url: str) -> Optional[dict]:
        """Scrape company website for contact info"""

        try:
            # Fetch main page
            response = await self.fetch_page(url, use_proxy=True)
            html = response.get('text', '')

            if not html:
                return None

            soup = BeautifulSoup(html, 'html.parser')

            # Extract emails
            page_text = soup.get_text()
            emails = extract_emails_from_text(page_text)

            if not emails:
                # Try to find contact or about page
                contact_links = soup.find_all('a', href=re.compile(r'(contact|about|team)', re.I))
                for link in contact_links[:2]:
                    href = link.get('href')
                    if href:
                        if not href.startswith('http'):
                            href = url.rstrip('/') + '/' + href.lstrip('/')

                        try:
                            contact_response = await self.fetch_page(href, use_proxy=True)
                            contact_html = contact_response.get('text', '')
                            contact_soup = BeautifulSoup(contact_html, 'html.parser')
                            contact_text = contact_soup.get_text()
                            emails = extract_emails_from_text(contact_text)
                            if emails:
                                break
                        except:
                            continue

            if not emails:
                return None

            # Try to extract founder name
            name = self._extract_founder_name(soup.get_text())

            # Try to find LinkedIn URL
            linkedin_url = None
            linkedin_links = soup.find_all('a', href=re.compile(r'linkedin\.com/in/', re.I))
            if linkedin_links:
                linkedin_url = linkedin_links[0].get('href')

            return {
                'email': emails[0],
                'name': name,
                'role': 'Founder',
                'linkedin_url': linkedin_url,
                'location': ''
            }

        except Exception as e:
            log.debug(f"Error scraping company website: {e}")
            return None

    def _extract_company_name(self, text: str) -> str:
        """Extract company name from article"""
        # Look for patterns like "Company Name, a B2B SaaS..."
        patterns = [
            r'^([A-Z][A-Za-z0-9\s&]{2,30}),\s+a\s+(?:B2B|SaaS|startup)',
            r'([A-Z][A-Za-z0-9\s&]{2,30})\s+(?:raised|announced|secured)',
            r'(?:startup|company)\s+([A-Z][A-Za-z0-9\s&]{2,30})\s+(?:raised|announced)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_funding_amount(self, text: str) -> str:
        """Extract funding amount from article"""
        patterns = [
            r'\$(\d+(?:\.\d+)?)\s*(million|M|billion|B)',
            r'(\d+(?:\.\d+)?)\s*million',
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(0)

        return ""

    def _extract_founder_name(self, text: str) -> str:
        """Extract founder name from text"""
        patterns = [
            r'(?:founded by|CEO|founder)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})',
            r'([A-Z][a-z]+\s+[A-Z][a-z]+),\s+(?:CEO|founder|co-founder)'
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(1).strip()

        return "Unknown"
