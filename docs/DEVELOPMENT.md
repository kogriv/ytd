# Разработка, план и прогресс

Полная история разработки, план итераций, чеклисты и текущий статус проекта.

- Актуальный README с кратким описанием и примерами использования: [../README.md](../README.md)
- Дата обновления: 26.10.2025

---

## Статус

- MVP: завершён (26.10.2025)
- Реализовано: одиночные видео, плейлисты (последовательно), аудио/видео, форматы и качество, сохранение метаданных, чистые логи, файл со ссылками, коды возврата, `--playlist-items`.
- Дальнейшие задачи: расширения (параллельная загрузка, субтитры/чаптеры/миниатюры, экспорт CSV/Excel, Docker/EXE, UX-флаги).

---

## План разработки (итерации)

1) Подготовка окружения и репозитория — статус: выполнено
- [x] Python установлен: 3.13.5
- [x] ffmpeg доступен: установлен portable в `tools/ffmpeg` и добавлен в PATH для текущей сессии (позже будет использоваться `ffmpeg_location` в коде)
- [x] Создано виртуальное окружение: `venv_ytd`
- [x] Добавлены `.gitignore` и базовая структура (выполнено ранее)
- [x] Добавлен `pyproject.toml` с build-system (hatchling) и console script `ytd`
- [x] Установлены зависимости; проверен запуск: `ytd --help`

2) Инициализация пакета — статус: выполнено
- [x] Добавлен `pyproject.toml` с зависимостями (`yt-dlp`, `typer`, `rich`, `pyyaml`) и console script `ytd`
- [x] Создан `ytd/__init__.py`

3) Разработка — статус: выполнено
- Реализованы Downloader, CLI, Конфиг, Логи/устойчивость

5) CLI (Typer) — статус: выполнено
- [x] Команды: `download`, `info` с полной интеграцией (Downloader, конфиг, логирование)
- [x] Локализация help на русском, удобные опции (--output, --audio-only, --quality, --dry-run, --verbose, и т.д.)
- [x] Коды возврата: 0 — успех; 1 — ошибка; 2 — частичный успех

6) Метаданные и шаблоны имён — статус: выполнено
- [x] JSONL метаданные; sanitize имён; интеграция в Downloader

6.1) Интеграционное тестирование — статус: завершено
- [x] Опциональные интеграционные тесты с реальным yt-dlp при `YTD_IT_URL`
- [x] Фактическая загрузка: проверена; dry-run и info работают
- [x] Улучшения логирования и два режима вывода (краткий/подробный)

7) Плейлисты и массовая загрузка — статус: выполнено (26.10.2025)
- [x] Последовательная обработка
- [x] Информация о плейлисте перед скачиванием (название, количество)
- [x] Сохранение метаданных по каждому элементу
- [x] Коды возврата учитывают частичные ошибки
- [x] Флаги CLI: `--playlist`, `--playlist-items`

8) Дополнительно (после MVP)
- [ ] Субтитры/чаптеры/миниатюры
- [ ] Параллелизм (ограничение конкуренции), очередь задач
- [ ] Экспорт отчётов (CSV/Excel), Docker/EXE-сборка

Критерии готовности каждого шага: воспроизводимость (README), предсказуемые ошибки/коды возврата, журналирование, тест(ы) на ключевую логику.

---

## Паттерны и подходы

- Facade/Wrapper — `Downloader` скрывает детали `yt_dlp.YoutubeDL`
- Builder — пошаговая сборка `ydl_opts` из `DownloadOptions` и `AppConfig`
- Strategy — выбор формата/качества/шаблона имени (переключаемые пресеты)
- Adapter — мост между хуком прогресса yt-dlp и нашим логированием/статусом
- Dependency Injection — передача `config` и `logger` в компоненты
- Retry с экспоненциальной задержкой — устойчивость к сетевым сбоям
- Command — команды CLI (`download`, `info`) как отдельные обработчики
- Value Object — `DownloadOptions`/`AppConfig` как неизменяемые носители параметров

---

## Контракты и сигнатуры (заготовки)

Типы (`ytd/types.py`):

