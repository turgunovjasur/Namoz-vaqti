"""Application composition root and polling lifecycle."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import date

import httpx
from aiogram import Bot, Dispatcher
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from namoz_bot.application.broadcasting import BroadcastReport, BroadcastService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.config import Settings
from namoz_bot.infrastructure.db import create_database
from namoz_bot.infrastructure.islom_api import IslomApiClient
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)
from namoz_bot.infrastructure.telegram import TelegramMessageSender
from namoz_bot.logging import configure_logging
from namoz_bot.presentation.handlers import router
from namoz_bot.presentation.middleware import ServicesMiddleware
from namoz_bot.scheduler import create_scheduler

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApplicationResources:
    """All process-owned resources with deterministic shutdown."""

    bot: Bot
    dispatcher: Dispatcher
    http_client: httpx.AsyncClient
    db_engine: AsyncEngine
    scheduler: AsyncIOScheduler

    async def close(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await self.bot.session.close()
        await self.http_client.aclose()
        await self.db_engine.dispose()


def _build_broadcast_runner(
    session_factory: async_sessionmaker[AsyncSession],
    schedule_service: ScheduleService,
    sender: TelegramMessageSender,
) -> Callable[[date], Awaitable[BroadcastReport]]:
    async def run_broadcast(target_date: date) -> BroadcastReport:
        async with session_factory() as session:
            service = BroadcastService(
                SqlAlchemySubscriptionRepository(session),
                SqlAlchemyDeliveryRepository(session),
                schedule_service,
                sender,
            )
            try:
                report = await service.send_next_day(target_date)
            except Exception:
                await session.rollback()
                logger.exception("daily_broadcast_failed date=%s", target_date.isoformat())
                raise
            await session.commit()
            logger.info(
                "daily_broadcast_complete date=%s sent=%d skipped=%d deactivated=%d failed=%d",
                target_date.isoformat(),
                report.sent,
                report.skipped,
                report.deactivated,
                report.failed,
            )
            return report

    return run_broadcast


def create_application(settings: Settings) -> ApplicationResources:
    """Compose adapters and services without starting network activity."""

    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher()
    http_client = httpx.AsyncClient(
        base_url=settings.islom_api_base_url,
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    )
    engine, session_factory = create_database(settings.database_url)
    schedule_service = ScheduleService(IslomApiClient(http_client))
    middleware = ServicesMiddleware(
        session_factory,
        schedule_service,
        timezone=settings.timezone,
    )
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher.include_router(router)

    sender = TelegramMessageSender(bot)
    run_broadcast = _build_broadcast_runner(session_factory, schedule_service, sender)
    scheduler = create_scheduler(
        run_broadcast,
        send_time=settings.daily_send_time,
        timezone=settings.timezone,
    )
    return ApplicationResources(bot, dispatcher, http_client, engine, scheduler)


async def run() -> None:
    """Run long-polling and the daily scheduler until shutdown."""

    configure_logging()
    resources = create_application(Settings())  # type: ignore[call-arg]
    resources.scheduler.start()
    try:
        await resources.dispatcher.start_polling(resources.bot)
    finally:
        await resources.close()


def run_cli() -> None:
    """Synchronous console-script entry point."""

    asyncio.run(run())


if __name__ == "__main__":
    run_cli()
