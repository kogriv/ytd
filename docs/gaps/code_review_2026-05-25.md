# Архитектурное и кодовое ревью проекта ytd

Status: closed (Maintenance 1.1; спринты A–J, 2026-05-25)  
Owner: @Ivan  
Created: 2026-05-25  
Last updated: 2026-05-25  
Scope: архитектура, реализация, качество кода, тестирование, эксплуатация, документация  
Версия проекта на момент ревью: MVP 1.0, Python 3.14, yt-dlp 2026.3.17  

### Исправлено после ревью (спринты A–J)

| Gap ID | Исправление |
|--------|-------------|
| GAP-CR-001 | BL-104: `ytd/workflows/`, `cli.py` ~394 строк |
| GAP-CR-002 | BL-101: `ytd/console.py` |
| GAP-CR-003, GAP-CR-011 | BL-102: `run_single_video_interactive_setup()` |
| GAP-CR-004 | BL-401: один `extract_info` на загрузку |
| GAP-CR-005 | BL-402, BL-403: file_path по id, history hooks |
| GAP-CR-006 | BL-203: декоратор `retry` |
| GAP-CR-007 | BL-704: `HistoryStore` |
| GAP-CR-008 | BL-702: двухэтапный `fetch_download` |
| GAP-CR-009 | BL-703: роли JSONL vs SQLite в docs |
| GAP-CR-010 | BL-202: playlist mode 2 |
| GAP-CR-012 | BL-301, BL-604: Unix pause listener |
| GAP-CR-013 | BL-201, BL-802: tri-state `--interactive` |
| GAP-CR-014 | BL-103: `process_playlist_entries()` (частично) |
| GAP-CR-015 | BL-105: `typer.Exit` |
| GAP-CR-016 | BL-106: TypeAlias + валидация config |
| GAP-CR-017 | BL-204: `logs/*.log` в `.gitignore` |
| GAP-CR-018 | BL-601: regression test doublesave |
| GAP-CR-019 | BL-602, BL-603, BL-604: тесты workflows/pause |
| GAP-CR-020 | BL-801, BL-802: синхронизация docs |
| GAP-CR-021 | BL-501, BL-502, BL-1002: cookies + anti-bot |
| GAP-CR-022 | BL-302: `no_progress`, auto-retry |
| GAP-CR-023 | BL-701: SQLite WAL |
| GAP-CR-024 | BL-901, BL-902: ruff + pre-commit |
| GAP-CR-025 | BL-903: WARNING для history/metadata |

**Открытый design debt:** GAP-CR-009 (JSONL + SQLite); **mitigated:** GAP-CR-001, GAP-CR-014 (дальнейшая декомпозиция опциональна).

---

## Содержание

