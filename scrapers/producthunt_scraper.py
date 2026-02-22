"""Product Hunt scraper using GraphQL API"""

from scrapers.base_scraper import BaseScraper
from typing import AsyncGenerator, Optional, Dict
from utils.logger import log
from utils.validators import extract_emails_from_text, is_valid_email
from datetime import datetime, timedelta


class ProductHuntScraper(BaseScraper):
    """Scraper for Product Hunt using GraphQL API"""

    def __init__(self, *args, **kwargs):
        super().__init__("producthunt", *args, **kwargs)

        self.graphql_url = "https://www.producthunt.com/frontend/graphql"

        # GraphQL query for posts
        self.posts_query = """
        query GetPosts($after: String) {
          posts(first: 20, after: $after, order: RANKING) {
            edges {
              node {
                id
                name
                tagline
                description
                url
                website
                votesCount
                commentsCount
                createdAt
                topics {
                  edges {
                    node {
                      name
                    }
                  }
                }
                makers {
                  edges {
                    node {
                      id
                      name
                      username
                      headline
                      profileUrl
                      websiteUrl
                      twitterUsername
                    }
                  }
                }
              }
              cursor
            }
            pageInfo {
              hasNextPage
              endCursor
            }
          }
        }
        """

    async def scrape(self) -> AsyncGenerator[dict, None]:
        """Scrape Product Hunt for leads"""

        # Get API key
        api_key = await self.api_key_rotator.get_key('producthunt')

        if not api_key:
            log.error("No Product Hunt API keys available")
            return

        headers = {
            'Authorization': f'Bearer {api_key.key}',
            'Content-Type': 'application/json'
        }

        cursor = None
        max_pages = 10
        page = 0

        while page < max_pages:
            try:
                # Prepare GraphQL query
                variables = {'after': cursor} if cursor else {}

                payload = {
                    'query': self.posts_query,
                    'variables': variables
                }

                # Fetch data
                response = await self.session_manager.post(
                    self.graphql_url,
                    headers=headers,
                    json=payload
                )

                async with response:
                    if response.status == 429:
                        await self.rate_limiter.handle_429(self.source_name, 60)
                        await self.api_key_rotator.mark_rate_limited(api_key, 60)
                        break

                    if response.status == 401:
                        log.error("Product Hunt authentication failed")
                        await self.api_key_rotator.mark_invalid(api_key)
                        break

                    response.raise_for_status()
                    data = await response.json()

                # Parse response
                posts_data = data.get('data', {}).get('posts', {})
                edges = posts_data.get('edges', [])

                if not edges:
                    break

                # Process each post
                for edge in edges:
                    post = edge.get('node', {})

                    # Filter by topics
                    topics = [t['node']['name'].lower() for t in post.get('topics', {}).get('edges', [])]
                    if any(t in topics for t in ['saas', 'b2b', 'marketing', 'productivity']):
                        yield post

                # Check for next page
                page_info = posts_data.get('pageInfo', {})
                if not page_info.get('hasNextPage'):
                    break

                cursor = page_info.get('endCursor')
                page += 1

            except Exception as e:
                log.error(f"Error fetching Product Hunt page {page}: {e}")
                break

    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """Extract lead data from Product Hunt post"""

        # Get makers (creators of the product)
        makers = raw_data.get('makers', {}).get('edges', [])

        if not makers:
            return None

        # Process first maker (usually the founder)
        maker = makers[0].get('node', {})

        # Get email from website or profile
        website = maker.get('websiteUrl') or raw_data.get('website')

        # Try to construct email or fetch from website
        email = None

        # If we have a website, try to scrape it for email
        if website:
            try:
                website_data = await self.fetch_page(website, use_proxy=True)
                if website_data:
                    text = website_data.get('text', '')
                    emails = extract_emails_from_text(text)
                    if emails:
                        email = emails[0]
            except Exception as e:
                log.debug(f"Error fetching website {website}: {e}")

        if not email:
            # Try common email patterns
            username = maker.get('username', '').lower()
            if website:
                domain = website.replace('https://', '').replace('http://', '').split('/')[0]
                # Common patterns
                possible_emails = [
                    f"{username}@{domain}",
                    f"hello@{domain}",
                    f"contact@{domain}",
                    f"info@{domain}"
                ]

                for possible_email in possible_emails:
                    if is_valid_email(possible_email):
                        email = possible_email
                        break

        if not email:
            return None

        # Build lead data
        name = maker.get('name', 'Unknown')
        company = raw_data.get('name', 'Unknown')
        role = maker.get('headline', 'Maker')

        # Build LinkedIn URL from Twitter if available
        linkedin_url = None
        twitter = maker.get('twitterUsername')
        if twitter:
            # Could potentially search LinkedIn by name
            pass

        # Determine signal type
        signal_type = 'product_launch'
        created_at = raw_data.get('createdAt')
        if created_at:
            try:
                created_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                days_old = (datetime.now(created_date.tzinfo) - created_date).days
                if days_old <= 7:
                    signal_type = 'recent_launch'
            except:
                pass

        return {
            'email': email,
            'name': name,
            'company': company,
            'role': role,
            'linkedin_url': linkedin_url,
            'website': website,
            'location': '',
            'signal_type': signal_type,
            'raw_data': str(raw_data)[:1000]
        }
