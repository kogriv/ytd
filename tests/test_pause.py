"""Тесты PauseController (BL-301, BL-604, BL-1101, BL-1202)."""

from __future__ import annotations

import threading

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


def test_listener_key_sets_resume_event() -> None:
    """BL-1202: во время паузы слушатель сам распознаёт клавишу возобновления."""
    controller = PauseController(pause_key="p", resume_key="r")
    controller._pause_requested.set()

    controller._handle_listener_key("r")

    assert controller._resume_requested.is_set()


def test_resume_key_ignored_when_not_paused() -> None:
    """Вне паузы клавиша возобновления ничего не делает."""
    controller = PauseController(pause_key="p", resume_key="r")

    controller._handle_listener_key("r")

    assert not controller._resume_requested.is_set()
    assert not controller.is_pause_requested()


def test_wait_if_paused_returns_when_resume_event_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """BL-1202: ожидание завершается по событию от слушателя, без второго чтения клавиш."""
    controller = PauseController()
    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(controller, "_keyboard_listener", lambda: None)

    def _fail_prompt(*args: object, **kwargs: object) -> str:
        raise AssertionError("prompt не должен вызываться при работающем слушателе")

    monkeypatch.setattr("ytd.pause.typer.prompt", _fail_prompt)

    controller.enable()
    controller._pause_requested.set()

    # Слушатель живёт в отдельном потоке — эмулируем нажатие оттуда же.
    timer = threading.Timer(0.05, lambda: controller._handle_listener_key("r"))
    timer.start()
    try:
        controller.wait_if_paused()
    finally:
        timer.cancel()
        controller.disable()

    assert not controller.is_pause_requested()
    assert not controller._resume_requested.is_set()


def test_wait_if_paused_exits_when_listener_stopped(monkeypatch: pytest.MonkeyPatch) -> None:
    """disable() разрывает ожидание вместо бесконечного цикла."""
    controller = PauseController()
    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: True)
    monkeypatch.setattr(controller, "_keyboard_listener", lambda: None)

    controller.enable()
    controller._pause_requested.set()
    controller._stop_listener.set()

    controller.wait_if_paused()  # не должно зависнуть

    assert not controller.is_pause_requested()


def test_wait_if_paused_falls_back_without_listener(monkeypatch: pytest.MonkeyPatch) -> None:
    """Если слушатель не запущен, используется prompt даже на интерактивном stdin."""
    controller = PauseController()
    controller._pause_requested.set()

    monkeypatch.setattr("ytd.pause.sys.stdin.isatty", lambda: True)
    prompted: list[bool] = []
    monkeypatch.setattr(
        "ytd.pause.typer.prompt",
        lambda *args, **kwargs: prompted.append(True) or "",
    )

    controller.wait_if_paused()

    assert prompted == [True]
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
