# Intra-video pause control

Status: implemented (BL-1001, 2026-05-25)
Priority: низкий
Owner: @Ivan
Created: 2025-10-27

## Summary
Возможность поставить на паузу загрузку **внутри** одного видео (не между видео в плейлисте, а во время скачивания текущего файла).

## Реализация

- CLI: `--intra-video-pause`
- Конфиг / ENV: `intra_video_pause: true`, `YTD_INTRA_VIDEO_PAUSE=1`
- Клавиши: `pause_key` / `resume_key` (по умолчанию `p` / `r`)
- Progress hook прерывает загрузку через `IntraVideoPauseRequested`
- После `r` загрузка перезапускается с `continuedl=True` (частичный файл сохраняется)

## Ограничения

- Не «заморозка» HTTP-сессии, а прерывание yt-dlp + resume с partial file
- Для mux audio+video поведение resume зависит от yt-dlp и формата
- Требуется интерактивный TTY для клавиш `p` / `r`

## References

- `ytd/pause.py` — `PauseController(intra_video=True)`
- `ytd/downloader.py` — progress hook + `_download_with_retries`
- yt-dlp: [External downloaders](https://github.com/yt-dlp/yt-dlp#external-downloaders) (альтернатива для native pause — не реализовано)
