"""Плейлист в интерактивном режиме: разбор, выбор режима, делегирование (BL-1105)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import typer

from ..console import safe_echo, safe_secho
from . import playlist_per_video, playlist_unified
from .context import DownloadTotals
from .download_one import EntrySetup, download_single_url
from .info_fetch import fetch_info
from .single_video import setup_from_info

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision


def run(ctx: DownloadContext, url: str, decision: HistoryDecision) -> DownloadTotals:
    """Получить состав плейлиста и выполнить выбранный пользователем режим."""

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

    setup = EntrySetup(overwrite=decision.overwrite)

    safe_echo("\n" + "═" * 60)
    safe_secho("⏳ Получение информации о плейлисте...", fg=typer.colors.CYAN, bold=True)
    safe_echo("Это может занять некоторое время для больших плейлистов.")
    safe_echo("═" * 60)

    try:
        info = fetch_info(
            ctx,
            url,
            title_hint="Плейлист",
            allow_skip=True,
            skip_message="[SKIP] Плейлист пропущен после сетевой ошибки",
        )
        if info is None:
            return DownloadTotals(failed=1)

        entries = info.get("entries") or []
        if entries:
            ia.show_playlist_info(info)
            mode = ia.choose_playlist_mode()
            if mode is None:
                safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
                return DownloadTotals()
            if mode == 1:
                return playlist_unified.run_mode(ctx, url, decision, info, entries)
            return playlist_per_video.run_mode(ctx, url, decision, info, entries)

        safe_secho(
            "[INFO] Плейлист пуст или это одиночное видео. Переходим в режим одиночного видео.",
            fg=typer.colors.CYAN,
        )
        setup = setup_from_info(ctx, info, decision)
    except Exception as exc:  # noqa: BLE001
        # TODO(GAP-CR-034): typer.Exit тоже наследуется от Exception и гасится здесь —
        # поведение сохранено как до BL-1105, исправление отдельной задачей.
        ctx.logger.warning(
            "Не удалось обработать плейлист: %s — продолжим с настройками по умолчанию", exc
        )

    # Плейлист не разобран (пуст, либо разбор упал) — отдаём ссылку yt-dlp целиком.
    return download_single_url(
        ctx,
        url,
        decision,
        setup=setup,
        playlist=True,
        playlist_items=ctx.playlist_items,
    )
