"""Загрузка одной ссылки как есть — базовый сценарий и общая точка выхода (BL-1105).

Сюда сходятся все ветки: прямой (неинтерактивный) путь, интерактивное одиночное
видео и fallback интерактивных сценариев, если разбор плейлиста не удался.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import typer

from ..console import safe_secho
from ..types import DownloadOptions, config_download_defaults
from .context import DownloadTotals
from .entry_download import download_entry_with_retry
from .url_sources import is_effective_playlist

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision


@dataclass(slots=True)
class EntrySetup:
    """Результат интерактивной настройки одной ссылки."""

    chosen_format: str | None = None
    file_prefix: str | None = None
    quality_suffix: str | None = None
    custom_name: str | None = None
    overwrite: bool = False


def build_options(
    ctx: DownloadContext,
    url: str,
    decision: HistoryDecision,
    *,
    setup: EntrySetup | None = None,
    playlist: bool = False,
    playlist_items: str | None = None,
) -> DownloadOptions:
    """Собрать `DownloadOptions` из конфига, решения по истории и настроек пользователя."""

    setup = setup or EntrySetup()
    name_template = setup.custom_name or ctx.cfg.name_template

    return DownloadOptions(
        url=url,
        output_dir=ctx.output_dir(decision),
        **config_download_defaults(ctx.cfg),
        name_template=name_template,
        dry_run=ctx.dry_run,
        playlist=playlist,
        playlist_items=playlist_items,
        custom_format=setup.chosen_format,
        file_prefix=setup.file_prefix,
        quality_suffix=setup.quality_suffix if not setup.custom_name else None,
        overwrite=setup.overwrite or decision.overwrite,
    )


def download_single_url(
    ctx: DownloadContext,
    url: str,
    decision: HistoryDecision,
    *,
    setup: EntrySetup | None = None,
    playlist: bool = False,
    playlist_items: str | None = None,
) -> DownloadTotals:
    """Скачать одну ссылку и вернуть итоги. Плейлист при `playlist=True` разбирает yt-dlp."""

    opts = build_options(
        ctx,
        url,
        decision,
        setup=setup,
        playlist=playlist,
        playlist_items=playlist_items,
    )

    # В интерактивном режиме заголовок уже выведен диалогами — не дублируем.
    loading_message = None if ctx.interactive else f"\n⏳ Загрузка: {url}"
    retry_message = None if ctx.interactive else f"\n↻ Повтор: {url}"

    result = download_entry_with_retry(
        ctx.dl,
        opts,
        logger=ctx.logger,
        url=url,
        title=url,
        loading_message=loading_message,
        retry_message=retry_message,
        skip_message=f"[SKIP] {url} — пропущено после сетевой ошибки",
        show_error_hints=True,
        error_message=lambda exc: f"[ERROR] {url} — {exc}",
    )

    if result.skipped_network or result.failed:
        return DownloadTotals(failed=1)

    totals = DownloadTotals()
    if not ctx.dry_run:
        totals.total_files += len(result.files)

    if ctx.dry_run or result.files:
        safe_secho(f"✓ [OK] {url}", fg=typer.colors.GREEN)
    else:
        # Сюда попадаем только при `not dry_run and not files` — это ошибка загрузки.
        safe_secho(f"⚠ [WARN] {url} — нет файлов", fg=typer.colors.YELLOW)
        totals.failed += 1

    return totals


def run(ctx: DownloadContext, url: str, decision: HistoryDecision) -> DownloadTotals:
    """Сценарий по умолчанию: скачать ссылку без интерактивных диалогов."""

    return download_single_url(
        ctx,
        url,
        decision,
        playlist=is_effective_playlist(ctx, url),
        playlist_items=ctx.playlist_items,
    )
