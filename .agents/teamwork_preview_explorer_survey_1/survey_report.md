# WORKSPACE CODE-LEVEL SURVEY REPORT: VQPVEO3PRO STUDIO

**Date**: 2026-09-08  
**Workspace**: `d:/New folder (5)`  
**Investigator**: `teamwork_preview_explorer_survey_1`  
**Integrity Mode**: Development / Read-Only Survey

---

## 1. Executive Summary

A comprehensive, code-level survey was conducted across all files, directories, databases, automation scripts, and extensions in `d:/New folder (5)`. 

### Key Findings:
1. **Desktop GUI Framework Mismatch**: The workspace currently contains **zero PySide6 code**. Instead, two web-based prototypes exist:
   - A **NiceGUI** (FastAPI + Quasar/Tailwind) web interface (`app.py`, `ui/` directory).
   - An older **Flask + Vanilla JS** web interface (`server.py`, `index.html`, `app.js`, `style.css`).
   To fulfill Requirement **R1**, a complete PySide6 dark-themed application with the specified 5 tab views must be built.
2. **Missing Core Database Tables**:
   - The current SQLite database (`database/database.db`, defined in `database/db.py`) only has 3 tables: `accounts`, `jobs`, and `system_settings`.
   - Tables for **`scenes`**, **`prompt_batches`**, and **`render_jobs`** are completely missing.
   - The `accounts` table is missing operational roles (`IMAGE_GEN` vs `VIDEO_GEN`) and health state enumerations (`READY`, `BUSY`, `RATE_LIMITED`).
3. **Communication Protocol Deviation (WebSocket vs Native Messaging)**:
   - The system currently communicates between Python and the Chrome Extension via **WebSocket** (`ws://127.0.0.1:5000/ws/extension`).
   - Requirement **R3** mandates **Chrome Native Messaging** (stdin/stdout length-prefixed 32-bit JSON protocol, host manifest registered at `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`).
4. **Missing FFmpeg Engine (R5)**:
   - There is no FFmpeg wrapper or video stitching engine in the codebase.
5. **Missing Automated Test Suite (R6)**:
   - There is no `tests/` directory or pytest test suite.
6. **Critical Bugs Identified in Existing Code**:
   - `workers/browser_worker.py:236`: `asyncio.get_event_loop()` called inside a new thread raises `RuntimeError` in Python 3.10+, preventing WebSocket dispatch of jobs.
   - `workers/browser_worker.py:69`: `launch_persistent_context` omits `executable_path=chrome_path`, launching bundled Chromium instead of Google Chrome with logged-in profiles.
   - `flow-extension/content.js:93`: Calls non-existent method `overlay.setJob(activeJobId)`, throwing `TypeError`.

---

## 2. Workspace Architecture & File Inventory

```
d:/New folder (5)/
├── ORIGINAL_REQUEST.md      # Ground truth specification and acceptance criteria
├── app.py                   # NiceGUI entry point, WebSocket server (/ws/extension)
├── server.py                # Legacy Flask server (runs on port 5000, uses database.json)
├── config.py                # Paths configuration (PROFILES_DIR, OUTPUT_DIR, DB_PATH, SERVER_PORT=5000)
├── index.html               # Legacy web UI for account management
├── app.js                   # Legacy web UI JS logic
├── style.css                # Legacy web UI stylesheet
├── ui/                      # NiceGUI tab implementations
│   ├── account_page.py      # Account management UI (cards, search, modal dialog)
│   ├── dashboard.py         # Summary metrics (total accounts, active, health, unhealthy)
│   ├── image_page.py        # Multi-line image prompt input
│   ├── video_page.py        # Multi-line video prompt input
│   └── queue_page.py        # Queue controls, worker badges, job list
├── database/
│   ├── db.py                # SQLite init_db() and connection factory
│   ├── models.py            # CRUD operations for accounts, jobs, system_settings
│   └── database.db          # Active SQLite database file
├── services/
│   └── account_service.py   # Account business logic, browser launcher wrapper
├── automation/
│   └── browser.py           # Chrome path detection, Playwright launch, cookie/history inspector
├── playwright/
│   └── browser.py           # Unused / duplicate older Playwright launcher
├── workers/
│   ├── browser_worker.py    # Per-account browser process manager and job execution
│   └── scheduler.py         # JobScheduler thread, round-robin dispatch
├── extension/               # Legacy monolithic extension (background.js, content.js, manifest.json)
├── flow-extension/          # Modular extension (manifest.json, background.js, flow.js, overlay.js, etc.)
│   ├── manifest.json        # MV3 manifest
│   ├── background.js        # Service worker, message relay
│   ├── websocket.js         # WebSocket client connecting to ws://127.0.0.1:5000/ws/extension
│   ├── content.js           # Injection coordinator, self-healing selector listeners
│   ├── flow.js              # FlowAdapter DOM automation queries and actions
│   ├── overlay.js           # FlowOverlay HUD UI
│   └── download.js          # chrome.downloads listener
├── profiles/                # User data directories for Chrome profiles
├── output/                  # Generated assets (contains scene_cat_fireplace.jpg)
├── projects/                # Directory for project assets (currently empty)
└── scratch/                 # Ad-hoc inspection and debugging scripts
```

