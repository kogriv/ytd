"""Тесты декомпозиции команды download (BL-1105)."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import typer

from ytd.types import AppConfig
from ytd.workflows import (
    download_command,
    download_one,
    playlist_batch,
    playlist_interactive,
    single_video,
)
from ytd.workflows.context import DownloadContext, DownloadTotals
from ytd.workflows.url_sources import (
    choose_interactive_playlist,
    collect_urls,
    is_effective_playlist,
    looks_like_playlist_url,
)

PLAYLIST_URL = "https://www.youtube.com/playlist?list=PLtest"
VIDEO_URL = "https://www.youtube.com/watch?v=abcdefghijk"


def make_ctx(
    *,
    interactive: bool = False,
    playlist: bool = False,
    playlist_items: str | None = None,
    pause_controller: object | None = None,
    auto_detect: bool = True,
) -> DownloadContext:
    cfg = AppConfig(auto_detect_playlists=auto_detect)
    return DownloadContext(
        cfg=cfg,
        logger=logging.getLogger("ytd.test"),
        dl=None,  # сценарий выбирается без обращения к загрузчику
        dry_run=False,
        interactive=interactive,
        history_available=False,
        playlist=playlist,
        playlist_items=playlist_items,
        pause_controller=pause_controller,
    )


# --- url_sources -----------------------------------------------------------


def test_collect_urls_merges_argument_and_file(tmp_path: Path) -> None:
    urls_file = tmp_path / "urls.txt"
    urls_file.write_text(
        "\n".join(["# комментарий", "", "https://example.com/a", "  https://example.com/b  "]),
        encoding="utf-8",
    )

    assert collect_urls(VIDEO_URL, urls_file) == [
        VIDEO_URL,
        "https://example.com/a",
        "https://example.com/b",
    ]


def test_collect_urls_without_sources_exits_with_code_2() -> None:
    with pytest.raises(typer.Exit) as exc_info:
        collect_urls(None, None)
    assert exc_info.value.exit_code == 2


def test_collect_urls_missing_file_raises() -> None:
    with pytest.raises(FileNotFoundError):
        collect_urls(None, Path("нет-такого-файла.txt"))


def test_looks_like_playlist_url() -> None:
    assert looks_like_playlist_url(PLAYLIST_URL)
    assert looks_like_playlist_url("https://www.youtube.com/watch?v=x&list=PL1")
    assert not looks_like_playlist_url(VIDEO_URL)


def test_choose_interactive_playlist_reduces_to_single_candidate() -> None:
    urls = [VIDEO_URL, PLAYLIST_URL]
    result = choose_interactive_playlist(
        urls, interactive=True, playlist_flag=False, auto_detect=True
    )
    assert result == [PLAYLIST_URL]


def test_choose_interactive_playlist_keeps_urls_without_interactive() -> None:
    urls = [VIDEO_URL, PLAYLIST_URL]
    result = choose_interactive_playlist(
        urls, interactive=False, playlist_flag=False, auto_detect=True
    )
    assert result == urls


def test_is_effective_playlist_respects_flags() -> None:
    assert is_effective_playlist(make_ctx(), PLAYLIST_URL)
    assert not is_effective_playlist(make_ctx(auto_detect=False), PLAYLIST_URL)
    assert is_effective_playlist(make_ctx(auto_detect=False, playlist=True), PLAYLIST_URL)
    # --playlist-items включает режим плейлиста даже для «одиночной» ссылки
    assert is_effective_playlist(make_ctx(playlist_items="1-3"), VIDEO_URL)
    assert not is_effective_playlist(make_ctx(), VIDEO_URL)


# --- выбор сценария --------------------------------------------------------


def test_select_scenario_interactive_playlist() -> None:
    ctx = make_ctx(interactive=True)
    assert download_command.select_scenario(ctx, PLAYLIST_URL) is playlist_interactive.run


def test_select_scenario_interactive_single_video() -> None:
    ctx = make_ctx(interactive=True)
    assert download_command.select_scenario(ctx, VIDEO_URL) is single_video.run


def test_select_scenario_playlist_with_pause_controller() -> None:
    ctx = make_ctx(pause_controller=object())
    assert download_command.select_scenario(ctx, PLAYLIST_URL) is playlist_batch.run


def test_select_scenario_defaults_to_direct_download() -> None:
    assert download_command.select_scenario(make_ctx(), VIDEO_URL) is download_one.run
    # без контроллера пауз плейлист уходит целиком в yt-dlp
    assert download_command.select_scenario(make_ctx(), PLAYLIST_URL) is download_one.run


# --- итоги -----------------------------------------------------------------


def test_download_totals_merge_and_exit_codes() -> None:
    totals = DownloadTotals()
    totals.merge(DownloadTotals(total_files=2))
    totals.merge(DownloadTotals(failed=1))

    assert (totals.total_files, totals.failed) == (2, 1)
    assert totals.exit_code() == 2  # частичный успех
    assert DownloadTotals(total_files=3).exit_code() == 0
    assert DownloadTotals(failed=2).exit_code() == 1
    assert DownloadTotals().exit_code() == 2  # нечего было качать


def test_context_output_dir_follows_history_decision(tmp_path: Path) -> None:
    from ytd.workflows.history_prompts import HistoryDecision

    ctx = make_ctx()
    assert ctx.output_dir(HistoryDecision(proceed=True)) == ctx.cfg.output
    assert ctx.output_dir(HistoryDecision(proceed=True, new_output=tmp_path)) == tmp_path
