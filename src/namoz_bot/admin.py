"""Explicit local/production admin server and trusted one-use login link CLI."""

import argparse
import asyncio
import os
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from namoz_bot.application.roles.registry import build_role_registry
from namoz_bot.config import Settings
from namoz_bot.infrastructure.admin_web.auth import AdminAuth
from namoz_bot.infrastructure.ai.gemini_client import GeminiClient
from namoz_bot.infrastructure.db import create_database
from namoz_bot.infrastructure.skills.bootstrap import build_runtime_capabilities
from namoz_bot.infrastructure.workforce.bootstrap import build_profile_service
from namoz_bot.infrastructure.workforce.profiles import SqlAlchemyProfileRepository
from namoz_bot.local import LocalSettings


def load_settings(*, local: bool) -> Settings:
    if local:
        test = LocalSettings()  # type: ignore[call-arg]
        return Settings(telegram_bot_token=test.token, database_url=test.database_url)
    return Settings()  # type: ignore[call-arg]


async def issue_link(
    settings: Settings, factory: async_sessionmaker[AsyncSession], telegram_id: int | None
) -> str:
    if telegram_id is None:
        if len(settings.admin_telegram_ids) != 1:
            raise ValueError("--telegram-id bilan administratorni tanlang.")
        telegram_id = next(iter(settings.admin_telegram_ids))
    token = await AdminAuth(factory, settings.admin_telegram_ids).issue_ticket(telegram_id)
    return f"{settings.admin_web_url}/#login={token}"


async def run(args: argparse.Namespace, settings: Settings) -> None:
    engine, factory = create_database(settings.database_url)
    try:
        if args.command == "link":
            link = await issue_link(settings, factory, cast(int | None, args.telegram_id))
            if args.output:
                path = Path(args.output)
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w") as file:
                    os.fchmod(file.fileno(), 0o600)
                    file.write(link + "\n")
                print("Bir martalik havola ko‘rsatilgan faylga yozildi.")
            else:
                print(link)
            return
        import uvicorn

        from namoz_bot.presentation.admin_web.app import create_app

        async with httpx.AsyncClient(timeout=30) as http:
            profiles = SqlAlchemyProfileRepository(
                factory,
                build_role_registry(build_runtime_capabilities(http=http)),
                admin_telegram_ids=settings.admin_telegram_ids,
            )
            transport = (
                GeminiClient(http, api_key=settings.gemini_api_key)
                if settings.gemini_api_key
                else None
            )
            service = build_profile_service(settings, profiles, transport)
            app = create_app(settings, factory, service)
            port = args.port or urlsplit(settings.admin_web_url).port or 8088
            config = uvicorn.Config(
                app,
                host=args.host,
                port=port,
                access_log=False,
                proxy_headers=False,
                log_level="warning",
            )
            print(
                f"Admin panel tayyor: {settings.admin_web_url} "
                f"({'TEST' if args.local else 'production'} baza)",
                flush=True,
            )
            await uvicorn.Server(config).serve()
    finally:
        await engine.dispose()


def run_cli() -> None:
    parser = argparse.ArgumentParser(description="Yordamchi admin panel")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--local", action="store_true", help="TEST bot va TEST bazadan foydalanish")
    mode.add_argument("--production", action="store_true", help="Production sozlamalari")
    parser.add_argument("command", choices=("serve", "link"), nargs="?", default="serve")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int)
    parser.add_argument("--telegram-id", type=int)
    parser.add_argument("--output", help="Kirish havolasini 0600 faylga yozish")
    args = parser.parse_args()
    asyncio.run(run(args, load_settings(local=args.local)))


if __name__ == "__main__":
    run_cli()
