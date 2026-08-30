# Бэклог исправлений ytd

Status: Maintenance 1.1 — complete (BL-1xx … BL-10xx done); Maintenance 1.2 — открыт (BL-11xx todo)  
Owner: @Ivan  
Created: 2026-05-25  
Last updated: 2026-08-31 (Maintenance 1.2 — добавлен спринт K по ревью 2026-08-31)

---

## Спринт A — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-101 | `ytd/console.py`, разрыв циклических import | done |
| BL-201 | Tri-state `--interactive` + конфиг `interactive_by_default` | done |
| BL-301 | Pause listener на Linux/macOS (termios + select) | done |
| BL-601 | Regression test doublesave плейлиста | done |
| BL-604 | Базовые тесты PauseController | done (частично) |

---

## Спринт B — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-401 | Один `extract_info` на загрузку | done |
| BL-501 | Cookies: `--cookies`, `--cookies-from-browser`, конфиг, ENV | done |
| BL-502 | Подсказки при anti-bot ошибках | done |
| BL-503 | Валидация proxy URL | done |

Тесты: **58 passed**, 2 skipped. Новые модули/тесты: `ytd/errors.py`, `tests/test_errors.py`; расширены `test_downloader.py`, `test_config.py`.

---

## Спринт C — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-102 | `run_single_video_interactive_setup()` + `SingleVideoSetupResult` | done |
| BL-103 | `workflows/playlist_entries.py`, `entry_download.py` | done |
| BL-104 | `workflows/download_command.py`, `cli.py` ~400 строк | done |

Новые модули: `ytd/workflows/` (`network.py`, `history_prompts.py`, `entry_download.py`, `playlist_entries.py`, `download_command.py`). Тесты: **60 passed**, 2 skipped; добавлен `tests/test_interactive_setup.py`.

---

## Спринт D — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-105 | `sys.exit` → `raise typer.Exit` в download/info | done |
| BL-701 | SQLite WAL + `busy_timeout=5000` | done |
| BL-702 | Двухэтапный lookup в `fetch_download` / `update_download` | done |
| BL-703 | JSONL vs SQLite в `docs/usage.md` | done |
| BL-801 | Обновлён `DEVELOPMENT.md` | done |
| BL-802 | Синхронизированы `README.md`, `usage.md` | done |
| BL-901 | ruff в dev-группе + CI job | done |
| BL-902 | `.pre-commit-config.yaml` (ruff) | done |
| BL-903 | WARNING вместо debug для ошибок history/metadata | done |

Тесты: **62 passed**, 2 skipped; добавлен `tests/test_history_fetch.py`.

---

## Спринт E — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-106 | TypeAlias + валидация quality/format/browser в config | done |
| BL-1002 | `browser_detect.py`, подсказка anti-bot с локальным браузером | done |
| BL-602 | Тесты `_parse_selection_mask` | done |
| BL-603 | Тесты `normalize_history_id` (+ fetch из BL-702) | done |
| BL-203 | Реализован декоратор `retry` | done |
| BL-204 | `logs/*.log` в `.gitignore` | done |

Тесты: **83 passed**, 2 skipped.

---

## Спринт F — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-202 | Playlist mode 2 — per-video interactive setup | done |

Тесты: **84 passed**, 2 skipped; `test_interactive_playlist_per_video_mode_downloads_each_entry`.

---

## Спринт G — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-704 | `HistoryStore` class + DI в `Downloader` | done |

Тесты: **86 passed**, 2 skipped; `tests/test_history_store.py`.

---

## Спринт H — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-402 | file_path по video_id, не по индексу | done |
| BL-403 | Incremental history на progress hook `finished` | done |

Тесты: **88 passed**, 2 skipped; `tests/test_downloader_history.py`.

---

## Спринт I — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-302 | Windows progress flush OSError (`no_progress`, auto-retry) | done |

Тесты: **91 passed**, 2 skipped.

---

## Спринт J — выполнено (2026-05-25)

| ID | Задача | Status |
|----|--------|--------|
| BL-1001 | Intra-video pause (`--intra-video-pause`, progress hook + continuedl) | done |

Тесты: **95 passed**, 2 skipped; `tests/test_intra_video_pause.py`.

---

## Спринт K — Maintenance 1.2 (открыт, 2026-08-31)

Источник: [ревью 2026-08-31](./gaps/code_review_2026-08-31.md), дизайн решений — [design_2026-08-31.md](./design_2026-08-31.md).

| ID | Задача | Gap | Priority | Status | Est |
|----|--------|-----|----------|--------|-----|
| BL-1101 | TTY-fallback в `wait_if_paused` до платформенной развилки | GAP-CR-026 | P0 | **done** | S |
| BL-1102 | Платформенно-независимые ассерты путей в тестах истории | GAP-CR-027 | P1 | **done** | S |
| BL-1103 | Матрица CI `ubuntu-latest` + `windows-latest` | GAP-CR-028 | P1 | **done** | S |
| BL-1104 | `pytest-timeout` и глобальный лимит на тест | GAP-CR-028 | P1 | **done** | S |
| BL-1105 | Декомпозиция `execute_download` на сценарии + `DownloadContext` | GAP-CR-029 | P2 | todo | L |
| BL-1106 | Удалить мёртвую ветку повторного опроса истории | GAP-CR-030 | P2 | todo | S |
| BL-1107 | Снять `urls.local.txt` с отслеживания, добавить `urls.example.txt` | GAP-CR-031 | P1 | **done** | S |
| BL-1108 | Привести раздел «Структура проекта» в README к факту | GAP-CR-032 | P3 | todo | S |
| BL-1109 | Актуализировать `devplan.md` / `devplan_ru.md` | GAP-CR-033 | P3 | todo | M |

