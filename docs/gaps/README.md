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
| [code_review_2026-05-25.md](./code_review_2026-05-25.md) | Ревью | closed | 25 гэпов `GAP-CR-001` … `GAP-CR-025`; бэклог A–J закрыт |
| [doublesave_antibot_issue.md](./doublesave_antibot_issue.md) | Bug + ops | closed | Doublesave, cookies, Windows flush — исправлено |
| [intravideo_pause_todo.md](./intravideo_pause_todo.md) | Feature | done | Intra-video pause (BL-1001) |

---

## Бэклог

Сгруппированные задачи: **[../backlog.md](../backlog.md)** — все BL-* **done** (Maintenance 1.1).

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
