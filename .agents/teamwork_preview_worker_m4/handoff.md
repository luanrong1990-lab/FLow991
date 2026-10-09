# Milestone M4 Completion Handoff Report: FFmpeg Video Stitching & Post-Processing Engine

## 1. Observation
- Target Objective: Implement Milestone M4 ("FFmpeg Video Stitching & Post-Processing Engine") under exclusive write ownership:
  - `services/ffmpeg_service.py`
  - `tests/test_ffmpeg_engine.py`
- Database Contracts (`database/models.py`):
  - `models.create_render_job(project_id, output_path, config_dict) -> int` (line 1083)
  - `models.update_render_job(job_id, status, progress, error, output_path) -> bool` (line 1109)
  - `models.get_render_job(job_id) -> Dict[str, Any]` (line 1152)
  - `models.get_project_timeline_clips(project_id) -> List[Dict[str, Any]]` (line 1060)
- Dispatch & Project Requirements (`ORIGINAL_REQUEST.md` §48-53, §76-77; `PROJECT.md` §88-93):
  - Concat demuxer with strict sequencing and path escaping.
  - Video filter: `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2`.
  - Audio loudness normalization: `loudnorm` filter (EBU R128 standard).
  - Background music (BGM) mixing with volume ducking: `amix` filter (`inputs=2:duration=first:dropout_transition=2`) with `volume` ducking filters.
  - Codecs: H.264 (`libx264`) + AAC (`aac`), `pix_fmt yuv420p`.
  - Progress parsing: `-progress pipe:1` (and stderr fallback), calculating percentage `(elapsed / total_duration) * 100.0` clamped to `[0.0, 100.0]`.
  - Real-time updates: emits percentage to callback and synchronizes with SQLite via `models.update_render_job(job_id, status='RENDERING', progress=pct)`.
  - Error handling: catches non-zero exit codes, parses error stderr, updates status to `'FAILED'`.

## 2. Logic Chain
1. **Concat Demuxer Generator**:
   - `escape_concat_path(path)` converts Windows backslashes `\` to `/` and escapes `'` as `'\''`, wrapping the path in `file '<escaped_path>'`.
   - `generate_concat_file(clips, concat_file_path=None)` writes an `ffconcat version 1.0` header followed by each clip line, creating an isolated temporary text file via `tempfile.mkstemp` if no path is given.
2. **Filter Graph Generator**:
   - `build_video_filter(upscale_1080p, target_width, target_height)` produces `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2`.
   - `build_filter_graph(options)` formats loudness normalization `loudnorm=I=-16:TP=-1.5:LRA=11`. When `bgm_file` is present, it constructs the complex filter graph:
     `[0:v]...[v_out];[0:a]volume=1.0[voice];[1:a]volume=0.2[bgm];[voice][bgm]amix=inputs=2:duration=first:dropout_transition=2[mixed];[mixed]loudnorm[a_out]`
     along with maps `["-map", "[v_out]", "-map", "[a_out]"]`.
   - `build_render_command(concat_file, output_file, options)` sets `-progress pipe:1`, `-f concat`, `-safe 0`, `-c:v libx264`, `-c:a aac`, `-pix_fmt yuv420p`, `-r 30`.
3. **Progress Parser & DB Synchronization**:
   - `parse_progress_line(line, total_duration)` parses `out_time_us=<us>`, `out_time_ms=<ms>`, `out_time=HH:MM:SS.ff`, `progress=end`, or stderr `time=HH:MM:SS.ff`, calculating clamped float percentage.
   - `process_progress_stream(...)` iterates the stream, invokes `progress_callback(pct)`, and throttles SQLite updates to `models.update_render_job(job_id, status='RENDERING', progress=pct)` (updating on >=1.0% diff, 0%, or 100%) to eliminate database lock contention.
4. **Subprocess Management & Error Handling**:
   - Runs `subprocess.Popen` reading `stdout` for progress while draining `stderr` in a background daemon thread to prevent OS pipe deadlocks.
   - On `returncode == 0`, updates job to `status='COMPLETED'`, `progress=100.0`.
   - On `returncode != 0`, extracts stderr failure details and updates job to `status='FAILED'`, `error=err_msg`.
   - Handles `FileNotFoundError` when FFmpeg is not installed, setting status to `FAILED`.
   - Temporary concat demuxer files are automatically cleaned up in a `finally:` block.
5. **Comprehensive Automated Test Suite (`tests/test_ffmpeg_engine.py`)**:
   - Implemented 35 distinct tests divided into 4 test classes:
     - `TestConcatDemuxer` (8 tests): path escaping, space handling, single quote escaping, backslash normalization, header checks, and empty/invalid input rejection.
     - `TestFilterGraphSyntax` (9 tests): 1080p scale & pad, loudnorm, BGM amix, volume ducking, and CLI command flags.
     - `TestProgressParsingLogic` (10 tests): `out_time_us`, `out_time_ms`, timestamps, `progress=end`, stderr regex, boundary clamping, and stream callback/DB updates.
     - `TestFFmpegEngineIntegration` (8 tests): mocked subprocess success with 100% completion, BGM integration, non-zero failure handling, missing binary handling, render cancellation, duration probing, binary availability, and project timeline stitching.

## 3. Caveats
- Subprocess tests mock `subprocess.Popen` and `subprocess.run` to guarantee deterministic, isolated unit and integration test execution without requiring pre-installed system FFmpeg binaries on every CI/CD runner. Real FFmpeg CLI execution will seamlessly utilize system FFmpeg or custom `FFMPEG_PATH` when present.
- DB updates during render progress streaming are throttled to increments of >=1.0% to prevent excessive disk I/O on SQLite WAL while ensuring the UI callback receives every update in real time.

## 4. Conclusion
- Milestone M4 implementation is completely implemented and verified:
  - `services/ffmpeg_service.py` fulfills all interface contracts and functional requirements.
  - `tests/test_ffmpeg_engine.py` provides 35 thorough tests verifying concat demuxing, filter graphs, progress parsing, and mock execution with database synchronization.

## 5. Verification Method
1. Inspect files:
   - `services/ffmpeg_service.py`
   - `tests/test_ffmpeg_engine.py`
2. Run automated test suite with pytest:
   `pytest -v tests/test_ffmpeg_engine.py`
3. Verify test coverage:
   All 35 tests pass with 0 failures and 0 regressions.
4. Invalidation conditions:
   - Modifying `scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2` syntax.
   - Removing `loudnorm` or `amix` filter definitions.
   - Failing to sanitize/escape single quotes or backslashes in concat demuxer lines.
