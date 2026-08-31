"""Плейлист, режим 1: единые настройки для всех видео (BL-1105)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_echo, safe_secho
from ..utils import extract_quality_suffix, find_best_quality_match, sanitize_filename
from .context import DownloadTotals
from .download_one import EntrySetup, build_options
from .info_fetch import fetch_info
from .playlist_entries import PreparedEntry, process_playlist_entries
from .playlist_resume import existing_files_map, resolve_download_indices

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision


def _analyze_first_entry(
    ctx: DownloadContext,
    entries: list[dict[str, Any]],
    totals: DownloadTotals,
) -> dict[str, Any]:
    """Взять форматы первого элемента как базу для общего меню качества."""

    from .. import interactive as ia

    first_entry = entries[0]
    first_entry_title = first_entry.get("title", "Первое видео")
    first_url = ia.get_entry_url(first_entry)
    if not first_url:
        safe_secho(
            f"[WARN] Не удалось определить URL первого видео плейлиста ({first_entry_title})",
            fg=typer.colors.YELLOW,
        )
        safe_echo(
            "      Поля original_url/webpage_url/url отсутствуют. Анализ форматов может быть неполным.",
        )
        return {}

    first_info = fetch_info(
        ctx,
        first_url,
        title_hint="Первое видео плейлиста",
        allow_skip=True,
        skip_message="[SKIP] Пропуск анализа первого видео плейлиста из-за сетевой ошибки",
    )
    if first_info is None:
        totals.failed += 1
        return {}
    return first_info


def run_mode(
    ctx: DownloadContext,
    url: str,
    decision: HistoryDecision,
    info: dict[str, Any],
    entries: list[dict[str, Any]],
) -> DownloadTotals:
    """Собрать общие настройки в диалоге и скачать плейлист поштучно."""

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

    totals = DownloadTotals()
    output_dir = ctx.output_dir(decision)

    safe_secho("\n→ Режим: Единые настройки для всех видео", fg=typer.colors.GREEN)
    safe_secho("\n⏳ Анализ доступных форматов...", fg=typer.colors.CYAN)

    first_info = _analyze_first_entry(ctx, entries, totals)

    height_to_ext, available_heights = ia.collect_available_heights(first_info.get("formats") or [])
    quality_options = ia.build_quality_options(height_to_ext, available_heights)
    chosen_label, chosen_format, target_height = ia.show_quality_menu(quality_options)

    default_suffix = extract_quality_suffix(chosen_format, chosen_label)
    quality_suffix = ia.configure_filename_suffix(default_suffix)
    use_numbering, prefix_template = ia.configure_playlist_numbering()
    strategy = ia.configure_quality_fallback()

    overwrite_all = ia.ask_overwrite_all() or decision.overwrite

    example_title = sanitize_filename(first_info.get("title") or entries[0].get("title", "Видео"))
    example_id = first_info.get("id") or entries[0].get("id", "ID")

    confirmed = ia.show_unified_settings_summary(
        chosen_label,
        quality_suffix,
        prefix_template if use_numbering else "",
        strategy,
        example_title,
        example_id,
    )
    if not confirmed:
        safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
        return totals

    indices_to_download, skip_playlist = resolve_download_indices(ctx, output_dir, entries)
    if skip_playlist:
        return totals

    existing_map = existing_files_map(output_dir, entries)

    safe_echo("\n" + "═" * 60)
    safe_secho(
        f"▶ Начинаем загрузку плейлиста ({len(entries)} видео)...",
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
            skip_message=f"[SKIP] {entry_title_hint} — пропущено из-за сетевой ошибки при анализе",
        )
        if entry_info is None:
            totals.failed += 1
            return None

        setup = EntrySetup(
            chosen_format=_format_for_entry(
                entry_info.get("formats") or [],
                chosen_format,
                target_height,
                strategy,
            ),
            file_prefix=_prefix_for_entry(idx, use_numbering, prefix_template),
            quality_suffix=quality_suffix,
            overwrite=overwrite_all,
        )
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


def _format_for_entry(
    entry_formats: list[dict[str, Any]],
    chosen_format: str,
    target_height: int | None,
    strategy: str,
) -> str:
    """Подобрать формат конкретного видео под выбранную высоту и стратегию fallback."""

    if not (isinstance(target_height, int) and target_height >= 0):
        return chosen_format

    from .. import interactive as ia

    height_to_ext, available_heights = ia.collect_available_heights(entry_formats)
    selected = find_best_quality_match(available_heights, target_height, strategy=strategy)
    if selected is None:
        return "bestvideo+bestaudio/best"

    ext = height_to_ext.get(selected) or "mp4"
    aud_ext = "m4a" if ext == "mp4" else "webm"
    return (
        f"bestvideo[height<={selected}][ext={ext}]+bestaudio[ext={aud_ext}]/"
        f"best[height<={selected}][ext={ext}]/best[height<={selected}]"
    )


def _prefix_for_entry(idx: int, use_numbering: bool, prefix_template: str) -> str | None:
    if not (use_numbering and prefix_template):
        return None
    try:
        return prefix_template.format(N=idx)
    except Exception:
        return f"{idx:02d}_"
