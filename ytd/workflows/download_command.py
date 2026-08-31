"""Оркестрация команды `download`: подготовка контекста и выбор сценария (BL-1105).

Сама работа вынесена в сценарии — `single_video`, `playlist_interactive`,
`playlist_batch`, `download_one`. Каждый сценарий имеет одну сигнатуру
`run(ctx, url, decision) -> DownloadTotals` и отвечает за свой путь целиком,
поэтому «провалиться» из одного сценария в другой по недосмотру нельзя.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import typer

from ..config import load_config, merge_cli_overrides
from ..console import safe_secho
from ..downloader import Downloader
from ..logging import setup_logging
from ..pause import PauseController
from ..types import AppConfig
from . import download_one, playlist_batch, playlist_interactive, single_video
from .context import DownloadContext, DownloadTotals
from .history_prompts import (
    HistoryDecision,
    history_identifier,
    initialize_history,
    prompt_history_decision,
)
from .url_sources import (
    choose_interactive_playlist,
    collect_urls,
    is_effective_playlist,
    looks_like_playlist_url,
)

__all__ = ["execute_download", "looks_like_playlist_url", "select_scenario"]

Scenario = Callable[[DownloadContext, str, HistoryDecision], DownloadTotals]


def _configure_streams() -> None:
    """Не падать на символах, которых нет в кодировке консоли."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(errors="replace")
            except (AttributeError, TypeError, ValueError, OSError):
                pass


def _cli_overrides(values: dict[str, Any]) -> dict[str, Any]:
    """Оставить только явно переданные пользователем опции."""

    return {key: value for key, value in values.items() if value is not None}


def _create_pause_controller(
    cfg: AppConfig,
    *,
    pause_between: bool,
    intra_video_pause: bool,
    interactive: bool,
    playlist_flag: bool,
    has_playlist_candidates: bool,
) -> PauseController | None:
    """Создать контроллер пауз, если хотя бы один режим паузы применим."""

    use_between = pause_between or cfg.pause_between_videos
    enable_between = use_between and (
        interactive
        or playlist_flag
        or (bool(getattr(cfg, "auto_detect_playlists", True)) and has_playlist_candidates)
    )
    enable_intra = intra_video_pause or cfg.intra_video_pause

    if not (enable_between or enable_intra):
        return None

    controller = PauseController(
        pause_key=cfg.pause_key or "p",
        resume_key=cfg.resume_key or "r",
        intra_video=enable_intra,
        between_entries=enable_between,
    )
    controller.enable()

    if enable_intra and enable_between:
        message = (
            "⏸  Режим пауз включен: 'p' — прервать текущую загрузку или пауза между видео; "
            "'r' — возобновить"
        )
    elif enable_intra:
        message = (
            "⏸  Пауза внутри файла: 'p' — прервать загрузку (продолжение с места остановки); "
            "'r' — возобновить"
        )
    else:
        message = "⏸  Режим пауз включен: нажмите 'p' во время загрузки для паузы после текущего видео"
    safe_secho(message, fg=typer.colors.CYAN)

    return controller


def _preflight_history(
    cfg: AppConfig,
    logger: Any,
    urls: list[str],
    *,
    history_available: bool,
) -> tuple[list[str], list[HistoryDecision]]:
    """Спросить про уже скачанные элементы до начала загрузок.

    Все вопросы задаются пачкой в начале, чтобы дальше процесс шёл без прерываний.
    """

    if not history_available:
        return urls, [HistoryDecision(proceed=True) for _ in urls]

    filtered: list[str] = []
    decisions: list[HistoryDecision] = []
    for url in urls:
        decision = prompt_history_decision(
            history_available=True,
            cfg=cfg,
            logger=logger,
            video_id=history_identifier(url),
            current_url=url,
            default_output_dir=cfg.output,
        )
        if not decision.proceed:
            continue
        filtered.append(url)
        decisions.append(decision)

    if not filtered:
        safe_secho(
            "[OK] Все запрошенные элементы уже скачаны — новых задач нет",
            fg=typer.colors.CYAN,
        )
        raise typer.Exit(code=0)

    return filtered, decisions


def select_scenario(ctx: DownloadContext, url: str) -> Scenario:
    """Выбрать сценарий загрузки ровно один раз на ссылку."""

    effective_playlist = is_effective_playlist(ctx, url)

    if ctx.interactive:
        return playlist_interactive.run if effective_playlist else single_video.run
    if ctx.pause_controller is not None and effective_playlist:
        return playlist_batch.run
    return download_one.run


