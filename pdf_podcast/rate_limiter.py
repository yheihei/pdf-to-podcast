"""Rate limiter for Gemini API requests to handle rate limits."""

import asyncio
import logging
import time
import random
from typing import Any, Callable, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    rpm_limit: int = 15  # Free tier default
    max_retries: int = 5
    base_delay: float = 2.0
    max_delay: float = 60.0
    jitter: bool = True


class GeminiRateLimiter:
    """Rate limiter for Gemini API with exponential backoff retry."""
    
    def __init__(self, config: Optional[RateLimitConfig] = None):
        """Initialize rate limiter.
        
        Args:
            config: Rate limiting configuration
        """
        self.config = config or RateLimitConfig()
        self.request_times = []
        self.lock = asyncio.Lock()
        
        logger.info(f"Rate limiter initialized with {self.config.rpm_limit} RPM limit")
    
    async def acquire(self) -> None:
        """Acquire permission to make a request, respecting RPM limits."""
        async with self.lock:
            now = time.time()
            
            # Remove requests older than 1 minute
            cutoff_time = now - 60.0
            self.request_times = [t for t in self.request_times if t > cutoff_time]
            
            # Check if we're at the limit
            if len(self.request_times) >= self.config.rpm_limit:
                # Calculate how long to wait
                oldest_request = min(self.request_times)
                wait_time = 60.0 - (now - oldest_request)
                
                if wait_time > 0:
                    logger.info(f"Rate limit reached, waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
            
            # Record this request
            self.request_times.append(time.time())
    
    async def call_with_backoff(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """Call function with exponential backoff retry.
        
        Args:
            func: Function to call
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result
            
        Raises:
            Exception: If all retries are exhausted
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries + 1):
            try:
                # Wait for rate limit permission
                await self.acquire()
                
                # Call the function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
                    
            except Exception as e:
                last_exception = e
                error_msg = str(e).lower()
                
                # Check if it's a rate limit error
                if any(indicator in error_msg for indicator in ["429", "rate limit", "quota", "too many requests"]):
                    if attempt < self.config.max_retries:
                        delay = self._calculate_backoff_delay(attempt)
                        logger.warning(f"Rate limit error (attempt {attempt + 1}/{self.config.max_retries + 1}), waiting {delay:.1f}s: {e}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Rate limit retries exhausted after {self.config.max_retries + 1} attempts")
                        raise Exception("Rate limit exceeded: Maximum retries reached") from e
                
                # Check if it's a server error (5xx)
                elif any(code in error_msg for code in ["500", "502", "503", "504", "server error"]):
                    if attempt < self.config.max_retries:
                        delay = self._calculate_backoff_delay(attempt, is_server_error=True)
                        logger.warning(f"Server error (attempt {attempt + 1}/{self.config.max_retries + 1}), waiting {delay:.1f}s: {e}")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Server error retries exhausted after {self.config.max_retries + 1} attempts")
                        raise
                
                # For other errors, don't retry
                else:
                    logger.error(f"Non-retryable error: {e}")
                    raise
        
        # This should never be reached, but just in case
        raise last_exception or Exception("Unknown error in rate limiter")
    
    def _calculate_backoff_delay(self, attempt: int, is_server_error: bool = False) -> float:
        """Calculate delay for exponential backoff.
        
        Args:
            attempt: Current attempt number (0-based)
            is_server_error: Whether this is a server error (shorter delays)
            
        Returns:
            Delay in seconds
        """
        if is_server_error:
            # Shorter delays for server errors
            delay = min(self.config.base_delay * (2 ** attempt), 10.0)
        else:
            # Exponential backoff for rate limit errors
            delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
        
        # Add jitter to avoid thundering herd
        if self.config.jitter:
            jitter_amount = delay * 0.1  # 10% jitter
            delay += random.uniform(-jitter_amount, jitter_amount)
        
        return max(delay, 0.1)  # Minimum 0.1 second delay
    
    def get_stats(self) -> dict:
        """Get rate limiter statistics.
        
        Returns:
            Dictionary with statistics
        """
        now = time.time()
        cutoff_time = now - 60.0
        recent_requests = [t for t in self.request_times if t > cutoff_time]
        
        return {
            "rpm_limit": self.config.rpm_limit,
            "requests_last_minute": len(recent_requests),
            "remaining_capacity": max(0, self.config.rpm_limit - len(recent_requests))
        }