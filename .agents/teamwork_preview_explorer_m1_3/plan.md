# M1 Exploration & Design Plan: Account Role/Status Modeling, Timestamp Cooldowns & Interface Contracts

**Agent**: `teamwork_preview_explorer_m1_3`  
**Milestone**: M1 - Database Architecture, Schema Migrations & Core Data Models  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_3`  
**Date**: 2026-09-08  

---

## 1. Executive Summary

This exploration evaluates the M1 database architecture and service layer with a specific focus on:
1. **Account Role Management** (`IMAGE_GEN` vs `VIDEO_GEN`) and **Health Status Modeling** (`READY`, `BUSY`, `RATE_LIMITED`).
2. **Deterministic Cooldown Mechanism** (`cooldown_until` as Unix epoch float vs ad-hoc `time.sleep`).
3. **Interface Contracts** required by downstream consumers: Playwright Scheduler (M3), Chrome Native Messaging Host (M2), PySide6 UI (M5), FFmpeg Engine (M4), and Pytest Test Suite (R6).
4. **Concrete Unit Test Recommendations** for M1 database operations.

Our investigation of the existing codebase (`database/db.py`, `database/models.py`, `services/account_service.py`, `workers/scheduler.py`, `workers/browser_worker.py`, and `app.py`) reveals that the legacy system relies on an in-memory `time.sleep` pattern inside ad-hoc threads without database persistence for cooldowns or rate-limits, lacks `role` and `health_status` columns entirely, and omits the interface contracts required by PROJECT.md §61-67.

---

## 2. Codebase Audit & Gap Analysis

### 2.1 Inspection of `database/db.py`
In `database/db.py` (lines 18-38):
- Current table schema:
  ```sql
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
- **Deficiencies Identified**:
  1. No `role` column: Cannot distinguish accounts dedicated to image generation (`IMAGE_GEN`) from video generation (`VIDEO_GEN`).
  2. No `health_status` column: Only has `status` ('ACTIVE'/'INACTIVE') and `health` (integer 0-100). The runtime operational states (`READY`, `BUSY`, `RATE_LIMITED`) cannot be tracked in SQLite.
  3. No `cooldown_until` column: Accounts have only `delay INTEGER DEFAULT 5` (a static delay duration in seconds), without a real-time timestamp column.
  4. Missing tables: Tables `scenes`, `prompt_batches`, and `render_jobs` are absent from `database/db.py`.

### 2.2 Inspection of `database/models.py`
In `database/models.py`:
- Lines 46-60: `save_account(account_dict)` hardcodes the column list `cols` to legacy columns:
  ```python
  cols = [
      'id', 'name', 'email', 'profile_path', 'proxy', 'delay', 'status', 'health',
      'google_ok', 'flow_ok', 'gemini_ok', 'request_count', 'success_count', 'failed_count',
      'last_check', 'created_at', 'server', 'project_id'
  ]
  ```
  Any caller passing `role`, `health_status`, or `cooldown_until` is silently ignored because those keys are not in `cols`.
- Lines 74-80: `update_account_status(account_id, status)` only updates `status`. PROJECT.md §62 specifies `update_account_status(account_id, status, health_status, cooldown_until=None)`.
- Lines 177-183: `get_pending_jobs()` does not support media type filtering or priority sorting.
- Missing methods: `get_accounts()`, `update_account_role()`, `set_account_cooldown()`, `get_available_accounts()`, `create_prompt_batch()`, `create_render_job()`, `update_render_job()`.

### 2.3 Inspection of `services/account_service.py`
In `services/account_service.py`:
- Acts as a passthrough to `models.py` for CRUD, with two threaded functions: `open_account_browser()` and `check_account_health_simulated()`.
- Lacks service functions for role management, cooldown setting, or rate limit backoff.

### 2.4 Inspection of Ad-hoc Cooldown in `app.py` and `workers/`
- In `app.py` (lines 70-78):
  ```python
  def delayed_idle(w, delay_time):
      import time
      w.state = f"DELAY ({delay_time}s)"
      time.sleep(delay_time)
      w.state = "IDLE"
      w.active_job_id = None
  threading.Thread(target=delayed_idle, args=(worker, cooldown_sec), daemon=True).start()
  ```
