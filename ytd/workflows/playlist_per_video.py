"""Плейлист, режим 2: настройка каждого видео отдельно (BL-1105, BL-202)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_echo, safe_secho
from .context import DownloadTotals
from .download_one import build_options
from .info_fetch import fetch_info
from .playlist_entries import PreparedEntry, process_playlist_entries
from .playlist_resume import existing_files_map, resolve_download_indices
from .single_video import setup_from_info

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision


def run_mode(
    ctx: DownloadContext,
    url: str,
    decision: HistoryDecision,
    info: dict[str, Any],
    entries: list[dict[str, Any]],
) -> DownloadTotals:
    """Пройти по элементам плейлиста, настраивая каждый отдельным диалогом."""

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

    totals = DownloadTotals()
    output_dir = ctx.output_dir(decision)

    safe_secho("\n→ Режим: Настройка каждого видео отдельно", fg=typer.colors.GREEN)

    indices_to_download, skip_playlist = resolve_download_indices(ctx, output_dir, entries)
    if skip_playlist:
        return totals

    existing_map = existing_files_map(output_dir, entries)

    safe_echo("\n" + "═" * 60)
    safe_secho(
        f"▶ Настройка и загрузка плейлиста ({len(entries)} видео)...",
        fg=typer.colors.GREEN,
        bold=True,
    )
    safe_echo("═" * 60 + "\n")

    def prepare_entry(idx: int, entry: dict[str, Any], total: int) -> PreparedEntry | None:
        entry_title_hint = entry.get("title", f"Видео {idx}")
        entry_url = ia.get_entry_url(entry)
        if not entry_url:
            safe_secho(
                f"[WARN] Пропуск: элемент #{idx} ({entry_title_hint}) не содержит URL",
                fg=typer.colors.YELLOW,
            )
            safe_echo("      yt-dlp не вернул поля original_url/webpage_url/url.")
            safe_echo("      Проверьте доступ к источнику (например, VK) или обновите yt-dlp.")
            return None

        entry_info = fetch_info(
            ctx,
            entry_url,
            title_hint=entry_title_hint,
            allow_skip=True,
            skip_message=f"[SKIP] {entry_title_hint} — пропущено из-за сетевой ошибки",
        )
        if entry_info is None:
            totals.failed += 1
            return None

        setup = setup_from_info(ctx, entry_info, decision)
        return PreparedEntry(
            opts=build_options(ctx, entry_url, decision, setup=setup),
            entry_url=entry_url,
            entry_title=entry_info.get("title", entry_title_hint),
            history_video_id=str(entry.get("id")) if entry.get("id") else None,
        )

    result = process_playlist_entries(
        entries,
        indices_to_download=indices_to_download,
        existing_map=existing_map,
        dl=ctx.dl,
        dry_run=ctx.dry_run,
        cfg=ctx.cfg,
        logger=ctx.logger,
        history_available=ctx.history_available,
        prepare_entry=prepare_entry,
        pause_controller=ctx.pause_controller,
        progress_style="header",
    )
    totals.total_files += result.total_files
    totals.failed += result.failed
    return totals
