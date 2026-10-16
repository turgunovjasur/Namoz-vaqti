from datetime import UTC, datetime

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.application.accounting import LedgerService
from namoz_bot.domain.accounting import AccountingRequest
from namoz_bot.domain.workforce.roles import RoleWrite
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository
from namoz_bot.infrastructure.orm import RoleAssignmentRecord, RoleCapabilityRecord
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.acceptance.test_accounting_journey import (
    accounting_input,
    entries,
    open_finance,
    response,
)
from tests.acceptance.test_accounting_journey import (
    finance_route as finance_route,
)
from tests.acceptance.test_accounting_journey import (
    ledger_journey as ledger_journey,
)
from tests.integration.test_dynamic_roles import ValidModels


@pytest.mark.parametrize("operation", ["expense", "undo"])
async def test_custom_finance_role_manual_write_and_receipt(
    ledger_journey, finance_route, operation
):
    j = ledger_journey
    j.seed_legacy_access = False
    factory = async_sessionmaker(j.app.db_engine, expire_on_commit=False)
    owner = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    profiles = j.app.dispatcher["profile_repository"]
    profiles.admin_telegram_ids = frozenset({7})
    service = j.app.dispatcher["role_catalog_service"]
    service.models.catalog = ValidModels(None, ("voice-test-model",))
    role = await service.create(
        owner.id,
        RoleWrite(
            name="Custom finance",
            description="Only permitted ledger actions",
            model_id="voice-test-model",
            capability_ids=frozenset({f"finance.{operation}"}),
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
            capability_ids=frozenset({f"finance.{operation}"}),
            expected_revision=0,
        )
    if operation == "undo":
        entry = await LedgerService(SqlAlchemyLedgerRepository(factory)).record(
            owner.id,
            AccountingRequest.model_validate(accounting_input()),
            "seed",
            datetime.now(UTC),
        )
    await open_finance(j)
    assert "yoqilmagan" not in j.last.text
    if operation == "expense":
        finance_route.respond(
            200,
            json=response(
                accounting_input(
                    intent="expense", amount=120000, category="kiyim", description="Kiyim"
                )
            ),
        )
        await j.text("120 mingga kiyim oldim")
        assert "Chiqim qayd etildi" in j.last.text
        assert len(await entries(j)) == 1
    else:
        await j.click(data=f"acct:7:undo:{entry.id}")
        assert "Yozuv bekor qilindi" in j.last.text
        assert (await entries(j))[0].cancelled
