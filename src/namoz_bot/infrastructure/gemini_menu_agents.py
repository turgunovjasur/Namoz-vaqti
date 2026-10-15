"""A narrow multimodal router and separately prompted, text-only menu interpreters."""

import base64
import json
from copy import deepcopy
from datetime import timedelta
from typing import Any

import httpx
from pydantic import SecretStr

from namoz_bot.application.roles.base import COMMON_INSTRUCTION as COMMON_INSTRUCTION
from namoz_bot.application.roles.manager import INSTRUCTION as ROUTER_INSTRUCTION
from namoz_bot.application.roles.registry import specialist_instructions
from namoz_bot.application.voice_reminders import MAX_VOICE_BYTES
from namoz_bot.domain.agent_protocol import (
    ACTION_MODELS,
    AgentContext,
    AgentDecision,
    AgentHandoff,
    AgentRoutingDecision,
    AgentSessionState,
    Domain,
    menu_actions,
)
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.infrastructure.gemini_main_agent import RESPONSE_SCHEMA, GeminiMainAgentClient

ROUTER_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "domain": {
            "type": "STRING",
            "enum": ["prayer", "nasihat", "reminder", "accounting", "settings", "assistant"],
        },
        "transcript": {"type": "STRING"},
        "control_action": {
            "type": "STRING",
            "nullable": True,
            "enum": ["help", "clarify", "cancel", "resume", "confirm"],
        },
        "clarification": {"type": "STRING", "nullable": True},
        "multiple_tasks": {"type": "BOOLEAN"},
    },
    "required": ["domain", "transcript", "control_action", "clarification", "multiple_tasks"],
}


MENU_INSTRUCTIONS: dict[Domain, str] = specialist_instructions()


def menu_schema(domain: Domain) -> dict[str, Any]:
    if domain not in MENU_INSTRUCTIONS:
        raise ValueError("Unsupported menu agent")
    schema = deepcopy(RESPONSE_SCHEMA)
    fields = {
        field
        for (owner, action), model in ACTION_MODELS.items()
        if owner == domain and action in menu_actions(domain)
        for field in model.model_fields
    }
    schema["properties"]["domain"]["enum"] = [domain, "assistant"]
    schema["properties"]["action"]["enum"] = [*menu_actions(domain), "clarify"]
    parameters = schema["properties"]["parameters"]
    parameters["properties"] = {
        name: prop for name, prop in parameters["properties"].items() if name in fields
    }
    parameters["required"] = list(parameters["properties"])
    if "view" in parameters["properties"]:
        parameters["properties"]["view"]["enum"] = {
            "prayer": ["region", "offsets"],
            "nasihat": ["interval"],
            "settings": ["general", "daily", "region", "offsets"],
        }[domain]
    return schema


class GeminiRoutingClient:
    def __init__(self, http_client: httpx.AsyncClient, *, api_key: SecretStr, model: str) -> None:
        self._client = GeminiMainAgentClient(
            http_client,
            api_key=api_key,
            model=model,
            system_instruction=ROUTER_INSTRUCTION,
            response_schema=ROUTER_SCHEMA,
        )

    async def route(
        self,
        *,
        text: str | None,
        audio: bytes | None,
        mime_type: str,
        context: AgentContext,
        pending: AgentSessionState | None,
    ) -> AgentRoutingDecision:
        if (text is None) == (audio is None):
            raise ValueError("Bitta matn yoki ovoz yuboring.")
        if text is not None and not 1 <= len(text.strip()) <= 2000:
            raise ValueError("Xabar 1–2000 belgidan iborat bo‘lsin.")
        if audio is not None and (
            not audio
            or len(audio) > MAX_VOICE_BYTES
            or mime_type
            not in {
                "audio/ogg",
                "audio/opus",
                "audio/mpeg",
                "audio/mp4",
            }
        ):
            raise ValueError("Ovozli xabar formati yoki hajmi noto‘g‘ri.")
        local = context.message_time.astimezone(TASHKENT)
        safe = {
            "message_time": local.isoformat(),
            "timezone": context.timezone,
            "language": context.language,
            "last_view": context.last_view.model_dump(exclude={"ids"})
            if context.last_view
            else None,
            "current_date": local.date().isoformat(),
            "tomorrow_date": (local + timedelta(days=1)).date().isoformat(),
            "pending": {
                "domain": pending.domain,
                "action": pending.action,
                "missing_fields": pending.missing_fields,
            }
            if pending
            else None,
        }
        parts: list[dict[str, Any]] = [{"text": json.dumps(safe, ensure_ascii=False)}]
        if audio is not None:
            parts.append(
                {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": base64.b64encode(audio).decode("ascii"),
                    }
                }
            )
        else:
            parts.append({"text": text})
        payload = await self._client.generate_json(parts, max_output_tokens=2048)
        try:
            return AgentRoutingDecision.model_validate_json(json.dumps(payload))
        except ValueError:
            raise ExternalServiceError("Xabarning yo‘nalishini aniqlab bo‘lmadi.") from None


class GeminiMenuAgentClient:
    def __init__(
        self, http_client: httpx.AsyncClient, *, api_key: SecretStr, model: str, domain: Domain
    ) -> None:
        self.domain = domain
        self._client = GeminiMainAgentClient(
            http_client,
            api_key=api_key,
            model=model,
            system_instruction=COMMON_INSTRUCTION + "\n\n" + MENU_INSTRUCTIONS[domain].strip(),
            response_schema=menu_schema(domain),
        )

    async def interpret(self, handoff: AgentHandoff) -> AgentDecision:
        if handoff.domain != self.domain:
            raise ValueError("Wrong menu handoff")
        decision = await self._client.extract(
            text=handoff.input,
            audio=None,
            mime_type="audio/ogg",
            context=handoff.context,
            pending=handoff.pending,
            request_id=handoff.request_id,
        )
        if decision.domain != self.domain and (decision.domain, decision.action) != (
            "assistant",
            "clarify",
        ):
            raise ExternalServiceError("Yordamchi agent o‘z vakolatidan chiqdi.")
        if decision.domain == self.domain and decision.action not in menu_actions(self.domain):
            raise ExternalServiceError("Yordamchi agent o‘z vakolatidan chiqdi.")
        return decision
