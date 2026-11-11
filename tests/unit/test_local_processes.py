import signal

from namoz_bot import local_processes
from namoz_bot.local_processes import Process, stop_existing_services


def test_restart_kills_stubborn_orphan_without_touching_production(tmp_path, monkeypatch):
    running = {
        100: Process(100, 1, "old", "python -m namoz_bot.local"),
        101: Process(101, 100, "old", "python -m namoz_bot.main"),
        102: Process(102, 1, "old", "python -m namoz_bot.admin --production serve"),
    }
    elapsed = 0.0

    def sleep(seconds):
        nonlocal elapsed
        elapsed += 15

    def kill(pid, sig):
        if pid == 100:
            running.pop(pid, None)
            running[101] = Process(101, 1, "old", "python -m namoz_bot.main")
        elif sig == signal.SIGKILL or pid == 102:
            running.pop(pid, None)

    monkeypatch.setattr(local_processes, "processes", lambda: dict(running))
    monkeypatch.setattr(local_processes, "in_project", lambda pid, project: True)
    monkeypatch.setattr(local_processes.os, "kill", kill)
    monkeypatch.setattr(local_processes.time, "monotonic", lambda: elapsed)
    monkeypatch.setattr(local_processes.time, "sleep", sleep)
    stop_existing_services(tmp_path)
    assert set(running) == {102}
