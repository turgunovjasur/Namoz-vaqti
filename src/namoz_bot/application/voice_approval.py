"""Durable approvals of exact voice interpretations before any business work."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from namoz_bot.application.agent_adapters import result
from namoz_bot.domain.agent_protocol import (
    AgentContext,
    AgentDecision,
    AgentDraftState,
    AgentResult,
    AgentRevisionConflict,
    AgentSessionState,
    AgentVoiceReview,
    operation_id_for,
)
from namoz_bot.domain.errors import ExternalServiceError

if TYPE_CHECKING:
    from namoz_bot.application.main_agent import MainAgent


class VoiceApproval:
    def __init__(self, main: MainAgent) -> None:
        self.main = main

    def prior(self, state: AgentSessionState | None) -> AgentSessionState | None:
        original = state.voice_review.prior if state and state.voice_review else state
        if original is None or original.expires_at <= self.main._now():
            return None
        return AgentSessionState.model_validate(original.model_dump())

    def pending_result(self, state: AgentSessionState, request_id: str) -> AgentResult:
        review = state.voice_review
        assert review is not None
        request = self.main._request(review.context, request_id, review.decision)
        request.operation_id = state.operation_id
        understood = review.decision
        if (
            understood.domain == "assistant"
            and understood.action in {"confirm", "resume"}
            and review.prior
        ):
            understood = AgentDecision(
                domain=review.prior.domain,
                action=review.prior.action,
                parameters=review.prior.parameters,
                transcript=understood.transcript,
                clarification=review.prior.question
                if any(field != "confirmation" for field in review.prior.missing_fields)
                else None,
            )
        return result(
            request,
            "needs_confirmation",
            data={
                "voice_review": True,
                "draft": understood.model_dump(mode="json"),
                "revision": state.revision,
            },
        )

    async def preview(
        self,
        *,
        context: AgentContext,
        request_id: str,
        audio: bytes,
        mime_type: str,
    ) -> AgentResult:
        if cached := await self.main._replay(context, request_id):
            return cached
        await self.main.store.cleanup(self.main._now())
        current = await self.main.store.get_session(context.user_id, self.main._now())
        prior = self.prior(current)
        context = context.model_copy(
            update={
                "last_view": await self.main.store.get_last_view(context.user_id, self.main._now()),
                "target_choices": prior.choices if prior else None,
            }
        )
        try:
            async with self.main._slots:
                decision = await self.main._extractor.extract(
                    text=None,
                    audio=audio,
                    mime_type=mime_type,
                    context=context,
                    pending=prior,
                    request_id=request_id,
                )
            merged = self.main._request(
                context,
                request_id,
                decision,
                prior
                if prior and (prior.domain, prior.action) == (decision.domain, decision.action)
                else None,
            )
            decision = decision.model_copy(update={"parameters": merged.parameters})
        except (ExternalServiceError, ValueError):
            if prior and not prior.missing_fields:
                prior = prior.model_copy(
                    update={
                        "missing_fields": ["confirmation"],
                        "question": "Oldingi qoralama saqlangan. «Davom et» deb uni tekshiring.",
                    }
                )
            output = self.main._error(context, request_id, "provider_unavailable")
            return await self._finish(current, prior, output, context=context)
        review = AgentVoiceReview(
            decision=decision,
            context=context,
            source_key=request_id,
            prior=AgentDraftState.model_validate(prior.model_dump(exclude={"voice_review"}))
            if prior
            else None,
            expires_at=self.main._now() + timedelta(minutes=15),
        )
        try:
            async with self.main.store.transaction(
                context.user_id,
                current.revision if current else None,
                now=self.main._now(),
            ) as transaction:
                state = AgentSessionState(
                    domain="assistant",
                    action="clarify",
                    parameters={},
                    operation_id=operation_id_for(context, request_id),
                    origin_source_key=f"voice:{operation_id_for(context, request_id)}",
                    origin_time=context.message_time,
                    missing_fields=["voice_approval"],
                    revision=transaction.revision + 1,
                    expires_at=max(review.expires_at, prior.expires_at)
                    if prior
                    else review.expires_at,
                    voice_review=review,
                )
                output = self.pending_result(state, request_id)
                await transaction.save_session(state)
                await transaction.save_receipt(output)
            return output
        except AgentRevisionConflict:
            return self.main._error(context, request_id, "stale_operation")

    async def _finish(
        self,
        current: AgentSessionState | None,
        prior: AgentSessionState | None,
        output: AgentResult,
        *,
        context: AgentContext,
    ) -> AgentResult:
        try:
            async with self.main.store.transaction(
                context.user_id,
                current.revision if current else None,
                now=self.main._now(),
            ) as transaction:
                await transaction.save_session(
                    prior.model_copy(
                        update={
                            "revision": transaction.revision + 1,
                        }
                    )
                    if prior
                    else None
                )
                if prior and output.status in {"needs_input", "needs_confirmation"}:
                    output.data["revision"] = transaction.revision + 1
                await transaction.save_receipt(output)
            return output
        except AgentRevisionConflict:
            return self.main._error(context, output.request_id, "stale_operation")

    async def decide(
        self,
        *,
        context: AgentContext,
        request_id: str,
        operation_id: str,
        revision: int,
        accept: bool,
    ) -> AgentResult:
        if cached := await self.main._replay(context, request_id):
            return cached
        current = await self.main.store.get_session(context.user_id, self.main._now())
        review = current.voice_review if current else None
        if (
            not current
            or not review
            or current.operation_id != operation_id
            or current.revision != revision
            or review.context.bot_id != context.bot_id
            or review.context.user_id != context.user_id
            or review.context.telegram_user_id != context.telegram_user_id
        ):
            return self.main._error(context, request_id, "stale_operation")
        prior = self.prior(current)
        if review.expires_at <= self.main._now():
            return await self._finish(
                current,
                prior,
                self.main._error(context, request_id, "stale_operation"),
                context=context,
            )
        if not accept:
            request = self.main._request(
                context,
                request_id,
                AgentDecision(
                    domain="assistant",
                    action="cancel",
                    transcript="Ovozli buyruq rad etildi",
                ),
            )
            return await self._finish(
                current,
                prior,
                result(
                    request,
                    "cancelled",
                    data={"text": "Ovozli buyruq bekor qilindi."},
                ),
                context=context,
            )
        decision = review.decision
        if decision.domain == "assistant":
            if decision.action in {"confirm", "resume"} and prior:
                decision = AgentDecision(
                    domain=prior.domain,
                    action=prior.action,
                    parameters=prior.parameters,
                    transcript=decision.transcript,
                )
                if any(field != "confirmation" for field in prior.missing_fields):
                    request = self.main._request(context, request_id, decision, prior)
                    output = result(
                        request,
                        "needs_input",
                        missing_fields=prior.missing_fields,
                        question=prior.question or "Buyruqdagi ma’lumotlarni aniqlashtiring.",
                    )
                    return await self._finish(current, prior, output, context=context)
            else:
                if decision.action in {"confirm", "resume"}:
                    return await self._finish(
                        current,
                        None,
                        self.main._error(context, request_id, "no_active_task"),
                        context=context,
                    )
                request = self.main._request(context, request_id, decision)
                output = await self.main._adapters.prepare(request)
                if decision.action == "cancel":
                    prior = None
                    output = result(request, "cancelled", data={"text": "Vazifa bekor qilindi."})
                return await self._finish(current, prior, output, context=context)
        source_context = review.context.model_copy(
            update={
                "region_code": context.region_code,
                "offsets": context.offsets,
            }
        )
        output = await self.main.apply_decision(
            context=source_context,
            request_id=request_id,
            decision=decision,
            pending=prior,
            approval_revision=current.revision,
            source_key=review.source_key,
            approve_effect=review.decision.action != "resume",
        )
        remaining = await self.main.store.get_session(context.user_id, self.main._now())
        if (
            remaining
            and remaining.operation_id == operation_id
            and remaining.revision == revision
            and output.status != "error"
        ):
            return await self._finish(current, prior, output, context=context)
        return output
