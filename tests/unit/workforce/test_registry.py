from datetime import UTC, datetime

import pytest

from namoz_bot.application.capabilities.registry import (
    CapabilityRegistry,
    build_capability_registry,
)
from namoz_bot.application.roles.registry import RoleRegistry
from namoz_bot.domain.agent_protocol import AgentContext, AgentRequest
from namoz_bot.domain.workforce.capabilities import CapabilitySelection
from tests.helpers.roles import build_role_registry

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)


def test_registry_rejects_duplicate_executor_identity():
    capabilities = build_capability_registry()
    balance = capabilities.get("finance.balance")
    with pytest.raises(ValueError, match="Duplicate capability"):
        CapabilityRegistry([balance, balance])


def test_role_registry_rejects_unknown_and_duplicate_references():
    capabilities = build_capability_registry()
    roles = build_role_registry(capabilities)
    accountant = roles.get("accounting")
    with pytest.raises(ValueError, match="Duplicate role"):
        RoleRegistry([accountant, accountant], capabilities)
    invalid = accountant.model_copy(update={"capability_ids": ("unknown.read",)})
    with pytest.raises(ValueError, match="Unknown capability"):
        RoleRegistry([invalid], capabilities)


def test_model_cannot_select_another_roles_capability_or_inject_identity():
    roles = build_role_registry(build_capability_registry())
    with pytest.raises(ValueError, match="outside"):
        roles.validate_selection(
            CapabilitySelection(role_id="settings", capability_id="finance.expense")
        )
    for parameters in [{"amount": True}, {"user_id": 987654}]:
        with pytest.raises(ValueError):
            roles.validate_selection(
                CapabilitySelection(
                    role_id="accounting", capability_id="finance.expense", parameters=parameters
                )
            )


def test_background_delivery_is_not_an_ai_callable_capability():
    roles = build_role_registry(build_capability_registry())
    with pytest.raises(ValueError, match="conversation"):
        roles.validate_selection(
            CapabilitySelection(role_id="nasihat", capability_id="nasihat.deliver")
        )


def test_shared_preferences_resolve_to_one_executor_for_two_roles():
    capabilities = build_capability_registry()
    context = AgentContext(
        bot_id=123456,
        user_id=1,
        telegram_user_id=7,
        chat_id=7,
        message_time=NOW,
        region_code="Toshkent",
    )
    prayer = AgentRequest(
        context=context,
        request_id="prayer",
        operation_id="prayer",
        domain="prayer",
        action="open_settings",
        parameters={"view": "region"},
        transcript="x",
    )
    settings = AgentRequest(
        context=context,
        request_id="settings",
        operation_id="settings",
        domain="settings",
        action="open",
        parameters={"view": "region"},
        transcript="x",
    )
    assert capabilities.for_request(prayer) is capabilities.for_request(settings)
    assert capabilities.for_request(prayer).spec.id == "preferences.region_view"


def test_missing_values_stay_missing_for_followup_merging():
    roles = build_role_registry(build_capability_registry())
    selection = roles.validate_selection(
        CapabilitySelection(
            role_id="reminder", capability_id="reminder.create", parameters={"time": "09:00"}
        )
    )
    assert selection.parameters == {"time": "09:00"}
