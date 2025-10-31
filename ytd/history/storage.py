from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional

from ..types import DownloadEvent
from ..utils import ensure_dir, save_metadata_jsonl

_DB_PATH: Optional[Path] = None


def _to_path(value: Any) -> Optional[Path]:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value.strip())
    return None


def _as_str(value: Any) -> Optional[str]:
    if value in {None, ""}:
        return None
    return str(value)


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


def ensure_schema() -> bool:
    """Убедиться, что схема таблицы истории создана.

    Возвращает True, если таблица была создана в ходе вызова.
    """
    with closing(get_connection()) as conn:
        existed = bool(
            conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='downloads'"
            ).fetchone()
        )

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
                playlist_title TEXT,
                retry_count INTEGER DEFAULT 0,
                last_action TEXT
            )
            """
        )

        existing_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(downloads)")  # type: ignore[misc]
        }

        if "retry_count" not in existing_columns:
            conn.execute("ALTER TABLE downloads ADD COLUMN retry_count INTEGER DEFAULT 0")
        if "last_action" not in existing_columns:
            conn.execute("ALTER TABLE downloads ADD COLUMN last_action TEXT")
        conn.commit()

        return not existed


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


def _extract_timestamp(raw: Any) -> Optional[str]:
    candidates: list[Any] = []
    if isinstance(raw, (int, float)):
        candidates.append(raw)
    elif isinstance(raw, str):
        stripped = raw.strip()
        if not stripped:
            return None
        candidates.append(stripped)
    else:
        candidates.append(raw)

    for value in candidates:
        if value in {None, ""}:
            continue
        if isinstance(value, (int, float)):
            try:
                return datetime.fromtimestamp(float(value)).isoformat(timespec="seconds")
            except (OverflowError, OSError, ValueError):
                continue
        if isinstance(value, str):
            # Формат YYYYMMDD
            if len(value) == 8 and value.isdigit():
                try:
                    parsed = datetime.strptime(value, "%Y%m%d")
                except ValueError:
                    parsed = None
                if parsed:
                    return parsed.isoformat()
            try:
                num = float(value)
            except ValueError:
                num = None
            if num is not None:
                try:
                    return datetime.fromtimestamp(num).isoformat(timespec="seconds")
                except (OverflowError, OSError, ValueError):
                    pass
            try:
                parsed = datetime.fromisoformat(value)
            except ValueError:
                parsed = None
            if parsed:
                return parsed.isoformat(timespec="seconds")
    return None


def import_from_jsonl(path: Path | str) -> int:
    """Импортировать историю из JSONL-файла метаданных.

    Возвращает количество добавленных записей. Если таблица уже содержит
    записи или файл не найден — возвращает 0.
    """

    jsonl_path = Path(path).expanduser()
    if not jsonl_path.is_file():
        return 0

    with closing(get_connection()) as conn:
        existing_row = conn.execute("SELECT 1 FROM downloads LIMIT 1").fetchone()
        if existing_row:
            return 0

    added = 0
    rows: list[dict[str, Any]] = []
    try:
        with jsonl_path.open("r", encoding="utf-8") as handle:
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(data, dict):
                    continue

                video_id = _as_str(
                    data.get("id")
                    or data.get("video_id")
                    or data.get("display_id")
                    or data.get("url")
                )
                if not video_id:
                    continue

                url = _as_str(
                    data.get("webpage_url")
                    or data.get("original_url")
                    or data.get("url")
                )
                if not url:
                    url = video_id

                title = _as_str(data.get("title"))
                status = _as_str(data.get("status")) or "finished"

                playlist_id = _as_str(data.get("playlist_id") or data.get("playlist"))
                playlist_title = _as_str(data.get("playlist_title") or data.get("playlist"))

                raw_path = (
                    data.get("filepath")
                    or data.get("filename")
                    or data.get("_filename")
                )
                if not raw_path:
                    requested = data.get("requested_downloads")
                    if isinstance(requested, list):
                        for item in requested:
                            if not isinstance(item, dict):
                                continue
                            raw_path = (
                                item.get("filepath")
                                or item.get("filename")
                                or item.get("_filename")
                            )
                            if raw_path:
                                break

                file_path = _normalize_path(_to_path(raw_path)) if raw_path else None

                finished_at = None
                for ts_key in ("epoch", "timestamp", "release_timestamp", "upload_date"):
                    finished_at = _extract_timestamp(data.get(ts_key))
                    if finished_at:
                        break

                row = {
                    "video_id": video_id,
                    "url": url,
                    "title": title,
                    "status": status,
                    "started_at": None,
                    "finished_at": finished_at,
                    "file_path": file_path,
                    "error": None,
                    "playlist_id": playlist_id,
                    "playlist_title": playlist_title,
                }
                rows.append(row)
    except OSError:
        return 0

    if not rows:
        return 0

    with closing(get_connection()) as conn:
        conn.executemany(
            """
            INSERT INTO downloads (
                video_id, url, title, status, started_at, finished_at,
                file_path, error, playlist_id, playlist_title
            ) VALUES (
                :video_id, :url, :title, :status, :started_at, :finished_at,
                :file_path, :error, :playlist_id, :playlist_title
            )
            ON CONFLICT(video_id) DO NOTHING
            """,
            rows,
        )
        conn.commit()
        added = conn.total_changes

    return added


def _row_to_dict(row: sqlite3.Row | None) -> Optional[dict[str, Any]]:
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}


def fetch_download(video_id: Optional[str] = None, url: Optional[str] = None) -> Optional[dict[str, Any]]:
    """Получить запись из истории по video_id или URL."""

    if not video_id and not url:
        return None

    ensure_schema()
    with closing(get_connection()) as conn:
        query = "SELECT * FROM downloads WHERE "
        conditions: list[str] = []
        params: dict[str, Any] = {}
        if video_id:
            conditions.append("video_id = :video_id")
            params["video_id"] = video_id
        if url:
            conditions.append("url = :url")
            params["url"] = url
        query += " OR ".join(conditions)
        query += " ORDER BY finished_at DESC NULLS LAST"

        try:
            row = conn.execute(query, params).fetchone()
        except sqlite3.OperationalError:
            # ORDER BY ... NULLS LAST поддерживается не во всех версиях SQLite
            fallback_query = query.replace(" ORDER BY finished_at DESC NULLS LAST", " ORDER BY finished_at DESC")
            row = conn.execute(fallback_query, params).fetchone()
        return _row_to_dict(row)


def update_download(
    video_id: Optional[str] = None,
    url: Optional[str] = None,
    *,
    status: Optional[str] = None,
    retry_increment: bool = False,
    last_action: Optional[str] = None,
) -> None:
    """Обновить запись истории для отражения действий пользователя."""

    if not video_id and not url:
        return

    ensure_schema()
    with closing(get_connection()) as conn:
        updates: list[str] = []
        params: dict[str, Any] = {}

        if status is not None:
            updates.append("status = :status")
            params["status"] = status

        if last_action is not None:
            updates.append("last_action = :last_action")
            params["last_action"] = last_action

        if retry_increment:
            updates.append("retry_count = COALESCE(retry_count, 0) + 1")

        if not updates:
            return

        conditions: list[str] = []
        if video_id:
            conditions.append("video_id = :video_id")
            params["video_id"] = video_id
        if url:
            conditions.append("url = :url")
            params["url"] = url

        where_clause = " OR ".join(conditions)
        query = f"UPDATE downloads SET {', '.join(updates)} WHERE {where_clause}"
        conn.execute(query, params)
        conn.commit()


def list_downloads(
    *,
    statuses: Optional[Iterable[str]] = None,
    limit: Optional[int] = None,
    since: Optional[str] = None,
    playlist_id: Optional[str] = None,
) -> list[dict[str, Any]]:
    """Получить список записей истории с поддержкой фильтров."""

    ensure_schema()

    normalized_statuses = [item for item in (statuses or []) if item]
    normalized_limit = int(limit) if limit and limit > 0 else None

    query = "SELECT * FROM downloads"
    conditions: list[str] = []
    params: dict[str, Any] = {}

    if normalized_statuses:
        placeholders = ", ".join(f":status_{idx}" for idx in range(len(normalized_statuses)))
        conditions.append(f"status IN ({placeholders})")
        for idx, status in enumerate(normalized_statuses):
            params[f"status_{idx}"] = status

    if since:
        conditions.append("COALESCE(finished_at, started_at) >= :since")
        params["since"] = since

    if playlist_id:
        conditions.append("playlist_id = :playlist_id")
        params["playlist_id"] = playlist_id

    if conditions:
        query += " WHERE " + " AND ".join(conditions)

    query += " ORDER BY COALESCE(finished_at, started_at) DESC"

    if normalized_limit is not None:
        query += " LIMIT :limit"
        params["limit"] = normalized_limit

    with closing(get_connection()) as conn:
        rows = conn.execute(query, params).fetchall()
        return [_row_to_dict(row) for row in rows if row is not None]