---

## 3. Detailed R1 (PySide6 Desktop GUI) Feature Inventory & Gap Analysis

Requirement **R1** specifies a dark-themed PySide6 application with 5 tab views:
1. Account Management
2. Image Generation
3. Video Generation
4. Stitch & Render (FFmpeg)
5. Dashboard

| Tab / Component | Required by R1 | Current Workspace Status | Gap & Details |
|---|---|---|---|
| **GUI Framework** | Python + PySide6 desktop app | **MISSING** (NiceGUI / Flask web apps) | PySide6 is not imported or used anywhere. The app currently runs as a web server on `localhost:5000`. Needs full PySide6 implementation (`QMainWindow`, `QTabWidget`, dark QSS stylesheet). |
| **Tab 1: Account Management** | List Chrome profiles, assign roles (`IMAGE_GEN` vs `VIDEO_GEN`), show health status (`READY`, `BUSY`, `RATE_LIMITED`), launch manual login, trigger Guided Mapping Setup Mode | **PARTIALLY IMPLEMENTED** (in NiceGUI `ui/account_page.py`) | - Missing operational roles (`IMAGE_GEN` vs `VIDEO_GEN`).<br>- Uses percentage health (0-100%) and `ACTIVE`/`INACTIVE` instead of required enum (`READY`, `BUSY`, `RATE_LIMITED`).<br>- Manual login launcher exists via subprocess.<br>- "Guided Mapping Setup Mode" trigger button is **missing**. |
| **Tab 2: Image Generation** | Multi-line batch prompt input (1 per line), scene sequence list, queue progress tracking with real-time account-to-scene mapping | **PARTIALLY IMPLEMENTED** (in NiceGUI `ui/image_page.py`) | - Multi-line prompt input exists and parses lines.<br>- **Missing** scene sequence list (scenes are not displayed or structured).<br>- **Missing** real-time account-to-scene mapping (queue is in a separate tab `queue_page.py` and only tracks raw jobs, not scenes). |
| **Tab 3: Video Generation** | Automatic ingestion of completed images as First Frame / reference ingredients, Veo 3.1 Lite config (8s, 16:9, 720p), video worker queue | **PARTIALLY IMPLEMENTED** (in NiceGUI `ui/video_page.py`) | - Currently just a clone of the image prompt text box.<br>- **Missing** automatic ingestion of completed images from Image Generation.<br>- **Missing** Veo 3.1 Lite configuration options.<br>- **Missing** dedicated video worker queue separation. |
| **Tab 4: Stitch & Render (FFmpeg)** | Video timeline viewer for completed clips, export configuration (1080p upscale, FPS, codec, audio normalization, background music), progress bar for rendering | **COMPLETELY MISSING** | - No UI tab or widgets exist for video stitching or timeline.<br>- No export configuration widgets.<br>- No FFmpeg backend wrapper exists in the project. |
| **Tab 5: Dashboard** | Metrics overview: total images/videos generated, success rate, queue depth, active worker statuses | **PARTIALLY IMPLEMENTED** (in NiceGUI `ui/dashboard.py` and `ui/queue_page.py`) | - Displays total accounts, active accounts, health %, unhealthy accounts.<br>- **Missing** total images generated count.<br>- **Missing** total videos generated count.<br>- **Missing** success rate metrics for media jobs.<br>- **Missing** queue depth indicators (currently placed in `queue_page.py`).<br>- Active worker statuses are in `queue_page.py`, not in Dashboard. |

