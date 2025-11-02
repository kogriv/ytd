"""Custom exceptions used by the ytd application."""

from __future__ import annotations


class NetworkUnavailableError(RuntimeError):
    """Raised when a download fails due to network connectivity problems."""

    def __init__(self, message: str, *, original: Exception | None = None) -> None:
        super().__init__(message)
        self.original = original


__all__ = ["NetworkUnavailableError"]
