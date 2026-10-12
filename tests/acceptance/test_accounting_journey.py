import json
from datetime import UTC, datetime

import pytest
from aiogram.methods import AnswerCallbackQuery
from aiogram.types import Update
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository
from tests.acceptance.test_voice_reminder_journey import (
    MODEL_URL,
    extracted,
    response,
)
from tests.acceptance.test_voice_reminder_journey import (
    voice_journey as _ledger_fixture,
)

ledger_journey = _ledger_fixture


def accounting_input(**changes):
    return {
        "transcript": "Oktyabrda o‘n million oylik tushdi",
        "intent": "income",
        "amount": 10_000_000,
        "currency": "UZS",
        "category": "oylik",
        "description": "Oylik",
        "month": "2026-10",
        "date": None,
        "report_type": None,
        "clarification": None,
    } | changes


@pytest.fixture
def finance_route(respx_mock):
    return respx_mock.post(MODEL_URL).respond(200, json=response(accounting_input()))


async def entries(journey, user=7):
    from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository

    factory = async_sessionmaker(journey.app.db_engine, expire_on_commit=False)
    owner = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(user)
    return await SqlAlchemyLedgerRepository(factory).history(owner.id, offset=0, limit=20)


async def open_finance(journey, user=7):
    await journey.text("💰 Kirim-chiqim", user=user)


async def test_section_is_available_and_zero_balance_menu_stays_open(ledger_journey):
    labels = [b.text for row in ledger_journey.session.reply_keyboards[7].keyboard for b in row]
    assert "💰 Kirim-chiqim" in labels
    await open_finance(ledger_journey)
    assert "0 so‘m" in ledger_journey.last.text
    assert "Kirim-chiqim" in ledger_journey.last.text
    assert 7 in ledger_journey.session.reply_keyboards


async def test_voice_income_expense_and_salary_report_use_persisted_records(
    ledger_journey, finance_route
):
    await open_finance(ledger_journey)
    await ledger_journey.voice()
    assert "10 000 000 so‘m" in ledger_journey.last.text
    assert "Kirim qayd etildi" in ledger_journey.last.text
    assert (await entries(ledger_journey))[0].occurred_on is None
    finance_route.respond(
        200,
        json=response(
            accounting_input(
                intent="expense", amount=120_000, category="kiyim", description="Kiyim", month=None
            )
        ),
    )
    await ledger_journey.voice()
    assert "Chiqim qayd etildi" in ledger_journey.last.text
    assert "9 880 000 so‘m" in ledger_journey.last.text
    finance_route.respond(
        200,
        json=response(
            accounting_input(
                intent="report", amount=None, category=None, description=None, report_type="salary"
            )
        ),
    )
    await ledger_journey.voice()
    assert "Oylik tushumi: 10 000 000 so‘m" in ledger_journey.last.text
    assert len(await entries(ledger_journey)) == 2
    await ledger_journey.click("📊 Shu oy hisoboti")
    assert "Jami chiqim: 120 000 so‘m" in ledger_journey.last.text
    await ledger_journey.click("📒 Tarix")
    assert "Kiyim" in ledger_journey.last.text and "Oylik" in ledger_journey.last.text
    assert 7 in ledger_journey.session.reply_keyboards


async def test_text_input_uses_same_extraction_and_saves_whole_amount(
    ledger_journey, finance_route
):
    await open_finance(ledger_journey)
    await ledger_journey.text("Oktyabrda 10 million oylik tushdi")
    assert len(await entries(ledger_journey)) == 1
    body = json.loads(finance_route.calls.last.request.content)
    parts = body["contents"][0]["parts"]
    assert "Oktyabrda 10 million" in parts[-1]["text"]
    assert not any("inlineData" in part for part in parts)


async def test_old_undo_button_cancels_only_its_record_and_repeat_is_safe(
    ledger_journey, finance_route
):
    await open_finance(ledger_journey)
    await ledger_journey.voice()
    undo_income = ledger_journey.button("↩️ Yozuvni bekor qilish")
    finance_route.respond(
        200,
        json=response(
            accounting_input(
                intent="expense", amount=120_000, category="kiyim", description="Kiyim"
            )
        ),
    )
    await ledger_journey.voice()
    await ledger_journey.click(data=undo_income)
    assert "-120 000 so‘m" in ledger_journey.last.text
    await ledger_journey.click(data=undo_income)
    assert "-120 000 so‘m" in ledger_journey.last.text
    saved = await entries(ledger_journey)
    assert saved[0].cancelled is False and saved[1].cancelled is True


