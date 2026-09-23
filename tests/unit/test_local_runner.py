import os
import subprocess

import pytest

from namoz_bot.local import LocalSettings, run_cli


def test_local_settings_use_only_test_credentials(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "TELEGRAM_BOT_TOKEN=production-token\n"
        "DATABASE_URL=postgresql+asyncpg:///production\n"
        "TEST_TELEGRAM_BOT_TOKEN=test-token\n"
        "TEST_DATABASE_URL=postgresql+asyncpg:///namoz_test\n"
    )
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "shell-production-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg:///shell-production")
    settings = LocalSettings()
    assert settings.token.get_secret_value() == "test-token"
    assert settings.database_url == "postgresql+asyncpg:///namoz_test"


@pytest.mark.parametrize("test_values", ["", "TEST_TELEGRAM_BOT_TOKEN=\nTEST_DATABASE_URL=\n"])
def test_missing_test_settings_stop_without_production_fallback(
    tmp_path, monkeypatch, capsys, test_values
):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("TELEGRAM_BOT_TOKEN=secret-production\n" + test_values)
    monkeypatch.delenv("TEST_TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit) as error:
        run_cli()
    assert error.value.code == 1
    output = capsys.readouterr().err
    assert "TEST_TELEGRAM_BOT_TOKEN" in output
    assert "secret-production" not in output


def test_local_runner_migrates_and_polls_with_same_test_environment(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg:///namoz_test")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "production-token")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg:///production")
    captured = []

    def migrate(command, *, env, check):
        captured.append((command, env))
        assert check

    def execute(executable, args, env):
        captured.append((args, env))

    monkeypatch.setattr(subprocess, "run", migrate)
    monkeypatch.setattr(os, "execvpe", execute)
    run_cli()
    assert captured[0][0][1:] == ["-m", "alembic", "upgrade", "head"]
    assert captured[1][0][1:] == ["-m", "namoz_bot.main"]
    for _, env in captured:
        assert env["TELEGRAM_BOT_TOKEN"] == "test-token"
        assert env["DATABASE_URL"] == "postgresql+asyncpg:///namoz_test"


def test_migration_failure_prevents_polling(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TEST_TELEGRAM_BOT_TOKEN", "test-token")
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql+asyncpg:///namoz_test")

    def fail(command, **kwargs):
        raise subprocess.CalledProcessError(2, command)

    def unexpected_poll(*args):
        pytest.fail("Must not start polling after failed migration")

    monkeypatch.setattr(subprocess, "run", fail)
    monkeypatch.setattr(os, "execvpe", unexpected_poll)
    with pytest.raises(SystemExit) as error:
        run_cli()
    assert error.value.code == 2
