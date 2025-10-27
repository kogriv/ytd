from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal


@dataclass(slots=True)
class DownloadOptions:
    """Параметры одной загрузки.

    Эти опции маппятся в настройки yt-dlp и управляют шаблоном имени,
    форматами и качеством, повторами и путями сохранения.
    """

    url: str
    output_dir: Path = Path("downloads")
    audio_only: bool = False
    audio_format: Literal["m4a", "mp3", "opus"] = "m4a"
    video_format: Literal["mp4", "webm"] = "mp4"
    quality: Literal["best", "1080p", "720p", "audio"] = "best"
    name_template: str = "%(title)s [%(id)s].%(ext)s"
    subtitles: list[str] = field(default_factory=list)
    proxy: Optional[str] = None
    retry: int = 3
    retry_delay: float = 5.0
    save_metadata: Optional[Path] = Path("data/meta.jsonl")
    dry_run: bool = False
    playlist: bool = False
    playlist_items: Optional[str] = None  # '1-3' или '1,3,5' для выбора конкретных видео
    # Явная строка формата yt-dlp (если задана, имеет приоритет над quality/audio_only/video_format)
    custom_format: Optional[str] = None
    # Префикс для имени файла (например, "01_" для нумерации)
    file_prefix: Optional[str] = None
    # Суффикс качества для имени файла (например, "_720p")
    quality_suffix: Optional[str] = None
    # Перезаписывать существующие файлы
    overwrite: bool = False


@dataclass(slots=True)
class AppConfig:
    """Глобальная конфигурация приложения и значения по умолчанию."""

    output: Path = Path("downloads")
    quality: str = "best"
    video_format: str = "mp4"
    audio_only: bool = False
    audio_format: str = "m4a"
    name_template: str = "%(title)s [%(id)s].%(ext)s"
    subtitles: list[str] = field(default_factory=list)
    proxy: Optional[str] = None
    retry: int = 3
    retry_delay: float = 5.0
    save_metadata: Optional[Path] = Path("data/meta.jsonl")
