# Milestone M4 Quality & Adversarial Review Report: FFmpeg Video Engine

## 1. Observation
- **Reviewed Codebase**:
  - `services/ffmpeg_service.py` (875 lines, 34,610 bytes)
  - `tests/test_ffmpeg_engine.py` (680 lines, 28,020 bytes, 35 tests)
  - `database/models.py` (lines 1060-1219: `get_project_timeline_clips`, `create_render_job`, `update_render_job`, `get_render_job`, `get_setting`)
  - `database/db.py` (lines 152-168: `render_jobs` table schema)
  - `PROJECT.md` (§88-93: M4 FFmpeg Interface Contract)
  - `ORIGINAL_REQUEST.md` (§47-53, §76-77: Requirements R5 & Acceptance Criteria)
  - Worker Handoff: `.agents/teamwork_preview_worker_m4/handoff.md`

- **Verbatim Implementations Observed in `services/ffmpeg_service.py`**:
  - Concat Demuxer Path Escaping (lines 53-68):
    ```python
    def escape_concat_path(path: str) -> str:
        if not path or not str(path).strip():
            raise ValueError("Clip path cannot be empty.")
        normalized = str(path).replace('\\', '/')
        escaped = normalized.replace("'", "'\\''")
        return f"file '{escaped}'"
    ```
  - Concat File Generation (lines 70-107): Writes header `ffconcat version 1.0` and individual clip entries to an isolated tempfile created via `tempfile.mkstemp(prefix="concat_timeline_", suffix=".txt")`.
  - 1080p Upscale & Letterbox Pad Filter (lines 257-270):
    ```python
    def build_video_filter(self, upscale_1080p: bool = True, target_width: int = 1920, target_height: int = 1080) -> Optional[str]:
        if not upscale_1080p:
            return None
        return f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2"
    ```
  - Audio Loudness Normalization & BGM Filter Graph (lines 312-343):
    Constructs multi-stream filter complex when BGM is present:
    `[0:v]...[v_out];[0:a]volume=1.0[voice];[1:a]volume=0.2[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[mixed];[mixed]loudnorm=I=-16:TP=-1.5:LRA=11[a_out]`
    along with `-map [v_out] -map [a_out]`.
  - CLI Command Builder (lines 395-434):
    Sets `-progress pipe:1`, `-f concat -safe 0 -i <concat_file>`, `-c:v libx264`, `-c:a aac`, `-pix_fmt yuv420p`, `-r 30`.
  - Real-Time Progress Parsing & DB Synchronization (lines 452-555):
    Parses `out_time_us`, `out_time_ms`, `out_time=HH:MM:SS.ff`, `progress=end`, and stderr `time=HH:MM:SS.ff`, clamping percentage to `[0.0, 100.0]`. Emits to `progress_callback(pct)` and throttles SQLite updates to `models.update_render_job(job_id, status='RENDERING', progress=pct)` by threshold `db_throttle_pct=1.0%`.
  - Subprocess Management & Deadlock Prevention (lines 657-697):
    Launches `subprocess.Popen` with piped stdout and stderr; spawns a dedicated daemon thread `capture_stderr` reading `process.stderr` in real time while main thread processes stdout lines.
  - Lifecycle & Cancellation (lines 767-797):
    `cancel_render(job_id)` terminates subprocess with `proc.terminate()`, kills on timeout with `proc.kill()`, and updates database status to `CANCELLED`.
  - High-Level Timeline Orchestration (lines 798-846):
    `render_project_timeline()` queries completed scenes in strict sequence from database, creates render job in SQLite, and triggers full render.

- **Observed in `tests/test_ffmpeg_engine.py`**:
  - 35 test functions across 4 test classes:
    - `TestConcatDemuxer` (8 tests): path escaping, spaces, single quotes, backslashes, header, empty/whitespace validation.
    - `TestFilterGraphSyntax` (9 tests): 1080p scale & pad, custom resolution, loudnorm, BGM amix, volume ducking, CLI command arguments.
    - `TestProgressParsingLogic` (10 tests): `out_time_us`, `out_time_ms`, timestamps, `progress=end`, stderr fallback, boundary clamping, non-time lines, stream callback, database sync.
    - `TestFFmpegEngineIntegration` (8 tests): mock process execution, BGM integration, error handling, binary not found, empty clips, cancel render, high-level project timeline stitching, duration probing, binary availability, module delegates.

