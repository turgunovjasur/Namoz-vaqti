"""Yordamchi handles input and approvals without executing business work."""

from collections.abc import Callable

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.workforce.feedback import FeedbackService
from namoz_bot.application.workforce.planning import Manager
from namoz_bot.application.workforce.ports import TaskStore, Transcriber
from namoz_bot.domain.agent_protocol import AgentContext
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.tasks import (
    ClarificationRequired,
    TaskConflict,
    TaskMessage,
    TaskPlan,
    TaskRevision,
)


class AssistantService:
    def __init__(
        self,
        manager: Manager,
        transcriber: Transcriber,
        tasks: TaskStore,
        profiles: ProfileService,
        render_plan: Callable[[TaskPlan], str],
    ):
        self.manager, self.transcriber, self.tasks, self.profiles, self.render_plan = (
            manager,
            transcriber,
            tasks,
            profiles,
            render_plan,
        )
        self.feedback = FeedbackService(tasks, manager)

    def _reply(self, task: TaskRevision) -> TaskMessage:
        if task.status == "awaiting_approval":
            return TaskMessage(
                text=self.render_plan(task.plan),
                task_id=task.plan.task_id,
                revision=task.plan.revision,
                buttons="approval",
            )
        if task.status == "needs_input":
            question = task.plan.question or (
                task.service_result.question if task.service_result else None
            )
            return TaskMessage(
                text=self.render_plan(task.plan) + "\n\n" + (question or "Buyruqni aniqlashtiring.")
            )
        return TaskMessage(text="Bu vazifa allaqachon qabul qilingan yoki yakunlangan.")

    async def receive(
        self,
        context: AgentContext,
        request_id: str,
        *,
        text: str | None = None,
        audio: bytes | None = None,
        mime_type: str = "audio/ogg",
    ) -> TaskMessage:
        if cached := await self.tasks.find_input(context, request_id):
            return self._reply(cached)
        if text and text.strip().lower() == "/resume":
            pending = await self.tasks.pending(context)
            return (
                self._reply(pending)
                if pending
                else TaskMessage(text="Tugallanmagan qoralama yo‘q.")
            )
        await self.tasks.invalidate(context)
        try:
            if (text is None) == (audio is None):
                raise ValueError("Bitta matn yoki ovoz yuboring.")
            assistant_model = await self.profiles.model("assistant")
            if audio is not None:
                text = await self.transcriber.transcribe(
                    audio, mime_type, model=assistant_model.model_id
                )
            assert text is not None
            pending = await self.tasks.pending(context)
            if pending and pending.status == "awaiting_correction":
                plan = await self.feedback.correct(
                    context=context,
                    task_id=pending.plan.task_id,
                    revision=pending.plan.revision,
                    text=text,
                    request_id=request_id,
                )
            else:
                plan = await self.manager.plan(
                    context=context,
                    request_id=request_id,
                    text=text,
                    pending=pending,
                    assistant_model=assistant_model,
                )
            return self._reply(await self.tasks.get_owned(plan.task_id, context))
        except (ClarificationRequired, AccessDenied) as exc:
            return TaskMessage(text=str(exc))
        except (ValueError, ExternalServiceError):
            return TaskMessage(
                text="Xabarni tushunib bo‘lmadi. Aniqlashtirib qayta yuboring; "
                "oldingi tasdiq bekor qilindi."
            )

    async def approve(
        self, context: AgentContext, request_id: str, task_id: str, revision: int, accepted: bool
    ) -> TaskMessage:
        try:
            task = await self.tasks.get_owned(task_id, context)
            if task.plan.revision != revision:
                raise TaskConflict("Old revision")
            if accepted:
                s = task.plan.selection
                await self.manager.access.require(context.user_id, s.role_id, s.capability_id)
            task = await self.tasks.approve(task_id, revision, context, request_id, accepted)
            if task.status == "cancelled":
                return TaskMessage(text="❌ Buyruq bekor qilindi.", dismiss_source=True)
            return TaskMessage(dismiss_source=True)
        except (TaskConflict, AccessDenied):
            return TaskMessage(
                text="Bu tasdiq eskirgan, sizga tegishli emas yoki imkoniyat o‘chirilgan."
            )
