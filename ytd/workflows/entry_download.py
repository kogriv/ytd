"""Single-entry download with network retry."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from ..console import safe_secho
from ..downloader import Downloader
from ..exceptions import NetworkUnavailableError
from ..types import DownloadOptions
from .network import prompt_network_recovery


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
    loading_message: str,
    retry_message: str | None = None,
) -> EntryDownloadResult:
    """Download one entry, retrying on network errors per user choice."""

    files: list[Path] = []
    download_failed = False
    skipped_due_to_network = False
    first_attempt = True
    retry_message = retry_message or loading_message.replace("⏳ Загрузка", "↻ Повтор", 1)

    while True:
        message = loading_message if first_attempt else retry_message
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
                    f"  ⚠ [SKIP] {title} — пропущено после сетевой ошибки",
                    fg=typer.colors.YELLOW,
                )
                break
            safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
            raise typer.Exit(1) from net_err
        except Exception:
            download_failed = True
            logger.exception("Ошибка загрузки %s", url)
            safe_secho(f"[ERROR] {title}", fg=typer.colors.RED)
            break

    return EntryDownloadResult(
        files=files,
        failed=download_failed,
        skipped_network=skipped_due_to_network,
    )
