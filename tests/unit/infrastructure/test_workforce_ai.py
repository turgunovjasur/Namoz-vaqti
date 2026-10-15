import json

import httpx
from pydantic import SecretStr

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.ai.role_interpreter import GeminiRoleInterpreter
from namoz_bot.infrastructure.ai.transcription import GeminiTranscriber
from tests.integration.test_agent_sessions import NOW


async def test_transcription_is_separate_from_routing_and_strict_identity_free_schema():
    bodies = []
    replies = [
        {"transcript": "Bu oy qancha sarfladim?"},
        {"role_id": "accounting", "question": None},
        {
            "capability_id": "finance.report",
            "parameters": {"report_type": "expense"},
            "question": None,
        },
    ]

    async def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {"parts": [{"text": json.dumps(replies.pop(0))}]},
                    }
                ]
            },
        )

    caps = build_capability_registry()
    roles = build_role_registry(caps)
    context = AgentContext(
        bot_id=123456,
        user_id=1,
        telegram_user_id=7,
        chat_id=7,
        message_time=NOW,
        region_code="Toshkent",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        transport = GeminiClient(http, api_key=SecretStr("private-key"))
        transcript = await GeminiTranscriber(transport).transcribe(
            b"OggS-test", "audio/ogg", model="assistant-model"
        )
        ai = GeminiRoleInterpreter(transport)
        role = roles.get("accounting").model_copy(update={"capability_ids": ("finance.report",)})
        assert (
            await ai.route(
                text=transcript, context=context, roles=(role,), pending=None, model="manager-model"
            )
            == "accounting"
        )
        selection = await ai.interpret(
            text=transcript,
            context=context,
            role=role,
            capabilities=(caps.get("finance.report").spec,),
            pending=None,
            model="accountant-model",
        )
        assert selection.capability_id == "finance.report"
    assert "inlineData" in bodies[0]["contents"][0]["parts"][0]
    assert all("inlineData" not in str(body["contents"]) for body in bodies[1:])
    assert "finance.expense" not in str(bodies[2]["generationConfig"]["responseSchema"])
    assert "user_id" not in str(bodies[2]["generationConfig"]["responseSchema"])


async def test_no_parameter_capability_omits_empty_provider_object():
    bodies = []

    async def respond(request):
        bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "finishReason": "STOP",
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {"capability_id": "finance.balance", "question": None}
                                    )
                                }
                            ]
                        },
                    }
                ]
            },
        )

    caps = build_capability_registry()
    role = (
        build_role_registry(caps)
        .get("accounting")
        .model_copy(update={"capability_ids": ("finance.balance",)})
    )
    context = AgentContext(
        bot_id=123456,
        user_id=1,
        telegram_user_id=7,
        chat_id=7,
        message_time=NOW,
        region_code="Toshkent",
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        result = await GeminiRoleInterpreter(
            GeminiClient(http, api_key=SecretStr("key"))
        ).interpret(
            text="Balans",
            context=context,
            role=role,
            capabilities=(caps.get("finance.balance").spec,),
            pending=None,
            model="model",
        )
    schema = bodies[0]["generationConfig"]["responseSchema"]
    assert "parameters" not in schema["properties"]
    assert result.parameters == {}