- In `workers/scheduler.py` (lines 50-60):
  ```python
  idle_list = [w for w in active_workers.values() if w.state == "IDLE" and w.websocket is not None]
  ```
- **Severe Flaws with Current Pattern**:
  - The delay is ephemeral and thread-blocked. If the app crashes or restarts, all cooldowns are lost.
  - The scheduler inspects an in-memory dictionary `active_workers` rather than querying the database.
  - When rate-limited (`app.py` line 79-87), the account is immediately reset to `worker.state = "IDLE"`, triggering immediate re-dispatch and compounding rate-limit penalties.
  - No role checking: Image generation and video generation jobs are dispatched to any connected worker without checking account capability.

---

## 3. Detailed Architectural Evaluations

### 3.1 Account Role Management & Health Status Modeling

#### A. Operational Role Modeling
- **`IMAGE_GEN`**:
  - Purpose: High-volume, fast turn-around image generation (Nano Banana 2).
  - Scheduling: Round-robin load balancing across all active `IMAGE_GEN` accounts.
  - Workload: Matched to jobs where `media_type == 'image'`.
- **`VIDEO_GEN`**:
  - Purpose: Resource-heavy, high-latency video generation (Veo 3.1 Lite; 8s, 16:9, 720p).
  - Scheduling: Priority dispatch queue. Video jobs take precedence over image jobs if video workers are available.
  - Workload: Matched to jobs where `media_type == 'video'`.
- **Role Constraints**:
  - Valid values: `'IMAGE_GEN'`, `'VIDEO_GEN'`.
  - Default: `'IMAGE_GEN'`.

#### B. Health Status Modeling
- **`READY`**:
  - Account profile is idle, authenticated with Google Flow, and available to accept a job.
  - Cooldown has expired (`cooldown_until <= current_time`).
- **`BUSY`**:
  - Account is currently running an active job (typing prompt, waiting for generation, or downloading asset).
- **`RATE_LIMITED`**:
  - Account received a rate-limiting / quota exhaustion response from Google Flow (e.g. HTTP 429, "Too many requests", or "Quota exceeded").
  - System automatically sets `health_status = 'RATE_LIMITED'` and sets `cooldown_until = current_time + backoff_seconds` (e.g., 60.0s).
- **Status vs Health Status Separation**:
  - `status` (`'ACTIVE'` vs `'INACTIVE'`): User-controlled administrative flag. If `status == 'INACTIVE'`, the account is never launched or dispatched to.
  - `health_status` (`'READY'`, `'BUSY'`, `'RATE_LIMITED'`): Worker/scheduler-controlled runtime state.
  - `health` (integer `0-100`): Historical reliability score calculated from `(success_count / request_count) * 100`.

---

### 3.2 Deterministic Cooldown Mechanism (`cooldown_until` vs `time.sleep`)

#### Architectural Comparison

| Criteria | Legacy: `time.sleep()` in Spawns | Proposed: `cooldown_until REAL` |
|---|---|---|
| **Persistence** | Lost immediately upon process termination. | Stored in SQLite; survives restarts. |
| **Concurrency Impact** | Spawns unbound background threads sleeping in RAM. | Zero extra threads; non-blocking comparison. |
| **Scheduler Efficiency** | Requires polling in-memory worker objects. | Pure SQL query: `cooldown_until <= :now`. |
| **Rate-Limit Backoff** | Not handled; worker returns to IDLE immediately. | Deterministic backoff: `now + backoff_seconds`. |
| **UI Presentation** | UI cannot calculate remaining time cleanly. | UI renders countdown: `max(0, cooldown_until - now)`. |
| **Testability** | Requires sleeping or patching `time.sleep`. | 100% deterministic with mock epoch timestamps. |

#### State Transition Matrix

```
                +--------------------------------------------------------+
                |                                                        |
                v                                                        |
       [ status: ACTIVE ]                                                |
       [ health_status: READY ]                                          |
       [ cooldown_until <= now ]                                         |
                |                                                        |
                | Scheduler assigns Job                                  |
                v                                                        |
       [ health_status: BUSY ]                                           |
                |                                                        |
        +-------+--------------------------------+                       |
        |                                        |                       |
        | Job Completes                          | Rate-Limit Encountered|
        v                                        v                       |
[ health_status: READY ]               [ health_status: RATE_LIMITED ]   |
[ cooldown_until = now + delay ]       [ cooldown_until = now + backoff ]|
        |                                        |                       |
        +-------------------+--------------------+                       |
                            |                                            |
                            | When current_time >= cooldown_until:       |
                            +--------------------------------------------+
```