---

## 4. Database Schema Analysis: Current vs Required

### Current Schema (`database/db.py`, `database/models.py`)

#### Table: `accounts`
```sql
CREATE TABLE accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    profile_path TEXT NOT NULL,
    proxy TEXT DEFAULT '',
    delay INTEGER DEFAULT 5,
    status TEXT NOT NULL DEFAULT 'INACTIVE',
    health INTEGER DEFAULT 100,
    google_ok INTEGER DEFAULT 0,
    flow_ok INTEGER DEFAULT 0,
    gemini_ok INTEGER DEFAULT 0,
    request_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failed_count INTEGER DEFAULT 0,
    last_check TEXT,
    created_at TEXT,
    server INTEGER DEFAULT 0,
    project_id TEXT DEFAULT ''
);
```

#### Table: `jobs`
```sql
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    project TEXT DEFAULT 'Default',
    media_type TEXT NOT NULL,
    prompt TEXT NOT NULL,
    ratio TEXT DEFAULT '1:1',
    model TEXT DEFAULT 'Default',
    status TEXT NOT NULL DEFAULT 'PENDING',
    progress INTEGER DEFAULT 0,
    result_file TEXT DEFAULT '',
    account_id TEXT DEFAULT '',
    error_message TEXT DEFAULT '',
    created_at TEXT
);
```

#### Table: `system_settings`
```sql
CREATE TABLE system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```

---

### Required Schema vs Current Gap

| Requirement Entity | Required Schema & Fields | Current Schema Status | Deficit / Migration Required |
|---|---|---|---|
| **Accounts** | `id`, `name`, `email`, `profile_name`, `role` (`IMAGE_GEN` \| `VIDEO_GEN` \| `BOTH`), `health_status` (`READY`, `BUSY`, `RATE_LIMITED`, `OFFLINE`), `proxy`, `delay_seconds`, `cooldown_until`, `last_used_at`, `total_requests`, `success_count`, `failed_count` | `accounts` table exists, but uses legacy fields: `status` (`ACTIVE`/`INACTIVE`), numeric `health`, lacks operational `role` | Needs migration to add `role`, `health_status`, `cooldown_until`, `last_used_at`. |
| **Scenes** | `id`, `batch_id`, `scene_index`, `prompt`, `reference_image_path`, `generated_image_path`, `generated_video_path`, `image_job_id`, `video_job_id`, `status` (`PENDING_IMAGE`, `IMAGE_DONE`, `PENDING_VIDEO`, `VIDEO_DONE`, `FAILED`), `created_at`, `updated_at` | **COMPLETELY MISSING** | Must create table `scenes` with foreign keys to batches and job references. |
| **Prompt Batches** | `id`, `name`, `batch_type` (`IMAGE`, `VIDEO`), `raw_input`, `total_scenes`, `completed_scenes`, `status`, `created_at` | **COMPLETELY MISSING** | Must create table `prompt_batches`. |
| **Render Jobs** | `id`, `project_name`, `timeline_scenes` (JSON list of scene IDs / file paths in order), `output_resolution` (`1080p`), `fps`, `video_codec`, `audio_codec`, `audio_norm_enabled`, `bgm_file_path`, `bgm_volume`, `status` (`PENDING`, `RENDERING`, `COMPLETED`, `FAILED`), `progress`, `output_path`, `error_message`, `created_at`, `completed_at` | **COMPLETELY MISSING** | Must create table `render_jobs`. |

---

## 5. Interaction Architecture & Data Flow

### Current Interaction Flow:
1. **Startup**: `app.py:9` runs `init_db()`. `app.py:13` starts `scheduler_instance.start()` background loop.
2. **User Input**:
   - In `ui/image_page.py`, user enters multi-line prompts. Clicking "TẠO HÀNG LOẠT ẢNH" splits lines and calls `models.add_job` inserting rows into `jobs` table with `status='PENDING'`, `media_type='image'`.
