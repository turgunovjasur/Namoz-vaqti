"""Route one intent, preserve partial tasks and execute only validated effects."""

import asyncio
import logging
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import monotonic
from typing import Protocol, cast

from pydantic import JsonValue

from namoz_bot.application.agent_adapters import AgentAdapters, result
from namoz_bot.application.agent_sessions import AgentStore, AgentTransaction
from namoz_bot.application.view_context import page_parameters
from namoz_bot.domain.agent_protocol import (
    AgentContext,
    AgentDecision,
    AgentRequest,
    AgentResult,
    AgentRevisionConflict,
    AgentSessionState,
    AgentViewState,
    operation_id_for,
)
from namoz_bot.domain.errors import ExternalServiceError, ReligiousReminderCooldownError
from namoz_bot.domain.reminders import TASHKENT

logger = logging.getLogger(__name__)
CONFIRMED_ACTIONS = {("reminder", "create"), ("reminder", "delete"), ("accounting", "undo")}


class AgentExtractor(Protocol):
    async def extract(
        self,
        *,
        text: str | None,
        audio: bytes | None,
        mime_type: str,
        context: AgentContext,
        pending: AgentSessionState | None,
        request_id: str | None = None,
    ) -> AgentDecision: ...


class AgentActionExecutor(Protocol):
    async def prepare(self, request: AgentRequest) -> AgentResult: ...
    async def execute(
        self, request: AgentRequest, transaction: AgentTransaction
    ) -> AgentResult: ...


