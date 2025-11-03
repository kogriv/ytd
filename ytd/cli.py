from __future__ import annotations

import csv
import io
import sys
import json
import re
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Any, TYPE_CHECKING, Mapping
from urllib.parse import urlparse, parse_qs

import typer

from .config import load_config, merge_cli_overrides
from .downloader import Downloader
from .exceptions import NetworkUnavailableError
from .history.storage import (
    ensure_schema,
    init_db,
    fetch_download,
    update_download,
    list_downloads,
    import_from_jsonl,
    normalize_history_id,
)
from .logging import setup_logging
from .types import AppConfig, DownloadOptions
from .utils import find_existing_files, extract_quality_suffix, sanitize_filename, find_best_quality_match
if TYPE_CHECKING:
    from .pause import PauseController


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


def _sanitize_console_text(value: object) -> str:
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
        typer.secho(_sanitize_console_text(message), *args, **kwargs)


def safe_echo(message: object = "", *args: Any, **kwargs: Any) -> None:
    try:
        typer.echo(message, *args, **kwargs)
    except UnicodeEncodeError:
        typer.echo(_sanitize_console_text(message), *args, **kwargs)


def _prompt_network_recovery(
    error: NetworkUnavailableError,
    *,
    context: Optional[str] = None,
    title_hint: Optional[str] = None,
) -> str:
    safe_echo()
    safe_secho("⚠ Потеряно подключение к сети", fg=typer.colors.RED, bold=True)
    if title_hint:
        safe_echo(f"  Объект: {title_hint}")
    if context:
        safe_echo(f"  URL: {context}")
    safe_echo(f"  Детали: {_sanitize_console_text(error)}")
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


def _initialize_history(cfg: AppConfig, logger: Optional[Any] = None) -> bool:
    """Подготовить базу истории и, при необходимости, импортировать JSONL."""

    if not getattr(cfg, "history_enabled", True):
        return False

    try:
        init_db(cfg.history_db)
        created = ensure_schema()
    except Exception as exc:  # noqa: BLE001
        if logger is not None:
            try:
                logger.debug("не удалось инициализировать историю: %s", exc)
            except Exception:  # noqa: BLE001
                pass
        return False

    if created and cfg.save_metadata:
        try:
            import_from_jsonl(cfg.save_metadata)
        except Exception as exc:  # noqa: BLE001
            if logger is not None:
                try:
                    logger.debug("не удалось импортировать историю из %s: %s", cfg.save_metadata, exc)
                except Exception:  # noqa: BLE001
                    pass

    return True


@dataclass
class HistoryDecision:
    proceed: bool
    overwrite: bool = False
    new_output: Optional[Path] = None
    action: Optional[str] = None
    increment_retry: bool = False


def _history_identifier(candidate: Optional[str]) -> Optional[str]:
    if not candidate:
        return None
    normalized = normalize_history_id(candidate)
    return normalized


def _print_history_card(entry: Mapping[str, Any]) -> None:
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


def _parse_since_option(value: Optional[str]) -> Optional[str]:
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
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed.isoformat(timespec="seconds")


