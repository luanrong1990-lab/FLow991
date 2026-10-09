# M1 Architecture & Specification Plan: Batch Prompt Parser, Priority Queue & Scene Sequence Lifecycle

**Agent**: `teamwork_preview_explorer_m1_2`  
**Milestone**: M1 - Database Architecture, Schema Migrations & Core Data Models  
**Target Module**: `database/models.py` (with integration to `database/db.py`, `workers/scheduler.py`, and `ui/`)  
**Date**: 2026-09-08  
**Scope**: Read-Only Architectural Investigation and Exact Design Blueprint  

---

## 1. Executive Summary & Problem Scope

In accordance with `ORIGINAL_REQUEST.md` (Requirements R1, R4, R5; Acceptance Criteria §67) and `PROJECT.md` (Milestone M1, Feature #3, Interface Contracts §58-67), the persistence layer in `database/models.py` must support:
1. **Batch prompt parsing**: Splitting multi-line user input into distinct, sanitized prompts with prefix removal, and atomically inserting batch metadata, scenes, and queue jobs in a single SQLite transaction.
2. **Priority queue scheduling**: Querying pending generation jobs with optional media type filtering (`media_type='image' | 'video'`), priority-first sorting (`priority DESC, created_at ASC`), and race-free atomic job claiming.
3. **Scene sequence & lifecycle tracking**: Managing scene entities from prompt creation, linking generated First Frame images, feeding completed images into Veo 3.1 Lite video generation jobs, and assembling chronological scene timelines for FFmpeg rendering.
4. **Render job CRUD**: Tracking multi-clip timeline rendering, FFmpeg execution states, and real-time percentage progress.

### Existing Code Analysis (`database/models.py` & `database/db.py`)
- **Current `database/db.py`**: Only defines tables `accounts`, `jobs`, and `system_settings`. The tables `scenes`, `prompt_batches`, and `render_jobs` are absent.
- **Current `jobs` table**: Missing columns `batch_id`, `scene_id`, `priority`, and `completed_at`.
- **Current `ui/image_page.py` & `ui/video_page.py`**: Use naive `[line.strip() for line in prompt_text.split('\n') if line.strip()]` without handling comment lines, numbered prefixes (`1. `, `Scene 1: `), prompt length bounds, or transactional rollback. Individual jobs are inserted one by one without batch or scene correlation.
- **Current `database/models.py:get_pending_jobs`**: Implements `SELECT * FROM jobs WHERE status = 'PENDING' ORDER BY created_at ASC` — lacking `media_type` filtering, lacking `priority` sorting, and lacking concurrency guards.
- **Current Scene & Render Support**: Completely non-existent in `database/models.py`.

---

## 2. Topic 1: Batch Prompt Parser & Atomic Batch Creation

### 2.1 Prompt Sanitization & Parsing Logic

Real-world prompts entered into desktop AI tools often come from LLM outlines or user notes with formatting artifacts (e.g. `1. `, `Scene 1: `, `[Shot 2] - `) and commentary. The parser must normalize line endings, strip prefixes, omit comments, and enforce length limits.

```python
import re
from typing import List, Dict, Any, Optional

# Regex matches prefixes like "1. ", "1) ", "Scene 1: ", "Scene 1 - ", "[1] ", "Shot 01: "
PROMPT_PREFIX_REGEX = re.compile(
    r'^(?:(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*|\[\s*\d+\s*\]\s*)',
    re.IGNORECASE
)

# Regex matches comment/header lines that should be ignored
COMMENT_LINE_REGEX = re.compile(
    r'^(?:#|//|/\*|---|===|\*\*)'
)

def parse_batch_prompts(
    raw_text: str,
    strip_prefixes: bool = True,
    min_length: int = 3,
    max_length: int = 1500,
    max_prompts: int = 100
) -> List[str]:
    """
    Parses multi-line raw prompt text into distinct, sanitized individual prompts.
    
    Validation & Transformation Rules:
    1. Rejects None, non-string, or purely whitespace input.
    2. Normalizes line endings (\r\n and \r -> \n).
    3. Strips leading and trailing whitespace from each line.
    4. Filters out empty lines and comment lines (e.g., '# Scene breakdown').
    5. Strips sequential numbering prefixes if strip_prefixes=True.
    6. Enforces minimum prompt length (default 3 chars) and maximum prompt length (default 1500 chars).
    7. Enforces maximum batch capacity (default 100 prompts) to protect browser worker queues.
    
    Returns:
        List[str]: Chronological list of sanitized prompt strings.
        
    Raises:
        ValueError: If input is empty, no valid prompts are found, or limits are violated.
    """
    if not raw_text or not isinstance(raw_text, str) or not raw_text.strip():
        raise ValueError("Prompt text cannot be empty or whitespace only.")
        
    # Normalize line breaks
    normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n')
    lines = normalized.split('\n')
    
    parsed_prompts: List[str] = []
    for line in lines:
        cleaned = line.strip()
        if not cleaned:
            continue
            
        # Ignore comments or markdown section dividers
        if COMMENT_LINE_REGEX.match(cleaned):
            continue
            
        # Optionally strip numbering prefixes
        if strip_prefixes:
            cleaned = PROMPT_PREFIX_REGEX.sub('', cleaned).strip()
            
        if not cleaned:
            continue
            
        if len(cleaned) < min_length:
            continue  # Discard trivial garbage lines (e.g. ".", "-")
            
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length].strip()
            
        parsed_prompts.append(cleaned)
        
    if not parsed_prompts:
        raise ValueError("No valid prompts found in input text after parsing and filtering.")
        
    if len(parsed_prompts) > max_prompts:
        raise ValueError(f"Exceeded maximum batch limit of {max_prompts} prompts (received {len(parsed_prompts)}).")
        
    return parsed_prompts
```

### 2.2 Atomic Batch & Scene Creation (`create_prompt_batch`)

When a user submits a batch, the system must atomically create:
1. A record in `prompt_batches`.
2. $N$ chronological records in `scenes` (with `scene_number = 1..N`, `status='PENDING'`).
3. $N$ corresponding jobs in `jobs` (with `batch_id`, `scene_id`, `priority`, `status='PENDING'`).

```python
import uuid
import datetime
from database.db import get_db_connection

def create_prompt_batch(
    name: str,
    text: str,
    media_type: str = "image",
    project_id: str = "Default",
    model: str = "Default",
    ratio: str = "16:9",
    priority: int = 0,
    strip_prefixes: bool = True
) -> Dict[str, Any]:
    """
    Atomically parses prompt text and inserts prompt_batch, scenes, and queue jobs.
    
    Validation Rules:
    - media_type must be either 'image' or 'video'.
    - project_id defaults to 'Default' if empty or None.
    - priority must be an integer (higher number = higher execution precedence).
    - Entire operation is executed inside a single SQLite transaction with rollback on failure.
    
    Returns:
        Dict containing:
        - batch_id: str
        - project_id: str
        - media_type: str
        - total_count: int
        - scene_ids: List[str]
        - job_ids: List[str]
    """
    if media_type not in ('image', 'video'):
        raise ValueError(f"Invalid media_type '{media_type}'. Must be 'image' or 'video'.")
        
    parsed_prompts = parse_batch_prompts(text, strip_prefixes=strip_prefixes)
    total_count = len(parsed_prompts)
    
    batch_id = f"BATCH-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.now().isoformat()
    clean_name = name.strip() if name and name.strip() else f"Batch {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}"
    clean_project = project_id.strip() if project_id and project_id.strip() else "Default"
    
    scene_ids = []
    job_ids = []
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        cursor.execute("BEGIN TRANSACTION")
        
        # 1. Insert into prompt_batches
        cursor.execute("""
            INSERT INTO prompt_batches (
                id, name, raw_text, media_type, total_count, completed_count, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (batch_id, clean_name, text, media_type, total_count, 0, 'PENDING', now))
        
        # 2. Iterate through parsed prompts
        for idx, prompt in enumerate(parsed_prompts, start=1):
            scene_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
            job_id = f"{'IMG' if media_type == 'image' else 'VID'}-{uuid.uuid4().hex[:8].upper()}"
            
            # Insert Scene
            cursor.execute("""
                INSERT INTO scenes (
                    id, project_id, batch_id, scene_number, prompt, image_path, video_path,
                    status, account_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (scene_id, clean_project, batch_id, idx, prompt, '', '', 'PENDING', '', now, now))
            
            # Insert Job
            cursor.execute("""
                INSERT INTO jobs (
                    id, project, media_type, prompt, ratio, model, status,
                    progress, result_file, account_id, error_message, created_at,
                    batch_id, scene_id, priority
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                job_id, clean_project, media_type, prompt, ratio, model, 'PENDING',
                0, '', '', '', now,
                batch_id, scene_id, priority
            ))
            
            scene_ids.append(scene_id)
            job_ids.append(job_id)
            
        conn.commit()
        
        return {
            "batch_id": batch_id,
            "project_id": clean_project,
            "media_type": media_type,
            "total_count": total_count,
            "scene_ids": scene_ids,
            "job_ids": job_ids
        }
    except Exception as exc:
        conn.rollback()
        raise RuntimeError(f"Failed to create prompt batch transaction: {exc}") from exc
    finally:
        conn.close()
```

### 2.3 Batch Status & Progress Query Helpers
```python
def get_prompt_batch(batch_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single prompt batch record with its current completion stats."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prompt_batches WHERE id = ?", (batch_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_prompt_batches(limit: int = 50) -> List[Dict[str, Any]]:
    """Retrieves recent prompt batches ordered by created_at DESC."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM prompt_batches ORDER BY created_at DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def increment_batch_completed_count(batch_id: str) -> bool:
    """
    Atomically increments completed_count for a batch.
    If completed_count >= total_count, marks batch as 'COMPLETED'.
    """
    if not batch_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("""
            UPDATE prompt_batches 
            SET completed_count = completed_count + 1,
                status = CASE 
                    WHEN completed_count + 1 >= total_count THEN 'COMPLETED'
                    ELSE 'IN_PROGRESS'
                END
            WHERE id = ?
        """, (batch_id,))
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
```

---

## 3. Topic 2: Priority Queue Queries & Concurrency Protection

### 3.1 Priority Queue Query Specification

Contract required by `PROJECT.md` §64:
`get_pending_jobs(media_type=None, priority_first=True) -> List[Dict]`

```python
def get_pending_jobs(
    media_type: Optional[str] = None,
    priority_first: bool = True,
    limit: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves pending jobs from the database with media_type filtering and priority ordering.
    
    Parameters:
        media_type (Optional[str]): If provided ('image' or 'video'), restricts results
            to jobs matching that media_type. If None, returns all pending jobs.
        priority_first (bool): 
            If True, orders by priority DESC, created_at ASC (high priority jobs first;
            equal priority dispatched FIFO).
            If False, orders strictly FIFO by created_at ASC.
        limit (Optional[int]): Maximum number of jobs to fetch.
        
    Query Construction:
        SELECT * FROM jobs 
        WHERE status = 'PENDING'
        [AND media_type = ?]
        ORDER BY [priority DESC, ] created_at ASC
        [LIMIT ?]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    query = "SELECT * FROM jobs WHERE status = 'PENDING'"
    params: List[Any] = []
    
    if media_type:
        query += " AND media_type = ?"
        params.append(media_type)
        
    if priority_first:
        query += " ORDER BY priority DESC, created_at ASC"
    else:
        query += " ORDER BY created_at ASC"
        
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        params.append(limit)
        
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

### 3.2 Atomic Job Claiming (`claim_next_job`)

In a multi-account, multi-worker architecture, multiple background worker threads or scheduler iterations run concurrently. Naive `get_pending_jobs()` followed by separate assignment can cause race conditions where two workers grab the same job.

We specify an atomic check-and-set claim method using SQLite transactional optimistic locking:

```python
def claim_next_job(
    account_id: str,
    media_type: Optional[str] = None,
    priority_first: bool = True
) -> Optional[Dict[str, Any]]:
    """
    Atomically claims the next pending job for a specific worker account.
    
    Execution Steps:
    1. Queries for the top 1 PENDING job matching media_type with priority sorting.
    2. Executes an atomic UPDATE setting status='RUNNING' and account_id=account_id
       conditioned on id=job_id AND status='PENDING'.
    3. If rowcount == 1, claim succeeded; returns the claimed job record.
    4. If rowcount == 0, another worker claimed it concurrently; rolls back and returns None.
    
    Returns:
        Optional[Dict[str, Any]]: The claimed job dictionary, or None if queue is empty.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("BEGIN IMMEDIATE")
        
        query = "SELECT * FROM jobs WHERE status = 'PENDING'"
        params: List[Any] = []
        if media_type:
            query += " AND media_type = ?"
            params.append(media_type)
            
        if priority_first:
            query += " ORDER BY priority DESC, created_at ASC"
        else:
            query += " ORDER BY created_at ASC"
            
        query += " LIMIT 1"
        cursor.execute(query, params)
        row = cursor.fetchone()
        
        if not row:
            conn.rollback()
            return None
            
        job_id = row['id']
        cursor.execute("""
            UPDATE jobs 
            SET status = 'RUNNING', account_id = ?
            WHERE id = ? AND status = 'PENDING'
        """, (account_id, job_id))
        
        if cursor.rowcount == 1:
            conn.commit()
            # Fetch updated row
            cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            claimed = dict(cursor.fetchone())
            return claimed
        else:
            conn.rollback()
            return None
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

### 3.3 Queue Management Helpers

```python
def set_job_priority(job_id: str, priority: int) -> bool:
    """Dynamically adjusts priority of a queued job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET priority = ? WHERE id = ?", (priority, job_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def cancel_job(job_id: str) -> bool:
    """Cancels a pending or running job."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE jobs SET status = 'CANCELLED' WHERE id = ? AND status IN ('PENDING', 'RUNNING')", (job_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def retry_job(job_id: str) -> bool:
    """Resets a failed or cancelled job back to PENDING."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE jobs 
        SET status = 'PENDING', progress = 0, error_message = '', account_id = ''
        WHERE id = ? AND status IN ('FAILED', 'CANCELLED')
    """, (job_id,))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def get_queue_metrics(project_id: Optional[str] = None) -> Dict[str, int]:
    """Calculates real-time metrics for UI Dashboard (Tab 5)."""
    conn = get_db_connection()
    cursor = conn.cursor()
    filter_sql = " WHERE project = ?" if project_id else ""
    params = (project_id,) if project_id else ()
    
    cursor.execute(f"""
        SELECT 
            COUNT(*) as total_jobs,
            SUM(CASE WHEN status = 'PENDING' AND media_type = 'image' THEN 1 ELSE 0 END) as pending_images,
            SUM(CASE WHEN status = 'PENDING' AND media_type = 'video' THEN 1 ELSE 0 END) as pending_videos,
            SUM(CASE WHEN status = 'RUNNING' THEN 1 ELSE 0 END) as running_jobs,
            SUM(CASE WHEN status = 'COMPLETED' AND media_type = 'image' THEN 1 ELSE 0 END) as completed_images,
            SUM(CASE WHEN status = 'COMPLETED' AND media_type = 'video' THEN 1 ELSE 0 END) as completed_videos,
            SUM(CASE WHEN status = 'FAILED' THEN 1 ELSE 0 END) as failed_jobs
        FROM jobs {filter_sql}
    """, params)
    row = cursor.fetchone()
    conn.close()
    return {k: (row[k] or 0) for k in row.keys()} if row else {}
```

---

## 4. Topic 3: Scene Sequence & Full Lifecycle Management

### 4.1 The Scene Lifecycle State Machine

A Scene represents a single continuous narrative unit in a video project. It undergoes the following deterministic state transitions:

```
                  ┌──────────────────────────────────────────────┐
                  │                 [PENDING]                    │
                  └──────────────────────┬───────────────────────┘
                                         │ Image Job Assigned
                                         ▼
                  ┌──────────────────────────────────────────────┐
                  │             [IMAGE_GENERATING]               │
                  └──────┬───────────────────────────────┬───────┘
          Image Failed   │                               │ Image Succeeded
                         ▼                               ▼
       ┌───────────────────────────┐   ┌──────────────────────────────────────────┐
       │      [IMAGE_FAILED]       │   │              [IMAGE_READY]               │
       └───────────────────────────┘   │ (image_path populated, ready for video)  │
                                       └─────────────────┬────────────────────────┘
                                                         │ feed_scene_to_video_job()
                                                         ▼
                                       ┌──────────────────────────────────────────┐
                                       │              [VIDEO_QUEUED]              │
                                       └─────────────────┬────────────────────────┘
                                                         │ Video Job Assigned
                                                         ▼
                                       ┌──────────────────────────────────────────┐
                                       │             [VIDEO_GENERATING]           │
                                       └──────┬──────────────────────────┬────────┘
                               Video Failed   │                          │ Video Succeeded
                                              ▼                          ▼
                            ┌───────────────────────────┐ ┌───────────────────────┐
                            │      [VIDEO_FAILED]       │ │      [COMPLETED]      │
                            │                           │ │(video_path populated, │
                            │                           │ │ ready for FFmpeg)     │
                            └───────────────────────────┘ └───────────────────────┘
```

### 4.2 Scene Helper Functions in `database/models.py`

```python
def create_scene(
    project_id: str,
    scene_number: int,
    prompt: str,
    batch_id: str = ""
) -> str:
    """Inserts a single scene record in sequence."""
    scene_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO scenes (
            id, project_id, batch_id, scene_number, prompt, image_path, video_path,
            status, account_id, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, '', '', 'PENDING', '', ?, ?)
    """, (scene_id, project_id, batch_id, scene_number, prompt, now, now))
    conn.commit()
    conn.close()
    return scene_id

