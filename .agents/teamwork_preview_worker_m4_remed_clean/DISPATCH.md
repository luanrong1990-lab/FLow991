## 2026-09-08T04:28:30Z

<USER_REQUEST>
You are teamwork_preview_worker_m4_remed_clean, a video post-processing remediation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m4_remed_clean
Project root is: d:/New folder (5)

STRICT OPERATIONAL CONSTRAINT:
DO NOT USE run_command! In this Windows background environment, run_command requires interactive user approval and blocks indefinitely. Use view_file and replace_file_content ONLY.

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.
Read Challenger M4 handoff report at: d:/New folder (5)/.agents/teamwork_preview_challenger_m4/handoff.md.
Read adversarial test suite at: d:/New folder (5)/tests/test_ffmpeg_adversarial.py.

Milestone M4 Remediation:
Your Exclusive Write Ownership:
- services/ffmpeg_service.py
- tests/test_ffmpeg_engine.py

Tasks:
1. In services/ffmpeg_service.py around line 319:
   In build_filter_graph():
   When upscale_1080p is False, the code currently appends "[0:v]copy[v_out]".
   In FFmpeg filtergraphs, 'copy' is NOT a valid filter (it is a CLI codec flag). The valid video passthrough filter in FFmpeg is 'null'.
   Use replace_file_content to change:
       filter_complex_parts.append("[0:v]copy[v_out]")
   To:
       filter_complex_parts.append("[0:v]null[v_out]")

2. In services/ffmpeg_service.py around line 325 and 353:
   In BGM mixing: when AI video clips from Veo 3.1 Lite have no audio stream (silent video), referencing "[0:a]" crashes FFmpeg with "matches no streams".
   Ensure audio stream specifier uses "[0:a?]" (optional audio stream) or cleanly handles silent input video clips.

3. In tests/test_ffmpeg_engine.py:
   Use replace_file_content to add a unit test `test_build_filter_graph_without_upscale_and_with_bgm` that asserts:
   - 'copy' is NOT present anywhere in the filter graph.
   - '[0:v]null[v_out]' is present.
   - Output video stream is properly mapped.

4. Deliver your complete handoff report to:
   d:/New folder (5)/.agents/teamwork_preview_worker_m4_remed_clean/handoff.md.
   Then send a message to parent reporting completion.
</USER_REQUEST>
