import asyncio
from uuid import uuid4

from namoz_bot.application.capabilities.registry import build_capability_registry
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.application.skills.native import NativeSkill
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.application.workforce.execution import TaskExecutionService
from namoz_bot.application.workforce.manager import ManagedExecution
from namoz_bot.application.workforce.review import ReviewService
from namoz_bot.application.workforce.worker import Worker
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from namoz_bot.domain.workforce.tasks import ReviewVerdict
from namoz_bot.infrastructure.orm import AgentRoleSkillRecord
from namoz_bot.infrastructure.workforce.outbox import SqlAlchemyTaskOutbox
from namoz_bot.presentation.result_messages import render_result
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant
from tests.integration.test_workforce_tasks import workforce as workforce
from tests.unit.skills.test_native_skills import Input, Output


async def test_same_user_new_task_finishes_and_delivers_while_generation_is_running(workforce):
    tasks, queue, _, original, factory, profiles, _ = workforce
    started, release, quick_done = asyncio.Event(), asyncio.Event(), asyncio.Event()

    async def prepare(call, parameters):
        if parameters.word == "slow":
            started.set()
            await release.wait()
        return Output(answer=parameters.word.upper())

    skill = NativeSkill(
        id="demo.generate",
        name="Generate",
        description="Generate text",
        input_model=Input,
        output_model=Output,
        prepare=prepare,
        render=lambda value: value.answer,
        effect="generate",
    )
    caps = build_capability_registry(extra_skills=(skill,))
    role = original.role.model_copy(update={"capability_ids": ("demo.generate",)})
    profiles.roles = RoleRegistry(
        [role if r.id == role.id else r for r in profiles.roles.all()], caps
    )
    async with factory.begin() as session:
        session.add(AgentRoleSkillRecord(role_id=role.id, capability_id="demo.generate"))
    await grant(
        profiles, original.context.user_id, original.context.user_id, role.id, {"demo.generate"}
    )
    access = AccessService(profiles, profiles.roles)

    class Reviewer:
        async def review(self, plan, result):
            return ReviewVerdict(decision="accept")

    delivered = []
    visible = {}

    class Sender:
        async def deliver_task(self, chat_id, message):
            delivered.append(message)
            message_id = len(delivered)
            visible[message_id] = message
            return message_id

        async def delete_task_message(self, chat_id, message_id):
            visible.pop(message_id, None)

    class Runner(ManagedExecution):
        async def run(self, claim):
            value = await super().run(claim)
            if claim.task.plan.selection.parameters["word"] == "quick":
                quick_done.set()
            return value

    async def enqueue(word):
        plan = original.model_copy(
            update={
                "task_id": uuid4().hex[:20],
                "request_id": word,
                "transcript": word,
                "role": role,
                "permission": await access.require(
                    original.context.user_id, role.id, "demo.generate"
                ),
                "selection": CapabilitySelection(
                    role_id=role.id, capability_id="demo.generate", parameters={"word": word}
                ),
            }
        )
        await tasks.save_plan(plan, expected_revision=None)
        await tasks.approve(plan.task_id, 1, plan.context, "yes:" + word, True)
        return plan

    worker = Worker(
        queue,
        Runner(
            tasks,
            TaskExecutionService(tasks, access, caps),
            ReviewService(Reviewer(), render_result),
        ),
        max_concurrency=2,
    )
    try:
        slow = await enqueue("slow")
        await worker.dispatch(NOW)
        await asyncio.wait_for(started.wait(), 2)
        quick = await asyncio.wait_for(enqueue("quick"), 2)
        await worker.dispatch(NOW)
        await asyncio.wait_for(quick_done.wait(), 2)
        await SqlAlchemyTaskOutbox(factory, clock=lambda: NOW).send_due(Sender())
        assert (await tasks.get_owned(slow.task_id, slow.context)).status == "running"
        assert (await tasks.get_owned(quick.task_id, quick.context)).status == "awaiting_feedback"
        assert any(m.task_id == quick.task_id and "QUICK" in m.text for m in delivered)
        assert not any(m.task_id == slow.task_id and m.buttons == "feedback" for m in delivered)
        assert any(m.task_id == slow.task_id and m.buttons is None for m in visible.values())
        assert not any(m.task_id == quick.task_id and m.buttons is None for m in visible.values())
        release.set()
        for _ in range(100):
            if (await tasks.get_owned(slow.task_id, slow.context)).status == "awaiting_feedback":
                break
            await asyncio.sleep(0.01)
        assert (await tasks.get_owned(slow.task_id, slow.context)).status == "awaiting_feedback"
        await SqlAlchemyTaskOutbox(factory, clock=lambda: NOW).send_due(Sender())
        assert any(m.task_id == slow.task_id and "SLOW" in m.text for m in delivered)
        assert len(visible) == 2
        assert all(m.buttons == "feedback" for m in visible.values())
    finally:
        release.set()
        await worker.close()
