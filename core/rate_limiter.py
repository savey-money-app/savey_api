"""Rate limiting and concurrency control for API endpoints"""

import asyncio
import time
from collections import defaultdict
from typing import Dict, Tuple
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter with per-user and global limits.
    """

    def __init__(
        self,
        rate: int = 10,  # requests per window
        window: int = 60,  # window in seconds
    ):
        self.rate = rate
        self.window = window
        # user_id -> (last_reset_time, token_count)
        self.buckets: Dict[str, Tuple[float, int]] = defaultdict(lambda: (time.time(), rate))
        self.lock = asyncio.Lock()

    async def is_allowed(self, user_id: str) -> bool:
        """Check if request is allowed for this user."""
        async with self.lock:
            now = time.time()
            last_reset, tokens = self.buckets[user_id]

            # Reset bucket if window has passed
            if now - last_reset >= self.window:
                self.buckets[user_id] = (now, self.rate)
                return True

            # Check if tokens available
            if tokens > 0:
                self.buckets[user_id] = (last_reset, tokens - 1)
                return True

            return False


class ConcurrencyLimiter:
    """
    Limits concurrent requests per user and globally.
    """

    def __init__(
        self,
        max_per_user: int = 3,  # max concurrent requests per user
        max_global: int = 50,  # max total concurrent requests
    ):
        self.max_per_user = max_per_user
        self.max_global = max_global
        self.user_semaphores: Dict[str, asyncio.Semaphore] = {}
        self.global_semaphore = asyncio.Semaphore(max_global)
        self.lock = asyncio.Lock()

    async def get_user_semaphore(self, user_id: str) -> asyncio.Semaphore:
        """Get or create semaphore for user."""
        async with self.lock:
            if user_id not in self.user_semaphores:
                self.user_semaphores[user_id] = asyncio.Semaphore(self.max_per_user)
            return self.user_semaphores[user_id]


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies rate limiting and concurrency control to API endpoints.
    """

    def __init__(
        self,
        app,
        rate_limit_requests: int = 20,  # 20 requests per minute per user
        rate_limit_window: int = 60,
        max_concurrent_per_user: int = 3,
        max_concurrent_global: int = 50,
        excluded_paths: list = None,
    ):
        super().__init__(app)
        self.rate_limiter = RateLimiter(rate=rate_limit_requests, window=rate_limit_window)
        self.concurrency_limiter = ConcurrencyLimiter(
            max_per_user=max_concurrent_per_user,
            max_global=max_concurrent_global,
        )
        self.excluded_paths = excluded_paths or ["/docs", "/redoc", "/openapi.json", "/health"]

    def should_rate_limit(self, path: str) -> bool:
        """Check if path should be rate limited."""
        # Skip static files and docs
        if any(path.startswith(excluded) for excluded in self.excluded_paths):
            return False
        # Rate limit API endpoints
        return path.startswith("/api/v1/")

    def get_user_id_from_request(self, request: Request) -> str:
        """Extract user ID from request. Fallback to IP if not authenticated."""
        # Try to get user ID from state (set by auth dependency)
        user_id = getattr(request.state, "user_id", None)
        if user_id:
            return str(user_id)

        # Fallback to IP address
        client_ip = request.client.host if request.client else "unknown"
        return f"ip:{client_ip}"

    async def dispatch(self, request: Request, call_next):
        """Process request with rate limiting and concurrency control."""
        path = request.url.path

        # Skip non-API paths
        if not self.should_rate_limit(path):
            return await call_next(request)

        user_id = self.get_user_id_from_request(request)

        # Check rate limit
        if not await self.rate_limiter.is_allowed(user_id):
            logger.warning(f"Rate limit exceeded for user {user_id} on {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please slow down your requests.",
                    "retry_after": self.rate_limiter.window,
                },
                headers={"Retry-After": str(self.rate_limiter.window)},
            )

        # Apply concurrency limits
        user_semaphore = await self.concurrency_limiter.get_user_semaphore(user_id)

        # Try to acquire global semaphore
        if not self.concurrency_limiter.global_semaphore.locked():
            await self.concurrency_limiter.global_semaphore.acquire()
        else:
            logger.warning(f"Global concurrency limit reached. User: {user_id}, Path: {path}")
            return JSONResponse(
                status_code=503,
                content={
                    "detail": "Server is at capacity. Please try again in a few seconds.",
                    "retry_after": 5,
                },
                headers={"Retry-After": "5"},
            )

        # Try to acquire user semaphore
        try:
            await asyncio.wait_for(
                user_semaphore.acquire(),
                timeout=1.0,  # Don't wait more than 1 second
            )
        except asyncio.TimeoutError:
            # User has too many concurrent requests
            self.concurrency_limiter.global_semaphore.release()
            logger.warning(f"User concurrency limit exceeded for {user_id} on {path}")
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Too many concurrent requests. Maximum {self.concurrency_limiter.max_per_user} allowed.",
                    "retry_after": 2,
                },
                headers={"Retry-After": "2"},
            )

        try:
            # Process request
            response = await call_next(request)
            return response
        finally:
            # Always release semaphores
            user_semaphore.release()
            self.concurrency_limiter.global_semaphore.release()
