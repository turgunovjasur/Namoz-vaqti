"""Replace this checkout's local services without touching unrelated processes."""

import fcntl
import os
import signal
import subprocess
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Process:
    pid: int
    parent: int = field(compare=False)  # Children may be reparented during shutdown.
    started: str
    command: str

    @property
    def arguments(self) -> list[str]:
        return self.command.partition(" -m ")[2].split()


def processes() -> dict[int, Process]:
    result = subprocess.run(
        ["ps", "-axo", "uid=,pid=,ppid=,stat=,lstart=,args="],
        capture_output=True,
        text=True,
        check=True,
    )
    found = {}
    for line in result.stdout.splitlines():
        fields = line.split(maxsplit=9)
        if len(fields) != 10 or int(fields[0]) != os.getuid() or "Z" in fields[3]:
            continue
        pid, parent = int(fields[1]), int(fields[2])
        found[pid] = Process(pid, parent, " ".join(fields[4:9]), fields[9])
    return found


def in_project(pid: int, project: Path) -> bool:
    result = subprocess.run(
        ["lsof", "-a", "-p", str(pid), "-d", "cwd", "-Fn"],
        capture_output=True,
        text=True,
        check=False,
    )
    return any(
        line.startswith("n") and Path(line[1:]).resolve() == project
        for line in result.stdout.splitlines()
    )


def stop_existing_services(project: Path) -> None:
    snapshot = processes()
    candidates = {
        pid: process
        for pid, process in snapshot.items()
        if pid != os.getpid()
        and process.arguments
        and process.arguments[0] in {"namoz_bot.local", "namoz_bot.admin", "namoz_bot.main"}
        and in_project(pid, project)
    }
    # Waiting launchers have no children yet. Only replace a running supervisor.
    supervisors = {
        pid
        for pid, process in candidates.items()
        if process.arguments == ["namoz_bot.local"]
        and any(child.parent == pid for child in candidates.values())
    }
    targets = {
        pid: process
        for pid, process in candidates.items()
        if pid in supervisors
        or process.parent in supervisors
        or process.arguments == ["namoz_bot.local", "--bot"]
        or (
            process.arguments[0] == "namoz_bot.admin"
            and "--local" in process.arguments
            and "link" not in process.arguments
        )
    }
    if not targets:
        return
    print(f"Oldingi lokal jarayonlar to‘xtatilmoqda ({len(targets)} ta)...", flush=True)
    for sig, timeout in ((signal.SIGTERM, 12), (signal.SIGKILL, 3)):
        current = processes()
        for pid, process in targets.items():
            if current.get(pid) == process:
                try:
                    os.kill(pid, sig)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            current = processes()
            targets = {pid: p for pid, p in targets.items() if current.get(pid) == p}
            if not targets:
                return
            time.sleep(0.1)
    raise RuntimeError("Oldingi lokal jarayonlarni to‘xtatib bo‘lmadi.")


@contextmanager
def startup_lock(project: Path) -> Iterator[Callable[[], None]]:
    """Serialize replacement, migrations and spawning, not service lifetime."""
    with (project / ".local-run.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)

        def release() -> None:
            fcntl.flock(lock, fcntl.LOCK_UN)

        try:
            yield release
        finally:
            release()
