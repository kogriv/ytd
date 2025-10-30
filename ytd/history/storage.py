from __future__ import annotations

import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from ..types import DownloadEvent
from ..utils import ensure_dir, save_metadata_jsonl

_DB_PATH: Optional[Path] = None


def init_db(path: Path | str) -> Path:
    """Установить путь к файлу БД истории загрузок."""
    global _DB_PATH
    db_path = Path(path).expanduser()
    ensure_dir(db_path.parent)
    _DB_PATH = db_path
    return db_path


def get_connection() -> sqlite3.Connection:
    """Получить соединение с SQLite-базой истории."""
    if _DB_PATH is None:
        raise RuntimeError("database path is not initialized; call init_db() first")
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema() -> None:
    """Убедиться, что схема таблицы истории создана."""
    with closing(get_connection()) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS downloads (
                video_id TEXT PRIMARY KEY,
                url TEXT,
                title TEXT,
                status TEXT,
                started_at DATETIME,
                finished_at DATETIME,
                file_path TEXT,
                error TEXT,
                playlist_id TEXT,
                playlist_title TEXT
            )
            """
        )
        conn.commit()


def _normalize_datetime(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat(timespec="seconds")
    return str(value)


def _normalize_path(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(Path(value))


def record_event(event: DownloadEvent) -> None:
    """Записать или обновить событие загрузки в истории."""
    ensure_schema()
    payload = {
        "video_id": event.video_id,
        "url": event.url,
        "title": event.title,
        "status": event.status,
        "started_at": _normalize_datetime(event.started_at),
        "finished_at": _normalize_datetime(event.finished_at),
        "file_path": _normalize_path(event.file_path),
        "error": event.error,
        "playlist_id": event.playlist_id,
        "playlist_title": event.playlist_title,
    }

    with closing(get_connection()) as conn:
        conn.execute(
            """
            INSERT INTO downloads (
                video_id, url, title, status, started_at,
                finished_at, file_path, error, playlist_id, playlist_title
            ) VALUES (
                :video_id, :url, :title, :status, :started_at,
                :finished_at, :file_path, :error, :playlist_id, :playlist_title
            )
            ON CONFLICT(video_id) DO UPDATE SET
                url = excluded.url,
                title = COALESCE(excluded.title, downloads.title),
                status = excluded.status,
                started_at = COALESCE(excluded.started_at, downloads.started_at),
                finished_at = COALESCE(excluded.finished_at, downloads.finished_at),
                file_path = COALESCE(excluded.file_path, downloads.file_path),
                error = COALESCE(excluded.error, downloads.error),
                playlist_id = COALESCE(excluded.playlist_id, downloads.playlist_id),
                playlist_title = COALESCE(excluded.playlist_title, downloads.playlist_title)
            """,
            payload,
        )
        conn.commit()

    if event.metadata and event.metadata_path:
        try:
            save_metadata_jsonl(event.metadata, event.metadata_path)
        except Exception:
            # История не должна падать из-за метаданных
            pass