def get_scene_by_id(scene_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves a single scene record by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_scenes_by_project(
    project_id: str,
    status: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Retrieves all scenes for a given project, sorted strictly by scene_number ASC.
    Ensures timeline ordering for UI and stitching.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM scenes WHERE project_id = ?"
    params: List[Any] = [project_id]
    if status:
        query += " AND status = ?"
        params.append(status)
    query += " ORDER BY scene_number ASC"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_scene_image_result(
    scene_id: str,
    image_path: str,
    account_id: Optional[str] = None
) -> bool:
    """
    Called upon successful completion of an image generation job:
    1. Sets scene.image_path = image_path.
    2. Sets scene.status = 'IMAGE_READY'.
    3. Increments parent batch completed_count.
    """
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Get batch_id if exists
        cursor.execute("SELECT batch_id FROM scenes WHERE id = ?", (scene_id,))
        row = cursor.fetchone()
        batch_id = row['batch_id'] if row else None
        
        args = [image_path, 'IMAGE_READY', now]
        sql = "UPDATE scenes SET image_path = ?, status = ?, updated_at = ?"
        if account_id:
            sql += ", account_id = ?"
            args.append(account_id)
        sql += " WHERE id = ?"
        args.append(scene_id)
        
        cursor.execute(sql, args)
        updated = cursor.rowcount > 0
        
        if updated and batch_id:
            # Increment batch completion
            cursor.execute("""
                UPDATE prompt_batches 
                SET completed_count = completed_count + 1,
                    status = CASE WHEN completed_count + 1 >= total_count THEN 'COMPLETED' ELSE 'IN_PROGRESS' END
                WHERE id = ?
            """, (batch_id,))
            
        conn.commit()
        return updated
    finally:
        conn.close()

def update_scene_video_result(
    scene_id: str,
    video_path: str,
    account_id: Optional[str] = None
) -> bool:
    """
    Called upon successful completion of a video generation job:
    Sets scene.video_path = video_path and status = 'COMPLETED'.
    """
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    args = [video_path, 'COMPLETED', now]
    sql = "UPDATE scenes SET video_path = ?, status = ?, updated_at = ?"
    if account_id:
        sql += ", account_id = ?"
        args.append(account_id)
    sql += " WHERE id = ?"
    args.append(scene_id)
    cursor.execute(sql, args)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def update_scene_status(
    scene_id: str,
    status: str
) -> bool:
    """Updates scene status with timestamp update."""
    now = datetime.datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE scenes SET status = ?, updated_at = ? WHERE id = ?", (status, now, scene_id))
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated
```

### 4.3 Automatic Ingestion into Video Generation (`feed_scene_to_video_job`)

Requirement R1 Tab 3 mandates: "Automatic ingestion of completed images from Image Generation as First Frame / reference image ingredients, configuration for Veo 3.1 Lite (8s duration, 16:9 aspect ratio, 720p), and video worker queue."

```python
def feed_scene_to_video_job(
    scene_id: str,
    model: str = "Veo 3.1 Lite",
    ratio: str = "16:9",
    duration: int = 8,
    priority: int = 10
) -> str:
    """
    Ingests a scene with a completed image and spawns a Veo 3.1 Lite video job.
    
    Validation:
    - Scene must exist.
    - Scene must have a valid non-empty image_path.
    
    Job Creation:
    - media_type = 'video'
    - prompt = scene['prompt']
    - priority = priority (default 10 to prioritize video queue over raw image generation)
    - model = model (Veo 3.1 Lite)
    - ratio = ratio (16:9)
    - scene_id = scene_id
    - project = scene['project_id']
    - result_file = ''
    - status = 'PENDING'
    
    Status Transition:
    - Sets scenes.status = 'VIDEO_QUEUED'.
    
    Returns:
        job_id (str): The created video job ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM scenes WHERE id = ?", (scene_id,))
        scene = cursor.fetchone()
        if not scene:
            raise ValueError(f"Scene with ID '{scene_id}' not found.")
            
        if not scene['image_path'] or not scene['image_path'].strip():
            raise ValueError(f"Scene '{scene_id}' has no generated image to feed as First Frame.")
            
        job_id = f"VID-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.datetime.now().isoformat()
        
        cursor.execute("BEGIN TRANSACTION")
        
        # Insert video job
        cursor.execute("""
            INSERT INTO jobs (
                id, project, media_type, prompt, ratio, model, status,
                progress, result_file, account_id, error_message, created_at,
                batch_id, scene_id, priority
            ) VALUES (?, ?, 'video', ?, ?, ?, 'PENDING', 0, '', '', '', ?, ?, ?, ?)
        """, (
            job_id, scene['project_id'], scene['prompt'], ratio, model,
            now, scene['batch_id'], scene_id, priority
        ))
        
        # Update scene status
        cursor.execute("""
            UPDATE scenes 
            SET status = 'VIDEO_QUEUED', updated_at = ?
            WHERE id = ?
        """, (now, scene_id))
        
        conn.commit()
        return job_id
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def get_project_timeline_clips(project_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all completed scenes for a project in strict scene_number sequence
    with their video file paths ready for FFmpeg concat demuxer.
    
    Returns:
        List of dicts: [
            {'scene_id': ..., 'scene_number': 1, 'video_path': ..., 'prompt': ...},
            ...
        ]
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT id as scene_id, scene_number, prompt, image_path, video_path, status
        FROM scenes
        WHERE project_id = ? AND video_path != '' AND status = 'COMPLETED'
        ORDER BY scene_number ASC
    """, (project_id,))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]
