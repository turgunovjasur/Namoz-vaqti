"""A native skill needs typed I/O and one executor, without legacy action registration."""

from collections.abc import Awaitable, Callable
from typing import Literal

from pydantic import BaseModel, JsonValue

from namoz_bot.application.agent_sessions import AgentTransaction
from namoz_bot.application.capabilities.base import Capability
from namoz_bot.application.skills.contracts import SkillCall
from namoz_bot.domain.agent_protocol import AgentResult
from namoz_bot.domain.workforce.capabilities import CapabilitySpec
from namoz_bot.domain.workforce.tasks import TaskPlan

RESERVED_IDENTITIES = frozenset(
    {
        "user_id",
        "telegram_user_id",
        "telegram_id",
        "actor_id",
        "bot_id",
        "chat_id",
        "role_id",
        "skill_id",
        "request_id",
        "operation_id",
        "idempotency_key",
    }
)


class NativeSkill[P: BaseModel, R: BaseModel](Capability):
    def __init__(
        self,
        *,
        id: str,
        name: str,
        description: str,
        input_model: type[P],
        output_model: type[R],
        execute: Callable[[SkillCall, P, AgentTransaction], Awaitable[R | dict[str, JsonValue]]],
        render: Callable[[R], str],
        effect: Literal["read", "write", "generate"],
        guidance: str = "",
        idempotent: bool = False,
    ) -> None:
        if RESERVED_IDENTITIES.intersection(input_model.model_fields):
            raise ValueError("Skill input cannot contain server-owned identity fields")
        if input_model.model_config.get("extra") != "forbid":
            raise ValueError("Skill input model must forbid extra parameters")
        if effect == "write" and not idempotent:
            raise ValueError("Write skills must implement durable idempotency")
        self.spec = CapabilitySpec(
            id=id,
            name=name,
            description=description,
            parameters_model=input_model,
            result_model=output_model,
            effect=effect,
            guidance=guidance,
        )
        self.input_model, self.output_model = input_model, output_model
        self._executor, self._renderer = execute, render

    async def prepare_plan(self, plan: TaskPlan) -> AgentResult | None:
        self.input_model.model_validate(plan.selection.parameters)
        return None

    async def execute_plan(
        self, plan: TaskPlan, transaction: AgentTransaction, prepared: AgentResult | None
    ) -> AgentResult:
        if plan.selection.capability_id != self.spec.id:
            raise ValueError("Skill outside selected operation")
        params = self.input_model.model_validate(plan.selection.parameters)
        call = SkillCall(
            context=plan.context,
            role_id=plan.selection.role_id,
            skill_id=self.spec.id,
            request_id=plan.request_id,
            operation_id=f"{plan.task_id}{plan.revision:06x}",
            idempotency_key=f"task:{plan.task_id}:{plan.revision}",
        )
        value = self.output_model.model_validate(await self._executor(call, params, transaction))
        text = self._renderer(value)
        if not 1 <= len(text.strip()) <= 3500:
            raise ValueError("Skill renderer must return 1..3500 characters")
        return AgentResult(
            request_id=plan.request_id,
            operation_id=call.operation_id,
            domain="assistant",
            action="skill_result",
            status="done",
            data={"skill_id": self.spec.id, "payload": value.model_dump(mode="json"), "text": text},
            effect="committed" if self.spec.effect == "write" else "none",
        )
