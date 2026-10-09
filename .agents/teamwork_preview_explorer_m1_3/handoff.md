# Handoff Report: Account Role/Status Modeling, Timestamp Cooldowns & Interface Contracts

**Agent**: `teamwork_preview_explorer_m1_3`  
**Milestone**: M1 - Database Architecture, Schema Migrations & Core Data Models  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_3`  
**Handoff Type**: Hard (Task Complete)  

---

## 1. Observation

Direct observations from codebase inspection:

### Observation 1: Missing Account Role, Health Status, and Cooldown Columns in `database/db.py`
In `database/db.py` lines 18-38:
```python
    # 1. Create accounts table
    cursor.execute("""
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
    """)
```
- The `accounts` table definition lacks:
  - `role`: Operational role (`IMAGE_GEN` vs `VIDEO_GEN`).
  - `health_status`: Operational health state (`READY`, `BUSY`, `RATE_LIMITED`).
  - `cooldown_until`: Real epoch float timestamp for deterministic cooldowns.
  - The migration block (lines 74-79) only migrates `project_id`.

### Observation 2: Incomplete Account Serialization in `database/models.py`
In `database/models.py` lines 46-60:
```python
    cols = [
        'id', 'name', 'email', 'profile_path', 'proxy', 'delay', 'status', 'health',
        'google_ok', 'flow_ok', 'gemini_ok', 'request_count', 'success_count', 'failed_count',
        'last_check', 'created_at', 'server', 'project_id'
    ]
    
    # Create the placeholder list and values list
    vals = [account_dict.get(col, None) for col in cols]
    placeholders = ', '.join(['?'] * len(cols))
    col_names = ', '.join(cols)
    
    cursor.execute(f"""
    INSERT OR REPLACE INTO accounts ({col_names})
    VALUES ({placeholders})
    """, vals)
```
- `cols` omits `role`, `health_status`, and `cooldown_until`. Any caller attempting to save or update these fields will have them silently discarded.
- In `database/models.py` lines 74-80:
  ```python
  def update_account_status(account_id, status):
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute("UPDATE accounts SET status = ? WHERE id = ?", (status, account_id))
      conn.commit()
      conn.close()
  ```
  This signature only accepts `status`, violating the contract specified in PROJECT.md §62: `update_account_status(account_id, status, health_status, cooldown_until=None)`.

### Observation 3: Ephemeral Ad-hoc `time.sleep` Cooldown in `app.py`
In `app.py` lines 66-78:
```python
    # Cơ chế Delay cooldown trước khi chuyển Worker về IDLE nhận job mới
    acc = models.get_account_by_id(assigned_account_id)
    cooldown_sec = int(acc.get('delay', 10)) if (acc and acc.get('delay')) else 10
    
    def delayed_idle(w, delay_time):
        import time
        w.state = f"DELAY ({delay_time}s)"
        time.sleep(delay_time)
        w.state = "IDLE"
        w.active_job_id = None
        
    import threading
    threading.Thread(target=delayed_idle, args=(worker, cooldown_sec), daemon=True).start()
```
And on failure/rate limit (`app.py` lines 79-87):
```python
    elif status == "FAILED":
        msg = data.get("message", "Error")
        models.update_job_status(job_id, "FAILED", error_message=msg)
        models.update_account_stats(assigned_account_id, request_inc=1, success_inc=0, failed_inc=1, health=90)
        
        worker.state = "IDLE"
        worker.active_job_id = None
```
- Cooldown is executed via a spawned background thread running `time.sleep(delay_time)`.
- Cooldown state is held strictly in-memory in `w.state = f"DELAY ({delay_time}s)"`.
- Cooldown state is not recorded in SQLite and does not survive application restarts.
- Failed or rate-limited jobs immediately reset the worker to `IDLE` without any cooldown or backoff, causing the scheduler to immediately re-assign jobs to a rate-limited worker.

### Observation 4: Scheduler Relies on In-Memory State Without Role/Cooldown Awareness
In `workers/scheduler.py` lines 50-60:
```python
    def _find_idle_worker(self):
        idle_list = [w for w in active_workers.values() if w.state == "IDLE" and w.websocket is not None]
        if not idle_list:
            return None
            
        if self.worker_rr_index >= len(idle_list):
            self.worker_rr_index = 0
            
        selected_worker = idle_list[self.worker_rr_index]
        self.worker_rr_index = (self.worker_rr_index + 1) % len(idle_list)
        return selected_worker
