# Gap-документы (docs/gaps)

Каталог известных архитектурных проблем, багов, ограничений и отложенных фич проекта **ytd**.

---

## Как пользоваться

1. **Новая проблема** — создайте файл `docs/gaps/<краткое_имя>.md` по образцу существующих (Summary, Symptoms, Root cause, Fix, TODO).
2. **Системное ревью** — крупные аудиты фиксируются отдельным документом с идентификаторами гэпов `GAP-*`.
3. **Задачи на исправление** — ведутся в [backlog.md](../backlog.md) с ID `BL-*` и ссылкой на gap.

---

## Документы

| Документ | Тип | Status | Описание |
|----------|-----|--------|----------|
| [tech_debt_2026-08-31.md](./tech_debt_2026-08-31.md) | Ревью долга | closed | 6 гэпов `GAP-CR-035` … `GAP-CR-040` + перенесённый `GAP-CR-009`; спринт L закрыт полностью |
| [code_review_2026-08-31.md](./code_review_2026-08-31.md) | Ревью | closed | 9 гэпов `GAP-CR-026` … `GAP-CR-034`; спринт K (Maintenance 1.2) закрыт полностью |
| [code_review_2026-05-25.md](./code_review_2026-05-25.md) | Ревью | closed | 25 гэпов `GAP-CR-001` … `GAP-CR-025`; бэклог A–J закрыт |
| [doublesave_antibot_issue.md](./doublesave_antibot_issue.md) | Bug + ops | closed | Doublesave, cookies, Windows flush — исправлено |
| [intravideo_pause_todo.md](./intravideo_pause_todo.md) | Feature | done | Intra-video pause (BL-1001) |

Сопутствующие документы вне каталога: [анализ проекта 2026-08-31](../analysis_2026-08-31.md), [дизайн исправлений 2026-08-31](../design_2026-08-31.md), [дизайн исправлений техдолга](../design_tech_debt_2026-08-31.md).

---

## Бэклог

Сгруппированные задачи: **[../backlog.md](../backlog.md)** — все BL-* **done**: Maintenance 1.1, 1.2 и 1.3.

---

## Индекс гэпов ревью техдолга 2026-08-31

Полные описания — в [tech_debt_2026-08-31.md](./tech_debt_2026-08-31.md).

| ID | Severity | Status | Краткое название |
|----|----------|--------|------------------|
| GAP-CR-035 | средняя | fixed | Висящая запись `in_progress` (плейлисты и не-YouTube одиночные) |
| GAP-CR-036 | средняя | fixed | Гонка за клавиатурным вводом при возобновлении |
| GAP-CR-037 | низкая | fixed | Нет проверки типов в CI |
| GAP-CR-038 | низкая | fixed | Нет метрики покрытия тестами |
| GAP-CR-039 | средняя | fixed | `main` не защищён обязательными проверками |
| GAP-CR-040 | низкая | fixed | Интеграционные тесты не выполняются нигде |

`GAP-CR-009` (JSONL + SQLite) перенесён из ревью 2026-05-25 и закрыт в BL-1207: JSONL стал опциональным и выключен по умолчанию.

---

## Индекс гэпов ревью 2026-08-31

Полные описания — в [code_review_2026-08-31.md](./code_review_2026-08-31.md).

| ID | Severity | Status | Краткое название |
|----|----------|--------|------------------|
| GAP-CR-026 | высокая | fixed | `wait_if_paused` вешает процесс на Windows без TTY |
| GAP-CR-027 | средняя | fixed | Тест импорта истории завязан на POSIX-разделитель |
| GAP-CR-028 | средняя | fixed | CI не покрывает Windows |
| GAP-CR-029 | средняя | fixed | `execute_download` — новый монолит (999 строк) |
| GAP-CR-030 | низкая | fixed | Мёртвая ветка повторного опроса истории |
| GAP-CR-031 | средняя | fixed | `urls.local.txt` с личными ссылками в репозитории |
| GAP-CR-032 | низкая | fixed | README описывает несуществующие каталоги |
| GAP-CR-033 | низкая | fixed | `devplan*.md` устарели относительно реализации |
| GAP-CR-034 | средняя | fixed | `typer.Exit` гасится широким `except` (найден при BL-1105) |

---

## Индекс гэпов ревью 2026-05-25

Полные описания — в [code_review_2026-05-25.md](./code_review_2026-05-25.md).

| ID | Severity | Status | Краткое название |
|----|----------|--------|------------------|
| GAP-CR-001 | высокая | mitigated | God Object `cli.py` → workflows |
| GAP-CR-002 | средняя | fixed | Циклические import |
| GAP-CR-003 | средняя | fixed | Дублирование interactive single video |
| GAP-CR-004 | средняя | fixed | Двойной `extract_info` |
| GAP-CR-005 | низкая | fixed | `file_paths` mapping в плейлисте |
| GAP-CR-006 | низкая | fixed | Заглушка `retry` decorator |
| GAP-CR-007 | низкая | fixed | Global `_DB_PATH` → HistoryStore |
| GAP-CR-008 | низкая | fixed | `fetch_download` OR query |
| GAP-CR-009 | низкая | documented | JSONL + SQLite (design debt) |
| GAP-CR-010 | средняя | fixed | Playlist mode 2 |
| GAP-CR-011 | низкая | fixed | `configure_filename_prefix` / BL-102 |
| GAP-CR-012 | высокая | fixed | Pause на Linux |
| GAP-CR-013 | высокая | fixed | `interactive` default vs config |
| GAP-CR-014 | средняя | mitigated | Три orchestrator'а плейлиста |
| GAP-CR-015 | низкая | fixed | `sys.exit` vs `typer.Exit` |
| GAP-CR-016 | низкая | fixed | Расхождение типов config |
| GAP-CR-017 | низкая | fixed | Logs в git |
| GAP-CR-018 | высокая | fixed | Regression test doublesave |
| GAP-CR-019 | средняя | fixed | Тесты workflows (базовое покрытие) |
| GAP-CR-020 | низкая | fixed | Устаревшие dev docs |
| GAP-CR-021 | высокая | fixed | Cookies / anti-bot |
| GAP-CR-022 | низкая | fixed | Windows progress flush |
| GAP-CR-023 | низкая | fixed | SQLite WAL |
| GAP-CR-024 | низкая | fixed | ruff / CI lint |
| GAP-CR-025 | низкая | fixed | Широкие `except Exception` (logging) |
