"""Environment-backed application configuration."""

from datetime import time

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
    timezone: str = Field(default="Asia/Tashkent", validation_alias="TIMEZONE")
    daily_send_time: time = Field(default=time(21, 0), validation_alias="DAILY_SEND_TIME")
    islom_api_base_url: str = Field(
        default="https://islomapi.uz",
        validation_alias="ISLOM_API_BASE_URL",
    )
