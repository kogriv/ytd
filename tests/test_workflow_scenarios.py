"""Тесты декомпозиции команды download (BL-1105)."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

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
from ytd.workflows.history_prompts import HistoryDecision
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
    ctx = make_ctx()
    assert ctx.output_dir(HistoryDecision(proceed=True)) == ctx.cfg.output
    assert ctx.output_dir(HistoryDecision(proceed=True, new_output=tmp_path)) == tmp_path


# --- остановка по требованию пользователя (BL-1110, GAP-CR-034) --------------

SCENARIO_MODULES = [single_video, playlist_interactive, playlist_batch]


def _module_id(module: object) -> str:
    return module.__name__.rsplit(".", 1)[-1]  # type: ignore[attr-defined]


@pytest.mark.parametrize("module", SCENARIO_MODULES, ids=_module_id)
@pytest.mark.parametrize("error_type", [typer.Exit, typer.Abort], ids=["exit", "abort"])
def test_scenario_does_not_swallow_user_stop(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
    error_type: type[Exception],
) -> None:
    """Выбор «завершить программу» и Ctrl+C не должны подменяться загрузкой по умолчанию."""

    def raise_stop(*args: object, **kwargs: object) -> None:
        raise error_type()

    def must_not_run(*args: object, **kwargs: object) -> None:
        raise AssertionError("после остановки загрузка не должна начинаться")

    monkeypatch.setattr(module, "fetch_info", raise_stop)
    monkeypatch.setattr(module, "download_single_url", must_not_run)

    with pytest.raises(error_type):
        module.run(make_ctx(interactive=True), VIDEO_URL, HistoryDecision(proceed=True))


@pytest.mark.parametrize("module", SCENARIO_MODULES, ids=_module_id)
def test_scenario_still_falls_back_on_real_error(
    monkeypatch: pytest.MonkeyPatch,
    module: Any,
) -> None:
    """Обычная ошибка разбора метаданных по-прежнему приводит к загрузке по умолчанию."""

    def boom(*args: object, **kwargs: object) -> None:
        raise RuntimeError("метаданные недоступны")

    calls: list[str] = []

    def fake_download(ctx: DownloadContext, url: str, decision: HistoryDecision, **kwargs: object):
        calls.append(url)
        return DownloadTotals(total_files=1)

    monkeypatch.setattr(module, "fetch_info", boom)
    monkeypatch.setattr(module, "download_single_url", fake_download)

    totals = module.run(make_ctx(interactive=True), VIDEO_URL, HistoryDecision(proceed=True))

    assert calls == [VIDEO_URL]
    assert totals.total_files == 1
