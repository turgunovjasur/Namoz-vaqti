"""Configured Gemini models must pass a harmless structured-output probe."""

import base64

from pydantic import JsonValue

from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.workforce.profiles import ModelOption
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient


class ModelCatalog:
    def __init__(self, transport: GeminiClient | None, allowed_models: tuple[str, ...]) -> None:
        self.transport = transport
        self.allowed_models = tuple(dict.fromkeys(allowed_models))

    def list_for_role(self, role_id: str) -> tuple[ModelOption, ...]:
        return tuple(ModelOption(id=model, name=model) for model in self.allowed_models)

    async def validate(self, model_id: str, role: RoleDefinition) -> None:
        if model_id not in self.allowed_models:
            raise ValueError("Model serverdagi ruxsat etilgan ro‘yxatda yo‘q.")
        if self.transport is None:
            raise ExternalServiceError("Gemini xizmati sozlanmagan.")
        parts: list[dict[str, JsonValue]] = [{"text": 'Return {"ok":true}.'}]
        if role.id == "assistant":
            # 80 ms of synthetic silent PCM WAV; no user audio or business call.
            import io
            import wave

            data = io.BytesIO()
            with wave.open(data, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(8000)
                wav.writeframes(bytes(1280))
            parts.append(
                {
                    "inlineData": {
                        "mimeType": "audio/wav",
                        "data": base64.b64encode(data.getvalue()).decode(),
                    }
                }
            )
        result = await self.transport.generate_json(
            model=model_id,
            instruction="Validate JSON output support. Return only an object with ok=true.",
            schema={
                "type": "OBJECT",
                "properties": {"ok": {"type": "BOOLEAN"}},
                "required": ["ok"],
            },
            parts=parts,
            max_output_tokens=64,
        )
        if result != {"ok": True}:
            raise ExternalServiceError("Model tekshiruvidan o‘tmadi.")
