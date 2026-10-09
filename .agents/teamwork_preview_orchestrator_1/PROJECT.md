# Project: VQPVEO3PRO - AI Video Generation Studio

## Architecture
VQPVEO3PRO is a full-stack desktop application combining Python (PySide6) and a Manifest V3 Chrome Extension to automate multi-account AI image generation (Nano Banana 2) and video generation (Veo 3.1 Lite) on Google Flow, and stitch final 1080p videos with FFmpeg.

- **Desktop GUI**: PySide6 dark-themed interface with 5 dedicated tab views.
- **Database & Persistence**: SQLite (`database/db.py`, `database/models.py`) with tables for `accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`.
- **Browser Management**: Playwright persistent Chrome contexts per account profile with anti-automation flags and extension loaded.
- **DOM Automation & Guided Mapping**: Chrome Extension (Manifest V3) in `extension/` with Setup Mode (visual inspector for CSS/XPath) and Run Mode (DOM executor driven by `flow_adapter_config.json`).
- **Inter-Process Communication**: Chrome Native Messaging over stdin/stdout with 32-bit length-prefixed JSON protocol registered at `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`.
- **Video Post-Processing**: FFmpeg wrapper (`services/ffmpeg_service.py`) supporting concat demuxing, 1080p upscaling, audio normalization, BGM mixing, and real-time progress parsing.
- **Automated Test Suite**: Comprehensive pytest suite in `tests/` covering Native Messaging framing, mock orchestrator scheduling, FFmpeg command generation, and extension schema validation.

## Feature Inventory
| # | Feature | Description | Milestone | Source |
|---|---------|-------------|-----------|--------|
| 1 | SQLite Database Initialization & Migrations | Tables: accounts, scenes, prompt_batches, jobs, render_jobs, system_settings with automated schema migration | M1 | ORIGINAL_REQUEST §17, §66 |
| 2 | Account Schema & Role Configuration | Model support for operational roles (IMAGE_GEN, VIDEO_GEN) and health status (READY, BUSY, RATE_LIMITED) | M1 | ORIGINAL_REQUEST §23, §44 |
| 3 | Batch Prompt Parser & Scene Model | Multi-line text splitting into distinct jobs and scenes in SQLite queue | M1 | ORIGINAL_REQUEST §24, §67 |
| 4 | Chrome Extension Manifest V3 | Manifest with nativeMessaging, storage, downloads permissions under extension/ | M2 | ORIGINAL_REQUEST §30, §70 |
| 5 | Native Messaging Binary Framing & Host | 32-bit length-prefixed JSON protocol over stdin/stdout in Python | M2 | ORIGINAL_REQUEST §35, §71 |
| 6 | Native Messaging Commands & Responses | Commands: generate_image, generate_video, enter_setup_mode, query_status; Responses: status_update, success, error | M2 | ORIGINAL_REQUEST §38-39 |
| 7 | Windows Registry Host Registration Script | Automated setup script for HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge | M2 | ORIGINAL_REQUEST §40, §72 |
| 8 | Guided Mapping Setup Mode | Injected visual overlay with interactive pointer/highlighter extracting CSS/XPath selectors into flow_adapter_config.json | M2 | ORIGINAL_REQUEST §31, §73 |
| 9 | Run Mode DOM Execution Engine | Config-driven DOM automation executing prompt typing, model/ratio setting, completion detection, and download | M2 | ORIGINAL_REQUEST §32 |
| 10 | Playwright Persistent Context Management | Independent browser launching per Google account profile with extension loaded and anti-automation flags | M3 | ORIGINAL_REQUEST §13, §43 |
| 11 | Priority Scheduling & Queue Management | Dedicated IMAGE_GEN rotation and priority VIDEO_GEN (Veo 3.1 Lite) queue dispatch | M3 | ORIGINAL_REQUEST §44 |
| 12 | Round-Robin Dispatch & Cooldown System | Worker round-robin selection with timestamp-based cooldown and rate-limit backoff handling | M3 | ORIGINAL_REQUEST §45 |
| 13 | FFmpeg Concat Demuxer Engine | Timeline concatenation of scene video clips | M4 | ORIGINAL_REQUEST §49, §76 |
| 14 | FFmpeg Audio Normalization & BGM Mixing | EBU R128 loudness normalization and background music mixing with volume balancing | M4 | ORIGINAL_REQUEST §50-51 |
| 15 | FFmpeg 1080p Upscaling & Transcoding | Upscaling to 1920x1080 with H.264/AAC encoding | M4 | ORIGINAL_REQUEST §52 |
| 16 | FFmpeg Real-Time Progress Parsing | Subprocess stdout/stderr progress parsing emitting percentage to UI/database | M4 | ORIGINAL_REQUEST §53 |
| 17 | PySide6 Dark-Themed GUI Shell | Desktop application base window, styling, and navigation across 5 tabs | M5 | ORIGINAL_REQUEST §21-22, §65 |
| 18 | Tab 1: Account Management View | List Chrome profiles, role selection, health status badges, manual login, and Guided Mapping trigger | M5 | ORIGINAL_REQUEST §23 |
| 19 | Tab 2: Image Generation View | Batch prompt input, scene sequence list, queue progress, and real-time worker-to-scene mapping | M5 | ORIGINAL_REQUEST §24 |
| 20 | Tab 3: Video Generation View | Ingestion of completed images as First Frame / reference ingredients, Veo 3.1 Lite controls, video queue | M5 | ORIGINAL_REQUEST §25 |
| 21 | Tab 4: Stitch & Render View | Timeline clip viewer, export configuration (upscale, FPS, codec, audio norm, BGM), render progress bar | M5 | ORIGINAL_REQUEST §26 |
| 22 | Tab 5: Dashboard View | Metrics cards (total images/videos, success rate, queue depth, active worker statuses) | M5 | ORIGINAL_REQUEST §27 |
| 23 | Automated Test: Native Messaging Framing | Unit tests for pack/unpack length-prefixed JSON binary framing | E2E | ORIGINAL_REQUEST §57 |
| 24 | Automated Test: Mock Orchestrator Scheduler | Tests verifying round-robin dispatch, priority sorting, and state transitions | E2E | ORIGINAL_REQUEST §58 |
| 25 | Automated Test: FFmpeg Command Builder | Tests verifying concat demuxer syntax, filter graph parameters, and progress parsing | E2E | ORIGINAL_REQUEST §59, §76 |
| 26 | Automated Test: Extension Schema Validation | Validation tests for flow_adapter_config.json and Manifest V3 structure | E2E | ORIGINAL_REQUEST §60 |
| 27 | Multi-Clip Mock Render Test | End-to-end integration test validating clip creation and stitching | E2E | ORIGINAL_REQUEST §77 |