class MainAgent:
    def __init__(
        self,
        extractor: AgentExtractor,
        store: AgentStore,
        *,
        adapters: AgentActionExecutor | None = None,
        now: Callable[[], datetime] | None = None,
        cooldown_seconds: int = 20,
        voice_first: bool = False,
    ) -> None:
        self.store = store
        self.voice_first = voice_first
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
        operation = pending.operation_id if pending else operation_id_for(context, request_id)
        params = dict(pending.parameters) if pending else {}
        if decision.domain == "reminder" and "kind" in decision.parameters:
            if decision.parameters["kind"] != params.get("kind"):
                params.pop("date", None)
                params.pop("weekdays", None)
        if pending and (decision.domain, decision.action) in {
            ("reminder", "delete"),
            ("accounting", "undo"),
        }:
            supplied = decision.parameters
            if supplied.get("target_id") is not None:
                params.pop("text", None)
                params.pop("ordinal", None)
            elif supplied.get("text") is not None or supplied.get("ordinal") is not None:
                params.pop("target_id", None)
                if supplied.get("text") is not None:
                    params.pop("ordinal", None)
                else:
                    params.pop("text", None)
        params.update(decision.parameters)
        if "page" in decision.parameters and not decision.parameters.get("page_step"):
            params.pop("page_step", None)
        params = page_parameters(params, decision.domain, decision.action, context.last_view)
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
        if pending and pending.voice_review:
            from namoz_bot.application.voice_approval import VoiceApproval

            return VoiceApproval(self).pending_result(pending, request_id)
        if self.voice_first:
            context = context.model_copy(
                update={
                    "last_view": await self.store.get_last_view(context.user_id, self._now()),
                    "target_choices": pending.choices if pending else None,
                }
            )
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
            self.voice_first
            and pending
            and not pending.missing_fields
            and (pending.domain, pending.action) in CONFIRMED_ACTIONS
            and command
            in {
                "ha",
                "yes",
                "да",
                "saqla",
                "tasdiqlayman",
                "ha, saqla",
                "ha saqla",
            }
        ):
            if pending.missing_fields:
                return await self._pending_result(context, request_id, pending)
            return await self.confirm(
                context=context,
                request_id=request_id,
                operation_id=pending.operation_id,
                revision=pending.revision,
            )
        if (
            pending
            and pending.domain == "reminder"
            and pending.action == "create"
            and not pending.missing_fields
            and command in {"ha", "yes", "да"}
        ):
            return await self._pending_result(context, request_id, pending)
        if audio is not None and not self.voice_first:
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
                    request_id=request_id,
                )
        except (ExternalServiceError, ValueError):
            self._voice_until.pop(context.user_id, None)
            if (
                self.voice_first
                and pending
                and not pending.missing_fields
                and (pending.domain, pending.action) in CONFIRMED_ACTIONS
            ):
                # Preserve the draft, but require its summary again after a failed new input.
                try:
                    async with self.store.transaction(
                        context.user_id, pending.revision, now=self._now()
                    ) as transaction:
                        await transaction.save_session(
                            pending.model_copy(
                                update={
                                    "missing_fields": ["confirmation"],
                                    "question": "Oldingi qoralama saqlangan. "
                                    "«Davom et» deb uni tekshiring.",
                                    "revision": transaction.revision + 1,
                                }
                            )
                        )
                except AgentRevisionConflict:
                    pass
            return self._error(context, request_id, "provider_unavailable")
        return await self.apply_decision(
            context=context, request_id=request_id, decision=decision, pending=pending
        )

    async def apply_decision(
        self,
        *,
        context: AgentContext,
        request_id: str,
        decision: AgentDecision,
        pending: AgentSessionState | None,
        approval_revision: int | None = None,
        approve_effect: bool = False,
        source_key: str | None = None,
    ) -> AgentResult:
        """Apply an internally validated decision, including a stored voice approval."""
        if decision.domain == "assistant" and decision.action == "resume":
            return await self.resume(context=context, request_id=request_id)
        if self.voice_first and decision.domain == "assistant" and decision.action == "confirm":
            if pending is None:
                return self._error(context, request_id, "no_active_task")
            if pending.missing_fields:
                return await self._pending_result(context, request_id, pending)
            return await self.confirm(
                context=context,
                request_id=request_id,
                operation_id=pending.operation_id,
                revision=pending.revision,
            )
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
        resolution_read = bool(
            self.voice_first
            and pending
            and (
                (pending.domain, pending.action, decision.domain, decision.action)
                in {
                    ("reminder", "delete", "reminder", "list"),
                    ("accounting", "undo", "accounting", "history"),
                }
            )
        )
        if (
            pending
            and not resolution_read
            and (decision.domain, decision.action) != (pending.domain, pending.action)
        ):
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
            request = self._request(
                context, source_key or request_id, decision, None if resolution_read else pending
            )
            request.request_id = request_id
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
                context.user_id,
                approval_revision
                if approval_revision is not None
                else (pending.revision if pending else None),
                now=self._now(),
            ) as transaction:
                output = prepared
                if approve_effect and prepared.status == "needs_confirmation":
                    confirmed = request.model_copy(update={"parameters": prepared.data["draft"]})
                    output = await self._adapters.execute(confirmed, transaction)
                    await transaction.save_session(None)
                elif prepared.status in {"needs_input", "needs_confirmation"}:
                    state = AgentSessionState(
                        operation_id=request.operation_id,
                        origin_source_key=pending.origin_source_key
                        if pending
                        else f"agent:{request.operation_id}",
                        origin_time=pending.origin_time if pending else context.message_time,
                        domain=request.domain,
                        action=request.action,
                        parameters=cast(dict[str, JsonValue], prepared.data["draft"])
                        if prepared.status == "needs_confirmation"
                        else request.parameters,
                        missing_fields=prepared.missing_fields,
                        question=prepared.question,
                        choices=AgentViewState.model_validate(prepared.data["choices"])
                        if prepared.data.get("choices")
                        else None,
                        revision=transaction.revision + 1,
                        expires_at=self._now() + timedelta(hours=24),
                    )
                    await transaction.save_session(state)
                    output.data["revision"] = state.revision
                elif prepared.status == "done":
                    if not prepared.data:
                        output = await self._adapters.execute(request, transaction)
                    if not resolution_read and (pending or approval_revision is not None):
                        await transaction.save_session(None)
                    elif pending and resolution_read and (pending.choices or approval_revision):
                        await transaction.save_session(
                            pending.model_copy(
                                update={
                                    "choices": None,
                                    "revision": transaction.revision + 1,
                                }
                            )
                        )
                elif (
                    self.voice_first
                    and pending
                    and prepared.status == "unsupported"
                    and (pending.domain, pending.action)
                    in {("reminder", "delete"), ("accounting", "undo")}
                ):
                    # A rejected replacement must never leave the previous target confirmed.
                    await transaction.save_session(None)
                elif approval_revision is not None:
                    await transaction.save_session(
                        pending.model_copy(update={"revision": transaction.revision + 1})
                        if pending
                        else None
                    )
                await transaction.save_receipt(output)
        except AgentRevisionConflict:
            return await self._replay(context, request_id) or self._error(
                context, request_id, "stale_operation"
            )
        except ValueError:
            return self._error(context, request_id, "invalid_input")
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
        if pending.voice_review:
            from namoz_bot.application.voice_approval import VoiceApproval

            return VoiceApproval(self).pending_result(pending, request_id)
        if self.voice_first:
            context = context.model_copy(
                update={
                    "last_view": await self.store.get_last_view(context.user_id, self._now()),
                    "target_choices": pending.choices,
                }
            )
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
        if self.voice_first and output.status in {"needs_input", "needs_confirmation"}:
            params = (
                cast(dict[str, JsonValue], output.data["draft"])
                if output.status == "needs_confirmation"
                else pending.parameters
            )
            choices = (
                AgentViewState.model_validate(output.data["choices"])
                if output.data.get("choices")
                else None
            )
            if (params, output.missing_fields, output.question, choices) != (
                pending.parameters,
                pending.missing_fields,
                pending.question,
                pending.choices,
            ):
                try:
                    async with self.store.transaction(
                        context.user_id, pending.revision, now=self._now()
                    ) as transaction:
                        pending = pending.model_copy(
                            update={
                                "parameters": params,
                                "missing_fields": output.missing_fields,
                                "question": output.question,
                                "choices": choices,
                                "revision": transaction.revision + 1,
                            }
                        )
                        await transaction.save_session(pending)
                        output.data["revision"] = pending.revision
                        await transaction.save_receipt(output)
                except AgentRevisionConflict:
                    return self._error(context, request_id, "stale_operation")
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
        allowed = CONFIRMED_ACTIONS if self.voice_first else {("reminder", "create")}
        if (pending.domain, pending.action) not in allowed:
            return self._error(context, request_id, "stale_operation")
        if pending.missing_fields:
            return await self._pending_result(context, request_id, pending)
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
            if self.voice_first and prepared.status == "unsupported":
                try:
                    async with self.store.transaction(
                        context.user_id, revision, now=self._now()
                    ) as transaction:
                        await transaction.save_session(None)
                        await transaction.save_receipt(prepared)
                except AgentRevisionConflict:
                    return self._error(context, request_id, "stale_operation")
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
        except ValueError:
            return self._error(context, request_id, "invalid_input")

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
