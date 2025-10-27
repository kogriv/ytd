from __future__ import annotations

from pathlib import Path
from typing import Optional, Union
import logging
from logging.handlers import RotatingFileHandler

from .utils import ensure_dir


def _coerce_level(level: Union[str, int]) -> int:
    if isinstance(level, int):
        return level
    try:
        return getattr(logging, str(level).upper())
    except AttributeError:
        return logging.INFO


def setup_logging(level: Union[str, int] = "INFO", log_file: Optional[Path] = Path("logs/ytd.log")) -> logging.Logger:
    """Настроить логгер приложения (консоль + файл с ротацией по размеру).

    Особенности:
    - idempotent: при повторных вызовах хендлеры пересоздаются, дубликаты не накапливаются
    - файл логов создаётся при необходимости, каталог — автоматически
    - кодировка UTF-8
    """
    logger = logging.getLogger("ytd")
    logger.setLevel(_coerce_level(level))
    logger.propagate = False

    # Очистить предыдущие хендлеры, чтобы избежать дубликатов
    for h in list(logger.handlers):
        try:
            h.close()
        except Exception:
            pass
        logger.removeHandler(h)

    # Форматтер
    fmt = logging.Formatter(fmt="%(asctime)s | %(levelname)s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Консоль: только INFO и выше (без DEBUG), чтобы не засорять вывод прогресс-бара
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)  # Всегда INFO для консоли, DEBUG только в файл
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # Файл (ротируемый)
    if log_file is not None:
        log_path = Path(log_file)
        ensure_dir(log_path.parent)
        fh = RotatingFileHandler(log_path, maxBytes=1_000_000, backupCount=5, encoding="utf-8")
        fh.setLevel(_coerce_level(level))
        fh.setFormatter(fmt)
        logger.addHandler(fh)

    # Короткий тест-сообщение при DEBUG можно оставить на уровне использования
    return logger
