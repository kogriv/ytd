from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, TypedDict

QualityPreset = Literal["best", "1080p", "720p", "audio"]
AudioFormat = Literal["m4a", "mp3", "opus"]
VideoFormat = Literal["mp4", "webm"]
BrowserCookieSource = Literal[
    "chrome",
    "chromium",
    "edge",
    "firefox",
    "opera",
    "safari",
    "brave",
    "vivaldi",
    "whale",
]

VALID_QUALITY: frozenset[str] = frozenset({"best", "1080p", "720p", "audio"})
VALID_AUDIO_FORMAT: frozenset[str] = frozenset({"m4a", "mp3", "opus"})
VALID_VIDEO_FORMAT: frozenset[str] = frozenset({"mp4", "webm"})
VALID_BROWSER_COOKIE_SOURCES: frozenset[str] = frozenset(
    {"chrome", "chromium", "edge", "firefox", "opera", "safari", "brave", "vivaldi", "whale"}
)


@dataclass(slots=True)
class DownloadOptions:
    """Параметры одной загрузки.

    Эти опции маппятся в настройки yt-dlp и управляют шаблоном имени,
    форматами и качеством, повторами и путями сохранения.
    """

    url: str
    output_dir: Path = Path("downloads")
    audio_only: bool = False
    audio_format: AudioFormat = "m4a"
    video_format: VideoFormat = "mp4"
    quality: QualityPreset = "best"
    name_template: str = "%(title)s [%(id)s].%(ext)s"
    subtitles: list[str] = field(default_factory=list)
    proxy: str | None = None
    cookies_file: Path | None = None
    cookies_from_browser: BrowserCookieSource | None = None
    retry: int = 3
    retry_delay: float = 5.0
    # None — не писать JSONL: журнал ведётся в SQLite, а построчный архив
    # получается через `ytd history export --format jsonl` (BL-1207).
    save_metadata: Path | None = None
    dry_run: bool = False
    playlist: bool = False
    playlist_items: str | None = None  # '1-3' или '1,3,5' для выбора конкретных видео
    # Явная строка формата yt-dlp (если задана, имеет приоритет над quality/audio_only/video_format)
    custom_format: str | None = None
    # Префикс для имени файла (например, "01_" для нумерации)
    file_prefix: str | None = None
    # Суффикс качества для имени файла (например, "_720p")
    quality_suffix: str | None = None
    # Перезаписывать существующие файлы
    overwrite: bool = False


@dataclass(slots=True)
class AppConfig:
    """Глобальная конфигурация приложения и значения по умолчанию."""

    output: Path = Path("downloads")
    quality: QualityPreset = "best"
    video_format: VideoFormat = "mp4"
    audio_only: bool = False
    audio_format: AudioFormat = "m4a"
    name_template: str = "%(title)s [%(id)s].%(ext)s"
    subtitles: list[str] = field(default_factory=list)
    proxy: str | None = None
    cookies_file: Path | None = None
    cookies_from_browser: BrowserCookieSource | None = None
    retry: int = 3
    retry_delay: float = 5.0
    # JSONL-архив метаданных отключён по умолчанию: задайте путь, если нужен
    # построчный дамп yt-dlp для grep/jq. Импорт из существующего файла
    # при первом создании базы продолжает работать (BL-1207).
    save_metadata: Path | None = None
    history_enabled: bool = True
    history_db: Path = Path("data/history.db")
    # Поддержка пауз между видео в плейлистах
    pause_between_videos: bool = False
    pause_key: str = "p"
    resume_key: str = "r"
    intra_video_pause: bool = False
    # Настройки удобства CLI
    interactive_by_default: bool = False
    auto_detect_playlists: bool = True
    # Отключить progress bar yt-dlp (обход OSError [Errno 22] на Windows)
    no_progress: bool = False


@dataclass(slots=True)
class DownloadEvent:
    """Событие скачивания для записи в историю."""

    video_id: str
    url: str
    title: str | None
    status: str
    started_at: datetime | None = None
    finished_at: datetime | None = None
    file_path: Path | None = None
    error: str | None = None
    playlist_id: str | None = None
    playlist_title: str | None = None
    metadata: Mapping[str, Any] | None = None
    metadata_path: Path | None = None


class DownloadDefaults(TypedDict):
    audio_only: bool
    audio_format: AudioFormat
    video_format: VideoFormat
    quality: QualityPreset
    subtitles: list[str]
    proxy: str | None
    cookies_file: Path | None
    cookies_from_browser: BrowserCookieSource | None
    retry: int
    retry_delay: float
    save_metadata: Path | None


def config_download_defaults(cfg: AppConfig) -> DownloadDefaults:
    """Общие поля DownloadOptions из глобального конфига."""
    return {
        "audio_only": cfg.audio_only,
        "audio_format": cfg.audio_format,
        "video_format": cfg.video_format,
        "quality": cfg.quality,
        "subtitles": list(cfg.subtitles),
        "proxy": cfg.proxy,
        "cookies_file": cfg.cookies_file,
        "cookies_from_browser": cfg.cookies_from_browser,
        "retry": cfg.retry,
        "retry_delay": cfg.retry_delay,
        "save_metadata": cfg.save_metadata,
    }
