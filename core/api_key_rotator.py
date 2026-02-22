"""API key rotation and management"""

import asyncio
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
from utils.logger import log
from config.settings import settings


@dataclass
class APIKey:
    """API key data structure"""
    key: str
    source: str
    requests_made: int = 0
    rate_limits_hit: int = 0
    last_used: Optional[datetime] = None
    is_valid: bool = True
    cooldown_until: Optional[datetime] = None

    def is_available(self) -> bool:
        """Check if key is available for use"""
        if not self.is_valid:
            return False

        if self.cooldown_until:
            return datetime.utcnow() >= self.cooldown_until

        return True


class APIKeyRotator:
    """Manages API key rotation across sources"""

    def __init__(self):
        self.keys: Dict[str, List[APIKey]] = {
            'reddit': [],
            'producthunt': [],
            'github': []
        }
        self.current_index: Dict[str, int] = {
            'reddit': 0,
            'producthunt': 0,
            'github': 0
        }
        self.locks: Dict[str, asyncio.Lock] = {
            source: asyncio.Lock() for source in self.keys.keys()
        }

    async def initialize(self):
        """Initialize API keys from settings"""
        # Reddit keys
        reddit_keys = settings.get_reddit_keys()
        for client_id, client_secret in reddit_keys:
            key_str = f"{client_id}:{client_secret}"
            self.keys['reddit'].append(APIKey(key=key_str, source='reddit'))

        # Product Hunt keys
        ph_keys = settings.get_producthunt_keys()
        for key in ph_keys:
            self.keys['producthunt'].append(APIKey(key=key, source='producthunt'))

        # GitHub keys
        gh_keys = settings.get_github_keys()
        for key in gh_keys:
            self.keys['github'].append(APIKey(key=key, source='github'))

        # Log initialization
        for source, keys in self.keys.items():
            if keys:
                log.info(f"Initialized {len(keys)} API keys for {source}")
            else:
                log.warning(f"No API keys configured for {source}")

    async def get_key(self, source: str) -> Optional[APIKey]:
        """
        Get next available API key for source

        Args:
            source: Source name (reddit, producthunt, github)

        Returns:
            APIKey object or None if no keys available
        """
        source = source.lower()

        if source not in self.keys:
            log.error(f"Unknown source: {source}")
            return None

        if not self.keys[source]:
            log.warning(f"No API keys configured for {source}")
            return None

        async with self.locks[source]:
            # Try to find available key
            attempts = 0
            while attempts < len(self.keys[source]):
                idx = self.current_index[source]
                key = self.keys[source][idx]

                # Move to next key
                self.current_index[source] = (idx + 1) % len(self.keys[source])

                # Check if key is available
                if key.is_available():
                    key.last_used = datetime.utcnow()
                    key.requests_made += 1
                    return key

                attempts += 1

            # No available keys, return one with shortest cooldown
            keys_with_cooldown = [k for k in self.keys[source] if k.cooldown_until]
            if keys_with_cooldown:
                return min(keys_with_cooldown, key=lambda k: k.cooldown_until)

            # Return first valid key as fallback
            valid_keys = [k for k in self.keys[source] if k.is_valid]
            return valid_keys[0] if valid_keys else None

    async def mark_rate_limited(self, key: APIKey, cooldown_seconds: int = 60):
        """
        Mark key as rate limited

        Args:
            key: APIKey object
            cooldown_seconds: Seconds to wait before using again
        """
        async with self.locks[key.source]:
            key.rate_limits_hit += 1
            key.cooldown_until = datetime.utcnow().timestamp() + cooldown_seconds

            log.warning(
                f"API key for {key.source} rate limited. "
                f"Cooldown: {cooldown_seconds}s. "
                f"Total rate limits: {key.rate_limits_hit}"
            )

    async def mark_invalid(self, key: APIKey):
        """Mark key as invalid (expired/revoked)"""
        async with self.locks[key.source]:
            key.is_valid = False
            log.error(f"API key for {key.source} marked as invalid")

    async def reset_cooldown(self, key: APIKey):
        """Reset cooldown for a key"""
        async with self.locks[key.source]:
            key.cooldown_until = None

    def get_reddit_credentials(self, key: APIKey) -> Tuple[str, str]:
        """
        Parse Reddit credentials from key

        Args:
            key: APIKey with format "client_id:client_secret"

        Returns:
            Tuple of (client_id, client_secret)
        """
        parts = key.key.split(':', 1)
        if len(parts) == 2:
            return parts[0], parts[1]
        return key.key, ""

    def get_stats(self, source: str = None) -> dict:
        """
        Get API key statistics

        Args:
            source: Specific source or None for all sources

        Returns:
            Dictionary of statistics
        """
        if source:
            sources = [source.lower()]
        else:
            sources = self.keys.keys()

        stats = {}

        for src in sources:
            if src not in self.keys:
                continue

            keys = self.keys[src]
            if not keys:
                stats[src] = {"total": 0, "valid": 0, "available": 0}
                continue

            valid = sum(1 for k in keys if k.is_valid)
            available = sum(1 for k in keys if k.is_available())
            total_requests = sum(k.requests_made for k in keys)
            total_rate_limits = sum(k.rate_limits_hit for k in keys)

            stats[src] = {
                "total": len(keys),
                "valid": valid,
                "available": available,
                "total_requests": total_requests,
                "total_rate_limits": total_rate_limits
            }

        return stats
