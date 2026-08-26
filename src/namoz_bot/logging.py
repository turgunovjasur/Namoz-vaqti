"""Application logging configuration without secret interpolation."""

import logging


def configure_logging(level: int = logging.INFO) -> None:
    """Configure concise process logs for container operation."""

    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
