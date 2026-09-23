"""Run migrations and polling using explicit local-test credentials only."""

import os
import subprocess
import sys

from pydantic import Field, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class LocalSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    token: SecretStr = Field(validation_alias="TEST_TELEGRAM_BOT_TOKEN", min_length=1)
    database_url: str = Field(validation_alias="TEST_DATABASE_URL", min_length=1)


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
    print("Test bot ishga tushmoqda. To‘xtatish: Ctrl+C.", flush=True)
    os.execvpe(sys.executable, [sys.executable, "-m", "namoz_bot.main"], environment)


if __name__ == "__main__":
    run_cli()
