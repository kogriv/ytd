from __future__ import annotations

import logging
import socket
import ssl
import sys
import time
from collections.abc import Iterable, Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yt_dlp as yt_dlp  # type: ignore
from yt_dlp.networking.exceptions import TransportError

from .exceptions import IntraVideoPauseRequested, NetworkUnavailableError
from .history.storage import HistoryStore, get_default_store, normalize_history_id
from .pause import PauseController
from .types import AppConfig, DownloadEvent, DownloadOptions
from .utils import ensure_dir, find_ffmpeg, save_metadata_jsonl


class Downloader:
    """Обёртка над yt-dlp с удобными дефолтами и логированием."""

    def __init__(
        self,
        config: AppConfig,
        logger: logging.Logger | None = None,
        verbose: bool = False,
        *,
        history_store: HistoryStore | None = None,
        pause_controller: PauseController | None = None,
    ) -> None:
        self.config = config
        self.logger = logger or logging.getLogger("ytd")
        self.verbose = verbose
        self.history_store = history_store
        self.pause_controller = pause_controller
        self._active_pause_controller: PauseController | None = None
        self._finished_files: dict[str, Path] = {}
        self._current_opts: DownloadOptions | None = None
        self._incremental_history = False

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

    @staticmethod
    def _entry_history_keys(entry: dict[str, Any], fallback_url: str | None = None) -> list[str]:
        keys: list[str] = []
        for field in ("id", "display_id", "url", "webpage_url", "original_url"):
            value = entry.get(field)
            if value not in {None, ""}:
                keys.append(str(value))
        if fallback_url:
            keys.append(fallback_url)
        deduped: list[str] = []
        seen: set[str] = set()
        for key in keys:
            if key not in seen:
                seen.add(key)
                deduped.append(key)
        return deduped

    @classmethod
    def _resolve_entry_file_path(
        cls,
        entry: dict[str, Any],
        opts: DownloadOptions,
        file_paths: dict[str, Path] | None,
    ) -> Path | None:
        if not file_paths:
            return None
        for key in cls._entry_history_keys(entry, opts.url):
            if key in file_paths:
                return file_paths[key]
        return None

    def _store_finished_file(self, path: Path, entry: dict[str, Any]) -> None:
        for key in self._entry_history_keys(entry):
            self._finished_files[key] = path

    def _finished_paths(self) -> list[Path]:
        seen: set[Path] = set()
        ordered: list[Path] = []
        for path in self._finished_files.values():
            if path in seen:
                continue
            seen.add(path)
            ordered.append(path)
        return ordered

    def _build_events(
        self,
        info: Any,
        opts: DownloadOptions,
        *,
        status: str,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        file_paths: dict[str, Path] | None = None,
        error: str | None = None,
    ) -> list[DownloadEvent]:
        """Сформировать DownloadEvent по данным yt-dlp."""

        entries = self._iter_entries(info)

        playlist_id: str | None = None
        playlist_title: str | None = None
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
        for entry in entries:
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

            resolved_path = self._resolve_entry_file_path(entry, opts, file_paths)

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
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        file_paths: dict[str, Path] | None = None,
        error: str | None = None,
    ) -> None:
        """Безопасно записать события загрузки в историю."""

        if not getattr(self.config, "history_enabled", True):
            return

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

        store = self.history_store
        if store is None:
            try:
                store = get_default_store()
            except RuntimeError:
                return

        for event in events:
            try:
                store.record_event(event)
            except Exception as history_err:  # noqa: BLE001
                self.logger.debug("не удалось записать историю: %s", history_err)
                break

    def _close_parent_record(
        self,
        info: Any,
        opts: DownloadOptions,
        *,
        status: str,
    ) -> None:
        """Закрыть запись истории, созданную по `opts.url` в начале загрузки.

        Финальные события строятся по данным yt-dlp и часто имеют другие ключи:
        у плейлиста — по каждому элементу, у одиночного видео — по `id` площадки.
        Ключи совпадают только там, где нормализация приводит URL и `id` к одному
        значению (YouTube: и то и другое → ``yt:<id>``). В остальных случаях —
        плейлисты, VK и прочие площадки — родительская строка иначе навсегда
        остаётся в статусе ``in_progress``.
        """

        if not getattr(self.config, "history_enabled", True) or opts.dry_run:
            return

        parent_key = normalize_history_id(opts.url)
        if parent_key is None:
            return

        for event in self._build_events(info, opts, status=status):
            key = normalize_history_id(event.video_id) or normalize_history_id(event.url)
            if key == parent_key:
                return  # финальный статус уже записан по этому же ключу

        is_playlist = isinstance(info, dict) and bool(info.get("entries"))
        title = info.get("title") if isinstance(info, dict) else None
        playlist_id = (info.get("id") or info.get("playlist_id")) if is_playlist else None

        self._record_history(
            {
                "id": opts.url,
                "webpage_url": opts.url,
                "title": title,
                "playlist_id": str(playlist_id) if playlist_id else None,
                "playlist_title": title if is_playlist else None,
            },
            opts,
            status=status,
            finished_at=datetime.now(UTC),
        )

    def _record_finished_hook_entry(self, entry: dict[str, Any], path: Path) -> None:
        if not getattr(self.config, "history_enabled", True):
            return
        opts = self._current_opts
        if opts is None or opts.dry_run:
            return
        self._incremental_history = True
        self._record_history(
            entry,
            opts,
            status="success",
            finished_at=datetime.now(UTC),
            file_paths={key: path for key in self._entry_history_keys(entry, opts.url)},
        )

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
        try:
            self._handle_progress_hook(d)
        except OSError as exc:
            self.logger.debug("progress hook: OSError при выводе: %s", exc)

    def _handle_progress_hook(self, d: dict[str, Any]) -> None:
        status = d.get("status")
        if status == "downloading":
            controller = self._active_pause_controller
            if controller is not None:
                controller.check_intra_video_pause_in_hook()
            p = d.get("_percent_str") or d.get("downloaded_bytes")
            self.logger.debug("downloading: %s", p)
        elif status == "finished":
            fn = d.get("filename")
            if fn:
                path = Path(fn)
                info_dict = d.get("info_dict")
                if isinstance(info_dict, dict):
                    self._store_finished_file(path, info_dict)
                    self._record_finished_hook_entry(info_dict, path)
                else:
                    self._finished_files[str(path)] = path
            self.logger.info("сохранено: %s", fn)
        elif status == "error":
            self.logger.error("ошибка загрузки: %s", d)

    # ---------------------- public API ----------------------
    def build_ydl_opts(self, opts: DownloadOptions, *, no_progress: bool | None = None) -> dict[str, Any]:
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
            "continuedl": True,
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
        disable_progress = self.config.no_progress if no_progress is None else no_progress
        if disable_progress:
            ydl_opts["noprogress"] = True
        elif self.verbose:
            # Подробный режим: показываем все логи yt-dlp
            ydl_opts["quiet"] = False
            ydl_opts["no_warnings"] = False
            ydl_opts["noprogress"] = False
        else:
            # Краткий режим: только progress-бар и критичные сообщения
            ydl_opts["quiet"] = True  # Подавляем большинство сообщений
            ydl_opts["no_warnings"] = True  # Убираем предупреждения
            ydl_opts["noprogress"] = False  # Но оставляем прогресс-бар

        if opts.proxy:
            ydl_opts["proxy"] = opts.proxy

        if opts.cookies_file:
            ydl_opts["cookiefile"] = str(Path(opts.cookies_file).expanduser())
        elif opts.cookies_from_browser:
            ydl_opts["cookiesfrombrowser"] = (opts.cookies_from_browser.strip(),)

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
            max_h: int | None = None
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
            cookies_file=self.config.cookies_file,
            cookies_from_browser=self.config.cookies_from_browser,
            retry=self.config.retry,
            retry_delay=self.config.retry_delay,
            save_metadata=self.config.save_metadata,
            dry_run=True,
            playlist=False,
        )
        ydl_opts = self.build_ydl_opts(base_opts)

        attempt = 0
        max_attempts = max(1, int(base_opts.retry))
        delay = max(0.0, float(base_opts.retry_delay))
        last_err: BaseException | None = None

        while attempt < max_attempts:
            attempt += 1
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
                    info = ydl.extract_info(url, download=False)
                return info  # type: ignore[no-any-return]
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                is_network = self._looks_like_network_issue(exc)
                if attempt >= max_attempts:
                    if is_network:
                        raise NetworkUnavailableError(str(exc), original=exc) from exc
                    raise

                if is_network:
                    self.logger.warning(
                        "сетевая ошибка при получении информации (попытка %d/%d): %s; повтор через %.1f с",
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )
                else:
                    self.logger.warning(
                        "ошибка при получении информации (попытка %d/%d): %s; повтор через %.1f с",
                        attempt,
                        max_attempts,
                        exc,
                        delay,
                    )

                if delay > 0:
                    time.sleep(delay)
                delay *= 2.0

        if last_err is not None:
            raise last_err
        raise RuntimeError("не удалось получить информацию")

    def download(
        self,
        opts: DownloadOptions,
        *,
        pause_controller: PauseController | None = None,
    ) -> list[Path]:
        """Скачать видео/аудио по DownloadOptions.

        Возвращает список путей к сохранённым файлам (для плейлистов — несколько).
        """
        active_pause = pause_controller if pause_controller is not None else self.pause_controller
        self._active_pause_controller = active_pause

        try:
            return self._download_with_retries(opts)
        finally:
            self._active_pause_controller = None

    def _download_with_retries(self, opts: DownloadOptions) -> list[Path]:
        while True:
            attempt = 0
            delay = max(0.0, float(opts.retry_delay))
            last_err: BaseException | None = None
            self._finished_files = {}
            self._incremental_history = False
            self._current_opts = opts
            suppress_progress = self.config.no_progress
            progress_retry_used = False
            intra_pause_restart = False

            while attempt < max(1, int(opts.retry)):
                attempt += 1
                ydl_opts = self.build_ydl_opts(opts, no_progress=suppress_progress)
                history_info: dict[str, Any] | None = None
                try:
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:  # type: ignore[attr-defined]
                        if opts.dry_run:
                            ydl.extract_info(opts.url, download=False)
                            return []

                        self._record_history(
                            {
                                "id": opts.url,
                                "webpage_url": opts.url,
                                "title": None,
                            },
                            opts,
                            status="in_progress",
                            started_at=datetime.now(UTC),
                        )

                        info = ydl.extract_info(opts.url, download=True)
                        history_info = info if isinstance(info, dict) else None

                        if isinstance(info, dict):
                            self._print_file_info(info)

                        if not self._finished_files and info:
                            try:
                                if isinstance(info, dict) and info.get("entries"):
                                    for entry in info.get("entries") or []:
                                        if not isinstance(entry, dict):
                                            continue
                                        fn = ydl.prepare_filename(entry)
                                        if fn:
                                            self._store_finished_file(Path(fn), entry)
                                else:
                                    fn = ydl.prepare_filename(info)
                                    if fn:
                                        path = Path(fn)
                                        if isinstance(info, dict):
                                            self._store_finished_file(path, info)
                                        else:
                                            self._finished_files[str(path)] = path
                            except Exception:
                                pass

                        if opts.save_metadata:
                            try:
                                if isinstance(info, dict) and info.get("entries"):
                                    for entry in info.get("entries") or []:
                                        if isinstance(entry, dict):
                                            save_metadata_jsonl(entry, opts.save_metadata)
                                elif isinstance(info, dict):
                                    save_metadata_jsonl(info, opts.save_metadata)
                            except Exception as meta_err:
                                self.logger.warning("не удалось сохранить метаданные: %s", meta_err)

                    if not self._incremental_history:
                        self._record_history(
                            history_info,
                            opts,
                            status="success",
                            finished_at=datetime.now(UTC),
                            file_paths=dict(self._finished_files),
                        )

                    self._close_parent_record(history_info, opts, status="success")

                    return self._finished_paths()
                except Exception as e:  # noqa: BLE001
                    if self._find_intra_video_pause(e) and self._active_pause_controller is not None:
                        self._active_pause_controller.wait_if_paused()
                        intra_pause_restart = True
                        break

                    if (
                        not suppress_progress
                        and not progress_retry_used
                        and self._should_retry_without_progress(e)
                    ):
                        self.logger.warning(
                            "ошибка progress bar (OSError 22), повтор без прогресс-бара; "
                            "для постоянного отключения задайте no_progress: true в конфиге"
                        )
                        suppress_progress = True
                        progress_retry_used = True
                        attempt -= 1
                        self._finished_files = {}
                        self._incremental_history = False
                        continue

                    last_err = e
                    is_network_issue = self._looks_like_network_issue(e)
                    self._record_history(
                        history_info,
                        opts,
                        status="failed",
                        finished_at=datetime.now(UTC),
                        error=str(e),
                    )
                    self._close_parent_record(history_info, opts, status="failed")
                    if attempt >= max(1, int(opts.retry)):
                        self.logger.error("не удалось скачать после %d попыток: %s", attempt, e)
                        if is_network_issue:
                            raise NetworkUnavailableError(str(e), original=e) from e
                        raise
                    if is_network_issue:
                        self.logger.warning(
                            "сетевая ошибка (попытка %d/%d): %s; повтор через %.1f с",
                            attempt,
                            int(opts.retry),
                            e,
                            delay,
                        )
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
                    delay *= 2.0

            if intra_pause_restart:
                continue

            if last_err:
                raise last_err
            return self._finished_paths()

    def _find_intra_video_pause(self, exc: BaseException) -> IntraVideoPauseRequested | None:
        for cause in self._iter_exception_chain(exc):
            if isinstance(cause, IntraVideoPauseRequested):
                return cause
        return None

    def _should_retry_without_progress(self, exc: BaseException) -> bool:
        return sys.platform == "win32" and self._is_progress_flush_error(exc)

    @staticmethod
    def _is_progress_flush_error(exc: BaseException) -> bool:
        """Определить OSError [Errno 22] от flush progress bar yt-dlp."""
        for cause in Downloader._iter_exception_chain(exc):
            if isinstance(cause, OSError) and cause.errno == 22:
                return True
        return False

    @staticmethod
    def _looks_like_network_issue(exc: BaseException) -> bool:
        """Попытаться определить, что ошибка связана с сетью."""

        for cause in Downloader._iter_exception_chain(exc):
            if isinstance(
                cause,
                (
                    NetworkUnavailableError,
                    TransportError,
                    TimeoutError,
                    socket.timeout,
                    ssl.SSLError,
                    ConnectionError,
                ),
            ):
                return True
            if isinstance(cause, OSError) and getattr(cause, "errno", None) in {101, 110, 111, 113}:
                return True

        lowered_chain = " ".join(str(cause).lower() for cause in Downloader._iter_exception_chain(exc))
        keywords = (
            "timed out",
            "handshake",
            "connection reset",
            "connection aborted",
            "connection refused",
            "ssl",
            "resolve",
            "proxy",
        )
        return any(keyword in lowered_chain for keyword in keywords)

    @staticmethod
    def _iter_exception_chain(exc: BaseException) -> Iterator[BaseException]:
        seen: set[int] = set()
        current: BaseException | None = exc
        while current is not None and id(current) not in seen:
            yield current
            seen.add(id(current))
            next_exc = current.__cause__ or current.__context__
            if isinstance(next_exc, BaseException):
                current = next_exc
            else:
                break
