"""Shared playlist entry download loop."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_secho
from ..downloader import Downloader
from ..types import DownloadOptions
from .entry_download import download_entry_with_retry
from .history_prompts import prompt_history_decision

if TYPE_CHECKING:
    from ..pause import PauseController


@dataclass
class PlaylistEntriesResult:
    total_files: int = 0
    failed: int = 0


@dataclass
class PreparedEntry:
    opts: DownloadOptions
    entry_url: str
    entry_title: str
    history_video_id: str | None = None


PrepareEntryFn = Callable[[int, dict[str, Any], int], PreparedEntry | None]


def process_playlist_entries(
    entries: list[dict[str, Any]],
    *,
    indices_to_download: set[int] | None,
    existing_map: dict[int, list[Path]],
    dl: Downloader,
    dry_run: bool,
    cfg: Any,
    logger: Any,
    history_available: bool,
    prepare_entry: PrepareEntryFn,
    pause_controller: PauseController | None,
    progress_style: str = "indent",
) -> PlaylistEntriesResult:
    """Iterate playlist entries: skip/resume/history/download/pause."""

    result = PlaylistEntriesResult()
    total = len(entries)

    for idx, entry in enumerate(entries, start=1):
        if indices_to_download is not None and idx not in indices_to_download:
            entry_title_hint = entry.get("title", f"Видео {idx}")
            if idx in existing_map:
                safe_secho(
                    f"[SKIP] {entry_title_hint} — уже скачано",
                    fg=typer.colors.CYAN,
                )
            else:
                safe_secho(
                    f"[SKIP] {entry_title_hint} — пропущено по выбору",
                    fg=typer.colors.YELLOW,
                )
            continue

        if progress_style == "header":
            safe_secho(f"[{idx}/{total}] Обработка...", fg=typer.colors.CYAN)

        prepared = prepare_entry(idx, entry, total)
        if prepared is None:
            continue

        decision = prompt_history_decision(
            history_available=history_available,
            cfg=cfg,
            logger=logger,
            video_id=prepared.history_video_id,
            current_url=prepared.entry_url,
            title_hint=prepared.entry_title,
            default_output_dir=prepared.opts.output_dir,
        )
        if not decision.proceed:
            continue
        if decision.new_output:
            prepared.opts.output_dir = decision.new_output
        if decision.overwrite:
            prepared.opts.overwrite = True

        if progress_style == "numbered":
            loading = f"[{idx}/{total}] ⏳ Загрузка: {prepared.entry_title[:60]}..."
            retry = f"[{idx}/{total}] ↻ Повтор: {prepared.entry_title[:60]}..."
        else:
            loading = f"  ⏳ Загрузка: {prepared.entry_title[:60]}..."
            retry = f"  ↻ Повтор: {prepared.entry_title[:60]}..."

        download_result = download_entry_with_retry(
            dl,
            prepared.opts,
            logger=logger,
            url=prepared.entry_url,
            title=prepared.entry_title,
            loading_message=loading,
            retry_message=retry,
        )

        if download_result.skipped_network:
            result.failed += 1
            continue
        if download_result.failed:
            result.failed += 1
            continue

        files = download_result.files
        if not dry_run:
            result.total_files += len(files)
        safe_secho(
            f"  ✓ [OK] {prepared.entry_title}"
            if (dry_run or files)
            else f"  ⚠ [WARN] {prepared.entry_title} — нет файлов",
            fg=typer.colors.GREEN if (dry_run or files) else typer.colors.YELLOW,
        )
        if not dry_run and not files:
            result.failed += 1

        if pause_controller and pause_controller.between_entries and pause_controller.is_pause_requested():
            pause_controller.wait_if_paused()

    return result
