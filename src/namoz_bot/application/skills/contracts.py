"""Immutable execution identity supplied by the server, never by the language model."""

from dataclasses import dataclass

from namoz_bot.domain.agent_protocol import AgentContext


@dataclass(frozen=True)
class SkillCall:
    context: AgentContext
    role_id: str
    skill_id: str
    request_id: str
    operation_id: str
    idempotency_key: str
