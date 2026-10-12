import logging
from pathlib import Path

from namoz_bot.logging import configure_logging


def test_unwritable_log_directory_keeps_stderr_logging(monkeypatch, tmp_path, caplog):
    captured = {}

    def denied(*args, **kwargs):
        raise PermissionError("read-only directory")

    monkeypatch.setattr(Path, "mkdir", denied)
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: captured.update(kwargs))
    configure_logging(log_path=tmp_path / "logs" / "bot.log")
    assert len(captured["handlers"]) == 1
    assert isinstance(captured["handlers"][0], logging.StreamHandler)
    assert "file_logging_unavailable" in caplog.text


def test_unwritable_log_file_keeps_stderr_logging(monkeypatch, tmp_path):
    captured = {}

    def denied(*args, **kwargs):
        raise PermissionError("read-only file")

    monkeypatch.setattr("namoz_bot.logging.RotatingFileHandler", denied)
    monkeypatch.setattr(logging, "basicConfig", lambda **kwargs: captured.update(kwargs))
    configure_logging(log_path=tmp_path / "bot.log")
    assert len(captured["handlers"]) == 1