def _report(totals: DownloadTotals, *, dry_run: bool) -> None:
    """Вывести итог и завершить команду соответствующим кодом возврата."""

    if dry_run:
        safe_secho("[OK] Dry-run завершён (файлы не скачаны)", fg=typer.colors.GREEN)
        raise typer.Exit(code=0)

    code = totals.exit_code()
    if code == 0:
        safe_secho(f"[OK] Скачано файлов: {totals.total_files}", fg=typer.colors.GREEN)
    elif totals.total_files > 0:
        safe_secho(
            f"[WARN] Скачано файлов: {totals.total_files}, ошибок: {totals.failed}",
            fg=typer.colors.YELLOW,
        )
    elif totals.failed > 0:
        safe_secho("✗ Ошибка загрузки (ни один файл не скачан)", fg=typer.colors.RED)
    else:
        safe_secho("⚠ Файлы не скачаны", fg=typer.colors.YELLOW)
    raise typer.Exit(code=code)


def execute_download(
    url: str | None = None,
    output: Path | None = None,
    urls_file: Path | None = None,
    audio_only: bool | None = None,
    audio_format: str | None = None,
    video_format: str | None = None,
    quality: str | None = None,
    name: str | None = None,
    subtitles: list[str] | None = None,
    proxy: str | None = None,
    cookies: Path | None = None,
    cookies_from_browser: str | None = None,
    retry: int | None = None,
    retry_delay: float | None = None,
    dry_run: bool = False,
    playlist: bool = False,
    playlist_items: str | None = None,
    interactive: bool | None = None,
    pause_between: bool = False,
    intra_video_pause: bool = False,
    verbose: bool = False,
):
    """Скачать видео/аудио по указанному URL."""

    _configure_streams()
    logger = setup_logging(level="DEBUG" if verbose else "INFO")

    try:
        cfg = merge_cli_overrides(
            load_config(),
            _cli_overrides(
                {
                    "output": output,
                    "audio_only": audio_only,
                    "audio_format": audio_format,
                    "video_format": video_format,
                    "quality": quality,
                    "name_template": name,
                    "subtitles": subtitles,
                    "proxy": proxy,
                    "cookies_file": cookies,
                    "cookies_from_browser": cookies_from_browser,
                    "retry": retry,
                    "retry_delay": retry_delay,
                }
            ),
        )

        if interactive is None:
            interactive = bool(getattr(cfg, "interactive_by_default", False))
        else:
            interactive = bool(interactive)

        history_store = initialize_history(cfg, logger)
        history_available = history_store is not None

        urls = collect_urls(url, urls_file)
        urls = choose_interactive_playlist(
            urls,
            interactive=interactive,
            playlist_flag=playlist,
            auto_detect=bool(getattr(cfg, "auto_detect_playlists", True)),
        )
        has_playlist_candidates = any(looks_like_playlist_url(item) for item in urls)

        urls, decisions = _preflight_history(
            cfg, logger, urls, history_available=history_available
        )

        pause_controller = _create_pause_controller(
            cfg,
            pause_between=pause_between,
            intra_video_pause=intra_video_pause,
            interactive=interactive,
            playlist_flag=playlist,
            has_playlist_candidates=has_playlist_candidates,
        )

        ctx = DownloadContext(
            cfg=cfg,
            logger=logger,
            dl=Downloader(cfg, logger, verbose=verbose, history_store=history_store),
            dry_run=dry_run,
            interactive=interactive,
            history_available=history_available,
            playlist=playlist,
            playlist_items=playlist_items,
            pause_controller=pause_controller,
        )
        ctx.dl.pause_controller = pause_controller

        totals = DownloadTotals()
        for index, one_url in enumerate(urls):
            decision = decisions[index] if index < len(decisions) else HistoryDecision(proceed=True)
            scenario = select_scenario(ctx, one_url)
            totals.merge(scenario(ctx, one_url, decision))

        if pause_controller:
            pause_controller.disable()

        _report(totals, dry_run=dry_run)

    except KeyboardInterrupt:
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    except typer.Abort:
        # click поднимает Abort при Ctrl+C или EOF в диалоге — это тоже отмена, а не ошибка.
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки")
        safe_secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
