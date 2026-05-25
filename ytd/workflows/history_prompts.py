"""History lookup prompts during download."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from ..console import safe_echo, safe_secho
from ..history.storage import (
    HistoryStore,
    fetch_download,
    get_default_store,
    init_db,
    normalize_history_id,
    update_download,
)
from ..types import AppConfig


@dataclass
class HistoryDecision:
    proceed: bool
    overwrite: bool = False
    new_output: Path | None = None
    action: str | None = None
    increment_retry: bool = False


def initialize_history(cfg: AppConfig, logger: Any | None = None) -> HistoryStore | None:
    """Подготовить базу истории и, при необходимости, импортировать JSONL."""

    if not getattr(cfg, "history_enabled", True):
        return None

    try:
        init_db(cfg.history_db)
        store = get_default_store()
        created = store.ensure_schema()
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            logger.warning("не удалось инициализировать историю (%s): %s", cfg.history_db, exc)
        return None

    if created and cfg.save_metadata:
        try:
            store.import_from_jsonl(cfg.save_metadata)
        except Exception as exc:  # noqa: BLE001
            if logger is not None:
                logger.warning(
                    "не удалось импортировать историю из %s: %s",
                    cfg.save_metadata,
                    exc,
                )

    return store


def history_identifier(candidate: str | None) -> str | None:
    if not candidate:
        return None
    return normalize_history_id(candidate)


def print_history_card(entry: Mapping[str, Any]) -> None:
    safe_echo()
    safe_secho("История загрузок:", fg=typer.colors.MAGENTA, bold=True)
    safe_echo(f"  Статус: {entry.get('status', 'unknown')}")
    title = entry.get("title") or "—"
    safe_echo(f"  Название: {title}")
    if entry.get("started_at"):
        safe_echo(f"  Начато: {entry.get('started_at')}")
    if entry.get("finished_at"):
        safe_echo(f"  Завершено: {entry.get('finished_at')}")
    if entry.get("file_path"):
        safe_echo(f"  Файл: {entry.get('file_path')}")
    if entry.get("error"):
        safe_secho(f"  Ошибка: {entry.get('error')}", fg=typer.colors.RED)
    retry_count = entry.get("retry_count")
    if retry_count is not None:
        safe_echo(f"  Повторы: {retry_count}")
    if entry.get("last_action"):
        safe_echo(f"  Последнее действие: {entry.get('last_action')}")


def prompt_history_decision(
    *,
    history_available: bool,
    cfg: AppConfig,
    logger: Any,
    video_id: str | None,
    current_url: str,
    title_hint: str | None = None,
    default_output_dir: Path | None = None,
) -> HistoryDecision:
    if not history_available:
        return HistoryDecision(proceed=True)
    try:
        entry = fetch_download(video_id=video_id, url=current_url)
    except Exception as fetch_err:  # noqa: BLE001
        logger.warning("не удалось получить историю для %s: %s", current_url, fetch_err)
        return HistoryDecision(proceed=True)

    if not entry:
        return HistoryDecision(proceed=True)

    if title_hint:
        safe_echo(f"→ {title_hint}")
    print_history_card(entry)
    status = (entry.get("status") or "").lower()

    if status == "success":
        safe_echo("Найдена успешная загрузка. Выберите действие:")
        safe_echo("  1) Пропустить повторную загрузку")
        safe_echo("  2) Перезаписать файлы")
        safe_echo("  3) Скачать в другую папку")
        choice = typer.prompt("Ваш выбор", default="1")

        if choice.strip() == "2":
            decision = HistoryDecision(
                proceed=True,
                overwrite=True,
                action="overwrite",
                increment_retry=True,
            )
        elif choice.strip() == "3":
            default_dir = Path(
                entry.get("file_path")
                or (default_output_dir or cfg.output)
            )
            new_dir_str = typer.prompt(
                "Введите путь к новой папке",
                default=str(default_dir),
            )
            decision = HistoryDecision(
                proceed=True,
                new_output=Path(new_dir_str).expanduser(),
                action="download_elsewhere",
                increment_retry=True,
            )
        else:
            decision = HistoryDecision(proceed=False, action="skip")
    elif status in {"failed", "in_progress"}:
        safe_echo("Предыдущая загрузка не завершилась успешно. Что сделать?")
        safe_echo("  1) Возобновить")
        safe_echo("  2) Начать заново")
        safe_echo("  0) Пропустить")
        choice = typer.prompt("Ваш выбор", default="1")
        normalized = choice.strip()
        if normalized == "2":
            decision = HistoryDecision(
                proceed=True,
                overwrite=True,
                action="restart",
                increment_retry=True,
            )
        elif normalized == "0":
            decision = HistoryDecision(proceed=False, action="skip")
        else:
            decision = HistoryDecision(
                proceed=True,
                action="resume",
                increment_retry=True,
            )
    else:
        safe_echo("Найдена запись в истории. Продолжить загрузку?")
        safe_echo("  1) Да")
        safe_echo("  0) Нет, пропустить")
        choice = typer.prompt("Ваш выбор", default="1")
        decision = (
            HistoryDecision(proceed=False, action="skip")
            if choice.strip() == "0"
            else HistoryDecision(proceed=True, action="proceed")
        )

    if history_available:
        try:
            update_download(
                video_id=video_id,
                url=current_url,
                last_action=decision.action,
                retry_increment=decision.increment_retry,
                status="in_progress" if decision.proceed and decision.action != "skip" else None,
            )
        except Exception as update_err:  # noqa: BLE001
            logger.warning(
                "не удалось обновить запись истории для %s: %s",
                current_url,
                update_err,
            )

    if not decision.proceed:
        safe_secho("Загрузка пропущена по истории", fg=typer.colors.CYAN)
    return decision