---

## 4. Proposed Interface Contracts for Downstream Consumers

### 4.1 Database Layer (`database/models.py`)

#### A. Account Query & Mutation Signatures
```python
from typing import List, Dict, Optional, Any
import time

def get_accounts(role: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Retrieves accounts matching optional role and status filters.
    Always includes keys: id, name, email, role, status, health_status, 
    cooldown_until, delay, proxy, health, profile_path, project_id, 
    request_count, success_count, failed_count, created_at.
    """

def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single account record by its ID."""

def save_account(account_dict: Dict[str, Any]) -> str:
    """
    Inserts or replaces an account record.
    Guarantees defaults:
      role = 'IMAGE_GEN'
      status = 'INACTIVE'
      health_status = 'READY'
      cooldown_until = 0.0
      health = 100
    """

def update_account_status(
    account_id: str, 
    status: Optional[str] = None, 
    health_status: Optional[str] = None, 
    cooldown_until: Optional[float] = None
) -> bool:
    """
    Dynamically updates administrative status ('ACTIVE'/'INACTIVE'),
    operational health_status ('READY'/'BUSY'/'RATE_LIMITED'), and/or 
    cooldown_until (epoch float).
    """

def update_account_role(account_id: str, role: str) -> bool:
    """Updates account role to 'IMAGE_GEN' or 'VIDEO_GEN'."""

def set_account_cooldown(account_id: str, cooldown_seconds: float) -> float:
    """
    Sets cooldown_until to time.time() + cooldown_seconds.
    Returns the target epoch float timestamp.
    """

def reset_account_cooldown(account_id: str) -> bool:
    """Resets cooldown_until to 0.0 and health_status to 'READY'."""

def get_available_accounts(
    role: Optional[str] = None, 
    current_time: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Queries accounts ready for immediate dispatch:
      WHERE status = 'ACTIVE' 
        AND health_status IN ('READY', 'RATE_LIMITED')
        AND cooldown_until <= :current_time
        AND (role = :role OR :role IS NULL)
    Ordered by cooldown_until ASC, last_check ASC.
    """
```

#### B. Queue, Batch & Scene Signatures (Required by M1/M3)
```python
def create_prompt_batch(
    name: str, 
    raw_text: str, 
    media_type: str = "image", 
    project_id: str = "Default"
) -> int:
    """
    Parses multi-line raw_text into distinct prompts.
    Inserts a prompt_batches record.
    Inserts corresponding records into 'jobs' and 'scenes'.
    Returns batch_id.
    """

def get_pending_jobs(
    media_type: Optional[str] = None, 
    priority_first: bool = True
) -> List[Dict[str, Any]]:
    """
    Retrieves pending jobs:
      WHERE status = 'PENDING'
    If media_type is provided, filters by media_type.
    If priority_first=True, orders by priority DESC, created_at ASC.
    """

def assign_job_to_account(job_id: str, account_id: str) -> bool:
    """Atomically sets job status='RUNNING' and account health_status='BUSY'."""

def complete_job(
    job_id: str, 
    account_id: str, 
    result_file: str, 
    cooldown_seconds: float = 5.0
) -> None:
    """
    Marks job as COMPLETED, updates result_file and progress=100.
    Releases account: health_status='READY', cooldown_until=now + cooldown_seconds.
    Increments account success_count.
    """

def fail_job(
    job_id: str, 
    account_id: str, 
    error_message: str, 
    is_rate_limited: bool = False, 
    backoff_seconds: float = 60.0
) -> None:
    """
    Marks job as FAILED with error_message.
    If is_rate_limited: sets account health_status='RATE_LIMITED', cooldown_until=now + backoff_seconds.
    Else: sets account health_status='READY', cooldown_until=now + 5.0.
    Increments account failed_count.
    """
```

