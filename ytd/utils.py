from __future__ import annotations

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any, Mapping, Callable, Optional


def ensure_dir(path: Path) -> None:
    """Гарантировать существование каталога (idempotent)."""
    Path(path).mkdir(parents=True, exist_ok=True)


def save_metadata_jsonl(meta: Mapping[str, Any], path: Path) -> None:
    """Добавить запись метаданных в JSONL-файл.

    - Гарантирует наличие каталога
    - Пишет одну JSON-запись в строку (UTF-8, без ASCII-эскейпа)
    - Очищает несериализуемые объекты (например, постпроцессоры yt-dlp)
    """
    ensure_dir(Path(path).parent)
    # Очистим мета от несериализуемых объектов
    clean_meta = _clean_for_json(meta)
    line = json.dumps(clean_meta, ensure_ascii=False)
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(line + "\n")


def _clean_for_json(obj: Any) -> Any:
    """Рекурсивно очистить объект от несериализуемых в JSON элементов."""
    if isinstance(obj, dict):
        return {k: _clean_for_json(v) for k, v in obj.items() 
                if not k.startswith("_") and _is_json_serializable(v)}
    elif isinstance(obj, (list, tuple)):
        return [_clean_for_json(item) for item in obj if _is_json_serializable(item)]
    elif isinstance(obj, (str, int, float, bool, type(None))):
        return obj
    else:
        return str(obj)  # Преобразуем несериализуемые типы в строку


def _is_json_serializable(obj: Any) -> bool:
    """Проверить, можно ли сериализовать объект в JSON."""
    if isinstance(obj, (str, int, float, bool, type(None))):
        return True
    if isinstance(obj, (list, tuple, dict)):
        return True
    # Любые другие объекты (классы, функции и т.п.) считаем несериализуемыми
    return False


_INVALID_CHARS = r"<>:/\\|\?\*\""  # набор недопустимых символов для Windows (включая двойную кавычку)
_INVALID_RE = re.compile(f"[{_INVALID_CHARS}]")
_CONTROL_RE = re.compile(r"[\x00-\x1F]")
_RESERVED = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_filename(name: str) -> str:
    """Очистить имя файла от недопустимых символов для ОС (Windows-safe).

    - Заменяет запрещённые символы на '_' (включая ")
    - Удаляет управляющие символы
    - Обрезает пробелы/точки в конце
    - Избегает зарезервированных имён (CON, PRN, AUX, NUL, COM1.., LPT1..)
    - Ограничивает длину до 255 символов
    """
    if not name:
        return ""

    # Разделим базу и расширение, чтобы корректно обрабатывать reserved base
    p = Path(name)
    base = p.stem if p.suffix else str(p)
    ext = p.suffix

    # Очистка запрещённых и управляющих символов
    base = _INVALID_RE.sub("_", base)
    base = _CONTROL_RE.sub("", base)
    base = base.strip().rstrip(". ")
    if not base:
        base = "_"

    # Reserved names
    if base.upper() in _RESERVED:
        base = base + "_"

    # Сборка обратно с расширением
    safe = base + ext
    # Удаляем недопустимые завершающие пробелы/точки, если они попали через необычное расширение
    safe = safe.strip().rstrip(". ")
    if not safe:
        safe = "_"

    # Ограничение длины
    if len(safe) > 255:
        # пытаемся сохранить расширение
        if ext and len(ext) < 20:
            keep = 255 - len(ext)
            safe = safe[:keep] + ext
        else:
            safe = safe[:255]

    return safe


def retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0) -> Callable:
    """Декоратор повторов с экспоненциальной задержкой.

    Пример:
        @retry(3, 1.0, 2.0)
        def fetch(): ...
    """
    def decorator(func: Callable) -> Callable:
        # TODO: обертка с попытками и задержками (пока не требуется)
        return func

    return decorator


