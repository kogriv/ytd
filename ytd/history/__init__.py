"""Storage helpers for download history."""

from .storage import init_db, get_connection, ensure_schema, record_event

__all__ = [
    "init_db",
    "get_connection",
    "ensure_schema",
    "record_event",
]
