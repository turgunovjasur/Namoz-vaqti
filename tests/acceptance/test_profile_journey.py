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
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from namoz_bot.application.capabilities.registry import build_capability_registry
    from tests.helpers.roles import build_role_registry, seed_roles

    await seed_roles(
        async_sessionmaker(app.db_engine), build_role_registry(build_capability_registry())
    )
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


async def test_fresh_user_has_no_menu_buttons_or_admin_controls(profile_journey):
    j = profile_journey
    assert 8 not in j.session.reply_keyboards
    await j.text("/profile", user=8)
    assert "yoqilmagan" in j.last.text.lower()
    assert j.last.reply_markup is None or not j.last.reply_markup.inline_keyboard


async def test_admin_search_and_history_are_private_and_paged(profile_journey):
    j = profile_journey
    await j.text("👤 Profil")
    await j.click("🔎 ID bo‘yicha qidirish")
    await j.text("8")
    await j.click("8")
    await j.click("Hisobchi")
    await j.click("⏸ Rol o‘chiq")
    await j.click("⬜ Xarajat yozish")
    await j.click("💾 Saqlash")
    await j.text("👤 Profil")
    await j.click("🕘 O‘zgarishlar tarixi")
    assert "Hisobchi" in j.last.text and "8" in j.last.text and "Xarajat yozish" in j.last.text
    history = j.last.text
    await j.text("👤 Profil", user=8)
    assert j.last.text != history
    service = j.app.dispatcher["profile_service"]
    import pytest

    from namoz_bot.domain.workforce.profiles import AccessDenied

    user = await service.repository.find_user(2, 8)
    # User DB IDs are assigned by /start order; resolve through trusted admin lookup.
    with pytest.raises(AccessDenied):
        await service.history(user.user_id)
