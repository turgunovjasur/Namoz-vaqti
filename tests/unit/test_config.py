from datetime import time

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