```python
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Literal

@dataclass(slots=True)
class DownloadOptions:
  url: str
  output_dir: Path = Path("downloads")
  audio_only: bool = False
  audio_format: Literal["m4a", "mp3", "opus"] = "m4a"
  video_format: Literal["mp4", "webm"] = "mp4"
  quality: Literal["best", "1080p", "720p", "audio"] = "best"
  name_template: str = "%(title)s [%(id)s].%(ext)s"
  subtitles: list[str] = field(default_factory=list)
  proxy: Optional[str] = None
  retry: int = 3
  retry_delay: float = 5.0
  save_metadata: Optional[Path] = Path("data/meta.jsonl")
  dry_run: bool = False
  playlist: bool = False

@dataclass(slots=True)
class AppConfig:
  output: Path = Path("downloads")
  quality: str = "best"
  video_format: str = "mp4"
  audio_only: bool = False
  audio_format: str = "m4a"
  name_template: str = "%(title)s [%(id)s].%(ext)s"
  subtitles: list[str] = field(default_factory=list)
  proxy: Optional[str] = None
  retry: int = 3
  retry_delay: float = 5.0
  save_metadata: Optional[Path] = Path("data/meta.jsonl")
```

Конфигурация (`ytd/config.py`):

```python
from pathlib import Path
from typing import Optional
from .types import AppConfig

def load_config(config_path: Optional[Path] = None) -> AppConfig:
  """Загрузить конфиг из файла/ENV, вернуть AppConfig с дефолтами."""
  ...

def merge_cli_overrides(cfg: AppConfig, overrides: dict) -> AppConfig:
  """Наложить значения из CLI, вернуть новый объект конфигурации."""
  ...
```

Логирование (`ytd/logging.py`):

```python
from pathlib import Path
from typing import Optional
import logging

def setup_logging(level: str = "INFO", log_file: Optional[Path] = Path("logs/ytd.log")) -> logging.Logger:
  """Настроить логгер приложения (консоль + файл)."""
  ...
```

Утилиты (`ytd/utils.py`):

```python
from pathlib import Path
from typing import Any, Mapping, Callable

def ensure_dir(path: Path) -> None:
  ...

def save_metadata_jsonl(meta: Mapping[str, Any], path: Path) -> None:
  ...

def sanitize_filename(name: str) -> str:
  ...

def retry(retries: int = 3, delay: float = 1.0, backoff: float = 2.0) -> Callable:
  """Декоратор повтора вызова с экспоненциальной задержкой."""
  ...
```

Загрузчик (`ytd/downloader.py`):

```python
from pathlib import Path
from typing import Any, Optional
import logging
from .types import AppConfig, DownloadOptions

class Downloader:
  def __init__(self, config: AppConfig, logger: Optional[logging.Logger] = None) -> None:
    ...

  def build_ydl_opts(self, opts: DownloadOptions) -> dict[str, Any]:
    ...

  def get_info(self, url: str) -> dict[str, Any]:
    ...

  def download(self, opts: DownloadOptions) -> list[Path]:
    ...
```

CLI (`ytd/cli.py`, Typer):

```python
import typer
from pathlib import Path
from typing import Optional

app = typer.Typer(no_args_is_help=True)

@app.command("download")
def download(
  url: str,
  output: Path = typer.Option(Path("downloads"), help="Папка назначения"),
  audio_only: bool = typer.Option(False, help="Скачать только аудио"),
  audio_format: str = typer.Option("m4a", help="Формат аудио"),
  video_format: str = typer.Option("mp4", help="Контейнер видео"),
  quality: str = typer.Option("best", help="Качество/пресет"),
  name: str = typer.Option("%(title)s [%(id)s].%(ext)s", help="Шаблон имени файла"),
  subtitles: list[str] = typer.Option([], help="Языки субтитров"),
  proxy: Optional[str] = typer.Option(None, help="Прокси URL"),
  dry_run: bool = typer.Option(False, help="Только показать действия"),
):
  ...

@app.command("info")
def info(url: str) -> None:
  ...

def main():
  app()
```
