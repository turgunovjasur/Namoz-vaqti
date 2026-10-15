import json

import httpx
import pytest
from pydantic import SecretStr

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.ai.model_catalog import ModelCatalog


async def test_model_catalog_requires_allowlist_and_successful_json_probe():
    calls = []

    async def respond(request):
        calls.append(request)
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"finishReason": "STOP", "content": {"parts": [{"text": '{"ok":true}'}]}}
                ]
            },
        )

    roles = build_role_registry(build_capability_registry())
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        catalog = ModelCatalog(
            GeminiClient(http, api_key=SecretStr("private-key")), ("allowed-model",)
        )
        with pytest.raises(ValueError):
            await catalog.validate("other-model", roles.get("accounting"))
        assert not calls
        await catalog.validate("allowed-model", roles.get("assistant"))
        body = json.loads(calls[0].content)
        assert "inlineData" in body["contents"][0]["parts"][1]
        assert "responseSchema" in body["generationConfig"]
    with pytest.raises(ExternalServiceError):
        await ModelCatalog(None, ("allowed-model",)).validate(
            "allowed-model", roles.get("accounting")
        )
