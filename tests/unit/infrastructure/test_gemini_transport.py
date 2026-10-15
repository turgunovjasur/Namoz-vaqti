import json

import httpx
import pytest
from pydantic import SecretStr

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient

URL = "https://generativelanguage.googleapis.com/v1beta/models/test-model:generateContent"
SCHEMA = {"type": "OBJECT", "properties": {"value": {"type": "INTEGER"}}}


async def generate(http, **options):
    return await GeminiClient(http, api_key=SecretStr("private-test-key")).generate_json(
        model="test-model",
        instruction="Return a value",
        schema=SCHEMA,
        parts=[{"text": "synthetic"}],
        max_output_tokens=1024,
        **options,
    )


async def test_transport_joins_visible_parts_and_keeps_credentials_out_of_url(respx_mock):
    route = respx_mock.post(URL).respond(
        200,
        json={
            "candidates": [
                {
                    "finishReason": "STOP",
                    "content": {
                        "parts": [
                            {"thought": True, "text": "private reasoning"},
                            {"text": '{"value":'},
                            {"text": "7}"},
                        ]
                    },
                }
            ],
        },
    )
    async with httpx.AsyncClient() as http:
        assert await generate(http) == {"value": 7}
    request = route.calls.last.request
    assert "private-test-key" not in str(request.url)
    assert request.headers["x-goog-api-key"] == "private-test-key"
    body = json.loads(request.content)
    assert body["generationConfig"] == {
        "temperature": 0,
        "maxOutputTokens": 1024,
        "responseMimeType": "application/json",
        "responseSchema": SCHEMA,
    }
    assert request.extensions["timeout"] == {"connect": 5, "read": 60, "write": 15, "pool": 5}


@pytest.mark.parametrize(
    "payload",
    [
        {"candidates": []},
        {"candidates": [{"finishReason": "MAX_TOKENS", "content": {"parts": [{"text": "{}"}]}}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "[1]"}]}}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "not-json"}]}}]},
        {"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": "x" * 16001}]}}]},
    ],
)
async def test_incomplete_or_invalid_provider_response_is_not_a_result(respx_mock, payload):
    respx_mock.post(URL).respond(200, json=payload)
    async with httpx.AsyncClient() as http:
        with pytest.raises(ExternalServiceError):
            await generate(http)


@pytest.mark.parametrize("failure", ["http", "timeout"])
async def test_transport_errors_do_not_expose_credentials_or_provider_body(respx_mock, failure):
    route = respx_mock.post(URL)
    if failure == "http":
        route.respond(403, text="private-test-key synthetic private response")
    else:
        route.mock(side_effect=httpx.ReadTimeout("private-test-key synthetic private response"))
    async with httpx.AsyncClient() as http:
        with pytest.raises(ExternalServiceError) as error:
            await generate(http)
    assert "private-test-key" not in str(error.value)
    assert "synthetic private response" not in str(error.value)


async def test_book_caller_can_keep_its_smaller_response_and_timeout_bounds(respx_mock):
    route = respx_mock.post(URL).respond(
        200,
        json={
            "candidates": [
                {"finishReason": "STOP", "content": {"parts": [{"text": '{"value":7}'}]}}
            ],
        },
    )
    async with httpx.AsyncClient() as http:
        assert await generate(
            http,
            temperature=0.3,
            timeout=httpx.Timeout(connect=5, read=35, write=5, pool=5),
            max_response_chars=1200,
        ) == {"value": 7}
    assert route.calls.last.request.extensions["timeout"]["read"] == 35
    assert json.loads(route.calls.last.request.content)["generationConfig"]["temperature"] == 0.3
