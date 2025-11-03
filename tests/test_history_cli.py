from __future__ import annotations

import csv
import io
import json
from datetime import datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ytd.cli import app
from ytd.history import init_db, ensure_schema, record_event
from ytd.types import DownloadEvent


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


@pytest.fixture
def populated_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    db_path = tmp_path / "history.db"
    monkeypatch.setenv("YTD_HISTORY_DB", str(db_path))

    init_db(db_path)
    ensure_schema()

    events = [
        DownloadEvent(
            video_id="aaa11111111",
            url="https://youtu.be/aaa11111111",
            title="Первое видео",
            status="finished",
            started_at=datetime(2024, 3, 1, 8, 0, 0),
            finished_at=datetime(2024, 3, 1, 9, 0, 0),
            file_path=tmp_path / "first.mp4",
            playlist_id="PL-001",
            playlist_title="Сборник 1",
        ),
        DownloadEvent(
            video_id="bbb22222222",
            url="https://youtu.be/bbb22222222",
            title="Второе видео",
            status="error",
            started_at=datetime(2024, 3, 2, 9, 0, 0),
            finished_at=datetime(2024, 3, 2, 9, 15, 0),
            file_path=tmp_path / "second.mp4",
            error="Network error",
        ),
        DownloadEvent(
            video_id="ccc33333333",
            url="https://youtu.be/ccc33333333",
            title="Третье видео",
            status="finished",
            started_at=datetime(2024, 3, 3, 10, 0, 0),
            finished_at=datetime(2024, 3, 3, 10, 30, 0),
            file_path=tmp_path / "third.mp4",
            playlist_id="PL-002",
            playlist_title="Сборник 2",
        ),
        DownloadEvent(
            video_id="https://vk.com/video-12345_67890",
            url="https://vk.com/video-12345_67890",
            title="VK Видео",
            status="finished",
            started_at=datetime(2024, 3, 4, 11, 0, 0),
            finished_at=datetime(2024, 3, 4, 11, 15, 0),
            file_path=tmp_path / "vk.mp4",
        ),
    ]

    for event in events:
        record_event(event)


def test_history_list_with_filters(runner: CliRunner, populated_history: None) -> None:
    result = runner.invoke(app, ["history", "--status", "finished", "--limit", "1"])

    assert result.exit_code == 0, result.stdout
    assert "https://vk.com/video-12345_67890" in result.stdout
    assert "yt:ccc33333333" not in result.stdout
    assert "yt:aaa11111111" not in result.stdout


def test_history_list_since_and_playlist(runner: CliRunner, populated_history: None) -> None:
    since_result = runner.invoke(app, ["history", "--since", "2024-03-02T00:00:00"])

    assert since_result.exit_code == 0
    assert "yt:aaa11111111" not in since_result.stdout
    assert "yt:bbb22222222" in since_result.stdout
    assert "yt:ccc33333333" in since_result.stdout
    assert "https://vk.com/video-12345_67890" in since_result.stdout

    playlist_result = runner.invoke(app, ["history", "--playlist", "PL-001"])

    assert playlist_result.exit_code == 0
    assert "yt:aaa11111111" in playlist_result.stdout
    assert "yt:bbb22222222" not in playlist_result.stdout


def test_history_show_displays_details(runner: CliRunner, populated_history: None) -> None:
    result = runner.invoke(app, ["history", "show", "bbb22222222"])

    assert result.exit_code == 0
    assert "Второе видео" in result.stdout
    assert "Ошибка" in result.stdout


def test_history_export_jsonl(runner: CliRunner, populated_history: None) -> None:
    result = runner.invoke(app, ["history", "--status", "finished", "export", "--format", "jsonl"])

    assert result.exit_code == 0
    lines = [line for line in result.stdout.strip().splitlines() if line]
    parsed = [json.loads(line) for line in lines]

    assert {item["video_id"] for item in parsed} == {
        "yt:aaa11111111",
        "yt:ccc33333333",
        "https://vk.com/video-12345_67890",
    }
    assert all(item["status"] == "finished" for item in parsed)


def test_history_export_csv(runner: CliRunner, populated_history: None) -> None:
    result = runner.invoke(app, ["history", "--limit", "2", "export", "--format", "csv"])

    assert result.exit_code == 0
    reader = csv.DictReader(io.StringIO(result.stdout))
    rows = list(reader)

    assert len(rows) == 2
    assert rows[0]["video_id"] == "https://vk.com/video-12345_67890"
    assert rows[1]["video_id"] == "yt:ccc33333333"


def test_history_lists_normalized_identifiers(runner: CliRunner, populated_history: None) -> None:
    result = runner.invoke(app, ["history"])

    assert result.exit_code == 0
    assert "yt:aaa11111111" in result.stdout
    assert "https://vk.com/video-12345_67890" in result.stdout
