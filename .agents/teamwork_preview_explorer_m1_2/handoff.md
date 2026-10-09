# Handoff Report: Batch Prompt Parser, Priority Queue & Scene Lifecycle (M1-2)

**Agent**: `teamwork_preview_explorer_m1_2`  
**Handoff Type**: Hard (Complete Investigation & Specification)  
**Milestone**: M1 - Database Architecture, Schema Migrations & Core Data Models  
**Project Root**: `d:/New folder (5)`  
**Report Location**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_2/handoff.md`  
**Reference Plan**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_2/plan.md`  

---

## 1. Observation

Direct code-level observations from the workspace:

### 1.1 Existing Multi-Line Prompt Processing
- **File**: `d:/New folder (5)/ui/image_page.py:10-18`
  ```python
  lines = [line.strip() for line in prompt_text.split('\n') if line.strip()]
  if not lines:
      ui.notify("Vui lòng nhập ít nhất 1 dòng Prompt!", type='warning')
      return
      
  success_count = 0
  for p in lines:
      job_id = f"IMG-{str(uuid.uuid4())[:8].upper()}"
  ```
  And `d:/New folder (5)/ui/video_page.py:10-18` has identical logic for video jobs.
- **Defects observed**:
  1. Splitting on `\n` does not sanitize carriage returns (`\r\n`).
  2. Numbered prefixes commonly found in LLM prompt batches (`1. `, `Scene 1: `, `[Shot 1] - `) are not stripped and are sent raw into the generation prompt.
  3. No comment line filtering (`#`, `//`).
  4. No batch entity or parent tracking is created; individual jobs are inserted into `jobs` table in isolated connections without transaction boundaries or rollback.
  5. No `scenes` records are created, losing narrative sequence index and scene-to-asset linking.

### 1.2 Existing Priority Queue Queries
- **File**: `d:/New folder (5)/database/models.py:176-184`
  ```python
  def get_pending_jobs():
      """Retrieves all pending jobs from the database sorted by created_at ASC."""
      conn = get_db_connection()
      cursor = conn.cursor()
      cursor.execute("SELECT * FROM jobs WHERE status = 'PENDING' ORDER BY created_at ASC")
      rows = cursor.fetchall()
      conn.close()
      return [dict_from_row(row) for row in rows]
  ```
- **Defects observed**:
  1. No `media_type` filtering: The scheduler cannot query strictly `'image'` jobs for `IMAGE_GEN` workers or strictly `'video'` jobs for `VIDEO_GEN` workers.
  2. No `priority` ordering: The table `jobs` lacks a `priority` column, and the query sorts only by `created_at ASC`. High-priority jobs (e.g. Veo 3.1 Lite video jobs per `PROJECT.md:85`) cannot jump the queue.
  3. No concurrency control: In multi-worker execution, `models.assign_job_to_account` (`database/models.py:210-216`) occurs after worker selection without an atomic check-and-set claim, creating potential race conditions.

### 1.3 Missing Scene Lifecycle Management
- **File**: `d:/New folder (5)/database/db.py:42-56`
  Only tables `accounts`, `jobs`, and `system_settings` are initialized.
- **Requirement**: `ORIGINAL_REQUEST.md:25` specifies:
  > "Video Generation: Automatic ingestion of completed images from Image Generation as First Frame / reference image ingredients, configuration for Veo 3.1 Lite (8s duration, 16:9 aspect ratio, 720p), and video worker queue."
- **Defects observed**:
  There is no `scenes` table or model methods to link a generated image output path to a scene, nor any method to feed that image path into a subsequent `video` generation job.

### 1.4 Missing Render Job CRUD & FFmpeg Tracking
- **File**: `d:/New folder (5)/PROJECT.md:65-66` defines required contract:
  - `create_render_job(project_id, output_path, config_dict) -> int`
  - `update_render_job(job_id, status, progress, error=None)`
- **Defects observed**:
  Neither `database/db.py` nor `database/models.py` has any schema or CRUD operations for `render_jobs`. There is no mechanism to track FFmpeg timeline concatenation, audio normalization, BGM mixing, or percentage progress (0-100%).

---

## 2. Logic Chain

1. **Premise 1 (Prompt Ingestion Integrity)**: Per `ORIGINAL_REQUEST.md:67` and `PROJECT.md:63`, prompt batching must split multi-line input into distinct jobs and scenes in the SQLite queue.
   - *Connecting Observation 1.1*: Naive `.split('\n')` in UI files leaves prefixes, lacks validation, and produces detached jobs with no scene ordering or atomic transactions.
   - *Deduction 1*: A dedicated `parse_batch_prompts(raw_text, strip_prefixes=True)` function must normalize newlines, trim prefixes via regex `PROMPT_PREFIX_REGEX`, filter comments, and enforce length bounds. An atomic `create_prompt_batch(name, text, media_type, project_id, ...)` must wrap `prompt_batches`, `scenes`, and `jobs` insertions into a single `BEGIN TRANSACTION ... COMMIT` block with rollback on failure.

2. **Premise 2 (Role-Aware Scheduling & Priority)**: Per `ORIGINAL_REQUEST.md:44` and `PROJECT.md:64, 85`, workers operate under specialized roles (`IMAGE_GEN` vs `VIDEO_GEN`) and video jobs have higher priority.
   - *Connecting Observation 1.2*: Current `get_pending_jobs()` does not filter by `media_type` and sorts strictly by `created_at ASC`.
   - *Deduction 2*: `get_pending_jobs` must accept `media_type: Optional[str] = None` and `priority_first: bool = True`, rendering SQL `ORDER BY priority DESC, created_at ASC`. To guarantee safe concurrent execution, an atomic `claim_next_job(account_id, media_type, priority_first)` must perform an atomic `UPDATE jobs SET status='RUNNING', account_id=? WHERE id=? AND status='PENDING'`.

