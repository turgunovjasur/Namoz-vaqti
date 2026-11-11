from datetime import time

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.domain.reminders import ReminderSpec
from namoz_bot.infrastructure.orm import FinanceEntryRecord, ReminderRecord, WorkforceTaskRecord
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from tests.acceptance.test_workforce_feedback import mock_replies
from tests.acceptance.test_workforce_journey import workforce_journey as workforce_journey
from tests.acceptance.test_workforce_journey import workforce_route as workforce_route
from tests.helpers.workforce import drain_workforce
from tests.integration.test_agent_sessions import NOW


@pytest.mark.parametrize("kind", ["finance", "finance_spoof", "reminder"])
async def test_correction_clarification_keeps_target_and_task(
    workforce_journey, workforce_route, kind
):
    j = workforce_journey
    if kind.startswith("finance"):
        await j.voice()
        role, cap, change = "accounting", "finance.expense", {"amount": 150000}
    else:
        role, cap, change = "reminder", "reminder.create", {"time": "10:00"}
        mock_replies(
            workforce_route,
            [
                {"role_id": role, "question": None},
                {
                    "capability_id": cap,
                    "parameters": {"text": "Kitob", "kind": "daily", "time": "09:00"},
                    "question": None,
                },
                {"decision": "accept", "issues": []},
            ],
        )
        await j.text("Har kuni 9 da kitob o‘qishni eslat")
    followup_cap = "finance.correct" if kind == "finance_spoof" else cap
    if kind == "finance_spoof":
        change.update(target_id=999, expected_record_revision=999, intent="income")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert "Siz kutgan natijami" in j.last.text, j.last.text
    await j.click("❌ Yo‘q")
    mock_replies(
        workforce_route,
        [
            {"role_id": role, "question": None},
            {
                "capability_id": cap,
                "parameters": {},
                "question": "Qaysi qiymat?",
                "continuation": True,
            },
            {"role_id": role, "question": None},
            {
                "capability_id": followup_cap,
                "parameters": change,
                "question": None,
                "continuation": True,
            },
            {"decision": "accept", "issues": []},
        ],
    )
    await j.text("Qiymat xato")
    assert "Qaysi qiymat" in j.last.text
    await j.text("150 ming" if kind.startswith("finance") else "10 da")
    assert "Oldin:" in j.last.text and "Keyin:" in j.last.text
    if kind == "reminder":
        assert "09:00" in j.last.text and "10:00" in j.last.text
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    async with async_sessionmaker(j.app.db_engine)() as session:
        tasks = list(await session.scalars(select(WorkforceTaskRecord)))
        assert len(tasks) == 1 and tasks[0].revision == 3
        if kind.startswith("finance"):
            entries = list(
                await session.scalars(select(FinanceEntryRecord).order_by(FinanceEntryRecord.id))
            )
            assert len(entries) == 2 and entries[0].cancelled_at is not None
            assert entries[1].supersedes_id == entries[0].id and entries[1].amount == 150000
        else:
            reminders = list(await session.scalars(select(ReminderRecord)))
            assert len(reminders) == 1 and reminders[0].at == "10:00"


async def test_v3_list_next_page_and_ordinal_delete_use_delivered_owned_view(
    workforce_journey, workforce_route
):
    j = workforce_journey
    factory = async_sessionmaker(j.app.db_engine, expire_on_commit=False)
    repo = SqlAlchemyReminderRepository(factory)
    rows = [
        await repo.create(1, 7, ReminderSpec(f"Kitob {n}", time(16), "daily"), f"seed{n}", NOW)
        for n in range(6)
    ]
    mock_replies(
        workforce_route,
        [
            {"role_id": "reminder", "question": None},
            {"capability_id": "reminder.list", "parameters": {}, "question": None},
            {"decision": "accept", "issues": []},
            {"role_id": "reminder", "question": None},
            {
                "capability_id": "reminder.list",
                "parameters": {"page_step": "next"},
                "question": None,
            },
            {"decision": "accept", "issues": []},
            {"role_id": "reminder", "question": None},
            {"capability_id": "reminder.delete", "parameters": {"ordinal": 1}, "question": None},
            {"decision": "accept", "issues": []},
        ],
    )
    for text in ("Eslatmalarim", "Keyingi sahifa"):
        await j.text(text)
        await j.click("✅ Ha")
        await drain_workforce(j.app)
    assert "Kitob 5" in j.last.text and "Kitob 0" not in j.last.text
    await j.text("Birinchisini o‘chir")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    assert await repo.get_for_user(1, rows[3].id) is None
    assert await repo.get_for_user(1, rows[0].id) is not None


async def test_independent_report_during_correction_question_starts_new_task(
    workforce_journey, workforce_route
):
    j = workforce_journey
    mock_replies(
        workforce_route,
        [
            {"role_id": "accounting", "question": None},
            {"capability_id": "finance.report", "parameters": {}, "question": None},
            {"decision": "accept", "issues": []},
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.report",
                "parameters": {},
                "question": "Qaysi oy?",
                "continuation": True,
            },
            {"role_id": "accounting", "question": None},
            {
                "capability_id": "finance.report",
                "parameters": {"month": "2026-09"},
                "question": None,
                "continuation": False,
            },
        ],
    )
    await j.text("Hisobot ber")
    await j.click("✅ Ha")
    await drain_workforce(j.app)
    await j.click("❌ Yo‘q")
    await j.text("Oy xato")
    await j.text("Boshqa ish: sentyabr hisobotini ber")
    async with async_sessionmaker(j.app.db_engine)() as session:
        tasks = list(await session.scalars(select(WorkforceTaskRecord)))
        assert len(tasks) == 2
