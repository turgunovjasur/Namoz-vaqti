import pytest

from namoz_bot.application.capabilities.registry import (
    CapabilityDispatcher,
    build_capability_registry,
)
from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.catalog import RoleCatalogService
from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.application.workforce.access import AccessService
from namoz_bot.domain.agent_protocol import AgentContext, AgentRequest
from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_dynamic_roles import ValidModels, draft
from tests.integration.test_workforce_access import grant


def test_new_registry_has_only_the_permanent_assistant():
    assert [r.id for r in build_role_registry(build_capability_registry()).all()] == ["assistant"]


async def test_panel_role_drives_legacy_skill_and_archive_revokes_it(store):
    _, factory, actor, target = store
    caps = build_capability_registry()
    roles = build_role_registry(caps)
    profiles = SqlAlchemyProfileRepository(factory, roles, admin_telegram_ids=frozenset({7}))
    runtime = SqlRoleCatalog(factory, roles, profiles=profiles)
    access = AccessService(profiles, roles, runtime=runtime.runtime)
    models = ProfileService(
        profiles, roles, ValidModels(None, ("model-a",)), default_models={"assistant": "model-a"}
    )
    service = RoleCatalogService(runtime, profiles, models)
    await runtime.initialize()
    created = await service.create(actor, draft(capability_ids=["finance.balance"]))
    async with runtime.scope():
        await grant(profiles, actor, target, created.id, {"finance.balance"})
        request = AgentRequest(
            domain="accounting",
            action="balance",
            transcript="Balans",
            request_id="dynamic",
            operation_id="a" * 26,
            context=AgentContext(
                bot_id=123456,
                user_id=target,
                telegram_user_id=8,
                chat_id=8,
                message_time=NOW,
                region_code="Toshkent",
            ),
        )
        result = await CapabilityDispatcher(roles, caps, access).prepare(request)
        assert result.status == "done"
    await service.archive(actor, created.id, expected_revision=1)
    assert not await access.allowed(target, created.id, "finance.balance")
    async with runtime.scope():
        assert roles.get(created.id).archived
    with pytest.raises(ValueError):
        await service.archive(actor, "assistant", expected_revision=1)
    with pytest.raises(ValueError):
        await service.update(
            actor, created.id, draft(expected_revision=2, expected_model_version=1)
        )