async def test_other_user_cannot_cancel_or_see_owner_records(ledger_journey, finance_route):
    await open_finance(ledger_journey)
    await ledger_journey.voice()
    record = (await entries(ledger_journey))[0]
    await ledger_journey.text("/start", user=8)
    await open_finance(ledger_journey, user=8)
    await ledger_journey.click(data=f"acct:8:undo:{record.id}", user=8)
    assert (await entries(ledger_journey))[0].cancelled is False
    assert await entries(ledger_journey, user=8) == []
    assert "0 so‘m" in ledger_journey.last.text


async def test_voice_balance_report_does_not_add_a_transaction(ledger_journey, finance_route):
    await open_finance(ledger_journey)
    finance_route.respond(
        200,
        json=response(
            accounting_input(
                intent="balance", amount=None, category=None, description=None, month=None
            )
        ),
    )
    await ledger_journey.voice()
    assert "Joriy balans: 0 so‘m" in ledger_journey.last.text
    assert await entries(ledger_journey) == []


@pytest.mark.parametrize(
    "changes",
    [
        {"amount": None, "clarification": "Qancha pul sarfladingiz?"},
        {"intent": "unclear", "clarification": "Summa va maqsadni aniq ayting."},
        {"intent": "unsupported"},
        {"amount": -120_000},
        {"amount": 12.5},
        {"date": "2026-02-30"},
        {"month": "2027-01"},
        {"currency": "OTHER"},
    ],
)
async def test_unclear_invalid_or_future_input_never_changes_balance(
    ledger_journey, finance_route, changes
):
    await open_finance(ledger_journey)
    finance_route.respond(200, json=response(accounting_input(**changes)))
    await ledger_journey.voice()
    assert await entries(ledger_journey) == []
    assert 7 in ledger_journey.session.reply_keyboards


async def test_provider_failure_leaves_accounting_usable(ledger_journey, finance_route):
    await open_finance(ledger_journey)
    finance_route.respond(503, json={"error": {"message": "voice-test-key"}})
    await ledger_journey.voice()
    assert "voice-test-key" not in ledger_journey.last.text
    assert "qayta" in ledger_journey.last.text
    await ledger_journey.click("💳 Balans")
    assert "Joriy balans: 0 so‘m" in ledger_journey.last.text


async def test_leaving_accounting_restores_reminder_voice_routing(ledger_journey, finance_route):
    await open_finance(ledger_journey)
    old_history = ledger_journey.button("📒 Tarix")
    await ledger_journey.text("🔔 Eslatmalar")
    finance_route.respond(200, json=response(extracted()))
    await ledger_journey.voice()
    await ledger_journey.click(data=old_history)
    assert "Onamga qo‘ng‘iroq qilish" in ledger_journey.last.text
    assert (await ledger_journey.draft())["step"] == "confirm"
    assert await entries(ledger_journey) == []


@pytest.mark.parametrize("ledger_journey", [None], indirect=True)
async def test_reports_work_without_gemini_key(ledger_journey, respx_mock):
    await open_finance(ledger_journey)
    await ledger_journey.voice()
    assert "sozlanmagan" in ledger_journey.last.text
    await ledger_journey.click("💳 Balans")
    assert "0 so‘m" in ledger_journey.last.text
    assert not respx_mock.calls


async def test_telegram_replayed_voice_records_only_once(ledger_journey, finance_route):
    await open_finance(ledger_journey)
    payload = {
        "message_id": 900,
        "date": datetime.now(UTC),
        "chat": {"id": 7, "type": "private"},
        "from": {"id": 7, "is_bot": False, "first_name": "Test"},
        "voice": {
            "file_id": "voice-id",
            "file_unique_id": "unique",
            "duration": 12,
            "file_size": 20,
            "mime_type": "audio/ogg",
        },
    }
    for identifier in (900, 901):
        await ledger_journey.app.dispatcher.feed_update(
            ledger_journey.app.bot,
            Update.model_validate({"update_id": identifier, "message": payload}),
        )
    assert len(await entries(ledger_journey)) == 1
    assert "10 000 000 so‘m" in ledger_journey.last.text
    assert not any(
        isinstance(call, AnswerCallbackQuery) and call.show_alert
        for call in ledger_journey.session.calls
    )
