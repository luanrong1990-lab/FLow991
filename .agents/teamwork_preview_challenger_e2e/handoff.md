# 5-Component Handoff Report: Adversarial Challenge of E2E Integration Suite

**Agent**: `teamwork_preview_challenger_e2e`  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_challenger_e2e`  
**Date**: 2026-09-08  
**Task Type**: Hard Handoff (Adversarial Verification Complete)  
**Verdict**: **REQUEST_CHANGES**

---

## 1. Observation

Direct code inspection of `tests/test_integration.py`, `services/ffmpeg_service.py`, `database/db.py`, `database/models.py`, and `workers/scheduler.py` revealed the following exact facts:

### A. Mock Process Fidelity
- In `tests/test_integration.py` (lines 343–365, 594–598):
  ```python
  simulated_stdout_lines = (
      "out_time_us=6000000\n"
      "out_time_us=12000000\n"
      "out_time_us=18000000\n"
      "out_time_us=24000000\n"
      "progress=end\n"
  )
  ...
  mock_proc = MagicMock()
  mock_proc.returncode = 0
  mock_proc.stdout = io.StringIO(simulated_stdout_lines)
  mock_proc.stderr = io.StringIO("")
  ```
  In Scenario 3 (lines 578–598):
  ```python
  simulated_stderr = (
      "[concat @ 0000021a8] Line 2: unknown keyword 'invalid_header'\n"
      "[concat @ 0000021a8] Impossible to open 'corrupted_or_missing_clip.mp4'\n"
      "corrupted_or_missing_clip.mp4: No such file or directory\n"
  )
  mock_proc.returncode = 1
  mock_proc.stderr = io.StringIO(simulated_stderr)
  ```
- In `services/ffmpeg_service.py`:
  - `parse_progress_line` (lines 506–513) parses `out_time_us=<microseconds>` and `progress=end` (lines 503–504) returning percentage floats.
  - Subprocess stderr lines are captured via background thread `capture_stderr` and logged into `render_jobs.error_message`.
  - Subprocess cancellation invokes `proc.terminate()` (line 824), verified in Scenario 6 (`mock_process.terminate.assert_called_once()`).

### B. Resource Leakage & Concat Demuxer Lifecycle
- In `services/ffmpeg_service.py` (lines 809–814):
  ```python
  finally:
      if concat_file and os.path.exists(concat_file) and not opts.get("keep_temp_files", False):
          try:
              os.remove(concat_file)
          except OSError as e:
              logger.debug(f"Could not remove temp concat file {concat_file}: {e}")
  ```
- In `tests/test_integration.py`:
  - Scenario 3 (lines 620–622): Successfully asserts that under failure, the demuxer file is cleanly removed:
    ```python
    assert not os.path.exists(demuxer_file), f"Temporary concat file was not cleaned up: {demuxer_file}"
    ```
  - Scenario 1 (line 382) and Scenario 4 (line 706): Both tests explicitly set:
    ```python
    "keep_temp_files": True
    ```
  - In `generate_concat_file` (lines 103–107 of `services/ffmpeg_service.py`), temp files are generated using `tempfile.mkstemp(prefix="concat_timeline_", suffix=".txt")` in the OS temp directory (`C:\Users\admin\AppData\Local\Temp\`).

### C. Database Isolation & Concurrency Safety
- In `database/db.py` (lines 4–12):
  ```python
  from config import DB_PATH

  def get_db_connection(db_path=None):
      path = db_path if db_path is not None else DB_PATH
      conn = sqlite3.connect(path, timeout=30.0)
  ```
- In `tests/test_integration.py` (lines 59–66):
  ```python
  @pytest.fixture
  def temp_db(tmp_path, monkeypatch):
      """Sets up an isolated SQLite database file per test."""
      db_file = tmp_path / "test_integration.db"
      monkeypatch.setattr("config.DB_PATH", str(db_file))
      db.init_db(str(db_file))
      yield str(db_file)
  ```
- In `database/models.py`:
  All model CRUD operations (e.g. lines 23, 552, 617) call:
  ```python
  conn = get_db_connection()
  ```
  No model function passes `db_path`.

### D. Priority Preemption Invariants
- In `tests/test_integration.py` (`test_e2e_full_three_scene_pipeline`, lines 243–297):
  1. Image jobs 1, 2, 3 from Step 1 are marked completed in Step 2 (lines 237–239).
  2. Step 3 creates 3 video jobs with `priority=10` via `models.feed_scene_to_video_job(...)` (lines 245–251).
  3. Step 4 creates a background image job with `priority=0` via `models.add_job(...)` (lines 262–268):
     ```python
     bg_image_job_id = models.add_job({
         "id": "IMG-BACKGROUND-01",
         "project": project_id,
         "media_type": "image",
         "prompt": "Background ambient texture",
         "priority": 0
     })
     ```
  4. Scheduler dispatch in Step 4 (lines 290–297):
     ```python
     dispatched_first = scheduler.dispatch_next()
     assert dispatched_first is not None
     assert dispatched_first["media_type"] == "video"
     assert dispatched_first["priority"] == 10
     assert dispatched_first["id"] in video_job_ids
     assert len(w_video.dispatched_jobs) == 1
     assert len(w_artist.dispatched_jobs) == 0
     ```
  5. The remaining 2 video jobs and `bg_image_job_id` are never dispatched via `scheduler.dispatch_next()`.

---

## 2. Logic Chain

1. **Database Isolation Leakage (Critical Vulnerability)**:
   - Python's `from config import DB_PATH` creates a module-level reference `database.db.DB_PATH` pointing to the string `"d:\New folder (5)\database\database.db"`.
   - `monkeypatch.setattr("config.DB_PATH", str(db_file))` updates the attribute on `config`, but does **NOT** rebind `database.db.DB_PATH`.
   - `db.init_db(str(db_file))` correctly initializes tables in `db_file` because it passes the explicit argument.
   - However, every subsequent call through `database.models` calls `get_db_connection()` with no argument, defaulting to the unpatched `database.db.DB_PATH`.
   - **Conclusion**: The integration suite (and all tests using this fixture pattern) does NOT run against `temp_db`. It writes to and reads from the persistent production database `database/database.db`. This causes cross-test state contamination, failure under parallel test execution (`pytest -n`), and persistent corruption of the application database.

2. **Resource Leakage on Success Paths (Medium Vulnerability)**:
   - `services/ffmpeg_service.py` correctly unlinks `concat_file` in its `finally:` block, provided `not opts.get("keep_temp_files", False)`.
   - Scenario 3 tests and confirms unlinking under the failure path.
   - However, Scenario 1 (`test_e2e_full_three_scene_pipeline`, line 382) and Scenario 4 (`test_e2e_timeline_clip_reordering_and_inclusion_filter`, line 706) explicitly pass `"keep_temp_files": True`.
   - Because `keep_temp_files` is `True`, unlinking is bypassed. Since `mkstemp` allocates files in the OS temp directory (`C:\Users\admin\AppData\Local\Temp\`), these files are not managed or cleaned by pytest's `tmp_path`.
   - Moreover, passing `keep_temp_files: True` was unnecessary because `fake_popen` already captures demuxer content synchronously during invocation (lines 354–360).
   - **Conclusion**: Concat demuxer unlinking is NOT verified on the success path in `test_integration.py`, and running these tests leaves dangling files in the OS temp directory.

3. **Inadequate Preemption Test Invariant (Medium Vulnerability)**:
   - In `test_e2e_full_three_scene_pipeline`, `IMG-BACKGROUND-01` (priority 0) is created **after** the three video jobs (priority 10).
   - Because the video jobs were created earlier in time ($T_{\text{video}} < T_{\text{image}}$), both `ORDER BY priority DESC` AND a naive FIFO `ORDER BY created_at ASC` produce the exact same order.
   - Therefore, the test does not prove that a priority 10 job jumps ahead of an already queued priority 0 job.
   - Additionally, only 1 job is dispatched via `scheduler.dispatch_next()`. The scheduler is never tested to confirm that all priority 10 video jobs are exhausted before the background image job is reached.

4. **Authenticity of Mock Process Fidelity (Positive Assessment with Caveats)**:
   - The subprocess mocking in `render_project_timeline` accurately emulates FFmpeg's `-progress pipe:1` microseconds output (`out_time_us`), final termination sentinel (`progress=end`), non-zero returncodes (exit code 1), and stderr diagnostics.
   - The mock correctly exercises the real line-by-line stream reading loop and background stderr thread without deadlocks.
   - Minor caveats: intermediate non-time lines (`frame=`, `bitrate=`) are omitted from the mock stream, and `mock_proc.returncode` is static rather than transitioning on `.wait()`.

---

## 3. Caveats

- In accordance with strict operational constraints, no terminal commands (`run_command`) were executed. Findings are verified via exact source line mapping, Python scoping semantics, and AST invariant analysis.
- The unit test suites `tests/test_ffmpeg_engine.py` and `tests/test_scheduler_adversarial.py` independently test aspects of progress parsing and priority preemption, but the Tier 4 E2E integration suite in `tests/test_integration.py` fails to enforce these invariants end-to-end.
- As an EMPIRICAL CHALLENGER / reviewer, no implementation or test files have been modified.

---

## 4. Conclusion & Required Changes

**Verdict**: **REQUEST_CHANGES**

The E2E integration test suite exhibits high design quality and comprehensive scenario breadth, but cannot be approved until the following three issues are resolved:

### Required Change 1: Fix Database Isolation in `temp_db` fixture and `database/db.py` (CRITICAL)
In `database/db.py`, change:
```python
import config