def _collect_history_filters(
    status: Optional[list[str]],
    limit: Optional[int],
    since: Optional[str],
    playlist: Optional[str],
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
    if not _initialize_history(cfg):
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

    header_parts = [_truncate_text(header, width).ljust(width) for (_, header, _), width in zip(columns, widths)]
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
    status: Optional[list[str]] = typer.Option(None, "--status", "-s", help="Фильтр по статусу (можно несколько)"),
    limit: Optional[int] = typer.Option(20, "--limit", "-n", help="Максимум записей (0 — без ограничений)"),
    since: Optional[str] = typer.Option(None, "--since", help="Показывать записи, созданные после указанной даты"),
    playlist: Optional[str] = typer.Option(None, "--playlist", help="ID плейлиста для фильтрации"),
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

    if not _initialize_history(cfg):
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


app = typer.Typer(no_args_is_help=True, add_completion=False, help="Простой загрузчик видео на базе yt-dlp")
app.add_typer(history_app, name="history")


def _looks_like_playlist_url(url: str) -> bool:
    """Грубая эвристика для определения ссылок на плейлист."""

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    path = (parsed.path or "").lower()
    if "playlist" in path:
        return True

    query = parse_qs(parsed.query)
    lists = query.get("list") or []
    return any(item.strip() for item in lists)


def _format_info(info: dict[str, Any]) -> str:
    """Отформатировать метаданные в читаемую строку."""
    lines = []
    lines.append(f"ID: {info.get('id', 'N/A')}")
    lines.append(f"Название: {info.get('title', 'N/A')}")
    lines.append(f"Канал: {info.get('uploader', 'N/A')}")
    lines.append(f"Длительность: {info.get('duration', 0)} сек")
    lines.append(f"Описание: {(info.get('description') or '')[:100]}...")
    
    # Форматы
    formats = info.get("formats", [])
    if formats:
        lines.append(f"\nДоступно форматов: {len(formats)}")
        # Покажем несколько примеров
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
    url: Optional[str] = typer.Argument(None, help="Ссылка на видео или плейлист"),
    output: Optional[Path] = typer.Option(None, "--output", "-o", help="Папка назначения"),
    urls_file: Optional[Path] = typer.Option(None, "--urls-file", help="Файл со списком ссылок (по одной в строке)", rich_help_panel="Дополнительно"),
    audio_only: Optional[bool] = typer.Option(None, "--audio-only", help="Скачать только аудио"),
    audio_format: Optional[str] = typer.Option(None, "--audio-format", help="Формат аудио (m4a/mp3/opus)"),
    video_format: Optional[str] = typer.Option(None, "--video-format", help="Контейнер видео (mp4/webm)"),
    quality: Optional[str] = typer.Option(None, "--quality", help="Качество/пресет (best/1080p/720p/audio)"),
    name: Optional[str] = typer.Option(None, "--name", help="Шаблон имени файла"),
    subtitles: Optional[list[str]] = typer.Option(None, "--subtitles", help="Языки субтитров"),
    proxy: Optional[str] = typer.Option(None, "--proxy", help="Прокси URL"),
    retry: Optional[int] = typer.Option(None, "--retry", help="Количество повторов при ошибках"),
    retry_delay: Optional[float] = typer.Option(None, "--retry-delay", help="Задержка между повторами (сек)"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Только показать действия"),
    playlist: bool = typer.Option(False, "--playlist", help="Обработать плейлист целиком"),
    playlist_items: Optional[str] = typer.Option(None, "--playlist-items", help="Номера видео в плейлисте (например '1-3' или '1,3,5')"),
    interactive: bool = typer.Option(False, "--interactive", "-i", help="Диалоговый выбор качества перед загрузкой (для одного URL)"),
    pause_between: bool = typer.Option(False, "--pause-between", help="Включить возможность паузы между видео в плейлисте (нажмите 'p' для паузы, 'r' для возобновления)", rich_help_panel="Дополнительно"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Подробные логи (DEBUG)"),
):
    """Скачать видео/аудио по указанному URL."""
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(errors="replace")  # type: ignore[call-arg]
        except (AttributeError, TypeError, ValueError, OSError):
            pass
    if hasattr(sys.stderr, "reconfigure"):
        try:
            sys.stderr.reconfigure(errors="replace")  # type: ignore[call-arg]
        except (AttributeError, TypeError, ValueError, OSError):
            pass

    from . import interactive as ia
    from .pause import PauseController

    log_level = "DEBUG" if verbose else "INFO"
    logger = setup_logging(level=log_level)
    
    try:
        # Загрузить конфиг из файла/ENV
        cfg = load_config()
        
        # Собрать CLI-оверрайды (только не-None значения)
        cli_overrides = {}
        if output is not None:
            cli_overrides["output"] = output
        if audio_only is not None:
            cli_overrides["audio_only"] = audio_only
        if audio_format is not None:
            cli_overrides["audio_format"] = audio_format
        if video_format is not None:
            cli_overrides["video_format"] = video_format
        if quality is not None:
            cli_overrides["quality"] = quality
        if name is not None:
            cli_overrides["name_template"] = name
        if subtitles is not None:
            cli_overrides["subtitles"] = subtitles
        if proxy is not None:
            cli_overrides["proxy"] = proxy
        if retry is not None:
            cli_overrides["retry"] = retry
        if retry_delay is not None:
            cli_overrides["retry_delay"] = retry_delay
        
        # Применить оверрайды
        cfg = merge_cli_overrides(cfg, cli_overrides)

        history_available = _initialize_history(cfg, logger)
        
        # Источник ссылок: позиционный аргумент и/или файл со списком
        def read_urls_from_file(fp: Path) -> list[str]:
            if not fp.exists():
                raise FileNotFoundError(f"Файл не найден: {fp}")
            urls: list[str] = []
            for line in fp.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                urls.append(s)
            return urls

        urls: list[str] = []
        if url:
            urls.append(url)
        if urls_file:
            urls.extend(read_urls_from_file(urls_file))
        if not urls:
            # Более дружелюбная диагностика для пустого файла со ссылками
            if urls_file is not None:
                safe_secho(f"Файл со ссылками пуст или не содержит валидных строк: {urls_file}", fg=typer.colors.YELLOW)
            else:
                safe_secho("Нужно указать URL или --urls-file", fg=typer.colors.RED)
            raise typer.Exit(code=2)

        selected_playlist_url: Optional[str] = None
        if interactive and playlist:
            playlist_candidates = [u for u in urls if _looks_like_playlist_url(u)]
            if len(playlist_candidates) > 1:
                safe_echo()
                safe_secho(
                    "Найдено несколько плейлистов в списке ссылок.",
                    fg=typer.colors.YELLOW,
                )
                safe_echo("Выберите плейлист для интерактивной загрузки:")
                for idx, candidate in enumerate(playlist_candidates, start=1):
                    safe_echo(f"  {idx}) {candidate}")
                safe_echo("  0) Отмена")

                while True:
                    choice = typer.prompt("Ваш выбор", default="1")
                    if choice == "0":
                        safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
                        raise typer.Exit(code=0)
                    try:
                        selected_idx = int(choice)
                    except ValueError:
                        selected_idx = -1

                    if 1 <= selected_idx <= len(playlist_candidates):
                        selected_playlist_url = playlist_candidates[selected_idx - 1]
                        break

                    safe_secho("Введите номер из списка.", fg=typer.colors.RED)

                safe_secho(f"Выбран плейлист: {selected_playlist_url}", fg=typer.colors.GREEN)
                if len(playlist_candidates) - 1:
                    safe_secho(
                        "Остальные плейлисты будут пропущены в интерактивном режиме.",
                        fg=typer.colors.YELLOW,
                    )
                ignored_count = len(urls) - len(playlist_candidates)
                if ignored_count:
                    safe_secho(
                        "Прочие ссылки из списка также будут пропущены в интерактивном режиме плейлиста.",
                        fg=typer.colors.YELLOW,
                    )
            elif len(playlist_candidates) == 1:
                selected_playlist_url = playlist_candidates[0]
                if len(urls) > 1:
                    safe_secho(
                        f"Интерактивный режим будет выполнен только для плейлиста: {selected_playlist_url}",
                        fg=typer.colors.CYAN,
                    )

        if selected_playlist_url:
            urls = [selected_playlist_url]

        # Запустить загрузку последовательно
        dl = Downloader(cfg, logger, verbose=verbose)

        def fetch_info_with_prompt(
            target_url: str,
            *,
            title_hint: Optional[str] = None,
            allow_skip: bool = False,
            skip_message: Optional[str] = None,
        ) -> Optional[dict[str, Any]]:
            while True:
                try:
                    return dl.get_info(target_url)
                except NetworkUnavailableError as net_err:
                    decision = _prompt_network_recovery(
                        net_err,
                        context=target_url,
                        title_hint=title_hint,
                    )
                    if decision == "retry":
                        continue
                    if decision == "skip" and allow_skip:
                        if skip_message:
                            safe_secho(skip_message, fg=typer.colors.YELLOW)
                        else:
                            hint = title_hint or target_url
                            safe_secho(
                                f"[SKIP] {hint} — пропущено после сетевой ошибки",
                                fg=typer.colors.YELLOW,
                            )
                        return None
                    safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
                    raise typer.Exit(1) from net_err

        def prompt_history_decision(
            *,
            video_id: Optional[str],
            current_url: str,
            title_hint: Optional[str] = None,
            default_output_dir: Optional[Path] = None,
        ) -> HistoryDecision:
            if not history_available:
                return HistoryDecision(proceed=True)
            try:
                entry = fetch_download(video_id=video_id, url=current_url)
            except Exception as fetch_err:  # noqa: BLE001
                logger.debug("не удалось получить историю для %s: %s", current_url, fetch_err)
                return HistoryDecision(proceed=True)

            if not entry:
                return HistoryDecision(proceed=True)

            if title_hint:
                safe_echo(f"→ {title_hint}")
            _print_history_card(entry)
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
                    logger.debug("не удалось обновить запись истории: %s", update_err)

            if not decision.proceed:
                safe_secho("Загрузка пропущена по истории", fg=typer.colors.CYAN)
            return decision

        preflight_history_decisions: list[HistoryDecision] = []
        if history_available:
            filtered_urls: list[str] = []
            for original_url in urls:
                decision = prompt_history_decision(
                    video_id=_history_identifier(original_url),
                    current_url=original_url,
                    default_output_dir=cfg.output,
                )
                if not decision.proceed:
                    continue
                filtered_urls.append(original_url)
                preflight_history_decisions.append(decision)
            urls = filtered_urls
            if not urls:
                safe_secho(
                    "[OK] Все запрошенные элементы уже скачаны — новых задач нет",
                    fg=typer.colors.CYAN,
                )
                raise typer.Exit(code=0)

        if not preflight_history_decisions and urls:
            preflight_history_decisions = [HistoryDecision(proceed=True) for _ in urls]

        total_files = 0
        failed = 0

        # Инициализировать контроллер пауз если включен режим паузы между видео
        # (либо через CLI флаг, либо через конфиг)
        pause_controller: Optional[PauseController] = None
        use_pause = pause_between or cfg.pause_between_videos
        if use_pause and (playlist or interactive):
            pause_controller = PauseController(
                pause_key=cfg.pause_key or "p",
                resume_key=cfg.resume_key or "r"
            )
            pause_controller.enable()
            safe_secho(
                "⏸  Режим пауз включен: нажмите 'p' во время загрузки для паузы после текущего видео",
                fg=typer.colors.CYAN
            )
        
        for url_index, one_url in enumerate(urls):
            preflight_decision = (
                preflight_history_decisions[url_index]
                if url_index < len(preflight_history_decisions)
                else HistoryDecision(proceed=True)
            )
            current_output_dir = preflight_decision.new_output or cfg.output
            chosen_format: Optional[str] = None
            chosen_label: str = "Лучшее доступное качество"
            file_prefix: Optional[str] = None
            quality_suffix: Optional[str] = None
            overwrite: bool = preflight_decision.overwrite
            custom_name: Optional[str] = None
            # Флаг, чтобы пропустить общий путь после интерактивной поштучной обработки плейлиста
            skip_post_processing: bool = False
            history_video_id: Optional[str] = _history_identifier(one_url)
            
            if interactive:
                if len(urls) > 1:
                    safe_secho("[WARN] Диалоговый выбор качества поддерживается только для одного URL. Флаг --interactive будет проигнорирован.", fg=typer.colors.YELLOW)
                elif playlist:
                    # ПЛЕЙЛИСТ В ИНТЕРАКТИВНОМ РЕЖИМЕ
                    safe_echo("\n" + "═" * 60)
                    safe_secho("⏳ Получение информации о плейлисте...", fg=typer.colors.CYAN, bold=True)
                    safe_echo("Это может занять некоторое время для больших плейлистов.")
                    safe_echo("═" * 60)
                    try:
                        info = fetch_info_with_prompt(
                            one_url,
                            title_hint="Плейлист",
                            allow_skip=True,
                            skip_message="[SKIP] Плейлист пропущен после сетевой ошибки",
                        )
                        if info is None:
                            failed += 1
                            continue
                        entries = info.get("entries") or []
                        if info.get("id"):
                            resolved_id = _history_identifier(str(info.get("id")))
                            if resolved_id:
                                history_video_id = resolved_id
                        
                        if not entries:
                            safe_secho("[WARN] Плейлист пуст, интерактивный режим отключён", fg=typer.colors.YELLOW)
                        else:
                            # Показать информацию о плейлисте
                            ia.show_playlist_info(info)
                            
                            # Выбрать режим
                            mode = ia.choose_playlist_mode()
                            
                            if mode is None:
                                safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
                                continue
                            elif mode == 1:
                                # Единые настройки для всех
                                safe_secho("\n→ Режим: Единые настройки для всех видео", fg=typer.colors.GREEN)
                                
                                safe_secho("\n⏳ Анализ доступных форматов...", fg=typer.colors.CYAN)
                                # Собрать общие доступные качества (пересечение)
                                # Для простоты берём форматы первого видео как базу
                                first_entry = entries[0]
                                # Если в первом элементе нет форматов, запросим отдельной загрузкой
                                first_url = ia.get_entry_url(first_entry)
                                first_info = (
                                    fetch_info_with_prompt(
                                        first_url,
                                        title_hint="Первое видео плейлиста",
                                        allow_skip=True,
                                        skip_message="[SKIP] Пропуск анализа первого видео плейлиста из-за сетевой ошибки",
                                    )
                                    if first_url
                                    else {}
                                )
                                if first_url and first_info is None:
                                    failed += 1
                                    first_info = {}
                                height_to_ext, available_heights = ia.collect_available_heights(
                                    (first_info.get("formats") or [])
                                )
                                
                                # Построить меню
                                quality_options = ia.build_quality_options(height_to_ext, available_heights)
                                chosen_label, chosen_format, target_height = ia.show_quality_menu(quality_options)
                                
                                # Суффикс качества
                                default_suffix = extract_quality_suffix(chosen_format, chosen_label)
                                quality_suffix = ia.configure_filename_suffix(default_suffix)
                                
                                # Нумерация файлов
                                use_numbering, prefix_template = ia.configure_playlist_numbering()
                                
                                # Настройка стратегии fallback для качества
                                strategy = ia.configure_quality_fallback()

                                # Перезапись для плейлиста целиком
                                overwrite_all = ia.ask_overwrite_all()
                                if preflight_decision.overwrite:
                                    overwrite_all = True

                                # Показать итоговую маску и подтвердить
                                example_title = sanitize_filename((first_info or {}).get("title") or entries[0].get("title", "Видео"))
                                example_id = (first_info or {}).get("id") or entries[0].get("id", "ID")
                                
                                confirmed = ia.show_unified_settings_summary(
                                    chosen_label,
                                    quality_suffix,
                                    prefix_template if use_numbering else "",
                                    strategy,
                                    example_title,
                                    example_id
                                )
                                
                                if not confirmed:
                                    safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
                                    continue

                                existing_map, missing_indices = ia.analyze_playlist_progress(current_output_dir, entries)
                                indices_to_download: Optional[set[int]] = None

                                delete_existing = False
                                if existing_map:
                                    selected_indices, delete_existing = ia.prompt_playlist_resume(
                                        entries,
                                        existing_map,
                                        missing_indices,
                                    )

                                    if delete_existing:
                                        safe_secho("Удаляем найденные файлы...", fg=typer.colors.YELLOW)
                                        removed = 0
                                        for files in existing_map.values():
                                            for file_path in files:
                                                try:
                                                    file_path.unlink()
                                                    removed += 1
                                                except FileNotFoundError:
                                                    continue
                                                except OSError as unlink_err:
                                                    logger.warning("Не удалось удалить %s: %s", file_path, unlink_err)
                                                    safe_secho(
                                                        f"[WARN] Не удалось удалить {file_path.name}: {unlink_err}",
                                                        fg=typer.colors.YELLOW,
                                                    )
                                        safe_secho(
                                            f"✓ Удалено файлов: {removed}. Плейлист будет скачан заново.",
                                            fg=typer.colors.CYAN,
                                        )

                                    if selected_indices:
                                        indices_to_download = set(selected_indices)
                                    else:
                                        if delete_existing:
                                            indices_to_download = set(range(1, len(entries) + 1))
                                        else:
                                            safe_secho(
                                                "[OK] Все видео плейлиста уже скачаны — загрузка не требуется",
                                                fg=typer.colors.GREEN,
                                            )
                                            continue
                                else:
                                    indices_to_download = None

                                # Применить настройки ко всем видео плейлиста
                                safe_echo("\n" + "═" * 60)
                                safe_secho(
                                    f"▶ Начинаем загрузку плейлиста ({len(entries)} видео)...",
                                    fg=typer.colors.GREEN,
                                    bold=True,
                                )
                                safe_echo("═" * 60 + "\n")

                                for idx, entry in enumerate(entries, start=1):
                                    if indices_to_download is not None and idx not in indices_to_download:
                                        entry_title_hint = entry.get("title", f"Видео {idx}")
                                        if idx in existing_map:
                                            safe_secho(
                                                f"[SKIP] {entry_title_hint} — уже скачано",
                                                fg=typer.colors.CYAN,
                                            )
                                        else:
                                            safe_secho(
                                                f"[SKIP] {entry_title_hint} — пропущено по выбору",
                                                fg=typer.colors.YELLOW,
                                            )
                                        continue

                                    safe_secho(f"[{idx}/{len(entries)}] Обработка...", fg=typer.colors.CYAN)
                                    entry_url = ia.get_entry_url(entry)
                                    if not entry_url:
                                        safe_secho(f"[WARN] Пропуск: не удалось получить URL для элемента #{idx}", fg=typer.colors.YELLOW)
                                        continue
                                    # Получить полную информацию для подбора качества
                                    entry_title_hint = entry.get("title", f"Видео {idx}")
                                    entry_info = fetch_info_with_prompt(
                                        entry_url,
                                        title_hint=entry_title_hint,
                                        allow_skip=True,
                                        skip_message=(
                                            f"[SKIP] {entry_title_hint} — пропущено из-за сетевой ошибки при анализе"
                                        ),
                                    )
                                    if entry_info is None:
                                        failed += 1
                                        continue
                                    entry_id = entry_info.get("id", entry.get("id", f"{idx}"))
                                    entry_title = entry_info.get("title", entry_title_hint)
                                    entry_fmts = entry_info.get("formats") or []

                                    # Если выбран аудио-только (target_height == -1)
                                    per_entry_format = chosen_format
                                    if isinstance(target_height, int) and target_height >= 0:
                                        h_to_ext, avail_h = ia.collect_available_heights(entry_fmts)
                                        sel_h = find_best_quality_match(avail_h, target_height, strategy=strategy)
                                        if sel_h is None:
                                            # fallback к лучшему доступному
                                            per_entry_format = "bestvideo+bestaudio/best"
                                        else:
                                            ext = h_to_ext.get(sel_h) or "mp4"
                                            aud_ext = "m4a" if ext == "mp4" else "webm"
                                            per_entry_format = (
                                                f"bestvideo[height<={sel_h}][ext={ext}]+bestaudio[ext={aud_ext}]/"
                                                f"best[height<={sel_h}][ext={ext}]/best[height<={sel_h}]"
                                            )

                                    # Префикс с автоинкрементом
                                    file_prefix = None
                                    if use_numbering and prefix_template:
                                        try:
                                            file_prefix = prefix_template.format(N=idx)
                                        except Exception:
                                            file_prefix = f"{idx:02d}_"

                                    # Сформировать опции загрузки для одного видео
                                    single_opts = DownloadOptions(
                                        url=entry_url,
                                        output_dir=current_output_dir,
                                        audio_only=cfg.audio_only,
                                        audio_format=cfg.audio_format,  # type: ignore[arg-type]
                                        video_format=cfg.video_format,  # type: ignore[arg-type]
                                        quality=cfg.quality,  # type: ignore[arg-type]
                                        name_template=cfg.name_template,
                                        subtitles=cfg.subtitles,
                                        proxy=cfg.proxy,
                                        retry=cfg.retry,
                                        retry_delay=cfg.retry_delay,
                                        save_metadata=cfg.save_metadata,
                                        dry_run=dry_run,
                                        playlist=False,  # скачиваем как одиночное видео
                                        playlist_items=None,
                                        custom_format=per_entry_format,
                                        file_prefix=file_prefix,
                                        quality_suffix=quality_suffix,
                                        overwrite=overwrite_all,
                                    )

                                    decision = prompt_history_decision(
                                        video_id=str(entry.get("id")) if entry.get("id") else None,
                                        current_url=entry_url,
                                        title_hint=entry_title,
                                        default_output_dir=single_opts.output_dir,
                                    )
                                    if not decision.proceed:
                                        continue
                                    if decision.new_output:
                                        single_opts.output_dir = decision.new_output
                                    if decision.overwrite:
                                        single_opts.overwrite = True

                                    files: list[Path] = []
                                    download_failed = False
                                    skipped_due_to_network = False
                                    first_attempt = True
                                    while True:
                                        if first_attempt:
                                            safe_secho(
                                                f"  ⏳ Загрузка: {entry_title[:60]}...",
                                                fg=typer.colors.CYAN,
                                            )
                                            first_attempt = False
                                        else:
                                            safe_secho(
                                                f"  ↻ Повтор: {entry_title[:60]}...",
                                                fg=typer.colors.CYAN,
                                            )
                                        try:
                                            files = dl.download(single_opts)
                                            break
                                        except KeyboardInterrupt:
                                            raise
                                        except NetworkUnavailableError as net_err:
                                            decision = _prompt_network_recovery(
                                                net_err,
                                                context=entry_url,
                                                title_hint=entry_title,
                                            )
                                            if decision == "retry":
                                                continue
                                            if decision == "skip":
                                                failed += 1
                                                skipped_due_to_network = True
                                                safe_secho(
                                                    f"  ⚠ [SKIP] {entry_title} — пропущено после сетевой ошибки",
                                                    fg=typer.colors.YELLOW,
                                                )
                                                break
                                            safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
                                            raise typer.Exit(1) from net_err
                                        except Exception:
                                            failed += 1
                                            download_failed = True
                                            logger.exception("Ошибка загрузки %s", entry_url)
                                            safe_secho(f"[ERROR] {entry_title}", fg=typer.colors.RED)
                                            break

                                    if skipped_due_to_network or download_failed:
                                        continue

                                    if not dry_run:
                                        total_files += len(files)
                                    safe_secho(
                                        f"  ✓ [OK] {entry_title}" if (dry_run or files) else f"  ⚠ [WARN] {entry_title} — нет файлов",
                                        fg=typer.colors.GREEN if (dry_run or files) else typer.colors.YELLOW,
                                    )
                                    if not dry_run and not files:
                                        failed += 1
                                    
                                    # Проверить, запрошена ли пауза после этого видео
                                    if pause_controller and pause_controller.is_pause_requested():
                                        pause_controller.wait_if_paused()

                                # После завершения режима с едиными настройками мы уже скачали все элементы
                                # этого плейлиста по одному. Сбросим потенциально протекший префикс и
                                # пометим, что нужно пропустить общий путь ниже по коду.
                                file_prefix = None
                                skip_post_processing = True

                            elif mode == 2:
                                # Настроить каждое отдельно
                                safe_secho("\n→ Режим: Настройка каждого видео отдельно", fg=typer.colors.GREEN)
                                # TODO: Реализовать покадровую настройку
                                
                    except Exception as e:
                        logger.warning("Не удалось обработать плейлист: %s — продолжим с настройками по умолчанию", e)
                else:
                    # ОДИНОЧНОЕ ВИДЕО В ИНТЕРАКТИВНОМ РЕЖИМЕ
                    safe_echo("\n" + "═" * 60)
                    safe_secho("⏳ Получение информации о видео...", fg=typer.colors.CYAN, bold=True)
                    safe_echo("═" * 60)
                    try:
                        info = fetch_info_with_prompt(
                            one_url,
                            title_hint="Видео",
                            allow_skip=True,
                            skip_message="[SKIP] Видео пропущено после сетевой ошибки",
                        )
                        if info is None:
                            failed += 1
                            continue
                        video_id = info.get("id", "unknown")
                        if info.get("id"):
                            resolved_id = _history_identifier(str(info.get("id")))
                            if resolved_id:
                                history_video_id = resolved_id
                        video_title = info.get("title", "unknown")
                        
                        fmts = info.get("formats") or []
                        # Собираем уникальные высоты и предпочтительный контейнер
                        height_to_ext, available_heights = ia.collect_available_heights(fmts)
                        
                        # Построить меню качества
                        quality_options = ia.build_quality_options(height_to_ext, available_heights)
                        
                        # Показать меню и получить выбор
                        safe_echo("\n" + "═" * 60)
                        safe_echo("ШАГ 1: Выберите качество")
                        safe_echo("═" * 60)
                        chosen_label, chosen_format, _ = ia.show_quality_menu(quality_options)
                        
                        # Определить суффикс качества
                        default_suffix = extract_quality_suffix(chosen_format, chosen_label)
                        
                        # Построить предлагаемое имя файла
                        safe_title = sanitize_filename(video_title)
                        # Определить вероятное расширение
                        if "audio" in chosen_label.lower():
                            ext_hint = "m4a"
                        else:
                            # Извлечь из формата или использовать дефолт
                            ext_match = re.search(r'ext=(\w+)', chosen_format)
                            ext_hint = ext_match.group(1) if ext_match else "mp4"
                        
                        # ШАГ 2: Настройка имени файла
                        safe_echo("\n" + "═" * 60)
                        safe_echo("ШАГ 2: Настройка имени файла")
                        safe_echo("═" * 60)
                        safe_echo(f"Название: {safe_title} [{video_id}]")
                        safe_echo(f"Расширение: .{ext_hint}")
                        safe_echo(f"Предложенный суффикс качества: {default_suffix}")
                        
                        # Спросить про суффикс качества
                        safe_echo("\nДобавить суффикс качества к имени файла?")
                        safe_echo(f"  1) Да, добавить '{default_suffix}'")
                        safe_echo("  2) Да, но указать свой суффикс")
                        safe_echo("  3) Нет, без суффикса")
                        
                        suffix_choice = typer.prompt("Выберите вариант", default="1")
                        
                        if suffix_choice == "2":
                            custom_suffix = typer.prompt("Введите суффикс (например, '_720p' или '_hd')", default=default_suffix)
                            quality_suffix = custom_suffix if custom_suffix else None
                        elif suffix_choice == "3":
                            quality_suffix = None
                        else:
                            quality_suffix = default_suffix
                        
                        # Построить полное имя с суффиксом (если есть)
                        name_with_suffix = f"{safe_title} [{video_id}]{quality_suffix or ''}.{ext_hint}"
                        
                        safe_echo(f"\nИтоговое имя: {name_with_suffix}")
                        safe_echo("\nДополнительные опции:")
                        safe_echo("  1) Использовать как есть")
                        safe_echo("  2) Добавить префикс (например, '01_')")
                        safe_echo("  3) Изменить имя полностью")
                        
                        name_choice = typer.prompt("Выберите действие", default="1")
                        
                        if name_choice == "2":
                            prefix = typer.prompt("Введите префикс (например, '01_')", default="")
                            if prefix:
                                file_prefix = prefix
                                safe_echo(f"Итоговое имя: {prefix}{name_with_suffix}")
                        elif name_choice == "3":
                            new_name = typer.prompt("Введите полное имя файла (с расширением)", default=name_with_suffix)
                            custom_name = sanitize_filename(new_name)
                            quality_suffix = None  # Отключить автосуффикс если полное имя задано
                            safe_echo(f"Итоговое имя: {custom_name}")
                        else:
                            safe_echo(f"Будет использовано: {name_with_suffix}")
                        
                        # ШАГ 3: Проверка существующих файлов
                        existing = find_existing_files(current_output_dir, video_id)
                        if existing:
                            safe_echo("\n" + "═" * 60)
                            safe_secho("⚠ ВНИМАНИЕ: Найдены существующие файлы этого видео:", fg=typer.colors.YELLOW)
                            safe_echo("═" * 60)
                            for i, ex_file in enumerate(existing, start=1):
                                size_mb = ex_file.stat().st_size / (1024 * 1024)
                                safe_echo(f"  {i}) {ex_file.name} ({size_mb:.1f} МБ)")
                            
                            overwrite_choice = typer.prompt(
                                "\nПерезаписать существующие файлы? (y/n)",
                                default="n"
                            )
                            if overwrite_choice.lower() in ("y", "yes", "д", "да"):
                                overwrite = True
                                safe_secho("✓ Существующие файлы будут перезаписаны", fg=typer.colors.GREEN)
                            else:
                                safe_secho("✓ Загрузка будет пропущена, если файл уже существует", fg=typer.colors.CYAN)
                        
                    except Exception as e:
                        logger.warning("Не удалось получить форматы: %s — продолжим с настройками по умолчанию", e)

            # Если мы уже обработали плейлист поштучно в интерактивном режиме —
            # пропускаем общий путь, чтобы не запустить повторную загрузку всего плейлиста.
            if skip_post_processing:
                continue

            # Определить итоговый шаблон имени
            final_name_template = cfg.name_template
            if custom_name:
                # Пользователь задал полное имя - используем его как есть
                final_name_template = custom_name
            
            # Если включен режим пауз и это плейлист (не интерактивный) — загружаем поштучно
            if pause_controller and playlist and not interactive:
                # Получить информацию о плейлисте
                try:
                    info = fetch_info_with_prompt(
                        one_url,
                        title_hint="Плейлист",
                        allow_skip=True,
                        skip_message="[SKIP] Плейлист пропущен после сетевой ошибки",
                    )
                    if info is None:
                        failed += 1
                        continue
                    entries = info.get("entries") or []
                    if entries:
                        safe_secho(f"▶ Плейлист: {len(entries)} видео", fg=typer.colors.GREEN)
                        for idx, entry in enumerate(entries, start=1):
                            entry_url = ia.get_entry_url(entry)
                            if not entry_url:
                                safe_secho(f"[WARN] Пропуск элемента #{idx}", fg=typer.colors.YELLOW)
                                continue
                            
                            entry_title = entry.get("title", f"Видео {idx}")
                            
                            single_opts = DownloadOptions(
                                url=entry_url,
                                output_dir=current_output_dir,
                                audio_only=cfg.audio_only,
                                audio_format=cfg.audio_format,  # type: ignore[arg-type]
                                video_format=cfg.video_format,  # type: ignore[arg-type]
                                quality=cfg.quality,  # type: ignore[arg-type]
                                name_template=final_name_template,
                                subtitles=cfg.subtitles,
                                proxy=cfg.proxy,
                                retry=cfg.retry,
                                retry_delay=cfg.retry_delay,
                                save_metadata=cfg.save_metadata,
                                dry_run=dry_run,
                                playlist=False,
                                playlist_items=None,
                                custom_format=chosen_format,
                                file_prefix=file_prefix,
                                quality_suffix=quality_suffix if not custom_name else None,
                                overwrite=overwrite,
                            )
                            
                            entry_history_id = (
                                _history_identifier(str(entry.get("id"))) if entry.get("id") else None
                            )
                            decision = prompt_history_decision(
                                video_id=entry_history_id,
                                current_url=entry_url,
                                title_hint=entry_title,
                                default_output_dir=single_opts.output_dir,
                            )
                            if not decision.proceed:
                                continue
                            if decision.new_output:
                                single_opts.output_dir = decision.new_output
                            if decision.overwrite:
                                single_opts.overwrite = True

                            files: list[Path] = []
                            download_failed = False
                            skipped_due_to_network = False
                            first_attempt = True

                            while True:
                                if first_attempt:
                                    safe_secho(
                                        f"[{idx}/{len(entries)}] ⏳ Загрузка: {entry_title[:60]}...",
                                        fg=typer.colors.CYAN,
                                    )
                                    first_attempt = False
                                else:
                                    safe_secho(
                                        f"[{idx}/{len(entries)}] ↻ Повтор: {entry_title[:60]}...",
                                        fg=typer.colors.CYAN,
                                    )

                                try:
                                    files = dl.download(single_opts)
                                    break
                                except KeyboardInterrupt:
                                    raise
                                except NetworkUnavailableError as net_err:
                                    decision = _prompt_network_recovery(
                                        net_err,
                                        context=entry_url,
                                        title_hint=entry_title,
                                    )
                                    if decision == "retry":
                                        continue
                                    if decision == "skip":
                                        failed += 1
                                        skipped_due_to_network = True
                                        safe_secho(
                                            f"  ⚠ [SKIP] {entry_title} — пропущено после сетевой ошибки",
                                            fg=typer.colors.YELLOW,
                                        )
                                        break
                                    safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
                                    raise typer.Exit(1) from net_err
                                except Exception:
                                    failed += 1
                                    download_failed = True
                                    logger.exception("Ошибка загрузки %s", entry_url)
                                    safe_secho(f"[ERROR] {entry_title}", fg=typer.colors.RED)
                                    break

                            if skipped_due_to_network or download_failed:
                                continue

                            if not dry_run:
                                total_files += len(files)
                            safe_secho(
                                f"  ✓ [OK] {entry_title}" if (dry_run or files) else f"  ⚠ [WARN] {entry_title} — нет файлов",
                                fg=typer.colors.GREEN if (dry_run or files) else typer.colors.YELLOW,
                            )
                            if not dry_run and not files:
                                failed += 1
                            
                            # Проверить паузу после видео
                            if pause_controller.is_pause_requested():
                                pause_controller.wait_if_paused()
                        
                        # Пропустить стандартный путь загрузки плейлиста
                        continue
                except Exception as e:
                    logger.warning("Не удалось разобрать плейлист для поштучной загрузки: %s — пробуем обычный путь", e)
            
            opts = DownloadOptions(
                url=one_url,
                output_dir=current_output_dir,
                audio_only=cfg.audio_only,
                audio_format=cfg.audio_format,  # type: ignore[arg-type]
                video_format=cfg.video_format,  # type: ignore[arg-type]
                quality=cfg.quality,  # type: ignore[arg-type]
                name_template=final_name_template,
                subtitles=cfg.subtitles,
                proxy=cfg.proxy,
                retry=cfg.retry,
                retry_delay=cfg.retry_delay,
                save_metadata=cfg.save_metadata,
                dry_run=dry_run,
                playlist=playlist,
                playlist_items=playlist_items,
                custom_format=chosen_format,
                file_prefix=file_prefix,
                quality_suffix=quality_suffix if not custom_name else None,
                overwrite=overwrite,
            )
            decision = preflight_decision
            if decision is None:
                decision = prompt_history_decision(
                    video_id=history_video_id,
                    current_url=one_url,
                    default_output_dir=current_output_dir,
                )
            if not decision.proceed:
                continue
            if decision.new_output:
                opts.output_dir = decision.new_output
            if decision.overwrite:
                overwrite = True
                opts.overwrite = True

            files: list[Path] = []
            download_failed = False
            skipped_due_to_network = False
            first_attempt = True

            while True:
                if not interactive:
                    if first_attempt:
                        safe_secho(f"\n⏳ Загрузка: {one_url}", fg=typer.colors.CYAN)
                    else:
                        safe_secho(f"\n↻ Повтор: {one_url}", fg=typer.colors.CYAN)

                try:
                    files = dl.download(opts)
                    break
                except KeyboardInterrupt:
                    raise
                except NetworkUnavailableError as net_err:
                    decision = _prompt_network_recovery(net_err, context=one_url)
                    if decision == "retry":
                        continue
                    if decision == "skip":
                        failed += 1
                        skipped_due_to_network = True
                        safe_secho(f"[SKIP] {one_url} — пропущено после сетевой ошибки", fg=typer.colors.YELLOW)
                        break
                    safe_secho("✗ Остановка по запросу пользователя", fg=typer.colors.RED)
                    raise typer.Exit(1) from net_err
                except Exception as e:  # noqa: BLE001
                    failed += 1
                    download_failed = True
                    logger.exception("Ошибка загрузки %s", one_url)
                    safe_secho(f"[ERROR] {one_url} — {e}", fg=typer.colors.RED)
                    break
                finally:
                    first_attempt = False

            if skipped_due_to_network or download_failed:
                continue

            if not dry_run:
                total_files += len(files)

            # Цветной вывод результата
            if dry_run or files:
                safe_secho(f"✓ [OK] {one_url}", fg=typer.colors.GREEN)
            else:
                safe_secho(f"⚠ [WARN] {one_url} — нет файлов", fg=typer.colors.YELLOW)

            if not dry_run and not files:
                failed += 1
        
        # Отключить контроллер пауз после завершения всех загрузок
        if pause_controller:
            pause_controller.disable()

        if dry_run:
            safe_secho("[OK] Dry-run завершён (файлы не скачаны)", fg=typer.colors.GREEN)
            sys.exit(0)

        if failed == 0 and total_files > 0:
            safe_secho(f"[OK] Скачано файлов: {total_files}", fg=typer.colors.GREEN)
            sys.exit(0)
        elif failed > 0 and total_files > 0:
            safe_secho(f"[WARN] Скачано файлов: {total_files}, ошибок: {failed}", fg=typer.colors.YELLOW)
            sys.exit(2)
        elif failed > 0 and total_files == 0:
            safe_secho("✗ Ошибка загрузки (ни один файл не скачан)", fg=typer.colors.RED)
            sys.exit(1)
        else:
            safe_secho("⚠ Файлы не скачаны", fg=typer.colors.YELLOW)
            sys.exit(2)
    
    except KeyboardInterrupt:
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        sys.exit(1)
    except typer.Exit:
        # Позволяем корректным выходам Typer завершаться без лишнего логирования стека
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки")
        safe_secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        sys.exit(1)


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
                    sys.exit(2)
                safe_secho("✗ Прервано по запросу пользователя", fg=typer.colors.RED)
                sys.exit(1)

        if json_output:
            safe_echo(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            safe_echo(_format_info(info))
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        sys.exit(1)
    except Exception as e:
        logger.exception("Ошибка получения метаданных")
        safe_secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        sys.exit(1)


def main() -> None:
    app()
