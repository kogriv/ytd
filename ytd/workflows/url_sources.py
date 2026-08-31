"""Источники ссылок и распознавание плейлистов (BL-1105)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import parse_qs, urlparse

import typer

from ..console import safe_echo, safe_secho

if TYPE_CHECKING:
    from .context import DownloadContext


def looks_like_playlist_url(url: str) -> bool:
    """Грубая эвристика для определения ссылок на плейлист."""

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    path = (parsed.path or "").lower()
    if "playlist" in path:
        return True

    query = parse_qs(parsed.query)
    lists = query.get("list") or []
    return any(item.strip() for item in lists)


def is_effective_playlist(ctx: DownloadContext, url: str) -> bool:
    """Обрабатывать ли ссылку как плейлист с учётом флагов и автодетекта."""

    looks_like = looks_like_playlist_url(url)
    return (
        bool(ctx.playlist_items)
        or (ctx.playlist and looks_like)
        or (ctx.auto_detect_playlists and looks_like)
    )


def read_urls_from_file(fp: Path) -> list[str]:
    """Прочитать список ссылок: одна строка — один URL, `#` — комментарий."""

    if not fp.exists():
        raise FileNotFoundError(f"Файл не найден: {fp}")
    urls: list[str] = []
    for line in fp.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        urls.append(stripped)
    return urls


def collect_urls(url: str | None, urls_file: Path | None) -> list[str]:
    """Собрать ссылки из позиционного аргумента и файла со списком."""

    urls: list[str] = []
    if url:
        urls.append(url)
    if urls_file:
        urls.extend(read_urls_from_file(urls_file))

    if urls:
        return urls

    if urls_file is not None:
        safe_secho(
            f"Файл со ссылками пуст или не содержит валидных строк: {urls_file}",
            fg=typer.colors.YELLOW,
        )
    else:
        safe_secho("Нужно указать URL или --urls-file", fg=typer.colors.RED)
    raise typer.Exit(code=2)


def choose_interactive_playlist(
    urls: list[str],
    *,
    interactive: bool,
    playlist_flag: bool,
    auto_detect: bool,
) -> list[str]:
    """В интерактивном режиме свести список ссылок к одному плейлисту.

    Возвращает исходный список, если интерактивный режим плейлиста не применяется.
    """

    playlist_candidates = [item for item in urls if looks_like_playlist_url(item)]
    use_playlist_interactive = interactive and (
        playlist_flag or (auto_detect and bool(playlist_candidates))
    )
    if not use_playlist_interactive:
        return urls

    if not playlist_candidates:
        safe_secho(
            "Флаг --playlist указан, но ни одна ссылка не похожа на плейлист.",
            fg=typer.colors.YELLOW,
        )
        return urls

    if len(playlist_candidates) == 1:
        selected = playlist_candidates[0]
        if len(urls) > 1:
            safe_secho(
                f"Интерактивный режим будет выполнен только для плейлиста: {selected}",
                fg=typer.colors.CYAN,
            )
        return [selected]

    safe_echo()
    safe_secho("Найдено несколько плейлистов в списке ссылок.", fg=typer.colors.YELLOW)
    safe_echo("Выберите плейлист для интерактивной загрузки:")
    for idx, candidate in enumerate(playlist_candidates, start=1):
        safe_echo(f"  {idx}) {candidate}")
    safe_echo("  0) Отмена")

    while True:
        choice = typer.prompt("Ваш выбор", default="1")
        if choice == "0":
            safe_secho("Загрузка отменена", fg=typer.colors.YELLOW)
            raise typer.Exit(code=0)
        try:
            selected_idx = int(choice)
        except ValueError:
            selected_idx = -1

        if 1 <= selected_idx <= len(playlist_candidates):
            selected = playlist_candidates[selected_idx - 1]
            break

        safe_secho("Введите номер из списка.", fg=typer.colors.RED)

    safe_secho(f"Выбран плейлист: {selected}", fg=typer.colors.GREEN)
    if len(playlist_candidates) - 1:
        safe_secho(
            "Остальные плейлисты будут пропущены в интерактивном режиме.",
            fg=typer.colors.YELLOW,
        )
    if len(urls) - len(playlist_candidates):
        safe_secho(
            "Прочие ссылки из списка также будут пропущены в интерактивном режиме плейлиста.",
            fg=typer.colors.YELLOW,
        )
    return [selected]
