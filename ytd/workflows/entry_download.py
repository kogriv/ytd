"""Single-entry download with network retry."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from ..console import safe_secho
from ..downloader import Downloader
from ..exceptions import NetworkUnavailableError
from ..types import DownloadOptions
from .network import echo_error_hints, prompt_network_recovery


@dataclass
class EntryDownloadResult:
    files: list[Path]
    failed: bool = False
    skipped_network: bool = False


def download_entry_with_retry(
    dl: Downloader,
    opts: DownloadOptions,
    *,
    logger: Any,
    url: str,
    title: str,
    loading_message: str | None,
    retry_message: str | None = None,
    skip_message: str | None = None,
    show_error_hints: bool = False,
    error_message: Callable[[BaseException], str] | None = None,
) -> EntryDownloadResult:
    """Download one entry, retrying on network errors per user choice.

    `loading_message=None` подавляет вывод перед попыткой (интерактивный режим уже
    вывел свой заголовок). `error_message` позволяет вызывающей стороне задать текст
    ошибки по исключению, `show_error_hints` — добавить подсказки про anti-bot.
    """

    files: list[Path] = []
    download_failed = False
    skipped_due_to_network = False
    first_attempt = True
    if retry_message is None and loading_message is not None:
        retry_message = loading_message.replace("⏳ Загрузка", "↻ Повтор", 1)

    while True:
        message = loading_message if first_attempt else retry_message
        if message:
            safe_secho(message, fg=typer.colors.CYAN)
        first_attempt = False

        try:
            files = dl.download(opts)
            break
        except KeyboardInterrupt:
            raise
        except NetworkUnavailableError as net_err:
            decision = prompt_network_recovery(
                net_err,
                context=url,
                title_hint=title,
            )
            if decision == "retry":
                continue
            if decision == "skip":
                skipped_due_to_network = True
                safe_secho(
                    skip_message
                    if skip_message
                    else f"  ⚠ [SKIP] {title} — пропущено после сетевой ошибки",
                    fg=typer.colors.YELLOW,
                )
                break
            safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
            raise typer.Exit(1) from net_err
        except Exception as exc:  # noqa: BLE001
            download_failed = True
            logger.exception("Ошибка загрузки %s", url)
            safe_secho(
                error_message(exc) if error_message else f"[ERROR] {title}",
                fg=typer.colors.RED,
            )
            if show_error_hints:
                echo_error_hints(exc)
            break

    return EntryDownloadResult(
        files=files,
        failed=download_failed,
        skipped_network=skipped_due_to_network,
    )