1. [Резюме](#резюме)
2. [Методология и контекст](#методология-и-контекст)
3. [Обзор архитектуры](#обзор-архитектуры)
4. [Ревью по модулям](#ревью-по-модулям)
5. [Каталог гэпов](#каталог-гэпов)
6. [Связь с существующими gap-документами](#связь-с-существующими-gap-документами)
7. [Итоговая оценка](#итоговая-оценка)

Связанный документ с задачами на исправление: [../backlog.md](../backlog.md).

---

## Резюме

**ytd** — зрелый MVP CLI-загрузчика видео и аудио на базе yt-dlp с русскоязычным интерфейсом, интерактивным выбором качества, журналом загрузок в SQLite и пакетной обработкой плейлистов. Проект пригоден для личного и рабочего использования.

**Главная архитектурная проблема (на момент ревью):** файл `ytd/cli.py` (~1680 строк) концентрировал оркестрацию загрузки. **После BL-104:** `cli.py` ~394 строк, логика в `ytd/workflows/`; полная декомпозиция на отдельные `download_*.py` — опциональный следующий этап (GAP-CR-001 mitigated).

**Сильные стороны:** модуль `Downloader` (обёртка yt-dlp), конфигурация через YAML и переменные окружения, история загрузок с нормализацией идентификаторов, продуманный интерактивный UX для плейлистов (resume, маски выбора, стратегии fallback качества), тесты с заглушкой FakeYDL.

**Критичные гэпы ревью — закрыты в спринтах A–J** (interactive default, Linux pause, doublesave regression, single extract_info, cookies, ruff/CI и др.). Актуальный статус каждого GAP-CR-* — в теле документа и [backlog.md](../backlog.md).

Полный перечень гэпов с идентификаторами — в разделе [Каталог гэпов](#каталог-гэпов). Задачи на исправление сгруппированы в [backlog.md](../backlog.md).

---

## Методология и контекст

### Что анализировалось

- Исходный код пакета `ytd/` (все модули).
- Тесты в `tests/`.
- Конфигурация проекта (`pyproject.toml`, `uv.lock`).
- Существующая документация (`README.md`, `docs/`, gap-документы).
- CI (`.github/workflows/test.yml`).

### Что не входило в ревью

- Полный аудит безопасности зависимостей (SCA).
- Нагрузочное тестирование и бенчмарки.
- Ручная проверка загрузки с реальных площадок (кроме косвенных данных из логов и gap-документов).

### Стек на момент ревью

| Компонент | Версия / состояние |
|-----------|-------------------|
| Python | 3.14.2 (`.python-version`, `requires-python >= 3.14`) |
| yt-dlp | 2026.3.17 |
| typer | 0.25.1 |
| rich | 15.0.0 |
| pytest | 9.0.3 (dev-группа) |
| CI | GitHub Actions, `uv sync --frozen` + pytest |

---

## Обзор архитектуры

### Задуманные слои

```
Presentation   → cli.py, interactive.py, pause.py
Domain         → downloader.py, types.py, config.py
Infrastructure → history/storage.py, utils.py, logging.py
External       → yt-dlp, SQLite, ffmpeg
```

### Поток загрузки (упрощённо)

```
cmd_download (cli.py)
    → load_config / merge_cli_overrides
    → _initialize_history (SQLite + импорт JSONL)
    → preflight history decisions (интерактивные промпты)
    → [ветвление по режиму]
        → интерактивный плейлист (поштучная загрузка)
        → неинтерактивный плейлист с паузой (ещё один поштучный цикл)
        → общий путь (одна DownloadOptions на URL)
    → Downloader.download / get_info
        → yt-dlp YoutubeDL
        → history.record_event + save_metadata_jsonl
```

### Что работает хорошо

1. **Facade над yt-dlp.** Класс `Downloader` инкапсулирует сбор опций, retry, логирование, запись истории и метаданных. Это правильное место для расширения (cookies, external downloader и т.д.).

2. **Value objects.** `AppConfig` и `DownloadOptions` как dataclass с `slots=True` — читаемый контракт между слоями.

3. **Приоритет конфигурации.** CLI > ENV > файл > defaults — предсказуемо и задокументировано.

4. **История загрузок.** Нормализация YouTube ID (`yt:VIDEO_ID`), UPSERT в SQLite, импорт из legacy JSONL, CLI для просмотра и экспорта.

5. **Интерактивный UX.** Меню качества, нумерация файлов плейлиста, resume с маской `3-7`, стратегии «эконом» / «богато» для fallback качества — редкий уровень проработки для CLI-утилиты такого размера.

### Архитектурные проблемы

#### GAP-CR-001 — God Object в `cli.py`

**Severity:** высокая  
**Status:** mitigated (BL-104; `cli.py` ~394 строк, оркестрация в `ytd/workflows/`)

**Описание.** Файл `cli.py` одновременно содержит:
- определение Typer-приложения и команд `download`, `info`, `history`;
- функции форматирования консоли (`safe_echo`, `safe_secho`);
- логику preflight-проверки истории (`prompt_history_decision`);
- обработку сетевых ошибок (`_prompt_network_recovery`);
- три независимых orchestrator'а загрузки плейлиста;
- дублированный интерактивный flow для одиночного видео (два почти идентичных блока «ШАГ 1–3»).

**Влияние.** Любое изменение UX или исправление бага требует правок в большом монолитном файле. Высок риск регрессий (исторически уже был баг двойной загрузки плейлиста — см. `doublesave_antibot_issue.md`). Новым контрибьюторам сложно ориентироваться.

**Рекомендация по исправлению.**

1. Выделить тонкий слой CLI: только парсинг аргuments и вызов workflow-функций.
2. Создать модуль `ytd/workflows/` (или `ytd/services/`):
   - `download_single.py` — одиночное видео;
   - `download_playlist_interactive.py` — интерактивный плейлист;
   - `download_playlist_batch.py` — неинтерактивный / с паузой.
3. Перенести `prompt_history_decision`, `_prompt_network_recovery` в `ytd/history/prompts.py` или `ytd/workflows/history.py`.
4. Целевой размер `cli.py`: не более 300–400 строк.

**Критерии приёмки.** Команда `download` делегирует работу workflow-модулям; `cli.py` не содержит циклов загрузки и не вызывает `Downloader.download` напрямую.

---

#### GAP-CR-002 — Циклические зависимости import

**Severity:** средняя  
**Status:** fixed (2026-05-25, BL-101)  
**Location:** `ytd/cli.py` ↔ `ytd/interactive.py` ↔ `ytd/pause.py`

**Описание.**

- `interactive.py` импортирует `safe_echo`, `safe_secho` из `cli.py` (строка 11).
- `pause.py` импортирует `safe_echo`, `safe_secho` из `cli.py` (строка 10).
- `cli.py` импортирует `interactive` и `pause` (внутри `cmd_download` — отложенно, но при загрузке модулей цикл замыкается).

Сейчас это работает благодаря порядку инициализации Python и отложенному import в `cmd_download`, но архитектурно неверно: presentation-модули нижнего уровня зависят от верхнего orchestrator'а.

**Влияние.** Хрупкость при рефакторинге; невозможность импортировать `interactive` или `pause` изолированно в тестах без подтягивания всего `cli.py`; риск `ImportError` при изменении порядка import.

**Рекомендация по исправлению.**

1. Создать модуль `ytd/console.py` (или `ytd/ui/console.py`).
2. Перенести `_sanitize_console_text`, `safe_echo`, `safe_secho` и константу `_SANITIZE_REPLACEMENTS` из `cli.py`.
3. Обновить import во всех модулях: `from .console import safe_echo, safe_secho`.
4. `cli.py` также импортирует из `console.py`.

**Критерии приёмки.** Нет import `cli` из `interactive.py` и `pause.py`; `python -c "from ytd.interactive import show_quality_menu"` не загружает Typer app.

---

#### GAP-CR-003 — Дублирование интерактивного flow одиночного видео

**Severity:** средняя  
**Status:** fixed (BL-102)  
**Location:** `ytd/interactive.py`, `ytd/workflows/download_command.py` (исторически дубли в `cli.py`)

**Описание.** Логика интерактивной настройки одиночного видео (ШАГ 1: качество, ШАГ 2: имя файла, ШАГ 3: проверка существующих файлов) скопирована дважды:
- когда плейлист оказался пустым и обрабатывается как одиночное видео;
- когда URL изначально не является плейлистом.

Блоки отличаются только контекстом (переменные `history_video_id`, `current_output_dir`), но структура идентична (~130 строк × 2).

**Влияние.** Дублирование — прямой источник расхождения поведения и регрессий: исправление в одном месте легко забыть во втором.

**Рекомендация по исправлению.**

1. Вынести функцию в `interactive.py`, например:
   ```python
   def run_single_video_interactive_setup(
       info: dict,
       output_dir: Path,
       *,
       default_suffix_fn=extract_quality_suffix,
   ) -> SingleVideoSetupResult
   ```
   где `SingleVideoSetupResult` — dataclass с полями `chosen_format`, `quality_suffix`, `file_prefix`, `custom_name`, `overwrite`.
2. Заменить оба блока в `cli.py` вызовом этой функции.
3. Добавить unit-тест на `run_single_video_interactive_setup` с моком `typer.prompt`.

**Критерии приёмки.** В `cli.py` нет двух копий блока «ШАГ 1–3»; поведение покрыто тестом.

---

## Ревью по модулям

### `ytd/downloader.py`

**Оценка:** 8/10 — сильная сторона проекта.

**Сильные стороны:**
- `build_ydl_opts` — полная сборка опций yt-dlp: шаблон имени с префиксом/суффиксом, custom format, audio/video presets, субтитры, ffmpeg, dry-run, overwrite.
- Retry с экспоненциальной задержкой в `get_info` и `download`.
- Классификация сетевых ошибок `_looks_like_network_issue` с обходом цепочки исключений.
- Запись истории на этапах `in_progress`, `success`, `failed`.
- Unicode-safe вывод границ в `_print_file_info` (fallback на `-` при неподдерживаемой кодировке).

#### GAP-CR-004 — Двойной вызов `extract_info` при каждой загрузке

**Severity:** средняя  
**Status:** fixed (2026-05-25, BL-401)  
**Location:** `ytd/downloader.py`, метод `download`, строки ~416–429

**Описание.** При реальной загрузке (не dry-run) код выполняет:
1. `ydl.extract_info(opts.url, download=False)` — для preview и записи `in_progress` в историю.
2. `ydl.extract_info(opts.url, download=not opts.dry_run)` — для фактического скачивания.

Каждый вызов — отдельный round-trip к API площадки (YouTube, VK и др.). В интерактивном режиме плейлиста это умножается: анализ плейлиста + анализ каждого entry + preflight + двойной extract при download.

**Влияние.** Лишняя нагрузка на API, повышенный риск rate limiting и anti-bot блокировок; увеличение времени загрузки.

**Рекомендация по исправлению.**

1. Объединить в один вызов `extract_info(url, download=True)` когда preview нужен только для `_print_file_info`.
2. Либо: использовать результат первого вызова, если yt-dlp позволяет передать уже полученный info во второй этап (через `process_ie_result` или повторное использование объекта — проверить API yt-dlp для текущей версии).
3. Для preview достаточно вызвать `_print_file_info` на info, возвращённом после download, если порядок вывода некритичен; либо вызывать preview только в verbose-режиме.
4. Добавить тест: mock `extract_info` считает количество вызовов — ожидание 1, не 2.

**Критерии приёмки.** На одну загрузку одного видео — не более одного сетевого extract (кроме явно документированных случаев, например интерактивный pre-analysis).

---

#### GAP-CR-005 — Неточное сопоставление `file_paths` при загрузке плейлиста

**Severity:** низкая  
**Status:** fixed (BL-402, BL-403)  
**Location:** `ytd/downloader.py`, `_build_events`, `_progress_hook`

**Описание.** При формировании событий истории для плейлиста `file_paths[idx]` сопоставляется с `entries[idx]` по позиции. Если часть элементов плейлиста не скачалась или `_finished_files` содержит неполный список, пути могут быть приписаны не тем video_id.

**Влияние.** Некорректные записи в истории (неправильный `file_path` для video_id). Для одиночных загрузок и поштучного интерактивного режима проблема не проявляется.

**Рекомендация по исправлению.**

1. Сопоставлять файлы по `id` из info entry, а не по индексу.
2. Либо записывать историю по одному событию на каждый успешно завершённый hook `finished`, а не batch после всего плейлиста.

**Критерии приёмки.** При частичном успехе плейлиста каждая запись history содержит корректный `file_path` для соответствующего `video_id`.

---

#### GAP-CR-006 — Заглушка декоратора `retry` в utils

**Severity:** низкая  
**Status:** fixed (BL-203)

**Описание.** Функция `retry()` объявлена как декоратор с документацией, но фактически возвращает функцию без обёртки (TODO в теле). Реальный retry реализован inline в `Downloader.get_info` и `Downloader.download`.

**Влияние.** Вводит в заблуждение читателя кода; мёртвый API.

**Рекомендация.** Либо реализовать декоратор и использовать в `Downloader`, либо удалить функцию и оставить retry только в `Downloader`.

---

### `ytd/history/storage.py`

**Оценка:** 7/10.

**Сильные стороны:**
- UPSERT через `ON CONFLICT(video_id) DO UPDATE`.
- Миграция схемы (`ALTER TABLE` для `retry_count`, `last_action`).
- `normalize_history_id` — YouTube ID + нормализация URL.
- Fallback SQL без `NULLS LAST` для старых SQLite.
- Импорт JSONL только при пустой таблице.

#### GAP-CR-007 — Глобальное состояние `_DB_PATH`

**Severity:** низкая  
**Status:** fixed (BL-704)  
**Location:** `ytd/history/storage.py`, класс `HistoryStore`

**Описание.** Путь к базе хранится в module-level global `_DB_PATH`, устанавливается через `init_db()`. Все функции (`record_event`, `fetch_download`, …) используют этот global.

**Влияние.** Усложняет параллельные тесты с разными БД; не thread-safe (для текущего CLI некритично); неявная зависимость от порядка вызова `init_db`.

**Рекомендация.**

1. Краткосрочно: документировать контракт «перед использованием history вызвать init_db».
2. Среднесрочно: класс `HistoryStore(path: Path)` с методами, передаваемый в `Downloader` через DI.
3. В тестах: fixture, явно вызывающая `init_db(tmp_path / "test.db")` перед каждым тестом (частично уже есть).

---

#### GAP-CR-008 — `fetch_download` с OR может вернуть неверную запись

**Severity:** низкая  
**Status:** fixed (BL-702)

**Описание.** При одновременной передаче `video_id` и `url` запрос строится как `WHERE video_id = :video_id OR url = :url`. Может вернуться запись, совпавшая по URL, но не по intended video_id, если в базе есть несколько связанных записей.

**Рекомендация.** Двухэтапный lookup: сначала точное совпадение по нормализованному `video_id`, затем fallback по `url`; не использовать OR в одном запросе без `ORDER BY` приоритета.

---

#### GAP-CR-009 — Дублирование источников правды: JSONL + SQLite

**Severity:** низкая  
**Status:** documented (BL-703; design debt — dual storage намеренно)

**Описание.** Метаданные пишутся в JSONL (`save_metadata_jsonl`) параллельно с SQLite-историей. Импорт из JSONL в SQLite однократный при создании таблицы. Дальнейшая синхронизация не garantированa.

**Рекомендация.** Зафиксировать в документации роли: SQLite — операционная история и CLI; JSONL — append-only архив метаданных yt-dlp. Либо постепенно deprecate JSONL в пользу SQLite + export.

---

### `ytd/interactive.py`

**Оценка:** 8/10 для UX-логики.

**Сильные стороны:** меню качества, fallback стратегии, resume плейлиста, парсинг масок выбора, `get_entry_url` с fallback по полям yt-dlp.

#### GAP-CR-010 — Режим 2 «настроить каждое видео отдельно» не реализован

**Severity:** средняя  
**Status:** fixed (BL-202)  
**Location:** `ytd/workflows/download_command.py` (mode 2)

**Описание.** В `choose_playlist_mode()` пользователю предлагается опция «2) Настроить каждое видео отдельно», но при выборе mode 2 выполнение не реализовано — блок пустой.

**Влияние.** Обещанная функциональность отсутствует; пользователь выбирает опцию и не получает ожидаемого поведения.

**Рекомендация.** Либо реализовать (вызов `run_single_video_interactive_setup` в цикле по entries), либо убрать пункт из меню до реализации и пометить в devplan.

---

#### GAP-CR-011 — `configure_filename_prefix()` не используется в основном flow

**Severity:** низкая  
**Status:** fixed (BL-102)

**Описание.** Функция объявлена, но основной интерактивный flow в `cli.py` дублирует аналогичную логику inline вместо вызова helper'а.

**Рекомендация.** Использовать helper или удалить мёртвый код (см. GAP-CR-003).

---

### `ytd/pause.py`

**Оценка:** 4/10 на Linux, 7/10 на Windows.

#### GAP-CR-012 — Пауза между видео не работает на Linux через клавишу `p`

**Severity:** высокая (UX / платформенная)  
**Status:** fixed (2026-05-25, BL-301)  
**Location:** `ytd/pause.py`, `_keyboard_listener`, строки 54–61

**Описание.** Слушатель клавиатуры использует только `msvcrt` (Windows). На Linux и macOS при `ImportError` listener silently return — фоновый поток завершается без прослушивания. При этом CLI выводит сообщение «нажмите 'p' во время загрузки» (`cli.py` ~779–781).

`wait_if_paused()` на non-Windows использует fallback `typer.prompt("Нажмите Enter…")`, но до этого пауза никогда не запрашивается, потому что `_pause_requested` never set без listener.

**Влияние.** Пользователи Linux (основная среда разработки и многие серверы) не могут поставить паузу между видео клавишей `p`, хотя функция заявлена в README и конфиге.

**Рекомендация.**

1. **Вариант A:** реализовать listener через `termios` + `tty` + `select` (Unix) по аналогии с msvcrt на Windows.
2. **Вариант B:** использовать кроссплатформенную библиотеку (например `pynput` — добавляет зависимость).
3. **Вариант C (минимальный):** при старте на non-Windows выводить предупреждение: «Пауза по клавише `p` доступна только на Windows; на Linux используйте Ctrl+C или дождитесь завершения видео» и не включать misleading UI.
4. Добавить тест с mock listener или platform marker.

**Критерии приёмки.** На Linux нажатие `p` во время загрузки устанавливает `_pause_requested`; после завершения текущего видео вызывается `wait_if_paused`.

---

### `ytd/config.py`

**Оценка:** 8/10.

**Замечание:** документация README упоминает `config.yaml`, код ищет `ytd.config.yaml` — в README это уже исправлено предупреждением; `docs/usage.md` всё ещё говорит «config.yaml» (см. GAP-CR-020).

---

### `ytd/cli.py` — UX и логика

#### GAP-CR-013 — Противоречие default `--interactive` и `interactive_by_default`

**Severity:** высокая  
**Status:** fixed (2026-05-25, BL-201)  
**Location:** `ytd/cli.py`, строки 453, 505–506; `config.example.yaml`, README

**Описание.**

- Typer option: `interactive: bool = typer.Option(True, …)` — интерактив **включён по умолчанию** в CLI.
- Конфиг: `interactive_by_default: false` — документация описывает включение через конфиг.
- Логика: `if not interactive and cfg.interactive_by_default: interactive = True` — конфиг может только **включить** интерактив, но не **выключить**, потому что CLI default уже `True`.

**Влияние.** Пользователь, настроивший `interactive_by_default: false` в `ytd.config.yaml`, всё равно получает интерактивные диалоги. Для автоматизации (`cron`, scripts) нужен обязательный `--no-interactive`, конфиг не работает как ожидается. Противоречие README и поведения.

**Рекомендация.**

1. Изменить CLI default на `interactive: bool = typer.Option(False, …)`.
2. После загрузки конфига: `if cfg.interactive_by_default: interactive = True` (CLI flag `--interactive` / `--no-interactive` имеет приоритет через явную проверку).
3. Либо: `interactive: Optional[bool] = typer.Option(None, …)` и разрешать три состояния: None → из конфига, True/False → явный override.
4. Обновить тесты CLI и README.

**Критерии приёмки.** При `interactive_by_default: false` и без флагов CLI загрузка идёт без диалогов; при `true` — с диалогами.

---

#### GAP-CR-014 — Три параллельных orchestrator'а плейлиста

**Severity:** средняя  
**Status:** mitigated (BL-103; общий цикл `process_playlist_entries`, batch-путь сохранён)  
**Location:** `ytd/workflows/` (исторически три path в `cli.py`)

**Описание.** Три отдельных code path для загрузки элементов плейлиста:
1. Интерактив unified mode — ручной цикл с `single_opts`.
2. Pause + non-interactive playlist — второй ручной цикл, структурно похожий на первый.
3. Общий `Downloader.download` с `playlist=True`.

**Влияние.** Дублирование логики retry, network recovery, history decision, подсчёта `failed`/`total_files`. Исправления нужно переносить в три места.

**Рекомендация.** Единая функция `download_playlist_entries(entries, opts_factory, …)` с параметрами режима; см. GAP-CR-001.

---

#### GAP-CR-015 — Смешение `sys.exit()` и `raise typer.Exit()`

**Severity:** низкая  
**Status:** fixed (BL-105)

**Описание.** В одной команде используются и `sys.exit(code)`, и `raise typer.Exit(code=…)`.

**Рекомендация.** Унифицировать на `raise typer.Exit` для корректной работы с Typer testing и hooks.

---

### `ytd/types.py`

#### GAP-CR-016 — Расхождение типов `AppConfig` и `DownloadOptions`

**Severity:** низкая  
**Status:** fixed (BL-106)

**Описание.** `AppConfig.quality`, `audio_format`, `video_format` типизированы как `str`. `DownloadOptions` использует `Literal["best", "1080p", …]`. При передаче из конфига mypy/pyright не могут проверить корректность; в коде — suppress через `type: ignore`.

**Рекомендация.** Выровнять типы (общие TypeAlias) или добавить валидацию в `load_config` / `merge_cli_overrides` с `typer.BadParameter` при неверных значениях.

---

### `ytd/logging.py`

**Оценка:** 8/10. Idempotent setup, rotating file handler, разделение уровней консоль/файл.

#### GAP-CR-017 — Лог-файл может попадать в git

**Severity:** низкая  
**Status:** fixed (BL-204)

**Описание.** Строка `#*.log` закомментирована; `logs/ytd.log` фигурировал в `git status` как modified.

**Рекомендация.** Раскомментировать `*.log` или добавить `logs/*.log` с сохранением `!logs/.gitkeep`.

---

### `ytd/utils.py`

**Оценка:** 8/10. `sanitize_filename` — Windows-safe, reserved names, длина 255. `find_existing_files` — корректный обход проблемы glob с `[]`.

---

## Тестирование

**Текущее состояние (2026-05-25):** 95 passed, 2 skipped (integration при `YTD_IT_URL`).

**Сильные стороны:**
- FakeYDL в autouse fixture — изоляция от сети.
- Покрыты: config, downloader opts, CLI базовые сценарии, history storage и CLI, utils, logging.

#### GAP-CR-018 — Нет regression-теста на двойную загрузку плейлиста

**Severity:** высокая  
**Status:** fixed (2026-05-25, BL-601)  
**Location:** отсутствует; связан с `docs/gaps/doublesave_antibot_issue.md`

**Описание.** Баг двойной загрузки после interactive unified mode был исправлен флагом `skip_post_processing`, но автоматического теста нет. Повторная регрессия возможна при рефакторинге `cli.py`.

**Рекомендация.**

1. Тест: mock `Downloader.download`, симулировать interactive playlist unified path, assert `download.call_count == len(entries)`.
2. Assert отсутствие второго вызова с `playlist=True` на тот же URL.

**Критерии приёмки.** Тест падает, если удалить `skip_post_processing`.

---

#### GAP-CR-019 — Нет тестов interactive, pause, playlist workflows

**Severity:** средняя  
**Status:** fixed (BL-602, BL-603, BL-604; базовое покрытие workflows/pause)

**Описание.** Добавлены тесты selection mask, normalize_history_id, pause controller, interactive setup, playlist regression; полное E2E-покрытие CLI-диалогов не требовалось.

---

## Документация

#### GAP-CR-020 — Устаревшие dev-документы

**Severity:** низкая  
**Status:** fixed (BL-801, BL-802)

**Описание.**

- `DEVELOPMENT.md`: Python 3.13.5, venv `venv_ytd` — не соответствует текущему `.venv` + Python 3.14.
- `devplan_ru.md`: «29 тестов» — сейчас 38.
- `usage.md`: «все параметры задаются в config.yaml» — код использует `ytd.config.yaml`.

**Рекомендация.** Синхронизировать документы с `pyproject.toml`, `.python-version`, фактическим числом тестов.

---

## Безопасность и эксплуатация

#### GAP-CR-021 — Нет поддержки cookies для обхода anti-bot YouTube

**Severity:** высокая (operational)  
**Status:** fixed (2026-05-25, BL-501, BL-502)  
**Location:** `ytd/downloader.py`; см. `docs/gaps/doublesave_antibot_issue.md`

**Описание.** yt-dlp поддерживает `cookiefile` и `cookiesfrombrowser`. ytd не пробрасывает эти опции в `ydl_opts`. При ошибке «Sign in to confirm you're not a bot» загрузка падает.

**Рекомендация.**

1. Поля в `AppConfig` / `DownloadOptions`: `cookies_file: Optional[Path]`, `cookies_from_browser: Optional[str]`.
2. CLI: `--cookies`, `--cookies-from-browser`.
3. ENV: `YTD_COOKIES`, `YTD_COOKIES_FROM_BROWSER`.
4. Проброс в `build_ydl_opts`.
5. При детектировании anti-bot в сообщении ошибки — подсказка пользователю в `_prompt_network_recovery` или отдельным handler.

---

#### GAP-CR-022 — OSError [Errno 22] на Windows при flush progress

**Severity:** низкая  
**Status:** fixed (BL-302)  
**Location:** `ytd/downloader.py`, `AppConfig.no_progress`

**Описание.** В логах зафиксирован `OSError [Errno 22] Invalid argument` при flush stdout/stderr во время progress bar yt-dlp на Windows.

**Рекомендация.** Опция `noprogress=True` для проблемных терминалов; catch OSError при flush в progress hook; документировать в manual.

---

#### GAP-CR-023 — SQLite без WAL и busy_timeout

**Severity:** низкая  
**Status:** fixed (BL-701)

**Рекомендация.** При `init_db`: `PRAGMA journal_mode=WAL; PRAGMA busy_timeout=5000;`

---

## Качество кода и tooling

#### GAP-CR-024 — Нет linter / formatter в CI

**Severity:** низкая  
**Status:** fixed (BL-901, BL-902)

---

#### GAP-CR-025 — Широкие `except Exception`

**Severity:** низкая (accepted pattern с оговорками)  
**Status:** fixed (BL-903)

**Рекомендация.** Сужать типы где возможно; для intentional swallow — логировать на WARNING, не только DEBUG.

---

## Связь с существующими gap-документами

| Документ | Связь с гэпами ревью |
|----------|---------------------|
| [doublesave_antibot_issue.md](./doublesave_antibot_issue.md) | GAP-CR-018, GAP-CR-021, GAP-CR-022 — **closed** (2026-05-25) |
| [intravideo_pause_todo.md](./intravideo_pause_todo.md) | BL-1001 done; не дублирует GAP-CR-012 |

Статусы legacy gap-документов синхронизированы с [backlog.md](../backlog.md).

---

## Итоговая оценка

| Критерий | Оценка (после A–J) | Комментарий |
|----------|-------------------|-------------|
| Архитектура | 7/10 | Workflows вынесены; batch/interactive paths частично унифицированы |
| Реализация Downloader | 8/10 | Зрелая обёртка yt-dlp, history hooks, pause, continuedl |
| UX / интерактив | 9/10 | Mode 2, tri-state interactive, pause Linux + intra-video |
| История | 8/10 | HistoryStore, WAL; JSONL dual storage — design debt |
| Тесты | 8/10 | 95+ unit; regression doublesave, workflows, pause |
| Документация | 8/10 | README, manual, backlog синхронизированы |
| Поддерживаемость | 7/10 | `cli.py` ~394 строк; опционально — дальнейший split workflows |

**Общий вывод:** бэклог Maintenance 1.1 закрыт. Проект готов к эксплуатации; опциональный следующий этап — полная унификация playlist orchestrator'ов (GAP-CR-014) и deprecate JSONL (GAP-CR-009).

---

## Индекс гэпов (краткий)

| ID | Severity | Краткое название |
|----|----------|------------------|
| GAP-CR-001 | высокая | God Object cli.py |
| GAP-CR-002 | средняя | Циклические import |
| GAP-CR-003 | средняя | Дублирование interactive single video |
| GAP-CR-004 | средняя | Двойной extract_info |
| GAP-CR-005 | низкая | file_paths mapping в плейлисте |
| GAP-CR-006 | низкая | Заглушка retry decorator |
| GAP-CR-007 | низкая | Global _DB_PATH |
| GAP-CR-008 | низкая | fetch_download OR query |
| GAP-CR-009 | низкая | JSONL + SQLite dual storage |
| GAP-CR-010 | средняя | Playlist mode 2 не реализован |
| GAP-CR-011 | низкая | Мёртвый configure_filename_prefix |
| GAP-CR-012 | высокая | Pause не работает на Linux |
| GAP-CR-013 | высокая | interactive default vs config |
| GAP-CR-014 | средняя | Три orchestrator'а плейлиста |
| GAP-CR-015 | низкая | sys.exit vs typer.Exit |
| GAP-CR-016 | низкая | Расхождение типов config |
| GAP-CR-017 | низкая | logs в git |
| GAP-CR-018 | высокая | Нет regression test doublesave |
| GAP-CR-019 | средняя | Нет тестов workflows |
| GAP-CR-020 | низкая | Устаревшие dev docs |
| GAP-CR-021 | высокая | Нет cookies / anti-bot |
| GAP-CR-022 | низкая | Windows progress flush OSError |
| GAP-CR-023 | низкая | SQLite WAL |
| GAP-CR-024 | низкая | Нет ruff/CI lint |
| GAP-CR-025 | низкая | Широкие except Exception |
