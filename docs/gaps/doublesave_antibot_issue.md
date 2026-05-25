# Duplicate downloads after interactive playlist + YouTube anti-bot

Status: closed (2026-05-25)  
Owner: @Ivan  
Last updated: 2026-05-25

## Summary

- **Doublesave:** при interactive unified mode плейлист скачивался дважды — **исправлено** (`skip_post_processing`, BL-601 regression test).
- **Anti-bot:** cookies и hints — **реализовано** (BL-501, BL-502, BL-1002).
- **Windows OSError [Errno 22]:** progress flush — **обход** (BL-302: `no_progress`, auto-retry).

## Symptoms (historical)

- После per-entry loop появлялся второй проход плейлиста с префиксом последнего файла (`11_...`).
- `UnavailableVideoError: Sign in to confirm you're not a bot` без cookies.
- `OSError [Errno 22] Invalid argument` при flush progress bar на Windows.

## Root cause (doublesave)

Control-flow fell through после interactive unified mode в generic playlist download path; `file_prefix` утекал из цикла.

## Fix implemented

| Проблема | Решение | Backlog |
|----------|---------|---------|
| Doublesave | `skip_post_processing` в `download_command.py` | BL-601 |
| Regression test | `tests/test_playlist_regression.py` | BL-601 |
| Cookies | `--cookies`, `--cookies-from-browser`, config, ENV | BL-501 |
| Anti-bot hints | `ytd/errors.py`, подсказки в CLI | BL-502 |
| Browser detect hint | `ytd/browser_detect.py` | BL-1002 |
| Windows flush | `no_progress`, auto-retry на OSError 22 | BL-302 |
| Playlist mode 2 | per-video interactive в цикле | BL-202 |
| Docs | README, manual troubleshooting | BL-502, BL-802 |

## Notes

- yt-dlp: `--cookies-from-browser`, `--cookies` проброшены через `DownloadOptions` / `build_ydl_opts`.
- При anti-bot по-прежнему нужны валидные cookies или снижение частоты запросов.

## Related

- [code_review_2026-05-25.md](./code_review_2026-05-25.md) — GAP-CR-018, GAP-CR-021, GAP-CR-022
- [backlog.md](../backlog.md)
