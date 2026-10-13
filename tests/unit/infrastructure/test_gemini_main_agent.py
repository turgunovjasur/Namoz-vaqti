import json
from datetime import UTC, datetime

import httpx
import pytest
from pydantic import SecretStr

from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.gemini_main_agent import GeminiMainAgentClient

URL = "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"


def context():
    return AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=1,
        message_time=datetime(2026, 10, 13, 10, tzinfo=UTC),
        region_code="Toshkent",
    )


def response(**changes):
    decision = {
        "domain": "accounting",
        "action": "balance",
        "parameters": {},
        "transcript": "Balansim qancha?",
        "clarification": None,
        "multiple_tasks": False,
    } | changes
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(decision)}]}}
        ]
    }


@pytest.mark.parametrize("audio", [None, b"OggS-test"])
async def test_text_or_audio_extraction_is_one_call(respx_mock, audio):
    route = respx_mock.post(URL).respond(200, json=response())
    async with httpx.AsyncClient() as http:
        client = GeminiMainAgentClient(http, api_key=SecretStr("secret"), model="test-model")
        decision = await client.extract(
            text="Balansim qancha?" if audio is None else None,
            audio=audio,
            mime_type="audio/ogg",
            context=context(),
            pending=None,
        )
    assert decision.action == "balance"
    assert route.call_count == 1
    body = json.loads(route.calls.last.request.content)
    assert body["generationConfig"]["responseMimeType"] == "application/json"
    assert "user_id" not in body["contents"][0]["parts"][0]["text"]
    assert ("inlineData" in body["contents"][0]["parts"][-1]) == (audio is not None)


@pytest.mark.parametrize(
    "payload", [response(user_id=99), response(action="execute_sql"), {"candidates": []}]
)
async def test_bad_json_or_identity_override_never_becomes_request(respx_mock, payload):
    respx_mock.post(URL).respond(200, json=payload)
    async with httpx.AsyncClient() as http:
        client = GeminiMainAgentClient(http, api_key=SecretStr("secret"), model="test-model")
        with pytest.raises(ExternalServiceError):
            await client.extract(
                text="test", audio=None, mime_type="audio/ogg", context=context(), pending=None
            )


async def test_timeout_has_safe_error(respx_mock):
    respx_mock.post(URL).mock(side_effect=httpx.ReadTimeout("sensitive-input"))
    async with httpx.AsyncClient() as http:
        client = GeminiMainAgentClient(http, api_key=SecretStr("secret"), model="test-model")
        with pytest.raises(ExternalServiceError) as error:
            await client.extract(
                text="test", audio=None, mime_type="audio/ogg", context=context(), pending=None
            )
    assert "sensitive" not in str(error.value)


async def test_oversized_voice_rejected_before_http(respx_mock):
    async with httpx.AsyncClient() as http:
        client = GeminiMainAgentClient(http, api_key=SecretStr("secret"), model="test-model")
        with pytest.raises(ValueError):
            await client.extract(
                text=None,
                audio=b"x" * (5 * 1024 * 1024 + 1),
                mime_type="audio/ogg",
                context=context(),
                pending=None,
            )
    assert not respx_mock.calls
