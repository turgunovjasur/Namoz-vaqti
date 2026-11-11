"""Run migrations, polling and the admin server with local-test credentials."""

import os
import runpy
import signal
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from types import FrameType

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

from namoz_bot.local_processes import startup_lock, stop_existing_services


class LocalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token: SecretStr = Field(validation_alias="TEST_TELEGRAM_BOT_TOKEN", min_length=1)
    database_url: str = Field(validation_alias="TEST_DATABASE_URL", min_length=1)


def run_services(environment: dict[str, str], *, on_started: Callable[[], None]) -> int:
    """Own both child processes and stop the sibling if either exits."""
    children: list[tuple[str, subprocess.Popen[bytes]]] = []
    stop_signal = 0

    def request_stop(signum: int, frame: FrameType | None) -> None:
        nonlocal stop_signal
        stop_signal = signum

    previous_handlers = {
        signum: signal.signal(signum, request_stop) for signum in (signal.SIGINT, signal.SIGTERM)
    }
    try:
        for name, arguments in (
            ("Admin web-server", ["namoz_bot.admin", "--local", "serve"]),
            ("Test bot", ["namoz_bot.local", "--bot"]),
        ):
            if stop_signal:
                return 128 + stop_signal
            child = subprocess.Popen(
                [sys.executable, "-m", *arguments],
                env=environment,
                start_new_session=True,
            )
            children.append((name, child))
        on_started()
        while not stop_signal:
            for name, child in children:
                code = child.poll()
                if code is not None:
                    print(f"{name} to‘xtadi (kod {code}). Ikkala xizmat yopilmoqda.", flush=True)
                    return code if code >= 0 else 128 - code
            time.sleep(0.1)
        return 128 + stop_signal
    finally:
        for _, child in children:
            if child.poll() is None:
                child.terminate()
        for _, child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def run_cli() -> None:
    try:
        settings = LocalSettings()  # type: ignore[call-arg]
    except ValidationError as exc:
        fields = ", ".join(str(error["loc"][0]) for error in exc.errors(include_input=False))
        print(f"Xato: .env ichidagi {fields} qiymatlarini to‘ldiring.", file=sys.stderr)
        raise SystemExit(1) from None

    environment = os.environ.copy()
    environment["TELEGRAM_BOT_TOKEN"] = settings.token.get_secret_value()
    environment["DATABASE_URL"] = settings.database_url
    environment["QORI_ENABLED"] = "true"
    with startup_lock(Path.cwd()) as release:
        try:
            stop_existing_services(Path.cwd())
        except (OSError, subprocess.CalledProcessError, RuntimeError):
            print("Eski lokal jarayonlarni tekshirish/to‘xtatish bajarilmadi.", file=sys.stderr)
            raise SystemExit(1) from None
        print("Lokal test bazasi tayyorlanmoqda...", flush=True)
        try:
            subprocess.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                env=environment,
                check=True,
            )
        except subprocess.CalledProcessError as exc:
            print("Migratsiya bajarilmadi. Test bot ishga tushirilmadi.", file=sys.stderr)
            raise SystemExit(exc.returncode) from None
        print("Test bot va admin web-server ishga tushmoqda. To‘xtatish: Ctrl+C.", flush=True)
        raise SystemExit(run_services(environment, on_started=release))


if __name__ == "__main__":
    if sys.argv[1:] == ["--bot"]:
        runpy.run_module("namoz_bot.main", run_name="__main__")
    else:
        run_cli()
