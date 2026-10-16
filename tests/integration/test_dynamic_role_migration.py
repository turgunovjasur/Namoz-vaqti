import os
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from tests.integration.test_reminder_repository import migrate


async def test_catalog_upgrade_preserves_existing_grants_models_and_role_ids():
    url = os.getenv("NAMOZ_TEST_DATABASE_URL")
    if not url:
        pytest.skip("NAMOZ_TEST_DATABASE_URL is not configured")
    assert "test" in url
    schema = "dynamic_roles_" + uuid4().hex
    admin = create_async_engine(url)
    engine = create_async_engine(url, connect_args={"server_settings": {"search_path": schema}})
    try:
        async with admin.begin() as c:
            await c.execute(text(f'CREATE SCHEMA "{schema}"'))
        async with engine.begin() as c:
            await c.run_sync(lambda conn: migrate(conn, "20261015_04"))
            await c.execute(
                text(
                    "INSERT INTO users (id,telegram_user_id,chat_id,region_code,is_active) "
                    "VALUES(99,7,7,'Toshkent',true)"
                )
            )
            await c.execute(
                text(
                    "INSERT INTO user_role_assignments(user_id,role_id,enabled,revision) "
                    "VALUES(99,'accounting',true,4)"
                )
            )
            await c.execute(
                text(
                    "INSERT INTO user_role_capabilities(user_id,role_id,capability_id) "
                    "VALUES(99,'accounting','finance.report')"
                )
            )
            await c.execute(
                text(
                    "INSERT INTO role_model_settings(role_id,model_id,version) "
                    "VALUES('accounting','existing-model',3)"
                )
            )
            await c.run_sync(migrate)
            assert await c.scalar(text("SELECT count(*) FROM agent_roles")) == 7
            assert await c.scalar(text("SELECT count(*) FROM user_role_capabilities")) == 1
            assert (
                await c.scalar(text("SELECT revision FROM user_role_assignments WHERE user_id=99"))
                == 4
            )
            assert (
                await c.scalar(
                    text("SELECT model_id FROM role_model_settings WHERE role_id='accounting'")
                )
                == "existing-model"
            )
            assert (
                await c.scalar(text("SELECT enabled FROM agent_roles WHERE id='manager'")) is False
            )
            await c.run_sync(lambda conn: migrate(conn, "20261015_04", downgrade=True))
            assert await c.scalar(text("SELECT count(*) FROM user_role_capabilities")) == 1
    finally:
        await engine.dispose()
        async with admin.begin() as c:
            await c.execute(text(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE'))
        await admin.dispose()
