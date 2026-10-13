from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from namoz_bot.domain.agent_protocol import AgentContext, AgentDecision, AgentResult


def context():
    return AgentContext(
        bot_id=123456,
        telegram_user_id=7,
        chat_id=7,
        user_id=1,
        message_time=datetime(2026, 10, 13, 10, tzinfo=UTC),
        region_code="Toshkent",
    )


@pytest.mark.parametrize("domain,action", [("prayer", "expense"), ("sql", "execute")])
def test_action_catalog_rejects_invalid_pair(domain, action):
    with pytest.raises(ValidationError):
        AgentDecision(domain=domain, action=action, transcript="test")


def test_provider_cannot_supply_owner():
    with pytest.raises(ValidationError):
        AgentDecision(domain="accounting", action="balance", transcript="test", user_id=8)


@pytest.mark.parametrize(
    "params",
    [
        {"amount": 1.5},
        {"amount": True},
        {"amount": -1},
        {"date": "2026-02-30"},
        {"month": "2026-13"},
    ],
)
def test_domain_parameters_reject_invalid_values(params):
    with pytest.raises(ValidationError):
        AgentDecision(domain="accounting", action="expense", parameters=params, transcript="x")


def test_reminder_time_is_validated():
    with pytest.raises(ValidationError):
        AgentDecision(
            domain="reminder", action="create", parameters={"time": "25:00"}, transcript="test"
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"status": "needs_input"},
        {"status": "error", "effect": "committed", "error_code": "timeout"},
        {"status": "needs_confirmation", "effect": "committed"},
    ],
)
def test_result_status_invariants(kwargs):
    with pytest.raises(ValidationError):
        AgentResult(request_id="r1", operation_id="o1", domain="assistant", action="help", **kwargs)


def test_context_rejects_naive_time():
    with pytest.raises(ValidationError):
        context().model_copy().model_validate(
            context().model_dump()
            | {
                "message_time": datetime(2026, 10, 13),
            }
        )
