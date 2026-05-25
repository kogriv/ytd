"""Тесты поведения флага --interactive и конфига interactive_by_default (BL-201)."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from ytd.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture(autouse=True)
def patch_yt_dlp(monkeypatch: pytest.MonkeyPatch):
    from types import SimpleNamespace

    from tests.test_cli import FakeYDL

    monkeypatch.setattr("ytd.downloader.yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL), raising=True)
    FakeYDL._should_fail = False
    yield


def _write_config(tmp_path: Path, *, interactive_by_default: bool) -> None:
    (tmp_path / "ytd.config.yaml").write_text(
        f"history_enabled: false\ninteractive_by_default: {str(interactive_by_default).lower()}\n",
        encoding="utf-8",
    )


def test_non_interactive_when_config_false_and_no_cli_flag(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, interactive_by_default=False)

    menu_calls: list[int] = []

    def fail_if_called(*args, **kwargs):
        menu_calls.append(1)
        raise AssertionError("show_quality_menu must not be called")

    monkeypatch.setattr("ytd.interactive.show_quality_menu", fail_if_called)

    result = runner.invoke(
        app,
        ["download", "https://example.com/video", "--output", str(tmp_path / "out")],
    )

    assert result.exit_code == 0, result.stdout
    assert menu_calls == []


def test_interactive_when_config_true_and_no_cli_flag(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, interactive_by_default=True)

    menu_calls: list[int] = []

    def record_menu(options):
        menu_calls.append(1)
        return options[0]

    monkeypatch.setattr("ytd.interactive.show_quality_menu", record_menu)
    monkeypatch.setattr("ytd.interactive.configure_filename_suffix", lambda default: None)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: kwargs.get("default", "1"))

    result = runner.invoke(
        app,
        ["download", "https://example.com/video", "--output", str(tmp_path / "out")],
    )

    assert result.exit_code == 0, result.stdout
    assert len(menu_calls) == 1


def test_cli_no_interactive_overrides_config_true(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, interactive_by_default=True)

    menu_calls: list[int] = []

    def fail_if_called(*args, **kwargs):
        menu_calls.append(1)
        raise AssertionError("show_quality_menu must not be called")

    monkeypatch.setattr("ytd.interactive.show_quality_menu", fail_if_called)

    result = runner.invoke(
        app,
        [
            "download",
            "https://example.com/video",
            "--output",
            str(tmp_path / "out"),
            "--no-interactive",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert menu_calls == []


def test_cli_interactive_overrides_config_false(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, interactive_by_default=False)

    menu_calls: list[int] = []

    def record_menu(options):
        menu_calls.append(1)
        return options[0]

    monkeypatch.setattr("ytd.interactive.show_quality_menu", record_menu)
    monkeypatch.setattr("ytd.interactive.configure_filename_suffix", lambda default: None)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: kwargs.get("default", "1"))

    result = runner.invoke(
        app,
        [
            "download",
            "https://example.com/video",
            "--output",
            str(tmp_path / "out"),
            "--interactive",
        ],
    )

    assert result.exit_code == 0, result.stdout
    assert len(menu_calls) == 1
