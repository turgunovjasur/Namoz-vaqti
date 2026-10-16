from tests.integration.test_admin_web import login
from tests.integration.test_admin_web import web as web
from tests.integration.test_agent_sessions import store as store
from tests.integration.test_dynamic_roles import ValidModels
from tests.integration.test_workforce_access import access_setup as access_setup


async def test_admin_creates_edits_role_template_and_assigns_reusable_skill(web):
    client, auth, _, _, target, _ = web
    await login(client, auth)
    client._transport.app.state.role_service.models.catalog = ValidModels(None, ("test-model",))
    template = (await client.get("/api/role-template")).json()
    assert "rules" in template
    response = await client.put(
        "/api/role-template",
        json={"rules": "Shared rule", "expected_revision": template["revision"]},
    )
    assert response.status_code == 200, response.text
    skills = (await client.get("/api/skills")).json()["skills"]
    assert any(s["id"] == "finance.report" for s in skills)
    payload = {
        "name": "Audit assistant",
        "description": "Only financial reports",
        "model_id": "test-model",
        "capability_ids": ["finance.report"],
        "enabled": True,
    }
    response = await client.post("/api/roles", json=payload)
    assert response.status_code == 200, response.text
    role = response.json()
    assert role["common_rules"] == "Shared rule" and role["revision"] == 1
    assert role["model"]["version"] == 1
    url = f"/api/users/{target}/assignments"
    response = await client.put(
        url,
        json={
            "changes": [
                {
                    "role_id": role["id"],
                    "enabled": True,
                    "capability_ids": ["finance.report"],
                    "expected_revision": 0,
                }
            ]
        },
    )
    assert response.status_code == 200, response.text
    assert (await client.get("/api/users", params={"role_id": role["id"]})).json()["users"][0][
        "user_id"
    ] == target
    payload.update(common_rules="Only this agent", expected_revision=1, expected_model_version=1)
    response = await client.put("/api/roles/" + role["id"], json=payload)
    assert response.status_code == 200, response.text
    assert response.json()["revision"] == 2
    assert (await client.put("/api/roles/" + role["id"], json=payload)).status_code == 409
    assert (await client.get("/api/role-template")).json()["rules"] == "Shared rule"
    assert any(r["id"] == role["id"] for r in (await client.get("/api/roles")).json()["roles"])
    assert (
        await client.post(
            "/api/roles", json={**payload, "name": "Unknown skill", "capability_ids": ["bad.skill"]}
        )
    ).status_code == 400
    await client.post("/api/auth/logout")
    assert (await client.post("/api/roles", json=payload)).status_code == 401
