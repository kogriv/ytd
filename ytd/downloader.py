from __future__ import annotations

import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

import yt_dlp as yt_dlp  # type: ignore

from .history import record_event
from .types import AppConfig, DownloadEvent, DownloadOptions
from .utils import ensure_dir, find_ffmpeg, save_metadata_jsonl


class Downloader:
    """Обёртка над yt-dlp с удобными дефолтами и логированием."""

    def __init__(self, config: AppConfig, logger: Optional[logging.Logger] = None, verbose: bool = False) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("ytd")
        self.verbose = verbose
        self._finished_files: list[Path] = []

    def _iter_entries(self, info: Any) -> list[dict[str, Any]]:
        """Преобразовать ответ yt-dlp в список записей для истории."""
        if not isinstance(info, dict):
            return []

        entries = info.get("entries")
        if isinstance(entries, Iterable):
            normalized: list[dict[str, Any]] = []
            for entry in entries:
                if isinstance(entry, dict):
                    normalized.append(entry)
            if normalized:
                return normalized

        if info:
            return [info]
        return []

    def _build_events(
        self,
        info: Any,
        opts: DownloadOptions,
        *,
        status: str,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        file_paths: Optional[list[Path]] = None,
        error: Optional[str] = None,
    ) -> list[DownloadEvent]:
        """Сформировать DownloadEvent по данным yt-dlp."""

        entries = self._iter_entries(info)

        playlist_id: Optional[str] = None
        playlist_title: Optional[str] = None
        if isinstance(info, dict) and info.get("entries"):
            raw_playlist_id = info.get("id") or info.get("playlist_id")
            raw_playlist_title = info.get("title") or info.get("playlist_title")
            if raw_playlist_id:
                playlist_id = str(raw_playlist_id)
            if raw_playlist_title:
                playlist_title = str(raw_playlist_title)

        if not entries:
            entries = [
                {
                    "id": opts.url,
                    "title": None,
                    "webpage_url": opts.url,
                }
            ]

        out: list[DownloadEvent] = []
        for idx, entry in enumerate(entries):
            video_id = entry.get("id") or entry.get("url") or opts.url
            if not video_id:
                continue
            url = (
                entry.get("webpage_url")
                or entry.get("original_url")
                or entry.get("url")
                or opts.url
            )
            title = entry.get("title")
            entry_playlist_id = entry.get("playlist_id") or playlist_id
            entry_playlist_title = entry.get("playlist_title") or playlist_title

            resolved_path: Optional[Path] = None
            if file_paths:
                if idx < len(file_paths):
                    resolved_path = Path(file_paths[idx])

            event = DownloadEvent(
                video_id=str(video_id),
                url=str(url),
                title=title,
                status=status,
                started_at=started_at,
                finished_at=finished_at,
                file_path=resolved_path,
                error=error,
                playlist_id=entry_playlist_id,
                playlist_title=entry_playlist_title,
            )
            out.append(event)
        return out

    def _record_history(
        self,
        info: Any,
        opts: DownloadOptions,
        *,
        status: str,
        started_at: Optional[datetime] = None,
        finished_at: Optional[datetime] = None,
        file_paths: Optional[list[Path]] = None,
        error: Optional[str] = None,
    ) -> None:
        """Безопасно записать события загрузки в историю."""

        if opts.dry_run:
            return

        events = self._build_events(
            info,
            opts,
            status=status,
            started_at=started_at,
            finished_at=finished_at,
            file_paths=file_paths,
            error=error,
        )

        for event in events:
            try:
                record_event(event)
            except Exception as history_err:  # noqa: BLE001
                self.logger.debug("не удалось записать историю: %s", history_err)
                break

    # ---------------------- internal helpers ----------------------
    def _print_file_info(self, info: dict[str, Any]) -> None:
        """Вывести информацию о загружаемом файле в консоль."""
        if not isinstance(info, dict):
            return
        
        def _border_line(symbol: str = "━") -> str:
            encoding = getattr(sys.stdout, "encoding", None)
            try:
                if not encoding:
                    raise LookupError
                symbol.encode(encoding)
                return symbol * 60
            except (UnicodeEncodeError, LookupError, AttributeError):
                return "-" * 60

        border = _border_line()

        # Если это плейлист
        entries = info.get("entries")
        if entries:
            self.logger.info(border)
            self.logger.info("Плейлист: %s", info.get("title", "неизвестно"))
            self.logger.info("Видео в плейлисте: %d", len(entries))
            self.logger.info(border)
            return
        
        # Для одиночного видео
        title = info.get("title", "неизвестно")
        uploader = info.get("uploader") or info.get("channel")
        duration = info.get("duration")
        view_count = info.get("view_count")
        
        self.logger.info(border)
        self.logger.info("Название: %s", title)
        if uploader:
            self.logger.info("Канал: %s", uploader)
        if duration:
            mins, secs = divmod(int(duration), 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                self.logger.info("Длительность: %d:%02d:%02d", hours, mins, secs)
            else:
                self.logger.info("Длительность: %d:%02d", mins, secs)
        if view_count:
            self.logger.info("Просмотров: %s", f"{view_count:,}".replace(",", " "))
        self.logger.info(border)
    
    def _progress_hook(self, d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            # Только DEBUG-уровень для деталей скачивания (не будет в консоли)
            p = d.get("_percent_str") or d.get("downloaded_bytes")
            self.logger.debug("downloading: %s", p)
        elif status == "finished":
            fn = d.get("filename")
            if fn:
                self._finished_files.append(Path(fn))
            self.logger.info("сохранено: %s", fn)
        elif status == "error":
            self.logger.error("ошибка загрузки: %s", d)

    # ---------------------- public API ----------------------
    def build_ydl_opts(self, opts: DownloadOptions) -> dict[str, Any]:
        """Собрать словарь опций для YoutubeDL из DownloadOptions.

        Здесь применяются пресеты качества/форматов и имя файла.
        """
        ensure_dir(opts.output_dir)
        
        # Построить шаблон имени с учетом префикса и суффикса качества
        name_parts = []
        if opts.file_prefix:
            name_parts.append(opts.file_prefix)
        
        # Базовый шаблон из настроек
        base_template = opts.name_template
        # Если есть суффикс качества, вставим его перед расширением
        if opts.quality_suffix:
            # Разбить шаблон на имя и расширение
            if ".%(ext)s" in base_template:
                name_base = base_template.replace(".%(ext)s", "")
                name_parts.append(f"{name_base}{opts.quality_suffix}.%(ext)s")
            else:
                name_parts.append(f"{base_template}{opts.quality_suffix}")
        else:
            name_parts.append(base_template)
        
        final_template = "".join(name_parts)
        outtmpl = str(Path(opts.output_dir) / final_template)

        ydl_opts: dict[str, Any] = {
            "outtmpl": outtmpl,
            "noplaylist": not opts.playlist,
            # Не передаём logger, чтобы прогресс-бар шёл напрямую в stderr
            # "logger": self.logger,
            "progress_hooks": [self._progress_hook],
            "retries": opts.retry,
            # Оставим выбор фрагментов по умолчанию, чтобы не создавать конкурентность
            "concurrent_fragment_downloads": 1,
        }
        
        # Перезапись существующих файлов
        if opts.overwrite:
            ydl_opts["overwrites"] = True

        # Если задано ограничение элементов плейлиста
        if opts.playlist_items:
            ydl_opts["playlist_items"] = opts.playlist_items
        
        # Настройка вывода в зависимости от verbose режима
        if self.verbose:
            # Подробный режим: показываем все логи yt-dlp
            ydl_opts["quiet"] = False
            ydl_opts["no_warnings"] = False
            ydl_opts["noprogress"] = False
        else:
            # Краткий режим: только прогресс-бар и критичные сообщения
            ydl_opts["quiet"] = True  # Подавляем большинство сообщений
            ydl_opts["no_warnings"] = True  # Убираем предупреждения
            ydl_opts["noprogress"] = False  # Но оставляем прогресс-бар

        if opts.proxy:
            ydl_opts["proxy"] = opts.proxy

        # Субтитры
        if opts.subtitles:
            ydl_opts["writesubtitles"] = True
            ydl_opts["subtitlelangs"] = opts.subtitles
            ydl_opts["subtitlesformat"] = "srt"
        else:
            ydl_opts["writesubtitles"] = False

        # ffmpeg
        ffmpeg_dir = find_ffmpeg()
        if ffmpeg_dir is not None:
            ydl_opts["ffmpeg_location"] = str(ffmpeg_dir)

        # Форматы/качество
        if opts.custom_format:
            # Явный формат от пользователя (например, из интерактивного выбора)
            ydl_opts["format"] = opts.custom_format
        elif opts.audio_only or opts.quality == "audio":
            # Аудио-только: предпочесть нужный контейнер, иначе bestaudio
            format_str = f"bestaudio[ext={opts.audio_format}]/bestaudio/best"
            ydl_opts["format"] = format_str
            # Постпроцессор для приведения формата (особенно для mp3/opus)
            ydl_opts["postprocessors"] = [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": opts.audio_format,
                    "preferredquality": "0",
                }
            ]
        else:
            ext = opts.video_format
            max_h: Optional[int] = None
            if opts.quality in ("1080p", "720p"):
                max_h = int(opts.quality.replace("p", ""))
            # Подбор сопоставимого аудио по контейнеру
            aud_ext = "m4a" if ext == "mp4" else "webm"
            if max_h:
                format_str = (
                    f"bestvideo[height<={max_h}][ext={ext}]+bestaudio[ext={aud_ext}]"
                    f"/best[height<={max_h}][ext={ext}]"
                    f"/best[height<={max_h}]"
                )
            else:
                format_str = (
                    f"bestvideo[ext={ext}]+bestaudio[ext={aud_ext}]"
                    f"/best[ext={ext}]"
                    f"/best"
                )
            ydl_opts["format"] = format_str

        # Dry-run: не скачивать фактически
        if opts.dry_run:
            ydl_opts["skip_download"] = True
            ydl_opts["simulate"] = True

        return ydl_opts

    def get_info(self, url: str) -> dict[str, Any]:
        """Получить метаданные по URL без скачивания."""
        # Строим опции из конфигурации по умолчанию, но принудительно без скачивания
        base_opts = DownloadOptions(
            url=url,
            output_dir=self.config.output,
            audio_only=self.config.audio_only,
            audio_format=self.config.audio_format,
            video_format=self.config.video_format,
            quality=self.config.quality,
            name_template=self.config.name_template,
            subtitles=self.config.subtitles,
            proxy=self.config.proxy,
            retry=self.config.retry,
            retry_delay=self.config.retry_delay,
            save_metadata=self.config.save_metadata,
            dry_run=True,
            playlist=False,
        )
        ydl_opts = self.build_ydl_opts(base_opts)
        # Без скачивания
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
            info = ydl.extract_info(url, download=False)
        return info  # type: ignore[no-any-return]

    def download(self, opts: DownloadOptions) -> list[Path]:
        """Скачать видео/аудио по DownloadOptions.

        Возвращает список путей к сохранённым файлам (для плейлистов — несколько).
        """
        ydl_opts = self.build_ydl_opts(opts)
        attempt = 0
        delay = max(0.0, float(opts.retry_delay))
        last_err: Optional[BaseException] = None
        self._finished_files = []

        while attempt < max(1, int(opts.retry)):
            attempt += 1
            history_info: Optional[dict[str, Any]] = None
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
                    # Сначала получим информацию без скачивания для вывода метаданных
                    if not opts.dry_run:
                        info_preview = ydl.extract_info(opts.url, download=False)
                        if info_preview:
                            self._print_file_info(info_preview)
                        history_info = info_preview if isinstance(info_preview, dict) else None
                        self._record_history(
                            history_info,
                            opts,
                            status="in_progress",
                            started_at=datetime.utcnow(),
                        )

                    # extract_info управляет и скачиванием, и dry-run через download=False
                    info = ydl.extract_info(opts.url, download=not opts.dry_run)
                    # при dry-run файлов нет — просто выходим
                    if opts.dry_run:
                        return []

                    if isinstance(info, dict):
                        history_info = info

                    # Если хуки не отработали (напр., старые версии), попробуем подготовить имя
                    if not self._finished_files and info:
                        try:
                            fn = ydl.prepare_filename(info)
                            if fn:
                                self._finished_files.append(Path(fn))
                        except Exception:
                            pass

                    # Сохранение метаданных (по каждой записи)
                    if opts.save_metadata:
                        try:
                            if isinstance(info, dict) and info.get("entries"):
                                for entry in info.get("entries") or []:
                                    if isinstance(entry, dict):
                                        save_metadata_jsonl(entry, opts.save_metadata)
                            elif isinstance(info, dict):
                                save_metadata_jsonl(info, opts.save_metadata)
                        except Exception as meta_err:  # не ломаем загрузку из-за метаданных
                            self.logger.warning("не удалось сохранить метаданные: %s", meta_err)

                self._record_history(
                    history_info,
                    opts,
                    status="success",
                    finished_at=datetime.utcnow(),
                    file_paths=list(self._finished_files),
                )

                return list(self._finished_files)
            except Exception as e:  # noqa: BLE001 — намеренно широкое перехватывание для ретраев
                last_err = e
                self._record_history(
                    history_info,
                    opts,
                    status="failed",
                    finished_at=datetime.utcnow(),
                    error=str(e),
                )
                if attempt >= max(1, int(opts.retry)):
                    self.logger.error("не удалось скачать после %d попыток: %s", attempt, e)
                    raise
                else:
                    self.logger.warning(
                        "ошибка (попытка %d/%d): %s; повтор через %.1f с",
                        attempt,
                        int(opts.retry),
                        e,
                        delay,
                    )
                    if delay > 0:
                        time.sleep(delay)
                    delay *= 2.0  # экспоненциальная задержка

        # Если почему-то вышли из цикла без возврата/исключения
        if last_err:
            raise last_err
        return list(self._finished_files)
