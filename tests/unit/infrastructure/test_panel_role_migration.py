import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


@pytest.mark.parametrize("existing", [False, True])
def test_panel_migration_preserves_existing_catalog_but_fresh_install_has_only_assistant(existing):
    path = Path(__file__).parents[3] / "alembic/versions/20261104_01_panel_roles.py"
    spec = importlib.util.spec_from_file_location("panel_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE users (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE admin_audit (id INTEGER PRIMARY KEY)")
        connection.exec_driver_sql("CREATE TABLE role_model_settings (role_id TEXT, model_id TEXT)")
        connection.exec_driver_sql(
            "CREATE TABLE agent_roles (id TEXT PRIMARY KEY, name TEXT, "
            "enabled BOOLEAN, system_role BOOLEAN)"
        )
        connection.exec_driver_sql(
            "CREATE TABLE agent_role_skills (role_id TEXT, capability_id TEXT)"
        )
        for id in ("assistant", "manager", "accounting"):
            connection.execute(
                sa.text("INSERT INTO agent_roles VALUES (:id, :name, true, :system)"),
                {"id": id, "name": id, "system": id in {"assistant", "manager"}},
            )
        connection.exec_driver_sql(
            "INSERT INTO agent_role_skills VALUES ('accounting','finance.report')"
        )
        if existing:
            connection.exec_driver_sql("INSERT INTO users VALUES (1)")
            connection.exec_driver_sql(
                "UPDATE agent_roles SET name='Custom accountant' WHERE id='accounting'"
            )
            connection.exec_driver_sql(
                "INSERT INTO role_model_settings VALUES ('accounting','custom-model')"
            )
        with Operations.context(MigrationContext.configure(connection)):
            module.upgrade()
        rows = {r.id: r for r in connection.execute(sa.text("SELECT * FROM agent_roles"))}
        if existing:
            assert rows["accounting"].name == "Custom accountant"
            assert rows["accounting"].enabled and not rows["accounting"].archived
            assert rows["manager"].archived and not rows["manager"].enabled
            assert (
                connection.scalar(sa.text("SELECT model_id FROM role_model_settings"))
                == "custom-model"
            )
        else:
            assert set(rows) == {"assistant"}
            assert connection.scalar(sa.text("SELECT count(*) FROM agent_role_skills")) == 0
    engine.dispose()
