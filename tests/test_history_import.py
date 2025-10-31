from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pytest

from ytd.history.storage import init_db, ensure_schema, import_from_jsonl, list_downloads


@pytest.fixture
def meta_file(tmp_path: Path) -> Path:
    meta = tmp_path / "data" / "meta.jsonl"
    meta.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        {"id": "aaa11111111", "title": "Первое", "webpage_url": "https://youtu.be/aaa11111111", "_filename": "downloads/first.mp4", "upload_date": "20240511"},
        {"id": "bbb22222222", "title": "Второе", "timestamp": 0, "requested_downloads": [{"filepath": "downloads/second.mp4"}]},
        "not a dict",
    ]
    meta.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False) if isinstance(item, dict) else str(item)
            for item in lines
        ),
        encoding="utf-8",
    )
    return meta


def test_import_from_jsonl_populates_history(tmp_path: Path, meta_file: Path) -> None:
    db_path = tmp_path / "history.db"
    init_db(db_path)
    created = ensure_schema()
    assert created is True

    imported = import_from_jsonl(meta_file)
    assert imported == 2

    entries = list_downloads()
    assert len(entries) == 2

    first = {item["video_id"]: item for item in entries}["aaa11111111"]
    assert first["title"] == "Первое"
    assert first["url"] == "https://youtu.be/aaa11111111"
    assert first["file_path"].endswith("downloads/first.mp4")
    assert first["finished_at"] == datetime.strptime("20240511", "%Y%m%d").isoformat()

    second = {item["video_id"]: item for item in entries}["bbb22222222"]
    expected_ts = datetime.fromtimestamp(0).isoformat(timespec="seconds")
    assert second["finished_at"] == expected_ts
    assert second["file_path"].endswith("downloads/second.mp4")


def test_import_from_jsonl_skips_when_table_not_empty(tmp_path: Path, meta_file: Path) -> None:
    db_path = tmp_path / "history.db"
    init_db(db_path)
    created = ensure_schema()
    assert created is True

    # Первая загрузка
    first_import = import_from_jsonl(meta_file)
    assert first_import == 2

    # Повторный импорт не должен ничего добавить
    second_import = import_from_jsonl(meta_file)
    assert second_import == 0

    entries = list_downloads()
    assert len(entries) == 2


def test_import_from_jsonl_missing_file(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    init_db(db_path)
    created = ensure_schema()
    assert created is True

    missing = tmp_path / "missing.jsonl"
    assert import_from_jsonl(missing) == 0
