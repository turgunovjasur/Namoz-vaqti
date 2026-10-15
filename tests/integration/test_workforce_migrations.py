import os
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_reminder_repository import migrate


async def test_profile_upgrade_backfills_only_existing_users_and_frozen_capabilities():
    url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    assert "test" in url
    schema = f"profiles_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as conn:
            await conn.run_sync(lambda c: migrate(c, "20261013_01"))
            old = await conn.scalar(
                text(
                    "INSERT INTO users (telegram_user_id,chat_id,region_code,is_active) "
                    "VALUES (7,7,'Toshkent',true) RETURNING id"
                )
            )
            await conn.run_sync(migrate)
            assert "profiles" in await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert (
                await conn.scalar(
                    text("SELECT count(*) FROM user_role_assignments WHERE user_id=:id"),
                    {"id": old},
                )
                == 5
            )
            assert (
                await conn.scalar(
                    text(
                        "SELECT count(*) FROM user_role_capabilities "
                        "WHERE capability_id='finance.correct'"
                    )
                )
                == 0
            )
            await conn.execute(
                text(
                    "INSERT INTO users (telegram_user_id,chat_id,region_code,is_active) "
                    "VALUES (8,8,'Toshkent',true)"
                )
            )
            assert await conn.scalar(text("SELECT count(*) FROM user_role_assignments")) == 5
            assert (
                await conn.scalar(
                    text("SELECT profile_type FROM profiles WHERE user_id=:id"), {"id": old}
                )
                == "user"
            )
            await conn.run_sync(lambda c: migrate(c, "20261013_01", downgrade=True))
            assert "profiles" not in await conn.run_sync(lambda c: inspect(c).get_table_names())
            assert await conn.scalar(text("SELECT count(*) FROM users")) == 2
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()
