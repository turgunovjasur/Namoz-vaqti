"""The manager routes only within current grants and freezes a concrete plan."""

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.manager import REVIEW_INSTRUCTION
from namoz_bot.application.view_context import ordinal_target, page_parameters
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.ports import RoleInterpreter, TaskStore
from namoz_bot.domain.agent_protocol import AgentContext, AgentViewState
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
        correcting = bool(
            pending and pending.status == "needs_input" and pending.plan.original_result
        )
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
                            or bool(
                                correcting and pending and c == pending.plan.selection.capability_id
                            )
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
        displayed = await self.tasks.displayed_view(context)
        if displayed and displayed.service_result:
            result = displayed.service_result
            entries = result.data.get("entries", [])
            view = AgentViewState.model_validate(
                {
                    "domain": result.domain,
                    "action": result.action,
                    "page": result.data.get("page", 0),
                    "today": result.data.get("today", False),
                    "ids": [r["id"] for r in entries if isinstance(r, dict)]
                    if isinstance(entries, list)
                    else [],
                }
            )
            context = context.model_copy(update={"last_view": view})
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
        if displayed and displayed.plan.selection.role_id != role_id:
            context = context.model_copy(update={"last_view": None})
        if pending and pending.service_result and pending.plan.selection.role_id == role_id:
            choices = pending.service_result.data.get("choices")
            if choices:
                context = context.model_copy(
                    update={"target_choices": AgentViewState.model_validate(choices)}
                )
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
        if correcting and pending and selected.continuation:
            target = pending.plan.selection
            chosen = self.access.roles.capabilities.get(selected.capability_id).spec
            if selected.role_id != target.role_id or (
                selected.capability_id != target.capability_id
                and chosen.correction_id != target.capability_id
            ):
                raise ClarificationRequired("Oldingi tuzatishdagi qiymatni aniqlashtiring.")
            selected = selected.model_copy(update={"capability_id": target.capability_id})
        elif (
            correcting
            and self.access.roles.capabilities.get(selected.capability_id).spec.requires_result
        ):
            raise ClarificationRequired("Bu javob oldingi tuzatishga tegishlimi? Aniqlashtiring.")
        followup = (
            pending is not None
            and pending.status == "needs_input"
            and (not correcting or selected.continuation)
            and (pending.plan.selection.role_id, pending.plan.selection.capability_id)
            == (selected.role_id, selected.capability_id)
        )
        if followup and pending is not None:
            changes = {k: v for k, v in selected.parameters.items() if v is not None}
            parameters = {**pending.plan.selection.parameters, **changes}
            if correcting:
                for key in ("target_id", "expected_record_revision", "intent"):
                    if key in pending.plan.selection.parameters:
                        parameters[key] = pending.plan.selection.parameters[key]
            selected = selected.model_copy(update={"parameters": parameters})
        spec = self.access.roles.capabilities.get(selected.capability_id).spec
        route = spec.routes[0]
        parameters = page_parameters(
            selected.parameters, route.domain, route.action, context.last_view
        )
        if parameters.get("ordinal") and parameters.get("target_id") is None:
            target_id = ordinal_target(parameters, route.domain, context)
            if target_id is not None:
                parameters["target_id"] = target_id
                parameters.pop("ordinal", None)
        selected = self.access.roles.validate_selection(
            selected.model_copy(update={"parameters": parameters})
        )
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
            original_result=pending.plan.original_result if followup and pending else None,
        )
        if not persist:
            return plan
        saved = await self.tasks.save_plan(
            plan, expected_revision=pending.plan.revision if followup and pending else None
        )
        if correcting and pending and not followup:
            await self.tasks.abandon_correction(
                context, pending.plan.task_id, pending.plan.revision
            )
        return saved.plan
