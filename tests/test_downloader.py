from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path
import time as _time

import pytest

from ytd.downloader import Downloader
from ytd.types import AppConfig, DownloadOptions


class FakeYDL:
    """Простая заглушка для yt_dlp.YoutubeDL с минимально нужным API."""

    failures: int = 0  # количество последовательных сбоев перед успехом
    instances: list["FakeYDL"] = []

    def __init__(self, params: dict):
        self.params = params
        FakeYDL.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def extract_info(self, url: str, download: bool):
        # эмулируем сетевой сбой указанное число раз
        if FakeYDL.failures > 0:
            FakeYDL.failures -= 1
            raise Exception("network error")
        info = {"id": "abc", "title": "Title", "ext": "mp4", "url": url}
        # при реальной загрузке вызовем хуки с 'finished'
        if download:
            hooks = self.params.get("progress_hooks", [])
            # смоделируем итоговый путь исходя из outtmpl (упрощённо)
            tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
            out = (
                tmpl.replace("%(title)s", info["title"])  # noqa: P103
                .replace("%(id)s", info["id"])  # noqa: P103
                .replace("%(ext)s", info["ext"])  # noqa: P103
            )
            for h in hooks:
                h({"status": "finished", "filename": out})
        return info

    def prepare_filename(self, info):
        tmpl = self.params.get("outtmpl", "%(title)s.%(ext)s")
        return (
            tmpl.replace("%(title)s", info.get("title", ""))
            .replace("%(id)s", info.get("id", ""))
            .replace("%(ext)s", info.get("ext", "mp4"))
        )


@pytest.fixture(autouse=True)
def patch_sleep(monkeypatch: pytest.MonkeyPatch):
    # чтобы тесты ретраев были быстрыми
    monkeypatch.setattr(_time, "sleep", lambda s: None)


def test_build_ydl_opts_audio_only_includes_postprocessor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # подменим поиск ffmpeg, чтобы опция присутствовала предсказуемо
    monkeypatch.setenv("YTD_FFMPEG", str(tmp_path / "ffmpeg_bin"))
    (tmp_path / "ffmpeg_bin").mkdir(parents=True)

    cfg = AppConfig()
    dl = Downloader(cfg)
    opts = DownloadOptions(
        url="https://example/y",
        output_dir=tmp_path / "out",
        audio_only=True,
        audio_format="m4a",
        subtitles=["ru"],
        proxy="http://proxy",
        retry=4,
        retry_delay=0.1,
        name_template="%(title)s [%(id)s].%(ext)s",
    )

    ydl_opts = dl.build_ydl_opts(opts)

    assert ydl_opts["noplaylist"] is True
    assert ydl_opts["writesubtitles"] is True
    assert ydl_opts["subtitlelangs"] == ["ru"]
    assert ydl_opts["proxy"] == "http://proxy"
    assert "ffmpeg_location" in ydl_opts

    # формат и постпроцессор
    assert "bestaudio" in ydl_opts["format"]
    assert "ext=m4a" in ydl_opts["format"]
    pps = ydl_opts.get("postprocessors", [])
    assert any(pp.get("key") == "FFmpegExtractAudio" for pp in pps)

    # outtmpl должен включать каталог и шаблон
    outtmpl = ydl_opts["outtmpl"]
    assert str(tmp_path / "out") in outtmpl
    assert "%(title)s" in outtmpl


def test_build_ydl_opts_video_quality_720p_mp4(tmp_path: Path):
    cfg = AppConfig()
    dl = Downloader(cfg)
    opts = DownloadOptions(
        url="u",
        output_dir=tmp_path,
        audio_only=False,
        video_format="mp4",
        quality="720p",
    )

    ydl_opts = dl.build_ydl_opts(opts)
    fmt = ydl_opts["format"]
    assert "height<=720" in fmt
    assert "ext=mp4" in fmt


def test_download_dry_run_calls_extract_info(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # подменим модуль yt_dlp в нашем модуле
    monkeypatch.setattr("ytd.downloader.yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL), raising=True)

    cfg = AppConfig(output=tmp_path)
    dl = Downloader(cfg)

    dopts = DownloadOptions(url="https://example/video", output_dir=tmp_path, dry_run=True)
    files = dl.download(dopts)

    # dry-run не возвращает файлов и вызывает extract_info с download=False
    assert files == []
    assert FakeYDL.instances[-1].params.get("skip_download") is True


def test_download_with_retries_success(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr("ytd.downloader.yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL), raising=True)

    # эмулируем 2 сбоя, затем успех
    FakeYDL.failures = 2

    cfg = AppConfig(output=tmp_path)
    dl = Downloader(cfg)

    dopts = DownloadOptions(
        url="https://example/video",
        output_dir=tmp_path,
        retry=3,
        retry_delay=0.01,
    )

    files = dl.download(dopts)

    # после успеха хук должен добавить итоговый файл
    assert len(files) == 1
    assert Path(files[0]).parent == tmp_path


def test_download_saves_metadata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    # подменим yt_dlp
    monkeypatch.setattr("ytd.downloader.yt_dlp", SimpleNamespace(YoutubeDL=FakeYDL), raising=True)

    cfg = AppConfig(output=tmp_path)
    dl = Downloader(cfg)

    meta_path = tmp_path / "data" / "meta.jsonl"
    dopts = DownloadOptions(
        url="https://example/video",
        output_dir=tmp_path,
        save_metadata=meta_path,
    )

    _ = dl.download(dopts)

    # файл метаданных должен быть создан и содержать запись с id
    assert meta_path.exists()
    text = meta_path.read_text(encoding="utf-8")
    assert "\n" in text
    assert "abc" in text or "Title" in text
