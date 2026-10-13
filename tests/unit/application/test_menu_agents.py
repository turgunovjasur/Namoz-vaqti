from datetime import UTC, datetime, timedelta

import pytest

from namoz_bot.application.agent_adapters import AgentAdapters
from namoz_bot.application.menu_agents import (
    AccountingAgent,
    MenuAgentDispatcher,
    NasihatAgent,
    PrayerAgent,
    ReminderAgent,
    RoutedAgentExtractor,
    SettingsAgent,
)
from namoz_bot.domain.agent_protocol import (
    AgentContext,
    AgentDecision,
    AgentHandoffReply,
    AgentRequest,
    AgentRoutingDecision,
    AgentSessionState,
)

NOW = datetime(2026, 10, 13, 10, tzinfo=UTC)


def context():
    return AgentContext(
        bot_id=1, telegram_user_id=7, chat_id=7, user_id=1, message_time=NOW, region_code="Toshkent"
    )


class Router:
    def __init__(self, **changes):
        self.output = AgentRoutingDecision(
            domain="accounting", transcript="Router paraphrase", **changes
        )
        self.calls = []

    async def route(self, **kwargs):
        self.calls.append(kwargs)
        return self.output


class Interpreter:
    def __init__(self, domain, action):
        self.domain, self.action = domain, action
        self.calls = []

    async def interpret(self, handoff):
        self.calls.append(handoff)
        return AgentDecision(domain=self.domain, action=self.action, transcript=handoff.input)


def agents():
    adapters = AgentAdapters()
    specs = [
        (PrayerAgent, "prayer", "schedule"),
        (NasihatAgent, "nasihat", "religious_excerpt"),
        (ReminderAgent, "reminder", "create"),
        (AccountingAgent, "accounting", "balance"),
        (SettingsAgent, "settings", "open"),
    ]
    return {domain: cls(Interpreter(domain, action), adapters) for cls, domain, action in specs}


async def test_only_selected_agent_gets_original_text_and_correlated_handoff():
    router, registry = Router(), agents()
    pipeline = RoutedAgentExtractor(router, registry)
    output = await pipeline.extract(
        text="Balansim qancha?",
        audio=None,
        mime_type="audio/ogg",
        context=context(),
        pending=None,
        request_id="r1",
    )
    assert output.domain == "accounting"
    handoff = registry["accounting"].interpreter.calls[0]
    assert handoff.input == "Balansim qancha?" and handoff.request_id == "r1"
    assert handoff.protocol_version == 1 and len(handoff.operation_id) == 32
    assert all(
        not agent.interpreter.calls for name, agent in registry.items() if name != "accounting"
    )


async def test_audio_is_only_received_by_router():
    router, registry = Router(), agents()
    await RoutedAgentExtractor(router, registry).extract(
        text=None,
        audio=b"OggS",
        mime_type="audio/ogg",
        context=context(),
        pending=None,
        request_id="voice",
    )
    assert router.calls[0]["audio"] == b"OggS"
    handoff = registry["accounting"].interpreter.calls[0]
    assert handoff.input == "Router paraphrase" and not hasattr(handoff, "audio")


@pytest.mark.parametrize("multiple", [False, True])
async def test_assistant_or_multiple_tasks_do_not_call_helpers(multiple):
    router, registry = Router(), agents()
    router.output = AgentRoutingDecision(
        domain="assistant",
        control_action="clarify" if multiple else "help",
        transcript="test",
        multiple_tasks=multiple,
    )
    output = await RoutedAgentExtractor(router, registry).extract(
        text="test",
        audio=None,
        mime_type="audio/ogg",
        context=context(),
        pending=None,
        request_id="help",
    )
    assert output.domain == "assistant" and output.multiple_tasks == multiple
    assert not any(agent.interpreter.calls for agent in registry.values())


async def test_cross_domain_pending_is_not_sent_to_selected_helper():
    router, registry = Router(), agents()
    pending = AgentSessionState(
        domain="reminder",
        action="create",
        parameters={"text": "Private reminder"},
        operation_id="old",
        origin_source_key="old",
        origin_time=NOW,
        revision=1,
        expires_at=NOW + timedelta(hours=24),
    )
    await RoutedAgentExtractor(router, registry).extract(
        text="Balans?",
        audio=None,
        mime_type="audio/ogg",
        context=context(),
        pending=pending,
        request_id="different",
    )
    assert registry["accounting"].interpreter.calls[0].pending is None


async def test_wrong_domain_or_correlation_reply_is_rejected():
    router, registry = Router(), agents()

    async def wrong(handoff):
        return AgentHandoffReply(
            request_id="wrong",
            operation_id=handoff.operation_id,
            domain="accounting",
            decision=AgentDecision(domain="accounting", action="balance", transcript="x"),
        )

    registry["accounting"].interpret = wrong
    with pytest.raises(ValueError):
        await RoutedAgentExtractor(router, registry).extract(
            text="x",
            audio=None,
            mime_type="audio/ogg",
            context=context(),
            pending=None,
            request_id="r1",
        )


async def test_agent_cannot_prepare_another_domains_action():
    request = AgentRequest(
        domain="accounting",
        action="balance",
        transcript="x",
        request_id="r1",
        operation_id="op",
        context=context(),
    )
    with pytest.raises(ValueError):
        await agents()["prayer"].prepare(request)


def test_dispatcher_requires_all_domains_and_matching_registration():
    registry = agents()
    registry.pop("accounting")
    with pytest.raises(ValueError):
        MenuAgentDispatcher(registry)
