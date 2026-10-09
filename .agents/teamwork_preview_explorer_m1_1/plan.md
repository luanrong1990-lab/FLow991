# Database Architecture, Schema Migrations & Core Data Models Plan (M1)

## 1. Executive Summary

Milestone M1 establishes the foundational persistence layer for **VQPVEO3PRO - AI Video Generation Studio**. The desktop application requires multi-account orchestration across two specialized roles (`IMAGE_GEN` for Nano Banana 2 and `VIDEO_GEN` for Veo 3.1 Lite), batch prompt parsing into scene sequences, priority job scheduling with cooldown tracking, and FFmpeg video render management.

This plan details:
- Safe, non-destructive, backward-compatible schema migrations for existing databases (`database/database.db`).
- Full DDL specifications for all 6 required tables (`accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`).
- Complete model interface implementations in `database/models.py` matching the M1 contract in `PROJECT.md` while remaining 100% compatible with existing callers in `app.py`, `workers/scheduler.py`, `workers/browser_worker.py`, `services/account_service.py`, and `ui/`.
- Concrete implementation specifications and verification tests.

---

## 2. Existing Schema vs. Target Schema Gap Analysis

### 2.1 Table: `accounts`
| Column | Existing Status | Target Status | Type / Constraint | Migration Required |
|---|---|---|---|---|
| `id` | Exists | Unchanged | TEXT PRIMARY KEY | No |
| `name` | Exists | Unchanged | TEXT NOT NULL | No |
| `email` | Exists | Unchanged | TEXT NOT NULL | No |
| `profile_path` | Exists | Unchanged | TEXT NOT NULL | No |
| `proxy` | Exists | Unchanged | TEXT DEFAULT '' | No |
| `delay` | Exists | Unchanged | INTEGER DEFAULT 5 | No |
| `status` | Exists | Unchanged | TEXT NOT NULL DEFAULT 'INACTIVE' | No |
| `health` | Exists | Unchanged | INTEGER DEFAULT 100 | No |
| `google_ok` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `flow_ok` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `gemini_ok` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `request_count` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `success_count` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `failed_count` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `last_check` | Exists | Unchanged | TEXT | No |
| `created_at` | Exists | Unchanged | TEXT | No |
| `server` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `project_id` | Added in partial migration | Unchanged | TEXT DEFAULT '' | Check & Ensure |
| `role` | **MISSING** | **NEW** | `TEXT DEFAULT 'IMAGE_GEN'` ('IMAGE_GEN' \| 'VIDEO_GEN') | **ALTER TABLE ADD COLUMN** |
| `health_status` | **MISSING** | **NEW** | `TEXT DEFAULT 'READY'` ('READY' \| 'BUSY' \| 'RATE_LIMITED') | **ALTER TABLE ADD COLUMN** |
| `cooldown_until` | **MISSING** | **NEW** | `REAL DEFAULT 0.0` (Unix epoch timestamp) | **ALTER TABLE ADD COLUMN** |

### 2.2 Table: `scenes`
Table does not exist. Entire table must be created:
- `id`: TEXT PRIMARY KEY
- `project_id`: TEXT NOT NULL DEFAULT 'Default'
- `scene_number`: INTEGER NOT NULL DEFAULT 1
- `prompt`: TEXT NOT NULL
- `image_path`: TEXT DEFAULT ''
- `video_path`: TEXT DEFAULT ''
- `status`: TEXT NOT NULL DEFAULT 'PENDING'
- `account_id`: TEXT DEFAULT ''
- `created_at`: TEXT
- `updated_at`: TEXT

### 2.3 Table: `prompt_batches`
Table does not exist. Entire table must be created:
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `name`: TEXT NOT NULL
- `raw_text`: TEXT NOT NULL
- `media_type`: TEXT NOT NULL DEFAULT 'image'
- `total_count`: INTEGER DEFAULT 0
- `completed_count`: INTEGER DEFAULT 0
- `status`: TEXT NOT NULL DEFAULT 'PENDING'
- `created_at`: TEXT
- `project_id`: TEXT DEFAULT 'Default'

