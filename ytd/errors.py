"""Классификация ошибок загрузки и подсказки пользователю."""

from __future__ import annotations

from .browser_detect import detect_cookies_browser_hint

_ANTIBOT_MARKERS: tuple[str, ...] = (
    "sign in to confirm",
    "not a bot",
    "confirm you're not a bot",
    "confirm you’re not a bot",
    "login required",
    "cookies",
    "use --cookies",
    "http error 429",
    "too many requests",
)


def looks_like_antibot_error(exc: BaseException) -> bool:
    """Определить, похожа ли ошибка на anti-bot / rate limit площадки."""
    parts: list[str] = [str(exc).lower()]
    cause = exc.__cause__ or exc.__context__
    if isinstance(cause, BaseException):
        parts.append(str(cause).lower())
    text = " ".join(parts)
    return any(marker in text for marker in _ANTIBOT_MARKERS)


def antibot_hint(*, cookies_from_browser_example: str | None = None) -> str:
    """Текст подсказки при anti-bot ошибке."""
    browser = cookies_from_browser_example or detect_cookies_browser_hint()
    return (
        "Похоже на блокировку anti-bot или лимит запросов. Попробуйте:\n"
        f"  • ytd download URL --cookies-from-browser {browser}\n"
        "  • ytd download URL --cookies /path/to/cookies.txt\n"
        "  • задать cookies_from_browser или cookies_file в ytd.config.yaml\n"
        "  • снизить частоту загрузок или использовать VPN/прокси (--proxy)"
    )