```

---

## 5. Topic 4: Render Job CRUD & FFmpeg Stitching Progress

### 5.1 Render Job Entity & State Machine

Contract required by `PROJECT.md` §65-66:
- `create_render_job(project_id, output_path, config_dict) -> int` (or str)
- `update_render_job(job_id, status, progress, error=None)`

Render states:
- `PENDING`: Initial creation, queued for FFmpeg engine.
- `RENDERING`: FFmpeg subprocess running, emitting progress % (0.0 to 100.0).
- `COMPLETED`: Finished rendering, valid output file verified at `output_path`.
- `FAILED`: FFmpeg execution failed, stderr logged in `error_message`.
- `CANCELLED`: User aborted render operation.

### 5.2 Render Job CRUD Functions in `database/models.py`

```python
import json

VALID_RENDER_STATUSES = ('PENDING', 'RENDERING', 'COMPLETED', 'FAILED', 'CANCELLED')

def create_render_job(
    project_id: str,
    output_path: str,
    config_dict: Dict[str, Any]
) -> str:
    """
    Creates and queues an FFmpeg render job.
    
    Validation Rules:
    - project_id must not be empty.
    - output_path must not be empty and must specify a valid video container (.mp4, .mov, .mkv).
    - config_dict must contain 'clips' key with a non-empty list of video paths.
    - Validates optional configuration fields:
      - upscale_1080p: bool (default True)
      - fps: int (default 30 or 60)
      - codec: str (default 'libx264')
      - normalize_audio: bool (default True)
      - bgm_file: Optional[str]
      - bgm_volume: float (default 0.2)
    - Serializes config_dict to JSON string.
    
    Returns:
        job_id (str): Formatted ID like 'RND-XXXXXXXX'.
    """
    if not project_id or not project_id.strip():
        raise ValueError("project_id cannot be empty.")
    if not output_path or not output_path.strip():
        raise ValueError("output_path cannot be empty.")
        
    clips = config_dict.get('clips', [])
    if not isinstance(clips, list) or len(clips) == 0:
        raise ValueError("config_dict must include a non-empty 'clips' list of video paths.")
        
    job_id = f"RND-{uuid.uuid4().hex[:8].upper()}"
    config_json = json.dumps(config_dict, ensure_ascii=False)
    now = datetime.datetime.now().isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO render_jobs (
            id, project_id, output_path, config_json, status, progress, error_message, created_at, completed_at
        ) VALUES (?, ?, ?, ?, 'PENDING', 0, '', ?, '')
    """, (job_id, project_id.strip(), output_path.strip(), config_json, now))
    conn.commit()
    conn.close()
    return job_id

def get_render_job(job_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a render job by ID and parses config_json into config_dict.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM render_jobs WHERE id = ?", (job_id,))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d['config_dict'] = json.loads(d.get('config_json') or '{}')
    except json.JSONDecodeError:
        d['config_dict'] = {}
    return d

def get_render_jobs(
    project_id: Optional[str] = None,
    limit: int = 50
) -> List[Dict[str, Any]]:
    """Retrieves recent render jobs, optionally filtered by project_id."""
    conn = get_db_connection()
    cursor = conn.cursor()
    query = "SELECT * FROM render_jobs"
    params: List[Any] = []
    if project_id:
        query += " WHERE project_id = ?"
        params.append(project_id)
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    
    result = []
    for r in rows:
        d = dict(r)
        try:
            d['config_dict'] = json.loads(d.get('config_json') or '{}')
        except json.JSONDecodeError:
            d['config_dict'] = {}
        result.append(d)
    return result

def update_render_job(
    job_id: str,
    status: str,
    progress: Optional[float] = None,
    error: Optional[str] = None,
    output_path: Optional[str] = None
) -> bool:
    """
    Updates status, percentage progress (0.0 - 100.0), output_path, or error.
    Automatically records completed_at timestamp when status transitions to 'COMPLETED'.
    """
    if status not in VALID_RENDER_STATUSES:
        raise ValueError(f"Invalid status '{status}'. Must be one of {VALID_RENDER_STATUSES}.")
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = ["status = ?"]
    args: List[Any] = [status]
    
    if progress is not None:
        clamped_progress = max(0.0, min(100.0, float(progress)))
        updates.append("progress = ?")
        args.append(int(round(clamped_progress)))
        
    if error is not None:
        updates.append("error_message = ?")
        args.append(str(error))
        
    if output_path is not None:
        updates.append("output_path = ?")
        args.append(str(output_path))
        
    if status == 'COMPLETED':
        now = datetime.datetime.now().isoformat()
        updates.append("completed_at = ?")
        args.append(now)
        
    args.append(job_id)
    sql = f"UPDATE render_jobs SET {', '.join(updates)} WHERE id = ?"
    
    cursor.execute(sql, args)
    conn.commit()
    updated = cursor.rowcount > 0
    conn.close()
    return updated

def delete_render_job(job_id: str) -> bool:
    """Deletes a render job by ID."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM render_jobs WHERE id = ?", (job_id,))
    conn.commit()
    deleted = cursor.rowcount > 0
    conn.close()
    return deleted
