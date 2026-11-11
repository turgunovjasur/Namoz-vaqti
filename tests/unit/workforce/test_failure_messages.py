import pytest

from namoz_bot.infrastructure.orm import WorkforceRevisionRecord
from namoz_bot.infrastructure.workforce.queue import failure_message


@pytest.mark.parametrize("effect", [None, "committed", "none"])
def test_failure_identifies_task_and_preserves_saved_action_warning(effect):
    row = WorkforceRevisionRecord(
        task_id="parallel-task",
        revision=2,
        plan={"transcript": "Oylik xarajatlar hisobotini tayyorla"},
        service_result={"effect": effect} if effect else None,
    )
    message = failure_message(row)
    assert "Oylik xarajatlar hisobotini tayyorla" in message.text
    assert message.task_id == "parallel-task"
    assert message.revision == 2
    if effect:
        assert "Amalni qayta bajarmang" in message.text
    if effect == "committed":
        assert "Amal saqlandi" in message.text
