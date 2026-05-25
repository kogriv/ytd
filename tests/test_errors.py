from __future__ import annotations

import pytest

from ytd.errors import antibot_hint, looks_like_antibot_error


@pytest.mark.parametrize(
    "message",
    [
        "Sign in to confirm you're not a bot",
        "ERROR: login required; use --cookies",
        "HTTP Error 429: Too Many Requests",
    ],
)
def test_looks_like_antibot_error_detects_known_messages(message: str) -> None:
    assert looks_like_antibot_error(RuntimeError(message)) is True


def test_looks_like_antibot_error_ignores_generic_errors() -> None:
    assert looks_like_antibot_error(RuntimeError("file not found")) is False


def test_antibot_hint_mentions_cli_flags() -> None:
    hint = antibot_hint()
    assert "--cookies-from-browser" in hint
    assert "--cookies" in hint


def test_antibot_hint_uses_detected_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("ytd.errors.detect_cookies_browser_hint", lambda: "edge")
    hint = antibot_hint()
    assert "--cookies-from-browser edge" in hint