## Milestones
| # | Name | Scope | Dependencies | Status |
|---|------|-------|-------------|--------|
| M1 | Database & Models | SQLite schema, migrations, accounts, scenes, prompt_batches, jobs, render_jobs models | none | DONE |
| M2 | Extension & Native Messaging | Chrome Extension (Manifest V3), Guided Mapping, DOM Executor, Native Messaging Host, Registry installer | M1 | PLANNED |
| M3 | Browser Manager & Scheduler | Playwright persistent contexts, account rotation, priority scheduling, cooldown handling | M1 | PLANNED |
| M4 | FFmpeg Video Engine | Concat demuxer, filter graph builder, audio norm, BGM mixing, 1080p upscale, progress parser | M1 | PLANNED |
| M5 | PySide6 Desktop GUI | 5 Tab Views: Accounts, Image Gen, Video Gen, Stitch & Render, Dashboard | M1, M2, M3, M4 | PLANNED |
| E2E | E2E Testing Suite & Mocks | Pytest test suite (framing, scheduler, FFmpeg, extension schema) & TEST_READY.md | M1 | PLANNED |
| M_FINAL | Final Milestone | 100% E2E test pass (Tiers 1-4) & adversarial coverage hardening (Tier 5) | M1, M2, M3, M4, M5, E2E | PLANNED |

## Interface Contracts

### M1 ↔ M2 / M3 / M4 / M5
- `database.db.init_db()`: Initializes tables, runs safe column migrations.
- `database.models`:
  - `get_accounts() -> List[Dict]`: returns accounts with `id`, `name`, `email`, `role`, `status`, `health_status`, `cooldown_until`.
  - `update_account_status(account_id, status, health_status, cooldown_until=None)`.
  - `create_prompt_batch(name, text, media_type, project_id) -> int`: splits multi-line text into distinct jobs/scenes in SQLite queue.
  - `get_pending_jobs(media_type=None, priority_first=True) -> List[Dict]`.
  - `create_render_job(project_id, output_path, config_dict) -> int`.
  - `update_render_job(job_id, status, progress, error=None)`.

