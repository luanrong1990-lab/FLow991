# Technical Survey Report: R4, R5, R6 Architecture & Implementation Baseline

**Date**: 2026-09-08  
**Inspector**: `teamwork_preview_explorer_survey_3`  
**Project**: VQPVEO3PRO - AI Video Generation Studio  
**Target Scope**: 
- **R4**: Account Rotation & Priority Scheduling with Playwright
- **R5**: FFmpeg Stitching & Post-Processing Engine
- **R6**: Automated Test Suite & Mocks

---

## 1. Executive Summary

| Requirement | Target Specification | Current Codebase State | Completion % | Critical Gaps |
|-------------|----------------------|------------------------|--------------|---------------|
| **R4**: Account Rotation & Priority Scheduling | Independent Playwright persistent contexts; role-based accounts (`IMAGE_GEN` vs `VIDEO_GEN`); round-robin dispatch; configurable per-account cooldown delays; busy/rate-limited handling | Rudimentary browser launcher in `automation/browser.py` and `workers/browser_worker.py`; basic round-robin scheduler in `workers/scheduler.py` | **~35%** | No role separation in DB (`accounts` lacks `role`); no priority queueing (video priority over image); ad-hoc cooldown sleep in WebSocket handler instead of timestamp-based scheduler; no `RATE_LIMITED` state management; tight coupling to WebSocket instead of Native Messaging |
| **R5**: FFmpeg Stitching & Post-Processing | Python wrapper for FFmpeg; concat demuxer; loudness normalization; BGM mixing with volume balancing; 1080p upscale (H.264/AAC); real-time progress parsing to UI | Completely absent across the repository (0 matches for `ffmpeg` in code) | **0%** | Entire engine is missing: no concat demuxer builder, no filter graph builder, no audio normalization (`loudnorm`), no BGM mixer (`amix`), no 1080p scaler, no stdout/stderr progress parser, no `render_jobs` table |
| **R6**: Automated Test Suite & Mocks | Comprehensive pytest suite: binary framing (length-prefixed JSON), mock orchestrator (round-robin, state transitions), FFmpeg command builder & progress parser, extension schema validation | No `tests/` directory; only manual scratch test scripts in `scratch/` | **0%** | Zero pytest test files exist; no binary framing tests, no mock orchestrator tests, no FFmpeg builder tests, no schema validation tests |

---

## 2. R4 Deep Dive: Playwright & Account Rotation / Priority Scheduling

### 2.1 File Inventory & Current Implementations

1. **`playwright/browser.py`** (77 lines):
   - **`parse_proxy(proxy_str)`** (lines 6-22): Parses `host:port` or `host:port:user:pass` into Playwright proxy dictionary.
   - **`launch_persistent_chrome(profile_name, proxy_str, target_url)`** (lines 24-76):
     - Uses `p.chromium.launch_persistent_context()` with bundled Chromium.
     - Args: `"--start-maximized"`, `"--disable-extensions-except={extension_path}"`, `"--load-extension={extension_path}"`.
     - Points to `../flow-extension`.
     - Blocks execution via `while len(context.pages) > 0: time.sleep(0.5)`.
     - *Flaw*: Synchronous blocking loop intended only for manual login; not suitable for background worker management.

2. **`automation/browser.py`** (303 lines):
   - **`find_chrome_path()`** (lines 7-19): Scans Windows paths (`C:\Program Files\Google\Chrome\Application\chrome.exe`, `C:\Program Files (x86)\...`, `%LOCALAPPDATA%\...`).
   - **`enable_chrome_developer_mode(profile_name)`** (lines 21-51): Directly modifies `profiles/<profile_name>/Default/Preferences` JSON to set `extensions.ui.developer_mode = True`.
   - **`get_clean_extension_path()`** (lines 82-132): Copies `flow-extension` to `C:\Users\Public\media_ai_flow_extension`.
     - *Rationale*: Solves Chrome CLI parsing bug caused by spaces/parentheses in `d:\New folder (5)`. Dynamically bumps `manifest.json` version timestamp (`1.3.<epoch>`) to invalidate stale Chrome extension cache.
   - **`launch_manual_chrome_setup(profile_name, target_url)`** (lines 52-80): Launches system Chrome via `subprocess.Popen` with `--user-data-dir`, blocking until closed.
   - **`launch_persistent_chrome(profile_name, proxy_str, target_url)`** (lines 134-195):
     - Launches system Chrome via Playwright with `executable_path=chrome_path`.
     - `ignore_default_args=["--no-sandbox", "--enable-automation", "--disable-extensions"]`.
     - Injects anti-automation bypass: `context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")`.
   - **`verify_google_session(profile_name)`** (lines 211-256): Inspects profile's SQLite `Cookies` file for `SID`, `HSID`, `SSID`.
   - **`extract_project_id_from_history(profile_name)`** (lines 257-302): Queries profile's SQLite `History` database for Flow project UUID (`/tools/flow/project/<id>`).

