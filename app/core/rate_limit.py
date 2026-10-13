import asyncio
import time
from collections import defaultdict, deque

from app.core.errors import APIError


class LoginRateLimiter:
    """Small per-process sliding-window limiter; use a shared store across workers."""

    def __init__(self, max_attempts: int = 10, window_seconds: int = 60) -> None:
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self._attempts: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.monotonic()
        async with self._lock:
            attempts = self._attempts[key]
            while attempts and now - attempts[0] >= self.window_seconds:
                attempts.popleft()
            if len(attempts) >= self.max_attempts:
                retry_after = max(1, int(self.window_seconds - (now - attempts[0])))
                raise APIError(
                    429,
                    "login_rate_limited",
                    "Too many login attempts. Try again later.",
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.append(now)
