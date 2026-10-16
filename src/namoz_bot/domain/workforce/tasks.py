"""Versioned approved work, bounded review and transport-neutral messages."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from namoz_bot.domain.agent_protocol import AgentContext, AgentResult
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.profiles import PermissionSnapshot, RoleModelSetting
from namoz_bot.domain.workforce.roles import RoleDefinition

TaskStatus = Literal[
    "draft",
    "needs_input",
    "awaiting_approval",
    "queued",
    "running",
    "reviewing",
    "awaiting_feedback",
    "awaiting_correction",
    "done",
    "cancelled",
    "failed",
]


class ClarificationRequired(Exception):
    """A safe question instead of guessing a role or operation."""


class TaskConflict(Exception):
    """A foreign, stale, expired or superseded task cannot advance."""


class TaskPlan(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    protocol_version: Literal[2] = 2
    coordinator_role: Literal["assistant", "manager"] = "manager"
    task_id: str = Field(pattern=r"^[a-f0-9]{20}$")
    revision: int = Field(ge=1, le=100000)
    request_id: str = Field(min_length=1, max_length=100)
    context: AgentContext
    permission: PermissionSnapshot
    role: RoleDefinition
    models: dict[str, RoleModelSetting]
    selection: CapabilitySelection
    transcript: str = Field(min_length=1, max_length=2000)
    expires_at: datetime
    question: str | None = Field(default=None, max_length=500)
    parent_revision: int | None = None
    review_instruction: str = ""
    original_result: AgentResult | None = None

    @model_validator(mode="after")
    def trusted_binding(self) -> "TaskPlan":
        p, s = self.permission, self.selection
        if (
            p.user_id != self.context.user_id
            or (p.role_id, p.capability_id) != (s.role_id, s.capability_id)
            or self.role.id != s.role_id
        ):
            raise ValueError("Task identity or permission mismatch")
        if s.capability_id not in self.role.capability_ids or any(
            r not in self.models for r in ("assistant", "manager", s.role_id)
        ):
            raise ValueError("Missing role scope or model snapshot")
        if self.expires_at.tzinfo is None:
            raise ValueError("Aware expiration required")
        return self


class ReviewVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    decision: Literal["accept", "revise", "clarify"]
    issues: list[str] = Field(default_factory=list, max_length=5)

    @model_validator(mode="after")
    def bounded_issues(self) -> "ReviewVerdict":
        if any(not issue.strip() or len(issue) > 300 for issue in self.issues):
            raise ValueError("Invalid review issues")
        return self


class TaskRevision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    plan: TaskPlan
    status: TaskStatus
    service_result: AgentResult | None = None
    review: ReviewVerdict | None = None
    feedback: str | None = None
    review_attempts: int = 0


class ClaimedTask(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    task: TaskRevision
    lease_token: str


class TaskMessage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str = Field(min_length=1, max_length=16000)
    task_id: str | None = None
    revision: int | None = None
    buttons: Literal["approval", "feedback"] | None = None
