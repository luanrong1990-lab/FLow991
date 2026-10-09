# Original User Request

## 2026-09-08T03:29:44Z

Build VQPVEO3PRO - AI Video Generation Studio, a full-stack desktop application using Python (PySide6) and a Chrome Extension (Manifest V3) that automates multi-account image generation (Nano Banana 2) and video generation (Veo 3.1 Lite) on Google Flow, and stitches final 1080p videos with FFmpeg.

Working directory: d:/New folder (5)
Integrity mode: development

## Architecture & Technology Directives

- Desktop GUI & Core Orchestrator: Python + PySide6.
- Browser Management: Playwright (exclusively for persistent Chrome profile launching and session lifecycle; no Playwright DOM manipulation on Google Flow).
- DOM Automation: Chrome Extension (Manifest V3) acting as a dynamic "Flow Adapter".
- Inter-Process Communication: Chrome Native Messaging (stdin/stdout length-prefixed JSON protocol between Python host and Extension).
- Video Post-Processing: FFmpeg (concatenation, audio normalization, BGM mix, 1080p upscaling).
- Data Persistence: SQLite database for accounts, scenes, prompt batches, and render jobs.

## Requirements

### R1. PySide6 Desktop GUI with 5 Tab Views
Implement a dark-themed PySide6 application structured into:
1. Account Management: List Google Chrome profiles, assign operational roles (IMAGE_GEN vs VIDEO_GEN), show health status (READY, BUSY, RATE_LIMITED), and provide buttons to launch manual login or trigger Guided Mapping Setup Mode.
2. Image Generation: Multi-line batch prompt input (each line is an individual prompt), scene sequence list, queue progress tracking with real-time account-to-scene mapping.
3. Video Generation: Automatic ingestion of completed images from Image Generation as First Frame / reference image ingredients, configuration for Veo 3.1 Lite (8s duration, 16:9 aspect ratio, 720p), and video worker queue.
4. Stitch & Render (FFmpeg): Video timeline viewer for completed clips, export configuration (1080p upscale, FPS, codec, audio normalization, background music), and progress bar for rendering.
5. Dashboard: Metrics overview (total images/videos generated, success rate, queue depth, active worker statuses).

### R2. Chrome Extension with Guided Mapping & Execution Engine
Construct a Manifest V3 extension located under extension/ featuring two modes:
- Setup Mode (Guided Mapping): Visual overlay injected into Google Flow with an interactive pointer/highlighter. Guides the user step-by-step to click critical UI elements (Prompt Box, Generate Button, Download Link, Model Selector, Ratio options). Automatically extracts robust CSS/XPath selectors and serializes them into flow_adapter_config.json.
- Run Mode (DOM Executor): Reads flow_adapter_config.json and executes DOM automation (clearing previous text, typing prompt, setting model/ratio/count, triggering generation, detecting completion, and downloading output).

### R3. Bidirectional Chrome Native Messaging Host
Implement standard Chrome Native Messaging protocol:
- Python Native Messaging host script/executable communicating via 32-bit length-prefixed JSON over stdin/stdout.
- Extension background service worker connects via chrome.runtime.connectNative.
- Commands supported: generate_image, generate_video, enter_setup_mode, query_status.
- Responses supported: status_update (progress %, state), success (downloaded file path), error (failure details).
- Include an automated setup/install script to register the Native Messaging Host manifest in the Windows Registry (HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge).

### R4. Account Rotation & Priority Scheduling
- Maintain independent browser processes per Google account using Playwright persistent contexts with the extension loaded.
- Support dedicated accounts for image generation (parallelized across rotated accounts to mitigate rate limits) and priority accounts for video generation (Veo 3.1 Lite).
- Scheduler dispatches jobs round-robin to available, non-busy workers with configurable per-account cooldown delays.

### R5. FFmpeg Stitching & Post-Processing Engine
Implement a Python engine wrapping FFmpeg:
- Concat multiple scene video clips in timeline order.
- Normalize audio loudness across clips.
- Support optional background music (BGM) mixing with volume balancing.
- Upscale resolution to 1080p using standard high-efficiency codecs (H.264/AAC).
- Parse FFmpeg stdout/stderr to emit real-time render percentage back to PySide6 UI.

### R6. Automated Test Suite & Mocks
Implement a complete pytest test suite:
- Unit tests for Native Messaging binary framing (pack/unpack length-prefixed JSON messages).
- Mock orchestrator tests verifying round-robin queue distribution and state transitions.
- FFmpeg command builder unit tests verifying correct filter graphs and arguments.
- Extension schema validation tests ensuring flow_adapter_config.json matches the required structure.

## Acceptance Criteria

### Desktop UI & State
- [ ] PySide6 application initializes without errors and displays all 5 tabs (Accounts, Image Gen, Video Gen, Stitch & Render, Dashboard).
- [ ] SQLite database is created and migrations run cleanly on initial startup.
- [ ] Batch prompt parser splits multi-line text into distinct jobs in the SQLite queue.

### Chrome Extension & Native Messaging
- [ ] Chrome extension manifest.json passes Manifest V3 validation with permissions for nativeMessaging, storage, and downloads.
- [ ] Native Messaging Host script correctly decodes incoming length-prefixed JSON and encodes outgoing responses.
- [ ] Automated registry installer script writes the host manifest path to Windows Registry.
- [ ] Guided Mapping script accurately computes a unique CSS/XPath selector from a selected DOM element.

### Video Engine & Pipeline
- [ ] FFmpeg engine generates valid concat demuxer files and execution commands.
- [ ] Mock multi-clip render test runs and confirms output video creation.

### Automated Testing
- [ ] pytest test suite executes cleanly and all unit/mock tests pass.
