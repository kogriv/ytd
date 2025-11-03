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

- **Одна команда для одиночных видео и плейлистов** — autodetect разбирает тип ссылки сам:
  - `ytd download https://vk.com/video-12345_67890`
  - Работает для YouTube, VK и других площадок, которые поддерживает yt-dlp
- **Загрузка списка ссылок из файла** (одна строка — один URL, `#` — комментарии):
  - `ytd download --urls-file urls.local.txt`
- **Интерактивный выбор качества** (если не включён по умолчанию):
  - `ytd download URL --interactive`
  - Чтобы не передавать флаг каждый раз, добавьте `interactive_by_default: true` в конфиг `config.yaml`
- **Только аудио m4a с пользовательским шаблоном имени**:
  - `ytd download URL --audio-only --audio-format m4a -o ./downloads --name "%(title)s [%(id)s]"`
- **Часть плейлиста или заданная нумерация**:
  - `ytd download PLAYLIST_URL --playlist-items 1-3`
- **Пауза между элементами плейлиста** (также настраивается в конфиге `pause_between_videos: true`):
  - `ytd download PLAYLIST_URL --pause-between`
  - Нажмите `p` во время загрузки для паузы, `r` (или Enter) — для продолжения
- **Сухой прогон без скачивания**:
  - `ytd download URL --interactive --dry-run`
- **Показать информацию о видео или плейлисте**:
  - `ytd info URL`

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