Подробные задачи — в [Группе 11](#группа-11--maintenance-12-ревью-2026-08-31). Рекомендованный порядок и зависимости — в разделе «Порядок внедрения» дизайн-дока.

Состояние на момент открытия спринта (Windows 11, Python 3.14): `ruff check .` — чисто; полный `pytest` **не завершается** (зависает на `tests/test_pause.py::test_wait_if_paused_clears_flag_with_prompt_fallback`); с `--deselect` этого теста — **93 passed, 1 failed, 2 skipped**.

Состояние после блока 1 (BL-1104 → BL-1101 → BL-1102, 2026-08-31): полный `pytest` на Windows завершается без `--deselect` — **97 passed, 2 skipped** за 32.7 с; `ruff check .` чисто.

Состояние после блока 2 (BL-1103, 2026-08-31): CI зелёный на обеих платформах — `test (ubuntu-latest)` 96 passed / 3 skipped, `test (windows-latest)` 97 passed / 2 skipped, `lint` passed. Осталось в спринте: BL-1105, BL-1106, BL-1108, BL-1109.

---

## Назначение документа

Этот бэклог содержит **сгруппированные задачи** на исправление гэпов, выявленных в [архитектурном и кодовом ревью](./gaps/code_review_2026-05-25.md) от 2026-05-25, а также связанных пунктов из существующих gap-документов.

Задачи **не выстроены в одно сплошное полотно**: они сгруппированы по темам (архитектура, UX, платформа, downloader, история, безопасность, тесты, документация, tooling). Внутри группы задачи упорядочены по приоритету.

---

## Как читать задачи

### Поля задачи

| Поле | Значение |
|------|----------|
| **ID** | Уникальный идентификатор задачи бэклога (`BL-xxx`) |
| **Gap** | Ссылка на гэп из ревью (`GAP-CR-xxx`) или legacy gap-документ |
| **Priority** | P0 — срочно / блокер UX или регрессии; P1 — важно для поддерживаемости; P2 — улучшения; P3 — отложено |
| **Status** | `todo` / `in_progress` / `done` / `cancelled` |
| **Estimate** | Ориентировочная сложность: S (< 2ч), M (2–8ч), L (1–3 дня), XL (> 3 дней) |

### Рекомендуемый порядок спринтов

1. **Спринт A (стабилизация):** группы 2, 3, 6 — быстрые исправления UX и regression tests.  
2. **Спринт B (эксплуатация):** группа 5 — cookies / anti-bot.  
3. **Спринт C (структура):** группы 1, 4 — рефакторинг CLI и downloader.  
4. **Спринт D (качество):** группы 7, 8, 9 — docs, lint, history hardening.

---

## Сводная таблица по группам

| Группа | Название | Задач | P0 | P1 | P2 | P3 |
|--------|----------|-------|----|----|----|-----|
| 1 | Архитектура и рефакторинг CLI | 6 | 0 | 4 | 2 | 0 |
| 2 | UX и логика CLI | 4 | 1 | 2 | 1 | 0 |
| 3 | Кроссплатформенность | 2 | 1 | 0 | 1 | 0 |
| 4 | Downloader и производительность | 3 | 0 | 1 | 2 | 0 |
| 5 | Безопасность и anti-bot | 3 | 0 | 2 | 1 | 0 |
| 6 | Тестирование | 4 | 1 | 2 | 1 | 0 |
| 7 | История и данные | 3 | 0 | 0 | 3 | 0 |
| 8 | Документация | 2 | 0 | 1 | 1 | 0 |
| 9 | Tooling и качество кода | 3 | 0 | 0 | 3 | 0 |
| 10 | Отложенные фичи (legacy gaps) | 2 | 0 | 0 | 1 | 1 |
| 11 | Maintenance 1.2 (ревью 2026-08-31) | 9 | 1 | 4 | 2 | 2 |

---

## Группа 1 — Архитектура и рефакторинг CLI

Цель: уменьшить монолит `cli.py`, устранить циклические зависимости, подготовить кодовую базу к новым фичам без регрессий.

### BL-101 — Вынести console helpers в отдельный модуль

- **Gap:** [GAP-CR-002](./gaps/code_review_2026-05-25.md#gap-cr-002--циклические-зависимости-import)
- **Priority:** P1 | **Status:** done | **Estimate:** S

**Шаги.**
1. Создать `ytd/console.py` с перенесёнными функциями.
2. Обновить import в `cli.py`, `interactive.py`, `pause.py`.
3. Убедиться, что `interactive` и `pause` не import `cli`.

**Критерии приёмки.**
- Нет циклических import между `cli`, `interactive`, `pause`.
- Все существующие тесты проходят.

---

### BL-102 — Дедупликация интерактивного setup одиночного видео

- **Gap:** [GAP-CR-003](./gaps/code_review_2026-05-25.md#gap-cr-003--дублирование-интерактивного-flow-одиночного-видео), [GAP-CR-011](./gaps/code_review_2026-05-25.md#gap-cr-011--configure_filename_prefix-не-используется-в-основном-flow)
- **Priority:** P1 | **Status:** done | **Estimate:** M

**Описание.** Объединить два идентичных блока «ШАГ 1–3» в одну функцию в `interactive.py`; задействовать `configure_filename_prefix`.

**Шаги.**
1. Определить dataclass `SingleVideoSetupResult`.
2. Реализовать `run_single_video_interactive_setup(info, output_dir, …)`.
3. Заменить оба дублированных блока в `cli.py`.
4. Unit-тест с mock `typer.prompt`.

**Критерии приёмки.**
- В `cli.py` один вызов helper вместо двух копий ~130 строк.
- Тест покрывает выбор качества и overwrite.

---

### BL-103 — Единый orchestrator загрузки элементов плейлиста

- **Gap:** [GAP-CR-014](./gaps/code_review_2026-05-25.md#gap-cr-014--три-параллельных-orchestratorа-плейлиста)
- **Priority:** P1 | **Status:** done | **Estimate:** L

**Описание.** Вынести общую логику цикла по entries (retry, network recovery, history decision, pause, подсчёт failed) в одну функцию или класс.

**Шаги.**
1. Создать `ytd/workflows/playlist_entries.py`.
2. Функция `download_entries(entries, build_opts_for_entry, …)`.
3. Подключить из interactive unified path и pause non-interactive path.
4. Сохранить поведение `skip_post_processing`.

**Критерии приёмки.**
- Логика retry/network/history не дублируется в трёх местах.
- Regression test BL-601 проходит.

---

### BL-104 — Разбить `cli.py` на workflow-модули

- **Gap:** [GAP-CR-001](./gaps/code_review_2026-05-25.md#gap-cr-001--god-object-в-clipy)
- **Priority:** P1 | **Status:** done | **Estimate:** XL

**Описание.** После BL-102 и BL-103 завершить декомпозицию: `cli.py` только Typer commands + тонкие wrappers.

**Шаги.**
1. `ytd/workflows/download.py` — главный entry для `cmd_download`.
2. `ytd/history/prompts.py` — `prompt_history_decision`, `_print_history_card`.
3. `ytd/workflows/network.py` — `_prompt_network_recovery`.
4. Целевой размер `cli.py` ≤ 400 строк.

**Критерии приёмки.**
- `cli.py` не вызывает `Downloader.download` напрямую.
- Все тесты + regression tests зелёные.

---

### BL-105 — Унифицировать выход через `typer.Exit`

- **Gap:** [GAP-CR-015](./gaps/code_review_2026-05-25.md#gap-cr-015--смешение-sysexit-и-raise-typerexit)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Описание.** Заменить `sys.exit(n)` на `raise typer.Exit(code=n)` в `cmd_download` и `cmd_info`.

**Критерии приёмки.** CliRunner tests проходят; нет прямых `sys.exit` в command handlers.

---

### BL-106 — Выровнять типы AppConfig и DownloadOptions

- **Gap:** [GAP-CR-016](./gaps/code_review_2026-05-25.md#gap-cr-016--расхождение-типов-appconfig-и-downloadoptions)
- **Priority:** P2 | **Status:** done | **Estimate:** M

**Описание.** Общие TypeAlias для quality/audio_format/video_format; валидация в `load_config`.

**Критерии приёмки.** Убраны `# type: ignore[arg-type]` при сборке `DownloadOptions` в cli.

---

## Группа 2 — UX и логика CLI

Цель: согласовать поведение с документацией и ожиданиями пользователя.

### BL-201 — Исправить default `--interactive` и конфиг `interactive_by_default`

- **Gap:** [GAP-CR-013](./gaps/code_review_2026-05-25.md#gap-cr-013--противоречие-default---interactive-и-interactive_by_default)
- **Priority:** P0 | **Status:** done | **Estimate:** S

**Описание.** CLI default должен позволять конфигу управлять интерактивом.

**Шаги.**
1. Изменить Typer option: default `False` или `Optional` tri-state.
2. После `load_config`: применить `interactive_by_default`.
3. `--interactive` / `--no-interactive` override поверх конфига.
4. Обновить `tests/test_cli.py`.
5. Сверить README и `config.example.yaml`.

**Критерии приёмки.**
- `interactive_by_default: false` + без флагов → загрузка без диалогов.
- `interactive_by_default: true` + без флагов → диалоги качества.
- `--no-interactive` всегда отключает.

---

### BL-202 — Реализовать или скрыть playlist mode 2

- **Gap:** [GAP-CR-010](./gaps/code_review_2026-05-25.md#gap-cr-010--режим-2-настроить-каждое-видео-отдельно-не-реализован)
- **Priority:** P1 | **Status:** done | **Estimate:** L

**Описание.** Пользователь может выбрать «настроить каждое видео отдельно», но код не реализован.

**Варианты.**
- **A (реализовать):** цикл по entries с `run_single_video_interactive_setup` + download.
- **B (временно):** убрать пункт 2 из меню; оставить TODO в devplan.

**Реализовано (вариант A):** mode 2 в `download_command.py` — `run_single_video_interactive_setup` для каждого entry через `process_playlist_entries`; regression test BL-202.

**Критерии приёмки (вариант A).** Mode 2 проходит полный flow для плейлиста из N элементов.

---

### BL-203 — Удалить или реализовать заглушку `retry` decorator

- **Gap:** [GAP-CR-006](./gaps/code_review_2026-05-25.md#gap-cr-006--заглушка-декоратора-retry-в-utils)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Описание.** Убрать misleading API в `utils.retry` или реализовать и применить в Downloader.

---

### BL-204 — Исключить `logs/*.log` из git

- **Gap:** [GAP-CR-017](./gaps/code_review_2026-05-25.md#gap-cr-017--лог-файл-может-попадать-в-git)
- **Priority:** P2 | **Status:** done | **Estimate:** S

---

## Группа 3 — Кроссплатформенность

Цель: одинаковые или честно документированные возможности на Linux, macOS, Windows.

### BL-301 — Пауза между видео на Linux и macOS

- **Gap:** [GAP-CR-012](./gaps/code_review_2026-05-25.md#gap-cr-012--пауза-между-видео-не-работает-на-linux-через-клавишу-p)
- **Priority:** P0 | **Status:** done | **Estimate:** M

**Описание.** Реализовать keyboard listener на Unix или явное предупреждение при старте.

**Шаги (рекомендуемый путь A).**
1. Модуль `ytd/pause_listener.py` с backend `msvcrt` / `termios`.
2. Unit-тests с mock stdin/termios.
3. Обновить README: платформенные ограничения, если fallback частичный.

**Критерии приёмки.** На Linux в интерактивном терминале `p` во время загрузки приводит к паузе после текущего видео.

---

### BL-302 — Windows progress flush OSError

- **Gap:** [GAP-CR-022](./gaps/code_review_2026-05-25.md#gap-cr-022--oserror-errno-22-на-windows-при-flush-progress), [doublesave_antibot_issue.md](./gaps/doublesave_antibot_issue.md)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Описание.** `no_progress` в конфиге; auto-retry без progress bar на Windows при OSError 22; OSError в progress hook.

---

## Группа 4 — Downloader и производительность

Цель: меньше запросов к API, корректнее история при batch-загрузках.

### BL-401 — Убрать двойной `extract_info` в `Downloader.download`

- **Gap:** [GAP-CR-004](./gaps/code_review_2026-05-25.md#gap-cr-004--двойной-вызов-extract_info-при-каждой-загрузке)
- **Priority:** P1 | **Status:** done | **Estimate:** M

**Шаги.**
1. Проанализировать API yt-dlp 2026.3.x для reuse info dict.
2. Объединить preview + download в один вызов где возможно.
3. Тест: mock считает вызовы `extract_info` — ожидание 1.

**Критерии приёмки.** Одна загрузка одного URL — один extract (не counting interactive pre-analysis).

---

### BL-402 — Корректное сопоставление file_paths в history для плейлистов

- **Gap:** [GAP-CR-005](./gaps/code_review_2026-05-25.md#gap-cr-005--неточное-сопоставление-file_paths-при-загрузке-плейлиста)
- **Priority:** P2 | **Status:** done | **Estimate:** M

**Описание.** Привязка `file_path` к `video_id`, не к индексу в списке.

---

### BL-403 — Запись истории по progress hook для batch playlist

- **Gap:** дополнение к GAP-CR-005  
- **Priority:** P3 | **Status:** done | **Estimate:** M

**Описание.** `record_event` на каждый `finished` hook; batch success пропускается при incremental history.

---

## Группа 5 — Безопасность и anti-bot

Цель: снизить частоту падений на YouTube и аналогичных площадках.

### BL-501 — Проброс cookies в yt-dlp

- **Gap:** [GAP-CR-021](./gaps/code_review_2026-05-25.md#gap-cr-021--нет-поддержки-cookies-для-обхода-anti-bot-youtube), [doublesave_antibot_issue.md](./gaps/doublesave_antibot_issue.md)
- **Priority:** P1 | **Status:** done | **Estimate:** M

**Шаги.**
1. `AppConfig`: `cookies_file`, `cookies_from_browser`.
2. `DownloadOptions` + `build_ydl_opts`: `cookiefile`, `cookiesfrombrowser`.
3. CLI: `--cookies PATH`, `--cookies-from-browser BROWSER`.
4. ENV: `YTD_COOKIES`, `YTD_COOKIES_FROM_BROWSER`.
5. `config.example.yaml` + README troubleshooting.

**Критерии приёмки.** `ytd download URL --cookies-from-browser firefox` передаёт опцию в yt-dlp.

---

### BL-502 — Подсказка при anti-bot ошибке

- **Gap:** GAP-CR-021  
- **Priority:** P1 | **Status:** done | **Estimate:** S

**Описание.** При сообщении «not a bot» / «Sign in» в exception — вывести hint про cookies и ссылку на docs.

**Зависимости.** BL-501 (желательно).

---

### BL-503 — Валидация proxy URL

- **Gap:** ревью, раздел безопасность  
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Описание.** Базовая проверка схемы `http(s)://` при load_config и CLI override.

---

## Группа 6 — Тестирование

Цель: защита от регрессий, покрытие критичных workflows.

### BL-601 — Regression test: нет второй загрузки плейлиста после interactive unified

- **Gap:** [GAP-CR-018](./gaps/code_review_2026-05-25.md#gap-cr-018--нет-regression-теста-на-двойную-загрузку-плейлиста), [doublesave_antibot_issue.md](./gaps/doublesave_antibot_issue.md)
- **Priority:** P0 | **Status:** done | **Estimate:** M

**Шаги.**
1. Mock `Downloader.download` / FakeYDL с playlist entries.
2. Симулировать interactive unified path (monkeypatch interactive helpers на defaults).
3. Assert: ровно N вызовов download, нет вызова с `playlist=True` на parent URL после цикла.

**Критерии приёмки.** Тест падает без `skip_post_processing`.

---

### BL-602 — Тесты `_parse_selection_mask` и playlist resume

- **Gap:** [GAP-CR-019](./gaps/code_review_2026-05-25.md#gap-cr-019--нет-тестов-interactive-pause-playlist-workflows)
- **Priority:** P1 | **Status:** done | **Estimate:** S

**Реализовано:** `tests/test_interactive_selection.py` — диапазоны, `all`/`все`, invalid input.

---

### BL-603 — Тесты `normalize_history_id` и `fetch_download`

- **Gap:** GAP-CR-008, GAP-CR-019  
- **Priority:** P1 | **Status:** done | **Estimate:** S

**Покрыть:** YouTube URL → `yt:ID`, normalized URL, OR lookup fix после BL-702.

**Реализовано:** `tests/test_browser_detect.py`, `tests/test_history_fetch.py`.

---

### BL-604 — Тесты pause controller

- **Gap:** GAP-CR-012, GAP-CR-019  
- **Priority:** P2 | **Status:** done (базовое покрытие) | **Estimate:** M

**Зависимости.** BL-301 (done).

**Реализовано:** `tests/test_pause.py` — listener key, tty fallback, enable/disable.

---

## Группа 7 — История и данные

Цель: надёжнее storage, яснее модель данных.

### BL-701 — SQLite WAL и busy_timeout

- **Gap:** [GAP-CR-023](./gaps/code_review_2026-05-25.md#gap-cr-023--sqlite-без-wal-и-busy_timeout)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Шаги.** В `init_db` или `get_connection`: PRAGMA journal_mode=WAL; busy_timeout=5000.

---

### BL-702 — Двухэтапный lookup в `fetch_download`

- **Gap:** [GAP-CR-008](./gaps/code_review_2026-05-25.md#gap-cr-008--fetch_download-с-or-может-вернуть-неверную-запись)
- **Priority:** P2 | **Status:** done | **Estimate:** S

---

### BL-703 — Документировать роли JSONL vs SQLite

- **Gap:** [GAP-CR-009](./gaps/code_review_2026-05-25.md#gap-cr-009--дублирование-источников-правды-jsonl--sqlite)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Шаги.** Раздел в `docs/usage.md` или manual: когда что используется, migration path.

---

### BL-704 — HistoryStore class (DI вместо global)

- **Gap:** [GAP-CR-007](./gaps/code_review_2026-05-25.md#gap-cr-007--глобальное-состояние-_db_path)
- **Priority:** P3 | **Status:** done | **Estimate:** L

**Описание.** Класс `HistoryStore(path)`; `Downloader(..., history_store=...)`; module-level API через default store (`init_db` / `get_default_store`).

---

## Группа 8 — Документация

Цель: синхронизация docs с кодом и Python 3.14.

### BL-801 — Обновить DEVELOPMENT.md и devplan

- **Gap:** [GAP-CR-020](./gaps/code_review_2026-05-25.md#gap-cr-020--устаревшие-dev-документы)
- **Priority:** P1 | **Status:** done | **Estimate:** S

**Обновить:**
- Python 3.14, uv, `.venv`
- 38+ tests
- ссылка на gap review и backlog

---

### BL-802 — Синхронизировать usage.md и README

- **Gap:** GAP-CR-020  
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Исправить:** `config.yaml` → `ytd.config.yaml`; interactive defaults после BL-201.

---

## Группа 9 — Tooling и качество кода

Цель: автоматическая проверка стиля и ловля ошибок до merge.

### BL-901 — Добавить ruff в dev-группу и CI

- **Gap:** [GAP-CR-024](./gaps/code_review_2026-05-25.md#gap-cr-024--нет-linter--formatter-в-ci)
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Шаги.**
1. `[dependency-groups] dev`: `ruff>=0.9`.
2. `[tool.ruff]` в pyproject.toml.
3. Job `ruff check` в `.github/workflows/test.yml`.

---

### BL-902 — pre-commit hooks

- **Gap:** GAP-CR-024  
- **Priority:** P2 | **Status:** done | **Estimate:** S

**Hooks:** ruff, pytest (optional local).

---

### BL-903 — Улучшить логирование swallowed exceptions

- **Gap:** [GAP-CR-025](./gaps/code_review_2026-05-25.md#gap-cr-025--широкие-except-exception)
- **Priority:** P2 | **Status:** done | **Estimate:** M

**Описание.** History/metadata failures: WARNING с контекстом URL/video_id.

---

## Группа 10 — Отложенные фичи (legacy gaps)

Задачи из ранее созданных gap-документов, **не входящие в scope ревью 2026-05-25**, но остающиеся в product backlog.

### BL-1001 — Intra-video pause (пауза внутри одного файла)

- **Gap:** [intravideo_pause_todo.md](./gaps/intravideo_pause_todo.md)
- **Priority:** P3 | **Status:** done | **Estimate:** XL

**Реализовано.** `--intra-video-pause`, конфиг `intra_video_pause`; progress hook + resume с `continuedl`.

---

### BL-1002 — Anti-bot: автоопределение браузера на Windows

- **Gap:** [doublesave_antibot_issue.md](./gaps/doublesave_antibot_issue.md) (Remaining TODOs)
- **Priority:** P2 | **Status:** done | **Estimate:** M

**Зависимости.** BL-501.

**Описание.** При anti-bot ошибке на Windows предложить `--cookies-from-browser edge|chrome`.

---

---

## Группа 11 — Maintenance 1.2 (ревью 2026-08-31)

Цель: восстановить достоверность прогона тестов на Windows, закрыть кроссплатформенный разрыв в CI, снять накопившийся долг по монолиту `execute_download` и расхождения документации.

Дизайн решений по каждой задаче — [design_2026-08-31.md](./design_2026-08-31.md), разделы D-1 … D-7.

### BL-1101 — TTY-fallback в `wait_if_paused` до платформенной развилки

- **Gap:** [GAP-CR-026](./gaps/code_review_2026-08-31.md#gap-cr-026--wait_if_paused-вешает-процесс-на-windows-без-tty) | **Design:** D-1
- **Priority:** P0 | **Status:** done (2026-08-31) | **Estimate:** S

**Описание.** На Windows `wait_if_paused` уходит в бесконечный `msvcrt.kbhit()` при не-интерактивном stdin: проверка интерактивности есть только в Unix-ветке. Процесс зависает навсегда; полный `pytest` на Windows не завершается.

**Шаги.**
1. Поднять `if not self._stdin_is_interactive(): self._wait_for_resume_prompt(); return` в `wait_if_paused` — до развилки по `sys.platform`.
2. Убрать ставшую избыточной проверку из `_wait_for_resume_unix`.
3. В `_wait_for_resume_windows` заменить `threading.Event().wait(0.1)` на ожидание `self._stop_listener`, чтобы `disable()` разрывал цикл.
4. Тесты: `test_wait_if_paused_uses_key_backend_on_tty`, `test_disable_interrupts_windows_wait` (skipif не-win32).

**Критерии приёмки.**
- При `sys.stdin.isatty() == False` цикл ожидания клавиши не запускается ни на одной платформе.
- `tests/test_pause.py` полностью зелёный на Windows и Linux.
- Полный `pytest` на Windows завершается без `--deselect`.

**Реализовано (2026-08-31).** Проверка `_stdin_is_interactive()` поднята в `wait_if_paused` (`ytd/pause.py:156`) с общим fallback на `_wait_for_resume_prompt`; дублирующая проверка удалена из `_wait_for_resume_unix`; оба цикла ожидания идут по `while not self._stop_listener.is_set()` с ожиданием на событии вместо `threading.Event().wait`. Тесты: `test_wait_if_paused_uses_key_backend_on_tty`, `test_wait_for_resume_windows_exits_when_listener_stopped` (skipif не-win32). `tests/test_pause.py` — 7 passed на Windows.

---

### BL-1102 — Платформенно-независимые ассерты путей в тестах истории

- **Gap:** [GAP-CR-027](./gaps/code_review_2026-08-31.md#gap-cr-027--тест-импорта-истории-завязан-на-posix-разделитель-путей) | **Design:** D-2
- **Priority:** P1 | **Status:** done (2026-08-31) | **Estimate:** S

**Описание.** `tests/test_history_import.py:46,52` сравнивают `file_path` со строкой с `/`, а `HistoryStore` сохраняет нативный путь ОС. На Windows тест падает. Продукт менять не нужно: нативное представление пути — намеренное.

**Шаги.**
1. Заменить `str.endswith(...)` на сравнение `Path(...) == Path(...)`.
2. Добавить комментарий, почему нормализация в продукте остаётся нативной.
3. Проверить остальные тесты на строковые сравнения путей (поиск `endswith("`, `in str(`) и починить аналогично.

**Критерии приёмки.** `tests/test_history_import.py` зелёный на Windows и Linux; в `tests/` нет ассертов, завязанных на разделитель пути.

**Реализовано (2026-08-31).** Ассерты переведены на `Path(...) == Path(...)`, добавлен комментарий о намеренной нативной нормализации `file_path`. Аудит остальных тестов: `test_downloader_history.py:121,124` и `test_utils.py:28` сравнивают только имя файла/расширение без разделителя — правки не требуют.

---

### BL-1103 — Матрица CI: ubuntu + windows

- **Gap:** [GAP-CR-028](./gaps/code_review_2026-08-31.md#gap-cr-028--ci-не-покрывает-windows) | **Design:** D-3
- **Priority:** P1 | **Status:** done (2026-08-31) | **Estimate:** S
- **Зависимости:** BL-1101, BL-1102, BL-1104 (иначе первая же Windows-сборка повиснет)

**Описание.** CI выполняется только на `ubuntu-latest`, тогда как основная платформа разработки — Windows и в коде есть Windows-специфичные ветки. Два дефекта дошли до `main` именно из-за этого.

**Шаги.**
1. `strategy.matrix.os: [ubuntu-latest, windows-latest]`, `fail-fast: false` для тестовой джобы.
2. Вынести `ruff check .` в отдельную джобу `lint` на ubuntu.
3. Проверить зелёный прогон обеих джоб.

**Критерии приёмки.** Джобы `test (ubuntu-latest)`, `test (windows-latest)`, `lint` зелёные на PR и на push в `main`.

**Реализовано (2026-08-31).** Первый прогон матрицы (`33342899092`) — success:

| Джоба | Результат | Время |
|-------|-----------|-------|
| `test (ubuntu-latest)` | 96 passed, 3 skipped за 31.4 с | 42 с |
| `test (windows-latest)` | 97 passed, 2 skipped за 35.9 с | 57 с |
| `lint` | All checks passed | 10 с |

Расхождение в счётчиках ожидаемое: `test_wait_for_resume_windows_exits_when_listener_stopped` помечен `skipif(sys.platform != "win32")`, на Linux уходит в skip. Обе платформы собирают одинаковые 99 тестов; Windows-результат в CI совпал с локальным прогоном.

---

### BL-1104 — `pytest-timeout` и глобальный лимит на тест

- **Gap:** [GAP-CR-028](./gaps/code_review_2026-08-31.md#gap-cr-028--ci-не-покрывает-windows) | **Design:** D-3
- **Priority:** P1 | **Status:** done (2026-08-31) | **Estimate:** S

**Описание.** Зависший тест блокирует весь прогон и локально, и в CI. Нужен лимит, превращающий зависание в падение с трассировкой.

**Шаги.**
1. `pytest-timeout>=2.3` в `[dependency-groups] dev`.
2. `[tool.pytest.ini_options]`: `timeout = 60`, `timeout_method = "thread"`.
3. Обновить `uv.lock` (`uv sync`).

**Критерии приёмки.** Искусственно зависший тест падает по таймауту за ≤ 60 с; штатный полный прогон (~40 с) не деградирует.

**Реализовано (2026-08-31).** `pytest-timeout==2.4.0` установлен через `uv sync`, `uv.lock` обновлён; `[tool.pytest.ini_options]` — `timeout = 60`, `timeout_method = "thread"`. Проверено на реальном зависании (до BL-1101): прогон упал по таймауту с трассировкой, указывающей точно на `ytd/pause.py:179`.

---

### BL-1105 — Декомпозиция `execute_download`

- **Gap:** [GAP-CR-029](./gaps/code_review_2026-08-31.md#gap-cr-029--execute_download--новый-монолит) | **Design:** D-4
- **Priority:** P2 | **Status:** todo | **Estimate:** L
- **Зависимости:** BL-1103 (рефакторинг под защитой двухплатформенного CI)

**Описание.** После BL-104 оркестрация переехала целиком в одну функцию на ~950 строк с семью вложенными замыканиями, захватывающими ~15 переменных. Ветки нельзя тестировать по отдельности; управляющий поток держится на флаге `skip_post_processing`.

**Шаги (по одному коммиту на этап, зелёные тесты после каждого).**
1. `workflows/context.py`: `DownloadContext`, `DownloadTotals` (+ `merge`, `exit_code`).
2. `workflows/url_sources.py`, `workflows/info_fetch.py` — чтение `--urls-file`, автодетект/выбор плейлиста, `fetch_info`.
3. `workflows/single_video.py`.
4. `workflows/playlist_unified.py`, `workflows/playlist_per_video.py`.
5. `workflows/playlist_batch.py` + `select_scenario`; удалить `skip_post_processing`.
6. Свести `execute_download` к подготовке контекста и диспетчеру; обновить `DEVELOPMENT.md`.

**Критерии приёмки.**
- `execute_download` ≤ ~150 строк; ни один модуль `workflows/` не превышает ~300 строк.
- Сценарии имеют единую сигнатуру `run(ctx, url, decision) -> DownloadTotals` и не используют замыкания над состоянием команды.
- Флага `skip_post_processing` в коде нет; выбор сценария однозначен по построению.
- `tests/test_playlist_regression.py`, `tests/test_cli.py`, `tests/test_interactive_config.py` проходят без изменений логики; exit-коды и итоговые сообщения не изменились.

---

### BL-1106 — Удалить мёртвую ветку повторного опроса истории

- **Gap:** [GAP-CR-030](./gaps/code_review_2026-08-31.md#gap-cr-030--мёртвая-ветка-повторного-опроса-истории) | **Design:** D-5
- **Priority:** P2 | **Status:** todo | **Estimate:** S
- **Зависимости:** выполняется внутри BL-1105 (этапы 3–5), чтобы не править участок дважды

**Описание.** `download_command.py:902-908`: `if decision is None` недостижимо — `preflight_decision` всегда заполнен. Решение зафиксировано: удалить ветку (повторный опрос был бы регрессом UX, а для элементов плейлиста уточнённый опрос уже выполняется в `process_playlist_entries`).

**Шаги.**
1. Удалить недостижимую ветку.
2. Удалить `history_video_id` и его уточнения, если после этого переменная не используется на данном пути (проверка ruff `F841`).

**Критерии приёмки.** Недостижимых веток в `execute_download` нет; `ruff check .` чист; тесты истории зелёные.

---

### BL-1107 — `urls.local.txt` вне репозитория

- **Gap:** [GAP-CR-031](./gaps/code_review_2026-08-31.md#gap-cr-031--urlslocaltxt-с-личными-ссылками-в-репозитории) | **Design:** D-6
- **Priority:** P1 | **Status:** done (2026-08-31) | **Estimate:** S

**Описание.** Файл заявлен как локальный («не попадает в Git»), но отслеживается; правило в `.gitignore:68` закомментировано. В файле реальные ссылки пользователя.

**Шаги.**
1. [x] `git rm --cached urls.local.txt` (файл остаётся на диске).
2. [x] Раскомментировать правило и расширить: `urls.local.txt`, `urls.*.local.txt` (`.gitignore:68-69`).
3. [x] Добавить `urls.example.txt` с синтетическими примерами.
4. [x] Упомянуть в README рядом с примером `--urls-file`, что рабочий файл локальный.
5. [x] Отдельное решение владельца: очищать ли историю коммитов (`git filter-repo` + force-push).
   **Решение (2026-08-31): историю не переписываем.** Ссылки остаются в прошлых ревизиях;
   репозиторий приватный, риск ограничен участниками с доступом. Переписывание истории
   ломает клоны, форки и PR, что перевешивает выгоду. К вопросу не возвращаемся без
   изменения статуса репозитория (например, перед публикацией).

**Критерии приёмки.** `git ls-files urls.local.txt` пусто; локальный файл не отображается как untracked-шум; в репозитории есть `urls.example.txt`. — Выполнено.

---

### BL-1108 — «Структура проекта» в README по факту

- **Gap:** [GAP-CR-032](./gaps/code_review_2026-08-31.md#gap-cr-032--readme-описывает-несуществующие-каталоги) | **Design:** D-7
- **Priority:** P3 | **Status:** todo | **Estimate:** S

**Описание.** README перечисляет `data/.gitkeep` и `downloads/.gitkeep`, которых нет ни в дереве, ни в индексе. Каталоги создаются автоматически при первом запуске.

**Шаги.** Обновить блок структуры; добавить примечание про автосоздание каталогов согласно `output` / `history_db` / `save_metadata`.

**Критерии приёмки.** Структура в README совпадает с `git ls-files`; несуществующие каталоги не упоминаются как существующие.

---

### BL-1109 — Актуализировать devplan

- **Gap:** [GAP-CR-033](./gaps/code_review_2026-08-31.md#gap-cr-033--devplanmd-устарели-относительно-реализации) | **Design:** D-7
- **Priority:** P3 | **Status:** todo | **Estimate:** M

**Описание.** `devplan.md` / `devplan_ru.md` (27.10.2025) в разделе «Ограничения сейчас» перечисляют как нереализованные: режим «каждое видео отдельно», возобновление загрузок, субтитры — всё это реализовано.

**Шаги.**
1. Переписать «Ограничения сейчас» под фактическое состояние.
2. Обновить «Технический долг»: GAP-CR-029, GAP-CR-009, покрытие Windows.
3. Дополнить «Реализовано» фичами Maintenance 1.1 (cookies, anti-bot hints, intra-video пауза, история SQLite, `no_progress`).
4. Проставить дату актуализации в шапке обеих версий.

**Критерии приёмки.** Ни одно «ограничение» не противоречит коду на `main`; EN- и RU-версии остаются построчно параллельными и правятся одним коммитом.

---

## Матрица трассировки Gap → Backlog

| Gap ID | Backlog задачи |
|--------|----------------|
| GAP-CR-001 | BL-104 |
| GAP-CR-002 | BL-101 |
| GAP-CR-003 | BL-102 |
| GAP-CR-004 | BL-401 |
| GAP-CR-005 | BL-402, BL-403 |
| GAP-CR-006 | BL-203 |
| GAP-CR-007 | BL-704 |
| GAP-CR-008 | BL-702, BL-603 |
| GAP-CR-009 | BL-703 |
| GAP-CR-010 | BL-202 |
| GAP-CR-011 | BL-102 |
| GAP-CR-012 | BL-301, BL-604 |
| GAP-CR-013 | BL-201, BL-802 |
| GAP-CR-014 | BL-103 |
| GAP-CR-015 | BL-105 |
| GAP-CR-016 | BL-106 |
| GAP-CR-017 | BL-204 |
| GAP-CR-018 | BL-601 |
| GAP-CR-019 | BL-602, BL-603, BL-604 |
| GAP-CR-020 | BL-801, BL-802 |
| GAP-CR-021 | BL-501, BL-502, BL-1002 |
| GAP-CR-022 | BL-302 |
| GAP-CR-023 | BL-701 |
| GAP-CR-024 | BL-901, BL-902 |
| GAP-CR-025 | BL-903 |
| GAP-CR-026 | BL-1101 |
| GAP-CR-027 | BL-1102 |
| GAP-CR-028 | BL-1103, BL-1104 |
| GAP-CR-029 | BL-1105 |
| GAP-CR-030 | BL-1106 |
| GAP-CR-031 | BL-1107 |
| GAP-CR-032 | BL-1108 |
| GAP-CR-033 | BL-1109 |

GAP-CR-001 … GAP-CR-025 — ревью [2026-05-25](./gaps/code_review_2026-05-25.md); GAP-CR-026 … GAP-CR-033 — ревью [2026-08-31](./gaps/code_review_2026-08-31.md).

---

## Чеклист закрытия бэклога (Definition of Done для релиза «Maintenance 1.1»)

- [x] Все P0 задачи: BL-201, BL-301, BL-601 — status `done`
- [x] Все P1 задачи групп 1, 5, 6 — status `done`
- [x] Regression suite: `pytest` green на Python 3.14 (95 passed, 2 skipped локально)
- [x] `docs/gaps/code_review_2026-05-25.md`: статусы GAP-CR-* обновлены
- [x] `doublesave_antibot_issue.md`: синхронизирован с закрытыми BL-*

---

## Чеклист закрытия (Definition of Done для релиза «Maintenance 1.2»)

- [x] P0: BL-1101 — status `done`
- [x] P1: BL-1102, BL-1103, BL-1104, BL-1107 — status `done`
- [x] Полный `pytest` завершается и зелёный на Windows **и** Linux без `--deselect`
- [x] `ruff check .` чист
- [x] CI: джобы `test (ubuntu-latest)`, `test (windows-latest)`, `lint` зелёные
- [ ] P2/P3: BL-1105, BL-1106, BL-1108, BL-1109 — `done` либо явно перенесены с обоснованием
- [ ] `docs/gaps/code_review_2026-08-31.md`: статусы GAP-CR-026 … GAP-CR-033 обновлены
- [ ] `docs/gaps/README.md`: индекс синхронизирован

---

## Связанные документы

- [Анализ проекта 2026-08-31](./analysis_2026-08-31.md)
- [Гэп-ревью 2026-08-31](./gaps/code_review_2026-08-31.md) — GAP-CR-026 … GAP-CR-033
- [Дизайн исправлений 2026-08-31](./design_2026-08-31.md) — D-1 … D-7
- [Архитектурное и кодовое ревью 2026-05-25 (полный текст)](./gaps/code_review_2026-05-25.md)
- [Duplicate downloads + anti-bot](./gaps/doublesave_antibot_issue.md)
- [Intra-video pause](./gaps/intravideo_pause_todo.md) — BL-1001 done
- [Дорожная карта (devplan)](./devplan_ru.md)
- [Разработка](./DEVELOPMENT.md)