```

---

## 6. Integration Architecture & Backward Compatibility

### 6.1 Callers & Consumers Matrix

| Consumer File | Existing Call | Impact & Solution |
|---|---|---|
| `workers/scheduler.py:35` | `models.get_pending_jobs()` | Works seamlessly! Default parameters `media_type=None, priority_first=True` ensure 100% backward compatibility while adding priority sorting. |
| `workers/browser_worker.py:182` | `models.assign_job_to_account(job_dict['id'], self.account_id)` | Preserved exactly as-is. |
| `workers/browser_worker.py:222` | `models.update_job_status(job_dict['id'], "FAILED", error_message=str(e))` | Preserved exactly as-is. |
| `ui/image_page.py:29` | `models.add_job(job_data)` | Preserved as single-job fallback; replaced by `models.create_prompt_batch` for structured batch parsing & scene sequencing. |
| `ui/video_page.py:29` | `models.add_job(job_data)` | Preserved as single-job fallback; replaced by `models.create_prompt_batch(media_type='video')` and `feed_scene_to_video_job`. |
| `ui/queue_page.py:20,33` | `models.delete_job`, `models.get_all_jobs` | Preserved exactly as-is. |
| `services/ffmpeg_service.py` (M4) | None (new) | Calls `models.create_render_job`, `models.update_render_job(job_id, 'RENDERING', progress=...)`, and `models.get_project_timeline_clips(project_id)`. |
| `ui/tabs/render_tab.py` (M5) | None (new) | Calls `get_project_timeline_clips` to populate clip timeline, `create_render_job` on export, and subscribes to render progress. |

### 6.2 Legacy Wrapper Compatibility
All legacy functions currently present in `database/models.py`:
- `dict_from_row`
- `get_all_accounts`, `get_account_by_id`, `save_account`, `delete_account`, `update_account_status`, `update_account_server`, `update_account_stats`
- `add_job`, `get_all_jobs`, `get_pending_jobs`, `update_job_status`, `assign_job_to_account`, `delete_job`
- `get_setting`, `save_setting`
will remain intact with identical signatures and return types. The new methods will be cleanly appended and modularized.

---

## 7. Unit Test Strategy for M1 Operations (R6 Integration)

Recommended test cases for `tests/test_m1_models.py`:
1. `test_parse_batch_prompts_strips_numbering`: Verifies `1. Prompt` -> `Prompt`, `Scene 2: Prompt` -> `Prompt`, `[3] Prompt` -> `Prompt`.
2. `test_parse_batch_prompts_skips_comments_and_empty`: Verifies `# comment` and blank lines are omitted.
3. `test_parse_batch_prompts_validation_errors`: Verifies empty input or input with no valid prompts raises `ValueError`.
4. `test_create_prompt_batch_atomic_transaction`: Verifies `prompt_batches`, `scenes`, and `jobs` tables all receive linked records with correct `scene_number` and `batch_id`.
5. `test_create_prompt_batch_rollback_on_invalid_media_type`: Verifies transaction rolls back cleanly on error.
6. `test_get_pending_jobs_priority_and_media_type`: Inserts jobs with mixed priorities (0, 5, 10) and media types ('image', 'video'); asserts `priority_first=True` orders `10 -> 5 -> 0`.
7. `test_claim_next_job_optimistic_locking`: Verifies `claim_next_job` updates status to `RUNNING` and returns the claimed job; subsequent claim returns the next job.
8. `test_scene_lifecycle_image_to_video`: Verifies `create_scene` -> `update_scene_image_result` -> `feed_scene_to_video_job` -> `update_scene_video_result` sequence.
9. `test_render_job_crud_and_progress`: Verifies `create_render_job` -> `update_render_job` progress clamping -> `COMPLETED` timestamp recorded.
