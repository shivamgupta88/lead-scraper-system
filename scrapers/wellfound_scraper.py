"""Wellfound (AngelList) scraper using Playwright"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, is_linkedin_url
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
import asyncio
import re


class WellfoundScraper(BaseScraper):
    """Scraper for Wellfound using Playwright for JavaScript rendering"""

    def __init__(self, *args, **kwargs):
        super().__init__("wellfound", *args, **kwargs)

        self.base_url = "https://wellfound.com"
        self.search_url = f"{self.base_url}/jobs"

        self.search_params = {
            'job_types': ['full-time'],
            'company_sizes': ['1-10', '11-50', '51-200'],
            'tags': ['saas', 'b2b', 'marketing']
        }

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape Wellfound for leads"""

        async with async_playwright() as p:
            try:
                # Launch browser
                browser = await p.chromium.launch(
                    headless=True,
                    args=['--disable-blink-features=AutomationControlled']
                )

                context = await browser.new_context(
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
                )

                page = await context.new_page()

                # Search for jobs
                for tag in self.search_params['tags']:
                    log.info(f"{self.source_name}: Searching for tag '{tag}'")

                    try:
                        # Navigate to search page
                        search_url = f"{self.search_url}?tag={tag}"
                        await page.goto(search_url, wait_until='networkidle', timeout=30000)

                        # Wait for job listings to load
                        await page.wait_for_selector('[data-test="JobsList"]', timeout=10000)

                        # Scroll to load more jobs
                        for _ in range(3):
                            await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
                            await asyncio.sleep(2)

                        # Extract job listings
                        job_cards = await page.query_selector_all('[data-test="JobCard"]')

                        log.info(f"{self.source_name}: Found {len(job_cards)} job listings for '{tag}'")

                        for job_card in job_cards[:20]:  # Limit to 20 per tag
                            try:
                                job_data = await self._extract_job_data(page, job_card)
                                if job_data:
                                    yield job_data

                            except Exception as e:
                                log.debug(f"Error extracting job card: {e}")
                                continue

                    except Exception as e:
                        log.error(f"Error searching Wellfound for '{tag}': {e}")
                        continue

                await browser.close()

            except Exception as e:
                log.error(f"Error in Wellfound scraper: {e}")

    async def _extract_job_data(self, page, job_card) -> Optional[dict]:
        """Extract data from a job card"""

        try:
            # Extract job title
            title_elem = await job_card.query_selector('[data-test="JobTitle"]')
            title = await title_elem.inner_text() if title_elem else ""

            # Extract company name
            company_elem = await job_card.query_selector('[data-test="CompanyName"]')
            company = await company_elem.inner_text() if company_elem else ""

            # Extract location
            location_elem = await job_card.query_selector('[data-test="JobLocation"]')
            location = await location_elem.inner_text() if location_elem else ""

            # Get job link
            link_elem = await job_card.query_selector('a')
            job_url = await link_elem.get_attribute('href') if link_elem else None

            if job_url and not job_url.startswith('http'):
                job_url = f"{self.base_url}{job_url}"

            # Click on job to get more details
            if job_url:
                try:
                    # Open in new tab
                    new_page = await page.context.new_page()
                    await new_page.goto(job_url, wait_until='networkidle', timeout=15000)

                    # Wait for content to load
                    await asyncio.sleep(2)

                    # Extract full job description
                    content = await new_page.content()

                    # Extract company profile link
                    company_link = None
                    company_link_elem = await new_page.query_selector('a[href*="/company/"]')
                    if company_link_elem:
                        company_link = await company_link_elem.get_attribute('href')
                        if company_link and not company_link.startswith('http'):
                            company_link = f"{self.base_url}{company_link}"

                    await new_page.close()

                    return {
                        'job_title': title,
                        'company': company,
                        'location': location,
                        'job_url': job_url,
                        'company_url': company_link,
                        'content': content
                    }

                except Exception as e:
                    log.debug(f"Error fetching job details: {e}")
                    return None

            return None

        except Exception as e:
            log.debug(f"Error in _extract_job_data: {e}")
            return None

    async def _fetch_company_profile(self, company_url: str) -> Optional[dict]:
        """Fetch company profile page"""

        async with async_playwright() as p:
            try:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()

                await page.goto(company_url, wait_until='networkidle', timeout=15000)
                await asyncio.sleep(2)

                # Extract company data
                content = await page.content()

                # Try to find founder/team info
                team_section = await page.query_selector('[data-test="TeamSection"]')
                team_html = await team_section.inner_html() if team_section else ""

                await browser.close()

                return {
                    'content': content,
                    'team_html': team_html
                }

            except Exception as e:
                log.debug(f"Error fetching company profile: {e}")
                return None

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from Wellfound job posting"""

        company = raw_data.get('company', 'Unknown')
        company_url = raw_data.get('company_url')
        content = raw_data.get('content', '')

        # Try to fetch company profile for founder info
        founder_data = None
        if company_url:
            try:
                founder_data = await self._fetch_company_profile(company_url)
            except Exception as e:
                log.debug(f"Error fetching company profile: {e}")

        # Extract emails from content
        all_text = content
        if founder_data:
            all_text += founder_data.get('content', '') + founder_data.get('team_html', '')

        emails = extract_emails_from_text(all_text)
        if not emails:
            return None

        # Extract founder name from team section
        name = self._extract_founder_name(all_text)

        # Extract LinkedIn URL
        linkedin_url = None
        linkedin_pattern = r'https?://(?:www\.)?linkedin\.com/in/[\w\-]+'
        match = re.search(linkedin_pattern, all_text)
        if match:
            linkedin_url = match.group(0)

        # Extract website
        website = company_url or self._extract_website(content)

        return {
            'email': emails[0],
            'name': name,
            'company': company,
            'role': 'Founder',  # Assumed from startup context
            'linkedin_url': linkedin_url,
            'website': website,
            'location': raw_data.get('location', ''),
            'signal_type': 'hiring',
            'raw_data': str(raw_data)[:1000]
        }

    def _extract_founder_name(self, html: str) -> str:
        """Extract founder name from HTML"""
        patterns = [
            r'<.*?>([A-Z][a-z]+\s+[A-Z][a-z]+)<.*?>(?:.*?)(?:Founder|CEO|Co-Founder)',
            r'(?:Founder|CEO|Co-Founder).*?<.*?>([A-Z][a-z]+\s+[A-Z][a-z]+)',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()

        return "Unknown"

    def _extract_website(self, html: str) -> str:
        """Extract company website from HTML"""
        pattern = r'https?://(?:www\.)?([\w\-]+\.(?:com|io|co|net|org))'
        matches = re.findall(pattern, html, re.IGNORECASE)

        # Filter out common domains
        exclude = ['wellfound.com', 'angellist.com', 'linkedin.com', 'twitter.com', 'facebook.com']

        for match in matches:
            if not any(ex in match for ex in exclude):
                return f"https://{match}"

        return ""
