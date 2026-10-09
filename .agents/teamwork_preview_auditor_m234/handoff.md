# Forensic Audit Report: Milestones M2, M3, M4

**Auditor**: teamwork_preview_auditor_m234  
**Date**: 2026-09-08T04:24:00Z  
**Target**: M2 (Chrome Extension & Native Messaging), M3 (Browser Manager & Scheduler), M4 (FFmpeg Video Engine)  
**Integrity Mode**: Development (from `ORIGINAL_REQUEST.md` line 8)  
**Verdict**: **CLEAN**

---

## 1. Observation

Direct code inspections across all audit targets revealed genuine, non-facade implementations:

### M2: Chrome Extension & Native Messaging Host
- **`automation/native_host.py`**:
  - Binary framing protocol (lines 46–132): `read_message` explicitly reads a 4-byte length prefix using `struct.unpack('<I', raw_length)[0]`, strictly enforces `MAX_MESSAGE_SIZE = 1024 * 1024` (1MB Chrome native limit), and enters a chunked read loop (`while bytes_read < msg_length: stream.read(...)`) to guarantee complete payload reception before decoding UTF-8 JSON. `send_message` computes byte length `len(encoded_payload)` (rather than string character length) and prefixes it with `struct.pack('<I', payload_len)` followed by immediate `stream.flush()`.
  - Command handling & DB sync (lines 134–276): Dispatches `generate_image`, `generate_video`, `enter_setup_mode`, and `query_status`, while incoming responses (`status_update`, `success`, `error`) invoke `database.models` methods `update_job_status`, `complete_job`, and `fail_job` (including rate-limit detection and backoff).
- **`automation/install_host.py`**:
  - Implements Chrome's exact deterministic extension ID algorithm in `compute_extension_id` (lines 40–50): base64 decodes RSA SPKI public key, hashes with SHA-256, extracts the first 16 bytes (32 nibbles), and translates each nibble (0–15) to `a`–`p`.
  - Writes launcher script `automation/host_launcher.bat` and host manifest `automation/com.vqp.flow_bridge.json` with `type: "stdio"` and `allowed_origins: ["chrome-extension://<id>/"]`.
  - Registers manifest in Windows Registry at `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge` via Python `winreg`.
- **`extension/` (Manifest V3)**:
  - `extension/manifest.json`: Declares `manifest_version: 3`, permissions (`["nativeMessaging", "storage", "downloads", "tabs", "activeTab"]`), service worker `background.js`, content scripts (`overlay.js`, `executor.js`, `content.js`), and stable RSA `key`.
  - `extension/background.js`: Connects via `chrome.runtime.connectNative("com.vqp.flow_bridge")`, bi-directionally routes messages between native host and active Google Flow tabs, and listens to `chrome.downloads.onChanged` to notify the Python host upon download completion with actual file paths.
  - `extension/overlay.js`: Complete visual Guided Mapping engine with `SelectorExtractor` (filtering dynamic hashes and transient CSS classes, deriving unique CSS selectors and hierarchical XPath with nth-of-type disambiguation) and floating `RuntimeStatusHUD`.
  - `extension/executor.js`: Multi-strategy element resolution (CSS -> XPath -> Fallback heuristics), `clearAndTypePrompt` supporting Lexical/React `contenteditable` editors via `execCommand` and input event lifecycle, and polling for generated download links.
  - `extension/flow_adapter_config.json`: Canonical schema defining `prompt_box`, `generate_button`, `download_link`, `model_selector` (Nano Banana 2, Veo 3.1 Lite), and `ratio_options` (16:9, 1:1, 9:16).

### M3: Browser Manager & Priority Scheduler
- **`automation/browser.py`**:
  - Discovers local Google Chrome binary (`C:\Program Files\Google\Chrome\Application\chrome.exe`, LocalAppData, etc.) with bundled Chromium fallback (`find_chrome_path`).
  - Directly modifies Chrome profile `Preferences` JSON to set `extensions.ui.developer_mode = True`.
  - Launches Playwright persistent context (`p.chromium.launch_persistent_context`) with custom profile path, `--disable-blink-features=AutomationControlled`, `--load-extension=<extension>`, `--disable-extensions-except=<extension>`, and init script removing `navigator.webdriver`.
  - Verifies Google sessions by reading SQLite `Cookies` (`SID`, `HSID`, `SSID`) and Flow project IDs from SQLite `History`.
