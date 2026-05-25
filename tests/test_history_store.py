from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from ytd.history.storage import HistoryStore, set_default_store
from ytd.types import DownloadEvent


def test_history_store_instances_are_isolated(tmp_path: Path) -> None:
    db_a = tmp_path / "a.db"
    db_b = tmp_path / "b.db"
    store_a = HistoryStore(db_a)
    store_b = HistoryStore(db_b)

    store_a.record_event(
        DownloadEvent(
            video_id="yt:vidaaaaaaaaa",
            url="https://example.com/a",
            title="Video A",
            status="success",
            started_at=datetime.now(tz=UTC),
            finished_at=datetime.now(tz=UTC),
        )
    )

    assert store_a.fetch_download(video_id="yt:vidaaaaaaaaa") is not None
    assert store_b.fetch_download(video_id="yt:vidaaaaaaaaa") is None


def test_init_db_sets_default_store(tmp_path: Path) -> None:
    from ytd.history.storage import get_default_store, init_db

    set_default_store(None)
    db_path = tmp_path / "default.db"
    init_db(db_path)

    store = get_default_store()
    assert store.path == db_path

    store.record_event(
        DownloadEvent(
            video_id="yt:vidbbbbbbbbb",
            url="https://example.com/b",
            title="Video B",
            status="success",
        )
    )
    assert store.fetch_download(video_id="yt:vidbbbbbbbbb") is not None
