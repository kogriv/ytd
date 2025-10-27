# Duplicate downloads after interactive playlist + YouTube anti-bot

Status: open
Owner: @Ivan
Last updated: 2025-10-27

## Summary
- When running an interactive playlist download with unified settings, the app re-downloads the whole playlist again using the last file prefix (e.g., `11_`), producing duplicates.
- Occasionally, YouTube returns "Sign in to confirm you’re not a bot" which stops some items without cookies.
- Windows-only OSError [Errno 22] Invalid argument appeared in logs around progress printing/flushing; likely a console stream quirk.

## Symptoms
- After the interactive per-entry loop completes (01_..11_), the log shows a second playlist start and files named with the last prefix (e.g., `11_...`) appear for earlier items.
- Errors in `logs/ytd.log`:
  - `UnavailableVideoError: Sign in to confirm you’re not a bot`
  - `OSError [Errno 22] Invalid argument` during stream flush.

## Root cause
- Control-flow fell through after interactive playlist unified mode. After downloading entries one-by-one, the code continued into the generic download path that treats the URL as a full playlist, causing a second pass. The outer `file_prefix` variable retained the last value from the per-entry loop (e.g., `"11_"`).

## Reproduction
1) Put a playlist URL into `urls.local.txt`.
2) Run interactive playlist mode, choose unified settings, confirm.
3) Observe: after the first pass, a second playlist processing starts and creates duplicates with the last prefix.

## Fix implemented
- Added a scoped flag `skip_post_processing` in `ytd/cli.py` to short-circuit the outer loop after the per-entry interactive run and reset `file_prefix` to avoid scope leakage.
- Removed the invalid `continue` that broke the `if/elif` chain.

## Remaining TODOs
- [ ] Add an interactive "per-item" settings mode (mode 2).
- [ ] Anti-bot mitigation: allow passing browser cookies to yt-dlp.
  - [ ] CLI flag: `--cookies-from-browser chrome|edge|firefox` and/or `--cookies FILE`
  - [ ] Config keys mirroring these options.
  - [ ] Detect Windows default browser and suggest a hint when anti-bot is detected.
- [ ] Consider setting `noprogress=True` for certain terminals to avoid flush issues, or catch/ignore flush OSErrors on Windows.
- [ ] Add a regression test that ensures no second download is triggered after interactive playlist unified mode.
- [ ] Document anti-bot troubleshooting in README/manual (cookies, rate limiting, retries).

## Notes
- yt-dlp supports: `--cookies-from-browser <br>` and `--cookies <file>`. We can plumb these through `DownloadOptions` and `Downloader`.
- The current fix stops duplicates; future enhancements above will reduce auth/anti-bot friction and improve UX.
