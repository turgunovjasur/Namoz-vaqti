"""One token may poll from only one process on the same host."""

import subprocess
import sys

import pytest
from pydantic import SecretStr


def test_same_token_is_rejected_in_another_process_and_can_restart(tmp_path):
    from namoz_bot.infrastructure.instance_lock import BotAlreadyRunningError, BotInstanceLock

    token = SecretStr("123456:INSTANCE_TEST_SECRET")
    contender = (
        "import sys; from pathlib import Path; from pydantic import SecretStr; "
        "from namoz_bot.infrastructure.instance_lock import BotInstanceLock, "
        "BotAlreadyRunningError; "
        "lock = BotInstanceLock(SecretStr('123456:INSTANCE_TEST_SECRET'), "
        "directory=Path(sys.argv[1])); "
        "\ntry:\n lock.__enter__()\nexcept BotAlreadyRunningError:\n sys.exit(7)\n"
        "lock.__exit__(None, None, None)"
    )
    with BotInstanceLock(token, directory=tmp_path):
        result = subprocess.run([sys.executable, "-c", contender, str(tmp_path)], check=False)
        assert result.returncode == 7
        with pytest.raises(BotAlreadyRunningError) as rejected:
            with BotInstanceLock(token, directory=tmp_path):
                pass
        assert token.get_secret_value() not in str(rejected.value)
    result = subprocess.run([sys.executable, "-c", contender, str(tmp_path)], check=False)
    assert result.returncode == 0
    assert all("INSTANCE_TEST_SECRET" not in item.name for item in tmp_path.iterdir())


def test_different_bot_tokens_may_run_together(tmp_path):
    from namoz_bot.infrastructure.instance_lock import BotInstanceLock

    with BotInstanceLock(SecretStr("123456:FIRST"), directory=tmp_path):
        with BotInstanceLock(SecretStr("654321:SECOND"), directory=tmp_path):
            pass


def test_exception_releases_lock_for_next_start(tmp_path):
    from namoz_bot.infrastructure.instance_lock import BotInstanceLock

    token = SecretStr("123456:RESTART")
    with pytest.raises(RuntimeError, match="test shutdown"):
        with BotInstanceLock(token, directory=tmp_path):
            raise RuntimeError("test shutdown")
    with BotInstanceLock(token, directory=tmp_path):
        pass
