"""The manager routes only within current grants and freezes a concrete plan."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.manager import REVIEW_INSTRUCTION
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.ports import RoleInterpreter, TaskStore
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.profiles import AccessDenied, RoleModelSetting
from namoz_bot.domain.workforce.tasks import ClarificationRequired, TaskPlan, TaskRevision


class Manager:
    def __init__(
        self,
        access: AccessService,
        profiles: ProfileService,
        interpreter: RoleInterpreter,
        tasks: TaskStore,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.access, self.profiles, self.interpreter, self.tasks = (
            access,
            profiles,
            interpreter,
            tasks,
        )
        self.clock = clock

    async def plan(
        self,
        *,
        context: AgentContext,
        request_id: str,
        text: str,
        pending: TaskRevision | None,
        assistant_model: RoleModelSetting | None = None,
        persist: bool = True,
    ) -> TaskPlan:
        if not 1 <= len(text.strip()) <= 2000:
            raise ValueError("Xabar 1–2000 belgidan iborat bo‘lsin.")
        allowed = await self.access.available_roles(context.user_id)
        roles = tuple(
            r.model_copy(
                update={
                    "capability_ids": tuple(
                        c
                        for c in r.capability_ids
                        if "conversation" in self.access.roles.capabilities.get(c).spec.entrypoints
                        and (
                            not self.access.roles.capabilities.get(c).spec.requires_result
                            or bool(pending and pending.status == "awaiting_correction")
                        )
                    )
                }
            )
            for r in allowed
        )
        roles = tuple(r for r in roles if r.capability_ids)
        if not roles:
            raise AccessDenied(
                "Sizga hali imkoniyatlar yoqilmagan. Administratorga murojaat qiling."
            )
        models = {r: await self.profiles.model(r) for r in ("assistant", "manager")}
        if assistant_model is not None:
            models["assistant"] = assistant_model
        described = tuple(
            r.model_copy(
                update={
                    "description": r.description
                    + " "
                    + "; ".join(
                        self.access.roles.capabilities.get(c).spec.name for c in r.capability_ids
                    )
                }
            )
            for r in roles
        )
        role_id = await self.interpreter.route(
            text=text,
            context=context,
            roles=described,
            pending=pending,
            model=models["manager"].model_id,
        )
        role = next((r for r in roles if r.id == role_id), None)
        if role is None:
            raise AccessDenied("Selected role is not granted")
        models[role_id] = await self.profiles.model(role_id)
        raw = await self.interpreter.interpret(
            text=text,
            context=context,
            role=role,
            capabilities=tuple(
                self.access.roles.capabilities.get(c).spec for c in role.capability_ids
            ),
            pending=pending,
            model=models[role_id].model_id,
        )
        selected = CapabilitySelection.model_validate(raw.model_dump())
        if selected.role_id != role_id or selected.capability_id not in role.capability_ids:
            raise AccessDenied("Selected capability is not granted")
        explicit = [
            r for r in roles if r.name.casefold() in text.casefold() or r.id in text.casefold()
        ]
        owners = [r for r in roles if selected.capability_id in r.capability_ids]
        if len(owners) > 1 and not explicit:
            raise ClarificationRequired(
                "Bu imkoniyat bir nechta rolda bor. Qaysi rol orqali: "
                + ", ".join(r.name for r in owners)
                + "?"
            )
        if len(explicit) == 1 and explicit[0].id != role_id:
            raise AccessDenied("Explicit role mismatch")
        followup = (
            pending is not None
            and pending.status == "needs_input"
            and (pending.plan.selection.role_id, pending.plan.selection.capability_id)
            == (selected.role_id, selected.capability_id)
        )
        if followup and pending is not None:
            selected = selected.model_copy(
                update={"parameters": {**pending.plan.selection.parameters, **selected.parameters}}
            )
        selected = self.access.roles.validate_selection(selected)
        permission = await self.access.require(
            context.user_id, selected.role_id, selected.capability_id
        )
        task_id = pending.plan.task_id if followup and pending else uuid4().hex[:20]
        revision = pending.plan.revision + 1 if followup and pending else 1
        plan = TaskPlan(
            task_id=task_id,
            revision=revision,
            request_id=request_id,
            context=context,
            permission=permission,
            role=role,
            models=models,
            selection=selected,
            transcript=text,
            expires_at=self.clock() + timedelta(minutes=15),
            question=selected.question,
            review_instruction=REVIEW_INSTRUCTION,
            parent_revision=pending.plan.revision if followup and pending else None,
        )
        if not persist:
            return plan
        saved = await self.tasks.save_plan(
            plan, expected_revision=pending.plan.revision if followup and pending else None
        )
        return saved.plan
