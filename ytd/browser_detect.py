"""Определение браузера для подсказок --cookies-from-browser."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path


def _map_prog_id_to_browser(prog_id: str) -> str | None:
    lowered = prog_id.lower()
    if "edge" in lowered or "msedge" in lowered:
        return "edge"
    if "chrome" in lowered:
        return "chrome"
    if "firefox" in lowered:
        return "firefox"
    if "brave" in lowered:
        return "brave"
    if "opera" in lowered:
        return "opera"
    if "vivaldi" in lowered:
        return "vivaldi"
    return None


def _detect_windows_browser() -> str | None:
    try:
        import winreg
    except ImportError:
        return None

    prog_id: str | None = None
    for subkey in (
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoiceLatest",
        r"Software\Microsoft\Windows\Shell\Associations\UrlAssociations\https\UserChoice",
    ):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, subkey) as key:
                prog_id = str(winreg.QueryValueEx(key, "ProgId")[0])
                break
        except OSError:
            continue

    if prog_id:
        mapped = _map_prog_id_to_browser(prog_id)
        if mapped:
            return mapped

    local_app_data = Path.home() / "AppData" / "Local"
    if (local_app_data / "Microsoft" / "Edge" / "User Data").exists():
        return "edge"
    if (local_app_data / "Google" / "Chrome" / "User Data").exists():
        return "chrome"
    if (local_app_data / "Mozilla" / "Firefox" / "Profiles").exists():
        return "firefox"
    return None


def _detect_mac_browser() -> str | None:
    app_support = Path.home() / "Library" / "Application Support"
    if (app_support / "Google" / "Chrome").exists():
        return "chrome"
    if (app_support / "Firefox" / "Profiles").exists():
        return "firefox"
    if (app_support / "Microsoft Edge").exists():
        return "edge"
    return "safari"


def _detect_linux_browser() -> str | None:
    home = Path.home()
    config = home / ".config"
    if (config / "google-chrome").exists():
        return "chrome"
    if (config / "chromium").exists():
        return "chromium"
    if (home / ".mozilla" / "firefox").exists():
        return "firefox"
    if (config / "microsoft-edge").exists():
        return "edge"
    if (config / "BraveSoftware" / "Brave-Browser").exists():
        return "brave"
    return None


@lru_cache(maxsize=1)
def detect_cookies_browser_hint() -> str:
    """Вернуть имя браузера для примера `--cookies-from-browser`."""

    if sys.platform == "win32":
        return _detect_windows_browser() or "edge"
    if sys.platform == "darwin":
        return _detect_mac_browser()
    return _detect_linux_browser() or "firefox"
