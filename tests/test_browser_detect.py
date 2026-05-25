from __future__ import annotations

import pytest

from ytd.browser_detect import detect_cookies_browser_hint
from ytd.history.storage import normalize_history_id


def test_normalize_history_id_youtube_url() -> None:
    assert normalize_history_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "yt:dQw4w9WgXcQ"


def test_normalize_history_id_youtube_short() -> None:
    assert normalize_history_id("https://youtu.be/dQw4w9WgXcQ") == "yt:dQw4w9WgXcQ"


def test_normalize_history_id_raw_youtube_id() -> None:
    assert normalize_history_id("dQw4w9WgXcQ") == "yt:dQw4w9WgXcQ"


def test_normalize_history_id_generic_url() -> None:
    normalized = normalize_history_id("https://example.com/video/123")
    assert normalized == "https://example.com/video/123"


def test_detect_cookies_browser_hint_windows_edge(monkeypatch: pytest.MonkeyPatch) -> None:
    detect_cookies_browser_hint.cache_clear()
    monkeypatch.setattr("ytd.browser_detect.sys.platform", "win32")
    monkeypatch.setattr("ytd.browser_detect._detect_windows_browser", lambda: "edge")
    assert detect_cookies_browser_hint() == "edge"


def test_detect_cookies_browser_hint_linux_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    detect_cookies_browser_hint.cache_clear()
    monkeypatch.setattr("ytd.browser_detect.sys.platform", "linux")
    monkeypatch.setattr("ytd.browser_detect._detect_linux_browser", lambda: None)
    assert detect_cookies_browser_hint() == "firefox"
