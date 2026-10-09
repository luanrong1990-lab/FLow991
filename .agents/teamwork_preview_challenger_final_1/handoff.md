# Phase 2 Adversarial Coverage Hardening Audit: Backend, Automation & Engine Track

## Verdict: REQUEST_CHANGES: Gaps Found

---

## 1. Observation

A systematic white-box coverage audit was performed comparing the production implementation files in `database/`, `automation/`, `workers/`, and `services/` against the test suites in `tests/`.

### Track 1: Database & Models (`database/db.py`, `database/models.py` vs `tests/test_database.py`, `tests/test_queue_concurrency.py`)
1. **Uncalled Database Model Functions**:
   In `database/models.py`, 47 functions are defined. Grep searches across all files in `tests/` revealed zero test calls for the following 10 functions:
   - `models.cancel_job(job_id: str) -> bool` (`database/models.py:809`)
   - `models.retry_job(job_id: str) -> bool` (`database/models.py:819`)
   - `models.set_job_priority(job_id: str, priority: int) -> bool` (`database/models.py:799`)
   - `models.delete_job(job_id: str) -> bool` (`database/models.py:833`)
   - `models.delete_render_job(job_id: int) -> bool` (`database/models.py:1189`)
   - `models.get_prompt_batches(limit: int = 50) -> List[Dict[str, Any]]` (`database/models.py:418`)
   - `models.increment_batch_completed_count(batch_id: int) -> bool` (`database/models.py:427`)
   - `models.update_scene(scene_id: str, ...)` (`database/models.py:913`)
   - `models.update_account_server(account_id: str, server_status: int)` (`database/models.py:226`)
   - `models.update_account_stats(account_id: str, ...)` (`database/models.py:234`)
2. **Missing Transaction Rollback Verification**:
   Functions `create_prompt_batch` (`models.py:369`), `claim_next_job` (`models.py:554`), `complete_job` (`models.py:705`), `fail_job` (`models.py:765`), and `feed_scene_to_video_job` (`models.py:1012`) implement explicit `try ... BEGIN TRANSACTION / BEGIN IMMEDIATE ... except: conn.rollback(); raise`.
   A search across all test suites for `rollback` yielded `No results found`. There are zero unit or adversarial tests simulating an exception mid-transaction to verify that partial writes are discarded.
3. **Verified Features**:
   - WAL Mode: `tests/test_database.py:21` (`test_init_db_creates_all_tables_and_wal`) verifies `PRAGMA journal_mode=WAL` and index creation.
   - Safe Migrations: `tests/test_database.py:60` (`test_safe_migration_on_legacy_db`) verifies non-destructive schema backfilling on legacy SQLite databases.
   - Regex Prefix Stripping: `tests/test_database.py:272` & `316` verify prefix removal across hierarchical numbers (`1.1.`), bracketed hashes (`[Shot #42] - `), hashes vs comments (`#1 ` vs `# Comment`), and normal numbers in prose (`3 cats playing in garden`).
   - Atomic Concurrency: `tests/test_queue_concurrency.py:77` verifies 20 concurrent threads claiming 50 jobs with zero duplicate claims.

### Track 2: Automation & Native Host (`automation/native_host.py`, `browser.py`, `install_host.py` vs `tests/test_native_messaging.py`, `tests/test_m2_adversarial.py`, `tests/test_extension_schema.py`)
1. **Zero Test Coverage for `automation/browser.py`**:
   Grep search for `launch_persistent_chrome`, `find_chrome_path`, `get_clean_extension_path`, `parse_proxy`, and `enable_chrome_developer_mode` across `tests/` yielded `No results found`.
   `automation/browser.py` is never imported or tested in any test suite. Consequently, Playwright launcher arguments:
   ```python
   "ignore_default_args": ["--no-sandbox", "--enable-automation", "--disable-extensions"],
   "args": [
       "--start-maximized",
       "--disable-blink-features=AutomationControlled",
       f"--disable-extensions-except={extension_path}",
       f"--load-extension={extension_path}"
   ],
   ```
   as well as anti-automation script injection (`Object.defineProperty(navigator, 'webdriver', {get: () => undefined})`) and proxy parsing logic (`parse_proxy`) have zero test coverage.
2. **Verified Features**:
   - 32-bit Framing & uint32 Boundaries: `tests/test_native_messaging.py:48-206` and `tests/test_m2_adversarial.py:35-226` verify little-endian `<I`, 0-length messages, exact 1MB (1,048,576 bytes), 1MB + 1 byte rejection, uint32 0xFFFFFFFF, 31st high-bit set (0x80000000), 1/3-byte prefix truncation, early/late EOF, non-UTF-8 bytes, pipelined messages, and embedded null bytes.
   - Commands & Responses: `generate_image`, `generate_video`, `enter_setup_mode`, `query_status`, `status_update`, `success`, and `error` transitions with SQLite job updates are tested in `tests/test_native_messaging.py`.
   - Windows Registry Installer: `tests/test_extension_schema.py:215` (`test_install_host_execution`) verifies `install()` creates `host_launcher.bat`, generates `com.vqp.flow_bridge.json`, and derives the 32-character Chrome extension ID.

