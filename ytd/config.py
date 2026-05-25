from __future__ import annotations

import os
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import yaml

from .types import (
    VALID_AUDIO_FORMAT,
    VALID_BROWSER_COOKIE_SOURCES,
    VALID_QUALITY,
    VALID_VIDEO_FORMAT,
    AppConfig,
)
from .utils import ensure_dir


def _validate_choice(field: str, value: str, allowed: frozenset[str]) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        allowed_list = ", ".join(sorted(allowed))
        raise ValueError(f"Недопустимое значение {field}: {value!r}. Допустимо: {allowed_list}")
    return normalized

_ENV_MAP: dict[str, str] = {
    "output": "YTD_OUTPUT",
    "quality": "YTD_QUALITY",
    "video_format": "YTD_VIDEO_FORMAT",
    "audio_only": "YTD_AUDIO_ONLY",
    "audio_format": "YTD_AUDIO_FORMAT",
    "name_template": "YTD_NAME_TEMPLATE",
    "subtitles": "YTD_SUBTITLES",
    "proxy": "YTD_PROXY",
    "cookies_file": "YTD_COOKIES_FILE",
    "cookies_from_browser": "YTD_COOKIES_FROM_BROWSER",
    "retry": "YTD_RETRY",
    "retry_delay": "YTD_RETRY_DELAY",
    "save_metadata": "YTD_SAVE_METADATA",
    "history_enabled": "YTD_HISTORY_ENABLED",
    "history_db": "YTD_HISTORY_DB",
    "pause_between_videos": "YTD_PAUSE_BETWEEN_VIDEOS",
    "pause_key": "YTD_PAUSE_KEY",
    "resume_key": "YTD_RESUME_KEY",
    "intra_video_pause": "YTD_INTRA_VIDEO_PAUSE",
    "interactive_by_default": "YTD_INTERACTIVE_BY_DEFAULT",
    "auto_detect_playlists": "YTD_AUTO_DETECT_PLAYLISTS",
    "no_progress": "YTD_NO_PROGRESS",
}


def _validate_proxy_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https", "socks4", "socks5", "socks5h"}:
        raise ValueError(
            f"Неподдерживаемая схема прокси: {parsed.scheme!r}. "
            "Используйте http, https, socks4, socks5 или socks5h."
        )
    if not parsed.netloc:
        raise ValueError("URL прокси должен содержать хост, например http://127.0.0.1:8080")
    return value.strip()


def _parse_bool(val: str) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path or not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        return {}
    return data


def _apply_file_overrides(base: AppConfig, cfg_dict: dict[str, Any]) -> AppConfig:
    if not cfg_dict:
        return base
    updates: dict[str, Any] = {}
    for key in asdict(base).keys():
        if key in cfg_dict and cfg_dict[key] is not None:
            updates[key] = cfg_dict[key]
    return replace(base, **_normalize_types(updates))


def _apply_env_overrides(base: AppConfig) -> AppConfig:
    updates: dict[str, Any] = {}
    for field, env_name in _ENV_MAP.items():
        if env_name in os.environ:
            raw = os.environ[env_name]
            if field in {"output", "save_metadata"}:
                updates[field] = raw
            elif field == "cookies_file":
                updates[field] = raw
            elif field == "subtitles":
                updates[field] = [s for s in [p.strip() for p in raw.split(",")] if s]
            elif field in {"retry"}:
                try:
                    updates[field] = int(raw)
                except ValueError:
                    continue
            elif field in {"retry_delay"}:
                try:
                    updates[field] = float(raw)
                except ValueError:
                    continue
            elif field in {"audio_only", "history_enabled", "pause_between_videos", "intra_video_pause", "interactive_by_default", "auto_detect_playlists", "no_progress"}:
                updates[field] = _parse_bool(raw)
            else:
                updates[field] = raw
    if not updates:
        return base
    return replace(base, **_normalize_types(updates))


