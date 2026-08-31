from __future__ import annotations

from pathlib import Path

import pytest

from ytd.interactive import (
    SingleVideoSetupResult,
    build_quality_options,
    collect_available_heights,
    run_single_video_interactive_setup,
)


@pytest.fixture
def sample_info() -> dict:
    return {
        "id": "abc123",
        "title": "Test Video",
        "formats": [
            {"height": 720, "vcodec": "avc1", "ext": "mp4"},
            {"height": 480, "vcodec": "avc1", "ext": "mp4"},
        ],
    }


def test_run_single_video_interactive_setup_defaults(
    sample_info: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ytd.interactive.show_quality_menu",
        lambda options: options[0],
    )
    monkeypatch.setattr(
        "ytd.interactive.configure_filename_suffix",
        lambda default: default,
    )
    monkeypatch.setattr(
        "ytd.interactive.configure_filename_prefix",
        lambda: (None, False, None),
    )
    monkeypatch.setattr(
        "ytd.interactive.find_existing_files",
        lambda output_dir, video_id: [],
    )
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: kwargs.get("default", "1"))

    result = run_single_video_interactive_setup(sample_info, tmp_path)

    assert isinstance(result, SingleVideoSetupResult)
    assert "vcodec^=avc1" in result.chosen_format
    assert result.chosen_label == "Лучшее совместимое MP4 качество"
    assert result.quality_suffix == "_best"
    assert result.file_prefix is None
    assert result.custom_name is None
    assert result.overwrite is False


def test_build_quality_options_prefers_h264_mp4_before_generic_mp4(sample_info: dict) -> None:
    height_to_ext, available_heights = collect_available_heights(sample_info["formats"])

    options = build_quality_options(height_to_ext, available_heights)

    best_label, best_format, _ = options[0]
    assert best_label == "Лучшее совместимое MP4 качество"
    assert best_format.startswith("bestvideo[vcodec^=avc1][ext=mp4]")

    option_720 = next(fmt for label, fmt, height in options if height == 720)
    assert "bestvideo[height<=720][vcodec^=avc1][ext=mp4]" in option_720
    assert option_720.index("vcodec^=avc1") < option_720.index("bestvideo[height<=720][ext=mp4]")


def test_run_single_video_interactive_setup_respects_overwrite_dialog(
    sample_info: dict,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "ytd.interactive.show_quality_menu",
        lambda options: options[0],
    )
    monkeypatch.setattr("ytd.interactive.configure_filename_suffix", lambda default: None)
    monkeypatch.setattr("ytd.interactive.configure_filename_prefix", lambda: (None, False, None))
    monkeypatch.setattr(
        "ytd.interactive.find_existing_files",
        lambda output_dir, video_id: [tmp_path / "existing.mp4"],
    )
    monkeypatch.setattr("ytd.interactive.check_existing_files_dialog", lambda output_dir, video_id: True)
    monkeypatch.setattr("typer.prompt", lambda *args, **kwargs: kwargs.get("default", "1"))

    result = run_single_video_interactive_setup(sample_info, tmp_path)

    assert result.overwrite is True