#### C. Render Job Signatures (Required by M4/M5)
```python
def create_render_job(project_id: str, output_path: str, config_dict: Dict[str, Any]) -> int:
    """Creates a new render job with status='PENDING', progress=0, config serialized as JSON."""

def update_render_job(
    job_id: int, 
    status: str, 
    progress: Optional[int] = None, 
    error: Optional[str] = None
) -> bool:
    """Updates render job status ('RENDERING', 'COMPLETED', 'FAILED'), progress, and error."""

def get_render_job(job_id: int) -> Optional[Dict[str, Any]]:
    """Retrieves render job details with parsed config dict."""
```

---

### 4.2 Service Layer (`services/account_service.py`)

Refactored signatures:
```python
def get_all_accounts() -> List[Dict[str, Any]]:
    return models.get_accounts()

def get_account_by_id(account_id: str) -> Optional[Dict[str, Any]]:
    return models.get_account_by_id(account_id)

def add_or_update_account(account_data: Dict[str, Any]) -> str:
    return models.save_account(account_data)

def delete_account(account_id: str) -> None:
    models.delete_account(account_id)

def set_account_role(account_id: str, role: str) -> bool:
    if role not in ('IMAGE_GEN', 'VIDEO_GEN'):
        raise ValueError(f"Invalid account role: {role}")
    return models.update_account_role(account_id, role)

def set_account_status(account_id: str, status: str) -> bool:
    if status not in ('ACTIVE', 'INACTIVE'):
        raise ValueError(f"Invalid account status: {status}")
    return models.update_account_status(account_id, status=status)

def apply_cooldown(account_id: str, cooldown_seconds: float) -> float:
    return models.set_account_cooldown(account_id, cooldown_seconds)

def reset_cooldown(account_id: str) -> bool:
    return models.reset_account_cooldown(account_id)

def mark_rate_limited(account_id: str, backoff_seconds: float = 60.0) -> None:
    models.update_account_status(
        account_id, 
        health_status='RATE_LIMITED', 
        cooldown_until=time.time() + backoff_seconds
    )
```

---

## 5. Concrete Unit Test Recommendations for M1 Database Operations

Unit tests should be located under `tests/test_database.py` and run via `pytest`.

### 5.1 Test Fixture Setup
```python
import pytest
import sqlite3
import time
from database import db, models

@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Sets up an isolated SQLite database file per test."""
    db_file = tmp_path / "test_media_studio.db"
    monkeypatch.setattr("config.DB_PATH", str(db_file))
    db.init_db()
    yield str(db_file)
```

### 5.2 Recommended Unit Test Cases

#### Category 1: Schema Initialization & Migrations
1. `test_init_db_creates_all_tables(temp_db)`:
   - Query `sqlite_master` for table names.
   - Assert `accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings` all exist.
2. `test_schema_migration_backward_compatibility(tmp_path, monkeypatch)`:
   - Create legacy table with only `(id, name, email, profile_path, status, health)`.
   - Insert a row: `("acc1", "User 1", "u1@gmail.com", "profile1", "ACTIVE", 100)`.
   - Run `db.init_db()`.
   - Assert `role`, `health_status`, `cooldown_until` exist on `accounts`.
   - Assert `acc1` has `role == 'IMAGE_GEN'`, `health_status == 'READY'`, `cooldown_until == 0.0`.
3. `test_init_db_idempotence(temp_db)`:
   - Call `db.init_db()` three times.
   - Assert no error raised and default seeded accounts are not duplicated.

#### Category 2: Account Role Modeling
4. `test_account_default_role(temp_db)`:
   - Save account without providing `role`.
   - Assert `models.get_account_by_id(aid)['role'] == 'IMAGE_GEN'`.
5. `test_account_role_assignment(temp_db)`:
   - Save account with `role='VIDEO_GEN'`.
   - Assert saved role is `'VIDEO_GEN'`.
   - Update role using `models.update_account_role(aid, 'IMAGE_GEN')`.
   - Assert updated role is `'IMAGE_GEN'`.
6. `test_account_role_invalid_rejected(temp_db)`:
   - Attempt to set role to `'AUDIO_GEN'`.
   - Verify `ValueError` is raised or fallback triggered.

