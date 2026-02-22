"""Abstract base class for all scrapers"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Dict, Optional
import asyncio
from utils.logger import log
from utils.retry import async_retry
from core.proxy_manager import ProxyManager, Proxy
from core.api_key_rotator import APIKeyRotator, APIKey
from core.rate_limiter import RateLimiter
from core.session_manager import SessionManager
from storage.database import Database
import aiohttp


class BaseScraper(ABC):
    """Abstract base class for all source scrapers"""

    def __init__(
        self,
        source_name: str,
        proxy_manager: ProxyManager,
        api_key_rotator: APIKeyRotator,
        rate_limiter: RateLimiter,
        session_manager: SessionManager,
        database: Database
    ):
        self.source_name = source_name
        self.proxy_manager = proxy_manager
        self.api_key_rotator = api_key_rotator
        self.rate_limiter = rate_limiter
        self.session_manager = session_manager
        self.database = database

        self.leads_scraped = 0
        self.checkpoint_interval = 100  # Save checkpoint every N leads

    @abstractmethod
    async def scrape(self) -> AsyncGenerator[dict, None]:
        """
        Main scraping method - must be implemented by subclasses

        Yields:
            Raw lead data dictionaries
        """
        pass

    @abstractmethod
    async def extract_lead_data(self, raw_data: dict) -> Optional[dict]:
        """
        Extract lead data from raw source data

        Args:
            raw_data: Raw data from source

        Returns:
            Standardized lead dictionary or None if extraction failed
        """
        pass

    @async_retry(
        max_attempts=3,
        exceptions=(aiohttp.ClientError, asyncio.TimeoutError)
    )
    async def fetch_page(
        self,
        url: str,
        use_proxy: bool = False,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        method: str = "GET",
        **kwargs
    ) -> Dict:
        """
        Fetch a page with retry logic

        Args:
            url: URL to fetch
            use_proxy: Whether to use proxy
            headers: Optional headers
            params: Optional query parameters
            method: HTTP method (GET/POST)
            **kwargs: Additional arguments for session manager

        Returns:
            Response data
        """
        # Acquire rate limit token
        await self.rate_limiter.acquire(self.source_name)

        # Get proxy if needed
        proxy = None
        if use_proxy:
            proxy = await self.proxy_manager.get_proxy()

        try:
            if method.upper() == "GET":
                response = await self.session_manager.get(
                    url,
                    proxy=proxy,
                    headers=headers,
                    params=params,
                    **kwargs
                )
            else:
                response = await self.session_manager.post(
                    url,
                    proxy=proxy,
                    headers=headers,
                    **kwargs
                )

            async with response:
                # Handle rate limiting
                if response.status == 429:
                    retry_after = response.headers.get('Retry-After', 60)
                    try:
                        retry_after = int(retry_after)
                    except ValueError:
                        retry_after = 60

                    await self.rate_limiter.handle_429(self.source_name, retry_after)
                    log.warning(f"{self.source_name}: Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    raise aiohttp.ClientError("Rate limited")

                # Handle auth errors
                elif response.status in (401, 403):
                    log.error(f"{self.source_name}: Authentication failed")
                    raise aiohttp.ClientError("Authentication failed")

                # Successful response
                response.raise_for_status()

                # Mark success
                await self.rate_limiter.record_success(self.source_name)
                if proxy:
                    await self.proxy_manager.mark_success(proxy)

                # Return JSON or text
                content_type = response.headers.get('Content-Type', '')
                if 'application/json' in content_type:
                    return await response.json()
                else:
                    text = await response.text()
                    return {'text': text, 'url': url}

        except aiohttp.ClientError as e:
            if proxy:
                await self.proxy_manager.mark_failure(proxy)
            log.debug(f"{self.source_name}: Request failed for {url}: {e}")
            raise

    async def save_checkpoint(self, cursor: str, metadata: Dict = None):
        """
        Save scraping checkpoint

        Args:
            cursor: Pagination cursor or position
            metadata: Additional metadata to save
        """
        try:
            await self.database.save_checkpoint(
                self.source_name,
                cursor,
                metadata or {}
            )
            log.debug(f"{self.source_name}: Checkpoint saved at {cursor}")
        except Exception as e:
            log.error(f"{self.source_name}: Failed to save checkpoint: {e}")

    async def resume_from_checkpoint(self) -> Optional[Dict]:
        """
        Resume from last checkpoint

        Returns:
            Checkpoint data or None if no checkpoint exists
        """
        try:
            checkpoint = await self.database.load_checkpoint(self.source_name)
            if checkpoint:
                log.info(
                    f"{self.source_name}: Resuming from checkpoint. "
                    f"Previous leads: {checkpoint.get('leads_count', 0)}"
                )
                return checkpoint
            return None
        except Exception as e:
            log.error(f"{self.source_name}: Failed to load checkpoint: {e}")
            return None

    def should_save_checkpoint(self) -> bool:
        """Check if checkpoint should be saved"""
        return self.leads_scraped % self.checkpoint_interval == 0

    async def log_error(
        self,
        error_type: str,
        error_message: str,
        traceback: str = None,
        context: Dict = None
    ):
        """
        Log error to database

        Args:
            error_type: Type of error
            error_message: Error message
            traceback: Optional traceback
            context: Optional context dictionary
        """
        try:
            await self.database.log_error(
                self.source_name,
                error_type,
                error_message,
                traceback,
                context or {}
            )
        except Exception as e:
            log.error(f"Failed to log error to database: {e}")

    def normalize_lead(self, lead: dict) -> dict:
        """
        Normalize lead data to standard format

        Args:
            lead: Raw lead dictionary

        Returns:
            Normalized lead dictionary
        """
        return {
            'email': lead.get('email', '').strip().lower(),
            'name': lead.get('name', '').strip(),
            'designation': lead.get('role', lead.get('designation', '')).strip(),
            'company': lead.get('company', '').strip(),
            'geography': lead.get('location', lead.get('geography', '')).strip(),
            'post_content': lead.get('post_content', lead.get('raw_data', ''))[:500],  # Limit to 500 chars
            'buying_intent': lead.get('signal_type', lead.get('buying_intent', '')).strip(),
            'linkedin_url': lead.get('linkedin_url', '').strip(),
            'website': lead.get('website', '').strip(),
            'source': self.source_name,
            'signal_type': lead.get('signal_type', '').strip(),
            'raw_data': str(lead.get('raw_data', ''))
        }

    async def run(self) -> AsyncGenerator[dict, None]:
        """
        Main entry point for running the scraper

        Yields:
            Extracted lead data
        """
        log.info(f"{self.source_name}: Starting scraper")

        try:
            # Try to resume from checkpoint
            checkpoint = await self.resume_from_checkpoint()

            # Run scraper
            async for raw_data in self.scrape():
                try:
                    # Extract lead data
                    lead_data = await self.extract_lead_data(raw_data)

                    if lead_data:
                        # Normalize data
                        normalized_lead = self.normalize_lead(lead_data)

                        # Yield the lead
                        yield normalized_lead

                        self.leads_scraped += 1

                        # Save checkpoint periodically
                        if self.should_save_checkpoint():
                            cursor = raw_data.get('_cursor', str(self.leads_scraped))
                            await self.save_checkpoint(
                                cursor,
                                {'leads_count': self.leads_scraped}
                            )

                except Exception as e:
                    log.error(f"{self.source_name}: Failed to extract lead: {e}")
                    await self.log_error(
                        "extraction_error",
                        str(e),
                        context={'raw_data': str(raw_data)[:500]}
                    )
                    continue

        except Exception as e:
            log.error(f"{self.source_name}: Scraper failed: {e}")
            await self.log_error("scraper_error", str(e))
            raise

        finally:
            log.info(f"{self.source_name}: Scraper finished. Total leads: {self.leads_scraped}")
