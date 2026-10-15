import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.application.workforce.authorization import access_context
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.infrastructure.orm import RoleCapabilityRecord
from tests.acceptance.test_menu_agent_journey import menu_journey as _conversation
from tests.acceptance.test_menu_agent_journey import routes as routes
from tests.integration.test_agent_sessions import NOW, finance_request
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant

conversation = _conversation


async def test_service_write_boundary_rechecks_without_menu(access_setup, store):
    profiles, access, user, other = access_setup
    repo, _, _, _ = store
    with access_context(access, user_id=user, telegram_user_id=7):
        with pytest.raises(AccessDenied):
            async with repo.transaction(user, None, now=NOW) as tx:
                await tx.ledger.record(user, finance_request(), "denied", NOW)
        await grant(profiles, user, user, "accounting", {"finance.income"})
        async with repo.transaction(user, None, now=NOW) as tx:
            with pytest.raises(AccessDenied):
                await tx.ledger.record(other, finance_request(), "wrong-owner", NOW)
            entry = await tx.ledger.record(user, finance_request(), "allowed", NOW)
            assert entry.amount == finance_request().amount


async def test_fresh_start_does_not_grant_roles_and_manual_path_denies(conversation):
    conversation.seed_legacy_access = False
    await conversation.text("/start", user=8)
    factory = async_sessionmaker(conversation.app.db_engine, expire_on_commit=False)
    access = conversation.app.dispatcher["access_service"]
    profile = conversation.app.dispatcher["profile_repository"]
    from namoz_bot.infrastructure.orm import UserRecord

    async with factory() as session:
        owner = await session.scalar(select(UserRecord.id).where(UserRecord.telegram_user_id == 8))
    assert not (await profile.get_profile(owner)).roles
    assert not await access.available_roles(owner)
    await conversation.text("📅 Bugungi jadval", user=8)
    assert "yoqilmagan" in conversation.last.text


async def test_old_voice_approval_cannot_bypass_revoked_grant(conversation, routes):
    await conversation.voice()
    yes = conversation.button("✅ Ha")
    factory = async_sessionmaker(conversation.app.db_engine, expire_on_commit=False)
    async with factory.begin() as session:
        await session.execute(
            delete(RoleCapabilityRecord).where(
                RoleCapabilityRecord.capability_id == "finance.expense"
            )
        )
    await conversation.click(data=yes)
    assert "yoqilmagan" in conversation.last.text or "o‘chirilgan" in conversation.last.text
    from namoz_bot.infrastructure.orm import FinanceEntryRecord

    async with factory() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
