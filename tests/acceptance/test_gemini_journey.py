import json

import httpx
import pytest
from aiogram.exceptions import TelegramBadRequest
from aiogram.methods import DeleteMessage, EditMessageText, SendMessage
from aiogram.types import ReplyKeyboardMarkup

from namoz_bot.config import Settings
from namoz_bot.infrastructure.orm import Base
from namoz_bot.main import create_application
from tests.acceptance.test_reminder_journey import Journey


def selected(identifier):
    return json.dumps({"passage_id": identifier})


@pytest.fixture
async def gemini_journey(tmp_path, request):
    params = getattr(request, "param", "gemini-test-key")
    options = params if isinstance(params, dict) else {"GEMINI_API_KEY": params}
    book_path = tmp_path / "book.json"
    texts = [
        "Yaxshilik qiling. <b>Mehr</b> ulashing.",
        "Shukr qiling. Sabrli bo‘ling.",
        "Mehribon bo‘ling. Yaxshilik qiling.",
        "Yaxshilik qiling. Mehr ulashing.",
        "Sabrli bo‘ling. Yaxshilik qiling.",
    ]
    book_path.write_text(
        json.dumps(
            {
                "title": "Sinov kitobi",
                "author": "Sinov muallifi",
                "passages": [
                    {"id": f"p{i}", "text": text, "page_start": i, "page_end": i}
                    for i, text in enumerate(texts, 1)
                ],
            }
        ),
        encoding="utf-8",
    )
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'gemini.db'}",
            GEMINI_API_KEY=options.get("GEMINI_API_KEY", "gemini-test-key"),
            GEMINI_BOOK_CORPUS_PATH=book_path,
            GEMINI_BUTTON_COOLDOWN_SECONDS=options.get("GEMINI_BUTTON_COOLDOWN_SECONDS", 0),
            GEMINI_REMINDER_INTERVAL_HOURS=options.get("GEMINI_REMINDER_INTERVAL_HOURS", 0),
            GEMINI_MODEL="gemini-3.5-flash-lite",
        )
    )
    async with app.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    yield Journey(app)
    await app.dispatcher.storage.close()
    await app.close()


@pytest.fixture
def gemini_route(respx_mock):
    return respx_mock.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    )


async def test_prayer_button_sends_fresh_book_passage_on_each_press(gemini_journey, gemini_route):
    replies = iter([selected("p1"), selected("p2")])

    def respond(request):
        assert request.headers["x-goog-api-key"] == "gemini-test-key"
        assert "key=" not in str(request.url)
        body = json.loads(request.content)
        assert "Yangi nasihat" in body["systemInstruction"]["parts"][0]["text"]
        assert "Sinov kitobi" in body["contents"][0]["parts"][0]["text"]
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": next(replies)}]},
                    }
                ],
            },
        )

    gemini_route.mock(side_effect=respond)
    await gemini_journey.text("/start")
    await gemini_journey.text("🕌 Namoz vaqti")
    labels = [b.text for row in gemini_journey.session.reply_keyboards[7].keyboard for b in row]
    assert "📖 Diniy eslatma" in labels

    await gemini_journey.text("📖 Diniy eslatma")
    assert isinstance(gemini_journey.last, SendMessage)
    assert "Yaxshilik qiling. <b>Mehr</b> ulashing." in gemini_journey.last.text
    assert gemini_journey.last.parse_mode is None
    assert gemini_journey.last.entities is None
    assert "Manba: «Sinov kitobi»" in gemini_journey.last.text
    assert "PDF sahifasi: 1" in gemini_journey.last.text

    await gemini_journey.text("📖 Diniy eslatma")
    assert "Shukr qiling. Sabrli bo‘ling." in gemini_journey.last.text
    assert "gemini-test-key" not in gemini_journey.last.text


@pytest.mark.parametrize("status", [400, 403, 429, 503])
async def test_gemini_http_error_returns_safe_retry_message(gemini_journey, gemini_route, status):
    gemini_route.respond(status, json={"error": {"message": "gemini-test-key"}})

    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert isinstance(gemini_journey.last, SendMessage)
    assert "birozdan keyin" in gemini_journey.last.text
    assert "gemini-test-key" not in gemini_journey.last.text


async def test_gemini_timeout_returns_safe_retry_message(gemini_journey, gemini_route):
    gemini_route.mock(side_effect=httpx.ReadTimeout("gemini-test-key"))

    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert isinstance(gemini_journey.last, SendMessage)
    assert "birozdan keyin" in gemini_journey.last.text
    assert "gemini-test-key" not in gemini_journey.last.text


