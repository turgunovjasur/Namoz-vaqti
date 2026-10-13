"""Route one intent, preserve partial tasks and execute only validated effects."""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol

from namoz_bot.application.agent_adapters import AgentAdapters, result
from namoz_bot.application.agent_sessions import AgentStore
from namoz_bot.domain.agent_protocol import (
    AgentContext,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRevisionConflict,
    AgentSessionState,
)
from namoz_bot.domain.errors import ExternalServiceError, ReligiousReminderCooldownError
from namoz_bot.domain.reminders import TASHKENT

logger = logging.getLogger(__name__)


class AgentExtractor(Protocol):
    async def extract(
        self,
        *,
        text: str | None,
        audio: bytes | None,
        mime_type: str,
        context: AgentContext,
        pending: AgentSessionState | None,
    ) -> AgentDecision: ...


class MainAgent:
    def __init__(
        self,
        extractor: AgentExtractor,
        store: AgentStore,
        *,
        adapters: AgentAdapters | None = None,
        now: Callable[[], datetime] | None = None,
        cooldown_seconds: int = 20,
    ) -> None:
        self.store = store
        self._extractor = extractor
        self._adapters = adapters or AgentAdapters()
        self._now = now or (lambda: datetime.now(UTC))
        self._slots = asyncio.Semaphore(3)
        self._cooldown = cooldown_seconds
        self._voice_until: dict[int, float] = {}

    async def has_pending(self, user_id: int, now: datetime) -> bool:
        return await self.store.get_session(user_id, now) is not None

    def _request(
        self,
        context: AgentContext,
        request_id: str,
        decision: AgentDecision,
        pending: AgentSessionState | None = None,
    ) -> AgentRequest:
        operation = (
            pending.operation_id
            if pending
            else hashlib.sha256(
                f"{context.bot_id}:{context.user_id}:{request_id}".encode(),
            ).hexdigest()[:32]
        )
        params = dict(pending.parameters) if pending else {}
        if decision.domain == "reminder" and "kind" in decision.parameters:
            if decision.parameters["kind"] != params.get("kind"):
                params.pop("date", None)
                params.pop("weekdays", None)
        params.update(decision.parameters)
        if (
            not pending
            and decision.domain == "accounting"
            and decision.action in {"income", "expense"}
        ):
            if not params.get("date") and not params.get("month"):
                params["date"] = context.message_time.astimezone(TASHKENT).date().isoformat()
        return AgentRequest.model_validate(
            {
                **decision.model_dump(),
                "parameters": params,
                "operation_id": operation,
                "request_id": request_id,
                "context": context,
            }
        )

    def _error(self, context: AgentContext, request_id: str, code: str) -> AgentResult:
        request = self._request(
            context,
            request_id,
            AgentDecision(
                domain="assistant",
                action="clarify",
                transcript="Xizmat xatosi",
            ),
        )
        return result(request, "error", error_code=code, retryable=code == "provider_unavailable")

    async def _replay(self, context: AgentContext, request_id: str) -> AgentResult | None:
        cached = await self.store.get_receipt(context.user_id, request_id, self._now())
        if cached and cached.status in {"needs_input", "needs_confirmation"}:
            current = await self.store.get_session(context.user_id, self._now())
            if current is None or current.operation_id != cached.operation_id:
                return cached.model_copy(
                    update={
                        "status": "cancelled",
                        "data": {},
                        "question": None,
                        "missing_fields": [],
                    }
                )
            return await self._pending_result(context, request_id, current)
        return cached

    async def respond(
        self,
        *,
        context: AgentContext,
        request_id: str,
        text: str | None,
        audio: bytes | None = None,
        mime_type: str = "audio/ogg",
    ) -> AgentResult:
        if cached := await self._replay(context, request_id):
            return cached
        await self.store.cleanup(self._now())
        pending = await self.store.get_session(context.user_id, self._now())
        command = (text or "").strip().casefold()
        if command in {"bekor qil", "bekor qilish", "cancel"}:
            if pending:
                return await self.cancel(
                    context=context,
                    request_id=request_id,
                    operation_id=pending.operation_id,
                    revision=pending.revision,
                )
            return self._error(context, request_id, "no_active_task")
        if command in {"davom et", "resume"}:
            return await self.resume(context=context, request_id=request_id)
        if (
            pending
            and pending.domain == "reminder"
            and pending.action == "create"
            and not pending.missing_fields
            and command in {"ha", "yes", "да"}
        ):
            return await self._pending_result(context, request_id, pending)
        if audio is not None:
            current = monotonic()
            self._voice_until = {
                u: until for u, until in self._voice_until.items() if until > current
            }
            if self._voice_until.get(context.user_id, 0) > current:
                return self._error(context, request_id, "voice_cooldown")
            self._voice_until[context.user_id] = current + self._cooldown
        try:
            async with self._slots:
                decision = await self._extractor.extract(
                    text=text,
                    audio=audio,
                    mime_type=mime_type,
                    context=context,
                    pending=pending,
                )
        except (ExternalServiceError, ValueError):
            self._voice_until.pop(context.user_id, None)
            return self._error(context, request_id, "provider_unavailable")
        if decision.domain == "assistant" and decision.action == "resume":
            return await self.resume(context=context, request_id=request_id)
        if decision.domain == "assistant" and decision.action == "cancel" and pending:
            return await self.cancel(
                context=context,
                request_id=request_id,
                operation_id=pending.operation_id,
                revision=pending.revision,
            )
        if decision.multiple_tasks:
            request = self._request(
                context,
                request_id,
                AgentDecision(
                    domain="assistant",
                    action="clarify",
                    transcript=decision.transcript,
                ),
            )
            return result(
                request,
                "needs_input",
                missing_fields=["single_task"],
                question="Bitta vazifani tanlang va alohida ayting. Qaysisini avval bajaray?",
            )
        if pending and (decision.domain, decision.action) != (pending.domain, pending.action):
            if decision.domain == "assistant" and decision.action == "clarify":
                return await self._pending_result(context, request_id, pending)
            request = self._request(context, request_id, decision)
            return result(
                request,
                "needs_input",
                missing_fields=["active_task"],
                question="Tugallanmagan vazifa bor. «Davom et» yoki «Bekor qil» deb yozing.",
                data={"pending_operation": pending.operation_id},
            )
        try:
            request = self._request(context, request_id, decision, pending)
            prepared = await self._adapters.prepare(request)
        except ReligiousReminderCooldownError as exc:
            return result(request, "unsupported", data={"text": str(exc)})
        except ExternalServiceError:
            return self._error(context, request_id, "provider_unavailable")
        except ValueError:
            return self._error(context, request_id, "invalid_input")
        if prepared.status == "error":
            return prepared
        try:
            async with self.store.transaction(
                context.user_id, pending.revision if pending else None, now=self._now()
            ) as transaction:
                output = prepared
                if prepared.status in {"needs_input", "needs_confirmation"}:
                    state = AgentSessionState(
                        operation_id=request.operation_id,
                        origin_source_key=pending.origin_source_key
                        if pending
                        else f"agent:{request.operation_id}",
                        origin_time=pending.origin_time if pending else context.message_time,
                        domain=request.domain,
                        action=request.action,
                        parameters=request.parameters,
                        missing_fields=prepared.missing_fields,
                        question=prepared.question,
                        revision=transaction.revision + 1,
                        expires_at=self._now() + timedelta(hours=24),
                    )
                    await transaction.save_session(state)
                    output.data["revision"] = state.revision
                elif prepared.status == "done":
                    if not prepared.data:
                        output = await self._adapters.execute(request, transaction)
                    if pending:
                        await transaction.save_session(None)
                await transaction.save_receipt(output)
        except AgentRevisionConflict:
            return await self._replay(context, request_id) or self._error(
                context, request_id, "stale_operation"
            )
        logger.info(
            "agent_result request=%s operation=%s domain=%s action=%s status=%s",
            request_id,
            request.operation_id,
            request.domain,
            request.action,
            output.status,
        )
        return output

    async def _pending_result(
        self,
        context: AgentContext,
        request_id: str,
        pending: AgentSessionState,
    ) -> AgentResult:
        request = self._request(
            context,
            request_id,
            AgentDecision(
                domain=pending.domain,
                action=pending.action,
                parameters=pending.parameters,
                transcript="Davom etish",
                clarification=pending.question
                if "clarification" in pending.missing_fields
                else None,
            ),
            pending,
        )
        output = await self._adapters.prepare(request)
        output.data["revision"] = pending.revision
        return output

    async def resume(self, *, context: AgentContext, request_id: str) -> AgentResult:
        pending = await self.store.get_session(context.user_id, self._now())
        if pending is None:
            return self._error(context, request_id, "no_active_task")
        return await self._pending_result(context, request_id, pending)

    async def confirm(
        self,
        *,
        context: AgentContext,
        request_id: str,
        operation_id: str,
        revision: int,
    ) -> AgentResult:
        if cached := await self._replay(context, request_id):
            return cached
        pending = await self.store.get_session(context.user_id, self._now())
        if pending is None or pending.operation_id != operation_id or pending.revision != revision:
            return self._error(context, request_id, "stale_operation")
        if (pending.domain, pending.action) != ("reminder", "create"):
            return self._error(context, request_id, "stale_operation")
        fresh_context = context.model_copy(update={"message_time": self._now()})
        request = self._request(
            fresh_context,
            request_id,
            AgentDecision(
                domain=pending.domain,
                action=pending.action,
                parameters=pending.parameters,
                transcript="Tasdiqlangan eslatma",
            ),
            pending,
        )
        prepared = await self._adapters.prepare(request)
        if prepared.status != "needs_confirmation":
            prepared.data["revision"] = pending.revision
            return prepared
        try:
            async with self.store.transaction(
                context.user_id, revision, now=self._now()
            ) as transaction:
                output = await self._adapters.execute(request, transaction)
                await transaction.save_session(None)
                await transaction.save_receipt(output)
            return output
        except AgentRevisionConflict:
            return await self._replay(context, request_id) or self._error(
                context, request_id, "stale_operation"
            )

    async def cancel(
        self,
        *,
        context: AgentContext,
        request_id: str,
        operation_id: str,
        revision: int,
    ) -> AgentResult:
        pending = await self.store.get_session(context.user_id, self._now())
        if pending is None or pending.operation_id != operation_id or pending.revision != revision:
            return self._error(context, request_id, "stale_operation")
        request = self._request(
            context,
            request_id,
            AgentDecision(
                domain="assistant",
                action="cancel",
                transcript="Bekor qilish",
            ),
        )
        output = result(request, "cancelled", data={"text": "Vazifa bekor qilindi."})
        output.operation_id = pending.operation_id
        try:
            async with self.store.transaction(
                context.user_id, revision, now=self._now()
            ) as transaction:
                await transaction.save_session(None)
                await transaction.save_receipt(output)
        except AgentRevisionConflict:
            return self._error(context, request_id, "stale_operation")
        return output
