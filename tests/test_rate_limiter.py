"""Tests for GeminiRateLimiter class."""

import asyncio
import pytest
import time
from unittest.mock import AsyncMock, patch

from pdf_podcast.rate_limiter import GeminiRateLimiter, RateLimitConfig


class TestGeminiRateLimiter:
    """Test cases for GeminiRateLimiter class."""
    
    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        config = RateLimitConfig(rpm_limit=2, max_retries=2, base_delay=1.0, jitter=False)
        return GeminiRateLimiter(config)
    
    @pytest.mark.asyncio
    async def test_acquire_basic(self, rate_limiter):
        """Test basic acquire functionality."""
        # Should succeed without delay
        await rate_limiter.acquire()
        assert len(rate_limiter.request_times) == 1
        
        # Second request should also succeed
        await rate_limiter.acquire()
        assert len(rate_limiter.request_times) == 2
    
    @pytest.mark.asyncio
    async def test_acquire_rate_limit(self, rate_limiter):
        """Test rate limiting behavior."""
        # Fill up the rate limit
        await rate_limiter.acquire()
        await rate_limiter.acquire()
        
        # Third request should be delayed
        start_time = time.time()
        await rate_limiter.acquire()
        elapsed = time.time() - start_time
        
        # Should have waited due to rate limit
        assert elapsed > 0.05  # Some delay expected
    
    @pytest.mark.asyncio
    async def test_call_with_backoff_success(self, rate_limiter):
        """Test successful function call with backoff."""
        mock_func = AsyncMock(return_value="success")
        
        result = await rate_limiter.call_with_backoff(mock_func, "arg1", key="value")
        
        assert result == "success"
        mock_func.assert_called_once_with("arg1", key="value")
    
    @pytest.mark.asyncio
    async def test_call_with_backoff_rate_limit_retry(self, rate_limiter):
        """Test retry behavior on rate limit error."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("429 rate limit exceeded"),
            "success"
        ]
        
        result = await rate_limiter.call_with_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_call_with_backoff_server_error_retry(self, rate_limiter):
        """Test retry behavior on server error."""
        mock_func = AsyncMock()
        mock_func.side_effect = [
            Exception("500 server error"),
            "success"
        ]
        
        result = await rate_limiter.call_with_backoff(mock_func)
        
        assert result == "success"
        assert mock_func.call_count == 2
    
    @pytest.mark.asyncio
    async def test_call_with_backoff_non_retryable_error(self, rate_limiter):
        """Test non-retryable error handling."""
        mock_func = AsyncMock(side_effect=ValueError("Invalid input"))
        
        with pytest.raises(ValueError):
            await rate_limiter.call_with_backoff(mock_func)
        
        # Should not retry on non-retryable errors
        assert mock_func.call_count == 1
    
    @pytest.mark.asyncio
    async def test_call_with_backoff_max_retries_exceeded(self, rate_limiter):
        """Test behavior when max retries are exceeded."""
        mock_func = AsyncMock(side_effect=Exception("429 rate limit"))
        
        with pytest.raises(Exception, match="Rate limit exceeded"):
            await rate_limiter.call_with_backoff(mock_func)
        
        # Should try max_retries + 1 times
        assert mock_func.call_count == rate_limiter.config.max_retries + 1
    
    def test_calculate_backoff_delay(self, rate_limiter):
        """Test backoff delay calculation."""
        # Rate limit error (longer delay)
        delay1 = rate_limiter._calculate_backoff_delay(0, is_server_error=False)
        delay2 = rate_limiter._calculate_backoff_delay(1, is_server_error=False)
        
        assert delay1 > 0
        assert delay2 > delay1  # Exponential backoff
        
        # Server error (shorter delay)
        delay3 = rate_limiter._calculate_backoff_delay(0, is_server_error=True)
        delay4 = rate_limiter._calculate_backoff_delay(1, is_server_error=True)
        
        assert delay3 > 0
        assert delay4 > delay3
        assert delay3 < delay1  # Server errors have shorter delays
    
    def test_get_stats(self, rate_limiter):
        """Test statistics generation."""
        stats = rate_limiter.get_stats()
        
        assert "rpm_limit" in stats
        assert "requests_last_minute" in stats
        assert "remaining_capacity" in stats
        assert stats["rpm_limit"] == 2
        assert stats["requests_last_minute"] == 0
        assert stats["remaining_capacity"] == 2
        
        # Add some requests
        rate_limiter.request_times = [time.time(), time.time()]
        stats = rate_limiter.get_stats()
        
        assert stats["requests_last_minute"] == 2
        assert stats["remaining_capacity"] == 0
    
    def test_config_defaults(self):
        """Test default configuration values."""
        config = RateLimitConfig()
        
        assert config.rpm_limit == 15
        assert config.max_retries == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 60.0
        assert config.jitter is True