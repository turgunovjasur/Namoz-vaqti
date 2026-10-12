"""Application composition root and polling lifecycle."""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import SimpleEventIsolation
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncEngine

from namoz_bot.application.accounting import LedgerService
from namoz_bot.application.daily_schedule import (
    DailyScheduleSettingsService,
    PersonalDailyBroadcastService,
)
from namoz_bot.application.religious_reminders import (
    PersonalReligiousBroadcastService,
    ReligiousIntervalService,
    ReligiousReminderService,
)
from namoz_bot.application.reminders import ReminderService
from namoz_bot.application.schedules import ScheduleService
from namoz_bot.application.voice_reminders import VoiceReminderService
from namoz_bot.config import Settings
from namoz_bot.infrastructure.accounting import SqlAlchemyLedgerRepository
from namoz_bot.infrastructure.daily_schedule import SqlAlchemyDailyScheduleRepository
from namoz_bot.infrastructure.db import create_database
from namoz_bot.infrastructure.gemini import GeminiReminderClient
from namoz_bot.infrastructure.gemini_accounting import GeminiAccountingClient
from namoz_bot.infrastructure.gemini_voice import GeminiVoiceReminderClient
from namoz_bot.infrastructure.instance_lock import BotAlreadyRunningError, BotInstanceLock
from namoz_bot.infrastructure.namoz_vaqti_api import NamozVaqtiApiClient
from namoz_bot.infrastructure.religious_intervals import SqlAlchemyReligiousIntervalRepository
from namoz_bot.infrastructure.reminders import SqlAlchemyReminderRepository
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)
from namoz_bot.infrastructure.telegram import TelegramMessageSender, TelegramRateLimiter
from namoz_bot.logging import configure_logging
from namoz_bot.presentation.accounting import build_accounting_router
from namoz_bot.presentation.handlers import build_prayer_router
from namoz_bot.presentation.middleware import ErrorHandlingMiddleware, ServicesMiddleware
from namoz_bot.presentation.religious_settings import build_religious_settings_router
from namoz_bot.presentation.reminders import build_reminder_router, build_voice_reminder_router
from namoz_bot.presentation.settings import build_settings_router

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ApplicationResources:
    """All process-owned resources with deterministic shutdown."""

    bot: Bot
    dispatcher: Dispatcher
    http_client: httpx.AsyncClient
    db_engine: AsyncEngine
    scheduler: AsyncIOScheduler
    religious_intervals: ReligiousIntervalService | None = None
    daily_settings: DailyScheduleSettingsService | None = None

    async def close(self) -> None:
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
        await self.bot.session.close()
        await self.http_client.aclose()
        await self.db_engine.dispose()


