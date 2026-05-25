"""Безопасный вывод в консоль (Unicode, ограничения кодировок терминала)."""

from __future__ import annotations

import re
from typing import Any

import typer

_SANITIZE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    ("✓", "[OK]"),
    ("✔", "[OK]"),
    ("✅", "[OK]"),
    ("⚠", "[WARN]"),
    ("⚠️", "[WARN]"),
    ("✗", "[ERROR]"),
    ("✘", "[ERROR]"),
    ("❌", "[ERROR]"),
    ("⛔", "[ERROR]"),
    ("→", "->"),
    ("▶", ">"),
    ("⏳", "..."),
    ("⏸", "[PAUSE]"),
    ("✦", "*"),
)


def sanitize_console_text(value: object) -> str:
    text = "" if value is None else str(value)
    for source, replacement in _SANITIZE_REPLACEMENTS:
        text = text.replace(source, replacement)
    text = re.sub(r"[═━]+", lambda match: "-" * len(match.group(0)), text)
    text = text.replace("—", "-")
    return text


def safe_secho(message: object = "", *args: Any, **kwargs: Any) -> None:
    try:
        typer.secho(message, *args, **kwargs)
    except UnicodeEncodeError:
        typer.secho(sanitize_console_text(message), *args, **kwargs)


def safe_echo(message: object = "", *args: Any, **kwargs: Any) -> None:
    try:
        typer.echo(message, *args, **kwargs)
    except UnicodeEncodeError:
        typer.echo(sanitize_console_text(message), *args, **kwargs)
