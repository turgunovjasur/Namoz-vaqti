"""Owner-scoped task transitions and atomic business receipts."""

import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from typing import cast

from sqlalchemy import select, update
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
    AgentReceiptRecord,
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

    async def save_result(self, result: AgentResult, *, replace_read: bool = False) -> None:
        lease_valid(self.task, self.task_revision.revision, self.token, self.clock())
        previous = self.task_revision.service_result
        if previous is not None:
            if (
                not replace_read
                or previous.get("effect") == "committed"
                or result.effect != "none"
                or self.task_revision.review_attempts != 1
            ):
                raise TaskConflict("Result already committed")
            await self._session.execute(
                update(AgentReceiptRecord)
                .where(
                    AgentReceiptRecord.user_id == self.task.user_id,
                    AgentReceiptRecord.request_id == result.request_id,
                )
                .values(result=result.model_dump(mode="json"))
            )
        else:
            if replace_read:
                raise TaskConflict("Missing original read result")
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
            previous = await session.get(
                WorkforceUpdateRecord, (plan.context.user_id, plan.context.bot_id, plan.request_id)
            )
            if previous is not None:
                if previous.action != "input":
                    raise TaskConflict("Update already used")
                old = await session.get(
                    WorkforceRevisionRecord, (previous.task_id, previous.revision)
                )
                if old is None:
                    raise TaskConflict("Missing input revision")
                return revision_value(old)
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
            session.add(
                WorkforceUpdateRecord(
                    user_id=plan.context.user_id,
                    bot_id=plan.context.bot_id,
                    request_id=plan.request_id,
                    task_id=plan.task_id,
                    revision=plan.revision,
                    action="input",
                )
            )
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

    async def pending(self, context: AgentContext) -> TaskRevision | None:
        async with self.factory() as session:
            task = await session.scalar(
                select(WorkforceTaskRecord)
                .where(
                    WorkforceTaskRecord.user_id == context.user_id,
                    WorkforceTaskRecord.bot_id == context.bot_id,
                    WorkforceTaskRecord.chat_id == context.chat_id,
                    WorkforceTaskRecord.status.in_(
                        ["needs_input", "awaiting_approval", "awaiting_correction"]
                    ),
                )
                .order_by(
                    WorkforceTaskRecord.created_at.desc(), WorkforceTaskRecord.revision.desc()
                )
                .limit(1)
            )
            if task is None:
                return None
            row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
            assert row is not None
            return revision_value(row)

    async def displayed_view(self, context: AgentContext) -> TaskRevision | None:
        async with self.factory() as session:
            row = await session.scalar(
                select(WorkforceRevisionRecord)
                .join(
                    WorkforceTaskRecord, WorkforceTaskRecord.id == WorkforceRevisionRecord.task_id
                )
                .join(
                    WorkforceOutboxRecord,
                    (WorkforceOutboxRecord.task_id == WorkforceRevisionRecord.task_id)
                    & (WorkforceOutboxRecord.revision == WorkforceRevisionRecord.revision),
                )
                .where(
                    WorkforceTaskRecord.user_id == context.user_id,
                    WorkforceTaskRecord.bot_id == context.bot_id,
                    WorkforceTaskRecord.chat_id == context.chat_id,
                    WorkforceOutboxRecord.kind == "result",
                    WorkforceOutboxRecord.status == "sent",
                    WorkforceOutboxRecord.next_attempt > self.clock() - timedelta(minutes=30),
                    WorkforceRevisionRecord.service_result["status"].as_string() == "done",
                    WorkforceRevisionRecord.service_result["action"]
                    .as_string()
                    .in_(["list", "history"]),
                )
                .order_by(WorkforceOutboxRecord.id.desc())
                .limit(1)
            )
            return revision_value(row) if row else None

    async def find_input(self, context: AgentContext, request_id: str) -> TaskRevision | None:
        async with self.factory() as session:
            update_record = await session.get(
                WorkforceUpdateRecord, (context.user_id, context.bot_id, request_id)
            )
            if update_record and update_record.action == "input":
                await self._owned(session, update_record.task_id, context)
                row = await session.get(
                    WorkforceRevisionRecord, (update_record.task_id, update_record.revision)
                )
                return revision_value(row) if row else None
            task = await session.scalar(
                select(WorkforceTaskRecord).where(
                    WorkforceTaskRecord.user_id == context.user_id,
                    WorkforceTaskRecord.bot_id == context.bot_id,
                    WorkforceTaskRecord.chat_id == context.chat_id,
                    WorkforceTaskRecord.request_id == request_id,
                )
            )
            if task is None:
                return None
            row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
            return revision_value(row) if row else None

    async def invalidate(self, context: AgentContext, *, questions: bool = False) -> None:
        async with self.factory.begin() as session:
            await lock_owner(session, context.user_id)
            tasks = list(
                await session.scalars(
                    select(WorkforceTaskRecord)
                    .where(
                        WorkforceTaskRecord.user_id == context.user_id,
                        WorkforceTaskRecord.bot_id == context.bot_id,
                        WorkforceTaskRecord.chat_id == context.chat_id,
                        WorkforceTaskRecord.status.in_(
                            ["awaiting_approval", "needs_input", "awaiting_correction"]
                            if questions
                            else ["awaiting_approval"]
                        ),
                    )
                    .with_for_update()
                )
            )
            for task in tasks:
                row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
                assert row is not None
                row.status = task.status = "cancelled"

    async def begin_review_retry(self, claim: ClaimedTask) -> bool:
        plan = claim.task.plan
        async with self.factory.begin() as session:
            await lock_owner(session, plan.context.user_id)
            task = await self._owned(session, plan.task_id, plan.context, lock=True)
            lease_valid(task, plan.revision, claim.lease_token, self.clock())
            row = await session.get(WorkforceRevisionRecord, (task.id, task.revision))
            assert row is not None
            if row.review_attempts >= 1:
                return False
            row.review_attempts += 1
            return True

    async def rate(
        self, context: AgentContext, task_id: str, revision: int, accepted: bool, request_id: str
    ) -> None:
        async with self.factory.begin() as session:
            await lock_owner(session, context.user_id)
            task = await self._owned(session, task_id, context, lock=True)
            if task.revision != revision:
                raise TaskConflict("Old feedback revision")
            previous = await session.get(
                WorkforceUpdateRecord, (context.user_id, context.bot_id, request_id)
            )
            action = "feedback_yes" if accepted else "feedback_no"
            if previous:
                if (previous.task_id, previous.revision, previous.action) != (
                    task_id,
                    revision,
                    action,
                ):
                    raise TaskConflict("Update used")
                return
            if task.status != "awaiting_feedback":
                raise TaskConflict("Feedback already processed")
            row = await session.get(WorkforceRevisionRecord, (task_id, revision))
            assert row is not None
            row.status = task.status = "done" if accepted else "awaiting_correction"
            row.feedback = "accepted" if accepted else "correction_requested"
            session.add(
                WorkforceUpdateRecord(
                    user_id=context.user_id,
                    bot_id=context.bot_id,
                    request_id=request_id,
                    task_id=task_id,
                    revision=revision,
                    action=action,
                )
            )

    async def abandon_correction(self, context: AgentContext, task_id: str, revision: int) -> None:
        async with self.factory.begin() as session:
            await lock_owner(session, context.user_id)
            task = await self._owned(session, task_id, context, lock=True)
            if task.revision == revision and task.status in {"awaiting_correction", "needs_input"}:
                row = await session.get(WorkforceRevisionRecord, (task_id, revision))
                assert row is not None
                row.status = task.status = "done"
                row.feedback = "correction_abandoned_for_new_request"
