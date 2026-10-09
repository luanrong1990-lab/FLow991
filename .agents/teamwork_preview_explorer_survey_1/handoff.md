# Handoff Report: Code-Level Survey & Gap Analysis

**Agent**: `teamwork_preview_explorer_survey_1`  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_survey_1`  
**Project Root**: `d:/New folder (5)`  
**Target Milestone**: Workspace Survey, R1 & Core Architecture Gap Analysis  
**Handoff Type**: Hard (Task Complete)

---

## 1. Observation

### Observation 1.1: GUI Framework Mismatch
- Exact grep search across workspace for `PySide6`:
  ```
  File: d:\New folder (5)\ORIGINAL_REQUEST.md, Line 5
  File: d:\New folder (5)\ORIGINAL_REQUEST.md, Line 12
  File: d:\New folder (5)\ORIGINAL_REQUEST.md, Line 21
  File: d:\New folder (5)\ORIGINAL_REQUEST.md, Line 65
  ```
  Result: 0 matches in Python code files (`*.py`).
- File `d:/New folder (5)/app.py`, Lines 1-5:
  ```python
  1: from nicegui import app, ui
  2: from config import SERVER_PORT
  3: from database.db import init_db
  4: from ui import dashboard, account_page, queue_page, image_page, video_page
  5: from fastapi import WebSocket, WebSocketDisconnect
  ```
- File `d:/New folder (5)/server.py`, Lines 4-7:
  ```python
  4: from flask import Flask, request, jsonify, send_from_path
  5: from playwright.sync_api import sync_playwright
  6: 
  7: app = Flask(__name__, static_folder=".", static_url_path="")
  ```
  Observation: The workspace currently runs as a web application via NiceGUI (`app.py`) or Flask (`server.py`), not a desktop PySide6 application.

### Observation 1.2: R1 Five Tab Views Gap
- Tabs defined in `d:/New folder (5)/app.py`, Lines 143-150:
  ```python
  143: with ui.tabs().classes('w-full bg-slate-900 border border-slate-800 rounded-xl text-slate-400') as tabs:
  144:     tab_dashboard = ui.tab('Dashboard', icon='dashboard')
  145:     tab_accounts = ui.tab('Tài khoản', icon='people')
  146:     tab_queue = ui.tab('Queue', icon='queue')
  147:     tab_image = ui.tab('Image', icon='photo')
  148:     tab_video = ui.tab('Video', icon='movie')
  149:     tab_settings = ui.tab('Cài đặt', icon='settings')
  ```
  - **Account Management**: `ui/account_page.py` displays cards with health % and `ACTIVE`/`INACTIVE` status. It lacks operational roles (`IMAGE_GEN` vs `VIDEO_GEN`) and health state enums (`READY`, `BUSY`, `RATE_LIMITED`).
  - **Image Generation**: `ui/image_page.py` has a multi-line prompt textarea (Lines 48-52) and splits lines to create jobs in `jobs` table (Lines 10-27). It lacks a scene sequence list and real-time account-to-scene mapping.
  - **Video Generation**: `ui/video_page.py` is an identical textarea prompt box. It lacks First Frame / reference image ingestion from Image Generation, lacks Veo 3.1 Lite configuration (8s, 16:9, 720p), and lacks a dedicated video worker queue.
  - **Stitch & Render (FFmpeg)**: Completely missing. No tab exists, no timeline viewer exists, no export config exists.
  - **Dashboard**: `ui/dashboard.py` displays 4 cards: Total Nick, Active Accounts, Health Index %, Unhealthy Accounts (<80%). It lacks metrics for total images/videos generated, success rate, and queue depth.

### Observation 1.3: Database Schema Gap
- File `d:/New folder (5)/database/db.py`, Lines 18-56:
  - Creates table `accounts` (`id`, `name`, `email`, `profile_path`, `proxy`, `delay`, `status`, `health`, `google_ok`, `flow_ok`, `gemini_ok`, `request_count`, `success_count`, `failed_count`, `last_check`, `created_at`, `server`).
  - Adds column `project_id` via `ALTER TABLE` (Line 76).
  - Creates table `jobs` (`id`, `project`, `media_type`, `prompt`, `ratio`, `model`, `status`, `progress`, `result_file`, `account_id`, `error_message`, `created_at`).
  - Creates table `system_settings` (`key`, `value`).
- Grep search for `CREATE TABLE` across workspace:
  ```
  database/db.py:18: CREATE TABLE IF NOT EXISTS accounts
  database/db.py:42: CREATE TABLE IF NOT EXISTS jobs
  database/db.py:83: CREATE TABLE IF NOT EXISTS system_settings
  ```
  Observation: Tables `scenes`, `prompt_batches`, and `render_jobs` DO NOT EXIST.

### Observation 1.4: Communication Protocol Deviation
- File `d:/New folder (5)/app.py`, Line 15:
  ```python
  @app.websocket('/ws/extension')
  async def websocket_endpoint(websocket: WebSocket):
  ```
- File `d:/New folder (5)/flow-extension/websocket.js`, Line 4:
  ```javascript
  const WS_URL = "ws://127.0.0.1:5000/ws/extension";
  ```
- File `d:/New folder (5)/ORIGINAL_REQUEST.md`, Lines 35-40:
  ```
  ### R3. Bidirectional Chrome Native Messaging Host
  Implement standard Chrome Native Messaging protocol:
  - Python Native Messaging host script/executable communicating via 32-bit length-prefixed JSON over stdin/stdout.
  - Extension background service worker connects via chrome.runtime.connectNative.
  - Commands supported: generate_image, generate_video, enter_setup_mode, query_status.
  - Responses supported: status_update (progress %, state), success (downloaded file path), error (failure details).
  - Include an automated setup/install script to register the Native Messaging Host manifest in the Windows Registry (HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge).
  ```
  Observation: Current inter-process communication uses WebSocket (`ws://127.0.0.1:5000/ws/extension`), whereas the specification mandates Chrome Native Messaging over `stdin`/`stdout`.

