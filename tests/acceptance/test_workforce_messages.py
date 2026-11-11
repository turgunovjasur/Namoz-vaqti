"""Task status cards disappear without removing results or another task's card."""

from aiogram.methods import SendMessage

from tests.acceptance.test_workforce_journey import workforce_journey as workforce_journey
from tests.acceptance.test_workforce_journey import workforce_route as workforce_route
from tests.helpers.workforce import drain_workforce


async def test_approval_status_and_feedback_leave_only_result(workforce_journey, workforce_route):
    j = workforce_journey
    before = set(j.session.messages)
    await j.voice()
    created = set(j.session.messages) - before
    assert len(created) == 1
    preview = next(iter(created))
    assert j.session.messages[preview].text.startswith("🤖")
    await j.click("✅ Ha")
    assert preview not in j.session.messages
    await j.app.scheduler.get_job("workforce-delivery").func()
    status = set(j.session.messages) - before
    assert len(status) == 1
    assert j.session.messages[next(iter(status))].text.startswith("🤖")
    await drain_workforce(j.app)
    remaining = set(j.session.messages) - before
    assert len(remaining) == 1 and remaining.isdisjoint(status)
    assert "120 000" in j.last.text
    result = next(iter(remaining))
    sent = sum(isinstance(c, SendMessage) for c in j.session.calls)
    await j.click("✅ Ha")
    assert sum(isinstance(c, SendMessage) for c in j.session.calls) == sent
    assert result in j.session.messages
    assert j.session.messages[result].reply_markup is None


async def test_reject_removes_preview_and_sends_one_assistant_reply(
    workforce_journey, workforce_route
):
    j = workforce_journey
    before = set(j.session.messages)
    await j.voice()
    preview = j.session.last_ids[7]
    await j.click("❌ Yo‘q")
    assert (7, preview) not in j.session.messages
    remaining = set(j.session.messages) - before
    assert len(remaining) == 1
    assert j.session.messages[next(iter(remaining))].text.startswith("🤖")
    await j.app.scheduler.get_job("workforce-delivery").func()
    assert set(j.session.messages) - before == remaining
