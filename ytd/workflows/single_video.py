"""Сценарий: интерактивная настройка и загрузка одиночного видео (BL-1105)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from ..console import safe_echo, safe_secho
from .context import DownloadTotals
from .download_one import EntrySetup, download_single_url
from .info_fetch import fetch_info

if TYPE_CHECKING:
    from .context import DownloadContext
    from .history_prompts import HistoryDecision

import typer


def setup_from_info(
    ctx: DownloadContext,
    info: dict[str, Any],
    decision: HistoryDecision,
) -> EntrySetup:
    """Провести диалоги качества/имени/перезаписи и вернуть настройки загрузки."""

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

    result = ia.run_single_video_interactive_setup(
        info,
        ctx.output_dir(decision),
        initial_overwrite=decision.overwrite,
    )
    return EntrySetup(
        chosen_format=result.chosen_format,
        file_prefix=result.file_prefix,
        quality_suffix=result.quality_suffix,
        custom_name=result.custom_name,
        overwrite=result.overwrite,
    )


def run(ctx: DownloadContext, url: str, decision: HistoryDecision) -> DownloadTotals:
    """Интерактивное одиночное видео: метаданные → диалоги → загрузка."""

    setup = EntrySetup(overwrite=decision.overwrite)

    safe_echo("\n" + "═" * 60)
    safe_secho("⏳ Получение информации о видео...", fg=typer.colors.CYAN, bold=True)
    safe_echo("═" * 60)

    try:
        info = fetch_info(
            ctx,
            url,
            title_hint="Видео",
            allow_skip=True,
            skip_message="[SKIP] Видео пропущено после сетевой ошибки",
        )
        if info is None:
            return DownloadTotals(failed=1)
        setup = setup_from_info(ctx, info, decision)
    except Exception as exc:  # noqa: BLE001
        # TODO(GAP-CR-034): typer.Exit наследуется от RuntimeError и тоже гасится здесь,
        # поэтому выбор «завершить программу» в диалоге сети не останавливает загрузку.
        # Поведение сохранено как было до BL-1105; исправление — отдельной задачей.
        ctx.logger.warning(
            "Не удалось получить форматы: %s — продолжим с настройками по умолчанию", exc
        )

    return download_single_url(ctx, url, decision, setup=setup)
