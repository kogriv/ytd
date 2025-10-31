from pathlib import Path
import pytest

from ytd.types import DownloadOptions, AppConfig


def test_download_options_defaults():
    url = "https://example.com/video"
    opts = DownloadOptions(url=url)

    assert opts.url == url
    assert isinstance(opts.output_dir, Path)
    assert opts.output_dir == Path("downloads")

    assert opts.audio_only is False
    assert opts.audio_format == "m4a"
    assert opts.video_format == "mp4"
    assert opts.quality == "best"
    assert opts.name_template == "%(title)s [%(id)s].%(ext)s"
    assert opts.subtitles == []
    assert opts.proxy is None
    assert opts.retry == 3
    assert pytest.approx(opts.retry_delay) == 5.0
    assert isinstance(opts.save_metadata, (type(None), Path))
    assert opts.save_metadata == Path("data/meta.jsonl")
    assert opts.dry_run is False
    assert opts.playlist is False


def test_download_options_overrides():
    url = "https://example.com/playlist"
    opts = DownloadOptions(
        url=url,
        output_dir=Path("D:/dl"),
        audio_only=True,
        audio_format="mp3",
        video_format="webm",
        quality="720p",
        name_template="%(title)s.%(ext)s",
        subtitles=["ru", "en"],
        proxy="http://127.0.0.1:8080",
        retry=5,
        retry_delay=2.5,
        dry_run=True,
        playlist=True,
    )

    assert opts.url == url
    assert opts.output_dir == Path("D:/dl")
    assert opts.audio_only is True
    assert opts.audio_format == "mp3"
    assert opts.video_format == "webm"
    assert opts.quality == "720p"
    assert opts.name_template == "%(title)s.%(ext)s"
    assert opts.subtitles == ["ru", "en"]
    assert opts.proxy == "http://127.0.0.1:8080"
    assert opts.retry == 5
    assert pytest.approx(opts.retry_delay) == 2.5
    assert opts.dry_run is True
    assert opts.playlist is True


def test_app_config_defaults():
    cfg = AppConfig()

    assert isinstance(cfg.output, Path)
    assert cfg.output == Path("downloads")
    assert cfg.quality == "best"
    assert cfg.video_format == "mp4"
    assert cfg.audio_only is False
    assert cfg.audio_format == "m4a"
    assert cfg.name_template == "%(title)s [%(id)s].%(ext)s"
    assert cfg.subtitles == []
    assert cfg.proxy is None
    assert cfg.retry == 3
    assert pytest.approx(cfg.retry_delay) == 5.0
    assert isinstance(cfg.save_metadata, (type(None), Path))
    assert cfg.save_metadata == Path("data/meta.jsonl")
    assert cfg.history_enabled is True
    assert cfg.history_db == Path("data/history.db")


def test_slots_prevent_new_attributes():
    opts = DownloadOptions(url="u")
    with pytest.raises(AttributeError):
        # slots запрещают добавление новых атрибутов
        setattr(opts, "new_field", 123)
