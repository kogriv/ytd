from __future__ import annotations

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from ytd.cli import app


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _get_url() -> str:
    url = os.environ.get("YTD_IT_URL")
    if not url:
        pytest.skip("YTD_IT_URL is not set; skipping integration tests")
    return url


def test_integration_info(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    url = _get_url()

    # В случае реального запуска требуется доступный ffmpeg (PATH / tools/ffmpeg/**/bin)
    res = runner.invoke(app, ["info", url, "--json"])

    assert res.exit_code == 0
    assert '"id"' in res.stdout or '"title"' in res.stdout


def test_integration_download_dry_run(runner: CliRunner, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    url = _get_url()

    res = runner.invoke(app, ["download", url, "--dry-run", "--output", str(tmp_path / "dl")])

    assert res.exit_code == 0
    assert "Dry-run завершён" in res.stdout