- **`workers/browser_worker.py`**:
  - `BrowserWorker` encapsulates thread lifecycle per account, injects `account_id` into DOM, handles execution via extension IPC, and manages `on_job_completed`, `on_job_rate_limited` (429/quota detection with backoff), and `on_job_failed`.
- **`workers/scheduler.py`**:
  - `JobScheduler` implements thread-safe lifecycle (`start`, `stop`, `is_running`) using `threading.RLock()` and `threading.Event()`.
  - `dispatch_next` queries `models.get_pending_jobs(priority_first=True)`: Veo 3.1 Lite video jobs (priority 10) preempt image jobs (priority 0).
  - Routes jobs based on role: `video` -> `VIDEO_GEN`, `image` -> `IMAGE_GEN`.
  - Filters eligible workers: checks `models.is_account_ready(acc)` (`cooldown_until <= now` and active status). Automatically recovers workers from `RATE_LIMITED` to `READY` when cooldown expires.
  - Round-robin selection (`_select_round_robin_worker`) ensures balanced cyclic dispatch across workers of each role.
  - Atomically claims jobs via `models.claim_next_job` using SQLite `BEGIN IMMEDIATE` transactions to prevent race conditions.

### M4: FFmpeg Video Post-Processing Engine
- **`services/ffmpeg_service.py`**:
  - Strict concat demuxer path escaping (`escape_concat_path`, lines 53–68): replaces Windows backslashes with forward slashes and escapes single quotes as `'\''` to output `file '<path>'`.
  - Concat demuxer generator (`generate_concat_file`): writes `ffconcat version 1.0` header followed by escaped clip paths.
  - 1080p scaling and aspect-ratio padding (`build_video_filter`, lines 257–270): generates `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2`.
  - EBU R128 audio loudness normalization: `loudnorm=I=-16:TP=-1.5:LRA=11`.
  - Background music mixing filter graph (`build_filter_graph`, lines 271–363): builds complex multi-input graph `[0:v]...[v_out]; [0:a]volume={voice_volume}[voice]; [1:a]volume={bgm_volume}[bgm]; [voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[mixed]; [mixed]loudnorm=...[a_out]` with `-map [v_out] -map [a_out]`.
  - Command builder (`build_render_command`, lines 368–435): includes `-y -nostats -progress pipe:1 -f concat -safe 0 -i <concat>`, `-c:v libx264 -c:a aac -pix_fmt yuv420p -r <fps>`.
  - Real-time progress parsing (`parse_progress_line` & `process_progress_stream`, lines 440–556): parses `progress=end` (100.0%), `out_time_us`, `out_time_ms`, `out_time`, and stderr `time=` fallback; throttles database progress writes to SQLite `render_jobs` to avoid lock contention.
  - Process execution (`render_timeline`, lines 561–766): executes `subprocess.Popen` with non-blocking daemon thread reading `stderr` (preventing pipe buffer deadlocks) while main thread consumes `stdout` progress lines.
  - Cancellation (`cancel_render`): safely terminates/kills active subprocess and updates database status to `CANCELLED`.
  - High-level orchestrator (`render_project_timeline`): stitches all completed project scenes in strict numerical sequence directly from SQLite.