### Track 3: Workers & Scheduler (`workers/browser_worker.py`, `workers/scheduler.py` vs `tests/test_scheduler.py`, `tests/test_scheduler_adversarial.py`)
1. **Zero Direct Unit Test Coverage for `BrowserWorker`**:
   In `tests/test_scheduler.py` and `tests/test_scheduler_adversarial.py`, all tests instantiate `MockWorker` and `MockAdversarialWorker`. The real `BrowserWorker` class (`workers/browser_worker.py:10`) is never instantiated or tested.
   Specifically, the real implementation logic in `BrowserWorker`:
   - `is_ready(current_time)`: state checks, `active_job_id` locking, and auto-resumption from `RATE_LIMITED` to `IDLE` with DB status updates (`workers/browser_worker.py:308`).
   - `on_job_completed(job_id, result_file, cooldown_seconds)`: stats increments and cooldown calculations (`workers/browser_worker.py:248`).
   - `on_job_rate_limited(job_id, error_message, backoff_seconds)`: backoff cooldown and error logging (`workers/browser_worker.py:269`).
   - `on_job_failed(job_id, error_message)`: automatic detection of rate-limiting via substring patterns (`"429"`, `"quota"`, `"rate limit"`) (`workers/browser_worker.py:286`).
   - `execute_job(job_dict)`: payload serialization with system setting fallbacks (`workers/browser_worker.py:174`).
   remains unexercised by direct unit tests.
2. **Verified Features**:
   - Round-Robin Dispatch: `tests/test_scheduler.py:93` and `tests/test_scheduler_adversarial.py:381` verify balanced cyclic dispatch across idle workers and independent cyclic pointers for segregated roles (`IMAGE_GEN` vs `VIDEO_GEN`).
   - Priority Preemption: `tests/test_scheduler.py:174` and `tests/test_scheduler_adversarial.py:93` verify Veo 3.1 Lite video jobs (priority 10) preempt earlier queued image jobs (priority 0) even under massive 500-job queue saturation, and priority 20 preempts priority 10.
   - Timestamp Cooldown Enforcement: `tests/test_scheduler.py:308` and `tests/test_scheduler_adversarial.py:241` verify sub-millisecond precision (locked at `T - 0.001`, unlocked at `T`) and staggered multi-worker cooldowns (10s, 20s, 30s).
   - Rate-Limit Backoff Recovery: `tests/test_scheduler.py:353` and `tests/test_scheduler_adversarial.py:319` verify status transition to `RATE_LIMITED`, blocking during backoff, and automatic recovery to `READY`/`BUSY` once the timestamp expires.

### Track 4: FFmpeg Engine (`services/ffmpeg_service.py` vs `tests/test_ffmpeg_engine.py`, `tests/test_ffmpeg_adversarial.py`)
1. **Verified Features (Zero Gaps)**:
   - Concat Demuxer: `tests/test_ffmpeg_engine.py:48-132` and `tests/test_ffmpeg_adversarial.py:41-89` verify `ffconcat version 1.0` headers, `file '<path>'` formatting, forward slash normalization, single-quote escaping (`'\\''`), Unicode/CJK/emoji paths, and shell metacharacters.
   - Null Video Filter: `tests/test_ffmpeg_engine.py:237` and `tests/test_ffmpeg_adversarial.py:133` verify that when `upscale_1080p=False` and BGM is enabled, `[0:v]null[v_out]` is used and the invalid `copy` filter is avoided.
   - Optional Audio `[0:a?]`: `tests/test_ffmpeg_engine.py:263` verifies `optional_audio=True` produces `[0:a?]` and `silent_video=True`/`has_audio=False` cleanly bypasses `[0:a]` to prevent stream collision with silent AI video clips.
   - 1080p Upscale & Letterbox Pad: `tests/test_ffmpeg_engine.py:141` and `tests/test_ffmpeg_adversarial.py:153` verify `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2` across 16:9, 9:16, and 1:1 aspect ratios.
   - EBU R128 Loudnorm: `tests/test_ffmpeg_engine.py:161` verifies `loudnorm=I=-16:TP=-1.5:LRA=11`.
   - BGM Mixing with Volume Ducking: `tests/test_ffmpeg_engine.py:186`, `221`, and `tests/test_ffmpeg_adversarial.py:169` verify `[0:a]volume=1.0[voice]`, `[1:a]volume=0.2[bgm]`, `amix=inputs=2:duration=first:dropout_transition=2[mixed]`.
   - Stdout Progress Parsing: `tests/test_ffmpeg_engine.py:318-400` and `tests/test_ffmpeg_adversarial.py:198-269` verify `out_time_us`, `out_time_ms`, `out_time=HH:MM:SS.ff`, `progress=end`, stderr fallback, boundary clamping, 0 duration, negative duration, corrupted stdout lines, and SQLite update throttling.

