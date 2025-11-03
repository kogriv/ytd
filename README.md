# ytd — простая CLI-утилита для загрузки видео с YouTube, VK и других площадок

Простой, надёжный загрузчик видео и аудио на Python с русским CLI. ytd использует [yt-dlp](https://github.com/yt-dlp/yt-dlp), поэтому поддерживает сотни источников — от YouTube и VK до Twitch, SoundCloud и других сервисов, которые знает yt-dlp. Без «велосипедов» и сложной настройки.

- Библиотека для загрузки: [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Python API) — максимально устойчив к изменениям сайтов и поддерживает множество площадок
- Пакетный режим и понятные опции
- Логи, сохранение метаданных, шаблоны имён файлов

---

## Стек технологий

- Python 3.11+
- yt-dlp (скачивание видео/аудио)
- Typer (CLI), rich (отформатированный вывод)
- PyYAML (конфигурация)
- ffmpeg (mux/конвертация, вызывается yt-dlp при необходимости)

---

## Структура проекта

```
.
├─ README.md
├─ .gitignore
├─ ytd/
│  ├─ cli.py
│  ├─ downloader.py
│  ├─ config.py
│  ├─ logging.py
│  ├─ utils.py
│  └─ types.py
├─ tests/
├─ data/
│  └─ .gitkeep
├─ downloads/
│  └─ .gitkeep
├─ logs/
│  └─ .gitkeep
└─ docs/
```

---

## Быстрый старт (примеры использования)

- Одно видео лучшего качества (по умолчанию):
  - `ytd download https://www.youtube.com/watch?v=...`
- Только аудио m4a в указанную папку с шаблоном имени:
  - `ytd download URL --audio-only --audio-format m4a -o ./downloads --name "%(title)s [%(id)s]"`
- Плейлист целиком:
  - `ytd download PLAYLIST_URL --playlist`
- Только первые три видео из плейлиста:
  - `ytd download PLAYLIST_URL --playlist --playlist-items 1-3`
- Плейлист из файла со ссылками (по одной в строке, строки с `#` игнорируются):
  - `ytd download --urls-file urls.local.txt --playlist`
- Показать информацию о видео/плейлисте:
  - `ytd info URL`
- Интерактивный выбор качества для одиночного видео:
  - `ytd download URL --interactive`
  - Программа предложит выбрать качество, добавить суффикс (например, `_720p`), префикс (например, `01_`), проверит существующие файлы и предложит перезаписать
- Интерактивная загрузка плейлиста с единой конфигурацией:
  - `ytd download PLAYLIST_URL --playlist --interactive`
  - Программа предложит выбрать режим (единые настройки или для каждого видео), качество, нумерацию (01_, 02_, ...), стратегию подбора качества
  - Результат: `01_Видео [ID]_720p.mp4`, `02_Видео [ID]_720p.mp4`, ...
- **Интерактивная загрузка плейлиста из файла с паузами** (рекомендуемая команда):
  - `ytd download --urls-file .\urls.local.txt --playlist --interactive --pause-between`
  - Или короткая версия: `ytd download --urls-file .\urls.local.txt --playlist -i --pause-between`
  - Выбор качества, нумерация, возможность поставить на паузу между видео (нажать `p`, возобновить `r`)
- Интерактивная загрузка с предпросмотром (dry-run):
  - `ytd download URL --interactive --dry-run`
  - `ytd download PLAYLIST_URL --playlist --interactive --dry-run`
- **Пауза между видео в плейлистах** (NEW):
  - `ytd download PLAYLIST_URL --playlist --pause-between`
  - Во время загрузки нажмите `p` для запроса паузы после текущего видео
  - После завершения загрузки нажмите `r` (или Enter) для возобновления
  - Работает как в обычном, так и в интерактивном режиме плейлиста
  - **Примечание**: требуется Windows (использует `msvcrt`); для Linux/macOS будет fallback на ввод Enter

## Журнал загрузок

- История сохраняется в SQLite-базу (`history_db`) и доступна через команды CLI:
  - `ytd history` — список последних загрузок с фильтрами по статусу, дате и плейлисту
  - `ytd history show <ID>` — карточка отдельной записи
  - `ytd history export --format jsonl|csv` — экспорт истории в stdout
- При первом создании базы, если файл метаданных (`save_metadata`, JSONL) уже существует, ytd импортирует прежние записи автоматически.
- Управление включением журнала и путями осуществляется в конфиге (`config.yaml`):
  - `history_enabled`: включить/отключить журнал полностью
  - `history_db`: путь к SQLite-файлу
  - `save_metadata`: путь к JSONL для хранения метаданных (используется и для начального импорта)
- Те же настройки можно задать через переменные окружения: `YTD_HISTORY_ENABLED`, `YTD_HISTORY_DB`, `YTD_SAVE_METADATA`.
- Подробнее — в [docs/usage.md](docs/usage.md).

