import pytest

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.domain.workforce.profiles import AccessDenied, ProfileConflict
from namoz_bot.infrastructure.ai.model_catalog import ModelCatalog
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup


class ValidModels(ModelCatalog):
    async def validate(self, model_id, role):
        if model_id not in self.allowed_models:
            raise ValueError("Unknown model")


@pytest.fixture
async def catalog_setup(access_setup, store):
    from namoz_bot.application.roles.catalog import RoleCatalogService
    from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog

    profiles, access, actor, target = access_setup
    _, factory, _, _ = store
    runtime = SqlRoleCatalog(factory, profiles.roles, profiles=profiles)
    await runtime.initialize()
    service = ProfileService(
        profiles,
        profiles.roles,
        ValidModels(None, ("model-a", "model-b")),
        default_models={r.id: "model-a" for r in profiles.roles.all()},
    )
    catalog = RoleCatalogService(runtime, profiles, service)
    return catalog, runtime, profiles, access, actor, target


def draft(**changes):
    from namoz_bot.domain.workforce.roles import RoleWrite

    return RoleWrite(
        **{
            "name": "Custom specialist",
            "description": "Report and reminders",
            "common_rules": "Ask when unclear",
            "capability_ids": ["finance.report", "reminder.create"],
            "model_id": "model-a",
            "enabled": True,
            **changes,
        }
    )


async def test_role_create_is_scoped_persistent_and_never_autogrants(catalog_setup):
    catalog, runtime, profiles, _, actor, target = catalog_setup
    created = await catalog.create(actor, draft())
    assert created.id.startswith("role_") and created.revision == 1
    async with runtime.scope():
        role = profiles.roles.get(created.id)
        assert role.name == "Custom specialist"
        assert set(role.capability_ids) == {"finance.report", "reminder.create"}
    assert (await profiles.get_profile(target)).roles == ()
    second = type(runtime)(runtime.factory, runtime.roles)
    async with second.scope():
        assert second.roles.get(created.id).common_rules == "Ask when unclear"


async def test_edit_conflicts_templates_copy_and_protected_system_roles(catalog_setup):
    catalog, _runtime, _, _, actor, target = catalog_setup
    with pytest.raises(AccessDenied):
        await catalog.create(target, draft())
    template = await catalog.template(actor)
    await catalog.set_template(actor, "New shared default", template.revision)
    role = await catalog.create(actor, draft(common_rules=None))
    assert role.common_rules == "New shared default"
    changed = await catalog.update(
        actor,
        role.id,
        draft(common_rules="Only this role", expected_revision=1, expected_model_version=1),
    )
    assert changed.revision == 2
    with pytest.raises(ProfileConflict):
        await catalog.update(actor, role.id, draft(expected_revision=1, expected_model_version=1))
    assert (await catalog.template(actor)).rules == "New shared default"
    with pytest.raises(ValueError):
        await catalog.update(actor, "assistant", draft(expected_revision=1))


async def test_removed_skill_cannot_reappear_as_old_user_grant(catalog_setup):
    catalog, runtime, profiles, _, actor, target = catalog_setup
    role = await catalog.create(actor, draft())
    async with runtime.scope():
        await profiles.set_grants(
            actor_id=actor,
            user_id=target,
            role_id=role.id,
            enabled=True,
            capability_ids=frozenset({"finance.report"}),
            expected_revision=0,
        )
    await catalog.update(
        actor,
        role.id,
        draft(capability_ids=["reminder.create"], expected_revision=1, expected_model_version=1),
    )
    await catalog.update(actor, role.id, draft(expected_revision=2, expected_model_version=1))
    view = await profiles.get_profile(target)
    assert view.roles[0].capability_ids == frozenset()
    assert view.roles[0].revision == 2
