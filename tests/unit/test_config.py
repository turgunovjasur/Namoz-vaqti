from datetime import time

from namoz_bot.config import Settings


def test_settings_use_tashkent_schedule_defaults() -> None:
    settings = Settings(
        telegram_bot_token="test-token",
        database_url="postgresql+asyncpg://user:pass@db/database",
    )

    assert settings.timezone == "Asia/Tashkent"
    assert settings.daily_send_time == time(21, 0)
    assert settings.islom_api_base_url == "https://islomapi.uz"


def test_settings_accept_environment_style_aliases() -> None:
    settings = Settings.model_validate(
        {
            "TELEGRAM_BOT_TOKEN": "test-token",
            "DATABASE_URL": "postgresql+asyncpg://user:pass@db/database",
            "DAILY_SEND_TIME": "20:30",
        }
    )

    assert settings.daily_send_time == time(20, 30)
