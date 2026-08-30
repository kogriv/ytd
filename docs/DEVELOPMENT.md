# Разработка, план и прогресс

Полная история разработки, план итераций, чеклисты и текущий статус проекта.

- Актуальный README с кратким описанием и примерами использования: [../README.md](../README.md)
- Бэклог и gap-ревью: [backlog.md](backlog.md), [gaps/code_review_2026-05-25.md](gaps/code_review_2026-05-25.md)
- Текущий цикл: [анализ 2026-08-31](analysis_2026-08-31.md), [гэпы 2026-08-31](gaps/code_review_2026-08-31.md), [дизайн исправлений](design_2026-08-31.md), спринт K в [backlog.md](backlog.md)
- Дата обновления: 2026-08-31

---

## Статус

- MVP: завершён (2025-10-26)
- Python **3.14**, менеджер зависимостей **uv**, виртуальное окружение `.venv`
- Тесты: **95+** unit ( `uv run pytest` ); интеграционные — при `YTD_IT_URL`
- Lint: **ruff** (`uv run ruff check .`), CI на GitHub Actions
- Реализовано: одиночные видео, плейлисты, интерактив, история SQLite, cookies, anti-bot hints
- Архитектура CLI: `ytd/workflows/` (`download_command`, `playlist_entries`, `network`, `history_prompts`)
- Maintenance 1.2 (открыт 2026-08-31): 8 гэпов `GAP-CR-026` … `GAP-CR-033`, задачи BL-1101 … BL-1109
- Известно на 2026-08-31: полный `pytest` на Windows зависает на `tests/test_pause.py::test_wait_if_paused_clears_flag_with_prompt_fallback` (BL-1101), падает `tests/test_history_import.py::test_import_from_jsonl_populates_history` (BL-1102); на Linux/CI прогон зелёный
- Дальнейшие задачи: опционально GAP-CR-009 (deprecate JSONL), GAP-CR-014 (полная унификация playlist paths) — вне scope Maintenance 1.1

---

## Быстрый старт для разработчика

```bash
# Python 3.14 + uv
uv sync
uv run pytest -q
uv run ruff check .
uv run ytd --help
```

Конфиг для локальных прогонов: скопировать `config.example.yaml` → `./ytd.config.yaml`.

Pre-commit (опционально): `uv run pre-commit install` — требует `pre-commit` в окружении или `pip install pre-commit`.

---

## План разработки (итерации)

1) Подготовка окружения — **выполнено** (Python 3.14, uv, `.venv`, CI)
2) Инициализация пакета — **выполнено**
3) Downloader + CLI — **выполнено**
4) Плейлисты, интерактив, pause — **выполнено**
5) История SQLite + JSONL — **выполнено**
6) Рефакторинг workflows (Спринты A–C) — **выполнено**
7) Качество: ruff, docs, history hardening (Спринт D) — **выполнено**

Критерии готовности: воспроизводимость (README), предсказуемые коды возврата, журналирование, тесты на ключевую логику.

---

## Паттерны и подходы

- Facade — `Downloader` скрывает детали `yt_dlp.YoutubeDL`
- Builder — сборка `ydl_opts` из `DownloadOptions` и `AppConfig`
- Workflow modules — оркестрация в `ytd/workflows/`, Typer только в `cli.py`
- Retry с экспоненциальной задержкой — устойчивость к сетевым сбоям
- Command — команды CLI (`download`, `info`, `history`) как отдельные обработчики

Подробные сигнатуры типов см. в исходниках `ytd/types.py`, `ytd/downloader.py`.
