
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    ENVIRONMENT: Literal["development", "test", "beta", "production"] = "development"
    DB_SSL_CA: str = ""
    RATE_LIMIT_ENABLED: bool = True

    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "maxbud_db"

    JWT_SECRET: str
    JWT_MINUTES: int = 60

    GROQ_API_KEY: str = ""
    GROQ_VISION_MODEL: str = ""
    GROQ_CHAT_MODEL: str = ""
    DEMO_PAYMENTS_ENABLED: bool = False
    FAMILY_PACK_MEMBER_LIMIT: int = 6
    PLAN_PRICES_JSON: str = '{"premium_individual":{"monthly":null,"yearly":null},"family_pack":{"monthly":null,"yearly":null}}'

    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = ""
    RECEIPT_STORAGE_DIR: str = str(BASE_DIR / "private_receipts")

    GOOGLE_CLIENT_ID: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_SECURITY: Literal["starttls", "ssl"] = "starttls"
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_PREMIUM_MONTHLY: str = ""
    STRIPE_PRICE_PREMIUM_YEARLY: str = ""
    STRIPE_PRICE_FAMILY_MONTHLY: str = ""
    STRIPE_PRICE_FAMILY_YEARLY: str = ""
    STRIPE_PORTAL_CONFIGURATION: str = ""
    FRONTEND_ORIGIN: str = "http://localhost:5173"

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    settings = Settings()

    if len(settings.JWT_SECRET.strip()) < 32:
        raise RuntimeError(
            "JWT_SECRET must be at least 32 characters"
        )

    if settings.FAMILY_PACK_MEMBER_LIMIT < 2 or settings.FAMILY_PACK_MEMBER_LIMIT > 50:
        raise RuntimeError("FAMILY_PACK_MEMBER_LIMIT must be between 2 and 50")
    if settings.ENVIRONMENT == "production":
        if settings.DEMO_PAYMENTS_ENABLED:
            raise RuntimeError("Unrestricted demo payments must be disabled in production")
    if settings.ENVIRONMENT in {"beta", "production"}:
        if not settings.FRONTEND_ORIGIN.startswith("https://"):
            raise RuntimeError("Production FRONTEND_ORIGIN must use HTTPS")
        if not settings.DB_SSL_CA:
            raise RuntimeError("Production MySQL requires DB_SSL_CA")
        if not settings.RATE_LIMIT_ENABLED:
            raise RuntimeError("Production rate limiting must be enabled")
    return settings
