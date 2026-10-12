"""Voice input must produce a validated draft, never an automatic database write."""

import base64
import json
from datetime import UTC, datetime, timedelta

import pytest
from aiogram.methods import GetFile
from aiogram.types import File, Update

from namoz_bot.config import Settings
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.orm import Base
from namoz_bot.main import create_application
from namoz_bot.presentation.religious_settings import ReligiousIntervalStates
from namoz_bot.presentation.settings import DailySettingsStates
from tests.acceptance.test_reminder_journey import Journey, LocalSession

AUDIO = b"OggS-local-test-audio"
AUDIO_SIZE = len(AUDIO)
MODEL_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/voice-test-model:generateContent"
)


class VoiceSession(LocalSession):
    async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
        if isinstance(method, GetFile):
            self.calls.append(method)
            return File(file_id=method.file_id, file_unique_id="unique", file_path="voice/test.ogg")
        result = await super().make_request(bot, method, timeout)
        # Real Telegram response parsing attaches the current bot to messages.
        return result.as_(bot) if hasattr(result, "as_") else result

    async def stream_content(self, *args, **kwargs):
        yield AUDIO


class VoiceJourney(Journey):
    def __init__(self, app):
        super().__init__(app)
        self.session = VoiceSession()
        app.bot.session = self.session

    async def voice(self, *, user=7, group=False, duration=12, size=AUDIO_SIZE):
        self.sequence += 1
        await self.app.dispatcher.feed_update(
            self.app.bot,
            Update.model_validate(
                {
                    "update_id": self.sequence,
                    "message": {
                        "message_id": self.sequence,
                        "date": datetime.now(UTC),
                        "chat": {
                            "id": -100 if group else user,
                            "type": "group" if group else "private",
                        },
                        "from": {"id": user, "is_bot": False, "first_name": "Test"},
                        "voice": {
                            "file_id": "voice-id",
                            "file_unique_id": "unique",
                            "duration": duration,
                            "file_size": size,
                            "mime_type": "audio/ogg",
                        },
                    },
                }
            ),
        )

    async def draft(self, user=7):
        context = self.app.dispatcher.fsm.get_context(bot=self.app.bot, chat_id=user, user_id=user)
        return await context.get_data()


@pytest.fixture
async def voice_journey(tmp_path, request):
    params = getattr(request, "param", "voice-test-key")
    options = params if isinstance(params, dict) else {"key": params}
    voice_model = options.get("voice_model", "voice-test-model")
    model_settings = {"GEMINI_VOICE_MODEL": voice_model} if voice_model is not None else {}
    app = create_application(
        Settings(
            _env_file=None,
            telegram_bot_token="123456:LOCAL_TEST",
            database_url=f"sqlite+aiosqlite:///{tmp_path / 'voice.db'}",
            GEMINI_API_KEY=options.get("key", "voice-test-key"),
            GEMINI_BOOK_CORPUS_PATH=None,
            GEMINI_MODEL=options.get("model", "gemini-3.8-flash"),
            VOICE_REMINDER_COOLDOWN_SECONDS=0,
            **model_settings,
        )
    )
    async with app.db_engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await app.bot.session.close()
    journey = VoiceJourney(app)
    await journey.text("/start")
    yield journey
    await app.dispatcher.storage.close()
    await app.close()


def extracted(**changes):
    tomorrow = (datetime.now(TASHKENT) + timedelta(days=1)).date().isoformat()
    return {
        "transcript": "Ertaga kechqurun sakkizda onamga qo‘ng‘iroq qilishni eslat",
        "intent": "create_reminder",
        "text": "Onamga qo‘ng‘iroq qilish",
        "time": "20:00",
        "date": tomorrow,
        "kind": "once",
        "weekdays": [],
        "clarification": None,
    } | changes


@pytest.fixture
def voice_route(respx_mock):
    route = respx_mock.post(MODEL_URL)
    route.respond(200, json=response(extracted()))
    return route


def response(fields):
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(fields)}]}}
        ]
    }


