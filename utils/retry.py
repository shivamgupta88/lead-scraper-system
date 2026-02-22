"""Retry decorators with exponential backoff"""

import asyncio
import functools
from typing import Callable, Type, Tuple
from config.settings import settings
from utils.logger import log


def async_retry(
    max_attempts: int = None,
    backoff_factor: float = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable = None
):
    """
    Async retry decorator with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts (default from settings)
        backoff_factor: Backoff multiplier (default from settings)
        exceptions: Tuple of exceptions to catch
        on_retry: Callback function called on each retry
    """
    if max_attempts is None:
        max_attempts = settings.max_retry_attempts
    if backoff_factor is None:
        backoff_factor = settings.retry_backoff_factor

    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        log.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise

                    # Calculate backoff delay
                    delay = backoff_factor ** (attempt - 1)

                    log.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {str(e)}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    # Call on_retry callback if provided
                    if on_retry:
                        try:
                            await on_retry(attempt, e)
                        except Exception as callback_error:
                            log.error(f"on_retry callback failed: {callback_error}")

                    await asyncio.sleep(delay)

            # This should never be reached, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def sync_retry(
    max_attempts: int = None,
    backoff_factor: float = None,
    exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Synchronous retry decorator with exponential backoff

    Args:
        max_attempts: Maximum number of retry attempts
        backoff_factor: Backoff multiplier
        exceptions: Tuple of exceptions to catch
    """
    if max_attempts is None:
        max_attempts = settings.max_retry_attempts
    if backoff_factor is None:
        backoff_factor = settings.retry_backoff_factor

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import time
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e

                    if attempt == max_attempts:
                        log.error(
                            f"{func.__name__} failed after {max_attempts} attempts: {str(e)}"
                        )
                        raise

                    delay = backoff_factor ** (attempt - 1)

                    log.warning(
                        f"{func.__name__} attempt {attempt}/{max_attempts} failed: {str(e)}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)

            if last_exception:
                raise last_exception

        return wrapper
    return decorator


class CircuitBreaker:
    """Circuit breaker pattern for preventing cascading failures"""

    def __init__(self, failure_threshold: int = 5, timeout: int = 60):
        """
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds before attempting to close circuit
        """
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.failures = 0
        self.last_failure_time = 0
        self.state = "closed"  # closed, open, half-open

    async def call(self, func: Callable, *args, **kwargs):
        """Execute function with circuit breaker protection"""
        if self.state == "open":
            # Check if timeout has passed
            if asyncio.get_event_loop().time() - self.last_failure_time >= self.timeout:
                self.state = "half-open"
                log.info(f"Circuit breaker entering half-open state for {func.__name__}")
            else:
                raise Exception(f"Circuit breaker is OPEN for {func.__name__}")

        try:
            result = await func(*args, **kwargs)

            # Success - reset or close circuit
            if self.state == "half-open":
                self.state = "closed"
                self.failures = 0
                log.info(f"Circuit breaker CLOSED for {func.__name__}")

            return result

        except Exception as e:
            self.failures += 1
            self.last_failure_time = asyncio.get_event_loop().time()

            if self.failures >= self.failure_threshold:
                self.state = "open"
                log.error(
                    f"Circuit breaker OPENED for {func.__name__} "
                    f"after {self.failures} failures"
                )

            raise e

    def reset(self):
        """Manually reset the circuit breaker"""
        self.state = "closed"
        self.failures = 0
        self.last_failure_time = 0