def get_db_connection(db_path=None):
    path = db_path if db_path is not None else config.DB_PATH
    ...
```
AND in `temp_db` fixture (`tests/test_integration.py` lines 60–65):
```python
@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_integration.db"
    monkeypatch.setattr("config.DB_PATH", str(db_file))
    monkeypatch.setattr("database.db.DB_PATH", str(db_file))
    db.init_db(str(db_file))
    yield str(db_file)
```

### Required Change 2: Eliminate Temp File Leakage and Verify Success Cleanup (MEDIUM)
In `tests/test_integration.py`:
- In `test_e2e_full_three_scene_pipeline`: Remove `"keep_temp_files": True` from options (or set to `False`). Capture the demuxer path in `fake_popen` and assert `assert not os.path.exists(concat_filepath)` after `render_project_timeline` completes.
- In `test_e2e_timeline_clip_reordering_and_inclusion_filter`: Remove `"keep_temp_files": True`.

### Required Change 3: Rigorously Enforce Preemption Invariant (MEDIUM)
In `test_e2e_full_three_scene_pipeline`:
- Queue the background image job (`IMG-BACKGROUND-01`, priority 0) **BEFORE** feeding scenes into video jobs (`priority 10`), establishing $T_{\text{image}} < T_{\text{video}}$.
- Dispatch all pending jobs or loop `dispatch_next()` to verify that all priority 10 video jobs are dispatched to `w_video` before `w_artist` receives `IMG-BACKGROUND-01`.

---

## 5. Verification Method

To independently verify these findings:
1. Inspect `database/db.py` line 4 and line 11 to confirm `from config import DB_PATH` and `path = db_path if db_path is not None else DB_PATH`.
2. Inspect `tests/test_integration.py` line 63 to confirm `monkeypatch.setattr("config.DB_PATH", str(db_file))` omits `database.db.DB_PATH`.
3. Inspect `tests/test_integration.py` lines 382 and 706 to confirm `"keep_temp_files": True`.
4. Inspect `tests/test_integration.py` lines 262–279 to confirm `bg_image_job_id` is created after `video_job_ids` and only one dispatch call is made.
