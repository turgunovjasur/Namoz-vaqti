"""Bounded Gemini JSON transport; semantic validation belongs to each caller."""

import json
import re
from typing import cast

import httpx
from pydantic import JsonValue, SecretStr

from namoz_bot.domain.errors import ExternalServiceError


class GeminiClient:
    def __init__(self, http_client: httpx.AsyncClient, *, api_key: SecretStr) -> None:
        self._http = http_client
        self._key = api_key

    async def generate_json(
        self,
        *,
        model: str,
        instruction: str,
        schema: dict[str, JsonValue],
        parts: list[dict[str, JsonValue]],
        max_output_tokens: int = 4096,
        temperature: float = 0,
        timeout: httpx.Timeout | None = None,  # noqa: ASYNC109 - HTTPX phase timeouts
        max_response_chars: int = 16000,
    ) -> dict[str, JsonValue]:
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", model):
            raise ValueError("Model nomi noto‘g‘ri.")
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            response = await self._http.post(
                url,
                headers={"x-goog-api-key": self._key.get_secret_value().strip()},
                json={
                    "systemInstruction": {"parts": [{"text": instruction}]},
                    "contents": [{"role": "user", "parts": parts}],
                    "generationConfig": {
                        "temperature": temperature,
                        "maxOutputTokens": max_output_tokens,
                        "responseMimeType": "application/json",
                        "responseSchema": schema,
                    },
                },
                timeout=timeout or httpx.Timeout(connect=5, read=60, write=15, pool=5),
            )
        except httpx.HTTPError:
            raise ExternalServiceError("AI xizmati bilan aloqa bo‘lmadi.") from None
        if not response.is_success:
            raise ExternalServiceError("AI xizmati vaqtincha ishlamayapti.")
        try:
            candidate = response.json()["candidates"][0]
            if candidate.get("finishReason") != "STOP":
                raise ValueError("Incomplete response")
            text = "".join(
                part["text"]
                for part in candidate["content"]["parts"]
                if "text" in part and not part.get("thought")
            )
            if not text or len(text) > max_response_chars:
                raise ValueError("Empty or oversized response")
            payload = json.loads(text)
            if not isinstance(payload, dict):
                raise ValueError("Object response required")
            return cast(dict[str, JsonValue], payload)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError):
            raise ExternalServiceError("AI javobi to‘liq emas yoki noto‘g‘ri.") from None
