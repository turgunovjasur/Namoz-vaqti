import httpx
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.orm import (
    FinanceEntryRecord,
    RoleCapabilityRecord,
    WorkforceTaskRecord,
)
from tests.acceptance.test_workforce_journey import (
    reply,
)
from tests.acceptance.test_workforce_journey import (
    workforce_journey as workforce_journey,
)
from tests.acceptance.test_workforce_journey import (
    workforce_route as workforce_route,
)
from tests.helpers.workforce import drain_workforce


async def test_negative_result_then_voice_correction_needs_approval_and_replaces_once(
    workforce_journey, workforce_route
):
    j = workforce_journey
    await j.voice()
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    old_yes = j.button("✅ Ha")
    await j.click("❌ Yo‘q")
    assert "Nima xato" in j.last.text
    factory = async_sessionmaker(j.app.db_engine)
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1
    responses = [
        {"transcript": "Summa 150 ming edi"},
        {"role_id": "accounting", "question": None},
        {
            "capability_id": "finance.expense",
            "parameters": {"amount": 150000},
            "question": None,
            "continuation": True,
        },
        {"decision": "accept", "issues": []},
    ]
    workforce_route.mock(
        side_effect=lambda request: httpx.Response(200, json=reply(responses.pop(0)))
    )
    await j.voice()
    assert "Eshitdim:" in j.last.text and "150 000" in j.last.text
    assert "Oldin:" in j.last.text and "120 000" in j.last.text and "Keyin:" in j.last.text
    async with factory() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "150 000" in j.last.text and "Siz kutgan natijami?" in j.last.text
    new_yes = j.button("✅ Ha")
    await j.click(data=old_yes)
    assert "eskirgan" in j.last.text.lower()
    before = set(j.session.messages)
    await j.click(data=new_yes)
    assert set(j.session.messages) == before
    async with factory() as session:
        entries = list(
            await session.scalars(select(FinanceEntryRecord).order_by(FinanceEntryRecord.id))
        )
        assert (
            len(entries) == 2
            and entries[0].cancelled_at is not None
            and entries[1].amount == 150000
        )


def mock_replies(route, responses):
    route.mock(side_effect=lambda request: httpx.Response(200, json=reply(responses.pop(0))))


async def test_unrelated_request_after_no_starts_different_task(workforce_journey, workforce_route):
    j = workforce_journey
    await j.voice()
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    await j.click("❌ Yo‘q")
    mock_replies(
        workforce_route,
        [
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.balance",
                "parameters": {},
                "question": None,
                "continuation": False,
            },
        ],
    )
    await j.text("Balansimni ko‘rsat")
    assert "Tushundim:" in j.last.text
    async with async_sessionmaker(j.app.db_engine)() as session:
        tasks = list(await session.scalars(select(WorkforceTaskRecord)))
        assert len(tasks) == 2 and {t.status for t in tasks} == {"done", "awaiting_approval"}
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_revoked_correction_does_not_replace_original(workforce_journey, workforce_route):
    j = workforce_journey
    await j.voice()
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    await j.click("❌ Yo‘q")
    mock_replies(
        workforce_route,
        [
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.expense",
                "parameters": {"amount": 150000},
                "question": None,
                "continuation": True,
            },
        ],
    )
    await j.text("Summa 150 ming edi")
    yes = j.button("✅ Ha")
    async with async_sessionmaker(j.app.db_engine).begin() as session:
        await session.execute(
            delete(RoleCapabilityRecord).where(
                RoleCapabilityRecord.capability_id == "finance.correct"
            )
        )
    await j.click(data=yes)
    assert "o‘chirilgan" in j.last.text
    await drain_workforce(j.app)
    async with async_sessionmaker(j.app.db_engine)() as session:
        entries = list(await session.scalars(select(FinanceEntryRecord)))
        assert len(entries) == 1 and entries[0].cancelled_at is None


async def test_report_correction_filters_without_changing_ledger(
    workforce_journey, workforce_route
):
    j = workforce_journey
    await j.voice()
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    mock_replies(
        workforce_route,
        [
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.report",
                "parameters": {"report_type": "expense"},
                "question": None,
            },
            {"decision": "accept", "issues": []},
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.report",
                "parameters": {"category": "oziq_ovqat"},
                "question": None,
                "continuation": True,
            },
            {"decision": "accept", "issues": []},
        ],
    )
    await j.text("Shu oy qancha xarajat qildim?")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "120 000" in j.last.text
    await j.click("❌ Yo‘q")
    await j.text("Faqat oziq ovqat bo‘yicha")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "Xarajat: 0 so‘m" in j.last.text
    assert "Xarajat: 0 so‘m" in j.last.text
    assert "-120 000" not in j.last.text
    async with async_sessionmaker(j.app.db_engine)() as session:
        entries = list(await session.scalars(select(FinanceEntryRecord)))
        assert len(entries) == 1 and entries[0].cancelled_at is None


async def test_relative_offset_correction_replaces_delta_instead_of_adding_again(
    workforce_journey, workforce_route
):
    j = workforce_journey
    mock_replies(
        workforce_route,
        [
            {"role_id": "prayer", "question": None},
            {
                "capability_id": "prayer.set_offset",
                "parameters": {"prayer": "shom", "minutes": 4, "mode": "add"},
                "question": None,
            },
            {"decision": "accept", "issues": []},
            {"role_id": "prayer", "question": None},
            {
                "capability_id": "prayer.set_offset",
                "parameters": {"minutes": 6},
                "question": None,
                "continuation": True,
            },
            {"decision": "accept", "issues": []},
        ],
    )
    await j.text("Shomga 4 daqiqa qo‘sh")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "+4 daqiqa" in j.last.text
    await j.click("❌ Yo‘q")
    await j.text("4 emas 6 bo‘lsin")
    assert "Tushundim:" in j.last.text
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "+6 daqiqa" in j.last.text
