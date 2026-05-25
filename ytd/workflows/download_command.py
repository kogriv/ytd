"""Main download command orchestration."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import typer

from ..config import load_config, merge_cli_overrides
from ..console import safe_echo, safe_secho
from ..downloader import Downloader
from ..exceptions import NetworkUnavailableError
from ..logging import setup_logging
from ..types import DownloadOptions, config_download_defaults
from ..utils import extract_quality_suffix, find_best_quality_match, sanitize_filename
from .history_prompts import (
    HistoryDecision,
    history_identifier,
    initialize_history,
)
from .history_prompts import (
    prompt_history_decision as workflow_prompt_history_decision,
)
from .network import echo_error_hints, prompt_network_recovery
from .playlist_entries import PreparedEntry, process_playlist_entries


def looks_like_playlist_url(url: str) -> bool:
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



def execute_download(
    url: str | None = None,
    output: Path | None = None,
    urls_file: Path | None = None,
    audio_only: bool | None = None,
    audio_format: str | None = None,
    video_format: str | None = None,
    quality: str | None = None,
    name: str | None = None,
    subtitles: list[str] | None = None,
    proxy: str | None = None,
    cookies: Path | None = None,
    cookies_from_browser: str | None = None,
    retry: int | None = None,
    retry_delay: float | None = None,
    dry_run: bool = False,
    playlist: bool = False,
    playlist_items: str | None = None,
    interactive: bool | None = None,
    pause_between: bool = False,
    intra_video_pause: bool = False,
    verbose: bool = False
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

    from .. import interactive as ia
    from ..pause import PauseController

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
        if cookies is not None:
            cli_overrides["cookies_file"] = cookies
        if cookies_from_browser is not None:
            cli_overrides["cookies_from_browser"] = cookies_from_browser
        if retry is not None:
            cli_overrides["retry"] = retry
        if retry_delay is not None:
            cli_overrides["retry_delay"] = retry_delay
        
        # Применить оверрайды
        cfg = merge_cli_overrides(cfg, cli_overrides)

        if interactive is None:
            interactive = bool(getattr(cfg, "interactive_by_default", False))
        else:
            interactive = bool(interactive)

        history_store = initialize_history(cfg, logger)
        history_available = history_store is not None
        
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

        auto_playlist_enabled = getattr(cfg, "auto_detect_playlists", True)
        playlist_candidates = [u for u in urls if looks_like_playlist_url(u)]

        selected_playlist_url: str | None = None
        use_playlist_interactive = interactive and (
            playlist or (auto_playlist_enabled and bool(playlist_candidates))
        )

        if use_playlist_interactive:
            if not playlist_candidates:
                safe_secho(
                    "Флаг --playlist указан, но ни одна ссылка не похожа на плейлист.",
                    fg=typer.colors.YELLOW,
                )
                use_playlist_interactive = False
            elif len(playlist_candidates) > 1:
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
        dl = Downloader(cfg, logger, verbose=verbose, history_store=history_store)

        def fetch_info_with_prompt(
            target_url: str,
            *,
            title_hint: str | None = None,
            allow_skip: bool = False,
            skip_message: str | None = None,
        ) -> dict[str, Any] | None:
            while True:
                try:
                    return dl.get_info(target_url)
                except NetworkUnavailableError as net_err:
                    decision = prompt_network_recovery(
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

        def prompt_history_decision(  # noqa: F811 — thin wrapper over workflow helper
            *,
            video_id: str | None,
            current_url: str,
            title_hint: str | None = None,
            default_output_dir: Path | None = None,
        ) -> HistoryDecision:
            return workflow_prompt_history_decision(
                history_available=history_available,
                cfg=cfg,
                logger=logger,
                video_id=video_id,
                current_url=current_url,
                title_hint=title_hint,
                default_output_dir=default_output_dir,
            )

        preflight_history_decisions: list[HistoryDecision] = []
        if history_available:
            filtered_urls: list[str] = []
            for original_url in urls:
                decision = prompt_history_decision(
                    video_id=history_identifier(original_url),
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

        # Инициализировать контроллер пауз
        pause_controller: PauseController | None = None
        use_between_pause = pause_between or cfg.pause_between_videos
        use_intra_pause = intra_video_pause or cfg.intra_video_pause
        enable_between_pause = use_between_pause and (
            interactive
            or playlist
            or (auto_playlist_enabled and bool(playlist_candidates))
        )
        enable_intra_pause = use_intra_pause

        if enable_between_pause or enable_intra_pause:
            pause_controller = PauseController(
                pause_key=cfg.pause_key or "p",
                resume_key=cfg.resume_key or "r",
                intra_video=enable_intra_pause,
                between_entries=enable_between_pause,
            )
            pause_controller.enable()
            if enable_intra_pause and enable_between_pause:
                pause_message = (
                    "⏸  Режим пауз включен: 'p' — прервать текущую загрузку или пауза между видео; "
                    "'r' — возобновить"
                )
            elif enable_intra_pause:
                pause_message = (
                    "⏸  Пауза внутри файла: 'p' — прервать загрузку (продолжение с места остановки); "
                    "'r' — возобновить"
                )
            else:
                pause_message = (
                    "⏸  Режим пауз включен: нажмите 'p' во время загрузки для паузы после текущего видео"
                )
            safe_secho(pause_message, fg=typer.colors.CYAN)

        dl.pause_controller = pause_controller
        
        for url_index, one_url in enumerate(urls):
            preflight_decision = (
                preflight_history_decisions[url_index]
                if url_index < len(preflight_history_decisions)
                else HistoryDecision(proceed=True)
            )
            current_output_dir = preflight_decision.new_output or cfg.output
            chosen_format: str | None = None
            chosen_label: str = "Лучшее доступное качество"
            file_prefix: str | None = None
            quality_suffix: str | None = None
            overwrite: bool = preflight_decision.overwrite
            custom_name: str | None = None
            # Флаг, чтобы пропустить общий путь после интерактивной поштучной обработки плейлиста
            skip_post_processing: bool = False
            history_video_id: str | None = history_identifier(one_url)

            looks_like_playlist = looks_like_playlist_url(one_url)
            effective_playlist = (
                bool(playlist_items)
                or (playlist and looks_like_playlist)
                or (auto_playlist_enabled and looks_like_playlist)
            )
            if interactive:
                if effective_playlist:
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
                            resolved_id = history_identifier(str(info.get("id")))
                            if resolved_id:
                                history_video_id = resolved_id
                        
                        if not entries:
                            safe_secho("[INFO] Плейлист пуст или это одиночное видео. Переходим в режим одиночного видео.", fg=typer.colors.CYAN)
                            setup = ia.run_single_video_interactive_setup(
                                info,
                                current_output_dir,
                                initial_overwrite=overwrite,
                            )
                            chosen_format = setup.chosen_format
                            chosen_label = setup.chosen_label
                            quality_suffix = setup.quality_suffix
                            file_prefix = setup.file_prefix
                            custom_name = setup.custom_name
                            overwrite = setup.overwrite
                        else:
                            # Показать информацию о плейлисте
                            ia.show_playlist_info(info)
                            
                            # Выбрать режим
                            mode = ia.choose_playlist_mode()

                            def resolve_playlist_download_indices() -> tuple[set[int] | None, bool]:
                                """Вернуть (индексы для загрузки, пропустить плейлист целиком)."""

                                existing_map, missing_indices = ia.analyze_playlist_progress(
                                    current_output_dir,
                                    entries,
                                )
                                indices: set[int] | None = None

                                if not existing_map:
                                    return None, False

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
                                                logger.warning(
                                                    "Не удалось удалить %s: %s",
                                                    file_path,
                                                    unlink_err,
                                                )
                                                safe_secho(
                                                    f"[WARN] Не удалось удалить {file_path.name}: {unlink_err}",
                                                    fg=typer.colors.YELLOW,
                                                )
                                    safe_secho(
                                        f"✓ Удалено файлов: {removed}. Плейлист будет скачан заново.",
                                        fg=typer.colors.CYAN,
                                    )

                                if selected_indices:
                                    indices = set(selected_indices)
                                elif delete_existing:
                                    indices = set(range(1, len(entries) + 1))
                                else:
                                    safe_secho(
                                        "[OK] Все видео плейлиста уже скачаны — загрузка не требуется",
                                        fg=typer.colors.GREEN,
                                    )
                                    return None, True

                                return indices, False

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
                                first_entry_title = first_entry.get("title", "Первое видео")
                                first_url = ia.get_entry_url(first_entry)
                                if not first_url:
                                    safe_secho(
                                        f"[WARN] Не удалось определить URL первого видео плейлиста ({first_entry_title})",
                                        fg=typer.colors.YELLOW,
                                    )
                                    safe_echo(
                                        "      Поля original_url/webpage_url/url отсутствуют. Анализ форматов может быть неполным.",
                                    )
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
                                    first_info.get("formats") or []
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

                                indices_to_download, skip_playlist = resolve_playlist_download_indices()
                                if skip_playlist:
                                    continue

                                existing_map, _ = ia.analyze_playlist_progress(
                                    current_output_dir,
                                    entries,
                                )

                                # Применить настройки ко всем видео плейлиста
                                safe_echo("\n" + "═" * 60)
                                safe_secho(
                                    f"▶ Начинаем загрузку плейлиста ({len(entries)} видео)...",
                                    fg=typer.colors.GREEN,
                                    bold=True,
                                )
                                safe_echo("═" * 60 + "\n")

                                def prepare_unified_entry(
                                    idx: int,
                                    entry: dict[str, Any],
                                    total: int,
                                ) -> PreparedEntry | None:
                                    nonlocal failed
                                    entry_title_hint = entry.get("title", f"Видео {idx}")
                                    entry_url = ia.get_entry_url(entry)
                                    if not entry_url:
                                        safe_secho(
                                            f"[WARN] Пропуск: элемент #{idx} ({entry_title_hint}) не содержит URL",
                                            fg=typer.colors.YELLOW,
                                        )
                                        safe_echo(
                                            "      yt-dlp не вернул поля original_url/webpage_url/url.",
                                        )
                                        safe_echo(
                                            "      Проверьте доступ к источнику (например, VK) или обновите yt-dlp.",
                                        )
                                        return None
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
                                        return None
                                    entry_title = entry_info.get("title", entry_title_hint)
                                    entry_fmts = entry_info.get("formats") or []

                                    per_entry_format = chosen_format
                                    if isinstance(target_height, int) and target_height >= 0:
                                        h_to_ext, avail_h = ia.collect_available_heights(entry_fmts)
                                        sel_h = find_best_quality_match(
                                            avail_h, target_height, strategy=strategy
                                        )
                                        if sel_h is None:
                                            per_entry_format = "bestvideo+bestaudio/best"
                                        else:
                                            ext = h_to_ext.get(sel_h) or "mp4"
                                            aud_ext = "m4a" if ext == "mp4" else "webm"
                                            per_entry_format = (
                                                f"bestvideo[height<={sel_h}][ext={ext}]+bestaudio[ext={aud_ext}]/"
                                                f"best[height<={sel_h}][ext={ext}]/best[height<={sel_h}]"
                                            )

                                    entry_file_prefix: str | None = None
                                    if use_numbering and prefix_template:
                                        try:
                                            entry_file_prefix = prefix_template.format(N=idx)
                                        except Exception:
                                            entry_file_prefix = f"{idx:02d}_"

                                    single_opts = DownloadOptions(
                                        url=entry_url,
                                        output_dir=current_output_dir,
                                        name_template=cfg.name_template,
                                        **config_download_defaults(cfg),
                                        dry_run=dry_run,
                                        playlist=False,
                                        playlist_items=None,
                                        custom_format=per_entry_format,
                                        file_prefix=entry_file_prefix,
                                        quality_suffix=quality_suffix,
                                        overwrite=overwrite_all,
                                    )
                                    return PreparedEntry(
                                        opts=single_opts,
                                        entry_url=entry_url,
                                        entry_title=entry_title,
                                        history_video_id=(
                                            str(entry.get("id")) if entry.get("id") else None
                                        ),
                                    )

                                playlist_result = process_playlist_entries(
                                    entries,
                                    indices_to_download=indices_to_download,
                                    existing_map=existing_map,
                                    dl=dl,
                                    dry_run=dry_run,
                                    cfg=cfg,
                                    logger=logger,
                                    history_available=history_available,
                                    prepare_entry=prepare_unified_entry,
                                    pause_controller=pause_controller,
                                    progress_style="header",
                                )
                                total_files += playlist_result.total_files
                                failed += playlist_result.failed

                                # После завершения режима с едиными настройками мы уже скачали все элементы
                                # этого плейлиста по одному. Сбросим потенциально протекший префикс и
                                # пометим, что нужно пропустить общий путь ниже по коду.
                                file_prefix = None
                                skip_post_processing = True

                            elif mode == 2:
                                safe_secho(
                                    "\n→ Режим: Настройка каждого видео отдельно",
                                    fg=typer.colors.GREEN,
                                )

                                indices_to_download, skip_playlist = resolve_playlist_download_indices()
                                if skip_playlist:
                                    continue

                                existing_map, _ = ia.analyze_playlist_progress(
                                    current_output_dir,
                                    entries,
                                )

                                safe_echo("\n" + "═" * 60)
                                safe_secho(
                                    f"▶ Настройка и загрузка плейлиста ({len(entries)} видео)...",
                                    fg=typer.colors.GREEN,
                                    bold=True,
                                )
                                safe_echo("═" * 60 + "\n")

                                per_video_overwrite = preflight_decision.overwrite

                                def prepare_individual_entry(
                                    idx: int,
                                    entry: dict[str, Any],
                                    total: int,
                                ) -> PreparedEntry | None:
                                    nonlocal failed
                                    entry_title_hint = entry.get("title", f"Видео {idx}")
                                    entry_url = ia.get_entry_url(entry)
                                    if not entry_url:
                                        safe_secho(
                                            f"[WARN] Пропуск: элемент #{idx} ({entry_title_hint}) не содержит URL",
                                            fg=typer.colors.YELLOW,
                                        )
                                        safe_echo(
                                            "      yt-dlp не вернул поля original_url/webpage_url/url.",
                                        )
                                        safe_echo(
                                            "      Проверьте доступ к источнику (например, VK) или обновите yt-dlp.",
                                        )
                                        return None

                                    entry_info = fetch_info_with_prompt(
                                        entry_url,
                                        title_hint=entry_title_hint,
                                        allow_skip=True,
                                        skip_message=(
                                            f"[SKIP] {entry_title_hint} — пропущено из-за сетевой ошибки"
                                        ),
                                    )
                                    if entry_info is None:
                                        failed += 1
                                        return None

                                    setup = ia.run_single_video_interactive_setup(
                                        entry_info,
                                        current_output_dir,
                                        initial_overwrite=per_video_overwrite,
                                    )
                                    entry_title = entry_info.get("title", entry_title_hint)
                                    name_template = setup.custom_name or cfg.name_template

                                    single_opts = DownloadOptions(
                                        url=entry_url,
                                        output_dir=current_output_dir,
                                        name_template=name_template,
                                        **config_download_defaults(cfg),
                                        dry_run=dry_run,
                                        playlist=False,
                                        playlist_items=None,
                                        custom_format=setup.chosen_format,
                                        file_prefix=setup.file_prefix,
                                        quality_suffix=(
                                            setup.quality_suffix if not setup.custom_name else None
                                        ),
                                        overwrite=setup.overwrite,
                                    )
                                    return PreparedEntry(
                                        opts=single_opts,
                                        entry_url=entry_url,
                                        entry_title=entry_title,
                                        history_video_id=(
                                            str(entry.get("id")) if entry.get("id") else None
                                        ),
                                    )

                                playlist_result = process_playlist_entries(
                                    entries,
                                    indices_to_download=indices_to_download,
                                    existing_map=existing_map,
                                    dl=dl,
                                    dry_run=dry_run,
                                    cfg=cfg,
                                    logger=logger,
                                    history_available=history_available,
                                    prepare_entry=prepare_individual_entry,
                                    pause_controller=pause_controller,
                                    progress_style="header",
                                )
                                total_files += playlist_result.total_files
                                failed += playlist_result.failed
                                skip_post_processing = True

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
                        if info.get("id"):
                            resolved_id = history_identifier(str(info.get("id")))
                            if resolved_id:
                                history_video_id = resolved_id
                        setup = ia.run_single_video_interactive_setup(
                            info,
                            current_output_dir,
                            initial_overwrite=overwrite,
                        )
                        chosen_format = setup.chosen_format
                        chosen_label = setup.chosen_label
                        quality_suffix = setup.quality_suffix
                        file_prefix = setup.file_prefix
                        custom_name = setup.custom_name
                        overwrite = setup.overwrite

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
            if pause_controller and effective_playlist and not interactive:
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

                        def prepare_pause_entry(
                            idx: int,
                            entry: dict[str, Any],
                            total: int,
                        ) -> PreparedEntry | None:
                            entry_title = entry.get("title", f"Видео {idx}")
                            entry_url = ia.get_entry_url(entry)
                            if not entry_url:
                                safe_secho(
                                    f"[WARN] Пропуск: элемент #{idx} ({entry_title}) не содержит URL",
                                    fg=typer.colors.YELLOW,
                                )
                                safe_echo(
                                    "      yt-dlp не вернул поля original_url/webpage_url/url.",
                                )
                                safe_echo(
                                    "      Проверьте доступ к источнику (например, VK) или обновите yt-dlp.",
                                )
                                return None

                            single_opts = DownloadOptions(
                                url=entry_url,
                                output_dir=current_output_dir,
                                **config_download_defaults(cfg),
                                name_template=final_name_template,
                                dry_run=dry_run,
                                playlist=False,
                                playlist_items=None,
                                custom_format=chosen_format,
                                file_prefix=file_prefix,
                                quality_suffix=quality_suffix if not custom_name else None,
                                overwrite=overwrite,
                            )
                            return PreparedEntry(
                                opts=single_opts,
                                entry_url=entry_url,
                                entry_title=entry_title,
                                history_video_id=(
                                    history_identifier(str(entry.get("id")))
                                    if entry.get("id")
                                    else None
                                ),
                            )

                        pause_result = process_playlist_entries(
                            entries,
                            indices_to_download=None,
                            existing_map={},
                            dl=dl,
                            dry_run=dry_run,
                            cfg=cfg,
                            logger=logger,
                            history_available=history_available,
                            prepare_entry=prepare_pause_entry,
                            pause_controller=pause_controller,
                            progress_style="numbered",
                        )
                        total_files += pause_result.total_files
                        failed += pause_result.failed

                        # Пропустить стандартный путь загрузки плейлиста
                        continue
                except Exception as e:
                    logger.warning("Не удалось разобрать плейлист для поштучной загрузки: %s — пробуем обычный путь", e)
            
            opts = DownloadOptions(
                url=one_url,
                output_dir=current_output_dir,
                **config_download_defaults(cfg),
                name_template=final_name_template,
                dry_run=dry_run,
                playlist=effective_playlist,
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
                    decision = prompt_network_recovery(net_err, context=one_url)
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
                    echo_error_hints(e)
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
            raise typer.Exit(code=0)

        if failed == 0 and total_files > 0:
            safe_secho(f"[OK] Скачано файлов: {total_files}", fg=typer.colors.GREEN)
            raise typer.Exit(code=0)
        elif failed > 0 and total_files > 0:
            safe_secho(f"[WARN] Скачано файлов: {total_files}, ошибок: {failed}", fg=typer.colors.YELLOW)
            raise typer.Exit(code=2)
        elif failed > 0 and total_files == 0:
            safe_secho("✗ Ошибка загрузки (ни один файл не скачан)", fg=typer.colors.RED)
            raise typer.Exit(code=1)
        else:
            safe_secho("⚠ Файлы не скачаны", fg=typer.colors.YELLOW)
            raise typer.Exit(code=2)

    except KeyboardInterrupt:
        safe_secho("\n✗ Прервано пользователем", fg=typer.colors.RED)
        raise typer.Exit(code=1) from None
    except typer.Exit:
        raise
    except Exception as e:
        logger.exception("Ошибка загрузки")
        safe_secho(f"✗ Ошибка: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1) from e
