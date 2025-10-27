# ytd — простая CLI-утилита для загрузки видео с YouTube

Простой, надёжный загрузчик YouTube-видео и аудио на Python с русским CLI. Основан на готовых, проверенных библиотеках; без «велосипедов» и сложной настройки.

- Библиотека для загрузки: [yt-dlp](https://github.com/yt-dlp/yt-dlp) (Python API) — максимально устойчив к изменениям YouTube
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
- Интерактивная загрузка с предпросмотром (dry-run):
  - `ytd download URL --interactive --dry-run`
  - `ytd download PLAYLIST_URL --playlist --interactive --dry-run`
