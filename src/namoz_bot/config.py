"""Environment-backed application configuration."""

from datetime import time
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    telegram_bot_token: SecretStr = Field(validation_alias="TELEGRAM_BOT_TOKEN")
    database_url: str = Field(validation_alias="DATABASE_URL")
    gemini_api_key: SecretStr | None = Field(default=None, validation_alias="GEMINI_API_KEY")
    gemini_book_corpus_path: Path | None = Field(
        default=None, validation_alias="GEMINI_BOOK_CORPUS_PATH"
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash-lite",
        validation_alias="GEMINI_MODEL",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    gemini_voice_model: str = Field(
        default="gemini-3.5-flash-lite",
        validation_alias="GEMINI_VOICE_MODEL",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    voice_reminder_cooldown_seconds: int = Field(
        default=20, ge=0, le=3600, validation_alias="VOICE_REMINDER_COOLDOWN_SECONDS"
    )
    gemini_reminder_interval_hours: int = Field(
        default=24,
        ge=0,
        le=168,
        validation_alias="GEMINI_REMINDER_INTERVAL_HOURS",
    )
    gemini_button_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        validation_alias="GEMINI_BUTTON_COOLDOWN_SECONDS",
    )
    timezone: str = Field(default="Asia/Tashkent", validation_alias="TIMEZONE")
    daily_send_time: time = Field(default=time(21, 0), validation_alias="DAILY_SEND_TIME")
    prayer_api_base_url: str = Field(
        default="https://namoz-vaqti.uz",
        validation_alias="PRAYER_API_BASE_URL",
    )
    broadcast_batch_size: int = Field(
        default=500,
        ge=1,
        le=5000,
        validation_alias="BROADCAST_BATCH_SIZE",
    )
    telegram_max_concurrency: int = Field(
        default=10,
        ge=1,
        le=100,
        validation_alias="TELEGRAM_MAX_CONCURRENCY",
    )
    telegram_messages_per_second: float = Field(
        default=25.0,
        gt=0,
        le=30,
        validation_alias="TELEGRAM_MESSAGES_PER_SECOND",
    )
