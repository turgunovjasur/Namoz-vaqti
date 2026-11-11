"""Admin role and reusable skill management. No executable code is accepted from forms."""

from collections.abc import Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from namoz_bot.application.roles.catalog import RoleCatalogService
from namoz_bot.domain.workforce.roles import RoleWrite
from namoz_bot.infrastructure.admin_web.auth import AdminIdentity
from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog
from namoz_bot.presentation.admin_web.role_views import role_view, skill_view


class TemplateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rules: str = Field(max_length=8000)
    expected_revision: int = Field(ge=1)


class ArchiveInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(ge=1)


def role_router(
    service: RoleCatalogService, catalog: SqlRoleCatalog, identity: Callable[..., Any]
) -> APIRouter:
    router = APIRouter()
    Actor = Annotated[AdminIdentity, Depends(identity)]

    @router.get("/api/roles")
    async def roles(actor: Actor) -> dict[str, Any]:
        return {
            "roles": [
                await role_view(service.models, r)
                for r in service.models.roles.all()
                if not r.archived
            ]
        }

    @router.get("/api/skills")
    async def skills(actor: Actor) -> dict[str, Any]:
        return {
            "skills": [
                skill_view(service.models, c.spec.id)
                for c in service.models.roles.capabilities.all()
            ]
        }

    @router.post("/api/roles")
    async def create(body: RoleWrite, actor: Actor) -> dict[str, Any]:
        role = await service.create(actor.user_id, body)
        return await role_view(service.models, role)

    @router.put("/api/roles/{role_id}")
    async def update(role_id: str, body: RoleWrite, actor: Actor) -> dict[str, Any]:
        role = await service.update(actor.user_id, role_id, body)
        return await role_view(service.models, role)

    @router.delete("/api/roles/{role_id}")
    async def archive(role_id: str, body: ArchiveInput, actor: Actor) -> dict[str, bool]:
        await service.archive(actor.user_id, role_id, expected_revision=body.expected_revision)
        return {"ok": True}

    @router.get("/api/role-template")
    async def template(actor: Actor) -> dict[str, Any]:
        return (await service.template(actor.user_id)).model_dump(mode="json")

    @router.put("/api/role-template")
    async def set_template(body: TemplateInput, actor: Actor) -> dict[str, Any]:
        return (
            await service.set_template(actor.user_id, body.rules, body.expected_revision)
        ).model_dump(mode="json")

    return router
