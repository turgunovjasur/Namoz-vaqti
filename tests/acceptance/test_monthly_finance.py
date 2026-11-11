from datetime import date

from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.domain.accounting import LedgerSpec
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository
from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from namoz_bot.presentation.accounting import ledger_service_month
from tests.acceptance.test_accounting_journey import accounting_input, response
from tests.acceptance.test_accounting_journey import finance_route as finance_route
from tests.acceptance.test_accounting_journey import ledger_journey as ledger_journey
from tests.acceptance.test_main_agent_journey import agent_journey as agent_journey
from tests.acceptance.test_main_agent_journey import agent_route as agent_route


async def test_month_navigation_history_and_today_write_do_not_mix_months(
    ledger_journey, finance_route
):
    j = ledger_journey
    factory = async_sessionmaker(j.app.db_engine, expire_on_commit=False)
    owner = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(7)
    repo = SqlAlchemyLedgerRepository(factory)
    month = ledger_service_month()
    prior = date(month.year - (month.month == 1), (month.month - 2) % 12 + 1, 1)
    await repo.create(
        owner.id, LedgerSpec("income", 2_000_000, "oylik", "Old month", prior, prior), "old"
    )
    await repo.create(
        owner.id, LedgerSpec("income", 5_000_000, "oylik", "Current month", month, month), "new"
    )
    await j.text("💰 Kirim-chiqim")
    assert "5 000 000" in j.last.text and "7 000 000" not in j.last.text
    await j.click("📒 Shu oy tarixi")
    assert "Current month" in j.last.text and "Old month" not in j.last.text
    await j.click("◀️ Oldingi oy")
    assert "2 000 000" in j.last.text and "5 000 000" not in j.last.text
    await j.click("📒 Shu oy tarixi")
    assert "Old month" in j.last.text and "Current month" not in j.last.text
    await j.click("💳 Umumiy balans")
    assert "7 000 000" in j.last.text
    await j.click("\N{HEAVY MINUS SIGN} Xarajat yozish")
    finance_route.respond(
        200,
        json=response(
            accounting_input(
                intent="expense",
                amount=1_000_000,
                category="kiyim",
                description="Today expense",
                month=None,
            )
        ),
    )
    await j.text("Bugun 1 millionga kiyim oldim")
    assert "4 000 000" in j.last.text
    assert await repo.balance(owner.id, month=prior) == 2_000_000
    assert await repo.balance(owner.id, month=month) == 4_000_000
    await j.click("📅 Oy tanlash")
    await j.click(data=f"acct:7:month:{prior.isoformat()}")
    assert "2 000 000" in j.last.text


async def test_backdated_agent_receipt_navigation_uses_receipt_month(agent_journey, agent_route):
    from tests.acceptance.test_main_agent_journey import response as agent_response

    current = ledger_service_month()
    prior = date(current.year - (current.month == 1), (current.month - 2) % 12 + 1, 1)
    agent_route.respond(
        200,
        json=agent_response(
            "accounting",
            "income",
            {
                "amount": 2_000_000,
                "currency": "UZS",
                "category": "oylik",
                "description": "Old salary",
                "month": prior.isoformat()[:7],
            },
        ),
    )
    await agent_journey.text("Oldingi oyda ikki million oylik tushgan")
    await agent_journey.click("📊 Oy hisoboti")
    assert "Jami kirim: 2 000 000 so‘m" in agent_journey.last.text
    await agent_journey.click("📒 Shu oy tarixi")
    assert "Old salary" in agent_journey.last.text