def find_ffmpeg() -> Optional[Path]:
    """Попытаться найти ffmpeg.

    Порядок:
      1) ENV: YTD_FFMPEG или FFMPEG_BINARY (путь к бинарю или его папке)
      2) PATH через shutil.which
      3) Локальная папка tools/ffmpeg/**/bin/ffmpeg(.exe)
    Возвращает путь к каталогу с ffmpeg или None.
    """
    # 1) ENV vars
    env_val = os.environ.get("YTD_FFMPEG") or os.environ.get("FFMPEG_BINARY")
    if env_val:
        p = Path(env_val)
        if p.is_dir():
            # Указана директория
            return p
        if p.is_file():
            return p.parent

    # 2) PATH
    which = shutil.which("ffmpeg")
    if which:
        return Path(which).parent

    # 3) Local tools folder
    tools_root = Path("tools") / "ffmpeg"
    if tools_root.exists():
        # искать рекурсивно ffmpeg(.exe)
        names = ["ffmpeg.exe", "ffmpeg"]
        for name in names:
            for cand in tools_root.rglob(name):
                if cand.is_file():
                    return cand.parent

    return None


def find_existing_files(output_dir: Path, video_id: str) -> list[Path]:
    """Найти существующие файлы в output_dir, которые соответствуют video_id.
    
    Args:
        output_dir: Папка для поиска
        video_id: ID видео YouTube (обязательно)
    
    Returns:
        Список найденных файлов с этим video_id
    """
    if not output_dir.exists():
        return []
    
    found: list[Path] = []
    # Расширения видео и аудио файлов
    video_exts = {".mp4", ".webm", ".mkv", ".flv", ".avi"}
    audio_exts = {".m4a", ".mp3", ".opus", ".ogg", ".wav"}
    all_exts = video_exts | audio_exts
    
    # Поиск по ID видео - используем точное сравнение, а не glob с []
    # так как квадратные скобки в glob имеют специальное значение
    search_pattern = f"[{video_id}]"
    
    for ext in all_exts:
        # Сканируем все файлы с нужным расширением
        for file in output_dir.glob(f"*{ext}"):
            if file.is_file() and search_pattern in file.name:
                found.append(file)
    
    return sorted(found)


def extract_quality_suffix(format_choice: str, format_label: str) -> str:
    """Извлечь суффикс качества из выбранного формата.
    
    Args:
        format_choice: Выбранная строка формата yt-dlp
        format_label: Читаемое название выбора (например, "Видео MP4 1080p")
    
    Returns:
        Суффикс для добавления к имени файла (например, "_1080p" или "_audio")
    """
    # Попытка извлечь разрешение из label
    height_match = re.search(r'(\d{3,4})p', format_label)
    if height_match:
        return f"_{height_match.group(1)}p"
    
    # Проверка на аудио-только
    if "audio" in format_label.lower() or "bestaudio" in format_choice:
        return "_audio"
    
    # Попытка извлечь из format_choice
    height_match = re.search(r'height<=(\d{3,4})', format_choice)
    if height_match:
        return f"_{height_match.group(1)}p"
    
    # По умолчанию - лучшее качество
    return "_best"


def find_best_quality_match(
    available_heights: list[int],
    target_height: Optional[int],
    strategy: str = "econom",
) -> Optional[int]:
    """Найти наилучшее соответствие качества для видео.

    Стратегии:
      - "econom" (рекомендуется): сначала максимальное ≤ target, если нет — минимальное ≥ target
      - "rich": сначала максимальное ≥ target, если нет — максимальное ≤ target

    Args:
        available_heights: Список доступных высот (разрешений) для видео
        target_height: Целевая высота (например, 720 для 720p), None для лучшего
        strategy: "econom" | "rich"

    Returns:
        Выбранная высота или None если нет подходящих
    """
    if not available_heights:
        return None
    
    # Если цель не указана - вернуть максимальное
    if target_height is None:
        return max(available_heights)
    
    # Точное совпадение
    if target_height in available_heights:
        return target_height
    
    # Списки ниже/выше цели
    lower = [h for h in available_heights if h <= target_height]
    higher = [h for h in available_heights if h >= target_height]

    if strategy == "rich":
        # Сначала максимальное ≥ target (самое высокое из доступных выше/равно)
        if higher:
            return max(higher)
        # Иначе максимальное ≤ target
        if lower:
            return max(lower)
        return None

    # По умолчанию "econom":
    # Сначала максимальное ≤ target
    if lower:
        return max(lower)
    # Иначе минимальное ≥ target
    if higher:
        return min(higher)
    return None
