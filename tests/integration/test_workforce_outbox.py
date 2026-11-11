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


async def test_failure_cleans_status_after_restart_and_cleanup_retry_never_resends(workforce):
    from aiogram import Bot
    from aiogram.methods import DeleteMessage, SendMessage

    from namoz_bot.infrastructure.telegram import TelegramMessageSender
    from tests.acceptance.test_voice_reminder_journey import VoiceSession

    tasks, queue, _, plan, factory, _, current = workforce
    await tasks.save_plan(plan, expected_revision=None)
    await tasks.approve(plan.task_id, 1, plan.context, "yes", True)

    class FlakyDeleteSession(VoiceSession):
        fail_delete = True

        async def make_request(self, bot, method, timeout=None):  # noqa: ASYNC109
            if isinstance(method, DeleteMessage) and self.fail_delete:
                self.fail_delete = False
                raise TimeoutError("Temporary transport failure")
            return await super().make_request(bot, method, timeout)

    transport = FlakyDeleteSession()
    bot = Bot("123456:LOCAL_TEST", session=transport)
    try:
        sender = TelegramMessageSender(bot)
        await SqlAlchemyTaskOutbox(factory, clock=lambda: current[0]).send_due(sender)
        status_id = transport.last_ids[7]
        claim = (await queue.claim(now=current[0], limit=1, lease_seconds=180))[0]
        await queue.fail(claim, permanent=True, now=current[0])
        await SqlAlchemyTaskOutbox(factory, clock=lambda: current[0]).send_due(sender)
        assert len(transport.messages) == 2  # Result delivered, cleanup will retry.
        final_id = transport.last_ids[7]
        current[0] += timedelta(minutes=2)
        await SqlAlchemyTaskOutbox(factory, clock=lambda: current[0]).send_due(sender)
        assert set(transport.messages) == {(7, final_id)}
        assert final_id != status_id
        assert len([c for c in transport.calls if isinstance(c, SendMessage)]) == 2
    finally:
        await bot.session.close()
