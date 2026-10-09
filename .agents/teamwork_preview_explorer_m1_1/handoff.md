# Milestone M1 Exploration Handoff Report: Database Architecture, Migrations & Core Data Models

## 1. Observation

Direct observations from examining the codebase, configuration, and interface specifications:

1. **`database/db.py` Current Implementation (Lines 18-38, 42-56, 75-79, 83-97)**:
   - `accounts` table definition in `db.py` (lines 19-37) currently lacks `role`, `health_status`, and `cooldown_until`:
     ```python
     CREATE TABLE IF NOT EXISTS accounts (
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
         server INTEGER DEFAULT 0
     )
     ```
   - Previous partial migration in `db.py` (lines 75-79) added `project_id`:
     ```python
     try:
         cursor.execute("ALTER TABLE accounts ADD COLUMN project_id TEXT DEFAULT ''")
     except sqlite3.OperationalError:
         pass
     ```
   - `jobs` table definition in `db.py` (lines 42-56) lacks `batch_id`, `scene_id`, `priority`, and `completed_at`:
     ```python
     CREATE TABLE IF NOT EXISTS jobs (
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
     )
     ```
   - Tables `scenes`, `prompt_batches`, and `render_jobs` do NOT exist in `database/db.py`.
   - `system_settings` table (lines 83-87) exists with default keys `global_model`, `global_ratio`, `global_quantity`.

2. **`PROJECT.md` Milestone M1 Contract Requirements (Lines 58-67)**:
   - Line 59: `database.db.init_db()`: Initializes tables, runs safe column migrations.
   - Line 60-66: `database.models`:
     - `get_accounts() -> List[Dict]`: returns accounts with `id`, `name`, `email`, `role`, `status`, `health_status`, `cooldown_until`.
     - `update_account_status(account_id, status, health_status, cooldown_until=None)`.
     - `create_prompt_batch(name, text, media_type, project_id) -> int`: splits multi-line text into distinct jobs/scenes in SQLite queue.
     - `get_pending_jobs(media_type=None, priority_first=True) -> List[Dict]`.
     - `create_render_job(project_id, output_path, config_dict) -> int`.
     - `update_render_job(job_id, status, progress, error=None)`.

3. **Existing Callers of `database/models.py` Across Codebase**:
   - `workers/scheduler.py` (line 35): `pending_jobs = models.get_pending_jobs()` (no arguments passed).
   - `workers/scheduler.py` (line 73): `accounts = models.get_all_accounts()`.
   - `services/account_service.py` (lines 8, 12, 16, 20, 119): calls `models.get_all_accounts()`, `models.get_account_by_id(account_id)`, `models.save_account(account_data)`, `models.delete_account(account_id)`, `models.update_account_status(account_id, status)` (with 2 positional arguments).
   - `ui/queue_page.py` (line 33): `jobs = models.get_all_jobs(50)`.
   - `ui/image_page.py` (line 29) & `ui/video_page.py` (line 29): `models.add_job(job_data)`.
   - `workers/browser_worker.py` (line 182): `models.assign_job_to_account(job_dict['id'], self.account_id)`.
   - `workers/browser_worker.py` (lines 188-190): `models.get_setting(...)`.
   - `app.py` (lines 54-82): `models.update_job_status(job_id, ...)` and `models.update_account_stats(...)`.

4. **`ORIGINAL_REQUEST.md` Specifications (Lines 23-27, 42-53)**:
   - Account roles: `IMAGE_GEN` vs `VIDEO_GEN`.
   - Account health statuses: `READY`, `BUSY`, `RATE_LIMITED`.
   - Priority scheduling: dedicated `IMAGE_GEN` rotation and priority `VIDEO_GEN` (Veo 3.1 Lite) queue dispatch.
   - Timestamp-based cooldown delays: `cooldown_until` (REAL timestamp).
   - Video generation reference: Ingestion of completed images from Image Generation as First Frame / reference ingredients for scenes.

