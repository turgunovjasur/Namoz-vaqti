"""Durable workforce boundaries independent of SQL and Telegram."""

from contextlib import AbstractAsyncContextManager
from datetime import datetime
from typing import Protocol

from namoz_bot.application.profiles.ports import PermissionTransaction
from namoz_bot.domain.agent_protocol import AgentContext, AgentResult
from namoz_bot.domain.workforce.capabilities import CapabilitySelection, CapabilitySpec
from namoz_bot.domain.workforce.roles import RoleDefinition
from namoz_bot.domain.workforce.tasks import (
    ClaimedTask,
    ReviewVerdict,
    TaskMessage,
    TaskPlan,
    TaskRevision,
)


class TaskTransaction(PermissionTransaction, Protocol):
    async def save_result(self, result: AgentResult, *, replace_read: bool = False) -> None: ...


class TaskStore(Protocol):
    async def pending(self, context: AgentContext) -> TaskRevision | None: ...
    async def find_input(self, context: AgentContext, request_id: str) -> TaskRevision | None: ...
    async def invalidate(self, context: AgentContext, *, questions: bool = False) -> None: ...
    async def begin_review_retry(self, claim: ClaimedTask) -> bool: ...

    async def save_plan(self, plan: TaskPlan, *, expected_revision: int | None) -> TaskRevision: ...
    async def get_owned(self, task_id: str, context: AgentContext) -> TaskRevision: ...
    async def approve(
        self, task_id: str, revision: int, context: AgentContext, request_id: str, accept: bool
    ) -> TaskRevision: ...
    def effect_scope(
        self, task_id: str, revision: int, lease_token: str
    ) -> AbstractAsyncContextManager[TaskTransaction]: ...
    async def complete(
        self, claim: ClaimedTask, verdict: ReviewVerdict, message: TaskMessage
    ) -> None: ...


class TaskQueue(Protocol):
    async def claim(
        self, *, now: datetime, limit: int, lease_seconds: int
    ) -> list[ClaimedTask]: ...
    async def heartbeat(self, task_id: str, token: str, now: datetime) -> bool: ...
    async def fail(self, claim: ClaimedTask, *, permanent: bool, now: datetime) -> None: ...


class TaskRunner(Protocol):
    async def run(self, claim: ClaimedTask) -> object: ...


class TaskSender(Protocol):
    async def deliver_task(self, chat_id: int, message: TaskMessage) -> None: ...


class Transcriber(Protocol):
    async def transcribe(self, audio: bytes, mime_type: str, *, model: str) -> str: ...


class RoleInterpreter(Protocol):
    async def route(
        self,
        *,
        text: str,
        context: AgentContext,
        roles: tuple[RoleDefinition, ...],
        pending: TaskRevision | None,
        model: str,
    ) -> str: ...
    async def interpret(
        self,
        *,
        text: str,
        context: AgentContext,
        role: RoleDefinition,
        capabilities: tuple[CapabilitySpec, ...],
        pending: TaskRevision | None,
        model: str,
    ) -> CapabilitySelection: ...


class ResultReviewer(Protocol):
    async def review(self, plan: TaskPlan, result: AgentResult) -> ReviewVerdict: ...
