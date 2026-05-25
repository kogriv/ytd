"""Тесты PauseController (BL-301, BL-604)."""

from __future__ import annotations

import pytest

from ytd.pause import PauseController


def test_handle_listener_key_sets_pause_event() -> None:
    controller = PauseController(pause_key="p", resume_key="r")

    assert not controller.is_pause_requested()
    controller._handle_listener_key("p")
    assert controller.is_pause_requested()
    controller._handle_listener_key("x")
    assert controller.is_pause_requested()


def test_handle_listener_key_respects_custom_pause_key() -> None:
    controller = PauseController(pause_key="x", resume_key="c")

    controller._handle_listener_key("p")
    assert not controller.is_pause_requested()
    controller._handle_listener_key("x")
    assert controller.is_pause_requested()


def test_wait_if_paused_clears_flag_with_prompt_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = PauseController()
    controller._pause_requested.set()

    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: False)
    monkeypatch.setattr("ytd.pause.typer.prompt", lambda *args, **kwargs: "")

    controller.wait_if_paused()
    assert not controller.is_pause_requested()


def test_enable_skips_listener_when_stdin_not_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = PauseController()
    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: False)

    controller.enable()

    assert not controller._enabled
    assert not controller._keyboard_available


def test_enable_starts_listener_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    controller = PauseController()
    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(controller, "_keyboard_listener", lambda: None)

    controller.enable()

    assert controller._enabled
    assert controller._keyboard_available
    controller.disable()
