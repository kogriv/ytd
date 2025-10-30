"""Storage helpers for download history."""

from .storage import (
    init_db,
    get_connection,
    ensure_schema,
    record_event,
    fetch_download,
    update_download,
)

__all__ = [
    "init_db",
    "get_connection",
    "ensure_schema",
    "record_event",
    "fetch_download",
    "update_download",
]