### 2.4 Table: `jobs`
| Column | Existing Status | Target Status | Type / Constraint | Migration Required |
|---|---|---|---|---|
| `id` | Exists | Unchanged | TEXT PRIMARY KEY | No |
| `project` | Exists | Unchanged | TEXT DEFAULT 'Default' | No |
| `media_type` | Exists | Unchanged | TEXT NOT NULL | No |
| `prompt` | Exists | Unchanged | TEXT NOT NULL | No |
| `ratio` | Exists | Unchanged | TEXT DEFAULT '1:1' | No |
| `model` | Exists | Unchanged | TEXT DEFAULT 'Default' | No |
| `status` | Exists | Unchanged | TEXT NOT NULL DEFAULT 'PENDING' | No |
| `progress` | Exists | Unchanged | INTEGER DEFAULT 0 | No |
| `result_file` | Exists | Unchanged | TEXT DEFAULT '' | No |
| `account_id` | Exists | Unchanged | TEXT DEFAULT '' | No |
| `error_message` | Exists | Unchanged | TEXT DEFAULT '' | No |
| `created_at` | Exists | Unchanged | TEXT | No |
| `batch_id` | **MISSING** | **NEW** | `INTEGER DEFAULT NULL` | **ALTER TABLE ADD COLUMN** |
| `scene_id` | **MISSING** | **NEW** | `TEXT DEFAULT ''` | **ALTER TABLE ADD COLUMN** |
| `priority` | **MISSING** | **NEW** | `INTEGER DEFAULT 0` | **ALTER TABLE ADD COLUMN** |
| `completed_at` | **MISSING** | **NEW** | `TEXT DEFAULT NULL` | **ALTER TABLE ADD COLUMN** |

### 2.5 Table: `render_jobs`
Table does not exist. Entire table must be created:
- `id`: INTEGER PRIMARY KEY AUTOINCREMENT
- `project_id`: TEXT NOT NULL DEFAULT 'Default'
- `output_path`: TEXT NOT NULL
- `config_json`: TEXT NOT NULL DEFAULT '{}'
- `status`: TEXT NOT NULL DEFAULT 'PENDING'
- `progress`: REAL DEFAULT 0.0
- `error_message`: TEXT DEFAULT ''
- `created_at`: TEXT
- `completed_at`: TEXT DEFAULT NULL

### 2.6 Table: `system_settings`
Table exists (`key TEXT PRIMARY KEY, value TEXT NOT NULL`).
Existing seeds: `global_model`, `global_ratio`, `global_quantity`.
Target updates: Expand default seeds using `INSERT OR IGNORE` for video generation and FFmpeg rendering defaults.

---

## 3. Safe Migration Architecture

### 3.1 Idempotent Column Addition Strategy
In SQLite, executing `ALTER TABLE <table> ADD COLUMN <def>` will raise an `sqlite3.OperationalError: duplicate column name: <name>` if the column already exists.
The recommended and robust pattern is:
1. Query `PRAGMA table_info(<table>)` to retrieve existing column names.
2. If the desired column is not present, execute `ALTER TABLE <table> ADD COLUMN <name> <def>`.
3. Backfill any existing rows where the newly added columns might be `NULL` with sensible defaults.

```python
def ensure_column_exists(cursor, table_name: str, col_name: str, col_def: str):
    """Safely adds a column to a table if it does not already exist."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if col_name not in existing_cols:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")
```

### 3.2 Performance & Concurrency Optimizations
- **WAL Mode**: Enable `PRAGMA journal_mode=WAL;` and `PRAGMA synchronous=NORMAL;` in `get_db_connection()`. Because PySide6 GUI, background scheduler, and worker threads concurrently read and write to SQLite, WAL (Write-Ahead Logging) eliminates SQLite table-lock contention.
- **Busy Timeout**: Configure `sqlite3.connect(DB_PATH, timeout=30.0)` so concurrent threads wait up to 30s rather than throwing `sqlite3.OperationalError: database is locked`.
- **Targeted Indices**: Create composite indices on frequently filtered and sorted columns:
  - `idx_jobs_pending_priority`: `jobs(status, priority DESC, created_at ASC)` for instant dispatch lookups.
  - `idx_accounts_cooldown`: `accounts(status, health_status, cooldown_until)` for fast scheduler rotation.
  - `idx_scenes_project_seq`: `scenes(project_id, scene_number ASC)` for timeline rendering.

---

## 4. Exact SQL DDL & Migration Logic

### 4.1 Table 1: `accounts`
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
    server INTEGER DEFAULT 0,
    project_id TEXT DEFAULT '',
    role TEXT DEFAULT 'IMAGE_GEN',
    health_status TEXT DEFAULT 'READY',
    cooldown_until REAL DEFAULT 0.0
);

-- Migrations for existing DB:
-- ALTER TABLE accounts ADD COLUMN project_id TEXT DEFAULT '';
-- ALTER TABLE accounts ADD COLUMN role TEXT DEFAULT 'IMAGE_GEN';
-- ALTER TABLE accounts ADD COLUMN health_status TEXT DEFAULT 'READY';
-- ALTER TABLE accounts ADD COLUMN cooldown_until REAL DEFAULT 0.0;