```
- Scheduler inspects only the in-memory `active_workers` dictionary and string `w.state == "IDLE"`.
- Scheduler does not check if worker's account role (`IMAGE_GEN` vs `VIDEO_GEN`) matches the job's `media_type`.
- Scheduler does not perform timestamp comparisons against `cooldown_until`.

### Observation 5: Missing Required Tables and Models from PROJECT.md
- PROJECT.md §17-19, §58-67 requires tables for `accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`.
- Currently, `scenes`, `prompt_batches`, and `render_jobs` tables are missing from `database/db.py`.
- Corresponding CRUD helper methods (`create_prompt_batch`, `create_render_job`, `update_render_job`, `get_accounts`) are missing from `database/models.py`.

---

## 2. Logic Chain

1. **Premise 1 (Role Segregation)**: From Observation 1 & 4, Google Flow requires different workloads for image generation (Nano Banana 2) vs video generation (Veo 3.1 Lite). Without an operational `role` column in `accounts` and matching logic in the scheduler, video jobs cannot be routed to dedicated priority accounts, violating ORIGINAL_REQUEST §23, §44.
2. **Premise 2 (Status Separation)**: From Observation 1 & 2, the current system conflates administrative activation (`ACTIVE` vs `INACTIVE`) with runtime operational status. A distinct `health_status` column (`READY`, `BUSY`, `RATE_LIMITED`) is essential so the system knows whether an active account is idle, currently processing, or blocked by upstream rate limits.
3. **Premise 3 (Cooldown Persistence & Determinism)**: From Observation 3, the legacy `delayed_idle` thread with `time.sleep()` is volatile and thread-blocking. When the process crashes or restarts, all cooldowns evaporate. Furthermore, on failure, resetting to `IDLE` immediately exacerbates Google Flow rate limits.
4. **Premise 4 (Non-blocking SQL Filtering)**: Moving cooldown to `cooldown_until REAL` (Unix epoch float timestamp in SQLite) allows the scheduler (Observation 4) to query ready workers directly in SQL:
   `WHERE status = 'ACTIVE' AND health_status = 'READY' AND cooldown_until <= :current_epoch AND role = :target_role`.
   This is non-blocking, survives restarts, and enables the UI to render countdowns cleanly.
5. **Premise 5 (Interface Contracts & Testability)**: Downstream milestones (M2 Native Host, M3 Playwright Scheduler, M4 FFmpeg Engine, M5 PySide6 UI) all depend on stable contracts defined in PROJECT.md §61-67. Standardizing these functions in `database/models.py` and `services/account_service.py` allows writing a comprehensive pytest test suite using mock timestamps and isolated temporary databases without needing real browser processes.

---

## 3. Caveats

1. **In-Memory Worker Websocket Synchronization**: Even though `cooldown_until` and `health_status` are stored in SQLite, the scheduler (M3) must still verify that the worker process has an active connection (`w.websocket is not None` or equivalent Native Messaging IPC pipe) before dispatching a job.
2. **Database Concurrency in SQLite**: Multiple threads (PySide6 UI, Scheduler loop, Native Host IPC) will be reading and writing to SQLite. SQLite handles concurrent reads, but writes require WAL (Write-Ahead Logging) mode (`PRAGMA journal_mode=WAL;`) and short lock durations or retry handlers to avoid `database is locked` errors.
3. **Downstream UI Refactoring (M5)**: The current UI in `ui/account_page.py` was built with NiceGUI. The project directive is PySide6 (PROJECT.md §6). The proposed contracts in Section 4 of `plan.md` are designed as standard Python dict/function interfaces compatible with PySide6 models and views.

---

## 4. Conclusion

1. **Schema Enhancements**: `accounts` table must be updated (with backward-compatible `ALTER TABLE` migrations in `database/db.py`) to include:
   - `role TEXT NOT NULL DEFAULT 'IMAGE_GEN' CHECK (role IN ('IMAGE_GEN', 'VIDEO_GEN'))`
   - `health_status TEXT NOT NULL DEFAULT 'READY' CHECK (health_status IN ('READY', 'BUSY', 'RATE_LIMITED', 'ERROR'))`
   - `cooldown_until REAL NOT NULL DEFAULT 0.0`
2. **Deterministic Cooldown Implementation**: Replace all ad-hoc `time.sleep` delays in `app.py` and `account_service.py` with timestamp calculation:
   - Normal completion: `cooldown_until = time.time() + float(account.get('delay', 5))`
   - Rate limited backoff: `cooldown_until = time.time() + backoff_seconds` (default 60s), `health_status = 'RATE_LIMITED'`
   - Reset: `cooldown_until = 0.0`, `health_status = 'READY'`
3. **Interface Contracts**: Implement the full contract in `database/models.py` as specified in `plan.md`:
   - `get_accounts(role=None, status=None) -> List[Dict]`
   - `update_account_status(account_id, status=None, health_status=None, cooldown_until=None) -> bool`
   - `update_account_role(account_id, role) -> bool`
   - `set_account_cooldown(account_id, cooldown_seconds) -> float`
   - `get_available_accounts(role=None, current_time=None) -> List[Dict]`
   - `create_prompt_batch(name, raw_text, media_type, project_id) -> int`
   - `get_pending_jobs(media_type=None, priority_first=True) -> List[Dict]`
   - `create_render_job(project_id, output_path, config_dict) -> int`
   - `update_render_job(job_id, status, progress=None, error=None) -> bool`
4. **Service Layer Cleanliness**: Wrap model calls in `services/account_service.py` with validation and expose clean APIs for PySide6 UI controllers and workers.
5. **Automated Testing Suite**: Implement the 13 recommended pytest test cases in `tests/test_database.py` covering schema migrations, role validation, deterministic cooldown expiry, priority queue sorting, and render job lifecycles.

---

## 5. Verification Method

### 5.1 Independent Code & File Verification
Inspect the created design documents:
- Plan file: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_3/plan.md`
- Handoff file: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_3/handoff.md`

### 5.2 Verification of Existing Files (Read-Only)
- Inspect `d:/New folder (5)/database/db.py` to confirm lack of `role`, `health_status`, `cooldown_until`.
- Inspect `d:/New folder (5)/database/models.py` lines 46-64 and 74-80 to verify omitted columns in `cols` and `update_account_status` parameter restriction.
- Inspect `d:/New folder (5)/app.py` lines 66-87 to verify the `delayed_idle` thread with `time.sleep()` pattern.
- Inspect `d:/New folder (5)/workers/scheduler.py` lines 50-60 to verify absence of role and cooldown checks.

### 5.3 Invalidation Conditions
This analysis would be invalidated if:
1. Google Flow automation did not distinguish between image generation and video generation accounts.
2. In-memory `time.sleep` was deemed acceptable across application restarts and crash recoveries.
3. Downstream consumers (M3 scheduler, M5 UI) did not require persistent status and cooldown querying.
