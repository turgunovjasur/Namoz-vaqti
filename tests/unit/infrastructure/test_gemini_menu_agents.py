import json
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from pydantic import SecretStr

from namoz_bot.domain.agent_protocol import AgentContext, AgentHandoff, AgentSessionState
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.gemini_menu_agents import GeminiMenuAgentClient, GeminiRoutingClient

URL = "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)


def context():
    return AgentContext(
        bot_id=1, telegram_user_id=7, chat_id=7, user_id=1, message_time=NOW, region_code="Toshkent"
    )


def response(value):
    return {
        "candidates": [
            {"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(value)}]}}
        ]
    }


async def test_router_schema_has_no_domain_parameters_and_no_private_pending(respx_mock):
    route = respx_mock.post(URL).respond(
        200,
        json=response(
            {
                "domain": "accounting",
                "transcript": "120 ming kiyim",
                "control_action": None,
                "clarification": None,
                "multiple_tasks": False,
            }
        ),
    )
    pending = AgentSessionState(
        domain="accounting",
        action="expense",
        operation_id="old",
        origin_source_key="old",
        origin_time=NOW,
        parameters={"description": "Private finance"},
        missing_fields=["amount"],
        revision=1,
        expires_at=NOW + timedelta(hours=24),
    )
    async with httpx.AsyncClient() as http:
        value = await GeminiRoutingClient(
            http, api_key=SecretStr("secret"), model="test-model"
        ).route(
            text="120 ming kiyim",
            audio=None,
            mime_type="audio/ogg",
            context=context(),
            pending=pending,
        )
    body = json.loads(route.calls.last.request.content)
    assert "parameters" not in body["generationConfig"]["responseSchema"]["properties"]
    assert "Private finance" not in json.dumps(body) and "user_id" not in json.dumps(body)
    assert value.domain == "accounting" and route.call_count == 1


@pytest.mark.parametrize(
    "domain,action,expected",
    [
        ("prayer", "schedule", {"date", "prayer", "view"}),
        ("nasihat", "religious_excerpt", {"view"}),
        ("reminder", "create", {"text", "time", "kind", "date", "weekdays", "today", "page"}),
        (
            "accounting",
            "balance",
            {
                "amount",
                "currency",
                "category",
                "description",
                "month",
                "date",
                "page",
                "report_type",
            },
        ),
        ("settings", "open", {"view"}),
    ],
)
async def test_each_menu_has_narrow_schema_and_own_instruction(
    respx_mock, domain, action, expected
):
    route = respx_mock.post(URL).respond(
        200,
        json=response(
            {
                "domain": domain,
                "action": action,
                "parameters": {},
                "transcript": "test",
                "clarification": None,
                "multiple_tasks": False,
            }
        ),
    )
    handoff = AgentHandoff(
        domain=domain, request_id="r1", operation_id="op", input="test", context=context()
    )
    async with httpx.AsyncClient() as http:
        value = await GeminiMenuAgentClient(
            http, api_key=SecretStr("secret"), model="test-model", domain=domain
        ).interpret(handoff)
    body = json.loads(route.calls.last.request.content)
    schema = body["generationConfig"]["responseSchema"]
    assert set(schema["properties"]["parameters"]["properties"]) == expected
    assert schema["properties"]["domain"]["enum"] == [domain, "assistant"]
    assert domain in body["systemInstruction"]["parts"][0]["text"]
    assert not any("inlineData" in part for part in body["contents"][0]["parts"])
    assert value.domain == domain


async def test_router_audio_is_a_single_inline_upload(respx_mock):
    route = respx_mock.post(URL).respond(
        200,
        json=response(
            {
                "domain": "reminder",
                "transcript": "Kitob",
                "control_action": None,
                "clarification": None,
                "multiple_tasks": False,
            }
        ),
    )
    async with httpx.AsyncClient() as http:
        await GeminiRoutingClient(http, api_key=SecretStr("secret"), model="test-model").route(
            text=None, audio=b"OggS-test", mime_type="audio/ogg", context=context(), pending=None
        )
    body = json.loads(route.calls.last.request.content)
    assert sum("inlineData" in p for p in body["contents"][0]["parts"]) == 1


async def test_helper_cannot_return_another_domain(respx_mock):
    respx_mock.post(URL).respond(
        200,
        json=response(
            {
                "domain": "accounting",
                "action": "balance",
                "parameters": {},
                "transcript": "test",
                "clarification": None,
                "multiple_tasks": False,
            }
        ),
    )
    async with httpx.AsyncClient() as http:
        helper = GeminiMenuAgentClient(
            http, api_key=SecretStr("secret"), model="test-model", domain="reminder"
        )
        with pytest.raises(ExternalServiceError):
            await helper.interpret(
                AgentHandoff(
                    domain="reminder",
                    request_id="r1",
                    operation_id="op",
                    input="test",
                    context=context(),
                )
            )
