from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from ytd.cli import app


class FakeYDL:
    """Заглушка для yt_dlp.YoutubeDL для CLI-тестов."""

    _should_fail: bool = False
    _info_data: dict[str, Any] = {
        "id": "test123",
        "title": "Test Video",
        "uploader": "Test Channel",
        "duration": 180,
        "description": "Test description",
        "formats": [
            {"format_id": "137", "ext": "mp4", "resolution": "1080p"},
            {"format_id": "136", "ext": "mp4", "resolution": "720p"},
        ],
    }

    def __init__(self, params: dict):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool):
        if FakeYDL._should_fail:
            raise Exception("Network error")
        
        # при download=True вызываем прогресс-хуки
        if download:
            hooks = self.params.get("progress_hooks", [])
            tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
            out = (
                tmpl.replace("%(title)s", self._info_data["title"])
                .replace("%(id)s", self._info_data["id"])
                .replace("%(ext)s", "mp4")
            )
            for h in hooks:
                h({"status": "finished", "filename": out})
        
        return self._info_data.copy()

    def prepare_filename(self, info):
        tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
        return (
            tmpl.replace("%(title)s", info.get("title", ""))
            .replace("%(id)s", info.get("id", ""))
            .replace("%(ext)s", "mp4")
        )


@pytest.fixture(autouse=True)
def patch_yt_dlp(monkeypatch: pytest.MonkeyPatch):
    """Подменить yt_dlp для всех тестов."""
    monkeypatch.setattr("ytd.downloader.yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL), raising=True)
    # сбросить состояние между тестами
    FakeYDL._should_fail = False
    yield


@pytest.fixture
def runner():
    return CliRunner()


def test_cli_download_basic(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест базовой команды download с минимальными опциями."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(app, ["download", "https://example.com/video", "--output", str(tmp_path / "dl")])
    
    assert result.exit_code == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert "Скачано файлов:" in result.stdout
    assert (tmp_path / "dl").is_dir()


def test_cli_download_urls_file(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест загрузки из файла ссылок (--urls-file)."""
    monkeypatch.chdir(tmp_path)
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text("""
# комментарий
https://example.com/video1
https://example.com/video2
""".strip(), encoding="utf-8")

    result = runner.invoke(app, [
        "download",
        "--urls-file",
        str(urls_file),
        "--output",
        str(tmp_path / "out"),
    ])

    assert result.exit_code == 0
    assert "Скачано файлов: 2" in result.stdout


def test_cli_download_audio_only(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест загрузки только аудио."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(
        app,
        [
            "download",
            "https://example.com/video",
            "--audio-only",
            "--audio-format",
            "mp3",
            "--output",
            str(tmp_path / "audio"),
        ],
    )
    
    assert result.exit_code == 0
    assert "Скачано файлов:" in result.stdout


def test_cli_download_dry_run(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест dry-run: не скачивает файлы."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(
        app,
        ["download", "https://example.com/video", "--dry-run", "--output", str(tmp_path / "dl")],
    )
    
    assert result.exit_code == 0
    assert "Dry-run завершён" in result.stdout


def test_cli_download_with_cli_overrides(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест CLI-оверрайдов: качество, формат, шаблон имени."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(
        app,
        [
            "download",
            "https://example.com/video",
            "--output",
            str(tmp_path / "out"),
            "--quality",
            "720p",
            "--video-format",
            "webm",
            "--name",
            "%(title)s.%(ext)s",
            "--retry",
            "5",
            "--retry-delay",
            "1.0",
        ],
    )
    
    assert result.exit_code == 0
    assert "Скачано файлов:" in result.stdout


def test_cli_download_handles_error(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест обработки ошибки загрузки."""
    monkeypatch.chdir(tmp_path)
    FakeYDL._should_fail = True
    
    result = runner.invoke(app, ["download", "https://example.com/video", "--output", str(tmp_path / "dl")])
    
    assert result.exit_code == 1
    assert "Ошибка" in result.stdout


def test_cli_info_basic(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест команды info: показывает метаданные."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(app, ["info", "https://example.com/video"])
    
    assert result.exit_code == 0
    assert "ID: test123" in result.stdout
    assert "Название: Test Video" in result.stdout
    assert "Канал: Test Channel" in result.stdout


def test_cli_info_json_output(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест команды info с --json: вывод сырого JSON."""
    monkeypatch.chdir(tmp_path)
    
    result = runner.invoke(app, ["info", "https://example.com/video", "--json"])
    
    assert result.exit_code == 0
    assert '"id": "test123"' in result.stdout
    assert '"title": "Test Video"' in result.stdout


def test_cli_info_handles_error(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Тест обработки ошибки в команде info."""
    monkeypatch.chdir(tmp_path)
    FakeYDL._should_fail = True
    
    result = runner.invoke(app, ["info", "https://example.com/video"])
    
    assert result.exit_code == 1
    assert "Ошибка" in result.stdout


def test_cli_no_command_shows_help(runner: CliRunner):
    """Тест что запуск без команды показывает help."""
    result = runner.invoke(app, [])
    
    # no_args_is_help=True в Typer возвращает exit_code=2 (не ошибка, но показ help)
    # https://github.com/tiangolo/typer/issues/18
    assert result.exit_code in (0, 2)
    assert "Простой загрузчик видео" in result.stdout or "download" in result.stdout
