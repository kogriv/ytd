from __future__ import annotations

import logging
from pathlib import Path

from ytd.logging import setup_logging


def test_setup_logging_creates_file_and_logs(tmp_path: Path):
    log_file = tmp_path / "logs" / "ytd.log"

    logger = setup_logging(level="DEBUG", log_file=log_file)
    logger.info("test message")

    assert log_file.exists()
    content = log_file.read_text(encoding="utf-8")
    assert "test message" in content
    assert "INFO" in content


def test_setup_logging_idempotent(tmp_path: Path):
    log_file = tmp_path / "logs" / "ytd.log"

    logger1 = setup_logging(level="INFO", log_file=log_file)
    handlers_count_1 = len(logger1.handlers)

    logger2 = setup_logging(level="INFO", log_file=log_file)
    handlers_count_2 = len(logger2.handlers)

    assert handlers_count_1 == handlers_count_2 == 2  # console + file

    logger2.info("once")
    text = log_file.read_text(encoding="utf-8")
    # Проверяем, что нет дублирования сообщений из-за дублированных хендлеров
    assert text.count("once") == 1


def test_setup_logging_numeric_level(tmp_path: Path):
    log_file = tmp_path / "logs" / "ytd.log"
    logger = setup_logging(level=logging.WARNING, log_file=log_file)
    logger.info("invisible")
    logger.warning("visible")

    text = log_file.read_text(encoding="utf-8")
    assert "invisible" not in text
    assert "visible" in text