def create_application(settings: Settings) -> ApplicationResources:
    """Compose adapters and services without starting network activity."""

    bot = Bot(token=settings.telegram_bot_token.get_secret_value())
    dispatcher = Dispatcher(events_isolation=SimpleEventIsolation())
    http_client = httpx.AsyncClient(
        base_url=settings.prayer_api_base_url,
        timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
    )
    voice_reminders = None
    if settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip():
        voice_reminders = VoiceReminderService(
            GeminiVoiceReminderClient(
                http_client,
                api_key=settings.gemini_api_key,
                model=settings.gemini_voice_model,
            ),
            cooldown_seconds=settings.voice_reminder_cooldown_seconds,
        )
    dispatcher["voice_reminders"] = voice_reminders
    engine, session_factory = create_database(settings.database_url)
    accounting_extractor = None
    if settings.gemini_api_key and settings.gemini_api_key.get_secret_value().strip():
        accounting_extractor = GeminiAccountingClient(
            http_client, api_key=settings.gemini_api_key, model=settings.gemini_voice_model
        )
    dispatcher["ledger_service"] = LedgerService(
        SqlAlchemyLedgerRepository(session_factory), accounting_extractor
    )
    schedule_service = ScheduleService(NamozVaqtiApiClient(http_client))
    religious_provider = None
    religious_reminders = None
    religious_intervals = None
    interval_repository = SqlAlchemyReligiousIntervalRepository(session_factory)
    daily_repository = SqlAlchemyDailyScheduleRepository(session_factory)
    daily_settings = DailyScheduleSettingsService(
        daily_repository, default_time=settings.daily_send_time
    )
    if (
        settings.gemini_api_key
        and settings.gemini_api_key.get_secret_value().strip()
        and settings.gemini_book_corpus_path is not None
    ):
        religious_provider = GeminiReminderClient(
            http_client,
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            corpus_path=settings.gemini_book_corpus_path,
        )
        religious_reminders = ReligiousReminderService(
            religious_provider,
            cooldown_seconds=settings.gemini_button_cooldown_seconds,
        )
        religious_intervals = ReligiousIntervalService(
            interval_repository, default_hours=settings.gemini_reminder_interval_hours
        )
    middleware = ServicesMiddleware(
        session_factory,
        schedule_service,
        timezone=settings.timezone,
        religious_reminders=religious_reminders,
        religious_intervals=religious_intervals,
        daily_settings=daily_settings,
    )
    dispatcher.message.outer_middleware(ErrorHandlingMiddleware())
    dispatcher.message.outer_middleware(middleware)
    dispatcher.callback_query.outer_middleware(ErrorHandlingMiddleware())
    dispatcher.callback_query.outer_middleware(middleware)
    dispatcher.include_router(build_accounting_router())
    dispatcher.include_router(build_voice_reminder_router())
    dispatcher.include_router(build_prayer_router())
    dispatcher.include_router(build_settings_router())
    dispatcher.include_router(build_religious_settings_router())
    dispatcher.include_router(build_reminder_router())

    sender = TelegramMessageSender(
        bot,
        rate_limiter=TelegramRateLimiter(messages_per_second=settings.telegram_messages_per_second),
    )
    scheduler = AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
    daily_broadcast = PersonalDailyBroadcastService(
        daily_repository,
        SqlAlchemySubscriptionRepository(session_factory),
        SqlAlchemyDeliveryRepository(session_factory),
        schedule_service,
        sender,
        default_time=settings.daily_send_time,
        batch_size=settings.broadcast_batch_size,
        max_concurrency=settings.telegram_max_concurrency,
    )
    scheduler.add_job(
        daily_broadcast.send,
        trigger="cron",
        second=0,
        id="daily-prayer-schedule",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
        misfire_grace_time=None,
    )
    if religious_provider is not None:
        religious_broadcast = PersonalReligiousBroadcastService(
            interval_repository,
            SqlAlchemySubscriptionRepository(session_factory),
            religious_provider,
            sender,
            batch_size=settings.broadcast_batch_size,
            max_concurrency=settings.telegram_max_concurrency,
            default_hours=settings.gemini_reminder_interval_hours,
        )
        scheduler.add_job(
            religious_broadcast.send,
            trigger="cron",
            minute=0,
            second=0,
            id="automatic-religious-reminders",
            replace_existing=True,
            coalesce=True,
            max_instances=1,
            misfire_grace_time=None,
        )
        logger.info(
            "religious_reminders_configured model=%s default_interval_hours=%s cooldown_seconds=%d",
            settings.gemini_model,
            settings.gemini_reminder_interval_hours,
            settings.gemini_button_cooldown_seconds,
        )
    reminders = ReminderService(SqlAlchemyReminderRepository(session_factory))

    async def send_reminders() -> None:
        await reminders.send_due(sender)

    scheduler.add_job(
        send_reminders,
        trigger="interval",
        seconds=15,
        id="personal-reminders",
        replace_existing=True,
        coalesce=True,
        max_instances=1,
    )
    return ApplicationResources(
        bot, dispatcher, http_client, engine, scheduler, religious_intervals, daily_settings
    )


async def run() -> None:
    """Run long-polling and the daily scheduler until shutdown."""

    configure_logging(log_path=Path("logs/namoz_bot.log"))
    settings = Settings()  # type: ignore[call-arg]
    try:
        with BotInstanceLock(settings.telegram_bot_token):
            await _run_polling(settings)
    except BotAlreadyRunningError as exc:
        logger.error("%s", exc)
        raise SystemExit(1) from None


async def _run_polling(settings: Settings) -> None:
    resources = create_application(settings)
    try:
        if resources.daily_settings is not None:
            await resources.daily_settings.initialize()
        if resources.religious_intervals is not None:
            await resources.religious_intervals.initialize()
        resources.scheduler.start()
        job = resources.scheduler.get_job("automatic-religious-reminders")
        if job is not None:
            logger.info(
                "religious_reminders_next_check next_check=%s", job.next_run_time.isoformat()
            )
        await resources.dispatcher.start_polling(resources.bot)
    finally:
        await resources.close()


def run_cli() -> None:
    """Synchronous console-script entry point."""

    asyncio.run(run())


if __name__ == "__main__":
    run_cli()
