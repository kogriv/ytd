from __future__ import annotations

import sys
import json
import re
from pathlib import Path
from typing import Optional, Any, Iterable
from urllib.parse import urlparse, parse_qs

import typer

from .config import load_config, merge_cli_overrides
from .downloader import Downloader
from .logging import setup_logging
from .types import DownloadOptions
from .utils import find_existing_files, extract_quality_suffix, sanitize_filename, find_best_quality_match
from . import interactive as ia
from .pause import PauseController

app = typer.Typer(no_args_is_help=True, add_completion=False, help="Простой загрузчик YouTube на базе yt-dlp")


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
                typer.secho(f"Файл со ссылками пуст или не содержит валидных строк: {urls_file}", fg=typer.colors.YELLOW)
            else:
                typer.secho("Нужно указать URL или --urls-file", fg=typer.colors.RED)
            raise typer.Exit(code=2)

        selected_playlist_url: Optional[str] = None
        if interactive and playlist:
            playlist_candidates = [u for u in urls if _looks_like_playlist_url(u)]
            if len(playlist_candidates) > 1:
                typer.echo()
                typer.secho(
                    "Найдено несколько плейлистов в списке ссылок.",
                    fg=typer.colors.YELLOW,
                )
                typer.echo("Выберите плейлист для интерактивной загрузки:")
                for idx, candidate in enumerate(playlist_candidates, start=1):
                    typer.echo(f"  {idx}) {candidate}")
                typer.echo("  0) Отмена")

                while True:
                    choice = typer.prompt("Ваш выбор", default="1")
                    if choice == "0":
                        typer.secho("Загрузка отменена", fg=typer.colors.YELLOW)
                        raise typer.Exit(code=0)
                    try:
                        selected_idx = int(choice)
                    except ValueError:
                        selected_idx = -1

                    if 1 <= selected_idx <= len(playlist_candidates):
                        selected_playlist_url = playlist_candidates[selected_idx - 1]
                        break

                    typer.secho("Введите номер из списка.", fg=typer.colors.RED)

                typer.secho(f"Выбран плейлист: {selected_playlist_url}", fg=typer.colors.GREEN)
                if len(playlist_candidates) - 1:
                    typer.secho(
                        "Остальные плейлисты будут пропущены в интерактивном режиме.",
                        fg=typer.colors.YELLOW,
                    )
                ignored_count = len(urls) - len(playlist_candidates)
                if ignored_count:
                    typer.secho(
                        "Прочие ссылки из списка также будут пропущены в интерактивном режиме плейлиста.",
                        fg=typer.colors.YELLOW,
                    )
            elif len(playlist_candidates) == 1:
                selected_playlist_url = playlist_candidates[0]
                if len(urls) > 1:
                    typer.secho(
                        f"Интерактивный режим будет выполнен только для плейлиста: {selected_playlist_url}",
                        fg=typer.colors.CYAN,
                    )

        if selected_playlist_url:
            urls = [selected_playlist_url]

        # Запустить загрузку последовательно
        dl = Downloader(cfg, logger, verbose=verbose)
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
            typer.secho(
                "⏸  Режим пауз включен: нажмите 'p' во время загрузки для паузы после текущего видео",
                fg=typer.colors.CYAN
            )
        
        for one_url in urls:
            chosen_format: Optional[str] = None
            chosen_label: str = "Лучшее доступное качество"
            file_prefix: Optional[str] = None
            quality_suffix: Optional[str] = None
            overwrite: bool = False
            custom_name: Optional[str] = None
            # Флаг, чтобы пропустить общий путь после интерактивной поштучной обработки плейлиста
            skip_post_processing: bool = False
            
            if interactive:
                if len(urls) > 1:
                    typer.secho("[WARN] Диалоговый выбор качества поддерживается только для одного URL. Флаг --interactive будет проигнорирован.", fg=typer.colors.YELLOW)
                elif playlist:
                    # ПЛЕЙЛИСТ В ИНТЕРАКТИВНОМ РЕЖИМЕ
                    typer.echo("\n" + "═" * 60)
                    typer.secho("⏳ Получение информации о плейлисте...", fg=typer.colors.CYAN, bold=True)
                    typer.echo("Это может занять некоторое время для больших плейлистов.")
                    typer.echo("═" * 60)
                    try:
                        info = dl.get_info(one_url)
                        entries = info.get("entries") or []
                        
                        if not entries:
                            typer.secho("[WARN] Плейлист пуст, интерактивный режим отключён", fg=typer.colors.YELLOW)
                        else:
                            # Показать информацию о плейлисте
                            ia.show_playlist_info(info)
                            
                            # Выбрать режим
                            mode = ia.choose_playlist_mode()
                            
                            if mode is None:
                                typer.secho("Загрузка отменена", fg=typer.colors.YELLOW)
                                continue
                            elif mode == 1:
                                # Единые настройки для всех
                                typer.secho("\n→ Режим: Единые настройки для всех видео", fg=typer.colors.GREEN)
                                
                                typer.secho("\n⏳ Анализ доступных форматов...", fg=typer.colors.CYAN)
                                # Собрать общие доступные качества (пересечение)
                                # Для простоты берём форматы первого видео как базу
                                first_entry = entries[0]
                                # Если в первом элементе нет форматов, запросим отдельной загрузкой
                                first_url = ia.get_entry_url(first_entry)
                                first_info = dl.get_info(first_url) if first_url else {}
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
                                    typer.secho("Загрузка отменена", fg=typer.colors.YELLOW)
                                    continue
                                
                                # Применить настройки ко всем видео плейлиста
                                typer.echo("\n" + "═" * 60)
                                typer.secho(f"▶ Начинаем загрузку плейлиста ({len(entries)} видео)...", fg=typer.colors.GREEN, bold=True)
                                typer.echo("═" * 60 + "\n")
                                
                                for idx, entry in enumerate(entries, start=1):
                                    typer.secho(f"[{idx}/{len(entries)}] Обработка...", fg=typer.colors.CYAN)
                                    entry_url = ia.get_entry_url(entry)
                                    if not entry_url:
                                        typer.secho(f"[WARN] Пропуск: не удалось получить URL для элемента #{idx}", fg=typer.colors.YELLOW)
                                        continue
                                    # Получить полную информацию для подбора качества
                                    entry_info = dl.get_info(entry_url)
                                    entry_id = entry_info.get("id", entry.get("id", f"{idx}"))
                                    entry_title = entry_info.get("title", entry.get("title", f"Видео {idx}"))
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
                                        output_dir=cfg.output,
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

                                    try:
                                        typer.secho(f"  ⏳ Загрузка: {entry_title[:60]}...", fg=typer.colors.CYAN)
                                        files = dl.download(single_opts)
                                        if not dry_run:
                                            total_files += len(files)
                                        typer.secho(f"  ✓ [OK] {entry_title}" if (dry_run or files) else f"  ⚠ [WARN] {entry_title} — нет файлов", 
                                                   fg=typer.colors.GREEN if (dry_run or files) else typer.colors.YELLOW)
                                        if not dry_run and not files:
                                            failed += 1
                                    except KeyboardInterrupt:
                                        raise
                                    except Exception:
                                        failed += 1
                                        logger.exception("Ошибка загрузки %s", entry_url)
                                        typer.secho(f"[ERROR] {entry_title}", fg=typer.colors.RED)
                                    
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
                                typer.secho("\n→ Режим: Настройка каждого видео отдельно", fg=typer.colors.GREEN)
                                # TODO: Реализовать покадровую настройку
                                
                    except Exception as e:
                        logger.warning("Не удалось обработать плейлист: %s — продолжим с настройками по умолчанию", e)
                else:
                    # ОДИНОЧНОЕ ВИДЕО В ИНТЕРАКТИВНОМ РЕЖИМЕ
                    typer.echo("\n" + "═" * 60)
                    typer.secho("⏳ Получение информации о видео...", fg=typer.colors.CYAN, bold=True)
                    typer.echo("═" * 60)
                    try:
                        info = dl.get_info(one_url)
                        video_id = info.get("id", "unknown")
                        video_title = info.get("title", "unknown")
                        
                        fmts = info.get("formats") or []
                        # Собираем уникальные высоты и предпочтительный контейнер
                        height_to_ext, available_heights = ia.collect_available_heights(fmts)
                        
                        # Построить меню качества
                        quality_options = ia.build_quality_options(height_to_ext, available_heights)
                        
                        # Показать меню и получить выбор
                        typer.echo("\n" + "═" * 60)
                        typer.echo("ШАГ 1: Выберите качество")
                        typer.echo("═" * 60)
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
                        typer.echo("\n" + "═" * 60)
                        typer.echo("ШАГ 2: Настройка имени файла")
                        typer.echo("═" * 60)
                        typer.echo(f"Название: {safe_title} [{video_id}]")
                        typer.echo(f"Расширение: .{ext_hint}")
                        typer.echo(f"Предложенный суффикс качества: {default_suffix}")
                        
                        # Спросить про суффикс качества
                        typer.echo("\nДобавить суффикс качества к имени файла?")
                        typer.echo(f"  1) Да, добавить '{default_suffix}'")
                        typer.echo("  2) Да, но указать свой суффикс")
                        typer.echo("  3) Нет, без суффикса")
                        
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
                        
                        typer.echo(f"\nИтоговое имя: {name_with_suffix}")
                        typer.echo("\nДополнительные опции:")
                        typer.echo("  1) Использовать как есть")
                        typer.echo("  2) Добавить префикс (например, '01_')")
                        typer.echo("  3) Изменить имя полностью")
                        
                        name_choice = typer.prompt("Выберите действие", default="1")
                        
                        if name_choice == "2":
                            prefix = typer.prompt("Введите префикс (например, '01_')", default="")
                            if prefix:
                                file_prefix = prefix
                                typer.echo(f"Итоговое имя: {prefix}{name_with_suffix}")
                        elif name_choice == "3":
                            new_name = typer.prompt("Введите полное имя файла (с расширением)", default=name_with_suffix)
                            custom_name = sanitize_filename(new_name)
                            quality_suffix = None  # Отключить автосуффикс если полное имя задано
                            typer.echo(f"Итоговое имя: {custom_name}")
                        else:
                            typer.echo(f"Будет использовано: {name_with_suffix}")
                        
                        # ШАГ 3: Проверка существующих файлов
                        existing = find_existing_files(cfg.output, video_id)
                        if existing:
                            typer.echo("\n" + "═" * 60)
                            typer.secho("⚠ ВНИМАНИЕ: Найдены существующие файлы этого видео:", fg=typer.colors.YELLOW)
                            typer.echo("═" * 60)
                            for i, ex_file in enumerate(existing, start=1):
                                size_mb = ex_file.stat().st_size / (1024 * 1024)
                                typer.echo(f"  {i}) {ex_file.name} ({size_mb:.1f} МБ)")
                            
                            overwrite_choice = typer.prompt(
                                "\nПерезаписать существующие файлы? (y/n)",
                                default="n"
                            )
                            if overwrite_choice.lower() in ("y", "yes", "д", "да"):
                                overwrite = True
                                typer.secho("✓ Существующие файлы будут перезаписаны", fg=typer.colors.GREEN)
                            else:
                                typer.secho("✓ Загрузка будет пропущена, если файл уже существует", fg=typer.colors.CYAN)
                        
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
                    info = dl.get_info(one_url)
                    entries = info.get("entries") or []
                    if entries:
                        typer.secho(f"▶ Плейлист: {len(entries)} видео", fg=typer.colors.GREEN)
                        for idx, entry in enumerate(entries, start=1):
                            entry_url = ia.get_entry_url(entry)
                            if not entry_url:
                                typer.secho(f"[WARN] Пропуск элемента #{idx}", fg=typer.colors.YELLOW)
                                continue
                            
                            entry_title = entry.get("title", f"Видео {idx}")
                            typer.secho(f"[{idx}/{len(entries)}] ⏳ Загрузка: {entry_title[:60]}...", fg=typer.colors.CYAN)
                            
                            single_opts = DownloadOptions(
                                url=entry_url,
                                output_dir=cfg.output,
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
                            
                            try:
                                files = dl.download(single_opts)
                                if not dry_run:
                                    total_files += len(files)
                                typer.secho(f"  ✓ [OK] {entry_title}" if (dry_run or files) else f"  ⚠ [WARN] {entry_title} — нет файлов",
                                           fg=typer.colors.GREEN if (dry_run or files) else typer.colors.YELLOW)
                                if not dry_run and not files:
                                    failed += 1
                            except KeyboardInterrupt:
                                raise
                            except Exception:
                                failed += 1
                                logger.exception("Ошибка загрузки %s", entry_url)
                                typer.secho(f"[ERROR] {entry_title}", fg=typer.colors.RED)
                            
                            # Проверить паузу после видео
                            if pause_controller.is_pause_requested():
                                pause_controller.wait_if_paused()
                        
                        # Пропустить стандартный путь загрузки плейлиста
                        continue
                except Exception as e:
                    logger.warning("Не удалось разобрать плейлист для поштучной загрузки: %s — пробуем обычный путь", e)
            
            opts = DownloadOptions(
                url=one_url,
                output_dir=cfg.output,
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
            try:
                # Показать индикатор начала загрузки
                if not interactive:
                    typer.secho(f"\n⏳ Загрузка: {one_url}", fg=typer.colors.CYAN)
                
                files = dl.download(opts)
                if not dry_run:
                    total_files += len(files)
                
                # Цветной вывод результата
                if dry_run or files:
                    typer.secho(f"✓ [OK] {one_url}", fg=typer.colors.GREEN)
                else:
                    typer.secho(f"⚠ [WARN] {one_url} — нет файлов", fg=typer.colors.YELLOW)
                
                if not dry_run and not files:
                    failed += 1
            except KeyboardInterrupt:
                raise
            except Exception as e:  # noqa: BLE001
                failed += 1
                logger.exception("Ошибка загрузки %s", one_url)
                typer.secho(f"[ERROR] {one_url} — {e}", fg=typer.colors.RED)
        
        # Отключить контроллер пауз после завершения всех загрузок
        if pause_controller:
            pause_controller.disable()

        if dry_run:
            typer.secho("[OK] Dry-run завершён (файлы не скачаны)", fg=typer.colors.GREEN)
            sys.exit(0)

        if failed == 0 and total_files > 0:
            typer.secho(f"[OK] Скачано файлов: {total_files}", fg=typer.colors.GREEN)
            sys.exit(0)
        elif failed > 0 and total_files > 0:
            typer.secho(f"[WARN] Скачано файлов: {total_files}, ошибок: {failed}", fg=typer.colors.YELLOW)
            sys.exit(2)
        elif failed > 0 and total_files == 0:
            typer.secho("✗ Ошибка загрузки (ни один файл не скачан)", fg=typer.colors.RED)
            sys.exit(1)
        else:
            typer.secho("⚠ Файлы не скачаны", fg=typer.colors.YELLOW)
            sys.exit(2)
    
    except KeyboardInterrupt:
        typer.secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        sys.exit(1)
    except typer.Exit:
        # Позволяем корректным выходам Typer завершаться без лишнего логирования стека
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки")
        typer.secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
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
        info = dl.get_info(url)
        
        if json_output:
            typer.echo(json.dumps(info, indent=2, ensure_ascii=False))
        else:
            typer.echo(_format_info(info))
        
        sys.exit(0)
    
    except KeyboardInterrupt:
        typer.secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        sys.exit(1)
    except Exception as e:
        logger.exception("Ошибка получения метаданных")
        typer.secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        sys.exit(1)


def main() -> None:
    app()
