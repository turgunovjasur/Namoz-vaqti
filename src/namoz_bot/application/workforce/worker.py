"""Bounded workers renew leases while provider calls run outside SQL locks."""

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from namoz_bot.application.workforce.ports import TaskQueue, TaskRunner
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.tasks import ClaimedTask, TaskConflict

logger = logging.getLogger(__name__)


class Worker:
    def __init__(self, queue: TaskQueue, runner: TaskRunner, *, max_concurrency: int = 3):
        if not 1 <= max_concurrency <= 32:
            raise ValueError("Worker concurrency must be between 1 and 32")
        self.queue, self.runner = queue, runner
        self.max_concurrency = max_concurrency
        self._active: set[asyncio.Task[None]] = set()
        self._dispatch_lock = asyncio.Lock()
        self._closed = False

    async def _heartbeat(self, claim: ClaimedTask, worker: asyncio.Task[object]) -> None:
        while True:
            await asyncio.sleep(30)
            if not await self.queue.heartbeat(
                claim.task.plan.task_id, claim.lease_token, datetime.now(UTC)
            ):
                worker.cancel()
                return

    async def _run(self, claim: ClaimedTask) -> None:
        current = asyncio.current_task()
        assert current is not None
        heartbeat = asyncio.create_task(self._heartbeat(claim, current))
        try:
            await self.runner.run(claim)
        except (AccessDenied, ValueError):
            await self.queue.fail(claim, permanent=True, now=datetime.now(UTC))
        except TaskConflict:
            pass
        except Exception:
            await self.queue.fail(claim, permanent=False, now=datetime.now(UTC))
        finally:
            heartbeat.cancel()
            with suppress(asyncio.CancelledError):
                await heartbeat

    def _finished(self, job: asyncio.Task[None]) -> None:
        self._active.discard(job)
        if not job.cancelled() and job.exception() is not None:
            logger.error("workforce_job_failed", exc_info=job.exception())

    async def _start(self, now: datetime) -> list[asyncio.Task[None]]:
        async with self._dispatch_lock:
            self._active = {job for job in self._active if not job.done()}
            capacity = self.max_concurrency - len(self._active)
            if self._closed or capacity <= 0:
                return []
            claims = await self.queue.claim(now=now, limit=capacity, lease_seconds=180)
            jobs = [asyncio.create_task(self._run(claim)) for claim in claims]
            self._active.update(jobs)
            for job in jobs:
                job.add_done_callback(self._finished)
            return jobs

    async def dispatch(self, now: datetime) -> None:
        """Fill free slots and return immediately, including while other jobs run."""
        await self._start(now)

    async def run_once(self, now: datetime) -> None:
        """Drain this batch for command-line callers and deterministic tests."""
        await asyncio.gather(*(await self._start(now)))

    async def close(self) -> None:
        async with self._dispatch_lock:
            self._closed = True
            jobs = list(self._active)
            for job in jobs:
                job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
