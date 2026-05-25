"""Network recovery prompts during download."""

from __future__ import annotations

import sys

import typer

from ..console import safe_echo, safe_secho, sanitize_console_text
from ..errors import antibot_hint, looks_like_antibot_error
from ..exceptions import NetworkUnavailableError


def prompt_network_recovery(
    error: NetworkUnavailableError,
    *,
    context: str | None = None,
    title_hint: str | None = None,
) -> str:
    safe_echo()
    safe_secho("⚠ Потеряно подключение к сети", fg=typer.colors.RED, bold=True)
    if title_hint:
        safe_echo(f"  Объект: {title_hint}")
    if context:
        safe_echo(f"  URL: {context}")
    safe_echo(f"  Детали: {sanitize_console_text(error)}")
    safe_echo("Возможные причины: отключён VPN/прокси, нет доступа в интернет, блокировка API.")

    if not sys.stdin.isatty():
        safe_secho("Терминал не интерактивный — остановка загрузки.", fg=typer.colors.RED)
        return "abort"

    safe_echo("После устранения проблемы выберите действие:")
    safe_echo("  1) Повторить попытку")
    safe_echo("  2) Пропустить этот элемент")
    safe_echo("  3) Завершить программу")

    while True:
        choice = typer.prompt("Ваш выбор", default="1").strip().lower()
        if choice in ("", "1", "r", "retry", "повтор", "п"):
            return "retry"
        if choice in ("2", "s", "skip", "пропустить", "п2"):
            return "skip"
        if choice in ("3", "q", "quit", "в", "выход", "abort"):
            return "abort"
        safe_secho("Введите 1, 2 или 3.", fg=typer.colors.YELLOW)


def echo_error_hints(exc: BaseException) -> None:
    if looks_like_antibot_error(exc):
        safe_echo(antibot_hint())
