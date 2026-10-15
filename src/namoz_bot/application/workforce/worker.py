"""Bounded workers renew leases while provider calls run outside SQL locks."""

import asyncio
from contextlib import suppress
from datetime import UTC, datetime

from namoz_bot.application.workforce.ports import TaskQueue, TaskRunner
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.domain.workforce.tasks import ClaimedTask, TaskConflict


class Worker:
    def __init__(self, queue: TaskQueue, runner: TaskRunner):
        self.queue, self.runner = queue, runner
        self._active: set[asyncio.Task[None]] = set()

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

    async def run_once(self, now: datetime) -> None:
        claims = await self.queue.claim(now=now, limit=3, lease_seconds=180)
        jobs = [asyncio.create_task(self._run(claim)) for claim in claims]
        self._active.update(jobs)
        try:
            await asyncio.gather(*jobs)
        finally:
            self._active.difference_update(jobs)

    async def close(self) -> None:
        jobs = list(self._active)
        for job in jobs:
            job.cancel()
        await asyncio.gather(*jobs, return_exceptions=True)