### Automated Test Suites
- `tests/test_native_messaging.py` (13 tests): Covers roundtrip pack/unpack, little-endian header byte order, empty payloads, UTF-8 multi-byte characters, 1MB boundaries, stream EOF/truncation, host commands, and DB updates.
- `tests/test_extension_schema.py` (13 tests): Covers Manifest V3 structure, required permissions, service worker, content scripts, RSA key extension ID derivation, flow adapter config schema, and registry installer.
- `tests/test_scheduler.py` (7 tests): Covers cyclic round-robin distribution, priority preemption (Veo 3.1 Lite over image jobs), role segregation, timestamp cooldown enforcement, 429 rate-limit backoff, and lifecycle.
- `tests/test_ffmpeg_engine.py` (22 tests): Covers concat escaping (spaces, single quotes, backslashes), filter graph syntax, EBU R128 loudness normalization, BGM mixing with volume ducking, progress stream parsing, mock subprocess execution, failure diagnostics capture, and project timeline rendering.

---

## 2. Logic Chain

1. **Rule Baseline**: Under Development Mode (`ORIGINAL_REQUEST.md`), prohibited patterns comprise:
   - Hardcoded test results / expected outputs bypassing real logic.
   - Facade implementations (empty methods, constant returns, unimplemented stubs).
   - Fabricated verification artifacts or pre-populated result files.
2. **Analysis of M2**:
   - `automation/native_host.py` implements true 32-bit little-endian binary unpacking (`struct.unpack('<I')`) and streaming buffer reads. No fixed inputs or predetermined strings are assumed.
   - `extension/overlay.js` and `extension/executor.js` contain full DOM traversal, selector extraction, Lexical editor keyboard events, and polling loops.
   - Registry registration and key derivation in `automation/install_host.py` adhere to the Google Chrome extension ID specification without mock shortcuts.
3. **Analysis of M3**:
   - Playwright context initialization in `automation/browser.py` properly sets anti-automation flags and loads unpacked extensions.
   - `workers/scheduler.py` coordinates real SQLite transaction queries (`BEGIN IMMEDIATE`) with timestamp cooldown arithmetic (`time.time()`) and cyclic worker rotation.
4. **Analysis of M4**:
   - `services/ffmpeg_service.py` builds authentic FFmpeg filter graphs, escapes arbitrary file system paths, parses real-time microsecond progress timestamps, and prevents pipe deadlocks with multi-threaded stderr consumption.
5. **Absence of Prohibited Artifacts**:
   - Workspace search revealed no fake pre-populated test results or artificial attestation files.
   - Unit and integration tests in `tests/` execute genuine code paths against temporary isolated databases (`temp_db`) and simulated byte streams.
6. **Verdict Deduction**: Every audited milestone authenticates genuine architectural implementation with zero evidence of cheating, hardcoded facades, or integrity circumvention.

---

## 3. Caveats

- **Live Flow Web Interaction**: Tests for browser automation utilize Playwright persistent context launchers and mock orchestrators. Live DOM interaction on `https://labs.google/flow` requires live Google account authentication and active network access, which was not executed during this static forensic audit.
- **External FFmpeg Binary**: In environments where FFmpeg is not installed in the system PATH, the FFmpeg engine falls back to configured binary paths; unit tests appropriately utilize mock process fixtures (`patch("subprocess.Popen")`) to verify command lines and progress stream parsing without requiring external FFmpeg binaries.

---

## 4. Conclusion

**Verdict: CLEAN**

No integrity violations, facade implementations, or hardcoded test shortcuts were detected. All components across M2, M3, and M4 are fully and genuinely implemented according to the specifications in `ORIGINAL_REQUEST.md` and `PROJECT.md`.

---

## 5. Verification Method

To independently verify the test suite and implementations:
```bash
# Run the test suite across all audited modules
pytest tests/test_native_messaging.py tests/test_extension_schema.py tests/test_scheduler.py tests/test_ffmpeg_engine.py -v

# Inspect implementation files directly
# M2: automation/native_host.py, automation/install_host.py, extension/manifest.json, extension/overlay.js, extension/executor.js
# M3: automation/browser.py, workers/browser_worker.py, workers/scheduler.py
# M4: services/ffmpeg_service.py
```

Invalidation conditions:
- Any test failing when running pytest on the aforementioned targets.
- Discovery of any hardcoded output branch bypassing computation in `native_host.py`, `scheduler.py`, or `ffmpeg_service.py`.