async def test_gemini_button_discards_unfinished_reminder(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": selected("p3")}]},
                }
            ],
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("🔔 Eslatmalar")
    await gemini_journey.text("➕ Eslatma qo‘shish")
    await gemini_journey.text("📖 Diniy eslatma")

    assert "Mehribon bo‘ling" in gemini_journey.last.text
    context = gemini_journey.app.dispatcher.fsm.get_context(
        bot=gemini_journey.app.bot, chat_id=7, user_id=7
    )
    assert await context.get_state() is None
    assert "📖 Diniy eslatma" in [
        b.text for row in gemini_journey.session.reply_keyboards[7].keyboard for b in row
    ]


@pytest.mark.parametrize("gemini_journey", [None, "", "   "], indirect=True)
async def test_missing_gemini_key_keeps_bot_usable(gemini_journey, respx_mock):
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert "sozlanmagan" in gemini_journey.last.text
    assert not respx_mock.calls


@pytest.mark.parametrize(
    "payload",
    [
        {},
        [],
        {"promptFeedback": {"blockReason": "SAFETY"}},
        {"candidates": [{"finishReason": "SAFETY"}]},
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "Yarim"}]}}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": " "}]}}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "a" * 2000}]}}]},
        {"candidates": [None]},
    ],
)
async def test_invalid_or_incomplete_gemini_content_is_not_sent(
    gemini_journey, gemini_route, payload
):
    gemini_route.respond(200, json=payload)
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert isinstance(gemini_journey.last, SendMessage)
    assert "birozdan keyin" in gemini_journey.last.text


async def test_gemini_thoughts_are_excluded_from_user_answer(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"thought": True, "text": "Internal reasoning"},
                            {"text": '{"passage_id":'},
                            {"text": '"p3"}'},
                        ]
                    },
                }
            ],
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert "Mehribon bo‘ling. Yaxshilik qiling." in gemini_journey.last.text
    assert "Internal reasoning" not in gemini_journey.last.text


async def test_non_json_gemini_response_returns_retry_message(gemini_journey, gemini_route):
    gemini_route.respond(200, text="upstream proxy error")
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")

    assert isinstance(gemini_journey.last, SendMessage)
    assert "birozdan keyin" in gemini_journey.last.text


async def test_gemini_response_respects_telegram_reply_keyboard_edit_restriction(
    gemini_journey, gemini_route, monkeypatch
):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": selected("p4")}]},
                }
            ],
        },
    )
    session = gemini_journey.session
    original = session.make_request
    keyboard_messages = set()

    async def telegram_request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, EditMessageText):
            if (method.chat_id, method.message_id) in keyboard_messages:
                raise TelegramBadRequest(method=method, message="message can't be edited")
        response = await original(bot, method, timeout)
        if isinstance(method, SendMessage) and isinstance(method.reply_markup, ReplyKeyboardMarkup):
            keyboard_messages.add((method.chat_id, response.message_id))
        return response

    monkeypatch.setattr(session, "make_request", telegram_request)
    await gemini_journey.text("/start")
    await gemini_journey.text("🕌 Namoz vaqti")
    await gemini_journey.text("📖 Diniy eslatma")

    assert "Yaxshilik qiling. Mehr ulashing." in gemini_journey.last.text
    assert all("tayyorlanmoqda" not in (m.text or "") for m in session.messages.values())


async def test_loading_cleanup_error_does_not_hide_gemini_response(
    gemini_journey, gemini_route, monkeypatch
):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": selected("p4")}]},
                }
            ],
        },
    )
    original = gemini_journey.session.make_request

    async def telegram_request(bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, DeleteMessage):
            raise TelegramBadRequest(method=method, message="message to delete not found")
        return await original(bot, method, timeout)

    await gemini_journey.text("/start")
    monkeypatch.setattr(gemini_journey.session, "make_request", telegram_request)
    await gemini_journey.text("📖 Diniy eslatma")

    assert "Yaxshilik qiling. Mehr ulashing." in gemini_journey.last.text
    assert isinstance(gemini_journey.last.reply_markup, ReplyKeyboardMarkup)


@pytest.mark.parametrize("gemini_journey", [{"GEMINI_BUTTON_COOLDOWN_SECONDS": 60}], indirect=True)
async def test_repeated_button_press_does_not_call_gemini_again(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": selected("p5")}]},
                }
            ],
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")
    await gemini_journey.text("📖 Diniy eslatma")

    assert "soniya kuting" in gemini_journey.last.text
    assert gemini_route.call_count == 1


