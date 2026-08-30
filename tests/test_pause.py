"""Тесты PauseController (BL-301, BL-604, BL-1101)."""

from __future__ import annotations

import sys

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


def test_wait_if_paused_uses_key_backend_on_tty(monkeypatch: pytest.MonkeyPatch) -> None:
    """BL-1101: при интерактивном stdin используется платформенный бэкенд, а не prompt-fallback."""
    controller = PauseController()
    controller._pause_requested.set()

    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: True)

    called: list[str] = []
    monkeypatch.setattr(controller, "_wait_for_resume_windows", lambda: called.append("win"))
    monkeypatch.setattr(controller, "_wait_for_resume_unix", lambda: called.append("unix"))

    def _fail_prompt(*args: object, **kwargs: object) -> str:
        raise AssertionError("prompt не должен вызываться при интерактивном stdin")

    monkeypatch.setattr("ytd.pause.typer.prompt", _fail_prompt)

    controller.wait_if_paused()

    assert called == ["win" if sys.platform == "win32" else "unix"]


@pytest.mark.skipif(sys.platform != "win32", reason="ветка msvcrt выполняется только на Windows")
def test_wait_for_resume_windows_exits_when_listener_stopped() -> None:
    """BL-1101: disable() разрывает ожидание клавиши вместо бесконечного цикла."""
    controller = PauseController()
    controller._pause_requested.set()
    controller._stop_listener.set()

    controller._wait_for_resume_windows()  # не должно зависнуть


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
