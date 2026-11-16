from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    database_url: str = Field(
        default="postgresql+psycopg://events:events@localhost:5432/events",
        validation_alias=AliasChoices(
            "DATABASE_URL",
            "POSTGRES_CONNECTION_STRING",
        ),
    )

    @field_validator("database_url")
    @classmethod
    def normalize_database_url(cls, value: str) -> str:
        if value.startswith("postgres://"):
            return value.replace("postgres://", "postgresql+psycopg://", 1)
        if value.startswith("postgresql://"):
            return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    events_api_url: str = "https://events-provider.dev-2.python-labs.ru"
    lms_token: str = ""
    sync_interval_seconds: int = 86400
    enable_background_sync: bool = True
    provider_timeout: float = 20.0

    model_config = SettingsConfigDict(env_file=ROOT / ".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
