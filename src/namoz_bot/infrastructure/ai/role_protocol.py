"""Structured protocol and context shared by coordinator and role agents."""

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.reminders import TASHKENT
from namoz_bot.domain.workforce.tasks import TaskRevision


class RouteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    role_id: str | None
    question: str | None = Field(default=None, max_length=500)


class SpecialistResponse(BaseModel):
    continuation: bool = False
    model_config = ConfigDict(extra="forbid", strict=True)
    capability_id: str | None
    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    question: str | None = Field(default=None, max_length=500)


def provider_schema(
    schema: dict[str, Any], definitions: dict[str, Any] | None = None
) -> dict[str, JsonValue]:
    definitions = definitions or schema.get("$defs", {})
    if "$ref" in schema:
        return provider_schema(definitions[schema["$ref"].split("/")[-1]], definitions)
    result: dict[str, JsonValue]
    if "anyOf" in schema:
        choices = [c for c in schema["anyOf"] if c.get("type") != "null"]
        nullable = len(choices) != len(schema["anyOf"])
        result = (
            provider_schema(choices[0], definitions)
            if len(choices) == 1
            else {"anyOf": [provider_schema(c, definitions) for c in choices]}
        )
        if nullable:
            result["nullable"] = True
        return result
    result = {}
    for key, value in schema.items():
        if key == "type":
            result[key] = str(value).upper()
        elif key == "properties":
            result[key] = {k: provider_schema(v, definitions) for k, v in value.items()}
        elif key == "items":
            result[key] = provider_schema(value, definitions)
        elif key in {
            "enum",
            "required",
            "description",
            "minimum",
            "maximum",
            "minItems",
            "maxItems",
        }:
            result[key] = value
    return result


def safe_context(context: AgentContext, pending: TaskRevision | None) -> dict[str, JsonValue]:
    return {
        "current_time": context.message_time.astimezone(TASHKENT).isoformat(),
        "timezone": context.timezone,
        "language": context.language,
        "last_view": context.last_view.model_dump(mode="json") if context.last_view else None,
        "target_choices": context.target_choices.model_dump(mode="json")
        if context.target_choices
        else None,
        "pending": {
            "selection": pending.plan.selection.model_dump(mode="json"),
            "status": pending.status,
            "evidence": pending.service_result.model_dump(mode="json")
            if pending.service_result
            else None,
            "question": pending.plan.question,
            "feedback": pending.feedback,
        }
        if pending
        else None,
    }
