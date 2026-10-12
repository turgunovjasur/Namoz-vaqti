"""Hold a per-token OS lock for the polling process lifetime."""

import fcntl
import hashlib
import os
import tempfile
from pathlib import Path
from types import TracebackType

from pydantic import SecretStr


class BotAlreadyRunningError(RuntimeError):
    """Another process already owns this bot token on this host."""


class BotInstanceLock:
    def __init__(self, token: SecretStr, *, directory: Path | None = None) -> None:
        digest = hashlib.sha256(token.get_secret_value().encode()).hexdigest()[:24]
        self._path = (directory or Path(tempfile.gettempdir())) / (
            f"namoz-bot-{os.getuid()}-{digest}.lock"
        )
        self._fd: int | None = None

    def __enter__(self) -> "BotInstanceLock":
        if self._fd is not None:
            raise BotAlreadyRunningError("Bu bot shu kompyuterda allaqachon ishlayapti.")
        fd = os.open(self._path, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(fd, 0)
            os.write(fd, str(os.getpid()).encode())
        except BlockingIOError:
            os.close(fd)
            raise BotAlreadyRunningError(
                "Bu bot shu kompyuterda allaqachon ishlayapti. "
                "Ikkinchi nusxa ochilmadi. Avval ishlayotgan botni to‘xtating."
            ) from None
        except OSError:
            os.close(fd)
            raise
        self._fd = fd
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._fd is not None:
            os.close(self._fd)
            self._fd = None
        # Never unlink: another starter may already have opened the same inode.
