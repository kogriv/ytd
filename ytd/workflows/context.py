"""Контекст и агрегированные итоги команды download (BL-1105).

`DownloadContext` заменяет захват переменных замыканиями: сценарии загрузки
получают всё необходимое явным параметром, поэтому их можно вызывать и
тестировать по отдельности.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from ..types import AppConfig

if TYPE_CHECKING:
    from ..downloader import Downloader
    from ..pause import PauseController
    from .history_prompts import HistoryDecision


@dataclass(slots=True)
class DownloadContext:
    """Неизменяемое окружение одной команды `download`."""

    cfg: AppConfig
    logger: logging.Logger
    dl: Downloader
    dry_run: bool
    interactive: bool
    history_available: bool
    playlist: bool
    playlist_items: str | None
    pause_controller: PauseController | None = None

    @property
    def auto_detect_playlists(self) -> bool:
        return bool(getattr(self.cfg, "auto_detect_playlists", True))

    def output_dir(self, decision: HistoryDecision | None = None) -> Path:
        """Каталог назначения с учётом решения по истории («скачать в другую папку»)."""
        if decision is not None and decision.new_output:
            return decision.new_output
        return self.cfg.output


@dataclass(slots=True)
class DownloadTotals:
    """Итоги загрузки; заменяет `nonlocal failed` и ручные счётчики."""

    total_files: int = 0
    failed: int = 0

    def merge(self, other: DownloadTotals) -> None:
        self.total_files += other.total_files
        self.failed += other.failed

    def exit_code(self) -> int:
        """Код возврата команды: 0 — успех, 1 — полный провал, 2 — частичный."""
        if self.failed == 0 and self.total_files > 0:
            return 0
        if self.failed > 0 and self.total_files > 0:
            return 2
        if self.failed > 0:
            return 1
        return 2
