# Development Roadmap — ytd

> **Comprehensive development plan and feature roadmap for ytd YouTube downloader**
> 
> Current version: Maintenance 1.2 (August 31, 2026); MVP 1.0 — October 27, 2025  
> Last updated: August 31, 2026 (BL-1109: state sections synced with `main`)

---

## Table of Contents

1. [Current State Analysis](#current-state-analysis)
2. [Architecture Overview](#architecture-overview)
3. [Development Branches](#development-branches)
4. [Priority Matrix](#priority-matrix)
5. [Detailed Feature Roadmap](#detailed-feature-roadmap)
6. [Technical Debt & Refactoring](#technical-debt--refactoring)
7. [Long-term Vision](#long-term-vision)

---

## Current State Analysis

### ✅ Implemented Features (MVP 1.0 + Maintenance 1.1 and 1.2)

**Core Functionality:**
- Single video/audio downloads with quality presets
- Playlist batch downloading (sequential processing)
- Interactive mode for single videos with quality selection
- Interactive mode for playlists: unified settings and per-video setup
- File naming customization (prefix, suffix, full override)
- Duplicate detection by video ID with overwrite control
- Smart quality fallback strategies ("economy" and "rich" modes)
- Progress indicators with colored terminal output
- Configuration via YAML files and environment variables
- Metadata in JSONL plus a SQLite download journal (`ytd history`)
- URL batch processing from files
- Subtitle downloads, cookies support and anti-bot hints
- Resume: continue a playlist, pause between videos and inside a file
- Comprehensive Russian documentation

**Technical Implementation:**
- Python 3.14, dependencies and environment managed by uv
- yt-dlp backend for video extraction
- Typer CLI framework with rich formatting; orchestration in `ytd/workflows/`
- pytest test suite (121 tests, 2 of them integration on demand)
- Download scenarios as separate modules sharing one signature
- Retry logic with exponential backoff and a network recovery dialog
- Cross-platform support (Windows, Linux, macOS); CI on ubuntu and windows + ruff

### 🔍 Current Limitations

1. **Interactive Mode:**
   - No preview of first N filenames before batch download
   - No "apply to remaining" option in per-video mode
   - Individual entries cannot be cancelled once a playlist starts

2. **Performance:**
   - Sequential-only playlist processing (no parallelism)
   - Resume restarts yt-dlp with `continuedl` rather than holding the connection
   - No bandwidth limiting

3. **Content Features:**
   - No thumbnail extraction
   - No chapter/segment metadata extraction
   - No comment/description archiving
   - No post-processing beyond what yt-dlp performs

4. **UX/UI:**
   - No download queue management
   - No real-time progress bars (only hooks)
   - No web UI or GUI
   - No notification system

5. **Advanced Features:**
   - No channel/user full archive mode
   - No scheduled downloads
   - No post-processing automation (custom ffmpeg filters)
   - No content filtering (duration, view count, etc.)
   - No integration with media libraries (Plex, Jellyfin)

---

## Architecture Overview

### Current Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│                    (ytd/cli.py - Typer)                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   download   │  │     info     │  │   history    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Business Logic Layer                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  workflows   │  │  Downloader  │  │    Config    │      │
│  │ (scenarios)  │  │   (wrapper)  │  │  + history   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                    Infrastructure Layer                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   yt-dlp     │  │  Filesystem  │  │   Logging    │      │
│  │   (API)      │  │   (utils)    │  │   (setup)    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

### Proposed Extensions

```
New layers to be added:
┌─────────────────────────────────────────────────────────────┐
│                     Presentation Layer (Future)              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Web UI     │  │   REST API   │  │   TUI/GUI    │      │
│  │  (FastAPI)   │  │  (FastAPI)   │  │  (Textual)   │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Queue & Workers Layer (Future)           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │  Task Queue  │  │ Worker Pool  │  │  Scheduler   │      │
│  │   (asyncio)  │  │ (concurrent) │  │  (APScheduler)│     │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                     Storage Layer (Future)                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Database   │  │    Cache     │  │   Reports    │      │
│  │  (SQLite)    │  │   (Redis?)   │  │ (CSV/Excel)  │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
```

---

## Development Branches

### 🌿 Branch Strategy

**Main Development Tracks:**

1. **Core Functionality** — extending download capabilities
2. **UX/UI Enhancements** — improving user experience
3. **Performance & Scale** — optimization and parallelism
4. **Content Features** — metadata, subtitles, chapters
5. **Integration & Distribution** — packaging, APIs, integrations
6. **Quality & Maintenance** — testing, refactoring, documentation

---

## Priority Matrix

```
Impact vs Effort Matrix:

High Impact │ 2. Per-video Mode    │ 1. Parallel Downloads  │
           │ 3. Resume Downloads  │ 5. Web UI              │
           │ 4. Subtitles/Thumbs  │ 8. Channel Archive     │
           │─────────────────────┼────────────────────────│
           │ 7. TUI Progress      │ 9. REST API            │
Low Impact │ 10. Notifications    │ 11. Media Library Sync │
           └─────────────────────┴────────────────────────┘
             Low Effort               High Effort

Priority Order (by quarter):
Q1 2026: 2, 3, 4, 7
Q2 2026: 1, 6, 12
Q3 2026: 5, 8, 13
Q4 2026: 9, 14, 15
```

---

## Detailed Feature Roadmap

### Phase 1: Interactive Mode Completion (Q1 2026)

#### 1.1 Per-Video Interactive Mode for Playlists
**Status:** partially done (BL-202): base per-video mode shipped; "apply to remaining" and preview remain  
**Priority:** HIGH  
**Effort:** MEDIUM  
**Impact:** HIGH

**Description:**
Complete the interactive playlist mode by implementing per-video quality selection with "apply to remaining" option.

**Implementation Details:**
- Show video info (title, duration, thumbnail) for each entry
- Allow individual quality selection
- Add "Apply to all remaining" checkbox
- Add "Skip this video" option
- Show progress: "Video 5 of 23"
- Support bulk actions: "Skip remaining", "Use same settings for remaining"

**Files to modify:**
- `ytd/interactive.py` — add per-video dialog functions
- `ytd/cli.py` — implement per-video mode flow (line 290)

**Acceptance Criteria:**
- User can select quality for each video individually
- User can apply settings to remaining videos
- User can skip individual videos
- Progress counter shows current position
- Dry-run mode shows all decisions before download

**Test Coverage:**
- Unit tests for new interactive functions
- Integration test with mock playlist (3-5 entries)
- Manual test with real playlist

---

#### 1.2 Filename Preview Feature
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** MEDIUM

**Description:**
Show preview of first 3-5 filenames before starting batch download to confirm naming scheme.

**Implementation Details:**
- Generate example filenames using actual video metadata
- Show sanitized names with prefixes/suffixes applied
- Highlight potential conflicts (duplicate names)
- Add confirmation prompt: "Proceed with download? [Y/n]"
- Option to go back and adjust settings

**Files to modify:**
- `ytd/interactive.py` — add preview function
- `ytd/cli.py` — call preview before download loop

**Acceptance Criteria:**
- Preview shows 3-5 actual filenames
- Sanitization and numbering visible
- User can cancel and adjust settings
- Duplicate warnings displayed

---

#### 1.3 Enhanced Duplicate Detection
**Status:** IMPROVEMENT  
**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** MEDIUM

**Description:**
Improve existing duplicate detection with fuzzy matching and partial file detection.

**Current Implementation:**
- Exact substring match on `[VIDEO_ID]`
- Simple overwrite prompt

**Improvements:**
- Detect partial downloads (incomplete files)
- Fuzzy match on title similarity (90%+ threshold)
- Show file size and date of existing file
- Options: Overwrite, Skip, Rename, Resume (if partial)
- Batch options: "Always overwrite", "Always skip", "Always rename"

**Files to modify:**
- `ytd/utils.py` — enhance `find_existing_files()` function
- `ytd/interactive.py` — improve overwrite dialogs

**Acceptance Criteria:**
- Partial files detected
- User sees details of existing file
- Multiple resolution strategies offered
- Batch mode reduces prompts

---

### Phase 2: Performance & Scalability (Q2 2026)

#### 2.1 Parallel Downloads
**Status:** NEW  
**Priority:** HIGH  
**Effort:** HIGH  
**Impact:** HIGH

**Description:**
Implement concurrent downloads with configurable worker pool for playlists and URL lists.

**Technical Approach:**
- Use `concurrent.futures.ThreadPoolExecutor` for I/O-bound yt-dlp calls
- Configurable max workers (default: 3, max: 10)
- Progress tracking for all active downloads
- Error isolation (one failure doesn't stop others)
- Rate limiting to avoid IP bans

**Implementation Details:**
```python
# New module: ytd/parallel.py
class ParallelDownloader:
    def __init__(self, max_workers: int = 3, rate_limit: float = 1.0):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.rate_limiter = RateLimiter(rate_limit)
    
    def download_batch(self, urls: list[str], options: DownloadOptions):
        futures = []
        for url in urls:
            future = self.executor.submit(self._download_with_rate_limit, url, options)
            futures.append(future)
        
        # Wait and collect results
        results = []
        for future in as_completed(futures):
            results.append(future.result())
        return results
```

**Configuration:**
```yaml
# ytd.yaml
parallel:
  enabled: true
  max_workers: 3
  rate_limit: 1.0  # seconds between starts
```

**Files to add:**
- `ytd/parallel.py` — parallel downloader implementation
- `ytd/rate_limiter.py` — simple rate limiting utility

**Files to modify:**
- `ytd/cli.py` — add `--parallel` flag and worker count option
- `ytd/config.py` — add parallel settings
- `ytd/types.py` — extend config dataclass

**Acceptance Criteria:**
- Multiple videos download simultaneously
- Progress tracked for each download
- Error in one download doesn't affect others
- Rate limiting prevents bans
- Resource usage stays reasonable
- Tests with 10+ video playlist

---

#### 2.2 Download Resume Capability
**Status:** NEW  
**Priority:** HIGH  
**Effort:** MEDIUM  
**Impact:** HIGH

**Description:**
Support resuming interrupted downloads using yt-dlp's built-in resume capabilities.

**Implementation Details:**
- Store download state in `.ytd_state/` directory
- Track partial files with `.part` extension
- Detect and resume partial downloads
- Clean up state files after successful download
- Handle resume failures gracefully

**State File Format (JSON):**
```json
{
  "video_id": "abc123",
  "url": "https://...",
  "partial_file": "path/to/video.part",
  "bytes_downloaded": 12345678,
  "total_bytes": 98765432,
  "format": "bestvideo+bestaudio",
  "started_at": "2026-01-15T10:30:00Z",
  "last_updated": "2026-01-15T10:35:00Z"
}
```

**Files to add:**
- `ytd/resume.py` — resume state management

**Files to modify:**
- `ytd/downloader.py` — integrate resume logic
- `ytd/utils.py` — add state file utilities

**Acceptance Criteria:**
- Interrupted downloads resume from last position
- State cleaned up on completion
- Works with parallel downloads
- Manual resume command: `ytd resume`

---

#### 2.3 Bandwidth Limiting
**Status:** NEW  
**Priority:** LOW  
**Effort:** LOW  
**Impact:** MEDIUM

**Description:**
Add bandwidth limiting to prevent network saturation.

**Implementation Details:**
- Use yt-dlp's `ratelimit` option
- CLI flag: `--rate-limit 1M` (1 MB/s)
- Config file setting: `rate_limit: "1M"`
- Support units: K, M, G (bytes per second)

**Files to modify:**
- `ytd/downloader.py` — add ratelimit to ydl_opts
- `ytd/cli.py` — add CLI flag
- `ytd/types.py` — add rate_limit field

**Acceptance Criteria:**
- Download speed respects limit
- Works with parallel downloads
- Units parsed correctly

---

### Phase 3: Content Features (Q2 2026)

#### 3.1 Subtitle Download
**Status:** PARTIAL (config exists, not exposed)  
**Priority:** HIGH  
**Effort:** LOW  
**Impact:** HIGH

**Description:**
Fully implement subtitle download with format options and auto-translation.

**Current State:**
- `subtitles` field exists in config
- Not exposed in interactive mode
- Not tested

**Enhancements:**
- CLI: `--subtitles en,ru --subtitle-format srt`
- Interactive mode: checkbox "Download subtitles"
- Auto-translation: `--subtitle-translate ru` (translate to Russian)
- Embed subtitles in video: `--embed-subs`
- Download only: keep separate .srt/.vtt files

**Files to modify:**
- `ytd/downloader.py` — configure subtitle options properly
- `ytd/interactive.py` — add subtitle dialog
- `ytd/cli.py` — expose subtitle flags

**Acceptance Criteria:**
- Subtitles download in specified languages
- Auto-translation works
- Embedding works for MP4
- Separate files option works

---

#### 3.2 Thumbnail Extraction
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** MEDIUM

**Description:**
Download and optionally embed video thumbnails.

**Implementation:**
- CLI: `--thumbnail --embed-thumbnail`
- Interactive: checkbox option
- Save as separate JPG/PNG file
- Embed in MP4/M4A metadata
- Multiple resolution options

**yt-dlp options:**
```python
'writethumbnail': True,
'embedthumbnail': True,  # requires AtomicParsley for m4a
```

**Files to modify:**
- `ytd/downloader.py` — add thumbnail options
- `ytd/interactive.py` — add thumbnail checkbox
- `ytd/types.py` — add thumbnail fields

**Acceptance Criteria:**
- Thumbnail saved as separate file
- Thumbnail embedded in metadata
- Works with audio-only downloads

---

#### 3.3 Chapter/Segment Extraction
**Status:** NEW  
**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** LOW

**Description:**
Extract and save video chapters/segments as separate files or metadata.

**Features:**
- Save chapter list to JSON file
- Split video by chapters (optional)
- Preserve chapter metadata in downloaded file

**Use Cases:**
- Podcasts with episode segments
- Educational content with topic sections
- Music albums with track markers

**Files to add:**
- `ytd/chapters.py` — chapter extraction utilities

**Acceptance Criteria:**
- Chapter metadata saved
- Optional video splitting by chapters
- Chapter info in progress output

---

#### 3.4 Comments & Description Archiving
**Status:** NEW  
**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** LOW

**Description:**
Archive video description, comments, and other metadata for research/archival purposes.

**Features:**
- `--archive-metadata` flag
- Save to structured JSON or SQLite
- Include: description, comments (top N), tags, timestamps
- Optional: full comment threads with replies

**Files to add:**
- `ytd/archiver.py` — metadata archiving

**Acceptance Criteria:**
- Full description saved
- Top N comments saved
- Data structured and searchable

---

### Phase 4: UX/UI Improvements (Q1 2026)

#### 4.1 Rich Progress Bars
**Status:** IMPROVEMENT  
**Priority:** HIGH  
**Effort:** LOW  
**Impact:** HIGH

**Description:**
Replace current progress hooks with rich progress bars using `rich.progress`.

**Current State:**
- Basic progress hooks (DEBUG level only)
- Minimal visual feedback

**Improvements:**
- Real-time progress bars with percentage, speed, ETA
- Multiple concurrent progress bars for parallel downloads
- Color-coded status (downloading, processing, finished, error)
- Overall playlist progress + individual file progress

**Implementation:**
```python
from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn

with Progress(
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    TextColumn("•"),
    TextColumn("[cyan]{task.completed}/{task.total}"),
) as progress:
    task = progress.add_task("Downloading video...", total=100)
    # Update progress in hook
```

**Files to modify:**
- `ytd/downloader.py` — integrate rich.progress
- `ytd/cli.py` — manage progress display

**Acceptance Criteria:**
- Smooth progress bars visible
- Multiple downloads show multiple bars
- Speed and ETA displayed
- Works in both verbose and quiet modes

---

#### 4.2 TUI (Text User Interface)
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** HIGH  
**Impact:** MEDIUM

**Description:**
Full-featured TUI using `textual` for interactive browsing and downloading.

**Features:**
- Search YouTube directly from TUI
- Browse search results with thumbnails (ASCII art)
- Queue management (add, remove, reorder)
- Live progress monitoring
- Download history
- Settings panel

**Technology:**
- `textual` — modern TUI framework
- `rich` for rendering
- Async architecture

**Screens:**
```
┌────────────────────────────────────────────────┐
│ ytd — YouTube Downloader TUI           [v1.0] │
├────────────────────────────────────────────────┤
│  Search: [____________________________]  [Go]  │
├────────────────────────────────────────────────┤
│  Queue (3 items):                              │
│  1. Video Title #1          [1080p] [▶ Ready] │
│  2. Video Title #2           [720p] [⏸ Paused]│
│  3. Playlist (45 videos)    [best]  [⏳ Active]│
├────────────────────────────────────────────────┤
│  Active Downloads:                             │
│  ┌─ Video Title #3 ───────────────┐            │
│  │ [████████░░░░░░░░░░] 45% 2.1MB/s│            │
│  └────────────────────────────────┘            │
├────────────────────────────────────────────────┤
│  [Add URL] [Settings] [History] [Quit]        │
└────────────────────────────────────────────────┘
```

**Files to add:**
- `ytd/tui/` — new subpackage
- `ytd/tui/app.py` — main TUI application
- `ytd/tui/screens/` — various screens
- `ytd/tui/widgets/` — custom widgets

**New command:**
```bash
ytd tui  # Launch TUI
```

**Acceptance Criteria:**
- TUI launches without errors
- Basic navigation works (keyboard + mouse)
- Queue management functional
- Downloads start from TUI
- Progress visible in real-time

---

#### 4.3 Desktop Notifications
**Status:** NEW  
**Priority:** LOW  
**Effort:** LOW  
**Impact:** LOW

**Description:**
Send desktop notifications on download completion/failure.

**Implementation:**
- Use `plyer` for cross-platform notifications
- Configure: `--notify` or `notify: true` in config
- Events: download complete, download failed, playlist complete

**Files to add:**
- `ytd/notifications.py`

**Acceptance Criteria:**
- Notifications appear on completion
- Cross-platform (Windows, Linux, macOS)
- Can be disabled

---

### Phase 5: Advanced Features (Q3 2026)

#### 5.1 Channel/User Archive Mode
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** HIGH  
**Impact:** MEDIUM

**Description:**
Download entire channels or user uploads with incremental updates.

**Features:**
- `ytd archive @username` — archive entire channel
- `ytd update @username` — download only new videos
- Store state in database (SQLite)
- Filter by date, view count, duration
- Resume interrupted archives
- Scheduled updates (cron/systemd timer)

**Database Schema:**
```sql
CREATE TABLE channels (
    channel_id TEXT PRIMARY KEY,
    channel_name TEXT,
    last_checked TIMESTAMP,
    video_count INTEGER
);

CREATE TABLE archived_videos (
    video_id TEXT PRIMARY KEY,
    channel_id TEXT,
    title TEXT,
    uploaded_at TIMESTAMP,
    downloaded_at TIMESTAMP,
    file_path TEXT,
    FOREIGN KEY (channel_id) REFERENCES channels(channel_id)
);
```

**Commands:**
```bash
ytd archive @channelname           # Initial archive
ytd update @channelname            # Incremental update
ytd archive status @channelname    # Show archive info
ytd archive list                   # List all archives
```

**Files to add:**
- `ytd/archive/` — new subpackage
- `ytd/archive/db.py` — SQLite database
- `ytd/archive/manager.py` — archive manager

**Acceptance Criteria:**
- Full channel download works
- Incremental updates download only new videos
- State persisted across runs
- Filtering options work

---

#### 5.2 Scheduled Downloads
**Status:** NEW  
**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** LOW

**Description:**
Schedule downloads for specific times (off-peak hours, etc.).

**Implementation:**
- Use `APScheduler` for scheduling
- CLI: `ytd schedule URL --at "02:00"` or `--in "2h"`
- Daemon mode: `ytd daemon start`
- List scheduled: `ytd schedule list`
- Cancel: `ytd schedule cancel <id>`

**Files to add:**
- `ytd/scheduler.py`
- `ytd/daemon.py`

**Acceptance Criteria:**
- Downloads execute at scheduled time
- Daemon runs in background
- Scheduled jobs persist across restarts

---

#### 5.3 Post-Processing Automation
**Status:** NEW  
**Priority:** LOW  
**Effort:** HIGH  
**Impact:** LOW

**Description:**
Custom ffmpeg filters and post-processing workflows.

**Features:**
- Custom ffmpeg filters: `--ffmpeg-args "-vf scale=1280:-1"`
- Trim video: `--trim 00:30-05:00`
- Extract audio segment
- Watermark removal (where legal)
- Auto-convert to specific formats
- Post-processing scripts/hooks

**Config Example:**
```yaml
post_processing:
  - name: "Convert to H.265"
    enabled: false
    ffmpeg_args: "-c:v libx265 -crf 28"
  - name: "Normalize Audio"
    enabled: true
    ffmpeg_args: "-af loudnorm"
```

**Files to add:**
- `ytd/postprocess.py`

**Acceptance Criteria:**
- Custom ffmpeg filters applied
- Multiple processing steps chain
- Conditional processing based on file properties

---

### Phase 6: Integration & Distribution (Q3-Q4 2026)

#### 6.1 Web UI
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** HIGH  
**Impact:** HIGH

**Description:**
Web-based interface for remote management and downloading.

**Technology Stack:**
- Backend: FastAPI
- Frontend: Vue.js 3 or React
- Real-time: WebSockets for progress
- Authentication: Optional (basic auth or OAuth)

**Features:**
- Upload URL or paste link
- Visual quality selection
- Queue management
- Progress monitoring
- Download history
- Settings panel
- Mobile-responsive

**Architecture:**
```
┌──────────────┐      WebSocket       ┌──────────────┐
│   Browser    │ ◄──────────────────► │   FastAPI    │
│  (Vue.js)    │      HTTP/REST       │   Backend    │
└──────────────┘                      └──────────────┘
                                             │
                                             ▼
                                      ┌──────────────┐
                                      │  ytd Core    │
                                      │  (library)   │
                                      └──────────────┘
```

**Files to add:**
- `ytd_web/` — new package
- `ytd_web/api.py` — FastAPI routes
- `ytd_web/static/` — frontend assets
- `ytd_web/websockets.py` — real-time updates

**New command:**
```bash
ytd serve --host 0.0.0.0 --port 8000
```

**Acceptance Criteria:**
- Web UI accessible in browser
- Downloads start from web interface
- Real-time progress updates
- Mobile-friendly design

---

#### 6.2 REST API
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** MEDIUM  
**Impact:** MEDIUM

**Description:**
RESTful API for integration with other tools and automation.

**Endpoints:**
```
POST   /api/downloads           # Start download
GET    /api/downloads           # List downloads
GET    /api/downloads/{id}      # Get download status
DELETE /api/downloads/{id}      # Cancel download
POST   /api/info                # Get video info
GET    /api/config              # Get current config
PUT    /api/config              # Update config
GET    /api/health              # Health check
```

**Example Request:**
```bash
curl -X POST http://localhost:8000/api/downloads \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://youtube.com/watch?v=...",
    "quality": "1080p",
    "output": "/downloads"
  }'
```

**Example Response:**
```json
{
  "download_id": "uuid-here",
  "status": "queued",
  "url": "https://youtube.com/watch?v=...",
  "title": "Video Title",
  "estimated_size": "125MB"
}
```

**Files to add:**
- `ytd/api/` — new subpackage
- `ytd/api/routes.py` — API endpoints
- `ytd/api/models.py` — Pydantic models

**Acceptance Criteria:**
- API endpoints respond correctly
- OpenAPI/Swagger documentation generated
- Authentication optional but supported
- Rate limiting implemented

---

#### 6.3 Docker Image
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** MEDIUM

**Description:**
Official Docker image for easy deployment.

**Dockerfile:**
```dockerfile
FROM python:3.14-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e .

VOLUME ["/downloads", "/config"]
EXPOSE 8000

ENTRYPOINT ["ytd"]
CMD ["serve", "--host", "0.0.0.0"]
```

**Docker Compose:**
```yaml
version: '3.8'
services:
  ytd:
    image: kogriv/ytd:latest
    ports:
      - "8000:8000"
    volumes:
      - ./downloads:/downloads
      - ./config:/config
    environment:
      - YTD_OUTPUT=/downloads
```

**Files to add:**
- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`

**Acceptance Criteria:**
- Docker image builds successfully
- Container runs ytd
- Volumes persist downloads
- Multi-arch support (amd64, arm64)

---

#### 6.4 Executable Builds
**Status:** NEW  
**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** MEDIUM

**Description:**
Standalone executables for Windows, Linux, macOS using PyInstaller.

**Build Process:**
```bash
pyinstaller --onefile --name ytd ytd/cli.py
```

**Distribution:**
- GitHub Releases with binaries
- Auto-builds via GitHub Actions
- Code signing (Windows/macOS)

**Files to add:**
- `ytd.spec` — PyInstaller spec file
- `.github/workflows/build.yml` — CI/CD for builds

**Acceptance Criteria:**
- Executables work without Python installed
- All platforms supported
- Reasonable file size (<50MB)

---

#### 6.5 Media Library Integration
**Status:** NEW  
**Priority:** LOW  
**Effort:** HIGH  
**Impact:** LOW

**Description:**
Integrate with Plex, Jellyfin, Kodi for automatic library updates.

**Features:**
- Auto-scan library after download
- Match video metadata to library format
- Organize by series/season (for show archives)
- Generate .nfo files for Kodi

**Files to add:**
- `ytd/integrations/` — integration plugins
- `ytd/integrations/plex.py`
- `ytd/integrations/jellyfin.py`

**Acceptance Criteria:**
- Downloads trigger library scan
- Metadata correctly formatted
- Works with popular media servers

---

### Phase 7: Quality & Maintenance (Ongoing)

#### 7.1 Expanded Test Coverage
**Status:** ONGOING  
**Priority:** HIGH  
**Effort:** MEDIUM  
**Impact:** HIGH

**Current Coverage:** ~60% (estimated)

**Goals:**
- 90%+ code coverage
- Integration tests for all major features
- Performance benchmarks
- Regression test suite

**Test Types:**
- Unit tests (existing)
- Integration tests (partial)
- End-to-end tests (CLI smoke tests)
- Performance tests (large playlists)
- Security tests (input validation)

**Files to expand:**
- `tests/` — all test modules

---

#### 7.2 Performance Benchmarking
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** MEDIUM  
**Impact:** MEDIUM

**Metrics to Track:**
- Download speed vs yt-dlp baseline
- Memory usage during parallel downloads
- Startup time
- Playlist processing time

**Tools:**
- `pytest-benchmark` for benchmarks
- `memory_profiler` for memory analysis
- GitHub Actions for CI benchmarks

**Files to add:**
- `tests/benchmarks/` — benchmark suite
- `.github/workflows/benchmark.yml`

---

#### 7.3 Security Audit
**Status:** NEW  
**Priority:** MEDIUM  
**Effort:** LOW  
**Impact:** HIGH

**Areas to Review:**
- Input validation (URLs, file paths)
- Shell injection risks (ffmpeg args)
- Path traversal vulnerabilities
- Dependency vulnerabilities (Dependabot)

**Tools:**
- `bandit` for Python security linting
- `safety` for dependency checks
- Manual code review

**Acceptance Criteria:**
- No high-severity issues
- Input validation comprehensive
- Dependencies up to date

---

#### 7.4 Documentation Expansion
**Status:** ONGOING  
**Priority:** HIGH  
**Effort:** LOW  
**Impact:** HIGH

**Documents to Add:**
- API documentation (Sphinx or MkDocs)
- Contributing guidelines
- Code of conduct
- Troubleshooting guide
- FAQ
- Video tutorials (optional)

**Files to add:**
- `docs/api/` — API reference
- `docs/contributing.md`
- `docs/troubleshooting.md`
- `docs/faq.md`

---

#### 7.5 Internationalization (i18n)
**Status:** NEW  
**Priority:** LOW  
**Effort:** MEDIUM  
**Impact:** MEDIUM

**Description:**
Support multiple languages beyond Russian/English.

**Implementation:**
- Use `gettext` for translations
- Extract strings to `.po` files
- Support language selection: `--lang en`

**Target Languages:**
- English (en)
- Russian (ru) — current
- Spanish (es)
- German (de)
- French (fr)

**Files to add:**
- `ytd/locale/` — translation files

---

## Technical Debt & Refactoring

### Current Technical Debt

1. **Two sources of truth (GAP-CR-009):** JSONL and SQLite coexist; roles are
   documented in `docs/usage.md`, but the data model stays dual
2. **No async/await:** All operations synchronous
3. **No type checking in CI** (mypy/pyright not wired) and no coverage metric
4. **Integration tests need network** and are opt-in via `YTD_IT_URL`
5. **`main` is not protected** by required checks — CI reports but does not block
6. **Limited error handling:** Some edge cases still lack test coverage

Closed in Maintenance 1.1 and 1.2: the `cli.py` monolith (BL-104) and
`execute_download` (BL-1105), per-video playlist mode (BL-202), config validation
(BL-106), network retries (BL-203), Windows coverage in CI (BL-1103).

### Refactoring Opportunities

#### R1: Extract CLI into Thin Controller — ✅ done (BL-104, BL-1105)
**Problem:** `cli.py` has business logic mixed with presentation  
**Solution:** Move logic to service layer, CLI only handles I/O  
**How it landed:** `ytd/workflows/` plays the service-layer role: `cli.py` is 394 lines
of Typer commands, `execute_download` is 112 lines of context setup and dispatch.

**Before:**
```python
# cli.py
def cmd_download(...):
    # 200 lines of logic
```

**After:**
```python
# cli.py
def cmd_download(...):
    service = DownloadService(config, logger)
    service.download(options)

# ytd/services/download_service.py
class DownloadService:
    def download(self, options): ...
```

---

#### R2: Introduce Service Layer — ✅ closed differently (BL-1105)
**Problem:** Direct coupling between CLI and Downloader  
**Solution:** Add service layer for business logic

**Actual structure (instead of `services/`):**
```
ytd/
  cli.py            — Presentation (Typer)
  workflows/        — orchestration
    download_command.py   — context + select_scenario
    single_video.py, playlist_*.py, download_one.py — scenarios
    context.py, url_sources.py, info_fetch.py       — shared pieces
  downloader.py     — Infrastructure (yt-dlp wrapper)
```

---

#### R3: Async/Await Refactoring
**Problem:** Synchronous operations block unnecessarily  
**Solution:** Refactor to async for better concurrency

**Benefit:**
- Better resource utilization
- Cleaner parallel download implementation
- Preparation for web UI

**Scope:**
- `downloader.py` — async methods
- `cli.py` — async command handlers
- Dependencies: `asyncio`, `aiofiles`

---

#### R4: Plugin Architecture
**Problem:** Hard to extend without modifying core  
**Solution:** Introduce plugin system

**Use Cases:**
- Custom post-processors
- Additional video sources (Vimeo, etc.)
- Custom metadata extractors

**Design:**
```python
# ytd/plugins/base.py
class Plugin(ABC):
    @abstractmethod
    def process(self, video: Video) -> Video: ...

# User plugin
class MyPlugin(Plugin):
    def process(self, video):
        # Custom logic
        return video

# Load plugins from config
plugins:
  - type: custom
    module: my_plugin.MyPlugin
    config: {...}
```

---

## Long-term Vision

### 2026: Feature-Complete CLI
- All core features implemented
- Stable API for library usage
- Comprehensive documentation
- High test coverage

### 2027: Platform & Ecosystem
- Web UI production-ready
- REST API stable
- Plugin marketplace
- Community contributions
- Multiple video platforms supported (Vimeo, Dailymotion, etc.)

### 2028+: AI & Intelligence
- Smart quality selection based on network speed
- Automatic content categorization
- Duplicate detection across platforms
- Transcript generation with AI
- Content recommendations

---

## Contributing to This Roadmap

**Priority Changes:** Features can move up/down based on:
- User feedback and feature requests
- Technical dependencies
- Available contributor time
- Security/bug severity

**Suggest Features:**
- Open GitHub issue with label `feature-request`
- Provide use case and impact estimate
- Community voting via 👍 reactions

**Claim Features:**
- Comment on issue "I'd like to work on this"
- Discuss implementation approach
- Submit PR following contribution guidelines

---

## Conclusion

This roadmap provides a comprehensive view of ytd's development trajectory. The project has a solid MVP foundation and clear paths for expansion across multiple dimensions:

- **User Experience:** TUI, Web UI, better progress tracking
- **Performance:** Parallel downloads, resume, caching
- **Content:** Subtitles, chapters, full archiving
- **Integration:** APIs, Docker, media library sync
- **Quality:** Tests, benchmarks, security

The modular architecture allows for parallel development across branches, enabling community contributions while maintaining stability.

**Next Immediate Steps:**
1. Complete interactive per-video mode (Phase 1.1)
2. Implement rich progress bars (Phase 4.1)
3. Add subtitle support (Phase 3.1)
4. Parallel downloads prototype (Phase 2.1)

*Last updated: October 27, 2025*
