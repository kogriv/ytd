"""Regression-тесты сценариев плейлиста (BL-601)."""

from __future__ import annotations

import copy
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from ytd.cli import app
from ytd.downloader import Downloader
from ytd.interactive import SingleVideoSetupResult

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLtest123"

PLAYLIST_ENTRIES: list[dict[str, Any]] = [
    {
        "id": "vid1",
        "title": "Video 1",
        "webpage_url": "https://www.youtube.com/watch?v=vid1",
        "formats": [
            {"format_id": "137", "ext": "mp4", "height": 1080, "vcodec": "avc1", "resolution": "1080p"},
        ],
    },
    {
        "id": "vid2",
        "title": "Video 2",
        "webpage_url": "https://www.youtube.com/watch?v=vid2",
        "formats": [
            {"format_id": "136", "ext": "mp4", "height": 720, "vcodec": "avc1", "resolution": "720p"},
        ],
    },
    {
        "id": "vid3",
        "title": "Video 3",
        "webpage_url": "https://www.youtube.com/watch?v=vid3",
        "formats": [
            {"format_id": "135", "ext": "mp4", "height": 480, "vcodec": "avc1", "resolution": "480p"},
        ],
    },
]

PLAYLIST_INFO: dict[str, Any] = {
    "id": "PLtest123",
    "title": "Test Playlist",
    "entries": PLAYLIST_ENTRIES,
}


class PlaylistFakeYDL:
    """Заглушка yt-dlp с поддержкой плейлиста и одиночных видео."""

    _should_fail = False

    def __init__(self, params: dict):
        self.params = params

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def _entry_info(self, entry: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": entry["id"],
            "title": entry["title"],
            "uploader": "Test Channel",
            "duration": 120,
            "description": "Entry description",
            "webpage_url": entry["webpage_url"],
            "formats": copy.deepcopy(entry.get("formats") or []),
        }

    def _emit_finished(self, info: dict[str, Any]) -> None:
        hooks = self.params.get("progress_hooks", [])
        tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
        out = (
            tmpl.replace("%(title)s", info["title"])
            .replace("%(id)s", info["id"])
            .replace("%(ext)s", "mp4")
        )
        for hook in hooks:
            hook({"status": "finished", "filename": out})

    def extract_info(self, url: str, download: bool = False):
        if self._should_fail:
            raise Exception("Network error")

        if "list=" in url or url.rstrip("/") == PLAYLIST_URL.rstrip("/"):
            return copy.deepcopy(PLAYLIST_INFO)

        for entry in PLAYLIST_ENTRIES:
            if entry["id"] in url or entry["webpage_url"] == url:
                info = self._entry_info(entry)
                if download:
                    self._emit_finished(info)
                return info

        info = {
            "id": "fallback",
            "title": "Fallback",
            "formats": PLAYLIST_ENTRIES[0]["formats"],
        }
        if download:
            self._emit_finished(info)
        return info

    def prepare_filename(self, info: dict[str, Any]) -> str:
        tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
        return (
            tmpl.replace("%(title)s", info.get("title", ""))
            .replace("%(id)s", info.get("id", ""))
            .replace("%(ext)s", "mp4")
        )


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def patch_playlist_ytdlp(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "ytd.downloader.yt_dlp",
        SimpleNamespace(YoutubeDL=PlaylistFakeYDL),
        raising=True,
    )
    PlaylistFakeYDL._should_fail = False


@pytest.fixture
def auto_interactive_playlist(monkeypatch: pytest.MonkeyPatch) -> None:
    """Авто-ответы на интерактивные диалоги unified playlist mode."""

    monkeypatch.setattr("ytd.interactive.show_playlist_info", lambda info: None)
    monkeypatch.setattr("ytd.interactive.choose_playlist_mode", lambda: 1)
    monkeypatch.setattr(
        "ytd.interactive.show_quality_menu",
        lambda options: options[0],
    )
    monkeypatch.setattr("ytd.interactive.configure_filename_suffix", lambda default: "_1080p")
    monkeypatch.setattr(
        "ytd.interactive.configure_playlist_numbering",
        lambda: (True, "{N:02d}_"),
    )
    monkeypatch.setattr("ytd.interactive.configure_quality_fallback", lambda: "econom")
    monkeypatch.setattr("ytd.interactive.ask_overwrite_all", lambda: True)
    monkeypatch.setattr(
        "ytd.interactive.show_unified_settings_summary",
        lambda *args, **kwargs: True,
    )
    monkeypatch.setattr(
        "ytd.interactive.analyze_playlist_progress",
        lambda output_dir, entries: ({}, list(range(1, len(entries) + 1))),
    )


