"""Owner-scoped task transitions and atomic business receipts."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import cast

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.workforce.ports import TaskTransaction
from namoz_bot.domain.agent_protocol import AgentContext, AgentResult
from namoz_bot.domain.workforce.tasks import (
    ClaimedTask,
    ReviewVerdict,
    TaskConflict,
    TaskMessage,
    TaskPlan,
    TaskRevision,
    TaskStatus,
)
from namoz_bot.infrastructure.agent_sessions import _aware
from namoz_bot.infrastructure.orm import (
    AgentSessionRecord,
    WorkforceOutboxRecord,
    WorkforceRevisionRecord,
    WorkforceTaskRecord,
    WorkforceUpdateRecord,
)
from namoz_bot.infrastructure.workforce.profiles import SqlPermissionTransaction, lock_owner


def revision_value(row: WorkforceRevisionRecord) -> TaskRevision:
    return TaskRevision(
        plan=TaskPlan.model_validate_json(json.dumps(row.plan)),
        status=cast(TaskStatus, row.status),
        service_result=AgentResult.model_validate_json(json.dumps(row.service_result))
        if row.service_result
        else None,
        review=ReviewVerdict.model_validate(row.review) if row.review else None,
        feedback=row.feedback,
        review_attempts=row.review_attempts,
    )


def lease_valid(task: WorkforceTaskRecord, revision: int, token: str, now: datetime) -> None:
    if (
        task.revision != revision
        or task.lease_token != token
        or task.lease_until is None
        or _aware(task.lease_until) <= now
        or task.status not in {"running", "reviewing"}
    ):
        raise TaskConflict("Worker lease lost")


async def put_outbox(
    session: AsyncSession,
    task: WorkforceTaskRecord,
    kind: str,
    message: TaskMessage,
    now: datetime,
    *,
    held: bool = False,
) -> None:
    insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
    await session.execute(
        insert(WorkforceOutboxRecord)
        .values(
            task_id=task.id,
            revision=task.revision,
            kind=kind,
            chat_id=task.chat_id,
            payload=message.model_dump(mode="json"),
            status="held" if held else "pending",
            attempts=0,
            next_attempt=now,
        )
        .on_conflict_do_nothing(index_elements=["task_id", "revision", "kind"])
    )


class SqlTaskTransaction(SqlPermissionTransaction):
    def bind_task(
        self,
        task: WorkforceTaskRecord,
        revision: WorkforceRevisionRecord,
        token: str,
        clock: Callable[[], datetime],
    ) -> None:
        self.task, self.task_revision, self.token, self.clock = task, revision, token, clock

    async def save_result(self, result: AgentResult) -> None:
        lease_valid(self.task, self.task_revision.revision, self.token, self.clock())
        if self.task_revision.service_result is not None:
            raise TaskConflict("Result already committed")
        await self.save_receipt(result)
        self.task_revision.service_result = result.model_dump(mode="json")
        self.task_revision.status = self.task.status = "reviewing"
        await put_outbox(
            self._session,
            self.task,
            "result",
            TaskMessage(
                text="Natija tayyorlanmoqda.", task_id=self.task.id, revision=self.task.revision
            ),
            self.clock(),
            held=True,
        )
        await self._session.flush()


class SqlAlchemyTaskStore:
    def __init__(
        self,
        factory: async_sessionmaker[AsyncSession],
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.factory, self.clock = factory, clock

    async def _owned(
        self, session: AsyncSession, task_id: str, context: AgentContext, *, lock: bool = False
    ) -> WorkforceTaskRecord:
        query = select(WorkforceTaskRecord).where(
            WorkforceTaskRecord.id == task_id,
            WorkforceTaskRecord.user_id == context.user_id,
            WorkforceTaskRecord.bot_id == context.bot_id,
            WorkforceTaskRecord.chat_id == context.chat_id,
        )
        row = await session.scalar(query.with_for_update() if lock else query)
        if row is None:
            raise TaskConflict("Foreign or missing task")
        return row

    async def get_owned(self, task_id: str, context: AgentContext) -> TaskRevision:
        async with self.factory() as session:
            task = await self._owned(session, task_id, context)
            row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
            assert row is not None
            return revision_value(row)

    async def save_plan(self, plan: TaskPlan, *, expected_revision: int | None) -> TaskRevision:
        async with self.factory.begin() as session:
            await lock_owner(session, plan.context.user_id)
            task = await session.scalar(
                select(WorkforceTaskRecord).where(
                    WorkforceTaskRecord.user_id == plan.context.user_id,
                    WorkforceTaskRecord.bot_id == plan.context.bot_id,
                    WorkforceTaskRecord.request_id == plan.request_id,
                )
            )
            if task is not None:
                row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
                assert row is not None
                return revision_value(row)
            status = "needs_input" if plan.question else "awaiting_approval"
            if expected_revision is None:
                if plan.revision != 1:
                    raise TaskConflict("New task revision must be 1")
                task = WorkforceTaskRecord(
                    id=plan.task_id,
                    user_id=plan.context.user_id,
                    bot_id=plan.context.bot_id,
                    chat_id=plan.context.chat_id,
                    request_id=plan.request_id,
                    revision=plan.revision,
                    status=status,
                    attempts=0,
                    created_at=self.clock(),
                )
                session.add(task)
                await session.flush()
            else:
                task = await self._owned(session, plan.task_id, plan.context, lock=True)
                if (
                    task.revision != expected_revision
                    or plan.revision != expected_revision + 1
                    or task.status not in {"needs_input", "awaiting_correction"}
                ):
                    raise TaskConflict("Task revision changed")
                task.revision, task.status = plan.revision, status
                task.lease_token = task.lease_until = None
                task.attempts = 0
            row = WorkforceRevisionRecord(
                task_id=plan.task_id,
                revision=plan.revision,
                status=status,
                plan=plan.model_dump(mode="json"),
                review_attempts=0,
            )
            session.add(row)
            await session.flush()
            return revision_value(row)

    async def approve(
        self, task_id: str, revision: int, context: AgentContext, request_id: str, accept: bool
    ) -> TaskRevision:
        async with self.factory.begin() as session:
            await lock_owner(session, context.user_id)
            task = await self._owned(session, task_id, context, lock=True)
            row = await session.get(WorkforceRevisionRecord, (task_id, revision))
            if row is None or task.revision != revision:
                raise TaskConflict("Old approval")
            previous = await session.get(
                WorkforceUpdateRecord, (context.user_id, context.bot_id, request_id)
            )
            if previous and (previous.task_id, previous.revision, previous.action) != (
                task_id,
                revision,
                "yes" if accept else "no",
            ):
                raise TaskConflict("Update already processed")
            if task.status != "awaiting_approval":
                if task.status in {
                    "queued",
                    "running",
                    "reviewing",
                    "awaiting_feedback",
                    "done",
                    "cancelled",
                }:
                    return revision_value(row)
                raise TaskConflict("Task is not awaiting approval")
            if TaskPlan.model_validate_json(json.dumps(row.plan)).expires_at <= self.clock():
                raise TaskConflict("Approval expired")
            if previous is None:
                session.add(
                    WorkforceUpdateRecord(
                        user_id=context.user_id,
                        bot_id=context.bot_id,
                        request_id=request_id,
                        task_id=task_id,
                        revision=revision,
                        action="yes" if accept else "no",
                    )
                )
            row.status = task.status = "queued" if accept else "cancelled"
            if accept:
                await put_outbox(
                    session,
                    task,
                    "accepted",
                    TaskMessage(
                        text="✅ Buyruq qabul qilindi. Ishni boshladim; tugagach xabar beraman."
                    ),
                    self.clock(),
                )
            await session.flush()
            return revision_value(row)

    @asynccontextmanager
    async def effect_scope(
        self, task_id: str, revision: int, lease_token: str
    ) -> AsyncIterator[TaskTransaction]:
        async with self.factory.begin() as session:
            task = await session.get(WorkforceTaskRecord, task_id)
            if task is None:
                raise TaskConflict("Missing task")
            await lock_owner(session, task.user_id)
            task = await session.scalar(
                select(WorkforceTaskRecord)
                .where(WorkforceTaskRecord.id == task_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            assert task is not None
            lease_valid(task, revision, lease_token, self.clock())
            row = await session.get(WorkforceRevisionRecord, (task_id, revision))
            assert row is not None
            insert = pg_insert if session.get_bind().dialect.name == "postgresql" else sqlite_insert
            await session.execute(
                insert(AgentSessionRecord)
                .values(user_id=task.user_id, revision=0)
                .on_conflict_do_nothing(index_elements=["user_id"])
            )
            agent = await session.get(AgentSessionRecord, task.user_id)
            assert agent is not None
            tx = SqlTaskTransaction(self.factory, session, agent, self.clock())
            tx.bind_task(task, row, lease_token, self.clock)
            yield tx
            lease_valid(task, revision, lease_token, self.clock())

    async def complete(
        self, claim: ClaimedTask, verdict: ReviewVerdict, message: TaskMessage
    ) -> None:
        plan = claim.task.plan
        async with self.factory.begin() as session:
            await lock_owner(session, plan.context.user_id)
            task = await self._owned(session, plan.task_id, plan.context, lock=True)
            lease_valid(task, plan.revision, claim.lease_token, self.clock())
            row = await session.get(WorkforceRevisionRecord, (plan.task_id, plan.revision))
            if row is None or row.service_result is None:
                raise TaskConflict("Missing saved result")
            row.review = verdict.model_dump(mode="json")
            result = AgentResult.model_validate_json(json.dumps(row.service_result))
            row.status = task.status = (
                "awaiting_feedback"
                if result.status == "done"
                else "needs_input"
                if result.status == "needs_input"
                else "failed"
            )
            outbox = await session.scalar(
                select(WorkforceOutboxRecord).where(
                    WorkforceOutboxRecord.task_id == task.id,
                    WorkforceOutboxRecord.revision == task.revision,
                    WorkforceOutboxRecord.kind == "result",
                )
            )
            assert outbox is not None
            outbox.payload, outbox.status = message.model_dump(mode="json"), "pending"
            task.lease_token = task.lease_until = None
