"""Application logging configuration without secret interpolation."""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging(level: int = logging.INFO, *, log_path: Path | None = None) -> None:
    """Configure concise process logs for container operation."""

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    file_error: OSError | None = None
    if log_path is not None:
        try:
            log_path.parent.mkdir(parents=True, exist_ok=True)
            handlers.append(
                RotatingFileHandler(log_path, maxBytes=5_000_000, backupCount=2, encoding="utf-8")
            )
        except OSError as exc:
            file_error = exc
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
    )
    if file_error is not None:
        logging.getLogger(__name__).warning(
            "file_logging_unavailable path=%s error=%s; using stderr",
            log_path,
            type(file_error).__name__,
        )