---

## 2. Logic Chain

1. **Schema Deficiencies & Risk Analysis**:
   - Based on Observation 1, if existing code or tests run against `database.db`, any query accessing `role`, `health_status`, `cooldown_until`, `batch_id`, `scene_id`, `priority`, or `completed_at` will fail with `sqlite3.OperationalError: no such column`.
   - Additionally, attempting queries on `scenes`, `prompt_batches`, or `render_jobs` will fail with `sqlite3.OperationalError: no such table`.

2. **Migration Safety & Backward Compatibility Strategy**:
   - Direct `ALTER TABLE` commands will crash if executed blindly on an already migrated database (e.g. `sqlite3.OperationalError: duplicate column name`).
   - Catching general `OperationalError` (as done on line 77 in `db.py`) can mask genuine database corruption or locks.
   - Inferring from Observation 1: inspecting `PRAGMA table_info(table_name)` prior to executing `ALTER TABLE ... ADD COLUMN ...` provides a completely idempotent, deterministic migration that never raises duplicate column errors and preserves existing row data.

3. **Preserving Existing Caller Signatures**:
   - From Observation 3, existing callers rely on:
     - `models.get_all_accounts()`
     - `models.update_account_status(account_id, status)` (2 positional args)
     - `models.get_pending_jobs()` (no args)
   - To adhere strictly to the `PROJECT.md` M1 contract (Observation 2) while maintaining 100% backward compatibility:
     - Provide `get_accounts(role=None)` and alias `get_all_accounts = get_accounts`.
     - Define `update_account_status(account_id, status=None, health_status=None, cooldown_until=None)` so calls with `(account_id, "ACTIVE")` succeed unchanged, while new callers can update `health_status` and `cooldown_until`.
     - Define `get_pending_jobs(media_type=None, priority_first=True)` with default arguments so `get_pending_jobs()` continues to work while applying the new `ORDER BY priority DESC, created_at ASC`.

4. **Batch Parsing & Priority Queueing Logic**:
   - From Observation 2 (`create_prompt_batch` contract) and Observation 4:
     - Multi-line text must be stripped and split.
     - Each line generates a scene in `scenes` with sequential `scene_number` and a corresponding job in `jobs`.
     - For video generation batches (`media_type='video'`), jobs receive a higher priority (e.g. `priority=10` vs `0` for images), satisfying the Veo 3.1 Lite priority dispatch requirement.
     - Inserting both records in an atomic transaction ensures consistency between `scenes` and `jobs`.

5. **Concurrency & Thread Safety**:
   - Desktop PySide6 UI, background scheduler thread, and Playwright worker threads concurrently access SQLite.
   - Activating `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` with `timeout=30.0` prevents `database is locked` exceptions during concurrent batch execution and UI status polling.

---

## 3. Caveats

1. **Foreign Key Enforcement**: While foreign key references (`batch_id` -> `prompt_batches.id`, `scene_id` -> `scenes.id`) are architecturally specified, SQLite does not enforce foreign keys unless `PRAGMA foreign_keys = ON;` is explicitly executed on each open connection. The connection factory `get_db_connection()` must execute this pragma.
2. **Dynamic DB Path in Tests**: When running automated tests, unit tests should be able to pass an in-memory (`:memory:`) or temporary database path to `init_db(db_path)` and `get_db_connection(db_path)` so tests do not overwrite production data in `database/database.db`.
3. **No Direct Source Code Modification**: In accordance with the explorer role's read-only constraints, no source code in `database/db.py` or `database/models.py` was altered during this task. Full proposed code is documented in `plan.md`.

---

## 4. Conclusion