3. **Scheduler**:
   - `workers/scheduler.py:_schedule_loop` wakes up every 100ms when `enabled=True`.
   - Fetches pending jobs via `models.get_pending_jobs()`.
   - Iterates through `active_workers.values()` to find a worker where `w.state == "IDLE" and w.websocket is not None`.
   - Calls `worker.execute_job(job)`.
4. **Browser Worker & WebSocket**:
   - `BrowserWorker` sets job to `RUNNING` via `models.assign_job_to_account`.
   - Attempts to send JSON payload `{"action": "generate", "job_id": ..., "prompt": ...}` to `self.websocket`.
5. **Extension Execution**:
   - `websocket.js` receives payload, calls `chrome.tabs.sendMessage` to `content.js`.
   - `content.js:startAutomation` invokes `FlowAdapter` (`flow.js`) to:
     - Open project (`adapter.openProject`)
     - Set prompt (`adapter.setPrompt`)
     - Apply model and ratio settings (`adapter.applySettings`)
     - Click generate (`adapter.clickGenerate`)
     - Wait for completion (`adapter.waitForFinish`)
     - Click download (`adapter.downloadResult`)
   - `download.js` listens to `chrome.downloads.onChanged` and sends `{status: "done", file: filename}` over WebSocket back to Python backend.
6. **Completion**:
   - `app.py:websocket_endpoint` updates SQLite job status to `COMPLETED`, updates account statistics, spawns `delayed_idle` thread for cooldown delay, and resets worker to `IDLE`.

### Protocol Mismatch vs Requirements:
- **WebSocket (`ws://127.0.0.1:5000/ws/extension`)**: Currently used in `app.py`, `workers/browser_worker.py`, and `flow-extension/websocket.js`.
- **Requirement R3 Mandate**: Chrome Native Messaging. Length-prefixed 32-bit JSON protocol over standard input/output (`stdin`/`stdout`), registered in Windows Registry at `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`.

---

## 6. Code Quality, Syntax Errors, Bugs, and Non-Functional Parts

### A. Critical Runtime Bugs
1. **`asyncio.get_event_loop()` in Spawned Thread (`workers/browser_worker.py:236`)**:
   - In `execute_job()`, line 216 calls:
     ```python
     threading.Thread(target=self._send_socket_async, args=(payload,), daemon=True).start()
     ```
   - In `_send_socket_async()`, line 236 calls:
     ```python
     loop = asyncio.get_event_loop()
     ```
   - In Python 3.10+, `asyncio.get_event_loop()` in a newly spawned thread raises `RuntimeError: There is no current event loop in thread 'Thread-X'`.
   - Because lines 241-243 catch `Exception` and only print an error message, the WebSocket payload is **silently never transmitted**.
2. **Missing `executable_path` in `workers/browser_worker.py:69`**:
   - Line 43 detects Google Chrome executable: `chrome_path = find_chrome_path()`.
   - But line 69 calls `p.chromium.launch_persistent_context(...)` without `executable_path=chrome_path`.
   - As a result, Playwright launches its bundled Chromium instead of Google Chrome, meaning saved Chrome profiles (Google logins, cookies, extensions) are not properly loaded.
3. **Extension Bug: Undefined Method `overlay.setJob` (`flow-extension/content.js:93`)**:
   - Line 93 calls `overlay.setJob(activeJobId)`.
   - Inspection of `flow-extension/overlay.js` reveals that class `FlowOverlay` has no `setJob()` method (it has `updateProgress()`, `updateProject()`, etc.).
   - This causes an unhandled `TypeError: overlay.setJob is not a function`, crashing the automation script before it inputs prompts or clicks generate.

### B. Architectural Deficits & Missing Components
1. **Zero PySide6 Desktop GUI**: The existing GUI is entirely web-based (NiceGUI + HTML/JS).
2. **Missing Chrome Native Messaging Host (R3)**:
   - No Python Native Messaging host script with 32-bit length-prefixed JSON binary framing (`struct.pack('<I', len(msg))` and `struct.unpack('<I', data)`).
   - No Native Messaging Host manifest JSON (`com.vqp.flow_bridge.json`).
   - No Windows Registry registration script for `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`.
