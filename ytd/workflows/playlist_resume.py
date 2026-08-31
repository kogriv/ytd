"""Определение уже скачанных элементов плейлиста и выбор, что качать (BL-1105)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import typer

from ..console import safe_secho

if TYPE_CHECKING:
    from .context import DownloadContext


def resolve_download_indices(
    ctx: DownloadContext,
    output_dir: Path,
    entries: list[dict[str, Any]],
) -> tuple[set[int] | None, bool]:
    """Спросить пользователя, какие элементы качать.

    Returns:
        (индексы для загрузки или None — все, признак «плейлист пропустить целиком»)
    """

    from .. import interactive as ia  # позднее связывание: тесты патчат ytd.interactive.*

    existing_map, missing_indices = ia.analyze_playlist_progress(output_dir, entries)
    if not existing_map:
        return None, False

    selected_indices, delete_existing = ia.prompt_playlist_resume(
        entries,
        existing_map,
        missing_indices,
    )

    if delete_existing:
        _delete_existing_files(ctx, existing_map)

    if selected_indices:
        return set(selected_indices), False
    if delete_existing:
        return set(range(1, len(entries) + 1)), False

    safe_secho(
        "[OK] Все видео плейлиста уже скачаны — загрузка не требуется",
        fg=typer.colors.GREEN,
    )
    return None, True


def _delete_existing_files(
    ctx: DownloadContext,
    existing_map: dict[int, list[Path]],
) -> None:
    safe_secho("Удаляем найденные файлы...", fg=typer.colors.YELLOW)
    removed = 0
    for files in existing_map.values():
        for file_path in files:
            try:
                file_path.unlink()
                removed += 1
            except FileNotFoundError:
                continue
            except OSError as unlink_err:
                ctx.logger.warning("Не удалось удалить %s: %s", file_path, unlink_err)
                safe_secho(
                    f"[WARN] Не удалось удалить {file_path.name}: {unlink_err}",
                    fg=typer.colors.YELLOW,
                )
    safe_secho(
        f"✓ Удалено файлов: {removed}. Плейлист будет скачан заново.",
        fg=typer.colors.CYAN,
    )


def existing_files_map(
    output_dir: Path,
    entries: list[dict[str, Any]],
) -> dict[int, list[Path]]:
    """Актуальная карта «индекс → уже скачанные файлы» (после возможного удаления)."""

    from .. import interactive as ia

    existing_map, _ = ia.analyze_playlist_progress(output_dir, entries)
    return existing_map
