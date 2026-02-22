"""aiohttp session management and connection pooling"""

import aiohttp
import asyncio
from typing import Optional, Dict
from utils.logger import log
from config.settings import settings
from core.proxy_manager import Proxy


class SessionManager:
    """Manages aiohttp sessions with connection pooling"""

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.headers: Dict[str, str] = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }

    async def initialize(self):
        """Initialize aiohttp session with connection pool"""
        timeout = aiohttp.ClientTimeout(total=settings.request_timeout)

        connector = aiohttp.TCPConnector(
            limit=settings.connection_pool_size,
            limit_per_host=30,
            ttl_dns_cache=300,
            ssl=False  # Disable SSL verification for faster requests
        )

        self.session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers=self.headers
        )

        log.info(
            f"Session manager initialized with {settings.connection_pool_size} "
            f"connections, {settings.request_timeout}s timeout"
        )

    async def close(self):
        """Close aiohttp session"""
        if self.session:
            await self.session.close()
            # Wait for connections to close
            await asyncio.sleep(0.25)
            log.info("Session manager closed")

    async def get(
        self,
        url: str,
        proxy: Optional[Proxy] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make GET request

        Args:
            url: Target URL
            proxy: Optional Proxy object
            headers: Optional additional headers
            params: Optional query parameters
            **kwargs: Additional aiohttp arguments

        Returns:
            aiohttp.ClientResponse
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        # Merge headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        # Setup proxy
        proxy_url = None
        proxy_auth = None
        if proxy:
            proxy_url = proxy.url
            proxy_auth = proxy.proxy_auth

        try:
            response = await self.session.get(
                url,
                headers=request_headers,
                params=params,
                proxy=proxy_url,
                proxy_auth=proxy_auth,
                **kwargs
            )
            return response

        except aiohttp.ClientError as e:
            log.debug(f"GET request failed for {url}: {e}")
            raise

    async def post(
        self,
        url: str,
        proxy: Optional[Proxy] = None,
        headers: Optional[Dict] = None,
        data: Optional[Dict] = None,
        json: Optional[Dict] = None,
        **kwargs
    ) -> aiohttp.ClientResponse:
        """
        Make POST request

        Args:
            url: Target URL
            proxy: Optional Proxy object
            headers: Optional additional headers
            data: Optional form data
            json: Optional JSON data
            **kwargs: Additional aiohttp arguments

        Returns:
            aiohttp.ClientResponse
        """
        if not self.session:
            raise RuntimeError("Session not initialized. Call initialize() first.")

        # Merge headers
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        # Setup proxy
        proxy_url = None
        proxy_auth = None
        if proxy:
            proxy_url = proxy.url
            proxy_auth = proxy.proxy_auth

        try:
            response = await self.session.post(
                url,
                headers=request_headers,
                data=data,
                json=json,
                proxy=proxy_url,
                proxy_auth=proxy_auth,
                **kwargs
            )
            return response

        except aiohttp.ClientError as e:
            log.debug(f"POST request failed for {url}: {e}")
            raise

    async def fetch_json(
        self,
        url: str,
        proxy: Optional[Proxy] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> Dict:
        """
        Fetch JSON data from URL

        Returns:
            Parsed JSON dictionary
        """
        async with await self.get(url, proxy, headers, params, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def fetch_text(
        self,
        url: str,
        proxy: Optional[Proxy] = None,
        headers: Optional[Dict] = None,
        params: Optional[Dict] = None,
        **kwargs
    ) -> str:
        """
        Fetch text content from URL

        Returns:
            Response text
        """
        async with await self.get(url, proxy, headers, params, **kwargs) as response:
            response.raise_for_status()
            return await response.text()
