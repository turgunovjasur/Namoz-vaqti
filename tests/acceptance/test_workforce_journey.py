import json

import pytest
from aiogram.methods import SendMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from namoz_bot.config import Settings
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.infrastructure.orm import Base, FinanceEntryRecord
from namoz_bot.main import create_application
from tests.acceptance.test_voice_reminder_journey import VoiceJourney
from tests.helpers.workforce import drain_workforce
from tests.integration.test_agent_sessions import NOW


@pytest.fixture
async def workforce_journey(tmp_path):
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'workforce.db'}",
            GEMINI_API_KEY="test-key",
            GEMINI_MAIN_AGENT_MODEL="workforce-model",
            MAIN_AGENT_VERSION=3,
            GEMINI_BOOK_CORPUS_PATH=None,
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
        )
    )
    async with app.db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    j = VoiceJourney(app)
    await j.text("/start")
    yield j
    await app.dispatcher.storage.close()
    await app.close()


def reply(value):
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}
        ]
    }


@pytest.fixture
def workforce_route(respx_mock):
    replies = [
        {"transcript": "120 mingga kiyim oldim"},
        {"role_id": "accounting", "question": None},
        {
            "capability_id": "finance.expense",
            "parameters": {
                "amount": 120000,
                "currency": "UZS",
                "category": "kiyim",
                "description": "Kiyim",
            },
            "question": None,
        },
        {"decision": "accept", "issues": []},
    ]

    def respond(request):
        import httpx

        return httpx.Response(200, json=reply(replies.pop(0)))

    return respx_mock.post(
        "https://generativelanguage.googleapis.com/v1beta/models/workforce-model:generateContent"
    ).mock(side_effect=respond)


async def test_voice_one_transcription_exact_approval_durable_execution_fresh_result(
    workforce_journey, workforce_route
):
    j = workforce_journey
    await j.voice()
    preview = j.session.last_ids[7]
    assert "Eshitdim:" in j.last.text and "Tushundim:" in j.last.text and "120 000" in j.last.text
    yes = j.button("✅ Ha")
    assert workforce_route.call_count == 3
    async with async_sessionmaker(j.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))
    await j.click(data=yes)
    assert workforce_route.call_count == 3
    job = j.app.scheduler.get_job("workforce")
    assert job is not None
    await drain_workforce(j.app)
    assert isinstance(j.last, SendMessage) and j.session.last_ids[7] != preview
    assert "120 000" in j.last.text and "Siz kutgan natijami?" in j.last.text
    assert workforce_route.call_count == 4
    await j.click(data=yes)
    await drain_workforce(j.app)
    async with async_sessionmaker(j.app.db_engine)() as session:
        assert len(list(await session.scalars(select(FinanceEntryRecord)))) == 1


async def test_failed_replacement_voice_retires_previous_approval(
    workforce_journey, workforce_route
):
    j = workforce_journey
    await j.voice()
    old = j.button("✅ Ha")
    await j.voice(size=6000000)
    await j.click(data=old)
    await drain_workforce(j.app)
    async with async_sessionmaker(j.app.db_engine)() as session:
        assert not list(await session.scalars(select(FinanceEntryRecord)))


async def test_full_granted_catalog_can_plan_through_all_three_provider_steps(
    workforce_journey, workforce_route
):
    assistant = workforce_journey.app.dispatcher["assistant_service"]
    context = AgentContext(
        bot_id=123456,
        user_id=1,
        telegram_user_id=7,
        chat_id=7,
        message_time=NOW,
        region_code="Toshkent",
    )
    model = await assistant.profiles.model("assistant")
    text = await assistant.transcriber.transcribe(b"OggS-test", "audio/ogg", model=model.model_id)
    plan = await assistant.manager.plan(
        context=context, request_id="debug", text=text, pending=None
    )
    assert plan.selection.capability_id == "finance.expense"


async def test_resume_uses_saved_card_without_new_ai_calls(workforce_journey, workforce_route):
    j = workforce_journey
    await j.voice()
    yes = j.button("✅ Ha")
    await j.text("/resume")
    assert j.button("✅ Ha") == yes
    assert workforce_route.call_count == 3
