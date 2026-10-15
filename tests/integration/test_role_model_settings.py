import pytest

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.domain.workforce.profiles import AccessDenied, ProfileConflict
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup
from tests.integration.test_workforce_access import grant


class Catalog:
    def __init__(self):
        self.calls = []

    async def validate(self, model_id, role):
        self.calls.append((model_id, role.id))
        if model_id != "allowed-model":
            raise ValueError("Unsupported model")

    def list_for_role(self, role_id):
        return ()


def service(profiles):
    return ProfileService(
        profiles,
        profiles.roles,
        Catalog(),
        default_models={r.id: "original-model" for r in profiles.roles.all()},
    )


async def test_model_change_is_global_versioned_persistent_and_probed(access_setup):
    profiles, _, admin, user = access_setup
    first = service(profiles)
    frozen = await first.model("accounting")
    changed = await first.set_model(
        actor_id=admin, role_id="accounting", model_id="allowed-model", expected_version=0
    )
    assert frozen.model_id == "original-model"
    assert changed.version == 1
    restarted = service(profiles)
    assert (await restarted.model("accounting")).model_id == "allowed-model"
    assert (await restarted.model("prayer")).model_id == "original-model"
    with pytest.raises(ValueError):
        await restarted.set_model(
            actor_id=admin, role_id="accounting", model_id="invalid-model", expected_version=1
        )
    assert (await restarted.model("accounting")) == changed
    with pytest.raises(ProfileConflict):
        await restarted.set_model(
            actor_id=admin, role_id="accounting", model_id="allowed-model", expected_version=0
        )
    with pytest.raises(AccessDenied):
        await restarted.set_model(
            actor_id=user, role_id="accounting", model_id="allowed-model", expected_version=1
        )
    assert len(restarted.catalog.calls) == 2


async def test_profiles_only_reveal_assignments_and_require_admin_for_other_users(access_setup):
    profiles, _, admin, user = access_setup
    app = service(profiles)
    assert (await app.self_view(user)).profile_type == "user"
    with pytest.raises(AccessDenied):
        await app.user_view(user, admin)
    with pytest.raises(AccessDenied):
        await app.list_users(user, after_id=0, limit=10)
    page = await app.list_users(admin, after_id=0, limit=1)
    assert len(page.users) == 1 and page.more
    assert not hasattr(page.users[0], "balance")


async def test_admin_lookup_and_audit_pagination_deny_user_and_show_only_changes(access_setup):
    profiles, _, admin, user = access_setup
    app = service(profiles)
    assert (await app.find_user(admin, 8)).user_id == user
    assert await app.find_user(admin, 999999) is None
    with pytest.raises(AccessDenied):
        await profiles.find_user(user, 7)
    await grant(profiles, admin, user, "accounting", {"finance.report"})
    await grant(profiles, admin, user, "accounting", {"finance.expense"})
    first = await app.history(admin, limit=1)
    second = await app.history(admin, before_id=first.changes[-1].id, limit=1)
    assert first.more and not second.more
    assert first.changes[0].id > second.changes[0].id
    assert first.changes[0].target_telegram_id == 8
    assert first.changes[0].detail["capability_ids"] == ["finance.expense"]
    assert not hasattr(first.changes[0], "balance")
    with pytest.raises(AccessDenied):
        await profiles.history(user, before_id=0, limit=10)