## 2. Logic Chain
1. **Integrity Audit**:
   - Inspected `services/ffmpeg_service.py` for dummy facades, bypassed work, or hardcoded return values. Found zero hardcoding; all commands, progress lines, filter strings, and database records are dynamically generated, parsed, and updated.
   - Inspected `tests/test_ffmpeg_engine.py` to check for self-certifying mock passes or trivial assertions. Found all 35 tests verify functional invariants against real calculations, real SQLite test databases (`temp_db`), and real mock stdout stream parsing.
   - Conclusion: **NO INTEGRITY VIOLATION**.

2. **Quality & Requirement Conformance**:
   - **Concat Demuxer**: Conforms to FFmpeg concat specification. Spaces are safely protected by single quotes; single quotes are escaped as `'\''`; Windows backslashes are converted to forward slashes to avoid escape collisions; temporary concat files are automatically removed in `finally:` block (Observation lines 53-107, 760-766).
   - **Video Upscale & Letterbox**: Conforms exactly to dispatch and PROJECT.md requirements: `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2` (Observation lines 257-270).
   - **Audio Normalization & BGM Ducking**: Implements EBU R128 `loudnorm=I=-16:TP=-1.5:LRA=11` and `amix=inputs=2:duration=first:dropout_transition=2` with ducked BGM volume `volume=0.2` and speech `volume=1.0` (Observation lines 312-343).
   - **Progress Reporting & DB Sync**: Emits percentage parsed from `-progress pipe:1` directly to UI callback and synchronizes with SQLite `render_jobs` table with a 1.0% diff throttle to prevent database lock contention (Observation lines 452-555).
   - **Error Handling & Cancellation**: Catches non-zero exit codes, parses error lines from stderr, marks `status='FAILED'` with error details, and supports graceful termination via `cancel_render(job_id)` (Observation lines 716-797).
   - Conclusion: **All Milestone M4 requirements are cleanly fulfilled**.

3. **Adversarial Stress-Testing**:
   - *OS Pipe Buffer Deadlock*: In standard subprocess invocations with `stdout=PIPE` and `stderr=PIPE`, child processes can deadlock if stderr fills the OS pipe buffer while stdout is read. Worker M4 mitigated this by spawning an asynchronous daemon thread `capture_stderr` that actively drains stderr in parallel (Observation lines 673-683).
   - *Database Lock Spam*: Rapid `-progress` outputs (10-30 lines/sec) could overwhelm SQLite with synchronous disk writes. Mitigated by `db_throttle_pct=1.0` while maintaining real-time UI responsiveness via callback (Observation lines 546-554).
   - *Missing FFmpeg / Invalid Files*: Gracefully handled by setting database status to `FAILED` with descriptive error messages rather than crashing unhandled (Observation lines 736-753).
   - *Resource Cleanup*: Concat file cleanup is housed in `finally:` block, preventing file handle leaks on failures or cancellations (Observation lines 760-766).

## 3. Caveats
- **Silent Input Clips with BGM**: If input scene clips generated by AI video models do not include an audio stream (`[0:a]`), FFmpeg complex filter mixing will throw a stream specifier error. The engine catches this error gracefully and sets `status='FAILED'`, but downstream GUI workflows in Milestone M5 should ideally ensure clips have audio streams or pass `normalize_audio=False` if input clips are strictly video-only.
- **Hardware Acceleration**: The engine uses standard CPU encoding (`libx264`, `preset=medium`, `crf=23`). Hardware acceleration (e.g. `h264_nvenc`) is not enabled by default, which ensures maximum compatibility across all machines.

## 4. Conclusion
Milestone M4 fulfills all functional requirements, interface contracts, and architectural guidelines without shortcuts or integrity violations.

**Verdict**: **APPROVE**

## 5. Verification Method
1. Inspect files:
   - `services/ffmpeg_service.py`
   - `tests/test_ffmpeg_engine.py`
2. Independent execution command:
   `pytest -v tests/test_ffmpeg_engine.py`
   (Verifies all 35 tests pass across concat demuxing, filter graph construction, progress parsing, and mock subprocess execution).
3. Invalidation conditions:
   - Removing `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2`.
   - Modifying `loudnorm` or `amix` filter complex syntax.
   - Altering `-progress pipe:1` parser logic or removing stderr drain thread.