### Observation 1.5: Critical Code Bugs & Non-Functional Elements
1. **Thread Event Loop Failure in `workers/browser_worker.py`**:
   - Lines 216 & 225-243:
     ```python
     threading.Thread(target=self._send_socket_async, args=(payload,), daemon=True).start()
     ...
     def _send_socket_async(self, payload):
         ...
         loop = asyncio.get_event_loop()
     ```
     In Python 3.10+, `asyncio.get_event_loop()` in a newly spawned background thread raises `RuntimeError: There is no current event loop in thread 'Thread-X'`. This causes socket dispatch to fail silently in the `except` block.
2. **Bundled Chromium Launched Instead of Real Chrome**:
   - `workers/browser_worker.py:43` finds `chrome_path = find_chrome_path()`, but Line 69 omits `executable_path=chrome_path`:
     ```python
     context = p.chromium.launch_persistent_context(
         user_data_dir=profile_path,
         headless=False,
         ...
     ```
     This launches Playwright's bundled Chromium without Google Chrome's profile data.
3. **Extension Function Crash in `flow-extension/content.js`**:
   - Line 93:
     ```javascript
     overlay.setJob(activeJobId);
     ```
   - In `flow-extension/overlay.js`, class `FlowOverlay` has no method named `setJob`. This raises `TypeError: overlay.setJob is not a function`, crashing the automation execution before prompt input.
4. **Missing FFmpeg Engine (R5)**:
   - Grep search for `ffmpeg` returns zero matches outside `ORIGINAL_REQUEST.md`. No FFmpeg wrapper or command generator exists.
5. **Missing Test Suite (R6)**:
   - No `tests/` directory exists. No pytest test files exist.

---

## 2. Logic Chain

1. **Step 1 (GUI Architecture)**:
   - From Observation 1.1, the existing UI code in `app.py` and `ui/*.py` uses NiceGUI (`from nicegui import app, ui`), and `server.py` uses Flask.
   - Requirement R1 explicitly specifies: *"Desktop GUI & Core Orchestrator: Python + PySide6"* with a *"dark-themed PySide6 application structured into: 1. Account Management, 2. Image Generation, 3. Video Generation, 4. Stitch & Render (FFmpeg), 5. Dashboard"*.
   - Therefore, the current GUI is fundamentally off-stack and requires a native PySide6 desktop implementation.

2. **Step 2 (Feature Inventory & Gap Analysis for R1)**:
   - From Observation 1.2:
     - Account Management lacks roles (`IMAGE_GEN`/`VIDEO_GEN`), lacks status (`READY`, `BUSY`, `RATE_LIMITED`), and lacks the Guided Mapping Setup Mode trigger button.
     - Image Generation lacks scene sequence listing and real-time account-to-scene mapping.
     - Video Generation lacks image ingredient ingestion from Image Generation, lacks Veo 3.1 Lite controls, and lacks worker queue isolation.
     - Stitch & Render is entirely absent (0% implemented).
     - Dashboard lacks total images/videos generated, success rate, and queue depth metrics.
   - Therefore, all 5 tabs in R1 are either partially implemented in NiceGUI or completely missing.

