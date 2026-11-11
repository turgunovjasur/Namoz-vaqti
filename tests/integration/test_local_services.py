"""Exercise the local launcher with real child processes and no external services."""

import json
import os
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def local_project(tmp_path):
    project = tmp_path / "project"
    package = project / "namoz_bot"
    package.mkdir(parents=True)
    (package / "__init__.py").touch()
    shutil.copy2(PROJECT_ROOT / "src/namoz_bot/local.py", package / "local.py")
    shutil.copy2(PROJECT_ROOT / "src/namoz_bot/local_processes.py", package / "local_processes.py")
    for name in ("run_local_bot.sh", "run_bot.sh"):
        shutil.copy2(PROJECT_ROOT / name, project / name)
    python = project / ".venv/bin/python"
    python.parent.mkdir(parents=True)
    python.write_text(f'#!/bin/sh\nexec {shlex.quote(sys.executable)} "$@"\n')
    python.chmod(0o755)
    (project / ".env").write_text(
        "TEST_TELEGRAM_BOT_TOKEN=test-token\nTEST_DATABASE_URL=sqlite:///test.db\n"
    )
    child = """
import json, os, signal, socket, sys, time
from pathlib import Path
name = Path(__file__).stem
if name == 'admin' and os.environ.get('ADMIN_TEST_PORT'):
    listener = socket.socket()
    listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    listener.bind(('127.0.0.1', int(os.environ['ADMIN_TEST_PORT'])))
    listener.listen()
Path(name + '.started').write_text(json.dumps({
    'pid': os.getpid(), 'args': sys.argv[1:],
    'token': os.environ['TELEGRAM_BOT_TOKEN'],
    'database': os.environ['DATABASE_URL'],
    'migrated': Path('migrated').exists(),
}))
def stop(signum, frame):
    Path(name + '.stopped').touch()
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
signal.signal(signal.SIGINT, stop)
if os.environ.get('FAIL_SERVICE') == name:
    time.sleep(0.3)
    sys.exit(7)
time.sleep(15)
"""
    for name in ("main", "admin"):
        (package / f"{name}.py").write_text(child)
    (project / "alembic.py").write_text(
        "import os, sys\nfrom pathlib import Path\n"
        "if os.environ.get('FAIL_MIGRATION'): sys.exit(4)\n"
        "Path('migrated').touch()\n"
    )
    yield project
    # Ensure a failing lifecycle assertion cannot leave test children running.
    for started in project.glob("*.started"):
        try:
            os.kill(json.loads(started.read_text())["pid"], signal.SIGKILL)
        except ProcessLookupError:
            pass


def launch(project, **extra):
    environment = os.environ.copy()
    environment.update(
        TEST_TELEGRAM_BOT_TOKEN="test-token",
        TEST_DATABASE_URL="sqlite:///test.db",
        TELEGRAM_BOT_TOKEN="production-token",
        DATABASE_URL="sqlite:///production.db",
        PYTHONPATH=str(project),
        **extra,
    )
    return subprocess.Popen(
        ["bash", str(project / "run_local_bot.sh")],
        cwd=project.parent,
        env=environment,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        start_new_session=True,
    )


def wait_for_services(project, process):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if all((project / f"{name}.started").exists() for name in ("main", "admin")):
            return
        if process.poll() is not None:
            break
        time.sleep(0.02)
    pytest.fail(
        "Bot and admin must both start"
        + (process.communicate()[1] if process.poll() is not None else "")
    )


@pytest.mark.parametrize("stop_signal", [signal.SIGINT, signal.SIGTERM])
def test_local_script_starts_both_after_migration_and_stops_both(local_project, stop_signal):
    process = launch(local_project)
    try:
        wait_for_services(local_project, process)
        for name in ("main", "admin"):
            data = json.loads((local_project / f"{name}.started").read_text())
            assert data["migrated"] is True
            assert data["token"] == "test-token"
            assert data["database"] == "sqlite:///test.db"
        admin = json.loads((local_project / "admin.started").read_text())
        assert admin["args"] == ["--local", "serve"]
        process.send_signal(stop_signal)
        process.communicate(timeout=5)
        for name in ("main", "admin"):
            assert (local_project / f"{name}.stopped").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


@pytest.mark.parametrize("failed", ["main", "admin"])
def test_service_failure_stops_sibling_and_preserves_exit_code(local_project, failed):
    process = launch(local_project, FAIL_SERVICE=failed)
    try:
        process.communicate(timeout=5)
        assert process.returncode == 7
        sibling = "admin" if failed == "main" else "main"
        assert (local_project / f"{sibling}.stopped").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=5)


def test_failed_migration_starts_neither_service(local_project):
    process = launch(local_project, FAIL_MIGRATION="1")
    process.communicate(timeout=5)
    assert process.returncode == 4
    assert not list(local_project.glob("*.started"))


def test_relaunch_stops_previous_local_services_before_starting_new_ones(local_project):
    first = launch(local_project)
    second = None
    try:
        wait_for_services(local_project, first)
        previous = {
            name: json.loads((local_project / f"{name}.started").read_text())["pid"]
            for name in ("main", "admin")
        }
        second = launch(local_project)
        try:
            first.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail("Restart must stop the previous local supervisor")
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            current = {
                name: json.loads((local_project / f"{name}.started").read_text())["pid"]
                for name in previous
            }
            if all(current[name] != previous[name] for name in previous):
                break
            time.sleep(0.02)
        assert all(current[name] != previous[name] for name in previous)
        assert second.poll() is None
        assert all((local_project / f"{name}.stopped").exists() for name in previous)
    finally:
        for process in (first, second):
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)


def test_relaunch_frees_port_of_standalone_local_admin_and_keeps_other_project(local_project):
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    environment = {
        **os.environ,
        "PYTHONPATH": str(local_project),
        "TELEGRAM_BOT_TOKEN": "test-token",
        "DATABASE_URL": "sqlite:///test.db",
    }
    other = local_project.parent / "other"
    other.mkdir()
    old_admin = subprocess.Popen(
        [sys.executable, "-m", "namoz_bot.admin", "--local", "serve"],
        cwd=local_project,
        env={**environment, "ADMIN_TEST_PORT": str(port)},
    )
    unrelated = subprocess.Popen(
        [sys.executable, "-m", "namoz_bot.admin", "--local", "serve"],
        cwd=other,
        env=environment,
    )
    replacement = None
    try:
        deadline = time.monotonic() + 5
        while not (local_project / "admin.started").exists():
            assert time.monotonic() < deadline
            time.sleep(0.02)
        replacement = launch(local_project, ADMIN_TEST_PORT=str(port))
        old_admin.wait(timeout=5)
        wait_for_services(local_project, replacement)
        assert json.loads((local_project / "admin.started").read_text())["pid"] != old_admin.pid
        assert replacement.poll() is None
        assert unrelated.poll() is None
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass
    finally:
        for process in (old_admin, unrelated, replacement):
            if process is not None and process.poll() is None:
                process.terminate()
                process.communicate(timeout=5)