3. **Missing Guided Mapping Setup Mode (R2)**:
   - In `flow-extension/`, there is only a passive HUD status widget (`overlay.js`).
   - There is no interactive visual element inspector/pointer/highlighter.
   - There is no step-by-step UI selector wizard.
   - There is no serialization to `flow_adapter_config.json`.
4. **Missing FFmpeg Stitching Engine (R5)**:
   - No concat demuxer generator.
   - No loudness normalization filter graph (`loudnorm`).
   - No background music audio mixer (`amix` / `amerge`).
   - No 1080p upscale filter graph (`scale=1920:1080:flags=lanczos`).
   - No real-time FFmpeg stderr progress parser.
5. **Missing Automated Test Suite (R6)**:
   - No pytest tests for binary framing, scheduler round-robin, FFmpeg command builder, or extension schema validation.
6. **Port Collision**:
   - Both `app.py` and `server.py` default to port 5000 (`config.py: SERVER_PORT = 5000`). If both are run, a port conflict error occurs.
7. **Stale / Duplicate Files**:
   - `playwright/browser.py` is an unmaintained duplicate of `automation/browser.py`.
   - `extension/` is an older unmaintained duplicate of `flow-extension/`.
   - `server.py` uses `database.json`, while `app.py` uses `database/database.db`.

---

## 7. Actionable Implementation Recommendations

1. **Implement R1 (PySide6 Desktop GUI)**:
   - Build a modern dark-themed Qt application using `PySide6.QtWidgets` (`QMainWindow`, `QTabWidget`, `QTableView`, `QProgressBar`, custom dark palette/QSS).
   - Implement the 5 required tabs:
     1. Account Management (Table of profiles, roles `IMAGE_GEN`/`VIDEO_GEN`, status badges `READY`/`BUSY`/`RATE_LIMITED`, login & setup buttons).
     2. Image Generation (Multi-line batch input, scene sequence table, real-time account-to-scene progress).
     3. Video Generation (First-frame image ingestion, Veo 3.1 Lite controls, video worker queue).
     4. Stitch & Render (FFmpeg) (Timeline clip viewer, 1080p/FPS/BGM configuration, render progress bar).
     5. Dashboard (Aggregated stats: images/videos created, success rates, queue depth, worker statuses).
2. **Upgrade SQLite Schema & Models**:
   - Add tables: `scenes`, `prompt_batches`, `render_jobs`.
   - Update `accounts` table with `role`, `health_status`, `cooldown_until`.
   - Write clean migration scripts and comprehensive CRUD methods in `database/models.py`.
3. **Implement R3 (Chrome Native Messaging Host)**:
   - Create `native_host/flow_bridge_host.py` handling 32-bit length-prefixed JSON over stdin/stdout.
   - Create manifest `com.vqp.flow_bridge.json`.
   - Create automated Windows registry installer script (`native_host/register_host.py` / `register_host.bat`).
4. **Implement R2 (Chrome Extension Guided Mapping & DOM Executor)**:
   - Fix `flow-extension/content.js` bugs (remove `setJob` error).
   - Build Guided Mapping Setup Mode overlay with highlighter and element click capture.
   - Serialize detected selectors to `flow_adapter_config.json`.
   - Update `manifest.json` to include `nativeMessaging` permission and connect via `chrome.runtime.connectNative`.
5. **Implement R4 (Account Rotation & Priority Scheduling)**:
   - Separate worker queues by account role (`IMAGE_GEN` vs `VIDEO_GEN`).
   - Round-robin dispatch with per-account cooldown tracking.
6. **Implement R5 (FFmpeg Stitching Engine)**:
   - Write `services/ffmpeg_engine.py` to generate concat files, audio normalization, BGM mixing, and 1080p rendering with real-time percentage callbacks.
7. **Implement R6 (Automated Test Suite)**:
   - Create `tests/` directory with pytest tests covering binary framing, scheduler logic, FFmpeg filter graphs, and extension config schema.