-- Indices:
CREATE INDEX IF NOT EXISTS idx_accounts_status_role ON accounts(status, role);
CREATE INDEX IF NOT EXISTS idx_accounts_cooldown ON accounts(cooldown_until);
```

### 4.2 Table 2: `scenes`
```sql
CREATE TABLE IF NOT EXISTS scenes (
    id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL DEFAULT 'Default',
    scene_number INTEGER NOT NULL DEFAULT 1,
    prompt TEXT NOT NULL,
    image_path TEXT DEFAULT '',
    video_path TEXT DEFAULT '',
    status TEXT NOT NULL DEFAULT 'PENDING',
    account_id TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_scenes_project_scene ON scenes(project_id, scene_number);
CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(status);
```

### 4.3 Table 3: `prompt_batches`
```sql
CREATE TABLE IF NOT EXISTS prompt_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    raw_text TEXT NOT NULL,
    media_type TEXT NOT NULL DEFAULT 'image',
    total_count INTEGER DEFAULT 0,
    completed_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING',
    project_id TEXT DEFAULT 'Default',
    created_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_prompt_batches_status ON prompt_batches(status);
```

### 4.4 Table 4: `jobs`
```sql
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
    created_at TEXT,
    batch_id INTEGER DEFAULT NULL,
    scene_id TEXT DEFAULT '',
    priority INTEGER DEFAULT 0,
    completed_at TEXT DEFAULT NULL
);

-- Migrations for existing DB:
-- ALTER TABLE jobs ADD COLUMN batch_id INTEGER DEFAULT NULL;
-- ALTER TABLE jobs ADD COLUMN scene_id TEXT DEFAULT '';
-- ALTER TABLE jobs ADD COLUMN priority INTEGER DEFAULT 0;
-- ALTER TABLE jobs ADD COLUMN completed_at TEXT DEFAULT NULL;

-- Indices:
CREATE INDEX IF NOT EXISTS idx_jobs_pending_priority ON jobs(status, priority DESC, created_at ASC);
CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_scene_id ON jobs(scene_id);
```

### 4.5 Table 5: `render_jobs`
```sql
CREATE TABLE IF NOT EXISTS render_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL DEFAULT 'Default',
    output_path TEXT NOT NULL,
    config_json TEXT NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'PENDING',
    progress REAL DEFAULT 0.0,
    error_message TEXT DEFAULT '',
    created_at TEXT,
    completed_at TEXT DEFAULT NULL
);

CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status);
CREATE INDEX IF NOT EXISTS idx_render_jobs_project ON render_jobs(project_id);
```

### 4.6 Table 6: `system_settings`
```sql
CREATE TABLE IF NOT EXISTS system_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```
Default Seeds:
- `global_model`: `'Nano Banana 2'`
- `global_ratio`: `'16:9'`
- `global_quantity`: `'x1'`
- `global_video_model`: `'Veo 3.1 Lite'`
- `global_video_duration`: `'8s'`
- `global_video_ratio`: `'16:9'`
- `global_video_resolution`: `'720p'`
- `render_upscale_1080p`: `'true'`
- `render_fps`: `'30'`
- `render_codec`: `'libx264'`
- `render_audio_normalize`: `'true'`
- `account_cooldown_seconds`: `'60'`

---

## 5. Implementation Specification: `database/db.py`

Below is the exact code proposed for `database/db.py`:

```python
import sqlite3
import os
import datetime
from config import DB_PATH

