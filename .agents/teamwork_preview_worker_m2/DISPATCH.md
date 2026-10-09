## 2026-09-08T04:12:04Z

You are teamwork_preview_worker_m2, an implementation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m2
Project root is: d:/New folder (5)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md immediately.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.

Read the specification survey reports:
- d:/New folder (5)/.agents/teamwork_preview_spec_miner_survey_2/spec_report.md
- d:/New folder (5)/.agents/teamwork_preview_spec_miner_survey_2/handoff.md

Milestone: M2 - Chrome Extension (Manifest V3) & Native Messaging Host
Your Exclusive Write Ownership:
- extension/ (manifest.json, background.js, content.js, overlay.js, executor.js, flow_adapter_config.json, etc.)
- automation/native_host.py
- automation/com.vqp.flow_bridge.json
- automation/host_launcher.bat
- automation/install_host.py
- automation/install_host.bat
- tests/test_native_messaging.py
- tests/test_extension_schema.py

Implementation Objectives:
1. extension/manifest.json:
   - Manifest V3 compliant with permissions: ["nativeMessaging", "storage", "downloads", "tabs", "activeTab"].
   - Host permissions for Google Flow: ["https://labs.google/*", "https://*.google.com/*"].
   - Register service worker background.js and content scripts content.js, overlay.js, executor.js.
   - Fixed "key" field for stable extension ID.
2. automation/native_host.py:
   - Standard 32-bit length-prefixed JSON protocol over stdin/stdout using struct.pack('<I', len) and struct.unpack('<I', len).
   - Functions: read_message(stream=sys.stdin.buffer), send_message(data, stream=sys.stdout.buffer).
   - Handle commands: generate_image, generate_video, enter_setup_mode, query_status.
   - Produce responses: status_update (progress, state), success (file_path), error (message).
   - Integration with database/models.py for updating jobs and accounts.
3. automation/install_host.py:
   - Automated Python script using winreg to register host manifest in:
     HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge
   - Generate automation/com.vqp.flow_bridge.json and automation/host_launcher.bat with absolute paths.
4. extension/overlay.js (Setup Mode - Guided Mapping):
   - Interactive visual pointer/highlighter overlay.
   - Guides user step-by-step to click: Prompt Box, Generate Button, Download Link, Model Selector, Ratio options.
   - Robustly extracts unique CSS selector AND XPath selector for each element.
   - Serializes configuration to flow_adapter_config.json and chrome.storage.local.
5. extension/executor.js (Run Mode - DOM Executor):
   - Reads flow_adapter_config.json.
   - Executes DOM automation: clearing text, typing prompt, setting model/ratio, clicking generate, polling/detecting completion, triggering download.
6. tests/test_native_messaging.py:
   - Comprehensive unit tests for 32-bit binary framing: pack/unpack, byte order, empty payloads, Unicode, large payloads (1MB), and stream errors.
7. tests/test_extension_schema.py:
   - Unit tests validating extension/manifest.json (V3, permissions, service worker).
   - Unit tests validating extension/flow_adapter_config.json schema (css/xpath selectors for all required elements).
8. Execute tests with pytest and write completion handoff to:
   d:/New folder (5)/.agents/teamwork_preview_worker_m2/handoff.md.
