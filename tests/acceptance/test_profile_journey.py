import pytest

from namoz_bot.config import Settings
from namoz_bot.infrastructure.orm import Base
from namoz_bot.main import create_application
from tests.acceptance.test_voice_reminder_journey import VoiceJourney


@pytest.fixture
async def profile_journey(tmp_path):
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'profiles.db'}",
            MAIN_AGENT_ENABLED=False,
            GEMINI_API_KEY=None,
            ADMIN_TELEGRAM_IDS=[7],
        )
    )
    async with app.db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    journey = VoiceJourney(app)
    journey.seed_legacy_access = False
    await journey.text("/start", user=8)
    await journey.text("/start")
    yield journey
    await app.dispatcher.storage.close()
    await app.close()


async def test_admin_assigns_subset_user_sees_own_roles_after_saved_restart(profile_journey):
    j = profile_journey
    await j.text("👤 Profil")
    assert "admin" in j.last.text.lower()
    await j.click("👥 Foydalanuvchilar")
    await j.click("8")
    await j.click("Hisobchi")
    assert "Amalga oshgan xarajat" in j.last.text
    await j.click("⏸ Rol o‘chiq")
    await j.click("⬜ Xarajat yozish")
    old = j.button("💾 Saqlash")
    assert len(old.encode()) <= 64
    await j.click(data=old)
    assert "saqlandi" in j.last.text.lower()
    await j.text("👤 Profil", user=8)
    assert "Hisobchi" in j.last.text and "Xarajat yozish" in j.last.text
    assert "Kirim yozish" not in j.last.text
    assert "Foydalanuvchilar" not in j.last.text
    await j.click(data=old, user=8)
    assert "eskirgan" in j.last.text.lower() or "tegishli" in j.last.text.lower()
    await j.text("👤 Profil", user=8)
    assert "Xarajat yozish" in j.last.text


async def test_fresh_user_has_only_profile_help_and_no_admin_controls(profile_journey):
    j = profile_journey
    labels = [b.text for row in j.session.reply_keyboards[8].keyboard for b in row]
    assert labels == ["👤 Profil", "ℹ️ Yordam"]
    await j.text("/profile", user=8)
    assert "yoqilmagan" in j.last.text.lower()
    assert j.last.reply_markup is None or not j.last.reply_markup.inline_keyboard
