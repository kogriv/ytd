"""Помощники для интерактивного режима CLI."""

from __future__ import annotations

import re
from typing import Any, Optional
from pathlib import Path

import typer

from .cli import safe_echo, safe_secho

from .utils import (
    extract_quality_suffix,
    sanitize_filename,
    find_existing_files,
    find_best_quality_match,
)


def collect_available_heights(formats: list[dict[str, Any]]) -> tuple[dict[int, str], list[int]]:
    """Собрать доступные высоты видео и предпочтительные контейнеры.
    
    Returns:
        (height_to_ext, available_heights_sorted)
    """
    height_to_ext: dict[int, str] = {}
    for f in formats:
        try:
            h = f.get("height")
            vcodec = f.get("vcodec")
            ext = f.get("ext")
            if vcodec and vcodec != "none" and isinstance(h, int):
                # предпочитаем mp4, иначе webm
                if h not in height_to_ext or (ext == "mp4" and height_to_ext[h] != "mp4"):
                    height_to_ext[h] = ext or "mp4"
        except Exception:
            continue
    available_heights = sorted(height_to_ext.keys(), reverse=True)
    return height_to_ext, available_heights


def build_quality_options(
    height_to_ext: dict[int, str],
    available_heights: list[int],
    max_options: int = 8
) -> list[tuple[str, str, Optional[int]]]:
    """Построить список опций качества для меню.
    
    Returns:
        List of (label, format_string, target_height)
    """
    options: list[tuple[str, str, Optional[int]]] = []
    
    # Лучшее доступное
    options.append(("Лучшее доступное качество", "bestvideo+bestaudio/best", None))
    
    # Популярные высоты
    for h in available_heights:
        ext = height_to_ext[h]
        aud_ext = "m4a" if ext == "mp4" else "webm"
        fmt = (
            f"bestvideo[height<={h}][ext={ext}]+bestaudio[ext={aud_ext}]/"
            f"best[height<={h}][ext={ext}]/best[height<={h}]"
        )
        options.append((f"Видео {ext.upper()} {h}p", fmt, h))
        if len(options) >= max_options:
            break
    
    # Аудио
    options.append(("Только аудио (m4a)", "bestaudio[ext=m4a]/bestaudio", -1))  # -1 = audio marker
    
    return options


def show_quality_menu(options: list[tuple[str, str, Optional[int]]]) -> tuple[str, str, Optional[int]]:
    """Показать меню выбора качества и вернуть выбранный вариант.
    
    Returns:
        (label, format_string, target_height)
    """
    safe_echo("\n" + "═" * 60)
    safe_echo("Выберите качество:")
    safe_echo("═" * 60)
    for i, (label, _, _) in enumerate(options, start=1):
        safe_echo(f"  {i}) {label}")
    
    choice = typer.prompt("Номер варианта", default="1")
    try:
        idx = int(str(choice).strip())
        if 1 <= idx <= len(options):
            return options[idx - 1]
        else:
            safe_secho("Некорректный выбор — будет использовано лучшее доступное", fg=typer.colors.YELLOW)
            return options[0]
    except Exception:
        safe_secho("Некорректный ввод — будет использовано лучшее доступное", fg=typer.colors.YELLOW)
        return options[0]


def configure_filename_suffix(default_suffix: str) -> Optional[str]:
    """Диалог настройки суффикса качества для имени файла."""
    safe_echo("\nДобавить суффикс качества к имени файла?")
    safe_echo(f"  1) Да, добавить '{default_suffix}'")
    safe_echo("  2) Да, но указать свой суффикс")
    safe_echo("  3) Нет, без суффикса")
    
    suffix_choice = typer.prompt("Выберите вариант", default="1")
    
    if suffix_choice == "2":
        custom_suffix = typer.prompt("Введите суффикс (например, '_720p' или '_hd')", default=default_suffix)
        return custom_suffix if custom_suffix else None
    elif suffix_choice == "3":
        return None
    else:
        return default_suffix


