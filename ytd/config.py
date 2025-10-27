from __future__ import annotations

import os
from dataclasses import replace, asdict
from pathlib import Path
from typing import Optional, Any

import yaml

from .types import AppConfig
from .utils import ensure_dir


_ENV_MAP: dict[str, str] = {
    "output": "YTD_OUTPUT",
    "quality": "YTD_QUALITY",
    "video_format": "YTD_VIDEO_FORMAT",
    "audio_only": "YTD_AUDIO_ONLY",
    "audio_format": "YTD_AUDIO_FORMAT",
    "name_template": "YTD_NAME_TEMPLATE",
    "subtitles": "YTD_SUBTITLES",
    "proxy": "YTD_PROXY",
    "retry": "YTD_RETRY",
    "retry_delay": "YTD_RETRY_DELAY",
    "save_metadata": "YTD_SAVE_METADATA",
    "pause_between_videos": "YTD_PAUSE_BETWEEN_VIDEOS",
    "pause_key": "YTD_PAUSE_KEY",
    "resume_key": "YTD_RESUME_KEY",
}


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
            elif field in {"audio_only"}:
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
    return replace(cfg, output=output, save_metadata=save_meta)


def load_config(config_path: Optional[Path] = None) -> AppConfig:
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