3. **Step 3 (Data Architecture)**:
   - From Observation 1.3, the database only contains `accounts`, `jobs`, and `system_settings`.
   - Requirement line 17 and line 66 require persistence for *"accounts, scenes, prompt batches, and render jobs"*.
   - Therefore, database schema migrations and model extensions are required for `scenes`, `prompt_batches`, `render_jobs`, and new account columns (`role`, `health_status`, `cooldown_until`).

4. **Step 4 (Inter-Process Communication & Browser Bridge)**:
   - From Observation 1.4, the existing system bridges Python and the Chrome Extension over a local WebSocket server at `ws://127.0.0.1:5000/ws/extension`.
   - Requirement R3 explicitly mandates *"Bidirectional Chrome Native Messaging Host communicating via 32-bit length-prefixed JSON over stdin/stdout"* and registration in `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`.
   - Therefore, a Native Messaging Host script and Windows Registry installer must be constructed to replace or supplement the WebSocket bridge.

5. **Step 5 (Code Health & Stability)**:
   - From Observation 1.5, there are three immediate blocking bugs:
     - `asyncio.get_event_loop()` failure prevents sending jobs to workers.
     - Omission of `executable_path` in `BrowserWorker` prevents using real Chrome profile credentials.
     - `overlay.setJob` call crashes extension automation.
   - Therefore, these runtime defects must be resolved before automated flow execution can succeed.

---

## 3. Caveats

1. **Subprocess/Command Execution**: Interactive command execution via `run_command` timed out due to system permission prompts; all observations were derived through direct inspection of files (`view_file`, `grep_search`, `find_by_name`).
2. **Chrome Dynamic Session State**: The existing profiles under `profiles/` contain SQLite cookies and history files, which indicate previous interactive manual sessions occurred, but live browser execution against Google Flow was not executed in this read-only phase.
3. **No Caveats Beyond Above**: All code paths and dependencies have been directly inspected.

---

## 4. Conclusion

The workspace contains substantial prototype foundations for account management, Playwright profile launching, and DOM interaction on Google Flow, but exhibits a significant architectural gap against the project specification:
1. **R1 (PySide6 Desktop GUI)** is **0% implemented in PySide6** (currently exists only as NiceGUI/Flask web prototypes). All 5 tab views require native PySide6 implementation.
2. **Database Architecture** is missing 3 of the 4 core entities (`scenes`, `prompt_batches`, `render_jobs`), and `accounts` lacks operational roles and status enumerations.
3. **R3 (Chrome Native Messaging)** is unimplemented (currently using WebSocket).
4. **R5 (FFmpeg Engine)** and **R6 (Automated Test Suite)** are completely unimplemented.
5. Three critical runtime bugs (`asyncio` thread loop, Playwright executable path, and extension `overlay.setJob`) block end-to-end execution.

A detailed technical inventory and migration roadmap has been compiled into `d:/New folder (5)/.agents/teamwork_preview_explorer_survey_1/survey_report.md`.

---

## 5. Verification Method

To independently verify the observations and conclusions:

1. **Verify Absence of PySide6**:
   - Inspect Python files: search for `import PySide6` or `from PySide6` across all `.py` files in `d:/New folder (5)`:
     ```powershell
     rg "PySide6" "d:/New folder (5)" -g "*.py"
     ```
     Expected result: 0 matches.
2. **Verify Database Schema**:
   - Inspect `d:/New folder (5)/database/db.py` lines 18-97:
     Verify only `accounts`, `jobs`, and `system_settings` tables are created; confirm absence of `scenes`, `prompt_batches`, `render_jobs`.
3. **Verify Runtime Bugs**:
   - Inspect `d:/New folder (5)/workers/browser_worker.py:236` (`asyncio.get_event_loop()`).
   - Inspect `d:/New folder (5)/workers/browser_worker.py:69` (missing `executable_path=chrome_path`).
   - Inspect `d:/New folder (5)/flow-extension/content.js:93` (`overlay.setJob(activeJobId)`) against `d:/New folder (5)/flow-extension/overlay.js` (confirming `setJob` does not exist).
4. **Verify Missing FFmpeg and Test Suite**:
   - Inspect project root: confirm absence of `tests/` directory and absence of any FFmpeg python wrapper in `services/`.

### Invalidation Conditions:
- If a PySide6 GUI module already exists under an unindexed directory, Conclusion 1 is invalidated.
- If `scenes` and `render_jobs` tables exist in SQLite, Conclusion 2 is invalidated.
