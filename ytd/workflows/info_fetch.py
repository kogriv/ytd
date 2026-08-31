"""Получение метаданных с диалогом восстановления при сетевой ошибке (BL-1105)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_secho
from ..exceptions import NetworkUnavailableError
from .network import prompt_network_recovery

if TYPE_CHECKING:
    from .context import DownloadContext


def fetch_info(
    ctx: DownloadContext,
    url: str,
    *,
    title_hint: str | None = None,
    allow_skip: bool = False,
    skip_message: str | None = None,
) -> dict[str, Any] | None:
    """Запросить метаданные, предлагая повтор/пропуск при потере сети.

    Возвращает `None`, если пользователь выбрал «пропустить» и это разрешено.
    При выборе «завершить программу» поднимает `typer.Exit(1)`.
    """

    while True:
        try:
            return ctx.dl.get_info(url)
        except NetworkUnavailableError as net_err:
            decision = prompt_network_recovery(
                net_err,
                context=url,
                title_hint=title_hint,
            )
            if decision == "retry":
                continue
            if decision == "skip" and allow_skip:
                if skip_message:
                    safe_secho(skip_message, fg=typer.colors.YELLOW)
                else:
                    hint = title_hint or url
                    safe_secho(
                        f"[SKIP] {hint} — пропущено после сетевой ошибки",
                        fg=typer.colors.YELLOW,
                    )
                return None
            safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
            raise typer.Exit(1) from net_err
