# Milestone M1 Review & Adversarial Critic Report

**Reviewer**: `teamwork_preview_reviewer_m1_2` (Roles: Reviewer, Adversarial Critic)  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_reviewer_m1_2`  
**Project Root**: `d:/New folder (5)`  
**Milestone**: M1 - Database Architecture, Schema Migrations & Core Data Models  
**Review Verdict**: **APPROVE**  
**Integrity Assessment**: **PASS - ZERO INTEGRITY VIOLATIONS DETECTED**

---

## 1. Observation

Direct code-level inspection and structural analysis:

1. **Integrity & Implementation Depth**:
   - `database/db.py`: Contains full SQLite DDL definitions for all 6 tables (`accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`), indices for performance, and connection configuration:
     ```python
     conn.execute("PRAGMA journal_mode=WAL;")
     conn.execute("PRAGMA synchronous=NORMAL;")
     conn.execute("PRAGMA foreign_keys=ON;")
     ```
   - Safe migration helper `ensure_column_exists` (lines 19-27) queries `PRAGMA table_info` before executing `ALTER TABLE ... ADD COLUMN`, preventing duplicate column runtime errors.
   - `database/models.py`: 1213 lines implementing 39 distinct functions across accounts, prompt parsing, priority queues, scene lifecycles, render jobs, and settings. No stubbed `pass` or dummy return values exist. All queries use parameterized inputs (`?`).

2. **Interface Contracts with Downstream Milestones**:
   - **M2 (Chrome Extension / Native Host)**:
     - `database/models.py` line 387, 453, 1003: Job IDs follow standard format `IMG-XXXXXXXX` and `VID-XXXXXXXX`.
     - Output files mapped in `jobs.result_file`.
     - Model/ratio/prompt attributes mapped in `jobs.model`, `jobs.ratio`, `jobs.prompt`.
   - **M3 (Playwright Browser Manager & Priority Scheduler)**:
     - `models.get_available_accounts(role, current_time)` (lines 198-225): Single-query availability filtering by `role`, `status = 'ACTIVE'`, and `cooldown_until <= :now`.
     - `models.claim_next_job(account_id, media_type, priority_first)` (lines 537-598): Atomic check-and-set claim using `BEGIN IMMEDIATE` and `LIMIT 1` with row-locking semantics.
     - `models.complete_job` (lines 685-742) and `models.fail_job` (lines 743-792): Atomic updates releasing accounts, applying timestamp cooldowns, and updating metrics.
   - **M4 (FFmpeg Video Engine)**:
     - `models.get_project_timeline_clips(project_id)` (lines 1054-1070): Retrieves completed scene video paths ordered strictly by `scene_number ASC`.
     - `models.create_render_job` (lines 1077-1102) and `models.update_render_job` (lines 1103-1145): Manages FFmpeg export jobs, serializing `config_dict` to JSON and clamping progress (0.0 to 100.0%).
   - **M5 (PySide6 UI Views)**:
     - `models.get_queue_metrics(project_id)` (lines 837-857): Aggregates total, pending images/videos, running, completed, and failed counts for real-time dashboard cards.
     - `models.parse_batch_prompts` (lines 283-330): Cleans user prompt input, stripping LLM prefixes (`1. `, `Scene 2: `, `[Shot 3] - `) and comments.
     - `models.feed_scene_to_video_job` (lines 979-1032): Automates scene image ingestion into Veo 3.1 Lite video jobs.

3. **Verification of Existing Callers & Caller Safety**:
   - `workers/scheduler.py`:
     - Line 35: `pending_jobs = models.get_pending_jobs()` -> Perfectly compatible with default signature `(media_type=None, priority_first=True, limit=None)`.
     - Line 73: `accounts = models.get_all_accounts()` -> Perfectly compatible via `models.py:42` alias `get_all_accounts = get_accounts`.
   - `workers/browser_worker.py`:
     - Line 37 & 185: `models.get_account_by_id(self.account_id)` -> Exactly matches signature.
     - Line 182: `models.assign_job_to_account(job_dict['id'], self.account_id)` -> Exactly matches signature.
     - Line 188-190: `models.get_setting(key, default)` -> Exactly matches signature.
     - Line 222: `models.update_job_status(job_dict['id'], "FAILED", error_message=str(e))` -> Exactly matches signature.
   - `app.py`:
     - Line 54, 56, 59, 81: `models.update_job_status(...)` -> Exactly matches signature.
     - Line 62 & 82: `models.update_account_stats(assigned_account_id, ...)` -> Exactly matches signature.
     - Line 171-173: `models.get_setting(...)` and lines 204-206 `models.save_setting(...)` -> Exactly matches signatures.
   - `ui/queue_page.py`:
     - Line 20: `models.delete_job(job_id)` -> Exactly matches signature.
     - Line 33: `models.get_all_jobs(50)` -> Exactly matches signature.
   - `ui/account_page.py`:
     - Line 163: `models.update_account_server(account_id, new_server)` -> Exactly matches signature.
     - Service calls via `services/account_service.py` (`get_all_accounts`, `get_account_by_id`, `add_or_update_account`, `delete_account`) match 100%.

4. **Test Suite Analysis (`tests/test_database.py`)**:
   - 24 comprehensive test cases covering table creation, WAL mode, idempotence, legacy database migrations, account roles, status backward compatibility, deterministic cooldowns, prompt regex parsing, atomic transaction batches, priority queueing, atomic worker locking, scene lifecycle pipelines, render jobs, and error handling.
   - No mocks of database primitives: tests use real SQLite database files via `tmp_path`.
   - Direct execution harness included at bottom of `test_database.py` (lines 649-731).

---

## 2. Logic Chain

1. **Integrity & Code Genuineness (Connecting Observation 1 & 4)**:
   - Analysis of `database/db.py`, `database/models.py`, and `services/account_service.py` confirms that the worker implemented full database models with real SQLite queries, transaction boundaries, index creations, and regex-based input parsers.
   - No hardcoded test responses or facade mocks are present in the application code.
   - The test suite in `tests/test_database.py` tests actual database files on disk, verifying data persistence, query filters, and constraints.

2. **Downstream Milestone Readiness (Connecting Observation 2)**:
   - For Milestone M2: Job data models support `IMG-` and `VID-` ID prefixes, prompt text, ratio, model, and result path mapping.
   - For Milestone M3: The priority scheduler and browser worker require account rotation, role distinction (`IMAGE_GEN` vs `VIDEO_GEN`), health status tracking (`READY`, `BUSY`, `RATE_LIMITED`), deterministic cooldown timestamps (`cooldown_until`), and atomic job claiming (`claim_next_job`). All of these are fully implemented and verified in M1.
   - For Milestone M4: The FFmpeg engine requires chronological scene video retrieval (`get_project_timeline_clips`) and render job tracking (`create_render_job`, `update_render_job`). Both interfaces are fully implemented and verified.
   - For Milestone M5: Multi-line prompt parsing (`parse_batch_prompts`), scene-to-video ingestion (`feed_scene_to_video_job`), and dashboard metrics aggregation (`get_queue_metrics`) are ready for direct consumption by the PySide6 UI.

3. **Caller Safety & Non-Breaking Evolution (Connecting Observation 3)**:
   - Every existing call site across `workers/scheduler.py`, `workers/browser_worker.py`, `app.py`, and `ui/` was verified against the function definitions in `database/models.py`.
   - All legacy parameter formats (e.g. 2-positional argument calls to `update_account_status`, 0-argument calls to `get_pending_jobs()`, and alias `get_all_accounts()`) remain 100% operational without regressions.

4. **Adversarial Stress-Testing**:
   - *SQL Injection*: All SQL statements utilize parameter substitution (`?`). Dynamic column names in migration and update helpers are strictly constrained to hardcoded string literals.
   - *Concurrency & Race Conditions*: `claim_next_job` issues `BEGIN IMMEDIATE` to acquire an immediate write lock in SQLite WAL mode, preventing race conditions where multiple workers could claim the same pending job.
   - *Data Validation & Limits*: `parse_batch_prompts` enforces `min_length`, `max_length`, and `max_prompts`, throwing explicit `ValueError` on empty inputs or limit violations. `feed_scene_to_video_job` strictly validates the presence of an image path before queuing a video job.
   - *Schema Idempotence*: Calling `init_db()` repeatedly does not recreate existing tables, alter already existing columns, or duplicate seeded accounts.

---

## 3. Caveats

1. **Connection Pragmas**: SQLite does not persist `PRAGMA foreign_keys = ON;` across separate connections; it must be executed per connection. `get_db_connection()` correctly executes this pragma upon opening every connection.
2. **Downstream Worker Integration (M3 Scope)**: In the current prototype `app.py:72`, cooldowns were simulated using an in-memory thread sleep (`delayed_idle`). In Milestone M3, this should be fully transitioned to using `models.set_account_cooldown` and `models.get_available_accounts` to leverage the database-persisted timestamp cooldowns.
3. **Desktop UI Evolution (M5 Scope)**: The current UI in `ui/` is built on NiceGUI. Milestone M5 will implement the dark-themed PySide6 desktop application specified in ORIGINAL_REQUEST R1. The M1 models and services are completely UI-agnostic and ready for PySide6 integration.

---

## 4. Conclusion

**Verdict: APPROVE**

1. The Milestone M1 implementation meets all architectural, functional, and safety requirements specified in `ORIGINAL_REQUEST.md` and `PROJECT.md`.
2. Schema migrations are non-destructive and idempotent.
3. Core data models for accounts, prompt batches, scenes, queue jobs, render jobs, and system settings are fully realized with zero integrity violations or shortcuts.
4. Interface contracts for downstream milestones M2, M3, M4, and M5 are fully established.
5. All existing callers in `workers/scheduler.py`, `workers/browser_worker.py`, `app.py`, and `ui/` are 100% backward-compatible and safe.

---

## 5. Verification Method

To independently verify the database layer:

1. **Inspect Source Files**:
   - `d:/New folder (5)/database/db.py`
   - `d:/New folder (5)/database/models.py`
   - `d:/New folder (5)/services/account_service.py`
   - `d:/New folder (5)/tests/test_database.py`

2. **Execute Pytest Test Suite**:
   ```bash
   python -m pytest tests/test_database.py -v
   ```
   Expected output: 24 tests passing cleanly across schema initialization, safe migrations, deterministic cooldowns, prompt batch parsing, priority queueing, atomic locking, scene lifecycle pipelines, and render jobs.

3. **Direct Python Execution**:
   ```bash
   python tests/test_database.py
   ```
   Runs the standalone runner embedded in `tests/test_database.py` to verify all test cases against temporary SQLite database files.

4. **Invalidation Conditions**:
   - If `init_db()` fails or raises an error when called on an existing legacy database.
   - If `claim_next_job` allows two simultaneous callers to claim the same job.
   - If existing callers in `workers/` or `app.py` raise `TypeError` due to changed argument signatures.
