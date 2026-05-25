from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ytd.downloader import Downloader
from ytd.history.storage import HistoryStore
from ytd.types import AppConfig, DownloadOptions


def test_build_events_maps_file_paths_by_video_id(tmp_path: Path) -> None:
    cfg = AppConfig(history_enabled=False)
    dl = Downloader(cfg)
    entries = [
        {"id": "vid_a", "webpage_url": "https://example/a"},
        {"id": "vid_b", "webpage_url": "https://example/b"},
        {"id": "vid_c", "webpage_url": "https://example/c"},
    ]
    info = {"id": "playlist", "title": "Playlist", "entries": entries}
    opts = DownloadOptions(url="https://example/playlist", output_dir=tmp_path)

    events = dl._build_events(
        info,
        opts,
        status="success",
        file_paths={
            "vid_a": tmp_path / "a.mp4",
            "vid_c": tmp_path / "c.mp4",
        },
    )

    by_id = {event.video_id: event for event in events}
    assert by_id["vid_a"].file_path == tmp_path / "a.mp4"
    assert by_id["vid_b"].file_path is None
    assert by_id["vid_c"].file_path == tmp_path / "c.mp4"


def test_playlist_batch_records_history_per_finished_hook(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class PlaylistFakeYDL:
        def __init__(self, params: dict):
            self.params = params

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url: str, download: bool = False):
            entries = [
                {
                    "id": "vid_a",
                    "title": "A",
                    "webpage_url": "https://example/a",
                    "ext": "mp4",
                },
                {
                    "id": "vid_b",
                    "title": "B",
                    "webpage_url": "https://example/b",
                    "ext": "mp4",
                },
                {
                    "id": "vid_c",
                    "title": "C",
                    "webpage_url": "https://example/c",
                    "ext": "mp4",
                },
            ]
            info = {"id": "playlist", "title": "Playlist", "entries": entries}
            if download:
                hooks = self.params.get("progress_hooks", [])
                finished = [
                    (entries[0], tmp_path / "a.mp4"),
                    (entries[2], tmp_path / "c.mp4"),
                ]
                for entry, path in finished:
                    for hook in hooks:
                        hook(
                            {
                                "status": "finished",
                                "filename": str(path),
                                "info_dict": entry,
                            }
                        )
            return info

        def prepare_filename(self, info):
            return str(tmp_path / f"{info['id']}.mp4")

    monkeypatch.setattr(
        "ytd.downloader.yt_dlp",
        SimpleNamespace(YoutubeDL=PlaylistFakeYDL),
        raising=True,
    )

    store = HistoryStore(tmp_path / "history.db")
    cfg = AppConfig(history_enabled=True)
    dl = Downloader(cfg, history_store=store)
    opts = DownloadOptions(
        url="https://example/playlist",
        output_dir=tmp_path,
        playlist=True,
        retry=1,
    )

    files = dl.download(opts)

    assert {path.name for path in files} == {"a.mp4", "c.mp4"}

    entry_a = store.fetch_download(video_id="vid_a")
    entry_b = store.fetch_download(video_id="vid_b")
    entry_c = store.fetch_download(video_id="vid_c")

    assert entry_a is not None
    assert entry_a["file_path"].endswith("a.mp4")
    assert entry_b is None
    assert entry_c is not None
    assert entry_c["file_path"].endswith("c.mp4")
