from __future__ import annotations

import os
from pathlib import Path

import pytest

from ytd.config import load_config, merge_cli_overrides
from ytd.types import AppConfig


def test_load_config_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Без файла и ENV — дефолты
    monkeypatch.delenv("YTD_CONFIG", raising=False)
    monkeypatch.delenv("YTD_OUTPUT", raising=False)
    monkeypatch.delenv("YTD_HISTORY_ENABLED", raising=False)

    monkeypatch.chdir(tmp_path)
    cfg = load_config()

    assert isinstance(cfg, AppConfig)
    assert cfg.output == tmp_path / "downloads"
    assert cfg.quality == "best"
    assert cfg.save_metadata == tmp_path / "data" / "meta.jsonl"
    assert cfg.history_enabled is True
    assert cfg.history_db == tmp_path / "data" / "history.db"
    # Директории должны быть созданы
    assert (tmp_path / "downloads").is_dir()
    assert (tmp_path / "data").is_dir()
    assert (tmp_path / "data" / "history.db").parent.is_dir()


def test_load_config_from_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "ytd.config.yaml"
    cfg_file.write_text(
        """
output: ./dl
quality: 720p
video_format: webm
audio_only: true
audio_format: mp3
name_template: "%(title)s.%(ext)s"
subtitles: [ru, en]
proxy: http://localhost:8888
retry: 5
retry_delay: 1.5
save_metadata: ./info/meta.jsonl
history_enabled: false
history_db: ./storage/custom-history.db
""",
        encoding="utf-8",
    )

    cfg = load_config()

    assert cfg.output == tmp_path / "dl"
    assert cfg.quality == "720p"
    assert cfg.video_format == "webm"
    assert cfg.audio_only is True
    assert cfg.audio_format == "mp3"
    assert cfg.name_template == "%(title)s.%(ext)s"
    assert cfg.subtitles == ["ru", "en"]
    assert cfg.proxy == "http://localhost:8888"
    assert cfg.retry == 5
    assert cfg.retry_delay == 1.5
    assert cfg.save_metadata == tmp_path / "info" / "meta.jsonl"
    assert cfg.history_enabled is False
    assert cfg.history_db == tmp_path / "storage" / "custom-history.db"
    # Папки созданы
    assert (tmp_path / "dl").is_dir()
    assert (tmp_path / "info").is_dir()
    assert (tmp_path / "storage").is_dir()


def test_env_overrides_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    cfg_file = tmp_path / "ytd.config.yaml"
    cfg_file.write_text("output: ./dl\nproxy: http://file-proxy\n", encoding="utf-8")

    monkeypatch.setenv("YTD_OUTPUT", str(tmp_path / "envdl"))
    monkeypatch.setenv("YTD_PROXY", "http://env-proxy")
    monkeypatch.setenv("YTD_SUBTITLES", "ru,en")
    monkeypatch.setenv("YTD_AUDIO_ONLY", "true")
    monkeypatch.setenv("YTD_HISTORY_ENABLED", "false")

    cfg = load_config()

    assert cfg.output == tmp_path / "envdl"
    assert cfg.proxy == "http://env-proxy"
    assert cfg.subtitles == ["ru", "en"]
    assert cfg.audio_only is True
    assert cfg.history_enabled is False


def test_merge_cli_overrides(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    cfg = load_config()

    merged = merge_cli_overrides(
        cfg,
        {
            "output": tmp_path / "cli",
            "audio_only": True,
            "retry": 7,
        },
    )

    assert merged.output == tmp_path / "cli"
    assert merged.audio_only is True
    assert merged.retry == 7
    # Папка должна быть создана
    assert (tmp_path / "cli").is_dir()