def configure_filename_prefix() -> tuple[Optional[str], bool, Optional[str]]:
    """Диалог настройки префикса для имени файла.
    
    Returns:
        (prefix, custom_name_used, custom_name)
    """
    safe_echo("\nДополнительные опции:")
    safe_echo("  1) Использовать как есть")
    safe_echo("  2) Добавить префикс (например, '01_')")
    safe_echo("  3) Изменить имя полностью")
    
    name_choice = typer.prompt("Выберите действие", default="1")
    
    if name_choice == "2":
        prefix = typer.prompt("Введите префикс (например, '01_')", default="")
        return (prefix if prefix else None, False, None)
    elif name_choice == "3":
        # Для полного имени вернем флаг, что используется кастомное имя
        return (None, True, None)  # custom_name будет установлено в вызывающем коде
    else:
        return (None, False, None)


def check_existing_files_dialog(output_dir: Path, video_id: str) -> bool:
    """Проверить существующие файлы и спросить про перезапись.
    
    Returns:
        True если нужно перезаписать, False иначе
    """
    existing = find_existing_files(output_dir, video_id)
    if not existing:
        return False
    
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
        safe_secho("✓ Существующие файлы будут перезаписаны", fg=typer.colors.GREEN)
        return True
    else:
        safe_secho("✓ Загрузка будет пропущена, если файл уже существует", fg=typer.colors.CYAN)
        return False


def show_playlist_info(playlist_info: dict[str, Any]) -> None:
    """Показать информацию о плейлисте и список видео."""
    title = playlist_info.get("title", "Неизвестный плейлист")
    entries = playlist_info.get("entries") or []
    
    safe_echo("\n" + "═" * 60)
    safe_secho(f"Обнаружен плейлист: \"{title}\" ({len(entries)} видео)", fg=typer.colors.CYAN, bold=True)
    safe_echo("═" * 60)
    
    # Показать первые 10 видео
    for i, entry in enumerate(entries[:10], start=1):
        video_title = entry.get("title", "Без названия")
        duration = entry.get("duration")
        dur_str = f"{int(duration // 60)}:{int(duration % 60):02d}" if duration else "?"
        safe_echo(f"  {i:2d}) {video_title} ({dur_str})")
    
    if len(entries) > 10:
        safe_echo(f"  ... и ещё {len(entries) - 10} видео")
    
    safe_echo("═" * 60)


def choose_playlist_mode() -> Optional[int]:
    """Выбрать режим настройки плейлиста.
    
    Returns:
        1 - единые настройки для всех
        2 - настроить каждое отдельно
        None - отмена
    """
    safe_echo("\nВыберите режим настройки:")
    safe_echo("  1) Единые настройки для всех видео (быстро, рекомендуется)")
    safe_echo("  2) Настроить каждое видео отдельно (долго, гибко)")
    safe_echo("  3) Отмена")
    
    choice = typer.prompt("Ваш выбор", default="1")
    
    if choice == "1":
        return 1
    elif choice == "2":
        return 2
    elif choice == "3":
        return None
    else:
        safe_secho("Некорректный выбор, используем единые настройки", fg=typer.colors.YELLOW)
        return 1


def configure_playlist_numbering() -> tuple[bool, str]:
    """Настроить нумерацию файлов плейлиста.
    
    Returns:
        (use_numbering, prefix_template)
        prefix_template может быть "{N:02d}_" для автоинкремента или пустая строка
    """
    safe_echo("\nДобавить номера к именам файлов?")
    safe_echo("  1) Да, с автоинкрементом (01_, 02_, 03_...)")
    safe_echo("  2) Да, с пользовательским шаблоном префикса")
    safe_echo("  3) Нет")
    
    choice = typer.prompt("Ваш выбор", default="1")
    
    if choice == "1":
        return (True, "{N:02d}_")
    elif choice == "2":
        template = typer.prompt(
            "Введите шаблон префикса (используйте {N} для номера, например 'Видео_{N:03d}_')",
            default="{N:02d}_"
        )
        return (True, template)
    else:
        return (False, "")


