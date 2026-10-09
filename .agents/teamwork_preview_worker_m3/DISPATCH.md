## 2026-09-08T04:12:38Z
You are teamwork_preview_worker_m3, an implementation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m3
Project root is: d:/New folder (5)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md immediately.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.

Read survey findings in:
- d:/New folder (5)/.agents/teamwork_preview_explorer_survey_3/survey_report.md & handoff.md

Milestone: M3 - Playwright Browser Manager & Account Rotation Scheduler
Your Exclusive Write Ownership:
- automation/browser.py
- workers/browser_worker.py
- workers/scheduler.py
- tests/test_scheduler.py

Implementation Objectives:
1. automation/browser.py:
   - Ensure launch_persistent_chrome passes extension path ('extension/'), anti-automation args ('--disable-blink-features=AutomationControlled'), and removes navigator.webdriver.
   - Robust Chrome discovery: search standard Windows Chrome paths with fallback to Playwright bundled Chromium.
2. workers/browser_worker.py:
   - Fix asyncio.get_event_loop() crash on line 236: ensure thread has a dedicated event loop or use asyncio.run/loop runner.
   - Pass executable_path=chrome_path to p.chromium.launch_persistent_context.
   - Integrate with database/models.py:
     - When starting a job, set account health_status='BUSY'.
     - On job completion: update account success count, calculate cooldown (models.set_account_cooldown).
     - On rate-limit: mark account health_status='RATE_LIMITED', apply backoff cooldown (e.g. 60s).
3. workers/scheduler.py:
   - Round-robin priority scheduler:
     - Dispatches jobs using models.get_pending_jobs(priority_first=True) so Veo 3.1 Lite video jobs (priority 10) preempt image jobs (priority 0).
     - Matches job media_type ('image' vs 'video') to account role ('IMAGE_GEN' vs 'VIDEO_GEN').
     - Checks timestamp cooldowns: only dispatches to workers where models.is_account_ready() returns True (cooldown_until <= now).
     - Atomically claims jobs via models.claim_next_job(account_id, media_type, priority_first=True).
     - Thread-safe start() / stop() lifecycle methods.
4. tests/test_scheduler.py:
   - Pytest unit tests for the scheduler with mock workers:
     - test_round_robin_distribution: verifies balanced round-robin dispatch across idle accounts.
     - test_priority_scheduling: verifies video jobs jump ahead of older image jobs.
     - test_role_filtering: verifies IMAGE_GEN accounts only receive image jobs, VIDEO_GEN accounts only receive video jobs.
     - test_cooldown_delay_enforcement: verifies workers in cooldown are skipped until cooldown timestamp expires.
     - test_rate_limit_backoff: verifies rate-limited workers receive backoff delays and resume when expired.
5. Run tests with pytest and write completion handoff to:
   d:/New folder (5)/.agents/teamwork_preview_worker_m3/handoff.md.