### M2 (Native Messaging Host) ↔ Chrome Extension
- Stdin/Stdout: 4-byte little-endian uint32 length prefix followed by UTF-8 encoded JSON string.
- Extension connect: `chrome.runtime.connectNative("com.vqp.flow_bridge")`.
- Host Commands:
  - `{"command": "generate_image", "prompt": str, "aspect_ratio": str, "model": str, "job_id": int}`
  - `{"command": "generate_video", "prompt": str, "image_path": str, "duration": int, "aspect_ratio": str, "job_id": int}`
  - `{"command": "enter_setup_mode"}`
  - `{"command": "query_status"}`
- Host Responses:
  - `{"type": "status_update", "job_id": int, "state": str, "progress": int}`
  - `{"type": "success", "job_id": int, "file_path": str}`
  - `{"type": "error", "job_id": int, "message": str}`
- Config: `flow_adapter_config.json`:
  - JSON schema containing keys: `prompt_box`, `generate_button`, `download_link`, `model_selector`, `ratio_options`. Each element specifies `css_selector`, `xpath_selector`, and fallback heuristics.

### M3 (Scheduler & Browser Worker) ↔ Application
- `Scheduler.start()` / `Scheduler.stop()`.
- `Scheduler.dispatch_next()`: Round-robin through idle workers whose `role` matches job `media_type` and `cooldown_until <= current_time`. Video jobs (Veo 3.1 Lite) dispatched with priority.
- `BrowserWorker.launch(profile_path)`: Launches persistent context with `--load-extension=extension` and real Chrome executable path.

### M4 (FFmpeg Engine) ↔ Application / UI
- `FFmpegEngine.render_timeline(clips: List[str], output_file: str, options: Dict, progress_callback: Callable[[float], None]) -> bool`:
  - Options: `upscale_1080p: bool`, `fps: int`, `codec: str`, `normalize_audio: bool`, `bgm_file: Optional[str]`, `bgm_volume: float`.
  - Generates concat demuxer text file in temp directory.
  - Emits real-time progress percentage (0-100) parsed from `-progress pipe:1`.

## Code Layout
```
d:/New folder (5)/
├── database/
│   ├── db.py                 # SQLite init, connection, migrations
│   └── models.py             # Data models and CRUD helpers
├── automation/
│   ├── browser.py            # Playwright persistent context launcher
│   ├── native_host.py        # Chrome Native Messaging Host (stdin/stdout JSON framing)
│   └── install_host.py       # Windows Registry installer for com.vqp.flow_bridge
├── extension/                # Chrome Extension (Manifest V3)
│   ├── manifest.json         # Manifest V3 (nativeMessaging, storage, downloads)
│   ├── background.js         # Service worker connecting to native host
│   ├── content.js            # Content script entrypoint
│   ├── overlay.js            # Guided mapping visual pointer & selector extractor
│   ├── executor.js           # Run mode DOM automation executor
│   └── flow_adapter_config.json # Target element selectors
├── workers/
│   ├── browser_worker.py     # Worker thread managing browser lifecycle & IPC
│   └── scheduler.py          # Round-robin priority scheduler with cooldowns
├── services/
│   ├── account_service.py    # Account management logic
│   └── ffmpeg_service.py     # FFmpeg concat, loudnorm, BGM mix, 1080p upscale
├── ui/
│   ├── app_window.py         # PySide6 main window & dark theme stylesheet
│   ├── tabs/
│   │   ├── accounts_tab.py   # Tab 1: Account Management
│   │   ├── image_gen_tab.py  # Tab 2: Image Generation
│   │   ├── video_gen_tab.py  # Tab 3: Video Generation
│   │   ├── render_tab.py     # Tab 4: Stitch & Render (FFmpeg)
│   │   └── dashboard_tab.py  # Tab 5: Metrics Dashboard
├── tests/
│   ├── test_native_messaging.py # Framing unit tests
│   ├── test_scheduler.py        # Mock orchestrator & round-robin tests
│   ├── test_ffmpeg_engine.py    # Concat, filter graph, progress tests
│   ├── test_extension_schema.py # Extension manifest & config tests
│   └── test_integration.py      # Multi-clip mock render test
├── main.py                   # PySide6 application launcher
└── config.py                 # Application configuration & paths
```
