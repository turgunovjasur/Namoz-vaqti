from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.domain.workforce.roles import RoleWrite
from namoz_bot.infrastructure.orm import RoleAssignmentRecord, RoleCapabilityRecord
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.acceptance.test_accounting_journey import ledger_journey as ledger_journey
from tests.integration.test_dynamic_roles import ValidModels


async def custom_agent(j, caps, name="Mening agentim"):
    j.seed_legacy_access = False
    factory = async_sessionmaker(j.app.db_engine, expire_on_commit=False)
    owner = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    profiles = j.app.dispatcher["profile_repository"]
    profiles.admin_telegram_ids = frozenset({7})
    catalog = j.app.dispatcher["role_catalog_service"]
    catalog.models.catalog = ValidModels(None, ("voice-test-model",))
    role = await catalog.create(
        owner.id,
        RoleWrite(
            name=name,
            description="Maxsus vazifa",
            model_id="voice-test-model",
            capability_ids=frozenset(caps),
        ),
    )
    async with factory.begin() as s:
        await s.execute(
            delete(RoleCapabilityRecord).where(RoleCapabilityRecord.user_id == owner.id)
        )
        await s.execute(
            delete(RoleAssignmentRecord).where(RoleAssignmentRecord.user_id == owner.id)
        )
    async with j.app.dispatcher["role_catalog"].scope():
        await profiles.set_grants(
            actor_id=owner.id,
            user_id=owner.id,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset(caps),
            expected_revision=0,
        )
    return catalog, owner.id, role


def reply_labels(j):
    return [b.text for row in j.session.reply_keyboards[7].keyboard for b in row]


def inline_labels(j):
    return [b.text for row in j.last.reply_markup.inline_keyboard for b in row]


async def test_custom_finance_menu_rename_and_revoked_callback(ledger_journey):
    j = ledger_journey
    catalog, owner, role = await custom_agent(j, {"finance.report"}, "Byudjet yordamchim")
    await j.text("/start")
    assert reply_labels(j) == ["💰 Byudjet yordamchim"]
    await j.text("💰 Byudjet yordamchim")
    assert "Byudjet yordamchim" in j.last.text
    assert "📊 Oy hisoboti" in inline_labels(j)
    assert "💳 Umumiy balans" not in inline_labels(j)
    assert "➕ Kirim yozish" not in inline_labels(j)
    role = await catalog.update(
        owner,
        role.id,
        RoleWrite(
            name="Yangi hisobchi",
            description=role.description,
            model_id="voice-test-model",
            capability_ids=frozenset(role.capability_ids),
            expected_revision=role.revision,
            expected_model_version=1,
        ),
    )
    await j.text("/start")
    assert reply_labels(j) == ["💰 Yangi hisobchi"]
    await j.text("💰 Yangi hisobchi")
    old = j.button("📊 Oy hisoboti")
    await catalog.archive(owner, role.id, expected_revision=role.revision)
    await j.click(data=old)
    assert "o‘chirilgan" in j.last.text
    await j.text("/start")
    assert 7 not in j.session.reply_keyboards


async def test_mixed_agent_exposes_granted_skills_and_switches_from_form(ledger_journey):
    j = ledger_journey
    _, _, _role = await custom_agent(j, {"reminder.create", "finance.report", "prayer.set_region"})
    await j.text("/start")
    await j.text("📅 Mening agentim")
    assert set(reply_labels(j)) == {
        "➕ Eslatma qo‘shish",
        "📊 Oy hisoboti",
        "📍 Hududni o‘zgartirish",
        "⬅️ Asosiy menyu",
    }
    await j.text("➕ Eslatma qo‘shish")
    assert "matn" in j.last.text.lower()
    await j.text("📊 Oy hisoboti")
    assert "Oy farqi" in j.last.text
    await j.text("📍 Hududni o‘zgartirish")
    assert "hudud" in j.last.text.lower() or "viloyat" in j.last.text.lower()


async def test_write_only_region_and_settings_skills_can_finish_forms(ledger_journey, monkeypatch):
    from datetime import datetime

    from namoz_bot.domain.reminders import TASHKENT
    from namoz_bot.main import NamozVaqtiApiClient
    from tests.acceptance.harness import FakeScheduleProvider

    async def schedule(self, region_code):
        return await FakeScheduleProvider().get_for_date(region_code, datetime.now(TASHKENT).date())

    monkeypatch.setattr(NamozVaqtiApiClient, "get_today", schedule)
    j = ledger_journey
    await custom_agent(j, {"prayer.set_region", "settings.set_daily"})
    await j.text("/start")
    await j.text("📅 Mening agentim")
    await j.text("📍 Hududni o‘zgartirish")
    await j.click(data="region-group:samarqand-viloyati")
    # Pick a concrete region through the existing authorized callback.
    await j.click(data="region:Samarqand")
    factory = async_sessionmaker(j.app.db_engine, expire_on_commit=False)
    updated = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    assert updated.region_code == "Samarqand"
    await j.text("🕒 Kunlik jadval yuborish vaqti")
    await j.click(data="daily:set:18:00")
    assert "18:00" in j.last.text


async def test_fallback_skill_retires_active_reminder_form(ledger_journey):
    j = ledger_journey
    await custom_agent(j, {"reminder.create", "prayer.reset_offsets"})
    await j.text("/start")
    await j.text("📅 Mening agentim")
    await j.text("➕ Eslatma qo‘shish")
    state = j.app.dispatcher.fsm.get_context(bot=j.app.bot, chat_id=7, user_id=7)
    assert await state.get_state() is not None
    await j.text("▶️ Farqlarni nolga qaytarish")
    assert await state.get_state() is None
    assert "creation_token" not in await state.get_data()


async def test_excerpt_only_agent_does_not_offer_interval_after_action(ledger_journey):
    j = ledger_journey
    await custom_agent(j, {"nasihat.excerpt"})
    await j.text("/start")
    await j.text("📖 Mening agentim")
    await j.text("📖 Diniy eslatma")
    assert set(reply_labels(j)) == {"📖 Diniy eslatma", "⬅️ Asosiy menyu"}