@pytest.fixture
def auto_interactive_playlist_per_video(monkeypatch: pytest.MonkeyPatch) -> None:
    """Авто-ответы на интерактивные диалоги per-video playlist mode."""

    monkeypatch.setattr("ytd.interactive.show_playlist_info", lambda info: None)
    monkeypatch.setattr("ytd.interactive.choose_playlist_mode", lambda: 2)
    monkeypatch.setattr(
        "ytd.interactive.analyze_playlist_progress",
        lambda output_dir, entries: ({}, list(range(1, len(entries) + 1))),
    )
    monkeypatch.setattr(
        "ytd.interactive.run_single_video_interactive_setup",
        lambda info, output_dir, initial_overwrite=False: SingleVideoSetupResult(
            chosen_format="bestvideo+bestaudio/best",
            chosen_label="Лучшее доступное качество",
            quality_suffix="_1080p",
            file_prefix=f"{info['id']}_",
            custom_name=None,
            overwrite=initial_overwrite,
        ),
    )


@pytest.fixture
def download_spy(monkeypatch: pytest.MonkeyPatch) -> list:
    calls: list = []

    def spy(self: Downloader, opts) -> list[Path]:
        calls.append(opts)
        return [opts.output_dir / f"{len(calls)}.mp4"]

    monkeypatch.setattr(Downloader, "download", spy)
    return calls


def _write_min_config(tmp_path: Path) -> None:
    (tmp_path / "ytd.config.yaml").write_text(
        "history_enabled: false\ninteractive_by_default: true\n",
        encoding="utf-8",
    )


def test_interactive_playlist_unified_does_not_redownload_parent(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_playlist_ytdlp: None,
    auto_interactive_playlist: None,
    download_spy: list,
) -> None:
    """BL-601: после поштучной загрузки плейлиста не вызывается второй проход по URL плейлиста."""
    monkeypatch.chdir(tmp_path)
    _write_min_config(tmp_path)
    output_dir = tmp_path / "downloads"

    result = runner.invoke(
        app,
        [
            "download",
            PLAYLIST_URL,
            "--output",
            str(output_dir),
            "--interactive",
        ],
    )

    assert result.exit_code == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert len(download_spy) == len(PLAYLIST_ENTRIES)

    for opts in download_spy:
        assert opts.playlist is False
        assert opts.url != PLAYLIST_URL
        assert "list=" not in opts.url

    entry_urls = {entry["webpage_url"] for entry in PLAYLIST_ENTRIES}
    assert {opts.url for opts in download_spy} == entry_urls

    playlist_batch_calls = [opts for opts in download_spy if opts.playlist]
    assert not playlist_batch_calls


def test_interactive_playlist_per_video_mode_downloads_each_entry(
    runner: CliRunner,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    patch_playlist_ytdlp: None,
    auto_interactive_playlist_per_video: None,
    download_spy: list,
) -> None:
    """BL-202: mode 2 настраивает и скачивает каждый элемент плейлиста отдельно."""
    monkeypatch.chdir(tmp_path)
    _write_min_config(tmp_path)
    output_dir = tmp_path / "downloads"

    setup_calls: list[str] = []

    def record_setup(info, output_dir, initial_overwrite=False):
        setup_calls.append(info["id"])
        return SingleVideoSetupResult(
            chosen_format="bestvideo+bestaudio/best",
            chosen_label="Лучшее доступное качество",
            quality_suffix="_1080p",
            file_prefix=f"{info['id']}_",
            custom_name=None,
            overwrite=initial_overwrite,
        )

    monkeypatch.setattr("ytd.interactive.run_single_video_interactive_setup", record_setup)

    result = runner.invoke(
        app,
        [
            "download",
            PLAYLIST_URL,
            "--output",
            str(output_dir),
            "--interactive",
        ],
    )

    assert result.exit_code == 0, f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
    assert len(download_spy) == len(PLAYLIST_ENTRIES)
    assert setup_calls == [entry["id"] for entry in PLAYLIST_ENTRIES]

    for opts in download_spy:
        assert opts.playlist is False
        assert opts.url != PLAYLIST_URL
        assert opts.custom_format == "bestvideo+bestaudio/best"
        assert opts.file_prefix is not None
