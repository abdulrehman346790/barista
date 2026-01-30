from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional, List


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "Basirat API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"

    # CORS - Allowed origins (comma-separated in env)
    CORS_ORIGINS: str = "http://localhost:8081,http://localhost:19006,http://localhost:3000,exp://localhost:8081"

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string."""
        if self.ENVIRONMENT == "development" and self.DEBUG:
            # In development, allow common dev origins
            return [
                "http://localhost:8081",
                "http://localhost:19006",
                "http://localhost:3000",
                "http://127.0.0.1:8081",
                "http://127.0.0.1:19006",
                "http://127.0.0.1:3000",
                "exp://localhost:8081",
                "exp://127.0.0.1:8081",
            ]
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    # Neon PostgreSQL
    DATABASE_URL: str

    # Upstash Redis
    UPSTASH_REDIS_URL: str
    UPSTASH_REDIS_TOKEN: str

    # Firebase (optional - app works without it for basic testing)
    FIREBASE_PROJECT_ID: str = ""
    FIREBASE_PRIVATE_KEY: str = ""
    FIREBASE_CLIENT_EMAIL: str = ""

    # Huggingface (optional - AI features disabled if not set)
    HF_TOKEN: str = ""

    # JWT Settings
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    ALGORITHM: str = "HS256"

    # Rate Limiting
    SWIPE_LIMIT_PER_DAY: int = 100
    API_RATE_LIMIT_PER_MINUTE: int = 100

    # OTP Settings
    OTP_EXPIRE_MINUTES: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()


settings = get_settings()
