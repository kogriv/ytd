"""Storage helpers for download history."""

from .storage import (
    HistoryStore,
    ensure_schema,
    fetch_download,
    get_connection,
    get_default_store,
    import_from_jsonl,
    init_db,
    list_downloads,
    normalize_history_id,
    record_event,
    set_default_store,
    update_download,
)

__all__ = [
    "HistoryStore",
    "init_db",
    "get_connection",
    "get_default_store",
    "set_default_store",
    "ensure_schema",
    "normalize_history_id",
    "record_event",
    "fetch_download",
    "update_download",
    "list_downloads",
    "import_from_jsonl",
]