3. **Premise 3 (Automated Pipeline: Image -> Video -> Concat)**: Per `ORIGINAL_REQUEST.md:24-26, 49-53`, the application operates as an automated studio where scenes progress from text prompts to generated images, to animated video clips, to final stitched 1080p video.
   - *Connecting Observation 1.3 & 1.4*: Without a `scenes` table and scene lifecycle state machine (`PENDING` -> `IMAGE_READY` -> `VIDEO_QUEUED` -> `COMPLETED`), images cannot be automatically passed as reference frames to Veo 3.1 Lite video generation.
   - *Deduction 3*: `database/models.py` must provide `create_scene`, `update_scene_image_result`, `feed_scene_to_video_job`, `update_scene_video_result`, and `get_project_timeline_clips`. For stitching, `create_render_job`, `get_render_job`, `update_render_job`, and `get_render_jobs` must be implemented with JSON serialization and percentage clamping.

4. **Premise 4 (Backward Compatibility)**: Multiple existing files (`workers/scheduler.py`, `workers/browser_worker.py`, `ui/queue_page.py`, `app.py`) rely on existing models signatures (`get_pending_jobs()`, `add_job()`, `get_all_jobs()`, etc.).
   - *Deduction 4*: New parameters in `get_pending_jobs(media_type=None, priority_first=True, limit=None)` must have defaults matching legacy behavior (`media_type=None`). Legacy functions must remain intact without signature breaking changes.

---

## 3. Caveats

1. **Schema Dependency on M1-1**: The methods specified herein depend on the database tables (`scenes`, `prompt_batches`, `render_jobs`) and column additions (`jobs.batch_id`, `jobs.scene_id`, `jobs.priority`, `jobs.completed_at`) being created by `m1_1` in `database/db.py`.
2. **Account Role Alignment with M1-3**: `claim_next_job` and scheduler integration assume account roles (`IMAGE_GEN` vs `VIDEO_GEN`) and cooldown timestamps as specified by `m1_3`.
3. **No Direct Code Modifications**: Per the explorer role constraints, all code changes are presented as concrete specifications and blueprints in `plan.md` and this handoff report. No production files were altered.

---

## 4. Conclusion

The specification for `database/models.py` is fully formulated and ready for implementation by the M1 worker agent. It delivers:
1. `parse_batch_prompts(raw_text, strip_prefixes=True, min_length=3, max_length=1500, max_prompts=100) -> List[str]`.
2. `create_prompt_batch(name, text, media_type="image", project_id="Default", model="Default", ratio="16:9", priority=0, strip_prefixes=True) -> Dict[str, Any]` with full transactional rollback.
3. `get_pending_jobs(media_type=None, priority_first=True, limit=None) -> List[Dict[str, Any]]` sorting by `priority DESC, created_at ASC`.
4. `claim_next_job(account_id, media_type=None, priority_first=True) -> Optional[Dict[str, Any]]` using atomic check-and-set.
5. Complete Scene CRUD and lifecycle methods: `create_scene`, `get_scene_by_id`, `get_scenes_by_project`, `update_scene_image_result`, `feed_scene_to_video_job`, `update_scene_video_result`, `get_project_timeline_clips`.
6. Complete Render Job CRUD: `create_render_job`, `get_render_job`, `get_render_jobs`, `update_render_job` (tracking 0.0-100.0% progress and timestamps), `delete_render_job`.
7. 100% backward compatibility for all existing callers in `workers/scheduler.py`, `workers/browser_worker.py`, and `ui/`.

---

## 5. Verification Method

To independently verify these specifications during implementation:

1. **Unit Tests (`tests/test_m1_models.py`)**:
   - Test prompt parsing with numbered prefixes:
     ```python
     prompts = parse_batch_prompts("1. First prompt\nScene 2: Second prompt\n# comment\n[3] Third prompt")
     assert prompts == ["First prompt", "Second prompt", "Third prompt"]
     ```
   - Test atomic batch creation:
     ```python
     batch_info = create_prompt_batch("Test Batch", "Prompt 1\nPrompt 2", media_type="image")
     assert batch_info["total_count"] == 2
     assert len(batch_info["scene_ids"]) == 2
     assert len(batch_info["job_ids"]) == 2
     ```
   - Test priority ordering:
     ```python
     # Insert job with priority 0, then job with priority 10
     jobs = get_pending_jobs(priority_first=True)
     assert jobs[0]["priority"] >= jobs[1]["priority"]
     ```
   - Test media_type filtering:
     ```python
     img_jobs = get_pending_jobs(media_type="image")
     assert all(j["media_type"] == "image" for j in img_jobs)
     ```
   - Test scene image to video ingestion:
     ```python
     vid_job_id = feed_scene_to_video_job(scene_id)
     assert vid_job_id.startswith("VID-")
     scene = get_scene_by_id(scene_id)
     assert scene["status"] == "VIDEO_QUEUED"
     ```
   - Test render job progress:
     ```python
     rnd_id = create_render_job("Proj1", "out.mp4", {"clips": ["c1.mp4", "c2.mp4"]})
     update_render_job(rnd_id, "RENDERING", progress=45.5)
     assert get_render_job(rnd_id)["progress"] == 46
     update_render_job(rnd_id, "COMPLETED", progress=100)
     assert get_render_job(rnd_id)["status"] == "COMPLETED"
     assert get_render_job(rnd_id)["completed_at"] != ""
     ```

2. **Files to Inspect**:
   - `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_2/plan.md` (complete source blueprints)
   - `d:/New folder (5)/database/models.py` (target implementation file)
   - `d:/New folder (5)/database/db.py` (target schema file)
