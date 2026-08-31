"""Плейлист без интерактива, но с паузами: поштучная загрузка (BL-1105)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_echo, safe_secho
from .context import DownloadTotals
from .download_one import build_options, download_single_url
from .history_prompts import history_identifier
from .info_fetch import fetch_info
from .playlist_entries import PreparedEntry, process_playlist_entries

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision


def run(ctx: DownloadContext, url: str, decision: HistoryDecision) -> DownloadTotals:
    """Разобрать плейлист и качать элементы по одному, чтобы работали паузы."""

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

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
            safe_secho(f"▶ Плейлист: {len(entries)} видео", fg=typer.colors.GREEN)

            def prepare_entry(idx: int, entry: dict[str, Any], total: int) -> PreparedEntry | None:
                entry_title = entry.get("title", f"Видео {idx}")
                entry_url = ia.get_entry_url(entry)
                if not entry_url:
                    safe_secho(
                        f"[WARN] Пропуск: элемент #{idx} ({entry_title}) не содержит URL",
                        fg=typer.colors.YELLOW,
                    )
                    safe_echo("      yt-dlp не вернул поля original_url/webpage_url/url.")
                    safe_echo(
                        "      Проверьте доступ к источнику (например, VK) или обновите yt-dlp."
                    )
                    return None

                return PreparedEntry(
                    opts=build_options(ctx, entry_url, decision),
                    entry_url=entry_url,
                    entry_title=entry_title,
                    history_video_id=(
                        history_identifier(str(entry.get("id"))) if entry.get("id") else None
                    ),
                )

            result = process_playlist_entries(
                entries,
                indices_to_download=None,
                existing_map={},
                dl=ctx.dl,
                dry_run=ctx.dry_run,
                cfg=ctx.cfg,
                logger=ctx.logger,
                history_available=ctx.history_available,
                prepare_entry=prepare_entry,
                pause_controller=ctx.pause_controller,
                progress_style="numbered",
            )
            return DownloadTotals(total_files=result.total_files, failed=result.failed)
    except Exception as exc:  # noqa: BLE001
        # TODO(GAP-CR-034): typer.Exit тоже гасится этим блоком — поведение сохранено
        # как до BL-1105, исправление отдельной задачей.
        ctx.logger.warning(
            "Не удалось разобрать плейлист для поштучной загрузки: %s — пробуем обычный путь", exc
        )

    # Плейлист пуст или не разобран — отдаём ссылку yt-dlp целиком.
    return download_single_url(
        ctx,
        url,
        decision,
        playlist=True,
        playlist_items=ctx.playlist_items,
    )
