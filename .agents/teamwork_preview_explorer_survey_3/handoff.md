# Handoff Report: Survey of R4, R5, R6

**Author**: `teamwork_preview_explorer_survey_3`  
**Recipient**: `teamwork_preview_orchestrator_1` (Conversation ID: `c24ef2c5-e625-4967-8e69-0738cb710185`)  
**Type**: Hard Handoff (Task complete)  
**Detailed Report**: `d:/New folder (5)/.agents/teamwork_preview_explorer_survey_3/survey_report.md`

---

## 1. Observation

### 1.1 R4 (Playwright & Account Rotation / Priority Scheduling)
- **`playwright/browser.py`** (lines 37-51):
  ```python
  with sync_playwright() as p:
      extension_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "flow-extension"))
      context = p.chromium.launch_persistent_context(
          user_data_dir=profile_path,
          headless=False,
          args=[
              "--start-maximized",
              f"--disable-extensions-except={extension_path}",
              f"--load-extension={extension_path}"
          ],
          proxy=proxy_config
      )
  ```
  This launches Playwright's bundled Chromium (not system Chrome), points to `flow-extension`, and blocks execution with `while len(context.pages) > 0: time.sleep(0.5)`.
- **`automation/browser.py`** (lines 93-95, 155-170):
  - Copies `flow-extension` to `C:\Users\Public\media_ai_flow_extension` to bypass Windows path spacing/parenthesis bugs in `d:\New folder (5)`.
  - Implements `launch_persistent_chrome` passing `executable_path=chrome_path` with anti-automation bypass `Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`.
  - Implements `enable_chrome_developer_mode(profile_name)` writing `extensions.ui.developer_mode = True` to `profiles/<profile>/Default/Preferences`.
- **`workers/browser_worker.py`** (lines 10-18, 69-83):
  - `BrowserWorker` maintains worker state: `"OFFLINE"`, `"STARTING"`, `"IDLE"`, `"BUSY"`, `"ERROR"`.
  - In `_run_loop()`, launches Playwright context using bundled Chromium (omitting `executable_path`).
  - Injects `data-media-ai-account-id` into the DOM and waits for WebSocket connection from the extension (`app.py` `/ws/extension`).
  - `execute_job(job_dict)` (lines 178-216) sets `self.state = "BUSY"` and dispatches JSON payload via WebSocket.
- **`workers/scheduler.py`** (lines 35-60):
  - `_schedule_loop()` runs in a daemon thread, polling `models.get_pending_jobs()`.
  - `_find_idle_worker()` selects workers from `idle_list = [w for w in active_workers.values() if w.state == "IDLE" and w.websocket is not None]` using modulo index `self.worker_rr_index = (self.worker_rr_index + 1) % len(idle_list)`.
  - Dispatches only 1 job per tick (`if success: break`).
- **`database/db.py`** (lines 19-38, 42-56):
  - `accounts` table contains columns: `id`, `name`, `email`, `profile_path`, `proxy`, `delay`, `status` (`'INACTIVE'`, `'ACTIVE'`), `health`, `google_ok`, `flow_ok`, `gemini_ok`, `request_count`, `success_count`, `failed_count`, `last_check`, `created_at`, `server`, `project_id`.
  - There is NO `role` column (`IMAGE_GEN` vs `VIDEO_GEN`).
  - There is NO `priority` column in `jobs`.
- **`app.py`** (lines 66-78):
  - Cooldown delay is triggered on completion in an ad-hoc thread:
    ```python
    def delayed_idle(w, delay_time):
        w.state = f"DELAY ({delay_time}s)"
        time.sleep(delay_time)
        w.state = "IDLE"
        w.active_job_id = None
    threading.Thread(target=delayed_idle, args=(worker, cooldown_sec), daemon=True).start()
    ```

### 1.2 R5 (FFmpeg Stitching & Post-Processing Engine)
- Directory inspection: `services/` contains ONLY `account_service.py` (5025 bytes).
- Pattern search: Ripgrep for `ffmpeg` across `d:/New folder (5)` returned zero results outside `ORIGINAL_REQUEST.md`.
- Concat demuxer builder: Not present.
- Filter graph builder (scale, pad, loudnorm, amix): Not present.
- Audio loudness normalization: Not present.
- BGM mixing and volume ducking: Not present.
- 1080p upscaling: Not present.
- Subprocess progress parser (`-progress pipe:1` or stderr parser): Not present.
- Database render tracking: No `render_jobs` table exists in `database/db.py`.

### 1.3 R6 (Automated Test Suite & Mocks)
- Directory inspection: `tests/` directory does not exist in the project root.
- Pattern search: Only `scratch/test_browser.py`, `scratch/test_launch.py`, `scratch/test_sw.py`, and `scratch/test_complete_job.py` exist, which are ad-hoc manual scripts.
- Unit tests for Native Messaging binary framing (pack/unpack length-prefixed JSON): Not present.
- Mock orchestrator tests (round-robin distribution, priority scheduling, state transitions): Not present.
- FFmpeg command builder unit tests (concat demuxer syntax, filter graph syntax, progress parsing): Not present.
- Extension schema validation tests (`flow_adapter_config.json`, Manifest V3 permissions): Not present.

