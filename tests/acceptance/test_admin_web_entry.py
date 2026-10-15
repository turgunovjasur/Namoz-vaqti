from urllib.parse import parse_qs, urlsplit

import pytest

from namoz_bot.config import Settings
from namoz_bot.infrastructure.orm import Base
from namoz_bot.main import create_application
from tests.acceptance.test_voice_reminder_journey import VoiceJourney


@pytest.fixture
async def admin_journey(tmp_path):
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'admin.db'}",
            MAIN_AGENT_ENABLED=False,
            GEMINI_API_KEY=None,
            ADMIN_TELEGRAM_IDS=[7],
            ADMIN_WEB_URL="https://admin.example",
        )
    )
    async with app.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    journey = VoiceJourney(app)
    journey.seed_legacy_access = False
    await journey.text("/start")
    await journey.text("/start", user=8)
    yield journey
    await app.dispatcher.storage.close()
    await app.close()


async def test_admin_command_has_one_use_link_and_ordinary_user_has_no_link(admin_journey):
    j = admin_journey
    await j.text("/admin")
    markup = j.last.reply_markup
    assert markup and markup.inline_keyboard
    url = markup.inline_keyboard[0][0].url
    assert urlsplit(url).netloc == "admin.example"
    token = parse_qs(urlsplit(url).fragment)["login"][0]
    auth = j.app.dispatcher["admin_web_auth"]
    session = await auth.exchange_ticket(token)
    assert (await auth.authenticate(session)).telegram_user_id == 7
    await j.text("/admin", user=8)
    assert j.last.reply_markup is None
    assert "administrator" in j.last.text.lower()


async def test_admin_profile_web_button_issues_fresh_link(admin_journey):
    j = admin_journey
    await j.text("/profile")
    await j.click("🌐 Admin web panel")
    assert j.last.reply_markup.inline_keyboard[0][0].url.startswith("https://admin.example/#login=")


def test_local_admin_settings_use_only_test_credentials(monkeypatch):
    from namoz_bot.admin import load_settings

    monkeypatch.setenv("TEST_TELEGRAM_BOT_TOKEN", "123456:test-only")
    monkeypatch.setenv("TEST_DATABASE_URL", "sqlite+aiosqlite:///test-only.db")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456:production")
    monkeypatch.setenv("DATABASE_URL", "sqlite+aiosqlite:///production.db")
    settings = load_settings(local=True)
    assert settings.telegram_bot_token.get_secret_value() == "123456:test-only"
    assert settings.database_url == "sqlite+aiosqlite:///test-only.db"