def _normalize_types(updates: dict[str, Any]) -> dict[str, Any]:
    # Приведение строк -> Path для путей
    out: dict[str, Any] = dict(updates)
    if "output" in out and isinstance(out["output"], str):
        out["output"] = Path(out["output"]).expanduser()
    if "save_metadata" in out and isinstance(out["save_metadata"], str):
        out["save_metadata"] = Path(out["save_metadata"]).expanduser()
    if "history_db" in out and isinstance(out["history_db"], str):
        out["history_db"] = Path(out["history_db"]).expanduser()
    if "cookies_file" in out and isinstance(out["cookies_file"], str):
        out["cookies_file"] = Path(out["cookies_file"]).expanduser()
    if "proxy" in out and isinstance(out["proxy"], str) and out["proxy"].strip():
        out["proxy"] = _validate_proxy_url(out["proxy"])
    if "quality" in out and isinstance(out["quality"], str):
        out["quality"] = _validate_choice("quality", out["quality"], VALID_QUALITY)
    if "audio_format" in out and isinstance(out["audio_format"], str):
        out["audio_format"] = _validate_choice("audio_format", out["audio_format"], VALID_AUDIO_FORMAT)
    if "video_format" in out and isinstance(out["video_format"], str):
        out["video_format"] = _validate_choice("video_format", out["video_format"], VALID_VIDEO_FORMAT)
    if "cookies_from_browser" in out and isinstance(out["cookies_from_browser"], str):
        browser = out["cookies_from_browser"].strip()
        if not browser:
            out["cookies_from_browser"] = None
        else:
            out["cookies_from_browser"] = _validate_choice(
                "cookies_from_browser",
                browser,
                VALID_BROWSER_COOKIE_SOURCES,
            )
    return out


def _normalize_and_prepare(cfg: AppConfig) -> AppConfig:
    # Нормализация путей и подготовка директорий
    output = Path(cfg.output).expanduser()
    if not output.is_absolute():
        output = Path.cwd() / output
    ensure_dir(output)
    save_meta = cfg.save_metadata
    if save_meta is not None:
        save_meta = Path(save_meta).expanduser()
        if not save_meta.is_absolute():
            save_meta = Path.cwd() / save_meta
        ensure_dir(save_meta.parent)
    history_db = Path(cfg.history_db).expanduser()
    if not history_db.is_absolute():
        history_db = Path.cwd() / history_db
    ensure_dir(history_db.parent)
    return replace(cfg, output=output, save_metadata=save_meta, history_db=history_db)


def load_config(config_path: Path | None = None) -> AppConfig:
    """Загрузить конфигурацию из файла/ENV и вернуть объект AppConfig.

    Приоритет источников: CLI (накладывается отдельно) > ENV > файл > дефолты.
    Поиск файла: указанная `config_path` -> переменная YTD_CONFIG -> `./ytd.config.yaml`.
    """
    base = AppConfig()

    # Определяем файл конфига
    if config_path is None:
        env_cfg = os.environ.get("YTD_CONFIG")
        if env_cfg:
            config_path = Path(env_cfg)
        else:
            config_path = Path.cwd() / "ytd.config.yaml"

    file_data = _load_yaml(config_path)
    cfg = _apply_file_overrides(base, file_data)
    cfg = _apply_env_overrides(cfg)
    cfg = _normalize_and_prepare(cfg)
    return cfg


def merge_cli_overrides(cfg: AppConfig, overrides: dict) -> AppConfig:
    """Наложить значения из CLI (overrides) поверх существующего конфига и вернуть копию.

    Пример overrides: {"output": Path("downloads"), "audio_only": True}
    """
    if not overrides:
        return cfg
    norm = _normalize_types({k: v for k, v in overrides.items() if v is not None})
    merged = replace(cfg, **norm)
    # Повторная нормализация директорий, если они были изменены
    return _normalize_and_prepare(merged)
