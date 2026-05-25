from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from ytd.downloader import Downloader
from ytd.exceptions import IntraVideoPauseRequested
from ytd.pause import PauseController
from ytd.types import AppConfig, DownloadOptions


def test_check_intra_video_pause_in_hook_raises_when_requested() -> None:
    controller = PauseController(intra_video=True, between_entries=False)
    controller._pause_requested.set()

    with pytest.raises(IntraVideoPauseRequested):
        controller.check_intra_video_pause_in_hook()


def test_check_intra_video_pause_in_hook_ignored_when_disabled() -> None:
    controller = PauseController(intra_video=False, between_entries=True)
    controller._pause_requested.set()

    controller.check_intra_video_pause_in_hook()


def test_download_resumes_after_intra_video_pause(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    attempts = {"count": 0}

    class PausingFakeYDL:
        instances: list[PausingFakeYDL] = []

        def __init__(self, params: dict):
            self.params = params
            PausingFakeYDL.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def extract_info(self, url: str, download: bool = False):
            attempts["count"] += 1
            info = {"id": "abc", "title": "Title", "ext": "mp4", "url": url}
            if not download:
                return info
            hooks = self.params.get("progress_hooks", [])
            if attempts["count"] == 1:
                for hook in hooks:
                    hook({"status": "downloading", "downloaded_bytes": 100})
            out = str(tmp_path / "Title [abc].mp4")
            for hook in hooks:
                hook(
                    {
                        "status": "finished",
                        "filename": out,
                        "info_dict": info,
                    }
                )
            return info

        def prepare_filename(self, info):
            return str(tmp_path / "Title [abc].mp4")

    monkeypatch.setattr(
        "ytd.downloader.yt_dlp",
        SimpleNamespace(YoutubeDL=PausingFakeYDL),
        raising=True,
    )
    PausingFakeYDL.instances.clear()

    controller = PauseController(intra_video=True, between_entries=False)
    controller.enable = lambda: None  # type: ignore[method-assign]
    controller._pause_requested.set()

    resumed = {"called": False}

    def fake_wait_if_paused() -> None:
        resumed["called"] = True
        controller.reset()

    controller.wait_if_paused = fake_wait_if_paused  # type: ignore[method-assign]

    cfg = AppConfig(output=tmp_path, history_enabled=False)
    dl = Downloader(cfg, pause_controller=controller)
    opts = DownloadOptions(url="https://example/video", output_dir=tmp_path, retry=1)

    files = dl.download(opts)

    assert resumed["called"] is True
    assert attempts["count"] == 2
    assert len(files) == 1
    assert PausingFakeYDL.instances[0].params["continuedl"] is True


def test_build_ydl_opts_enables_continuedl(tmp_path: Path) -> None:
    cfg = AppConfig()
    dl = Downloader(cfg)
    opts = DownloadOptions(url="https://example/video", output_dir=tmp_path)

    ydl_opts = dl.build_ydl_opts(opts)

    assert ydl_opts["continuedl"] is True
