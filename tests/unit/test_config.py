from datetime import time

import pytest
from pydantic import ValidationError

from namoz_bot.config import Settings


def test_settings_use_tashkent_schedule_defaults() -> None:
    settings = Settings(
        telegram_bot_token="test-token",
        database_url="postgresql+asyncpg://user:pass@db/database",
    )

    assert settings.timezone == "Asia/Tashkent"
    assert settings.daily_send_time == time(21, 0)
    assert settings.prayer_api_base_url == "https://namoz-vaqti.uz"
    assert settings.broadcast_batch_size == 500
    assert settings.telegram_max_concurrency == 10
    assert settings.telegram_messages_per_second == 25.0


def test_settings_accept_environment_style_aliases() -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@db/database",
            "PRAYER_API_BASE_URL": "https://prayer-api.example",
            "DAILY_SEND_TIME": "20:30",
            "BROADCAST_BATCH_SIZE": "200",
            "TELEGRAM_MAX_CONCURRENCY": "8",
            "TELEGRAM_MESSAGES_PER_SECOND": "20",
        }
    )

    assert settings.daily_send_time == time(20, 30)
    assert settings.prayer_api_base_url == "https://prayer-api.example"
    assert settings.broadcast_batch_size == 200
    assert settings.telegram_max_concurrency == 8
    assert settings.telegram_messages_per_second == 20.0


def test_settings_read_gemini_key_without_exposing_it() -> None:
    settings = Settings(
        _env_file=None,
        TELEGRAM_BOT_TOKEN="test-token",
        DATABASE_URL="sqlite+aiosqlite:///:memory:",
        GEMINI_API_KEY="secret-gemini-test-key",
        GEMINI_MODEL="gemini-3.5-flash-lite",
    )

    assert settings.gemini_api_key.get_secret_value() == "secret-gemini-test-key"
    assert "secret-gemini-test-key" not in repr(settings)
    assert settings.gemini_model == "gemini-3.5-flash-lite"


def test_settings_reject_gemini_model_with_url_components() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            TELEGRAM_BOT_TOKEN="test-token",
            DATABASE_URL="sqlite+aiosqlite:///:memory:",
            GEMINI_MODEL="../models/other?key=secret",
        )


def test_settings_accept_gemini_reminder_interval_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_REMINDER_INTERVAL_HOURS", "6")
    settings = Settings(
        _env_file=None,
        telegram_bot_token="test-token",
        database_url="sqlite+aiosqlite:///:memory:",
    )

    assert settings.gemini_reminder_interval_hours == 6


def test_settings_reject_fractional_hour_interval():
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            telegram_bot_token="test-token",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_REMINDER_INTERVAL_HOURS=1.5,
        )


def test_settings_reject_negative_gemini_reminder_interval() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            telegram_bot_token="test-token",
            database_url="sqlite+aiosqlite:///:memory:",
            GEMINI_REMINDER_INTERVAL_HOURS=-1,
        )
