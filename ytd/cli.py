from __future__ import annotations

import csv
import io
import json
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from .config import load_config
from .console import safe_echo, safe_secho
from .downloader import Downloader
from .exceptions import NetworkUnavailableError
from .history.storage import (
    fetch_download,
    list_downloads,
)
from .logging import setup_logging
from .workflows.download_command import execute_download
from .workflows.history_prompts import (
    history_identifier,
    initialize_history,
    print_history_card,
)
from .workflows.network import echo_error_hints, prompt_network_recovery

if TYPE_CHECKING:
    pass

# Aliases for history CLI and legacy call sites
_initialize_history = initialize_history
_history_identifier = history_identifier
_print_history_card = print_history_card
_prompt_network_recovery = prompt_network_recovery
_echo_error_hints = echo_error_hints


def _parse_since_option(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:  # noqa: PERF203
        raise typer.BadParameter(
            "Неверный формат даты. Используйте ISO 8601, например 2024-01-01T00:00:00",
            param_name="since",
        ) from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed.isoformat(timespec="seconds")


def _collect_history_filters(
    status: list[str] | None,
    limit: int | None,
    since: str | None,
    playlist: str | None,
) -> dict[str, Any]:
    filters: dict[str, Any] = {}

    statuses = [item for item in (status or []) if item]
    if statuses:
        filters["statuses"] = statuses

    if limit is not None and limit > 0:
        filters["limit"] = limit

    parsed_since = _parse_since_option(since)
    if parsed_since:
        filters["since"] = parsed_since

    playlist_id = (playlist or "").strip()
    if playlist_id:
        filters["playlist_id"] = playlist_id

    return filters


def _load_history_entries(filters: Mapping[str, Any]) -> list[dict[str, Any]]:
    cfg = load_config()
    if not cfg.history_enabled:
        return []
    if _initialize_history(cfg) is None:
        return []
    return list_downloads(**filters)


def _truncate_text(value: str, max_length: int) -> str:
    if len(value) <= max_length:
        return value
    if max_length <= 1:
        return value[:max_length]
    return value[: max_length - 1] + "…"


def _history_value(entry: Mapping[str, Any], key: str) -> str:
    if key == "finished_at":
        raw = entry.get("finished_at") or entry.get("started_at")
    elif key == "playlist":
        raw = entry.get("playlist_title") or entry.get("playlist_id")
    else:
        raw = entry.get(key)
    if raw in {None, ""}:
        return "—"
    return str(raw)


def _print_history_table(entries: list[dict[str, Any]]) -> None:
    if not entries:
        safe_secho("История загрузок пуста.", fg=typer.colors.YELLOW)
        return

    columns: list[tuple[str, str, int]] = [
        ("video_id", "ID/Ссылка", 40),
        ("status", "Статус", 10),
        ("title", "Название", 32),
        ("finished_at", "Завершено", 19),
        ("playlist", "Плейлист", 18),
    ]

    display_rows: list[list[str]] = []
    widths: list[int] = []

    for key, header, max_width in columns:
        column_values = [_truncate_text(_history_value(entry, key), max_width) for entry in entries]
        column_width = max(len(header), *(len(val) for val in column_values)) if column_values else len(header)
        column_width = min(column_width, max_width)
        widths.append(column_width)
        for idx, value in enumerate(column_values):
            if len(display_rows) <= idx:
                display_rows.append(["" for _ in columns])
            display_rows[idx][len(widths) - 1] = value.ljust(column_width)

    header_parts = [_truncate_text(header, width).ljust(width) for (_, header, _), width in zip(columns, widths, strict=True)]
    header_line = " | ".join(header_parts)
    separator = "-+-".join("-" * width for width in widths)

    safe_secho(header_line, bold=True)
    safe_secho(separator)
    for row in display_rows:
        safe_echo(" | ".join(row))


def _export_history_csv(entries: list[dict[str, Any]]) -> None:
    fieldnames = [
        "video_id",
        "url",
        "title",
        "status",
        "started_at",
        "finished_at",
        "file_path",
        "error",
        "playlist_id",
        "playlist_title",
        "retry_count",
        "last_action",
    ]

    header_buffer = io.StringIO()
    header_writer = csv.DictWriter(header_buffer, fieldnames=fieldnames, extrasaction="ignore")
    header_writer.writeheader()
    safe_echo(header_buffer.getvalue().strip("\r\n"))

    for entry in entries:
        row_buffer = io.StringIO()
        row_writer = csv.DictWriter(row_buffer, fieldnames=fieldnames, extrasaction="ignore")
        sanitized = {key: ("" if entry.get(key) is None else entry.get(key)) for key in fieldnames}
        row_writer.writerow(sanitized)
        safe_echo(row_buffer.getvalue().strip("\r\n"))


history_app = typer.Typer(
    name="history",
    help="Просмотр и экспорт истории загрузок",
    add_completion=False,
    invoke_without_command=True,
)


@history_app.callback()
def history_root(
    ctx: typer.Context,
    status: list[str] | None = typer.Option(None, "--status", "-s", help="Фильтр по статусу (можно несколько)"),
    limit: int | None = typer.Option(20, "--limit", "-n", help="Максимум записей (0 — без ограничений)"),
    since: str | None = typer.Option(None, "--since", help="Показывать записи, созданные после указанной даты"),
    playlist: str | None = typer.Option(None, "--playlist", help="ID плейлиста для фильтрации"),
) -> None:
    filters = _collect_history_filters(status, limit, since, playlist)
    ctx.ensure_object(dict)
    ctx.obj["history_filters"] = filters

    if ctx.invoked_subcommand is None:
        entries = _load_history_entries(filters)
        _print_history_table(entries)


@history_app.command("show")
def history_show(video_id: str = typer.Argument(..., help="Идентификатор или ссылка для просмотра")) -> None:
    cfg = load_config()
    if not cfg.history_enabled:
        safe_secho("История отключена в конфигурации.", fg=typer.colors.YELLOW)
        raise typer.Exit(code=1)

    if _initialize_history(cfg) is None:
        safe_secho("Не удалось инициализировать базу истории.", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    normalized = _history_identifier(video_id)
    entry = None

    if normalized:
        entry = fetch_download(video_id=normalized)

    if entry is None:
        entry = fetch_download(video_id=video_id)

    if entry is None:
        entry = fetch_download(url=video_id)

    if not entry:
        safe_secho("✗ Запись не найдена", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    _print_history_card(entry)


@history_app.command("export")
def history_export(
    ctx: typer.Context,
    format: str = typer.Option(..., "--format", "-f", help="Формат экспорта: jsonl или csv"),
) -> None:
    filters = (ctx.obj or {}).get("history_filters", {})
    entries = _load_history_entries(filters)
    fmt = format.lower()

    if fmt == "jsonl":
        for entry in entries:
            safe_echo(json.dumps(entry, ensure_ascii=False))
    elif fmt == "csv":
        _export_history_csv(entries)
    else:
        raise typer.BadParameter("Поддерживаемые форматы: jsonl, csv", param_name="format")


app = typer.Typer(
    no_args_is_help=True,
    add_completion=False,
    help="Простой загрузчик видео с площадок, поддерживаемых yt-dlp",
)
app.add_typer(history_app, name="history")


def _format_info(info: dict[str, Any]) -> str:
    """Отформатировать метаданные в читаемую строку."""
    lines = []
    lines.append(f"ID: {info.get('id', 'N/A')}")
    lines.append(f"Название: {info.get('title', 'N/A')}")
    lines.append(f"Канал: {info.get('uploader', 'N/A')}")
    lines.append(f"Длительность: {info.get('duration', 0)} сек")
    lines.append(f"Описание: {(info.get('description') or '')[:100]}...")

    formats = info.get("formats", [])
    if formats:
        lines.append(f"\nДоступно форматов: {len(formats)}")
        for fmt in formats[:5]:
            fmt_id = fmt.get("format_id", "?")
            ext = fmt.get("ext", "?")
            res = fmt.get("resolution", "?")
            lines.append(f"  - {fmt_id}: {ext}, {res}")
        if len(formats) > 5:
            lines.append(f"  ... и ещё {len(formats) - 5}")

    return "\n".join(lines)


@app.command("download")
def cmd_download(
    url: str | None = typer.Argument(None, help="Ссылка на видео или плейлист"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Папка назначения"),
    urls_file: Path | None = typer.Option(None, "--urls-file", help="Файл со списком ссылок (по одной в строке)", rich_help_panel="Дополнительно"),
    audio_only: bool | None = typer.Option(None, "--audio-only", help="Скачать только аудио"),
    audio_format: str | None = typer.Option(None, "--audio-format", help="Формат аудио (m4a/mp3/opus)"),
    video_format: str | None = typer.Option(None, "--video-format", help="Контейнер видео (mp4/webm)"),
    quality: str | None = typer.Option(None, "--quality", help="Качество/пресет (best/1080p/720p/audio)"),
    name: str | None = typer.Option(None, "--name", help="Шаблон имени файла"),
    subtitles: list[str] | None = typer.Option(None, "--subtitles", help="Языки субтитров"),
    proxy: str | None = typer.Option(None, "--proxy", help="Прокси URL"),
    cookies: Path | None = typer.Option(
        None,
        "--cookies",
        help="Файл cookies (Netscape) для yt-dlp",
        rich_help_panel="Дополнительно",
    ),
    cookies_from_browser: str | None = typer.Option(
        None,
        "--cookies-from-browser",
        help="Извлечь cookies из браузера (chrome, firefox, edge, …)",
        rich_help_panel="Дополнительно",
    ),
    retry: int | None = typer.Option(None, "--retry", help="Количество повторов при ошибках"),
    retry_delay: float | None = typer.Option(None, "--retry-delay", help="Задержка между повторами (сек)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Только показать действия"),
    playlist: bool = typer.Option(False, "--playlist", help="Обработать плейлист целиком"),
    playlist_items: str | None = typer.Option(None, "--playlist-items", help="Номера видео в плейлисте (например '1-3' или '1,3,5')"),
    interactive: bool | None = typer.Option(
        None,
        "--interactive/--no-interactive",
        "-i/-I",
        help="Диалоговый выбор качества (по умолчанию — из конфига interactive_by_default)",
    ),
    pause_between: bool = typer.Option(False, "--pause-between", help="Пауза между видео в плейлисте ('p' / 'r')", rich_help_panel="Дополнительно"),
    intra_video_pause: bool = typer.Option(
        False,
        "--intra-video-pause",
        help="Пауза внутри текущего файла: прервать загрузку и продолжить с места остановки ('p' / 'r')",
        rich_help_panel="Дополнительно",
    ),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробные логи (DEBUG)"),
):
    """Скачать видео/аудио по указанному URL."""
    execute_download(
        url=url,
        output=output,
        urls_file=urls_file,
        audio_only=audio_only,
        audio_format=audio_format,
        video_format=video_format,
        quality=quality,
        name=name,
        subtitles=subtitles,
        proxy=proxy,
        cookies=cookies,
        cookies_from_browser=cookies_from_browser,
        retry=retry,
        retry_delay=retry_delay,
        dry_run=dry_run,
        playlist=playlist,
        playlist_items=playlist_items,
        interactive=interactive,
        pause_between=pause_between,
        intra_video_pause=intra_video_pause,
        verbose=verbose,
    )


@app.command("info")
def cmd_info(
    url: str = typer.Argument(..., help="Ссылка на видео или плейлист"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробные логи (DEBUG)"),
    json_output: bool = typer.Option(False, "--json", help="Вывести сырой JSON"),
) -> None:
    """Показать метаданные и доступные форматы без скачивания."""
    log_level = "DEBUG" if verbose else "INFO"
    logger = setup_logging(level=log_level)
    
    try:
        cfg = load_config()
        dl = Downloader(cfg, logger)
        while True:
            try:
                info = dl.get_info(url)
                break
            except NetworkUnavailableError as net_err:
                decision = _prompt_network_recovery(net_err, context=url)
                if decision == "retry":
                    continue
                if decision == "skip":
                    safe_secho("Информация не получена из-за сетевой ошибки", fg=typer.colors.YELLOW)
                    raise typer.Exit(code=2) from net_err
                safe_secho("✗ Прервано по запросу пользователя", fg=typer.colors.RED)
                raise typer.Exit(code=1) from net_err

        if json_output:
            safe_echo(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            safe_echo(_format_info(info))

    except KeyboardInterrupt:
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Ошибка получения метаданных")
        safe_secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e


def main() -> None:
    app()
