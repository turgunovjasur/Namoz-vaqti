import os
from uuid import uuid4

import pytest
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_reminder_repository import migrate


async def test_agent_migration_roundtrip_preserves_existing_records():
    url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    assert "test" in (make_url(url).database or "")
    schema = f"agent_migration_{uuid4().hex}"
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as connection:
            await connection.run_sync(lambda conn: migrate(conn, "20261012_01"))
            assert "agent_sessions" not in await connection.run_sync(
                lambda conn: inspect(conn).get_table_names()
            )
            user = await connection.scalar(
                text(
                    "INSERT INTO users (telegram_user_id,chat_id,region_code,is_active) "
                    "VALUES (7,7,'Toshkent',true) RETURNING id"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO finance_entries "
                    "(user_id,kind,amount,category,description,period,source_key) "
                    "VALUES (:user,'income',120000,'boshqa_kirim','Old data','2026-10-01','old')"
                ),
                {"user": user},
            )
            await connection.execute(
                text(
                    "INSERT INTO reminders (user_id,chat_id,text,at,kind,status,creation_token) "
                    "VALUES (:user,7,'Old reminder','09:00','daily','active','old')"
                ),
                {"user": user},
            )
            await connection.run_sync(migrate)
            assert "agent_receipts" in await connection.run_sync(
                lambda conn: inspect(conn).get_table_names()
            )
            await connection.execute(
                text("INSERT INTO agent_sessions (user_id,revision) VALUES (:user,0)"),
                {"user": user},
            )
            await connection.execute(
                text(
                    "INSERT INTO agent_receipts (user_id,request_id,result,created_at) "
                    "VALUES (:user,'request','{}',now())"
                ),
                {"user": user},
            )
            await connection.run_sync(lambda conn: migrate(conn, "20261012_01", downgrade=True))
            assert "agent_sessions" not in await connection.run_sync(
                lambda conn: inspect(conn).get_table_names()
            )
            assert await connection.scalar(text("SELECT amount FROM finance_entries")) == 120000
            assert await connection.scalar(text("SELECT text FROM reminders")) == "Old reminder"
    finally:
        await engine.dispose()
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()
