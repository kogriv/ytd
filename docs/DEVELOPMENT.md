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
- Lint: **ruff** (`uv run ruff check .`), типы: **mypy** (три платформенные модели), покрытие: **pytest-cov** (порог 66%)
- CI на GitHub Actions: матрица `ubuntu-latest` + `windows-latest` (тесты, покрытие считается на ubuntu) и отдельная джоба `lint` (ruff + mypy)
- Реализовано: одиночные видео, плейлисты, интерактив, история SQLite, cookies, anti-bot hints
- Архитектура CLI: `cli.py` → `workflows/download_command.execute_download` (подготовка `DownloadContext` + `select_scenario`) → сценарий: `single_video`, `playlist_interactive` (→ `playlist_unified` / `playlist_per_video`), `playlist_batch` или `download_one`. Общие части: `context`, `url_sources`, `info_fetch`, `playlist_resume`, `playlist_entries`, `entry_download`, `network`, `history_prompts`
- Maintenance 1.2 (открыт 2026-08-31): 8 гэпов `GAP-CR-026` … `GAP-CR-033`, задачи BL-1101 … BL-1109
- Блок 1 закрыт (2026-08-31): BL-1104 (`pytest-timeout`, `timeout = 60`), BL-1101 (TTY-fallback в `wait_if_paused`), BL-1102 (`Path`-ассерты), BL-1107 (`urls.local.txt` вне git). Полный `pytest` на Windows: **97 passed, 2 skipped** за ~33 с
- Блок 2 закрыт (2026-08-31): BL-1103 — матрица CI; прогон зелёный на обеих платформах (ubuntu 96 passed / 3 skipped, windows 97 passed / 2 skipped, lint passed)
- Блок 3 закрыт (2026-08-31): BL-1105 + BL-1106 — декомпозиция `execute_download` (112 строк вместо ~950), сценарии в отдельных модулях, `skip_post_processing` удалён. Тесты: **110 passed, 2 skipped**
- BL-1110 закрыт (2026-08-31): остановка пользователем (`typer.Exit` / `typer.Abort`) больше не гасится сценариями. Тесты: **119 passed, 2 skipped**
- **Maintenance 1.2 закрыт (2026-08-31):** все 10 задач спринта K и все 9 гэпов ревью 2026-08-31; README и `devplan*.md` синхронизированы с кодом (BL-1108, BL-1109)
- **Maintenance 1.3 открыт (2026-08-31):** [ревью техдолга](gaps/tech_debt_2026-08-31.md) — `GAP-CR-035` … `GAP-CR-040` + перенесённый `GAP-CR-009`; задачи BL-1201 … BL-1207, [дизайн](design_tech_debt_2026-08-31.md)
- Дефекты спринта L закрыты (2026-08-31): висящая запись `in_progress` (BL-1201) и гонка за клавиатурным вводом при возобновлении паузы (BL-1202). Тесты: **125 passed, 2 skipped**
- Ворота качества закрыты (2026-08-31): BL-1203 (mypy в CI, три платформенные модели) и BL-1204 (покрытие 68%, порог 66%). Тесты: **127 passed, 2 skipped**
- **Maintenance 1.3 закрыт (2026-08-31):** все 7 задач спринта L и все 7 гэпов ревью техдолга. Приняты решения: `main` защищён обязательными проверками (BL-1205), интеграционные тесты — ручной инструмент (BL-1206), JSONL опционален и выключен по умолчанию (BL-1207)
- Дальнейшие задачи: опционально GAP-CR-009 (deprecate JSONL), GAP-CR-014 (полная унификация playlist paths) — вне scope Maintenance 1.1

---

## Быстрый старт для разработчика

```bash
# Python 3.14 + uv
uv sync
uv run pytest -q
uv run ruff check .
uv run mypy                    # проверка типов для текущей ОС
uv run ytd --help
```

Дополнительные проверки:

```bash
# покрытие с указанием незакрытых строк (порог в CI — 66%)
uv run pytest -q --cov --cov-report=term-missing

# типы под всеми платформенными моделями, как в CI:
# ветки msvcrt / termios / winreg видны только под своей платформой
uv run mypy --platform win32
uv run mypy --platform linux
uv run mypy --platform darwin
```

### Рабочий поток и защита ветки

Ветка `main` защищена: обязательны зелёные проверки `test (ubuntu-latest)`, `test (windows-latest)` и `lint`, прямой push и force-push запрещены (решение BL-1205). CI перестал быть отчётом и стал барьером.

```bash
git checkout -b fix/короткое-описание
# ... правки, uv run pytest -q, uv run ruff check ., uv run mypy
git commit -m "..."
git push -u origin fix/короткое-описание
gh pr create --fill
gh pr merge --squash --delete-branch   # смержится после зелёного CI
```

Владелец репозитория (администратор) правило не обходит по умолчанию, но может временно снять его в настройках, если потребуется срочная правка.

### Интеграционные тесты

Два теста в `tests/test_integration.py` работают с живой площадкой и включаются переменной `YTD_IT_URL`. Без неё они пропускаются — именно они дают `2 skipped` в каждом обычном прогоне.

```bash
# PowerShell
$env:YTD_IT_URL = "https://www.youtube.com/watch?v=VIDEO_ID"
uv run pytest tests/test_integration.py -q

# bash
YTD_IT_URL="https://www.youtube.com/watch?v=VIDEO_ID" uv run pytest tests/test_integration.py -q
```

Проверяют `ytd info --json` и `ytd download --dry-run` — то есть получение метаданных без скачивания файлов.

**В CI они намеренно не запускаются** (решение BL-1206): результат зависит от доступности площадки и её anti-bot защиты, поэтому регулярные прогоны давали бы красные сборки из-за YouTube, а не из-за кода. Это ручной инструмент — запускайте перед релизом или когда есть подозрение, что сломался экстрактор yt-dlp.

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