async def test_complete_voice_requires_save_and_duplicate_tap_creates_one_row(
    voice_journey, voice_route
):
    await voice_journey.voice()
    assert "Onamga qo‘ng‘iroq qilish" in voice_journey.last.text
    assert "20:00" in voice_journey.last.text
    assert await voice_journey.rows() == []
    data = await voice_journey.draft()
    assert data["step"] == "confirm"
    assert data["date"] == extracted()["date"]
    body = json.loads(voice_route.calls.last.request.content)
    parts = body["contents"][0]["parts"]
    assert base64.b64decode(parts[1]["inlineData"]["data"]) == AUDIO
    assert "Asia/Tashkent" in parts[0]["text"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    saved = await voice_journey.click("✅ Saqlash")
    await voice_journey.click(data=saved)
    rows = await voice_journey.rows()
    assert len(rows) == 1
    assert rows[0].spec.text == "Onamga qo‘ng‘iroq qilish"
    assert rows[0].spec.on_date.isoformat() == extracted()["date"]
    assert rows[0].spec.at.isoformat() == "20:00:00"


async def test_missing_time_keeps_spoken_date_after_user_selects_time(voice_journey, voice_route):
    voice_route.respond(
        200, json=response(extracted(time=None, clarification="Soat nechida eslatay?"))
    )
    await voice_journey.voice()
    assert (await voice_journey.draft())["step"] == "time"
    assert "Soat nechida" in voice_journey.last.text
    await voice_journey.choose_time(hour=18, minute=30)
    assert (await voice_journey.draft())["step"] == "confirm"
    await voice_journey.click("✅ Saqlash")
    row = (await voice_journey.rows())[0]
    assert row.spec.on_date.isoformat() == extracted()["date"]
    assert row.spec.at.isoformat() == "18:30:00"


async def test_missing_schedule_keeps_spoken_time(voice_journey, voice_route):
    voice_route.respond(200, json=response(extracted(date=None, kind=None)))
    await voice_journey.voice()
    assert (await voice_journey.draft())["step"] == "schedule"
    await voice_journey.click("🔁 Har kuni")
    assert (await voice_journey.draft())["step"] == "confirm"
    await voice_journey.click("✅ Saqlash")
    row = (await voice_journey.rows())[0]
    assert row.spec.kind == "daily"
    assert row.spec.at.isoformat() == "20:00:00"


@pytest.mark.parametrize("finish", ["✅ Saqlash", "❌ Bekor qilish"])
async def test_voice_keeps_main_menu_during_preview_edit_and_finish(
    voice_journey, voice_route, finish
):
    main_id = voice_journey.session.last_ids[7]
    await voice_journey.voice()
    assert 7 in voice_journey.session.reply_keyboards
    assert (7, main_id) in voice_journey.session.messages
    await voice_journey.click("✏️ Tahrirlash")
    await voice_journey.text("Tuzatilgan matn")
    assert 7 in voice_journey.session.reply_keyboards
    await voice_journey.click(finish)
    assert 7 in voice_journey.session.reply_keyboards
    labels = [
        button.text for row in voice_journey.session.reply_keyboards[7].keyboard for button in row
    ]
    assert labels == ["🕌 Namoz vaqti", "🔔 Eslatmalar", "💰 Kirim-chiqim", "⚙️ Sozlamalar"]


async def test_voice_restores_main_menu_when_reminders_had_hidden_it(voice_journey, voice_route):
    await voice_journey.text("🔔 Eslatmalar")
    assert 7 not in voice_journey.session.reply_keyboards
    await voice_journey.voice()
    assert 7 in voice_journey.session.reply_keyboards
    assert (await voice_journey.draft())["step"] == "confirm"


@pytest.mark.parametrize(
    "voice_journey", [{"voice_model": None, "model": "gemini-3.8-flash"}], indirect=True
)
async def test_voice_default_is_independent_of_religious_model(voice_journey, respx_mock):
    route = respx_mock.post(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-3.5-flash-lite:generateContent"
    ).respond(200, json=response(extracted()))
    await voice_journey.voice()
    assert (await voice_journey.draft())["step"] == "confirm"
    assert len(route.calls) == 1


@pytest.mark.parametrize(
    "active_state", [DailySettingsStates.custom_time, ReligiousIntervalStates.custom_hours]
)
async def test_voice_creation_works_while_settings_input_is_open(
    voice_journey, voice_route, active_state
):
    context = voice_journey.app.dispatcher.fsm.get_context(
        bot=voice_journey.app.bot, chat_id=7, user_id=7
    )
    await context.set_state(active_state)
    await voice_journey.voice()
    assert (await voice_journey.draft())["step"] == "confirm"
    assert "Onamga qo‘ng‘iroq qilish" in voice_journey.last.text


@pytest.mark.parametrize("kind,days", [("daily", []), ("weekly", [0, 2, 4])])
async def test_spoken_recurring_schedule_is_saved(voice_journey, voice_route, kind, days):
    voice_route.respond(200, json=response(extracted(kind=kind, date=None, weekdays=days)))
    await voice_journey.voice()
    await voice_journey.click("✅ Saqlash")
    row = (await voice_journey.rows())[0]
    assert row.spec.kind == kind
    assert row.spec.weekdays == tuple(days)


async def test_voice_preview_can_edit_text_and_keep_schedule(voice_journey, voice_route):
    await voice_journey.voice()
    await voice_journey.click("✏️ Tahrirlash")
    await voice_journey.text("Otamga qo‘ng‘iroq qilish")
    assert (await voice_journey.draft())["step"] == "confirm"
    await voice_journey.click("✅ Saqlash")
    row = (await voice_journey.rows())[0]
    assert row.spec.text == "Otamga qo‘ng‘iroq qilish"
    assert row.spec.on_date.isoformat() == extracted()["date"]


async def test_voice_cancel_discards_draft_without_saving(voice_journey, voice_route):
    await voice_journey.voice()
    await voice_journey.click("❌ Bekor qilish")
    assert await voice_journey.rows() == []
    assert "creation_token" not in await voice_journey.draft()


async def test_past_spoken_date_requires_future_date_selection(voice_journey, voice_route):
    voice_route.respond(200, json=response(extracted(date="2020-01-01")))
    await voice_journey.voice()
    assert (await voice_journey.draft())["step"] == "date"
    assert "o‘tib ketgan" in voice_journey.last.text
    assert await voice_journey.rows() == []


@pytest.mark.parametrize("intent", ["unsupported", "unclear"])
async def test_non_creation_voice_preserves_current_manual_draft(
    voice_journey, voice_route, intent
):
    await voice_journey.text("➕ Eslatma qo‘shish")
    await voice_journey.text("Asl eslatma")
    before = await voice_journey.draft()
    voice_route.respond(
        200,
        json=response(extracted(intent=intent, text=None, time=None, date=None, kind=None)),
    )
    await voice_journey.voice()
    assert await voice_journey.draft() == before
    assert "ovoz" in voice_journey.last.text.lower()


@pytest.mark.parametrize("status", [403, 429, 503])
async def test_api_failure_keeps_draft_and_hides_provider_secrets(
    voice_journey, voice_route, status
):
    await voice_journey.text("➕ Eslatma qo‘shish")
    before = await voice_journey.draft()
    voice_route.respond(status, json={"error": {"message": "voice-test-key"}})
    await voice_journey.voice()
    assert await voice_journey.draft() == before
    assert "qayta" in voice_journey.last.text
    assert "voice-test-key" not in voice_journey.last.text


@pytest.mark.parametrize(
    "changes",
    [{"time": "25:00"}, {"weekdays": [7]}, {"date": "2026-02-30"}, {"text": ""}],
)
async def test_invalid_ai_fields_cannot_be_saved(voice_journey, voice_route, changes):
    voice_route.respond(200, json=response(extracted(**changes)))
    await voice_journey.voice()
    assert "qayta" in voice_journey.last.text
    assert "creation_token" not in await voice_journey.draft()


@pytest.mark.parametrize("duration,size", [(121, 20), (12, 5 * 1024 * 1024 + 1)])
async def test_large_voice_is_rejected_before_download(voice_journey, respx_mock, duration, size):
    await voice_journey.voice(duration=duration, size=size)
    assert "qisqa" in voice_journey.last.text
    assert not any(isinstance(call, GetFile) for call in voice_journey.session.calls)
    assert not respx_mock.calls


async def test_group_voice_is_not_uploaded(voice_journey, respx_mock):
    await voice_journey.voice(group=True)
    assert "shaxsiy chat" in voice_journey.last.text
    assert not respx_mock.calls


@pytest.mark.parametrize("voice_journey", [None, "", "   "], indirect=True)
async def test_missing_key_returns_setup_message(voice_journey, respx_mock):
    await voice_journey.voice()
    assert "sozlanmagan" in voice_journey.last.text
    assert not respx_mock.calls