1. **All 6 Required Tables Are Fully Specified**:
   - `accounts`: Added `role` ('IMAGE_GEN' | 'VIDEO_GEN'), `health_status` ('READY' | 'BUSY' | 'RATE_LIMITED'), `cooldown_until` (REAL timestamp).
   - `scenes`: Full table schema with `id`, `project_id`, `scene_number`, `prompt`, `image_path`, `video_path`, `status`, `account_id`, `created_at`, `updated_at`.
   - `prompt_batches`: Full table schema with `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `name`, `raw_text`, `media_type`, `total_count`, `completed_count`, `status`, `created_at`, `project_id`.
   - `jobs`: Added `batch_id`, `scene_id`, `priority` (INTEGER DEFAULT 0), `completed_at` (TEXT DEFAULT NULL).
   - `render_jobs`: Full table schema with `id` (INTEGER PRIMARY KEY AUTOINCREMENT), `project_id`, `output_path`, `config_json`, `status`, `progress`, `error_message`, `created_at`, `completed_at`.
   - `system_settings`: Expanded default seeds for video models, FFmpeg options, and cooldown settings.
2. **Safe Migration Strategy**:
   - Uses `PRAGMA table_info` column checking + `ALTER TABLE ADD COLUMN` for non-destructive upgrades of existing SQLite databases.
3. **Complete Contract & Caller Alignment**:
   - Implements all 6 interface functions in `database/models.py` (`get_accounts`, `update_account_status`, `create_prompt_batch`, `get_pending_jobs`, `create_render_job`, `update_render_job`) plus scene/batch CRUD helpers, retaining 100% backward compatibility with all legacy code.
4. **Complete Implementation Artifacts**:
   - Full implementation blueprint, SQL scripts, and Python source code are published in `plan.md`.

---

## 5. Verification Method

To independently verify the proposed architecture when implementing Milestone M1:

1. **Unit Test Suite Creation**:
   - Create `tests/test_database.py` with the following test cases:
     ```bash
     pytest tests/test_database.py -v
     ```
   - **Test 1: Fresh Database Initialization**:
     - Call `init_db(temp_db_path)`.
     - Inspect `sqlite_master` for tables `accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`.
     - Invalidation condition: Any missing table or column fails the test.
   - **Test 2: Safe Idempotent Migration on Existing Legacy DB**:
     - Create a mock database with only the legacy `accounts` and `jobs` columns.
     - Call `init_db(legacy_db_path)` twice consecutively.
     - Verify no `OperationalError` occurs and new columns (`role`, `health_status`, `cooldown_until`, `batch_id`, `scene_id`, `priority`, `completed_at`) are present.
     - Invalidation condition: Raising duplicate column error or corrupting existing records.
   - **Test 3: Prompt Batch Splitting & Scene Generation**:
     - Call `create_prompt_batch("Batch 1", "Line 1\nLine 2\nLine 3", media_type="video", project_id="Proj1")`.
     - Verify return value is an integer `batch_id > 0`.
     - Verify 3 records in `scenes` with `scene_number` 1, 2, 3 and `project_id = 'Proj1'`.
     - Verify 3 records in `jobs` with `priority = 10` and matching `batch_id` and `scene_id`.
   - **Test 4: Priority Queue Sorting**:
     - Insert an image job (`priority = 0`) then a video job (`priority = 10`).
     - Call `get_pending_jobs()`.
     - Verify the video job is the first element returned.
   - **Test 5: Render Job Lifecycle**:
     - Call `job_id = create_render_job("Proj1", "output/final.mp4", {"fps": 30, "upscale": True})`.
     - Call `update_render_job(job_id, "RENDERING", progress=50.0)`.
     - Call `update_render_job(job_id, "COMPLETED", progress=100.0)`.
     - Retrieve record and verify `completed_at` is populated and `progress == 100.0`.
   - **Test 6: Account Status & Cooldown Mechanics**:
     - Call `update_account_status("account001", status="ACTIVE", health_status="RATE_LIMITED", cooldown_until=time.time()+60)`.
     - Query account and assert all updated fields match.

2. **Existing Code Validation**:
   - Run `python scratch/check_db.py` to confirm legacy queries against the upgraded database succeed without warning or error.
