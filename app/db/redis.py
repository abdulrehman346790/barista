from upstash_redis import Redis
from typing import Optional
import json

from app.config import settings


# Global Redis client
redis_client: Optional[Redis] = None


async def init_redis():
    """Initialize Upstash Redis connection."""
    global redis_client
    redis_client = Redis(
        url=settings.UPSTASH_REDIS_URL,
        token=settings.UPSTASH_REDIS_TOKEN,
    )
    print("Redis (Upstash) initialized")


async def close_redis():
    """Close Redis connection."""
    global redis_client
    redis_client = None
    print("Redis connection closed")


def get_redis() -> Redis:
    """Get Redis client instance."""
    if redis_client is None:
        raise RuntimeError("Redis not initialized. Call init_redis() first.")
    return redis_client


class RedisService:
    """
    Redis service for caching and session management.
    Optimized for Upstash free tier (10k commands/day).
    """

    def __init__(self):
        self.client = get_redis()

    # ==================== OTP Management ====================

    async def store_otp(self, phone: str, otp: str) -> None:
        """Store OTP with 5 minute expiry."""
        key = f"otp:{phone}"
        self.client.setex(key, settings.OTP_EXPIRE_MINUTES * 60, otp)

    async def verify_otp(self, phone: str, otp: str) -> bool:
        """Verify OTP and delete if valid."""
        key = f"otp:{phone}"
        stored_otp = self.client.get(key)
        if stored_otp and stored_otp == otp:
            self.client.delete(key)
            return True
        return False

    # ==================== Session Management ====================

    async def store_refresh_token(self, user_id: str, token: str) -> None:
        """Store refresh token with 7 day expiry."""
        key = f"session:{user_id}"
        self.client.setex(key, settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400, token)

    async def get_refresh_token(self, user_id: str) -> Optional[str]:
        """Get stored refresh token."""
        key = f"session:{user_id}"
        return self.client.get(key)

    async def delete_refresh_token(self, user_id: str) -> None:
        """Delete refresh token (logout)."""
        key = f"session:{user_id}"
        self.client.delete(key)

    # ==================== Rate Limiting ====================

    async def check_swipe_limit(self, user_id: str) -> tuple[bool, int]:
        """
        Check if user has exceeded daily swipe limit.
        Returns (is_allowed, remaining_swipes).
        """
        key = f"ratelimit:swipe:{user_id}"
        count = self.client.get(key)

        if count is None:
            # First swipe of the day
            self.client.setex(key, 86400, "1")  # 24 hour expiry
            return True, settings.SWIPE_LIMIT_PER_DAY - 1

        current_count = int(count)
        if current_count >= settings.SWIPE_LIMIT_PER_DAY:
            return False, 0

        self.client.incr(key)
        return True, settings.SWIPE_LIMIT_PER_DAY - current_count - 1

    # ==================== Caching ====================

    async def cache_discover_queue(self, user_id: str, profile_ids: list[str]) -> None:
        """Cache discover queue for 10 minutes."""
        key = f"discover:{user_id}"
        self.client.setex(key, 600, json.dumps(profile_ids))

    async def get_discover_queue(self, user_id: str) -> Optional[list[str]]:
        """Get cached discover queue."""
        key = f"discover:{user_id}"
        data = self.client.get(key)
        return json.loads(data) if data else None

    # ==================== Online Status ====================

    async def set_online(self, user_id: str) -> None:
        """Mark user as online for 5 minutes."""
        key = f"online:{user_id}"
        self.client.setex(key, 300, "1")

    async def is_online(self, user_id: str) -> bool:
        """Check if user is online."""
        key = f"online:{user_id}"
        return self.client.get(key) is not None
