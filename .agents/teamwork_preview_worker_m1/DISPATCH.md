## 2026-09-08T03:42:40Z
You are teamwork_preview_worker_m1, an implementation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m1
Project root is: d:/New folder (5)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md immediately.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.

Read the exploratory findings and blueprints:
- d:/New folder (5)/.agents/teamwork_preview_explorer_m1_1/plan.md & handoff.md
- d:/New folder (5)/.agents/teamwork_preview_explorer_m1_2/plan.md & handoff.md
- d:/New folder (5)/.agents/teamwork_preview_explorer_m1_3/plan.md & handoff.md

Milestone: M1 - Database Architecture, Schema Migrations & Core Data Models
Your Exclusive Write Ownership:
- database/db.py
- database/models.py
- services/account_service.py (if updating account helper methods)
- tests/test_database.py

Implementation Objectives:
1. database/db.py:
   - Implement clean SQLite initialization with WAL mode (PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;).
   - Safe, idempotent migrations checking PRAGMA table_info before ALTER TABLE ADD COLUMN.
   - 6 tables: accounts (with role: 'IMAGE_GEN' | 'VIDEO_GEN', health_status: 'READY' | 'BUSY' | 'RATE_LIMITED', cooldown_until: REAL), scenes, prompt_batches, jobs (with batch_id, scene_id, priority, completed_at), render_jobs, system_settings.
2. database/models.py:
   - Implement all required methods per PROJECT.md interface contract:
     - get_accounts(role=None, status=None) & alias get_all_accounts
     - update_account_status(account_id, status=None, health_status=None, cooldown_until=None)
     - update_account_role(account_id, role)
     - set_account_cooldown(account_id, cooldown_seconds)
     - parse_batch_prompts(raw_text, strip_prefixes=True)
     - create_prompt_batch(name, text, media_type, project_id, ...)
     - get_pending_jobs(media_type=None, priority_first=True)
     - claim_next_job(account_id, media_type=None, priority_first=True)
     - create_render_job(project_id, output_path, config_dict)
     - update_render_job(job_id, status, progress=None, error=None)
     - get_render_job(job_id), get_render_jobs(project_id=None)
     - Scene lifecycle: create_scene, get_scene_by_id, get_scenes_by_project, update_scene_image_result, feed_scene_to_video_job, update_scene_video_result, get_project_timeline_clips
   - Retain full backward compatibility with existing callers.
3. tests/test_database.py:
   - Comprehensive pytest suite verifying fresh DB creation, idempotent migration on existing DB, batch prompt parsing with numbered prefix stripping, priority queue ordering, scene lifecycle transitions, account role & deterministic cooldown mechanics, and render job status updates.
4. Execute tests using pytest and verify 100% passing.

Output Requirements:
- Write your completion handoff report to d:/New folder (5)/.agents/teamwork_preview_worker_m1/handoff.md including Observation, Logic Chain, Caveats, Conclusion, and Verification Method with exact test commands and results.