def configure_quality_fallback() -> str:
    """Спросить стратегию подбора качества при отсутствии целевого.

    Стратегии:
      1) эконом — сначала максимально возможное НЕ ВЫШЕ выбранного,
                  если нет — минимально возможное НЕ НИЖЕ выбранного (рекомендуется)
      2) богато — сначала максимально возможное НЕ НИЖЕ выбранного,
                  если нет — максимально возможное НЕ ВЫШЕ выбранного

    Returns:
        "econom" или "rich"
    """
    safe_echo("\nЕсли выбранное качество недоступно для некоторых видео:")
    safe_echo("  1) эконом — сначала ≤ выбранного, если нет — ≥ выбранного (рекомендуется)")
    safe_echo("  2) богато — сначала ≥ выбранного, если нет — ≤ выбранного")

    choice = typer.prompt("Ваш выбор", default="1")

    return "rich" if choice == "2" else "econom"


def show_unified_settings_summary(
    quality_label: str,
    quality_suffix: Optional[str],
    prefix_template: str,
    strategy: str,
    example_title: str,
    example_id: str
) -> bool:
    """Показать итоговую маску и примеры, спросить подтверждение.
    
    Returns:
        True если пользователь подтвердил, False если отменил
    """
    safe_echo("\n" + "═" * 60)
    safe_secho("Итоговые настройки для плейлиста:", fg=typer.colors.GREEN, bold=True)
    safe_echo("═" * 60)
    safe_echo(f"Качество: {quality_label}")
    safe_echo(f"Суффикс качества: {quality_suffix or '(нет)'}")
    safe_echo(f"Префикс/нумерация: {prefix_template or '(нет)'}")
    strategy_text = (
        "эконом — сначала ≤ выбранного, если нет — ≥ выбранного"
        if strategy != "rich"
        else "богато — сначала ≥ выбранного, если нет — ≤ выбранного"
    )
    safe_echo(f"Если качество недоступно: {strategy_text}")
    
    # Построить пример имени
    suffix_part = quality_suffix or ""
    prefix_part = prefix_template.replace("{N:02d}", "01").replace("{N:03d}", "001").replace("{N}", "1")
    example_name = f"{prefix_part}{example_title} [{example_id}]{suffix_part}.mp4"
    
    safe_echo(f"\nПример имени файла:")
    safe_echo(f"  {example_name}")
    
    confirm = typer.prompt("\nНачать загрузку? (y/n)", default="y")
    return confirm.lower() in ("y", "yes", "д", "да")


def ask_overwrite_all() -> bool:
    """Спросить, нужно ли перезаписывать существующие файлы для всего плейлиста."""
    choice = typer.prompt("Перезаписывать существующие файлы в плейлисте? (y/n)", default="n")
    return choice.lower() in ("y", "yes", "д", "да")


def analyze_playlist_progress(
    output_dir: Path,
    entries: list[dict[str, Any]],
) -> tuple[dict[int, list[Path]], list[int]]:
    """Определить, какие элементы плейлиста уже скачаны."""

    existing: dict[int, list[Path]] = {}
    missing: list[int] = []

    for idx, entry in enumerate(entries, start=1):
        video_id = entry.get("id")
        if not video_id:
            missing.append(idx)
            continue

        found = find_existing_files(output_dir, video_id)
        if found:
            existing[idx] = found
        else:
            missing.append(idx)

    return existing, missing