---

## 2. Logic Chain

1. The assignment mandate required a white-box audit of source code vs test suites to verify all 39+ model functions, prompt prefix sanitization regexes, WAL mode, transaction rollbacks, concurrent claiming, binary framing, uint32 checks, registry installer, Playwright launcher args, round-robin dispatch, priority preemption, cooldown enforcement, rate-limit backoff recovery, and FFmpeg filter/progress capabilities.
2. In Track 1, 10 model functions in `database/models.py` (`cancel_job`, `retry_job`, `set_job_priority`, `delete_job`, `delete_render_job`, `get_prompt_batches`, `increment_batch_completed_count`, `update_scene`, `update_account_server`, `update_account_stats`) are never invoked by any automated test. Furthermore, while rollback code exists in 5 transactional functions, no test verifies rollback behavior under an injected error or database constraint failure.
3. In Track 2, `automation/browser.py` has no unit tests. The Playwright launcher argument assembly (`launch_persistent_chrome`), anti-automation init script (`navigator.webdriver`), and proxy parsing (`parse_proxy`) have zero test coverage.
4. In Track 3, `workers/browser_worker.py` contains the real `BrowserWorker` class with lifecycle, cooldown enforcement, and heuristic rate-limit detection methods. The test suites solely test `MockWorker` and `MockAdversarialWorker`, leaving the production `BrowserWorker` class completely unverified.
5. In Track 4, all 7 specified FFmpeg engine capabilities (concat demuxer, null video filter, optional audio `[0:a?]`, 1080p upscale pad, EBU R128 loudnorm, BGM mixing with ducking, and stdout progress parsing) are thoroughly verified with zero gaps.
6. Because significant functional and adversarial coverage gaps exist in Tracks 1, 2, and 3, an approval verdict cannot be granted.

---

## 3. Caveats

- Operating within the Windows background environment constraint, `run_command` was strictly prohibited to prevent indefinite interactive blocking. Verification was conducted through comprehensive static analysis, line-by-line code tracing, and pattern searches (`view_file` and `grep_search`).
- Some functions (such as `update_account_stats` or `assign_job_to_account`) are called indirectly by mock classes or higher-level workflows, but lack dedicated unit tests covering their direct return values, boundary cases, and error handling.
- `automation/browser.py` launches a real browser GUI via Playwright; testing it in CI/headless unit tests requires mock parameter extraction tests rather than opening real Chrome windows.

---

## 4. Conclusion

**Verdict**: `REQUEST_CHANGES: Gaps Found`

### Actionable Remediation Requirements:
1. **Track 1 Remediation**:
   - Add unit tests for the 10 uncalled model functions: `cancel_job`, `retry_job`, `set_job_priority`, `delete_job`, `delete_render_job`, `get_prompt_batches`, `increment_batch_completed_count`, `update_scene`, `update_account_server`, and `update_account_stats`.
   - Add transaction rollback tests simulating exceptions mid-operation in `create_prompt_batch`, `claim_next_job`, `complete_job`, `fail_job`, and `feed_scene_to_video_job` to confirm that partial writes are discarded.
2. **Track 2 Remediation**:
   - Add a test suite (e.g. `tests/test_browser_launcher.py`) that tests `parse_proxy`, `find_chrome_path`, `enable_chrome_developer_mode`, `get_clean_extension_path`, and inspects the dictionary passed to Playwright's `launch_persistent_context` (verifying `--disable-blink-features=AutomationControlled`, `--load-extension`, `--disable-extensions-except`, and `navigator.webdriver` removal) using mock Playwright objects.
3. **Track 3 Remediation**:
   - Add unit tests for the actual `BrowserWorker` class in `workers/browser_worker.py`: test `is_ready()`, `on_job_completed()`, `on_job_rate_limited()`, `on_job_failed()` with automatic 429/quota detection regexes, and `execute_job()` payload construction.

---

## 5. Verification Method

Once the proposed test cases are added, the coverage and invariants can be independently validated via:

```powershell
# 1. Run database & concurrency tests
pytest tests/test_database.py tests/test_queue_concurrency.py -v

# 2. Run native messaging & browser launcher tests
pytest tests/test_native_messaging.py tests/test_m2_adversarial.py -v

# 3. Run scheduler & browser worker tests
pytest tests/test_scheduler.py tests/test_scheduler_adversarial.py -v

# 4. Run FFmpeg engine & adversarial tests
pytest tests/test_ffmpeg_engine.py tests/test_ffmpeg_adversarial.py -v

# 5. Full test suite execution
pytest tests/ -v
```

Invalidation condition: If all 47 model functions have direct unit tests, transaction rollbacks are verified via error injection, `automation/browser.py` launcher arguments are tested, and `workers/browser_worker.py` methods are tested directly, the verdict transitions to `APPROVE: No Remaining Gaps`.