---

## 2. Logic Chain

1. **R4 Assessment**:
   - *Observation*: `accounts` table in `database/db.py` contains `id, name, email, profile_path, proxy, delay, status, health...` but lacks `role` (`IMAGE_GEN` vs `VIDEO_GEN`).
   - *Observation*: `workers/scheduler.py` queries `get_pending_jobs()` by `created_at ASC` and dispatches to any idle worker regardless of job media type or account capability.
   - *Logic*: Without a `role` column in the database and without filtering/priority sorting in the scheduler, dedicated account rotation and priority scheduling for Veo 3.1 Lite (as required in R4) cannot function.
   - *Observation*: Cooldown is implemented via `time.sleep` in a UI/WebSocket callback thread in `app.py`.
   - *Logic*: The scheduler itself does not track worker cooldown timestamps (`cooldown_until`). A worker can be erroneously re-dispatched if its state becomes `IDLE` prematurely, and failed jobs skip cooldown entirely.

2. **R5 Assessment**:
   - *Observation*: Searching the codebase for `ffmpeg` yielded 0 hits, and `services/` only contains `account_service.py`.
   - *Logic*: The entire video stitching, audio normalization, BGM mixing, 1080p upscaling, and progress parsing pipeline mandated by R5 is completely unwritten (0% implementation).

3. **R6 Assessment**:
   - *Observation*: `tests/` does not exist; no pytest test files exist in the repository.
   - *Logic*: Automated verification cannot pass acceptance criteria without authoring the full suite under `tests/` covering binary framing, scheduler orchestration, FFmpeg command generation, and extension config schema.

---

## 3. Caveats

1. **Operating System and Chrome Path**: The host environment is Windows. Chrome paths in `automation/browser.py` assume standard installation directories (`C:\Program Files\Google\Chrome\...`). If Chrome is installed in a non-standard location or portable folder, discovery relies on fallback to Playwright bundled Chromium.
2. **Terminal Execution Access**: Executing terminal commands via `run_command` timed out waiting for user confirmation during survey. All findings in this report are based on local filesystem inspection, static code analysis, and syntax verification without executing live browser automation or external API calls.
3. **Dual Extension Artifacts**: The workspace contains both `extension/` and `flow-extension/`. `flow-extension` is the active extension currently loaded by `automation/browser.py`, while `extension/` is a smaller stub. Neither currently implements Chrome Native Messaging (`chrome.runtime.connectNative`).

---

## 4. Conclusion

1. **R4 (Account Rotation & Priority Scheduling)** is **~35% implemented**:
   - Browser launching and basic worker state tracking exist in `automation/browser.py` and `workers/browser_worker.py`.
   - Critical missing features: Account operational roles (`IMAGE_GEN` vs `VIDEO_GEN`), priority queue ordering (Veo 3.1 Lite video priority over image batches), deterministic timestamp-based cooldowns (`cooldown_until`), and rate-limit backoff handling.
2. **R5 (FFmpeg Stitching & Post-Processing Engine)** is **0% implemented**:
   - Must create `services/ffmpeg_service.py` with concat demuxer generation, filter graph construction (`scale`, `pad`, `loudnorm`, `amix`), asynchronous execution with progress parsing, and `render_jobs` database persistence.
3. **R6 (Automated Test Suite & Mocks)** is **0% implemented**:
   - Must create `tests/` containing `test_native_messaging.py`, `test_scheduler.py`, `test_ffmpeg_engine.py`, and `test_extension_schema.py`.

---

## 5. Verification Method

To independently verify the observations and gaps noted in this report:

1. **Inspect Account Schema & Models**:
   - Inspect `database/db.py` (lines 19-38) to verify that `accounts` table definition has no `role` column.
   - Inspect `database/models.py` (lines 176-183) to verify that `get_pending_jobs()` performs no priority ordering.
2. **Inspect Scheduler & Worker Code**:
   - Inspect `workers/scheduler.py` (lines 50-60) to verify that `_find_idle_worker()` only checks `w.state == "IDLE"` with no capability/role matching.
   - Inspect `workers/browser_worker.py` (lines 69-82) to verify Playwright persistent launch arguments.
3. **Verify Absence of FFmpeg**:
   - Run grep search for `ffmpeg` across the workspace:
     `Get-ChildItem -Recurse -File | Select-String "ffmpeg"` (should only return `ORIGINAL_REQUEST.md`).
   - Inspect `services/` directory to verify only `account_service.py` exists.
4. **Verify Absence of Test Suite**:
   - Inspect project root to verify `tests/` directory is absent.
   - Inspect `scratch/` to confirm scripts are manual execution tests rather than pytest unit tests.