#### Category 3: Deterministic Cooldown & Health Status
7. `test_account_health_status_update(temp_db)`:
   - Test transitions: `READY` -> `BUSY` -> `RATE_LIMITED` -> `READY`.
   - Verify persistence in SQLite.
8. `test_deterministic_cooldown_with_mock_time(temp_db)`:
   - Set account `cooldown_until = 1500.0`.
   - At `current_time = 1499.9`, assert `models.is_account_ready(acc, 1499.9) is False`.
   - At `current_time = 1500.0`, assert `models.is_account_ready(acc, 1500.0) is True`.
   - At `current_time = 1505.0`, assert `models.is_account_ready(acc, 1505.0) is True`.
9. `test_get_available_accounts_filtering(temp_db)`:
   - Create 4 accounts:
     - `A1`: `status='ACTIVE'`, `role='IMAGE_GEN'`, `health_status='READY'`, `cooldown_until=100.0`
     - `A2`: `status='ACTIVE'`, `role='IMAGE_GEN'`, `health_status='BUSY'`, `cooldown_until=0.0`
     - `A3`: `status='ACTIVE'`, `role='IMAGE_GEN'`, `health_status='RATE_LIMITED'`, `cooldown_until=500.0`
     - `A4`: `status='INACTIVE'`, `role='IMAGE_GEN'`, `health_status='READY'`, `cooldown_until=0.0`
     - `A5`: `status='ACTIVE'`, `role='VIDEO_GEN'`, `health_status='READY'`, `cooldown_until=100.0`
   - At `current_time = 200.0`:
     - Query `get_available_accounts(role='IMAGE_GEN', current_time=200.0)` -> returns `[A1]`.
     - Query `get_available_accounts(role='VIDEO_GEN', current_time=200.0)` -> returns `[A5]`.
   - At `current_time = 501.0`:
     - Query `get_available_accounts(role='IMAGE_GEN', current_time=501.0)` -> returns `[A1, A3]` (rate-limited cooldown expired).
10. `test_rate_limit_backoff_and_cooldown_reset(temp_db)`:
    - Call `mark_rate_limited(aid, backoff_seconds=60.0)`.
    - Assert account has `health_status == 'RATE_LIMITED'` and `cooldown_until > time.time()`.
    - Call `reset_account_cooldown(aid)`.
    - Assert `health_status == 'READY'` and `cooldown_until == 0.0`.

#### Category 4: Queue, Batch & Render Job Contracts
11. `test_create_prompt_batch_splits_lines(temp_db)`:
    - Input: `"Line 1\n\n  Line 2  \nLine 3"`.
    - Call `create_prompt_batch("Batch 1", text, media_type="image")`.
    - Verify 1 batch with `total_count=3`, 3 records in `jobs`, and 3 records in `scenes`.
12. `test_get_pending_jobs_priority_ordering(temp_db)`:
    - Add regular job `J1` (priority=0, created earlier).
    - Add priority job `J2` (priority=10, created later).
    - Assert `get_pending_jobs()[0]['id'] == J2['id']`.
13. `test_render_job_crud_lifecycle(temp_db)`:
    - Call `create_render_job(project_id="P1", output_path="out.mp4", config_dict={"fps": 30})`.
    - Call `update_render_job(job_id, status='RENDERING', progress=50)`.
    - Verify progress is 50.
    - Call `update_render_job(job_id, status='COMPLETED', progress=100)`.
    - Verify completed status and valid config retrieval.

---

## 6. Implementation Roadmap for M1 Authors
1. **`database/db.py`**:
   - Update `CREATE TABLE IF NOT EXISTS accounts` to include `role`, `health_status`, `cooldown_until`.
   - Add safe `ALTER TABLE accounts ADD COLUMN ...` statements in `init_db()`.
   - Add DDL for `scenes`, `prompt_batches`, `render_jobs`.
2. **`database/models.py`**:
   - Implement the contract functions documented in Section 4.1.
   - Update `save_account` to include new fields.
   - Ensure backward compatibility with existing callers.
3. **`services/account_service.py`**:
   - Expose the domain methods documented in Section 4.2.
4. **`tests/test_database.py`**:
   - Implement the 13 recommended unit test cases.
