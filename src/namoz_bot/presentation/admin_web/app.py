"""Same-origin admin API and compiled UI. Authorization stays server-side."""

import hmac
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.profiles.service import ProfileService
from namoz_bot.application.roles.catalog import RoleCatalogService
from namoz_bot.config import Settings
from namoz_bot.domain.errors import ExternalServiceError
from namoz_bot.domain.workforce.profiles import AccessDenied, ProfileConflict
from namoz_bot.infrastructure.admin_web.auth import AdminAuth, AdminIdentity, csrf_token
from namoz_bot.infrastructure.admin_web.queries import AdminQueries
from namoz_bot.infrastructure.roles.repository import SqlRoleCatalog
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from namoz_bot.presentation.admin_web.role_routes import role_router
from namoz_bot.presentation.admin_web.schemas import AssignmentInput, ModelInput, TicketInput

COOKIE = "yordamchi_admin"


def create_app(
    settings: Settings,
    factory: async_sessionmaker[AsyncSession],
    service: ProfileService,
    *,
    dist: Path | None = None,
) -> FastAPI:
    dist = dist or settings.admin_web_dist
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    auth = AdminAuth(factory, settings.admin_telegram_ids)
    app.state.auth = auth
    profiles = service.repository
    if not isinstance(profiles, SqlAlchemyProfileRepository):
        raise TypeError("Admin panel requires the SQL profile repository")
    queries = AdminQueries(profiles)
    catalog = SqlRoleCatalog(factory, service.roles, profiles=profiles)
    role_service = RoleCatalogService(catalog, profiles, service)
    app.state.role_service = role_service
    origin = settings.admin_web_url
    authority = urlsplit(origin).netloc.lower()
    secure = origin.startswith("https://")

    @app.middleware("http")
    async def boundaries(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.headers.get("host", "").lower() != authority:
            return JSONResponse({"detail": "Noto‘g‘ri server manzili."}, status_code=400)
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if request.headers.get("origin") != origin:
                return JSONResponse({"detail": "So‘rov manbasi tasdiqlanmadi."}, status_code=403)
        if request.url.path.startswith("/api/"):
            async with catalog.scope():
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
            "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; "
            "form-action 'self'; object-src 'none'"
        )
        if secure:
            response.headers["Strict-Transport-Security"] = "max-age=31536000"
        return response

    @app.exception_handler(AccessDenied)
    async def denied(request: Request, exc: AccessDenied) -> JSONResponse:
        return JSONResponse({"detail": str(exc)}, status_code=403)

    @app.exception_handler(ProfileConflict)
    async def conflict(request: Request, exc: ProfileConflict) -> JSONResponse:
        return JSONResponse(
            {"detail": "Ma’lumot boshqa joyda o‘zgartirilgan. Yangilab qayta tahrirlang."},
            status_code=409,
        )

    @app.exception_handler(ValueError)
    async def invalid(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Rol, imkoniyat yoki model qiymatini tekshiring."}, status_code=400
        )

    @app.exception_handler(KeyError)
    async def missing(request: Request, exc: KeyError) -> JSONResponse:
        return JSONResponse({"detail": "Rol topilmadi."}, status_code=404)

    @app.exception_handler(ExternalServiceError)
    async def unavailable(request: Request, exc: ExternalServiceError) -> JSONResponse:
        return JSONResponse(
            {"detail": "Gemini modelini tekshirish bajarilmadi. Sozlama saqlanmadi."},
            status_code=502,
        )

    async def identity(request: Request) -> AdminIdentity:
        try:
            actor = await auth.authenticate(request.cookies.get(COOKIE))
        except AccessDenied as exc:
            raise HTTPException(401, str(exc)) from None
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if not hmac.compare_digest(
                request.headers.get("x-csrf-token", "").encode(), actor.csrf_token.encode()
            ):
                raise HTTPException(403, "Sahifani yangilang va qayta urinib ko‘ring.")
        return actor

    Actor = Annotated[AdminIdentity, Depends(identity)]

    @app.post("/api/auth/exchange")
    async def exchange(body: TicketInput, request: Request, response: Response) -> dict[str, str]:
        try:
            token = await auth.exchange_ticket(body.token)
        except AccessDenied as exc:
            raise HTTPException(401, str(exc)) from None
        old = request.cookies.get(COOKIE)
        if old:
            await auth.revoke(old)
        response.set_cookie(
            COOKIE,
            token,
            max_age=8 * 3600,
            httponly=True,
            secure=secure,
            samesite="strict",
            path="/",
        )
        return {"csrf_token": csrf_token(token)}

    @app.get("/api/session")
    async def session(actor: Actor) -> dict[str, Any]:
        return {
            "csrf_token": actor.csrf_token,
            "admin": (await service.self_view(actor.user_id)).model_dump(mode="json"),
        }

    @app.post("/api/auth/logout")
    async def logout(actor: Actor, request: Request, response: Response) -> dict[str, bool]:
        await auth.revoke(request.cookies[COOKIE])
        response.delete_cookie(COOKIE, path="/", secure=secure, httponly=True, samesite="strict")
        return {"ok": True}

    @app.get("/api/users")
    async def users(
        actor: Actor,
        q: Annotated[str, Query(max_length=100)] = "",
        role_id: Annotated[str | None, Query(max_length=32)] = None,
        after_id: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=20)] = 20,
    ) -> dict[str, Any]:
        page = await queries.users(
            actor.user_id, q=q, role_id=role_id, after_id=after_id, limit=limit
        )
        return {**page.model_dump(mode="json"), "counts": await queries.counts(actor.user_id)}

    @app.get("/api/users/{user_id}")
    async def user(user_id: int, actor: Actor) -> dict[str, Any]:
        return (await service.user_view(actor.user_id, user_id)).model_dump(mode="json")

    @app.put("/api/users/{user_id}/assignments")
    async def assignments(user_id: int, body: AssignmentInput, actor: Actor) -> dict[str, Any]:
        return (
            await service.set_assignments(
                actor_id=actor.user_id, user_id=user_id, changes=tuple(body.changes)
            )
        ).model_dump(mode="json")

    app.include_router(role_router(role_service, catalog, identity))

    @app.get("/api/models")
    async def models(actor: Actor) -> dict[str, Any]:
        return {
            "models": [
                {
                    **(await service.model(r.id)).model_dump(mode="json"),
                    "options": service.model_options(r.id),
                }
                for r in service.roles.all()
                if not r.archived
            ]
        }

    @app.put("/api/models/{role_id}")
    async def set_model(role_id: str, body: ModelInput, actor: Actor) -> dict[str, Any]:
        return (
            await service.set_model(
                actor_id=actor.user_id,
                role_id=role_id,
                model_id=body.model_id,
                expected_version=body.expected_version,
            )
        ).model_dump(mode="json")

    @app.get("/api/history")
    async def history(actor: Actor, before_id: Annotated[int, Query(ge=0)] = 0) -> dict[str, Any]:
        return (await service.history(actor.user_id, before_id=before_id, limit=20)).model_dump(
            mode="json"
        )

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/")
    async def index() -> Response:
        if not (dist / "index.html").is_file():
            return JSONResponse(
                {"detail": "Frontendni avval yig‘ing: cd web/admin && npm ci && npm run build"},
                status_code=503,
            )
        return FileResponse(dist / "index.html")

    return app