3. **`workers/browser_worker.py`** (243 lines):
   - **Class `BrowserWorker`**:
     - Manages single account lifecycle (`self.state`: `OFFLINE`, `STARTING`, `IDLE`, `BUSY`, `ERROR`).
     - Threaded worker loop `_run_loop()` launches Playwright persistent context.
     - *Issue*: In line 69, calls `p.chromium.launch_persistent_context()` without `executable_path=chrome_path`, reverting to Playwright's bundled Chromium instead of the detected system Chrome binary.
     - Injects account identification: `data-media-ai-account-id` into DOM via `add_init_script` and fallback `page.evaluate()`.
     - Expects WebSocket connection from extension back to `app.py` (`/ws/extension`).
     - `execute_job(job_dict)` (lines 172-224): Sets `self.state = "BUSY"`, assigns job in SQLite DB (`assign_job_to_account`), and asynchronously transmits JSON payload over WebSocket.

4. **`workers/scheduler.py`** (90 lines):
   - **Class `JobScheduler`**:
     - `_schedule_loop()` polls `models.get_pending_jobs()` every 100ms.
     - Selects worker using `_find_idle_worker()`:
       ```python
       idle_list = [w for w in active_workers.values() if w.state == "IDLE" and w.websocket is not None]
       if not idle_list:
           return None
       if self.worker_rr_index >= len(idle_list):
           self.worker_rr_index = 0
       selected_worker = idle_list[self.worker_rr_index]
       self.worker_rr_index = (self.worker_rr_index + 1) % len(idle_list)
       ```
     - Breaks loop after dispatching 1 job per tick (`if success: break`).