def get_db_connection(db_path=None):
    """Establishes and returns an SQLite database connection with WAL mode and row factory."""
    path = db_path if db_path is not None else DB_PATH
    conn = sqlite3.connect(path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn

def ensure_column_exists(cursor, table_name: str, col_name: str, col_def: str):
    """Idempotently adds a column to an SQLite table if missing."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    existing_cols = [row[1] for row in cursor.fetchall()]
    if col_name not in existing_cols:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}")

def init_db(db_path=None):
    """Initializes the database schema, executes safe migrations, and seeds default data."""
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Accounts Table
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
        server INTEGER DEFAULT 0,
        project_id TEXT DEFAULT '',
        role TEXT DEFAULT 'IMAGE_GEN',
        health_status TEXT DEFAULT 'READY',
        cooldown_until REAL DEFAULT 0.0
    )
    """)
    
    # Safe Migrations for accounts table
    ensure_column_exists(cursor, "accounts", "project_id", "TEXT DEFAULT ''")
    ensure_column_exists(cursor, "accounts", "role", "TEXT DEFAULT 'IMAGE_GEN'")
    ensure_column_exists(cursor, "accounts", "health_status", "TEXT DEFAULT 'READY'")
    ensure_column_exists(cursor, "accounts", "cooldown_until", "REAL DEFAULT 0.0")
    
    cursor.execute("UPDATE accounts SET role = 'IMAGE_GEN' WHERE role IS NULL OR role = ''")
    cursor.execute("UPDATE accounts SET health_status = 'READY' WHERE health_status IS NULL OR health_status = ''")
    cursor.execute("UPDATE accounts SET cooldown_until = 0.0 WHERE cooldown_until IS NULL")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_status_role ON accounts(status, role)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_accounts_cooldown ON accounts(cooldown_until)")

    # 2. Scenes Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scenes (
        id TEXT PRIMARY KEY,
        project_id TEXT NOT NULL DEFAULT 'Default',
        scene_number INTEGER NOT NULL DEFAULT 1,
        prompt TEXT NOT NULL,
        image_path TEXT DEFAULT '',
        video_path TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'PENDING',
        account_id TEXT DEFAULT '',
        created_at TEXT,
        updated_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_project_scene ON scenes(project_id, scene_number)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_scenes_status ON scenes(status)")

    # 3. Prompt Batches Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS prompt_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        raw_text TEXT NOT NULL,
        media_type TEXT NOT NULL DEFAULT 'image',
        total_count INTEGER DEFAULT 0,
        completed_count INTEGER DEFAULT 0,
        status TEXT NOT NULL DEFAULT 'PENDING',
        project_id TEXT DEFAULT 'Default',
        created_at TEXT
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_prompt_batches_status ON prompt_batches(status)")

    # 4. Jobs Table
    cursor.execute("""
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
        created_at TEXT,
        batch_id INTEGER DEFAULT NULL,
        scene_id TEXT DEFAULT '',
        priority INTEGER DEFAULT 0,
        completed_at TEXT DEFAULT NULL
    )
    """)
    
    # Safe Migrations for jobs table
    ensure_column_exists(cursor, "jobs", "batch_id", "INTEGER DEFAULT NULL")
    ensure_column_exists(cursor, "jobs", "scene_id", "TEXT DEFAULT ''")
    ensure_column_exists(cursor, "jobs", "priority", "INTEGER DEFAULT 0")
    ensure_column_exists(cursor, "jobs", "completed_at", "TEXT DEFAULT NULL")
    
    cursor.execute("UPDATE jobs SET priority = 0 WHERE priority IS NULL")
    
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_pending_priority ON jobs(status, priority DESC, created_at ASC)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_batch_id ON jobs(batch_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_scene_id ON jobs(scene_id)")

    # 5. Render Jobs Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS render_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_id TEXT NOT NULL DEFAULT 'Default',
        output_path TEXT NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        status TEXT NOT NULL DEFAULT 'PENDING',
        progress REAL DEFAULT 0.0,
        error_message TEXT DEFAULT '',
        created_at TEXT,
        completed_at TEXT DEFAULT NULL
    )
    """)
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_render_jobs_status ON render_jobs(status)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_render_jobs_project ON render_jobs(project_id)")

    # 6. System Settings Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS system_settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """)
    
    # Seed default settings
    default_settings = [
        ('global_model', 'Nano Banana 2'),
        ('global_ratio', '16:9'),
        ('global_quantity', 'x1'),
        ('global_video_model', 'Veo 3.1 Lite'),
        ('global_video_duration', '8s'),
        ('global_video_ratio', '16:9'),
        ('global_video_resolution', '720p'),
        ('render_upscale_1080p', 'true'),
        ('render_fps', '30'),
        ('render_codec', 'libx264'),
        ('render_audio_normalize', 'true'),
        ('account_cooldown_seconds', '60')
    ]
    for key, val in default_settings:
        cursor.execute("INSERT OR IGNORE INTO system_settings (key, value) VALUES (?, ?)", (key, val))
        
    # Seed default accounts if empty
    cursor.execute("SELECT COUNT(*) FROM accounts")
    if cursor.fetchone()[0] == 0:
        now = datetime.datetime.now().isoformat()
        default_accounts = [
            ("account001", "Tài khoản 1", "4-kts.vantien1@gmail.com", "account001", "", 5, "ACTIVE", 100, 1, 1, 0, 37, 37, 0, now, now, 1, "", "IMAGE_GEN", "READY", 0.0),
            ("account002", "Tài khoản 2", "Luanrong", "account002", "", 5, "ACTIVE", 100, 1, 1, 0, 38, 38, 0, now, now, 0, "", "VIDEO_GEN", "READY", 0.0)
        ]
        cursor.executemany("""
        INSERT INTO accounts (
            id, name, email, profile_path, proxy, delay, status, health, 
            google_ok, flow_ok, gemini_ok, request_count, success_count, failed_count, 
            last_check, created_at, server, project_id, role, health_status, cooldown_until
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, default_accounts)
        
    conn.commit()
    conn.close()
    print("Database initialized successfully.")
```

---

## 6. Implementation Specification: `database/models.py`

Below is the complete specification for `database/models.py` satisfying all M1 contracts and backward-compatibility needs:

```python
import sqlite3
import datetime
import uuid
import json
from database.db import get_db_connection

def dict_from_row(row):
    """Converts a sqlite3.Row object to a standard Python dictionary."""
    return dict(row) if row else None

# ==========================================================
# 1. Accounts Models
# ==========================================================

def get_accounts(role=None):
    """
    Contract M1: returns accounts with id, name, email, role, status, health_status, cooldown_until.
    Optionally filters by role ('IMAGE_GEN' or 'VIDEO_GEN').
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    if role:
        cursor.execute("SELECT * FROM accounts WHERE role = ? ORDER BY created_at DESC", (role,))
    else:
        cursor.execute("SELECT * FROM accounts ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(row) for row in rows]

def get_all_accounts():
    """Backward compatibility alias for get_accounts()."""
    return get_accounts()

def get_account_by_id(account_id):
    """Retrieves a single account record by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    conn.close()
    return dict_from_row(row)

def save_account(account_dict):
    """Inserts or updates an account record, preserving all fields and new defaults."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if 'id' not in account_dict or not account_dict['id']:
        account_dict['id'] = str(uuid.uuid4())
        
    if 'created_at' not in account_dict or not account_dict['created_at']:
        account_dict['created_at'] = datetime.datetime.now().isoformat()
        
    if 'status' not in account_dict:
        account_dict['status'] = 'INACTIVE'
        
    if 'health' not in account_dict:
        account_dict['health'] = 100

    if 'role' not in account_dict or not account_dict['role']:
        account_dict['role'] = 'IMAGE_GEN'

    if 'health_status' not in account_dict or not account_dict['health_status']:
        account_dict['health_status'] = 'READY'

    if 'cooldown_until' not in account_dict:
        account_dict['cooldown_until'] = 0.0
        
    cols = [
        'id', 'name', 'email', 'profile_path', 'proxy', 'delay', 'status', 'health',
        'google_ok', 'flow_ok', 'gemini_ok', 'request_count', 'success_count', 'failed_count',
        'last_check', 'created_at', 'server', 'project_id', 'role', 'health_status', 'cooldown_until'
    ]
    
    vals = [account_dict.get(col, None) for col in cols]
    placeholders = ', '.join(['?'] * len(cols))
    col_names = ', '.join(cols)
    
    cursor.execute(f"""
    INSERT OR REPLACE INTO accounts ({col_names})
    VALUES ({placeholders})
    """, vals)
    
    conn.commit()
    conn.close()
    return account_dict['id']

def delete_account(account_id):
    """Deletes an account record by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
    conn.commit()
    conn.close()

def update_account_status(account_id, status=None, health_status=None, cooldown_until=None):
    """
    Contract M1 & Backward Compatibility:
    Updates status ('ACTIVE', 'INACTIVE'), health_status ('READY', 'BUSY', 'RATE_LIMITED'),
    and/or cooldown_until (REAL timestamp).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    args = []
    if status is not None:
        updates.append("status = ?")
        args.append(status)
    if health_status is not None:
        updates.append("health_status = ?")
        args.append(health_status)
    if cooldown_until is not None:
        updates.append("cooldown_until = ?")
        args.append(float(cooldown_until))
        
    if updates:
        args.append(account_id)
        cursor.execute(f"UPDATE accounts SET {', '.join(updates)} WHERE id = ?", args)
        conn.commit()
    conn.close()

def update_account_server(account_id, server_status):
    """Updates server status flag of an account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE accounts SET server = ? WHERE id = ?", (server_status, account_id))
    conn.commit()
    conn.close()

def update_account_stats(account_id, request_inc, success_inc, failed_inc, health, google_ok=None, flow_ok=None, gemini_ok=None):
    """Increments stats counters and updates health of an account."""
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    
    cursor.execute("SELECT request_count, success_count, failed_count FROM accounts WHERE id = ?", (account_id,))
    row = cursor.fetchone()
    if not row:
        conn.close()
        return
        
    new_req = row['request_count'] + request_inc
    new_success = row['success_count'] + success_inc
    new_failed = row['failed_count'] + failed_inc
    
    google_sql = ", google_ok = ?" if google_ok is not None else ""
    flow_sql = ", flow_ok = ?" if flow_ok is not None else ""
    gemini_sql = ", gemini_ok = ?" if gemini_ok is not None else ""
    
    args = [new_req, new_success, new_failed, health, now]
    if google_ok is not None: args.append(google_ok)
    if flow_ok is not None: args.append(flow_ok)
    if gemini_ok is not None: args.append(gemini_ok)
    args.append(account_id)
    
    cursor.execute(f"""
    UPDATE accounts 
    SET request_count = ?, success_count = ?, failed_count = ?, health = ?, last_check = ?
        {google_sql} {flow_sql} {gemini_sql}
    WHERE id = ?
    """, args)
    conn.commit()
    conn.close()

# ==========================================================
# 2. Batch & Scene Models
# ==========================================================

def create_prompt_batch(name, text, media_type='image', project_id='Default') -> int:
    """
    Contract M1: splits multi-line text into distinct jobs/scenes in SQLite queue.
    Returns: batch_id (int).
    """
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return 0
        
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. Insert prompt_batch
    cursor.execute("""
    INSERT INTO prompt_batches (name, raw_text, media_type, total_count, completed_count, status, project_id, created_at)
    VALUES (?, ?, ?, ?, 0, 'PENDING', ?, ?)
    """, (name, text, media_type, len(lines), project_id, now))
    batch_id = cursor.lastrowid
    
    # Default priority: 10 for video (Veo 3.1 Lite priority scheduling), 0 for image
    priority_val = 10 if media_type == 'video' else 0
    
    # 2. Insert scenes and jobs
    for idx, prompt_line in enumerate(lines, 1):
        scene_id = f"SCENE-{uuid.uuid4().hex[:8].upper()}"
        job_id = f"{'VID' if media_type == 'video' else 'IMG'}-{uuid.uuid4().hex[:8].upper()}"
        
        cursor.execute("""
        INSERT INTO scenes (id, project_id, scene_number, prompt, image_path, video_path, status, account_id, created_at, updated_at)
        VALUES (?, ?, ?, ?, '', '', 'PENDING', '', ?, ?)
        """, (scene_id, project_id, idx, prompt_line, now, now))
        
        cursor.execute("""
        INSERT INTO jobs (id, project, media_type, prompt, ratio, model, status, progress, result_file, account_id, error_message, created_at, batch_id, scene_id, priority, completed_at)
        VALUES (?, ?, ?, ?, 'Default', 'Default', 'PENDING', 0, '', '', '', ?, ?, ?, ?, NULL)
        """, (job_id, project_id, media_type, prompt_line, now, batch_id, scene_id, priority_val))
        
    conn.commit()
    conn.close()
    return batch_id

def get_prompt_batches(limit=50):
    """Retrieves list of prompt batches."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prompt_batches ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

def get_prompt_batch_by_id(batch_id):
    """Retrieves a single prompt batch by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prompt_batches WHERE id = ?", (batch_id,))
    row = cursor.fetchone()
    conn.close()
    return dict_from_row(row)

def get_scenes_by_project(project_id='Default'):
    """Retrieves all scenes for a project sorted by scene_number ASC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenes WHERE project_id = ? ORDER BY scene_number ASC", (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

def get_scene_by_id(scene_id):
    """Retrieves a single scene by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    row = cursor.fetchone()
    conn.close()
    return dict_from_row(row)

def update_scene(scene_id, status=None, image_path=None, video_path=None, account_id=None):
    """Updates scene fields and sets updated_at timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["updated_at = ?"]
    args = [datetime.datetime.now().isoformat()]
    
    if status is not None:
        updates.append("status = ?")
        args.append(status)
    if image_path is not None:
        updates.append("image_path = ?")
        args.append(image_path)
    if video_path is not None:
        updates.append("video_path = ?")
        args.append(video_path)
    if account_id is not None:
        updates.append("account_id = ?")
        args.append(account_id)
        
    args.append(scene_id)
    cursor.execute(f"UPDATE scenes SET {', '.join(updates)} WHERE id = ?", args)
    conn.commit()
    conn.close()

# ==========================================================
# 3. Queue Jobs Models
# ==========================================================

def add_job(job_dict):
    """Inserts a new job in the database, populating new fields."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if 'id' not in job_dict or not job_dict['id']:
        job_dict['id'] = str(uuid.uuid4())
        
    if 'created_at' not in job_dict or not job_dict['created_at']:
        job_dict['created_at'] = datetime.datetime.now().isoformat()
        
    if 'status' not in job_dict:
        job_dict['status'] = 'PENDING'
        
    if 'progress' not in job_dict:
        job_dict['progress'] = 0

    if 'priority' not in job_dict:
        # Default priority: 10 if video, 0 if image
        job_dict['priority'] = 10 if job_dict.get('media_type') == 'video' else 0

    cols = [
        'id', 'project', 'media_type', 'prompt', 'ratio', 'model', 
        'status', 'progress', 'result_file', 'account_id', 'error_message', 
        'created_at', 'batch_id', 'scene_id', 'priority', 'completed_at'
    ]
    
    vals = [job_dict.get(col, None) for col in cols]
    placeholders = ', '.join(['?'] * len(cols))
    col_names = ', '.join(cols)
    
    cursor.execute(f"""
    INSERT INTO jobs ({col_names})
    VALUES ({placeholders})
    """, vals)
    
    conn.commit()
    conn.close()
    return job_dict['id']

def get_all_jobs(limit=50):
    """Retrieves all jobs from the database sorted by created_at DESC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(row) for row in rows]

def get_pending_jobs(media_type=None, priority_first=True):
    """
    Contract M1 & Backward Compatibility:
    Retrieves pending jobs.
    If media_type is specified ('image' or 'video'), filters by media_type.
    If priority_first is True, orders by priority DESC, created_at ASC.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    order_clause = "ORDER BY priority DESC, created_at ASC" if priority_first else "ORDER BY created_at ASC"
    
    if media_type:
        cursor.execute(f"SELECT * FROM jobs WHERE status = 'PENDING' AND media_type = ? {order_clause}", (media_type,))
    else:
        cursor.execute(f"SELECT * FROM jobs WHERE status = 'PENDING' {order_clause}")
        
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(row) for row in rows]

def update_job_status(job_id, status, progress=None, result_file=None, error_message=None, completed_at=None):
    """Updates status, progress, result file, error message, and completion timestamp."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = ["status = ?"]
    args = [status]
    
    if progress is not None:
        updates.append("progress = ?")
        args.append(progress)
    if result_file is not None:
        updates.append("result_file = ?")
        args.append(result_file)
    if error_message is not None:
        updates.append("error_message = ?")
        args.append(error_message)
        
    now = datetime.datetime.now().isoformat()
    if completed_at is not None:
        updates.append("completed_at = ?")
        args.append(completed_at)
    elif status in ('COMPLETED', 'FAILED'):
        updates.append("completed_at = ?")
        args.append(now)
        
    args.append(job_id)
    cursor.execute(f"UPDATE jobs SET {', '.join(updates)} WHERE id = ?", args)
    
    # If job has linked scene_id and result_file, update the scene automatically
    if result_file and status == 'COMPLETED':
        cursor.execute("SELECT scene_id, media_type FROM jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        if job_row and job_row['scene_id']:
            scene_col = 'image_path' if job_row['media_type'] == 'image' else 'video_path'
            cursor.execute(f"""
            UPDATE scenes SET {scene_col} = ?, status = 'COMPLETED', updated_at = ? 
            WHERE id = ?
            """, (result_file, now, job_row['scene_id']))
            
    # Update batch progress if batch_id exists
    if status in ('COMPLETED', 'FAILED'):
        cursor.execute("SELECT batch_id FROM jobs WHERE id = ?", (job_id,))
        job_row = cursor.fetchone()
        if job_row and job_row['batch_id']:
            b_id = job_row['batch_id']
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE batch_id = ? AND status = 'COMPLETED'", (b_id,))
            comp_cnt = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE batch_id = ? AND status = 'PENDING'", (b_id,))
            pending_cnt = cursor.fetchone()[0]
            batch_st = 'COMPLETED' if pending_cnt == 0 else 'PROCESSING'
            cursor.execute("UPDATE prompt_batches SET completed_count = ?, status = ? WHERE id = ?", (comp_cnt, batch_st, b_id))
            
    conn.commit()
    conn.close()

def assign_job_to_account(job_id, account_id):
    """Assigns a job to a specific worker/account and updates status to RUNNING."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET account_id = ?, status = 'RUNNING' WHERE id = ?", (account_id, job_id))
    
    # Also update scene status if linked
    cursor.execute("SELECT scene_id FROM jobs WHERE id = ?", (job_id,))
    job_row = cursor.fetchone()
    if job_row and job_row['scene_id']:
        cursor.execute("UPDATE scenes SET account_id = ?, status = 'RUNNING', updated_at = ? WHERE id = ?", 
                       (account_id, datetime.datetime.now().isoformat(), job_row['scene_id']))
                       
    conn.commit()
    conn.close()

def delete_job(job_id):
    """Deletes a job from the database by its ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
    conn.commit()
    conn.close()

# ==========================================================
# 4. Render Jobs Models (FFmpeg)
# ==========================================================

def create_render_job(project_id, output_path, config_dict) -> int:
    """
    Contract M1: Creates a render job record and returns its ID (int).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.datetime.now().isoformat()
    config_json = json.dumps(config_dict) if isinstance(config_dict, dict) else str(config_dict)
    
    cursor.execute("""
    INSERT INTO render_jobs (project_id, output_path, config_json, status, progress, error_message, created_at, completed_at)
    VALUES (?, ?, ?, 'PENDING', 0.0, '', ?, NULL)
    """, (project_id, output_path, config_json, now))
    
    job_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return job_id

def update_render_job(job_id, status, progress=None, error=None):
    """
    Contract M1: Updates a render job's status, progress, and error message.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    updates = ["status = ?"]
    args = [status]
    
    if progress is not None:
        updates.append("progress = ?")
        args.append(float(progress))
        
    if error is not None:
        updates.append("error_message = ?")
        args.append(str(error))
        
    if status in ('COMPLETED', 'FAILED'):
        updates.append("completed_at = ?")
        args.append(datetime.datetime.now().isoformat())
        
    args.append(job_id)
    cursor.execute(f"UPDATE render_jobs SET {', '.join(updates)} WHERE id = ?", args)
    conn.commit()
    conn.close()

def get_render_job_by_id(job_id):
    """Retrieves a single render job by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM render_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    return dict_from_row(row)

def get_all_render_jobs(project_id=None, limit=50):
    """Retrieves all render jobs, optionally filtered by project_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    if project_id:
        cursor.execute("SELECT * FROM render_jobs WHERE project_id = ? ORDER BY created_at DESC LIMIT ?", (project_id, limit))
    else:
        cursor.execute("SELECT * FROM render_jobs ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict_from_row(r) for r in rows]

# ==========================================================
# 5. System Settings Models
# ==========================================================

def get_setting(key, default=None):
    """Retrieves a single system setting by key."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM system_settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row['value'] if row else default

def save_setting(key, value):
    """Saves or updates a system setting."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO system_settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()
```

---

## 7. Downstream Compatibility & Impact Analysis

1. **M2 (Chrome Extension & Native Messaging)**:
   - Native host scripts and background workers can record and update generation jobs using `update_job_status`, linking output file paths directly to `result_file` and automatically updating `scenes(image_path, video_path)`.
2. **M3 (Browser Manager & Scheduler)**:
   - `get_accounts(role=...)`: Allows `workers/scheduler.py` to filter workers by `role` ('IMAGE_GEN' vs 'VIDEO_GEN').
   - `update_account_status(account_id, health_status='RATE_LIMITED', cooldown_until=time.time()+delay)`: Enables precise cooldown handling.
   - `get_pending_jobs(media_type=..., priority_first=True)`: Dispatches priority video jobs (`Veo 3.1 Lite`) ahead of image batches.
3. **M4 (FFmpeg Video Engine)**:
   - `create_render_job` and `update_render_job`: Fully align with `FFmpegEngine.render_timeline()`, logging progress from `-progress pipe:1` into `render_jobs(progress)`.
   - `get_scenes_by_project`: Feeds completed scene video clips in `scene_number ASC` directly into FFmpeg concat demuxer.
4. **M5 (PySide6 Desktop GUI Tabs)**:
   - Tab 1 (Accounts): Renders `role`, `health_status`, `cooldown_until`.
   - Tab 2 (Image Gen): Calls `create_prompt_batch` to generate batch image jobs and scenes.
   - Tab 3 (Video Gen): Reads completed images from `scenes` to feed as First Frame reference ingredients.
   - Tab 4 (Stitch & Render): Reads scenes and writes `render_jobs`.
   - Tab 5 (Dashboard): Queries aggregate statistics from `accounts`, `scenes`, `jobs`, and `render_jobs`.
5. **Existing Code Compatibility**:
   - Every existing call in `app.py`, `services/account_service.py`, `workers/scheduler.py`, `workers/browser_worker.py`, `ui/queue_page.py`, `ui/account_page.py`, `ui/image_page.py`, and `ui/video_page.py` is fully preserved with identical parameter semantics.

---

## 8. Automated Test Suite Specification (`tests/test_database.py`)

A comprehensive unit test file `tests/test_database.py` will test:
1. `test_init_db_creates_all_tables`: Verifies that calling `init_db(temp_db_path)` creates all 6 tables (`accounts`, `scenes`, `prompt_batches`, `jobs`, `render_jobs`, `system_settings`).
2. `test_accounts_schema_and_defaults`: Verifies `role`, `health_status`, `cooldown_until` exist and have correct defaults.
3. `test_safe_migration_on_legacy_db`: Creates a mock legacy SQLite database missing the new columns, executes `init_db(temp_db_path)`, and verifies existing rows retain data and new columns are added without error.
4. `test_create_prompt_batch`: Verifies prompt splitting, batch insertion, scene numbering, and job creation with priority sorting.
5. `test_get_pending_jobs_priority`: Verifies that jobs with `priority=10` are returned before `priority=0`.
6. `test_render_jobs_lifecycle`: Verifies creating a render job with config dict, updating progress, and completing with timestamp.
7. `test_system_settings`: Verifies reading and saving system settings.

This concludes the plan.
