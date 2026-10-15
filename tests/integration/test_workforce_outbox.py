from datetime import timedelta

from namoz_bot.infrastructure.workforce.outbox import SqlAlchemyTaskOutbox
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_tasks import workforce as workforce


class AmbiguousSender:
    def __init__(self):
        self.messages = []

    async def deliver_task(self, chat_id, message):
        self.messages.append((chat_id, message))
        if len(self.messages) == 1:
            raise TimeoutError("sent but acknowledgment unknown")


async def test_ambiguous_telegram_retry_only_retries_outbox_not_business(workforce):
    tasks, _, _, plan, factory, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)
    sender = AmbiguousSender()
    outbox = SqlAlchemyTaskOutbox(factory, clock=lambda: current[0])
    await outbox.send_due(sender)
    current[0] += timedelta(minutes=2)
    await SqlAlchemyTaskOutbox(factory, clock=lambda: current[0]).send_due(sender)
    assert len(sender.messages) == 2
    assert sender.messages[0] == sender.messages[1]
    await outbox.send_due(sender)
    assert len(sender.messages) == 2
    assert (await tasks.get_owned(plan.task_id, plan.context)).service_result is None