5. **`database/models.py` & `database/db.py`**:
   - `accounts` table schema: `id`, `name`, `email`, `profile_path`, `proxy`, `delay`, `status` (`ACTIVE`/`INACTIVE`), `health`, `google_ok`, `flow_ok`, `gemini_ok`, `request_count`, `success_count`, `failed_count`, `last_check`, `created_at`, `server`, `project_id`.
   - `jobs` table schema: `id`, `project`, `media_type` (`image`/`video`), `prompt`, `ratio`, `model`, `status` (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`), `progress`, `result_file`, `account_id`, `error_message`, `created_at`.

### 2.2 Detailed Gap Analysis for R4

1. **Missing Operational Roles (`IMAGE_GEN` vs `VIDEO_GEN`)**:
   - `accounts` table in SQLite does not possess a `role` field.
   - Accounts cannot be assigned dedicated roles (`IMAGE_GEN` vs `VIDEO_GEN`).
   - The scheduler treats all accounts identically, failing to reserve priority accounts for Veo 3.1 Lite video generation.

2. **Absence of Priority Scheduling**:
   - The scheduler queries all `PENDING` jobs purely by `created_at ASC` (`SELECT * FROM jobs WHERE status = 'PENDING' ORDER BY created_at ASC`).
   - There is no priority ordering (e.g., `VIDEO_GEN` jobs jumping ahead of `IMAGE_GEN` jobs, or priority worker pools).
   - Video jobs and image jobs compete indiscriminately for any available worker.

3. **Flawed Round-Robin Algorithm**:
   - In `_find_idle_worker()`, `self.worker_rr_index` is incremented over a dynamic list `idle_list`. Because `len(idle_list)` changes dynamically as workers finish or take jobs, indexing into this list using a persistent pointer can cause workers to be repeatedly bypassed or starved.
   - Standard round-robin requires either a FIFO idle worker queue or dispatch tracking based on `last_dispatched_at` timestamps.

4. **Ad-hoc Cooldown Delay Handling**:
   - Cooldown is currently implemented in `app.py` lines 67-78 inside an async WebSocket handler via `threading.Thread(target=delayed_idle, args=(worker, cooldown_sec)).start()`.
   - If the application crashes, restarts, or disconnects, cooldown state is lost.
   - The scheduler itself has no concept of `cooldown_until` timestamp. Once a worker reports `IDLE`, it can be immediately re-dispatched.
   - If a job fails, the cooldown is skipped entirely (`worker.state = "IDLE"` immediately), potentially triggering immediate retry loops on rate-limited accounts.

5. **Rate Limiting & Health States**:
   - R1 & R4 require worker health states: `READY`, `BUSY`, `RATE_LIMITED`.
   - Current codebase uses: `OFFLINE`, `STARTING`, `IDLE`, `BUSY`, `ERROR`, and `ACTIVE`/`INACTIVE` in DB.
   - `RATE_LIMITED` state does not exist in code; no exponential backoff or rotation trigger on HTTP 429 / quota errors.
   - Account health is currently updated with simulated mock random values in `services/account_service.py` (`check_account_health_simulated`).

6. **IPC Protocol Decoupling**:
   - R4 specifies persistent contexts with extension loaded communicating via Chrome Native Messaging (`com.vqp.flow_bridge`), whereas `BrowserWorker` is currently coupled to WebSocket (`flow-extension/websocket.js` connecting to NiceGUI/FastAPI on port 5000/8080).

---

## 3. R5 Deep Dive: FFmpeg Stitching & Post-Processing Engine

### 3.1 File Inventory & Current Implementations

- **`services/`**: Contains only `account_service.py`. No FFmpeg service or wrapper exists.
- **Repository-wide Grep**: 0 occurrences of `ffmpeg` in any source file.
- **Status**: **100% Unimplemented**.

### 3.2 Required Specification & Architecture Breakdown

To fulfill R5 and Acceptance Criteria, an FFmpeg wrapper service must be built from the ground up:

1. **Concat Demuxer File Generator**:
   - Must generate valid concat script files formatted as:
     ```text
     ffconcat version 1.0
     file 'clip_001.mp4'
     duration 8.000000
     file 'clip_002.mp4'
     duration 8.000000
     ```
   - Must sanitize absolute Windows paths (e.g., using forward slashes `d:/...` or escaping special characters) to ensure FFmpeg parses the concat list cleanly.

2. **Filter Graph Builder (`-filter_complex`)**:
   - **1080p Upscaling & Aspect Ratio**:
     - Google Veo 3.1 Lite generates 720p clips.
     - Must upscale to 1080p (1920x1080) with high visual fidelity:
       `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2`
     - Codecs: H.264 (`-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p`) + AAC (`-c:a aac -b:a 192k`).
   - **Audio Loudness Normalization**:
     - EBU R128 two-pass or single-pass dynamic normalization (`loudnorm=I=-16:TP=-1.5:LRA=11`).
     - Must prevent clipping and ensure consistent volume across concatenated scenes.
   - **Background Music (BGM) Mixing**:
     - Optional audio track input (`-i bgm.mp3`).
     - Volume balancing: `[1:a]volume=0.25[bgm]; [0:a][bgm]amix=inputs=2:duration=first:dropout_transition=2[aout]`.
     - Must truncate or loop BGM to match exact video timeline duration.

3. **Subprocess Execution & Real-Time Progress Parsing**:
   - Launch FFmpeg with `-progress pipe:1` or `-progress pipe:2` (stdout/stderr).
   - Parse key-value progress lines:
     ```text
     frame=240
     fps=48.2
     out_time_ms=8000000
     progress=continue
     ```
   - Calculate percentage: `progress_pct = min(100.0, (out_time_ms / total_duration_ms) * 100)`.
   - Emit progress via Qt Signals (in PySide6 desktop app) or callbacks to update UI progress bars.

4. **Persistence & Data Model**:
   - Missing SQLite schema for `render_jobs` / `timeline_scenes`.
   - Need fields: `id`, `project_id`, `scene_ids`, `output_path`, `status`, `progress`, `fps`, `resolution`, `bgm_path`, `bgm_volume`, `created_at`.

---

## 4. R6 Deep Dive: Automated Test Suite & Mocks

### 4.1 Current Test Inventory

1. **`tests/` directory**: Does NOT exist.
2. **`scratch/` manual test scripts**:
   - `scratch/test_browser.py`: Manual script launching Playwright persistent context.
   - `scratch/test_launch.py`: Manual script running Chrome subprocess.
   - `scratch/test_sw.py`: Manual script checking service worker registration.
   - `scratch/test_complete_job.py`: Manual DB insert script for testing image display.
   - `scratch/validate_manifest.py`: Validates JSON parseability of `flow-extension/manifest.json`.
3. **Automated Test Runners**:
   - No `pytest.ini`, `conftest.py`, or test targets configured.

### 4.2 Required Automated Test Matrix (R6)

To meet R6 acceptance criteria, the following test modules must be implemented under `tests/`:

| Test Module | Target Functionality | Key Test Cases Required |
|-------------|----------------------|-------------------------|
| **`tests/test_native_messaging.py`** | 32-bit length-prefixed JSON binary framing | 1. Pack JSON to binary: verify 4-byte little-endian header length + UTF-8 payload.<br>2. Unpack binary to JSON: verify valid frame decoding.<br>3. Partial read / stream fragmentation handling.<br>4. Oversized payload rejection (> 1MB limit per Chrome spec).<br>5. Non-UTF8 / malformed JSON error handling. |
| **`tests/test_scheduler.py`** | Queue scheduling, account rotation, worker state | 1. Round-robin dispatch distribution across N idle workers.<br>2. Job priority: verify `VIDEO_GEN` job is dispatched before pending `IMAGE_GEN` jobs.<br>3. Role enforcement: verify `IMAGE_GEN` worker rejects `VIDEO_GEN` job and vice-versa.<br>4. Cooldown delay: verify worker is ineligible for dispatch until `cooldown_until` timestamp elapses.<br>5. Busy state: verify worker with `state != "IDLE"` is skipped.<br>6. Rate-limited state: verify worker transitions to `RATE_LIMITED` and enters backoff.<br>7. Recovery: verify worker re-enters `IDLE` after backoff expires. |
| **`tests/test_ffmpeg_engine.py`** | FFmpeg command builder, filter complex, progress parser | 1. Concat file generation: valid syntax, correctly escaped paths.<br>2. Filter graph without BGM: verify scale 1920x1080 pad and loudnorm arguments.<br>3. Filter graph with BGM: verify `amix`, volume balancing, and stream mapping.<br>4. Progress line parsing: parse `out_time_ms=...` and verify accurate percentage calculation (0% -> 50% -> 100%).<br>5. Mock render execution: run FFmpeg against synthetic test inputs (e.g. `testsrc` / `sine` filters) and confirm output file creation without needing external video files. |
| **`tests/test_extension_schema.py`** | Extension Manifest V3 & `flow_adapter_config.json` | 1. Manifest V3 validation: `manifest_version == 3`, required permissions (`nativeMessaging`, `storage`, `downloads`).<br>2. `flow_adapter_config.json` schema validation: presence of required selector keys (`prompt_box`, `generate_button`, `download_link`, `model_selector`, `ratio_options`).<br>3. Validate CSS/XPath selector formatting and non-emptiness. |

---

## 5. Technical Recommendations for Implementation

1. **Consolidate Browser & Extension Launching**:
   - Merge `playwright/browser.py` and `automation/browser.py` into a unified `automation/browser_manager.py`.
   - Retain `get_clean_extension_path()` and `enable_chrome_developer_mode()` as they solve real Windows path spacing and Chrome extension developer mode requirements.
   - Ensure `launch_persistent_context` explicitly passes `executable_path=find_chrome_path()` to use the real Chrome binary.

2. **Refactor Scheduler to Priority-Aware State Machine**:
   - Add `role` (`IMAGE_GEN`, `VIDEO_GEN`, `HYBRID`) to `accounts` table.
   - Add `priority` (integer, e.g. 10 for video, 1 for image) to `jobs` table.
   - Replace dynamic index round-robin with a timestamp-based or FIFO queue dispatch:
     - Worker maintains `cooldown_until: float` (unix epoch).
     - Worker is eligible when `state == "IDLE" and now() >= cooldown_until`.
     - Filter workers by capability (`account.role == job.media_type`).

3. **Implement FFmpeg Engine in `services/ffmpeg_service.py`**:
   - Provide a clean class `FFmpegEngine` with methods:
     - `build_concat_file(clip_paths, output_txt_path)`
     - `build_render_command(concat_txt, output_path, bgm_path=None, bgm_volume=0.2, upscale=True, normalize_audio=True)`
     - `parse_progress(line, total_duration_sec)`
     - `render_async(config, progress_callback=None, completion_callback=None)`

4. **Establish Standard `tests/` Directory**:
   - Add `pytest` configuration and test fixtures.
   - Implement unit and mock tests with zero reliance on live external servers or Google accounts.