@pytest.mark.parametrize("gemini_journey", [{"GEMINI_BUTTON_COOLDOWN_SECONDS": 60}], indirect=True)
async def test_repeated_cooldown_updates_same_editable_message(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": selected("p5")}]}}
            ]
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("🕌 Namoz vaqti")
    await gemini_journey.text("📖 Diniy eslatma")
    await gemini_journey.text("📖 Diniy eslatma")
    wait_id = gemini_journey.session.last_ids[7]
    assert "soniya kuting" in gemini_journey.last.text
    assert gemini_journey.last.reply_markup is None
    sends_before = sum(isinstance(call, SendMessage) for call in gemini_journey.session.calls)

    await gemini_journey.text("📖 Diniy eslatma")

    assert isinstance(gemini_journey.last, EditMessageText)
    assert gemini_journey.last.message_id == wait_id
    assert (
        sum(isinstance(call, SendMessage) for call in gemini_journey.session.calls) == sends_before
    )
    assert gemini_route.call_count == 1
    assert "📖 Diniy eslatma" in [
        b.text for row in gemini_journey.session.reply_keyboards[7].keyboard for b in row
    ]


@pytest.mark.parametrize("gemini_journey", [{"GEMINI_BUTTON_COOLDOWN_SECONDS": 60}], indirect=True)
async def test_deleted_wait_message_is_replaced_once_then_reused(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": selected("p5")}]}}
            ]
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")
    await gemini_journey.text("📖 Diniy eslatma")
    old_id = gemini_journey.session.last_ids[7]
    gemini_journey.session.messages.pop((7, old_id))
    await gemini_journey.text("📖 Diniy eslatma")
    new_id = gemini_journey.session.last_ids[7]
    assert new_id != old_id
    await gemini_journey.text("📖 Diniy eslatma")
    assert isinstance(gemini_journey.last, EditMessageText)
    assert gemini_journey.last.message_id == new_id
    assert gemini_route.call_count == 1


@pytest.mark.parametrize("gemini_journey", [{"GEMINI_BUTTON_COOLDOWN_SECONDS": 60}], indirect=True)
async def test_unchanged_wait_message_does_not_create_another_message(gemini_journey, gemini_route):
    gemini_route.respond(
        200,
        json={
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": selected("p5")}]}}
            ]
        },
    )
    await gemini_journey.text("/start")
    await gemini_journey.text("📖 Diniy eslatma")
    await gemini_journey.text("📖 Diniy eslatma")
    sends_before = sum(isinstance(call, SendMessage) for call in gemini_journey.session.calls)
    gemini_journey.session.fail_edit = "message is not modified"
    await gemini_journey.text("📖 Diniy eslatma")
    assert (
        sum(isinstance(call, SendMessage) for call in gemini_journey.session.calls) == sends_before
    )
    assert gemini_route.call_count == 1


@pytest.mark.parametrize("gemini_journey", [{"GEMINI_REMINDER_INTERVAL_HOURS": 24}], indirect=True)
async def test_scheduled_nasihat_reaches_active_users_once_per_run(gemini_journey, gemini_route):
    from datetime import UTC, datetime, timedelta

    from sqlalchemy.ext.asyncio import async_sessionmaker

    from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository
    from namoz_bot.infrastructure.repositories import SqlAlchemySubscriptionRepository

    gemini_route.respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {"parts": [{"text": selected("p5")}]},
                }
            ],
        },
    )
    for identifier in (7, 8, 9):
        await gemini_journey.text("/start", user=identifier)
    repository = SqlAlchemySubscriptionRepository(
        async_sessionmaker(gemini_journey.app.db_engine, expire_on_commit=False)
    )
    await repository.set_active(9, False)
    intervals = SqlAlchemyReligiousIntervalRepository(
        async_sessionmaker(gemini_journey.app.db_engine, expire_on_commit=False)
    )
    for identifier in (7, 8, 9):
        await intervals.set_interval(identifier, 24, datetime.now(UTC) - timedelta(days=1))
    job = gemini_journey.app.scheduler.get_job("automatic-religious-reminders")
    assert job is not None

    report = await job.func()

    sends = [
        call
        for call in gemini_journey.session.calls
        if isinstance(call, SendMessage) and "Sabrli bo‘ling" in call.text
    ]
    assert [call.chat_id for call in sends] == [7, 8]
    assert report.sent == 2
    assert gemini_route.call_count == 1
    assert all("Manba: «Sinov kitobi»" in call.text for call in sends)
