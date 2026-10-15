"""Run a specialist, inspect its evidence and publish a canonical result."""

from namoz_bot.application.workforce.execution import TaskExecutionService
from namoz_bot.application.workforce.ports import TaskStore
from namoz_bot.application.workforce.review import ReviewService
from namoz_bot.domain.workforce.tasks import ClaimedTask, ReviewVerdict, TaskMessage


class ManagedExecution:
    def __init__(self, tasks: TaskStore, execution: TaskExecutionService, review: ReviewService):
        self.tasks, self.execution, self.review = tasks, execution, review

    async def run(self, claim: ClaimedTask) -> object:
        task = await self.execution.run(claim)
        assert task.service_result is not None
        result = task.service_result
        complete = False
        verdict = ReviewVerdict(decision="clarify", issues=["Tekshiruv yakunlanmadi."])
        try:
            verdict = await self.review.inspect(task.plan, result)
            if verdict.decision == "revise" and await self.tasks.begin_review_retry(claim):
                capability = self.execution.capabilities.get(task.plan.selection.capability_id)
                if capability.spec.effect == "read":
                    task = await self.execution.reread(claim)
                    assert task.service_result is not None
                    result = task.service_result
                # Writes get one render/review retry, never another execution.
                verdict = await self.review.inspect(task.plan, result)
            complete = verdict.decision == "accept"
        except Exception:
            # The saved service result remains authoritative after provider/reviewer failure.
            pass
        await self.tasks.complete(
            claim,
            verdict,
            TaskMessage(
                text=self.review.render(result, complete=complete),
                task_id=task.plan.task_id,
                revision=task.plan.revision,
                buttons="feedback" if result.status == "done" else None,
            ),
        )

        return await self.tasks.get_owned(task.plan.task_id, task.plan.context)
