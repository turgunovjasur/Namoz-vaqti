"""Optional isolated PostgreSQL + Alembic checks."""

import asyncio
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from alembic import command
from namoz_bot.domain.models import DeliveryType, UserSubscription
from namoz_bot.infrastructure.repositories import (
    SqlAlchemyDeliveryRepository,
    SqlAlchemySubscriptionRepository,
)


async def test_postgres_migration_and_concurrent_claim_are_isolated() -> None:
    database_url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if database_url is None:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    database_name = make_url(database_url).database or ""
    if not any(marker in database_name for marker in ("test", "verify")):
        pytest.fail("Refusing to modify a database not explicitly named test/verify")

    schema = f"namoz_verify_{uuid4().hex}"
    admin_engine = create_async_engine(database_url)
    schema_engine = create_async_engine(
        database_url,
        connect_args={"server_settings": {"search_path": schema}},
    )
    try:
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with schema_engine.begin() as connection:
            await connection.run_sync(_upgrade_to_head)

        factory = async_sessionmaker(schema_engine, expire_on_commit=False)
        first_start, second_start = await asyncio.gather(
            SqlAlchemySubscriptionRepository(factory).upsert_start(
                UserSubscription(991001, 991001, "Toshkent", True)
            ),
            SqlAlchemySubscriptionRepository(factory).upsert_start(
                UserSubscription(991001, 991002, "Toshkent", True)
            ),
        )
        assert sum(created for _, created in (first_start, second_start)) == 1
        user = await SqlAlchemySubscriptionRepository(factory).get_by_telegram_user_id(991001)
        assert user is not None
        assert user.id is not None

        first, second = await asyncio.gather(
            SqlAlchemyDeliveryRepository(factory).claim_batch(
                [user.id], date(2026, 8, 27), DeliveryType.DAILY
            ),
            SqlAlchemyDeliveryRepository(factory).claim_batch(
                [user.id], date(2026, 8, 27), DeliveryType.DAILY
            ),
        )

        assert sum(user.id in claimed for claimed in (first, second)) == 1
    finally:
        await schema_engine.dispose()
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin_engine.dispose()


def _upgrade_to_head(connection: Connection) -> None:
    project_root = Path(__file__).resolve().parents[2]
    config = Config(project_root / "alembic.ini")
    config.set_main_option("script_location", str(project_root / "alembic"))
    config.attributes["connection"] = connection
    command.upgrade(config, "head")
