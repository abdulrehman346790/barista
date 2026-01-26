from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    APP_NAME: str = "Basirat API"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str
    API_V1_PREFIX: str = "/api/v1"

    # Neon PostgreSQL
    DATABASE_URL: str

    # Upstash Redis
    UPSTASH_REDIS_URL: str
    UPSTASH_REDIS_TOKEN: str

    # Firebase
    FIREBASE_PROJECT_ID: str
    FIREBASE_PRIVATE_KEY: str
    FIREBASE_CLIENT_EMAIL: str

    # Huggingface
    HF_TOKEN: str

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
