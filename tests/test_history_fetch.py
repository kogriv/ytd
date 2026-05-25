from __future__ import annotations

from pathlib import Path

from ytd.history.storage import ensure_schema, fetch_download, init_db, record_event, update_download
from ytd.types import DownloadEvent


def test_fetch_download_prefers_video_id_over_url(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    init_db(db_path)
    ensure_schema()

    record_event(
        DownloadEvent(
            video_id="yt:aaa11111111",
            url="https://youtu.be/aaa11111111",
            title="By ID",
            status="success",
        )
    )
    record_event(
        DownloadEvent(
            video_id="yt:bbb22222222",
            url="https://youtu.be/bbb22222222",
            title="By URL",
            status="success",
        )
    )

    entry = fetch_download(
        video_id="yt:aaa11111111",
        url="https://youtu.be/bbb22222222",
    )

    assert entry is not None
    assert entry["title"] == "By ID"


def test_update_download_prefers_video_id_over_url(tmp_path: Path) -> None:
    db_path = tmp_path / "history.db"
    init_db(db_path)
    ensure_schema()

    record_event(
        DownloadEvent(
            video_id="yt:aaa11111111",
            url="https://youtu.be/aaa11111111",
            title="Target",
            status="success",
        )
    )
    record_event(
        DownloadEvent(
            video_id="yt:bbb22222222",
            url="https://youtu.be/bbb22222222",
            title="Other",
            status="success",
        )
    )

    update_download(
        video_id="yt:aaa11111111",
        url="https://youtu.be/bbb22222222",
        last_action="overwrite",
    )

    first = fetch_download(video_id="yt:aaa11111111")
    second = fetch_download(video_id="yt:bbb22222222")

    assert first is not None
    assert first["last_action"] == "overwrite"
    assert second is not None
    assert second.get("last_action") is None
