"""Proxy rotation and health monitoring"""

import aiohttp
import asyncio
from typing import List, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from utils.logger import log
from config.settings import settings
import random


@dataclass
class Proxy:
    """Proxy data structure"""
    url: str
    username: Optional[str] = None
    password: Optional[str] = None
    success_count: int = 0
    failure_count: int = 0
    last_used: Optional[datetime] = None
    is_healthy: bool = True

    @property
    def success_rate(self) -> float:
        """Calculate proxy success rate"""
        total = self.success_count + self.failure_count
        if total == 0:
            return 1.0
        return self.success_count / total

    @property
    def proxy_auth(self) -> Optional[aiohttp.BasicAuth]:
        """Get proxy authentication"""
        if self.username and self.password:
            return aiohttp.BasicAuth(self.username, self.password)
        return None


class ProxyManager:
    """Manages proxy pool with health monitoring"""

    def __init__(self):
        self.proxies: List[Proxy] = []
        self.current_index = 0
        self.lock = asyncio.Lock()
        self.health_check_interval = 300  # 5 minutes

    async def initialize(self):
        """Initialize proxy pool from Webshare.io API"""
        if not settings.webshare_api_key:
            log.warning("No Webshare API key provided. Running without proxies.")
            return

        try:
            await self._fetch_proxies_from_webshare()
            log.info(f"Initialized {len(self.proxies)} proxies")

            # Start health check task
            asyncio.create_task(self._periodic_health_check())

        except Exception as e:
            log.error(f"Failed to initialize proxies: {e}")

    async def _fetch_proxies_from_webshare(self):
        """Fetch proxy list from Webshare.io API"""
        url = "https://proxy.webshare.io/api/v2/proxy/list/"
        headers = {"Authorization": f"Token {settings.webshare_api_key}"}

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                headers=headers,
                params={"mode": "direct", "page_size": settings.proxy_count}
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    proxies_data = data.get('results', [])

                    for proxy_info in proxies_data:
                        proxy_url = f"http://{proxy_info['proxy_address']}:{proxy_info['port']}"
                        self.proxies.append(Proxy(
                            url=proxy_url,
                            username=proxy_info.get('username'),
                            password=proxy_info.get('password')
                        ))

                    log.info(f"Fetched {len(self.proxies)} proxies from Webshare.io")
                else:
                    log.error(f"Failed to fetch proxies: HTTP {response.status}")

    async def get_proxy(self) -> Optional[Proxy]:
        """Get next healthy proxy from pool (round-robin)"""
        if not self.proxies:
            return None

        async with self.lock:
            # Find next healthy proxy
            attempts = 0
            while attempts < len(self.proxies):
                proxy = self.proxies[self.current_index]
                self.current_index = (self.current_index + 1) % len(self.proxies)

                if proxy.is_healthy:
                    proxy.last_used = datetime.utcnow()
                    return proxy

                attempts += 1

            # No healthy proxies found, return least recently failed
            return min(self.proxies, key=lambda p: p.failure_count)

    async def get_random_proxy(self) -> Optional[Proxy]:
        """Get random healthy proxy from pool"""
        if not self.proxies:
            return None

        healthy_proxies = [p for p in self.proxies if p.is_healthy]

        if not healthy_proxies:
            # No healthy proxies, return one with best success rate
            return max(self.proxies, key=lambda p: p.success_rate)

        return random.choice(healthy_proxies)

    async def mark_success(self, proxy: Proxy):
        """Mark proxy request as successful"""
        async with self.lock:
            proxy.success_count += 1
            proxy.is_healthy = True

    async def mark_failure(self, proxy: Proxy):
        """Mark proxy request as failed"""
        async with self.lock:
            proxy.failure_count += 1

            # Mark as unhealthy if success rate drops below 50%
            if proxy.success_rate < 0.5 and proxy.failure_count > 5:
                proxy.is_healthy = False
                log.warning(
                    f"Proxy {proxy.url} marked unhealthy. "
                    f"Success rate: {proxy.success_rate:.2%}"
                )

    async def _check_proxy_health(self, proxy: Proxy) -> bool:
        """Check if proxy is working"""
        test_url = "https://httpbin.org/ip"

        try:
            timeout = aiohttp.ClientTimeout(total=10)
            connector = aiohttp.TCPConnector(ssl=False)

            async with aiohttp.ClientSession(
                timeout=timeout,
                connector=connector
            ) as session:
                async with session.get(
                    test_url,
                    proxy=proxy.url,
                    proxy_auth=proxy.proxy_auth
                ) as response:
                    if response.status == 200:
                        return True
                    return False

        except Exception as e:
            log.debug(f"Proxy {proxy.url} health check failed: {e}")
            return False

    async def _periodic_health_check(self):
        """Periodically check health of all proxies"""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)

                log.info("Running proxy health checks...")
                tasks = [self._check_proxy_health(proxy) for proxy in self.proxies]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                async with self.lock:
                    for proxy, is_healthy in zip(self.proxies, results):
                        if isinstance(is_healthy, bool):
                            proxy.is_healthy = is_healthy

                healthy_count = sum(1 for p in self.proxies if p.is_healthy)
                log.info(f"Health check complete: {healthy_count}/{len(self.proxies)} proxies healthy")

            except Exception as e:
                log.error(f"Error in periodic health check: {e}")

    def get_stats(self) -> dict:
        """Get proxy pool statistics"""
        if not self.proxies:
            return {"total": 0, "healthy": 0, "unhealthy": 0}

        healthy = sum(1 for p in self.proxies if p.is_healthy)
        total_success = sum(p.success_count for p in self.proxies)
        total_failure = sum(p.failure_count for p in self.proxies)

        return {
            "total": len(self.proxies),
            "healthy": healthy,
            "unhealthy": len(self.proxies) - healthy,
            "total_requests": total_success + total_failure,
            "success_rate": total_success / (total_success + total_failure) if (total_success + total_failure) > 0 else 0
        }
