"""Compile corrections against saved evidence; negative feedback never repeats writes."""

from namoz_bot.application.workforce.planning import Manager
from namoz_bot.application.workforce.ports import TaskStore
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.tasks import (
    ClarificationRequired,
    TaskConflict,
    TaskMessage,
    TaskPlan,
)


class FeedbackService:
    def __init__(self, tasks: TaskStore, manager: Manager):
        self.tasks, self.manager = tasks, manager

    async def rate(
        self, *, context: AgentContext, task_id: str, revision: int, accepted: bool, request_id: str
    ) -> TaskMessage:
        await self.tasks.rate(context, task_id, revision, accepted, request_id)
        return TaskMessage(
            text="✅ Vazifa yakunlandi."
            if accepted
            else "Nima xato bo‘ldi yoki nimani boshqacha kutgandingiz? Matn yoki ovoz bilan ayting."
        )

    async def correct(
        self, *, context: AgentContext, task_id: str, revision: int, text: str, request_id: str
    ) -> TaskPlan:
        old = await self.tasks.get_owned(task_id, context)
        if (
            old.plan.revision != revision
            or old.status != "awaiting_correction"
            or old.service_result is None
        ):
            raise TaskConflict("Correction no longer current")
        candidate = await self.manager.plan(
            context=context, request_id=request_id, text=text, pending=old, persist=False
        )
        selected = candidate.selection
        if not selected.continuation:
            if self.manager.access.roles.capabilities.get(
                selected.capability_id
            ).spec.requires_result:
                raise ClarificationRequired(
                    "Tuzatish qaysi oldingi natijaga tegishli ekanini aniqlashtiring."
                )
            saved = await self.tasks.save_plan(candidate, expected_revision=None)
            await self.tasks.abandon_correction(context, task_id, revision)
            return saved.plan
        original = old.plan.selection
        if selected.role_id != original.role_id:
            raise ClarificationRequired(
                "Oldingi natijani tuzatish uchun o‘sha rolning xatosini ayting."
            )
        spec = self.manager.access.roles.capabilities.get(original.capability_id).spec
        target = spec.correction_id or (spec.id if spec.effect in {"read", "generate"} else None)
        if target is None:
            raise ClarificationRequired(
                "Bu amalni avtomatik qaytarib bo‘lmaydi. Kerakli yangi buyruqni alohida ayting."
            )
        if selected.capability_id not in {original.capability_id, target}:
            raise ClarificationRequired(
                "Qaysi qiymat xato bo‘lganini ayting; asl amal qayta yozilmaydi."
            )
        changes = {k: v for k, v in selected.parameters.items() if v is not None}
        params = {**original.parameters, **changes}
        evidence = old.service_result.data
        if target == "finance.correct":
            for key in ("target_id", "expected_record_revision", "intent"):
                params.pop(key, None)
            params.update(
                target_id=evidence["entry_id"],
                expected_record_revision=evidence["record_revision"],
                intent=evidence["kind"],
            )
            if "month" not in changes:
                params["month"] = str(evidence["period"])[:7]
            if "date" not in changes:
                params["date"] = evidence.get("occurred_on")
        elif target == "reminder.update":
            params.update(
                target_id=evidence["reminder_id"],
                expected_record_revision=evidence["record_revision"],
            )
            if params.get("kind") == "daily":
                params.pop("date", None)
                params["weekdays"] = []
            elif params.get("kind") == "once":
                params["weekdays"] = []
            elif params.get("kind") == "weekly":
                params.pop("date", None)
        elif target == "prayer.set_offset" and params.get("mode") == "add":
            if "minutes" not in evidence or params.get("prayer") != evidence.get("prayer"):
                raise ClarificationRequired(
                    "Yakuniy daqiqa farqini yangi buyruq bilan aniq ayting."
                )
            params["minutes"] = (
                int(str(evidence["minutes"]))
                - int(str(original.parameters["minutes"]))
                + int(str(params["minutes"]))
            )
            params["mode"] = "set"
        selection = self.manager.access.roles.validate_selection(
            CapabilitySelection(
                role_id=original.role_id,
                capability_id=target,
                parameters=params,
                question=selected.question,
                continuation=True,
            )
        )
        permission = await self.manager.access.require(context.user_id, selection.role_id, target)
        plan = candidate.model_copy(
            update={
                "task_id": task_id,
                "revision": revision + 1,
                "parent_revision": revision,
                "selection": selection,
                "permission": permission,
                "question": selected.question,
                "original_result": old.service_result,
            }
        )
        return (await self.tasks.save_plan(plan, expected_revision=revision)).plan