def _parse_selection_mask(mask: str, total: int) -> list[int]:
    """Разобрать строку с выбором индексов плейлиста."""

    if total <= 0:
        return []

    mask = mask.strip()
    if not mask:
        raise ValueError("пустой ввод")

    tokens = [token.strip() for token in mask.replace(";", ",").split(",") if token.strip()]
    if not tokens:
        raise ValueError("пустой ввод")

    result: set[int] = set()

    for token in tokens:
        lowered = token.lower()
        if lowered in {"all", "все"}:
            return list(range(1, total + 1))

        if "-" in token:
            start_raw, end_raw = token.split("-", 1)
            start_raw = start_raw.strip()
            end_raw = end_raw.strip()

            start = 1 if start_raw == "" else int(start_raw)
            end = total if end_raw == "" else int(end_raw)

            if start < 1 or end < 1 or start > total or end > total:
                raise ValueError("диапазон вне допустимых пределов")
            if start > end:
                raise ValueError("начало диапазона больше конца")

            for value in range(start, end + 1):
                result.add(value)
            continue

        value = int(token)
        if value < 1 or value > total:
            raise ValueError("номер вне диапазона")
        result.add(value)

    if not result:
        raise ValueError("не выбрано ни одного видео")

    return sorted(result)


def _prompt_manual_selection(total: int, default_indices: list[int]) -> list[int]:
    """Запросить у пользователя явный список видео для скачивания."""

    default_mask = ",".join(str(i) for i in default_indices) if default_indices else "all"

    safe_echo("\nВыбор вручную: укажите номера видео через запятую.")
    safe_echo("Поддерживаются диапазоны (например, '3-7'), записи вида '5-' (с 5-го до конца), '-4' (с начала до 4-го) и 'all'.")

    while True:
        user_input = typer.prompt("Номера/диапазоны", default=default_mask)
        try:
            selection = _parse_selection_mask(user_input, total)
        except ValueError as exc:
            safe_secho(f"[ERROR] {exc}", fg=typer.colors.RED)
            continue

        if not selection:
            safe_secho("[WARN] Не выбрано ни одного видео", fg=typer.colors.YELLOW)
            continue

        return selection


def prompt_playlist_resume(
    entries: list[dict[str, Any]],
    existing_map: dict[int, list[Path]],
    missing_indices: list[int],
) -> tuple[list[int], bool]:
    """Показать пользователю опции продолжения скачивания плейлиста."""

    total = len(entries)
    if total == 0:
        return [], False

    if not existing_map:
        return list(range(1, total + 1)), False

    safe_echo("\n" + "═" * 60)
    safe_secho(
        f"Найдено уже скачанных видео: {len(existing_map)}",
        fg=typer.colors.CYAN,
    )
    safe_echo("═" * 60)

    for idx in sorted(existing_map):
        entry = entries[idx - 1] if idx - 1 < len(entries) else {}
        title = entry.get("title", f"Видео {idx}")
        safe_echo(f"  {idx:2d}) {title} — файлов: {len(existing_map[idx])}")

    safe_echo("═" * 60)

    default_choice = "1"
    if missing_indices:
        next_index = missing_indices[0]
        safe_echo(f"По умолчанию будет продолжено с видео #{next_index}.")
        safe_echo("Доступные действия:")
        safe_echo("  1) Продолжить с указанного видео")
        safe_echo("  2) Удалить найденные файлы и скачать плейлист заново")
        safe_echo("  3) Выбрать вручную, какие видео скачать")
    else:
        safe_echo("Все видео из плейлиста уже присутствуют в папке загрузки.")
        safe_echo("Выберите действие:")
        safe_echo("  1) Пропустить загрузку")
        safe_echo("  2) Удалить найденные файлы и скачать плейлист заново")
        safe_echo("  3) Выбрать вручную, какие видео скачать")

    while True:
        choice = typer.prompt("Ваш выбор", default=default_choice)
        if choice == "1":
            if missing_indices:
                return list(range(missing_indices[0], total + 1)), False
            return [], False
        if choice == "2":
            return list(range(1, total + 1)), True
        if choice == "3":
            selection = _prompt_manual_selection(total, missing_indices)
            return selection, False

        safe_secho("Введите 1, 2 или 3", fg=typer.colors.RED)


def get_entry_url(entry: dict[str, Any]) -> Optional[str]:
    """Получить URL конкретного видео из элемента плейлиста."""

    candidates = (
        entry.get("original_url"),
        entry.get("webpage_url"),
        entry.get("url"),
    )
    for candidate in candidates:
        if candidate:
            return str(candidate)
    return None
