
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_USER: str
    DB_PASSWORD: str
    DB_NAME: str = "maxbud_db"

    JWT_SECRET: str
    JWT_MINUTES: int = 60

    GOOGLE_CLIENT_ID: str = ""
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

    return settings
