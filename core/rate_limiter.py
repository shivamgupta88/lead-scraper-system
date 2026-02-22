"""Token bucket rate limiter with adaptive adjustment"""

import asyncio
import time
from typing import Dict, Optional
from dataclasses import dataclass
from utils.logger import log
from config.sources_config import SOURCE_CONFIG


@dataclass
class TokenBucket:
    """Token bucket for rate limiting"""
    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float

    def refill(self):
        """Refill tokens based on elapsed time"""
        now = time.time()
        elapsed = now - self.last_refill

        # Add tokens based on elapsed time
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens

        Returns:
            True if tokens were consumed, False otherwise
        """
        self.refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True

        return False

    def get_wait_time(self, tokens: int = 1) -> float:
        """Calculate wait time needed for tokens"""
        self.refill()

        if self.tokens >= tokens:
            return 0.0

        tokens_needed = tokens - self.tokens
        return tokens_needed / self.refill_rate


class RateLimiter:
    """Adaptive rate limiter with token bucket algorithm"""

    def __init__(self):
        self.buckets: Dict[str, TokenBucket] = {}
        self.locks: Dict[str, asyncio.Lock] = {}
        self.rate_limit_counters: Dict[str, int] = {}
        self.success_streaks: Dict[str, int] = {}

    async def initialize(self):
        """Initialize rate limiters for all sources"""
        for source, config in SOURCE_CONFIG.items():
            rate_limit = config.get('rate_limit', 60)  # requests per minute

            # Convert to requests per second
            refill_rate = rate_limit / 60.0

            self.buckets[source] = TokenBucket(
                capacity=rate_limit,
                tokens=rate_limit,
                refill_rate=refill_rate,
                last_refill=time.time()
            )

            self.locks[source] = asyncio.Lock()
            self.rate_limit_counters[source] = 0
            self.success_streaks[source] = 0

            log.info(f"Rate limiter initialized for {source}: {rate_limit} req/min")

    async def acquire(self, source: str, tokens: int = 1) -> bool:
        """
        Acquire rate limit tokens

        Args:
            source: Source name
            tokens: Number of tokens to acquire

        Returns:
            True when tokens acquired
        """
        source = source.lower()

        if source not in self.buckets:
            log.warning(f"No rate limiter configured for {source}, allowing request")
            return True

        async with self.locks[source]:
            bucket = self.buckets[source]

            # Try to consume tokens
            if bucket.consume(tokens):
                return True

            # Calculate wait time
            wait_time = bucket.get_wait_time(tokens)

            log.debug(f"Rate limit reached for {source}, waiting {wait_time:.2f}s")

        # Wait outside the lock
        await asyncio.sleep(wait_time)

        # Try again
        async with self.locks[source]:
            bucket.consume(tokens)
            return True

    async def handle_429(self, source: str, retry_after: Optional[int] = None):
        """
        Handle 429 rate limit response

        Args:
            source: Source name
            retry_after: Retry-After header value in seconds
        """
        source = source.lower()

        if source not in self.buckets:
            return

        async with self.locks[source]:
            # Increment rate limit counter
            self.rate_limit_counters[source] = self.rate_limit_counters.get(source, 0) + 1
            self.success_streaks[source] = 0

            # Reduce rate limit capacity by 20%
            bucket = self.buckets[source]
            old_capacity = bucket.capacity
            bucket.capacity *= 0.8
            bucket.refill_rate = bucket.capacity / 60.0  # maintain per-minute rate
            bucket.tokens = min(bucket.tokens, bucket.capacity)

            log.warning(
                f"Rate limit hit for {source}. "
                f"Reduced capacity: {old_capacity:.0f} -> {bucket.capacity:.0f} req/min. "
                f"Total 429s: {self.rate_limit_counters[source]}"
            )

            # If retry_after provided, empty the bucket and set refill time
            if retry_after:
                bucket.tokens = 0
                bucket.last_refill = time.time() + retry_after
                log.info(f"Honoring Retry-After: {retry_after}s for {source}")

    async def record_success(self, source: str):
        """
        Record successful request

        Gradually increase rate limit after sustained success
        """
        source = source.lower()

        if source not in self.buckets:
            return

        async with self.locks[source]:
            # Increment success streak
            self.success_streaks[source] = self.success_streaks.get(source, 0) + 1

            # After 100 successful requests, increase capacity by 5%
            if self.success_streaks[source] >= 100:
                bucket = self.buckets[source]
                config = SOURCE_CONFIG.get(source, {})
                max_rate = config.get('rate_limit', 60)

                # Don't exceed original max
                if bucket.capacity < max_rate:
                    old_capacity = bucket.capacity
                    bucket.capacity = min(max_rate, bucket.capacity * 1.05)
                    bucket.refill_rate = bucket.capacity / 60.0

                    log.info(
                        f"Increased rate limit for {source}: "
                        f"{old_capacity:.0f} -> {bucket.capacity:.0f} req/min"
                    )

                # Reset streak
                self.success_streaks[source] = 0

    def get_current_rate(self, source: str) -> float:
        """Get current rate limit for source (requests per minute)"""
        source = source.lower()

        if source not in self.buckets:
            return 0.0

        return self.buckets[source].capacity

    def get_stats(self, source: str = None) -> dict:
        """Get rate limiter statistics"""
        if source:
            sources = [source.lower()]
        else:
            sources = self.buckets.keys()

        stats = {}

        for src in sources:
            if src not in self.buckets:
                continue

            bucket = self.buckets[src]
            bucket.refill()

            config = SOURCE_CONFIG.get(src, {})
            max_rate = config.get('rate_limit', 60)

            stats[src] = {
                "current_rate": round(bucket.capacity, 2),
                "max_rate": max_rate,
                "tokens_available": round(bucket.tokens, 2),
                "rate_limits_hit": self.rate_limit_counters.get(src, 0),
                "success_streak": self.success_streaks.get(src, 0)
            }

        return stats
