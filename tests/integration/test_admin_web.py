from datetime import timedelta

import httpx
import pytest
from sqlalchemy import select

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.config import Settings
from namoz_bot.domain.workforce.profiles import AccessDenied
from namoz_bot.infrastructure.ai.model_catalog import ModelCatalog
from namoz_bot.infrastructure.orm import UserRecord
from tests.integration.test_agent_sessions import NOW
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_workforce_access import access_setup as access_setup


@pytest.fixture
async def web(access_setup, store):
    from namoz_bot.infrastructure.admin_web.auth import AdminAuth
    from namoz_bot.presentation.admin_web.app import create_app

    profiles, _, actor, other = access_setup
    _, factory, _, _ = store
    settings = Settings(
        telegram_bot_token="123:test",
        database_url="unused",
        admin_telegram_ids=frozenset({7}),
        admin_web_url="http://localhost:8088",
        _env_file=None,
    )
    service = ProfileService(
        profiles,
        profiles.roles,
        ModelCatalog(None, ("test-model",)),
        default_models={r.id: "test-model" for r in profiles.roles.all()},
    )
    auth = AdminAuth(factory, settings.admin_telegram_ids)
    app = create_app(settings, factory, service)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://localhost:8088",
        headers={"Origin": "http://localhost:8088"},
    ) as client:
        yield client, auth, profiles, actor, other, factory


async def login(client, auth):
    ticket = await auth.issue_ticket(7)
    response = await client.post("/api/auth/exchange", json={"token": ticket})
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return ticket


async def test_login_is_single_use_logout_revokes_and_never_exposes_finance(web):
    client, auth, _, _, _, _ = web
    assert (await client.get("/api/users")).status_code == 401
    ticket = await login(client, auth)
    assert (await client.post("/api/auth/exchange", json={"token": ticket})).status_code == 401
    users = (await client.get("/api/users")).json()
    assert [u["telegram_user_id"] for u in users["users"]] == [7, 8]
    assert "finance_entries" not in str(users)
    assert (await client.post("/api/auth/logout")).status_code == 200
    assert (await client.get("/api/session")).status_code == 401


async def test_ticket_expiry_and_nonadmin_and_admin_revocation(web):
    client, auth, _, _, _, _ = web
    with pytest.raises(AccessDenied):
        await auth.issue_ticket(8)
    expired = await auth.issue_ticket(7, now=NOW - timedelta(minutes=6))
    assert (await client.post("/api/auth/exchange", json={"token": expired})).status_code == 401
    await login(client, auth)
    auth.admin_telegram_ids = frozenset()
    # app owns another Auth instance with the same authoritative configuration; revoke it too.
    client._transport.app.state.auth.admin_telegram_ids = frozenset()
    assert (await client.get("/api/session")).status_code == 401


async def test_csrf_origin_and_host_are_required_for_writes(web):
    client, auth, _, _, _, _ = web
    await login(client, auth)
    client.headers.pop("X-CSRF-Token")
    assert (await client.post("/api/auth/logout")).status_code == 403
    client.headers["Origin"] = "https://evil.example"
    assert (await client.post("/api/auth/exchange", json={"token": "x"})).status_code == 403
    assert (await client.get("/api/session", headers={"Host": "evil.example"})).status_code == 400


async def test_search_filters_atomic_stale_edit_and_registry_metadata(web):
    client, auth, profiles, _actor, other, factory = web
    async with factory.begin() as session:
        row = await session.get(UserRecord, other)
        row.display_name, row.username = "Aziza Test", "aziza_demo"
    await login(client, auth)
    page = (await client.get("/api/users", params={"q": "AZIZA", "limit": 1})).json()
    assert [u["user_id"] for u in page["users"]] == [other]
    assert not page["more"]
    assert (await client.get("/api/users", params={"q": "100%"})).json()["users"] == []
    payload = {
        "changes": [
            {
                "role_id": "accounting",
                "enabled": True,
                "capability_ids": ["finance.report"],
                "expected_revision": 0,
            }
        ]
    }
    url = f"/api/users/{other}/assignments"
    response = await client.put(url, json=payload)
    assert response.status_code == 200, response.text
    assert (await client.put(url, json=payload)).status_code == 409
    assert (await client.get("/api/users", params={"role_id": "accounting"})).json()["users"][0][
        "user_id"
    ] == other
    assert (await profiles.current_grant(other, "accounting", "finance.report")) is not None
    assert await profiles.current_grant(other, "accounting", "finance.expense") is None
    roles = (await client.get("/api/roles")).json()["roles"]
    accountant = next(r for r in roles if r["id"] == "accounting")
    assert "finance.report" in [c["id"] for c in accountant["capabilities"]]
    assert "instruction" not in str(roles)
    assert (await client.get("/api/history")).json()["changes"][0]["actor_telegram_id"] == 7
    models = (await client.get("/api/models")).json()["models"]
    assert len(models) == 7
    assert all(m["model_id"] == "test-model" for m in models)


async def test_session_token_stored_only_as_hash_and_expiry(web):
    from namoz_bot.infrastructure.orm import AdminWebSessionRecord

    client, auth, _, _, _, factory = web
    await login(client, auth)
    token = client.cookies.get("yordamchi_admin")
    async with factory.begin() as session:
        row = await session.scalar(select(AdminWebSessionRecord))
        assert row.token_hash != token
        assert len(row.token_hash) == 64
        row.expires_at = NOW - timedelta(days=1)
    assert (await client.get("/api/users")).status_code == 401
