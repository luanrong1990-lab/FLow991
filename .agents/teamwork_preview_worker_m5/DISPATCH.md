## 2026-09-08T04:26:44Z

You are teamwork_preview_worker_m5, a desktop GUI implementation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m5
Project root is: d:/New folder (5)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.

Milestone: M5 - PySide6 Desktop GUI with 5 Tab Views
Your Exclusive Write Ownership:
- ui/__init__.py
- ui/theme.py
- ui/app_window.py
- ui/tabs/__init__.py
- ui/tabs/accounts_tab.py
- ui/tabs/image_gen_tab.py
- ui/tabs/video_gen_tab.py
- ui/tabs/render_tab.py
- ui/tabs/dashboard_tab.py
- main.py
- tests/test_gui.py

Implementation Tasks (Requirement R1):
1. ui/theme.py:
   - Modern dark theme palette (dark background #1e1e2e, card background #252538, accent #89b4fa, success #a6e3a1, warning #f9e2af, error #f38ba8, text #cdd6f4).
   - PySide6 stylesheet string with styled QTabWidget, QPushButton, QTableWidget, QLineEdit, QTextEdit, QProgressBar, QComboBox, QSpinBox.
   - Helper functions for status badges (READY, BUSY, RATE_LIMITED, PENDING, COMPLETED, FAILED).

2. ui/tabs/accounts_tab.py:
   - Connects to database.models (get_all_accounts, create_account, update_account_role).
   - Chrome profile list / table with ID, Profile Name, Role (IMAGE_GEN, VIDEO_GEN dropdown), Health Status badge, Success/Failure stats, Cooldown timer.
   - Action buttons: "Add Profile", "Refresh", "Launch Manual Login" (calls automation.browser.launch_persistent_chrome), "Trigger Setup Mode" (Guided Mapping).

3. ui/tabs/image_gen_tab.py:
   - Multi-line batch prompt text area with prompt format guidelines (numbered 1. , Scene 1: , [Shot #1], comments #, //).
   - "Parse Prompts" button using database.models.parse_batch_prompts.
   - Scene sequence table: Scene #, Prompt text, Assigned Account, Status, Output Thumbnail path.
   - "Queue Image Generation" button: calls create_prompt_batch & create_job(media_type='image', priority=0).
   - Queue progress bar and real-time status update timer.

4. ui/tabs/video_gen_tab.py:
   - Completed image ingredient selector (loads completed image scenes from DB).
   - Veo 3.1 Lite controls:
     - Duration: 8s (fixed or configurable)
     - Aspect ratio: 16:9 (also 1:1, 9:16)
     - Resolution: 720p
     - Motion guidance text prompt field.
   - "Queue Video Generation" button: calls create_job(media_type='video', priority=10).
   - Video scenes table with status, duration, and generated video file path.

5. ui/tabs/render_tab.py:
   - Timeline clip sequencer: lists video clips in scene order with Up/Down reordering and include checkboxes.
   - Export settings:
     - 1080p upscale checkbox (checked by default).
     - FPS spinbox (default 30).
     - Audio normalization checkbox (EBU R128 loudnorm).
     - BGM selector: file picker for audio file, volume ducking sliders (voice volume, bgm volume).
     - Output destination file picker.
   - "Start Stitch & Render" button: executes services.ffmpeg_service.FFmpegEngine in a QThread.
   - Real-time FFmpeg progress bar (0-100%) and render status label.

6. ui/tabs/dashboard_tab.py:
   - Real-time generation metrics cards: Total Images, Total Videos, Success Rate %, Queue Depth.
   - Active worker status table: account ID, profile, status (READY, BUSY, RATE_LIMITED), current job.
   - Scheduler controls: Start / Pause Scheduler.

7. ui/app_window.py:
   - QMainWindow with dark theme, window title "VQPVEO3PRO - AI Video Generation Studio".
   - Centered QTabWidget holding the 5 tabs.
   - QStatusBar displaying DB status and worker counts.

8. main.py:
   - PySide6 launcher: calls database.db.init_db(), starts JobScheduler, instantiates QApplication & MainWindow.
   - Gracefully stops JobScheduler on app exit.

9. tests/test_gui.py:
   - Comprehensive unit tests verifying:
     - All 5 tab classes instantiate correctly.
     - MainWindow initializes with 5 tabs and correct titles.
     - Theme stylesheet applies cleanly.
     - Model bindings and signal connections function without error.

10. Deliver handoff report to:
    d:/New folder (5)/.agents/teamwork_preview_worker_m5/handoff.md.

## 2026-09-08T04:27:44Z

**Context**: Shell command execution in this environment.
**Content**: In this Windows environment, subagent calls to `run_command` require interactive user approval which may block or time out. Please author all UI modules (`ui/theme.py`, `ui/tabs/*.py`, `ui/app_window.py`, `main.py`, `tests/test_gui.py`) using `write_to_file` and `replace_file_content`. Verify code structure and model-view bindings thoroughly via file inspection, and do not block waiting for `run_command`.
**Action**: Implement all PySide6 GUI components, write your completion report to `handoff.md`, and report back.
