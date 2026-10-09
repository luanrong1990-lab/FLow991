# AI SCRIPT-TO-VIDEO DESKTOP APPLICATION
## System Architecture & Engineering Specification

**Document Version:** 1.0  
**Target Platform:** Windows 10/11  
**Application Type:** Local Desktop Application  
**Primary Framework:** Python + PySide6  
**Architecture:** Modular Desktop + Provider-Based AI + Chrome Extension Bridge

---

# 1. PURPOSE

This document defines the technical architecture for a production-ready Windows desktop application that converts a topic, idea, or article into a complete narrated video.

The application must run primarily on the user's personal computer.

The system should use local processing whenever practical and external APIs only when necessary.

The application must be modular so individual components can be replaced without rewriting the entire system.

The most important architectural requirement is that Google Flow must be integrated through a dedicated **Flow Controller** rather than embedding Google Flow-specific logic throughout the application.

---

# 2. HIGH-LEVEL WORKFLOW

The complete workflow is:

```text
USER INPUT
   │
   ├── Topic
   ├── Idea
   ├── Article
   ├── Article URL
   └── Text File
   │
   ▼
SOURCE PROCESSOR
   │
   ▼
AI SCRIPT ENGINE
   │
   ├── Script
   ├── 5 Titles
   ├── Description
   ├── Tags
   └── Hashtags
   │
   ▼
VOICE IMPORT
   │
   ▼
ASR + VAD
   │
   ▼
SEMANTIC SEGMENTATION
   │
   ▼
VISUAL PROMPT ENGINE
   │
   ▼
IMAGE PROVIDER
   │
   ├── Google Flow
   ├── Local ComfyUI
   ├── Flux
   ├── Gemini Image
   └── Other providers
   │
   ▼
IMAGE / VOICE GRID
   │
   ├── Image
   ├── Voice
   ├── Prompt
   ├── Effects
   └── Subtitles
   │
   ▼
TIMELINE ENGINE
   │
   ▼
FFMPEG RENDER ENGINE
   │
   ▼
FINAL MP4
```

---

# 3. CORE ARCHITECTURAL PRINCIPLE

The application must follow this principle:

```text
UI
 ↓
Application Services
 ↓
Domain Models
 ↓
Provider Interfaces
 ↓
Provider Implementations
```

The GUI must NOT directly call:

- Google Flow
- Chrome
- FFmpeg
- Whisper
- AI APIs

Instead, the GUI communicates with application services.

Example:

```text
UI
 ↓
VisualGenerationService
 ↓
ImageProvider
 ↓
FlowProvider
 ↓
FlowController
 ↓
Chrome Extension
 ↓
Google Flow
```

This separation is mandatory.

---

# 4. PROJECT STRUCTURE

Recommended project structure:

```text
ai_video_studio/
│
├── main.py
│
├── app/
│   │
│   ├── config/
│   │   ├── settings.py
│   │   ├── paths.py
│   │   └── secrets.py
│   │
│   ├── core/
│   │   ├── events.py
│   │   ├── exceptions.py
│   │   ├── result.py
│   │   └── dependency_manager.py
│   │
│   ├── domain/
│   │   ├── project.py
│   │   ├── script.py
│   │   ├── voice_segment.py
│   │   ├── visual_prompt.py
│   │   ├── image_asset.py
│   │   ├── subtitle.py
│   │   ├── effect.py
│   │   ├── timeline.py
│   │   ├── chrome_profile.py
│   │   └── flow_job.py
│   │
│   ├── services/
│   │   ├── project_service.py
│   │   ├── script_service.py
│   │   ├── voice_service.py
│   │   ├── visual_service.py
│   │   ├── subtitle_service.py
│   │   ├── render_service.py
│   │   └── flow_service.py
│   │
│   ├── ai/
│   │   ├── base_provider.py
│   │   ├── openai_provider.py
│   │   ├── gemini_provider.py
│   │   ├── openrouter_provider.py
│   │   └── prompt_manager.py
│   │
│   ├── audio/
│   │   ├── asr_engine.py
│   │   ├── vad_engine.py
│   │   ├── segmentation_engine.py
│   │   └── subtitle_engine.py
│   │
│   ├── visual/
│   │   ├── image_provider.py
│   │   ├── flow_provider.py
│   │   ├── local_image_provider.py
│   │   ├── prompt_engine.py
│   │   └── character_manager.py
│   │
│   ├── chrome/
│   │   ├── chrome_manager.py
│   │   ├── profile_manager.py
│   │   ├── bridge_server.py
│   │   ├── bridge_protocol.py
│   │   └── flow_controller.py
│   │
│   ├── video/
│   │   ├── timeline_engine.py
│   │   ├── effect_engine.py
│   │   ├── karaoke_engine.py
│   │   ├── ffmpeg_engine.py
│   │   └── render_pipeline.py
│   │
│   ├── storage/
│   │   ├── database.py
│   │   ├── project_repository.py
│   │   ├── cache_manager.py
│   │   └── file_manager.py
│   │
│   └── ui/
│       ├── main_window.py
│       ├── project_view.py
│       ├── script_view.py
│       ├── voice_view.py
│       ├── visual_grid.py
│       ├── timeline_view.py
│       ├── export_view.py
│       └── settings_view.py
│
├── chrome_extension/
│   ├── manifest.json
│   ├── background/
│   │   └── service_worker.js
│   ├── content/
│   │   └── flow_controller.js
│   ├── calibration/
│   │   ├── calibration.js
│   │   └── calibration.css
│   ├── popup/
│   │   ├── popup.html
│   │   ├── popup.js
│   │   └── popup.css
│   └── shared/
│       └── protocol.js
│
├── tests/
│
├── projects/
│
├── requirements.txt
├── requirements.lock.txt
├── ARCHITECTURE.md
├── README.md
├── build_windows.bat
└── run.bat
```

---

# 5. DOMAIN MODELS

The system must use explicit data models.

Use Pydantic or dataclasses.

Core models:

```text
Project
Script
VoiceTrack
VoiceSegment
VisualPrompt
ImageAsset
SubtitleTrack
Effect
TimelineItem
ChromeProfile
FlowJob
RenderSettings
```

Each model must have a stable ID.

Example:

```json
{
    "segment_id": "SEG_0001",
    "start": 0.0,
    "end": 6.8,
    "text": "Many people reach retirement...",
    "visual_prompt": "...",
    "image_path": "images/SEG_0001.png",
    "status": "completed"
}
```

---

# 6. PROJECT DIRECTORY

Each project should have its own isolated directory.

Example:

```text
projects/
└── retirement_story/
    │
    ├── project.json
    ├── project.db
    │
    ├── source/
    │
    ├── script/
    │   ├── script.json
    │   ├── script.txt
    │   └── seo.json
    │
    ├── voice/
    │   ├── original.wav
    │   └── normalized.wav
    │
    ├── segments/
    │   ├── transcript.json
    │   └── segments.json
    │
    ├── prompts/
    │
    ├── images/
    │
    ├── subtitles/
    │
    ├── preview/
    │
    ├── output/
    │
    └── logs/
```

---

# 7. AI PROVIDER ARCHITECTURE

Never hard-code an AI provider into business logic.

Define:

```python
class AIProvider:
    """
    Giao diện chung cho tất cả nhà cung cấp AI.
    """

    def generate(self, prompt: str) -> str:
        raise NotImplementedError
```

Implement:

```text
GeminiProvider
OpenAIProvider
OpenRouterProvider
CustomOpenAICompatibleProvider
```

The application uses:

```text
AIProvider
```

instead of directly referencing Gemini/OpenAI.

---

# 8. IMAGE PROVIDER ARCHITECTURE

The same principle applies to image generation.

Define:

```python
class ImageProvider:
    """
    Giao diện chung cho tất cả hệ thống tạo ảnh.
    """

    def generate(self, request):
        raise NotImplementedError
```

Possible implementations:

```text
FlowProvider
ComfyUIProvider
FluxProvider
GeminiImageProvider
OpenAIImageProvider
```

The UI must only communicate with:

```text
VisualGenerationService
```

and must not know how images are generated.

---

# 9. FLOW PROVIDER

Google Flow is treated as one image-generation provider.

Architecture:

```text
VisualGenerationService
        │
        ▼
ImageProvider
        │
        ▼
FlowProvider
        │
        ▼
FlowController
        │
        ▼
Local Bridge
        │
        ▼
Chrome Extension
        │
        ▼
Real Chrome
        │
        ▼
Google Flow
```

This is the most important architectural separation in the project.

---

# 10. FLOW CONTROLLER

`FlowController` is responsible for Google Flow-specific orchestration.

It must NOT be responsible for:

- UI
- AI script generation
- Voice processing
- Video rendering
- Subtitle generation

It only manages Flow-related operations.

Responsibilities:

```text
Open Flow
Check Flow availability
Select Chrome profile
Send prompt
Wait for generation
Detect generation result
Request download
Verify download
Return image path
Report errors
Retry failed jobs
```

---

# 11. FLOW CONTROLLER INTERFACE

Recommended interface:

```python
class FlowController:

    async def connect(self):
        """Kết nối với Chrome Extension."""

    async def open_flow(self, profile_id):
        """Mở Google Flow bằng Chrome profile đã chọn."""

    async def generate_image(self, job):
        """Gửi prompt và chờ Flow tạo ảnh."""

    async def download_result(self, job):
        """Tải kết quả về máy."""

    async def cancel_job(self, job_id):
        """Hủy job đang chạy."""

    async def reconnect(self):
        """Kết nối lại nếu extension bị mất kết nối."""
```

---

# 12. FLOW JOB

Every image generation request must become a `FlowJob`.

Example:

```json
{
    "job_id": "FLOW_JOB_001",
    "project_id": "PROJECT_001",
    "segment_id": "SEG_001",
    "profile_id": "PROFILE_01",
    "prompt": "Cinematic retirement scene...",
    "status": "pending",
    "retry_count": 0
}
```

Statuses:

```text
PENDING
QUEUED
CONNECTING
SUBMITTING
GENERATING
READY
DOWNLOADING
COMPLETED
FAILED
CANCELLED
```

---

# 13. FLOW JOB QUEUE

Do not generate all images simultaneously.

Use a queue:

```text
                 ┌──────────────┐
                 │ Flow Job Queue│
                 └──────┬───────┘
                        │
          ┌─────────────┼─────────────┐
          ▼             ▼             ▼
      Profile 1     Profile 2     Profile 3
          │             │             │
          ▼             ▼             ▼
       Chrome        Chrome        Chrome
          │             │             │
          ▼             ▼             ▼
        Flow           Flow          Flow
```

The queue manager must control:

- Maximum concurrent jobs
- Profile availability
- Retry count
- Rate limits
- Failed jobs
- Download completion

---

# 14. CHROME PROFILE MANAGER

The application must support user-created Chrome profiles.

Store only references required to launch Chrome.

Example:

```json
{
    "profile_id": "PROFILE_01",
    "name": "Google Account 1",
    "chrome_user_data_dir": "...",
    "profile_directory": "Profile 1"
}
```

Never store:

- Google password
- Authentication cookies
- Sensitive authentication tokens

The user logs into Google normally.

---

# 15. CHROME LAUNCHER

The desktop application should launch Chrome using the selected profile.

Conceptually:

```text
Python Application
       │
       ▼
ChromeManager
       │
       ▼
Chrome executable
       │
       ▼
Selected Chrome profile
       │
       ▼
https://flow.google.com/
```

The exact Chrome executable path must be detected automatically.

Possible locations should be checked.

Allow manual override in Settings.

---

# 16. CHROME EXTENSION

Use Chrome Manifest V3.

The extension is responsible for interacting with the actual Flow page.

It should NOT contain the project's business logic.

It should act as a browser-side automation adapter.

Responsibilities:

```text
Receive commands
Find Flow UI elements
Insert prompts
Click controls
Observe generation state
Identify generated result
Trigger download
Return status
```

---

# 17. LOCAL BRIDGE

Communication architecture:

```text
PySide6
   │
   │ WebSocket
   ▼
Local Bridge
   │
   │ WebSocket
   ▼
Chrome Extension
```

The bridge should listen only on:

```text
127.0.0.1
```

Do not expose the bridge publicly.

Use a local authentication token.

---

# 18. BRIDGE PROTOCOL

All communication must use JSON.

Example request:

```json
{
    "type": "GENERATE_IMAGE",
    "request_id": "REQ_001",
    "project_id": "PROJECT_001",
    "segment_id": "SEG_001",
    "profile_id": "PROFILE_01",
    "prompt": "Cinematic elderly man walking..."
}
```

Response:

```json
{
    "type": "GENERATION_STATUS",
    "request_id": "REQ_001",
    "status": "GENERATING"
}
```

Completion:

```json
{
    "type": "GENERATION_COMPLETED",
    "request_id": "REQ_001",
    "segment_id": "SEG_001",
    "download_path": "C:/Projects/.../SEG_001.png"
}
```

Error:

```json
{
    "type": "ERROR",
    "request_id": "REQ_001",
    "code": "FLOW_GENERATION_FAILED",
    "message": "Generation failed."
}
```

---

# 19. EXTENSION CONNECTION STATE

The desktop application must display:

```text
Chrome Extension:
● Connected
```

or:

```text
Chrome Extension:
● Disconnected
```

Additional state:

```text
Chrome Profile:
Connected

Google Flow:
Available

Flow Job:
Generating
```

---

# 20. CALIBRATION SYSTEM

Google Flow's web interface can change.

Therefore the extension must include a Calibration System.

The first time Flow integration is configured:

```text
Calibration Wizard
        │
        ▼
Open Google Flow
        │
        ▼
Find Prompt Input
        │
        ▼
User confirms
        │
        ▼
Find Generate button
        │
        ▼
User confirms
        │
        ▼
Find Result container
        │
        ▼
User confirms
        │
        ▼
Find Download control
        │
        ▼
User confirms
```

Calibration data is stored locally.

---

# 21. CALIBRATION DATA

Do not save arbitrary screen coordinates as the primary method.

Prefer:

```text
DOM selectors
Accessibility attributes
Semantic labels
Stable attributes
Element relationships
```

Example:

```json
{
    "prompt_input": {
        "strategy": "semantic",
        "selector": "..."
    },
    "generate_button": {
        "strategy": "semantic",
        "selector": "..."
    }
}
```

Selectors must be treated as configuration and may be recalibrated.

---

# 22. FLOW UI DETECTION STRATEGY

Use this priority:

```text
Priority 1:
DOM / semantic element detection

Priority 2:
Accessibility information

Priority 3:
Stable element attributes

Priority 4:
Visual element recognition

Priority 5:
Coordinate-based interaction
```

Coordinate-based automation should be the last fallback.

Do NOT build the entire system around fixed screen coordinates.

---

# 23. FLOW STATE MACHINE

FlowController should use a state machine.

Example:

```text
DISCONNECTED
      │
      ▼
CONNECTING
      │
      ▼
CONNECTED
      │
      ▼
FLOW_READY
      │
      ▼
PROMPT_SUBMITTING
      │
      ▼
GENERATING
      │
      ├──── ERROR ────► RETRY
      │
      ▼
RESULT_READY
      │
      ▼
DOWNLOADING
      │
      ▼
COMPLETED
```

This prevents uncontrolled browser actions.

---

# 24. FLOW TIMEOUTS

Every operation must have a timeout.

Examples:

```text
Connect timeout
Prompt timeout
Generation timeout
Download timeout
```

Never wait forever.

Example:

```python
# Giới hạn thời gian chờ Flow phản hồi để tránh job bị treo vô hạn.
FLOW_GENERATION_TIMEOUT = 300
```

---

# 25. RETRY SYSTEM

Failed jobs should be retried.

Example:

```text
Attempt 1
   ↓
Failed
   ↓
Wait
   ↓
Attempt 2
   ↓
Failed
   ↓
Wait
   ↓
Attempt 3
   ↓
Failed
   ↓
Mark FAILED
```

Retry count must be configurable.

---

# 26. FLOW RECOVERY

If Chrome closes:

```text
Chrome disconnected
       ↓
Save job state
       ↓
Restart Chrome
       ↓
Reconnect Extension
       ↓
Verify Flow
       ↓
Resume unfinished job
```

Do not restart completed jobs.

---

# 27. FLOW PROFILE ROTATION

Multiple Chrome profiles can be used as independent workers.

Example:

```text
PROFILE_01 → BUSY
PROFILE_02 → AVAILABLE
PROFILE_03 → BUSY
PROFILE_04 → AVAILABLE
```

The scheduler assigns a job to an available profile.

The system must NOT implement mechanisms intended to bypass:

- Google limits
- Account restrictions
- Quotas
- Anti-abuse systems
- Terms of service

Profile management exists for legitimate user-controlled sessions and workload organization.

---

# 28. VOICE PROCESSING ARCHITECTURE

Voice pipeline:

```text
Audio File
    ↓
Audio Validation
    ↓
Normalization
    ↓
VAD
    ↓
faster-whisper
    ↓
Word timestamps
    ↓
Sentence detection
    ↓
Semantic grouping
    ↓
VoiceSegment[]
```

Use GPU acceleration when available.

---

# 29. SEMANTIC SEGMENTATION

Do not split audio using fixed intervals only.

Segmentation should consider:

```text
Silence
Sentence boundaries
Punctuation
Speech rate
Semantic meaning
Maximum duration
Minimum duration
```

Preferred segment duration:

```text
5–8 seconds
```

Allowed range:

```text
2–12 seconds
```

These values must be configurable.

---

# 30. VISUAL PROMPT ENGINE

For each `VoiceSegment`:

```text
VoiceSegment
      ↓
PromptEngine
      ↓
VisualPrompt
```

The prompt should contain:

```text
Subject
Environment
Characters
Character consistency
Lighting
Camera
Composition
Mood
Time period
Visual style
Negative instructions
```

---

# 31. CHARACTER CONSISTENCY

Create a `CharacterManager`.

Example:

```text
Character
 ├── ID
 ├── Age
 ├── Gender
 ├── Face
 ├── Hair
 ├── Clothing
 ├── Body type
 ├── Personality
 └── Visual style
```

Prompts should reuse character information.

---

# 32. IMAGE ASSET MANAGEMENT

Every image must be associated with:

```text
project_id
segment_id
prompt_id
provider
generation_time
file_path
status
```

Example:

```text
SEG_0001.png
SEG_0002.png
SEG_0003.png
```

Never rely only on the original filename returned by Flow.

---

# 33. GRID EDITOR

The main visual editor uses cards.

Each card represents:

```text
One Voice Segment
+
One Image
+
One Subtitle
+
One Effect
```

Card controls:

```text
Play Voice
Edit Text
Edit Prompt
Regenerate Image
Replace Image
Select Effect
Edit Subtitle
Preview
```

---

# 34. TIMELINE ARCHITECTURE

The timeline is data-driven.

Each item has:

```text
start
end
duration
asset
effect
subtitle
```

Changing one segment's duration must update dependent timeline elements.

Do not manually maintain multiple independent timing systems.

---

# 35. KARAOKE ENGINE

Use word-level ASR timestamps.

Generate subtitle events.

Support:

```text
Word highlight
Phrase highlight
Sentence highlight
```

The subtitle renderer should support:

```text
Font
Size
Position
Stroke
Shadow
Background
Alignment
Maximum line length
Highlight timing
```

---

# 36. SMART LINE BREAKING

Default maximum:

```text
70 characters
```

The algorithm should prefer:

```text
Phrase boundaries
Punctuation
Word boundaries
Natural linguistic units
```

Never split inside a word.

Avoid unnatural subtitle segmentation.

---

# 37. VIDEO EFFECT ENGINE

Effects are stored as parameters.

Example:

```json
{
    "type": "zoom_in",
    "start_scale": 1.0,
    "end_scale": 1.12,
    "duration": 6.8
}
```

Original images must remain untouched.

---

# 38. RENDER ENGINE

Use FFmpeg as the primary rendering backend.

Pipeline:

```text
Image
+
Voice
+
Effects
+
Subtitle
+
BGM
+
Transitions
        ↓
FFmpeg Filter Graph
        ↓
Video
```

The rendering layer must be independent from the GUI.

---

# 39. PREVIEW ENGINE

Preview should use lower-resolution media.

Do not render 4K previews unnecessarily.

Example:

```text
Preview:
720p

Final:
1080p / 1440p / 4K
```

---

# 40. DATABASE

Use SQLite.

Suggested tables:

```text
projects
scripts
voice_tracks
voice_segments
visual_prompts
images
subtitles
effects
timeline_items
chrome_profiles
flow_jobs
render_jobs
```

The database stores project metadata.

Actual media files remain in the project directory.

---

# 41. CACHING

Cache:

```text
Article extraction
AI script
SEO metadata
ASR
Segmentation
Visual prompts
Flow results
Subtitle timestamps
```

The system should avoid repeating expensive operations unnecessarily.

---

# 42. THREADING MODEL

PySide6 UI must never block.

Recommended:

```text
UI Thread
   │
   ├── Worker: AI
   ├── Worker: ASR
   ├── Worker: Flow
   ├── Worker: Download
   └── Worker: FFmpeg
```

Use:

```text
QThread
QThreadPool
QRunnable
```

or an equivalent architecture.

---

# 43. EVENT-DRIVEN UI

Services should emit events.

Examples:

```text
SCRIPT_GENERATION_STARTED
SCRIPT_GENERATION_COMPLETED

ASR_STARTED
ASR_COMPLETED

FLOW_CONNECTED
FLOW_JOB_STARTED
FLOW_JOB_COMPLETED
FLOW_JOB_FAILED

RENDER_STARTED
RENDER_PROGRESS
RENDER_COMPLETED
```

The GUI listens to events instead of directly controlling backend modules.

---

# 44. ERROR MANAGEMENT

Create centralized error handling.

Errors should contain:

```text
code
message
module
severity
timestamp
recoverable
```

Example:

```json
{
    "code": "FLOW_TIMEOUT",
    "message": "Google Flow did not finish within the configured timeout.",
    "module": "FlowController",
    "recoverable": true
}
```

---

# 45. LOGGING

Use structured application logs.

Example:

```text
logs/application.log
logs/flow.log
logs/render.log
logs/ai.log
```

Do not log API keys or authentication credentials.

---

# 46. SECURITY

The application must:

- Store API keys securely where possible.
- Never log API keys.
- Never store Google passwords.
- Never extract Google cookies.
- Never bypass authentication.
- Bind the local bridge to localhost.
- Authenticate local bridge messages.
- Validate all commands received from the extension.

---

# 47. DEPENDENCY MANAGEMENT

At startup:

```text
Check Python
Check packages
Check FFmpeg
Check Chrome
Check GPU
Check CUDA
```

If a dependency is missing:

```text
Detect
 ↓
Install
 ↓
Verify
 ↓
Continue
```

Required dependencies may include:

```text
PySide6
Pydantic
faster-whisper
websockets
requests
httpx
numpy
soundfile
ffmpeg-python
```

Use additional libraries only when they are justified.

Do not install unnecessary packages.

---

# 48. GPU MANAGEMENT

The target hardware is approximately:

```text
Ryzen 9 5950X
32 GB RAM
RTX 3060 12 GB
```

The system should:

- Detect NVIDIA GPU.
- Detect CUDA support.
- Prefer GPU ASR when available.
- Use FP16 when supported.
- Avoid loading unnecessary models simultaneously.
- Release GPU memory when modules finish.
- Fall back to CPU when GPU processing fails.

---

# 49. SETTINGS

Settings should be stored separately from project data.

Categories:

```text
AI
Voice
ASR
Chrome
Google Flow
Image Providers
Subtitles
Video
FFmpeg
Performance
Storage
Logging
```

---

# 50. FIRST-RUN SETUP

First launch:

```text
Welcome
   ↓
Dependency Check
   ↓
FFmpeg Check
   ↓
Chrome Check
   ↓
GPU Check
   ↓
AI Configuration
   ↓
Chrome Extension Configuration
   ↓
Flow Calibration
   ↓
System Test
   ↓
Ready
```

---

# 51. GOOGLE FLOW SYSTEM TEST

After calibration, run a controlled test.

Example:

```text
Test prompt:
"A simple cinematic landscape"
```

The system verifies:

```text
Chrome opened
Extension connected
Flow opened
Prompt inserted
Generate executed
Result detected
Download completed
Image exists
```

Only after successful testing should Flow be marked:

```text
READY
```

---

# 52. FLOW PROVIDER INDEPENDENCE

The application must work without Google Flow.

If Flow is unavailable:

```text
FlowProvider
    ↓
Unavailable
```

The user can select another provider:

```text
ComfyUI
Flux
Gemini
Other
```

The rest of the application remains unchanged.

---

# 53. PROVIDER INTERFACE EXAMPLE

```python
class ImageProvider:
    """
    Giao diện chung để hệ thống có thể sử dụng nhiều nhà cung cấp tạo ảnh.
    """

    def generate(self, request):
        raise NotImplementedError

    def is_available(self):
        raise NotImplementedError

    def cancel(self, job_id):
        raise NotImplementedError
```

Flow-specific implementation:

```python
class FlowProvider(ImageProvider):
    """
    Provider kết nối Google Flow thông qua Chrome Extension.
    """

    def __init__(self, flow_controller):
        self.flow_controller = flow_controller

    async def generate(self, request):
        # Chuyển yêu cầu tạo ảnh tới FlowController.
        return await self.flow_controller.generate_image(request)
```

The UI must never instantiate `FlowController` directly.

---

# 54. DATA FLOW EXAMPLE

When the user clicks:

```text
Generate Images
```

the process must be:

```text
UI
 ↓
VisualService
 ↓
PromptEngine
 ↓
ImageProvider
 ↓
FlowProvider
 ↓
FlowController
 ↓
Bridge
 ↓
Chrome Extension
 ↓
Google Flow
```

Result:

```text
Google Flow
 ↓
Chrome Extension
 ↓
Bridge
 ↓
FlowController
 ↓
FlowProvider
 ↓
VisualService
 ↓
ProjectRepository
 ↓
UI
```

---

# 55. DO NOT COUPLE MODULES

Bad:

```python
# UI trực tiếp điều khiển Chrome.
chrome.click(...)
flow.generate(...)
```

Good:

```python
# UI chỉ yêu cầu service tạo ảnh.
visual_service.generate_images(project_id)
```

The service decides which provider to use.

---

# 56. CODE DOCUMENTATION

All important code must contain Vietnamese comments.

Example:

```python
async def generate_image(self, request):
    """
    Điều phối một yêu cầu tạo ảnh thông qua Google Flow.

    Quy trình:
    1. Kiểm tra Chrome Extension.
    2. Kiểm tra Google Flow.
    3. Gửi prompt.
    4. Theo dõi trạng thái tạo ảnh.
    5. Tải kết quả.
    6. Kiểm tra file.
    7. Trả kết quả cho VisualService.
    """

    # Kiểm tra kết nối trước khi gửi yêu cầu.
    await self.ensure_connected()

    # Gửi yêu cầu tới Chrome Extension.
    await self.bridge.send(request)
```

Use English for:

```text
Classes
Functions
Variables
Modules
JSON keys
Database fields
```

Use Vietnamese for explanations/comments.

---

# 57. TESTING ARCHITECTURE

Tests must be separated into:

```text
Unit Tests
Integration Tests
Provider Tests
Bridge Tests
Flow Tests
Rendering Tests
```

Important tests:

```text
test_segmentation.py
test_subtitle.py
test_timeline.py
test_flow_protocol.py
test_flow_controller.py
test_image_provider.py
test_render_pipeline.py
```

Flow tests should support a mock Flow environment so ordinary development does not require Google Flow every time.

---

# 58. MOCK FLOW PROVIDER

Create:

```text
MockImageProvider
```

for development.

Example:

```text
Prompt
 ↓
Mock Provider
 ↓
Generated test image
```

This allows:

- UI development
- Grid development
- Timeline development
- Subtitle development
- Rendering development

without repeatedly using Flow.

---

# 59. DEVELOPMENT PHASES

Implementation must follow this order.

## Phase 1

Application shell:

```text
PySide6
Settings
Project management
Logging
Dependency checking
```

## Phase 2

AI:

```text
Topic
Article
Script
SEO metadata
```

## Phase 3

Voice:

```text
Import
ASR
VAD
Segmentation
```

## Phase 4

Visual:

```text
Prompt generation
Character consistency
Image provider interface
Mock provider
```

## Phase 5

Chrome:

```text
Chrome Profile Manager
Chrome Launcher
Local Bridge
Chrome Extension
```

## Phase 6

Flow:

```text
Calibration
FlowController
FlowProvider
Flow Job Queue
Download Manager
Recovery
```

## Phase 7

Editor:

```text
Grid Cards
Image replacement
Prompt editing
Effects
```

## Phase 8

Subtitles:

```text
Word timestamps
Karaoke
Smart line breaking
```

## Phase 9

Timeline:

```text
Voice
Image
Subtitle
Effects
```

## Phase 10

Rendering:

```text
FFmpeg
Preview
Final MP4
```

## Phase 11

Production:

```text
Caching
Recovery
Installer
Testing
Documentation
```

---

# 60. DEVELOPMENT RULE

Never implement the entire application in one uncontrolled step.

After every phase:

```text
Implement
 ↓
Run
 ↓
Test
 ↓
Fix
 ↓
Document
 ↓
Continue
```

Previous functionality must remain operational.

---

# 61. BUILD REQUIREMENT

The final application must be buildable on Windows.

Provide:

```text
run.bat
build_windows.bat
requirements.txt
README.md
```

Use PyInstaller or another reliable Windows packaging system.

The final user experience should be:

```text
Install
 ↓
Launch
 ↓
Configure
 ↓
Create Project
 ↓
Generate Video
```

without requiring the user to understand Python internals.

---

# 62. FINAL ARCHITECTURE

The final architecture should look like:

```text
                         ┌─────────────────────────┐
                         │       PySide6 UI        │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │   Application Services  │
                         └────────────┬────────────┘
                                      │
                 ┌────────────────────┼────────────────────┐
                 │                    │                    │
                 ▼                    ▼                    ▼
           AI Providers        Voice Processing       Video Engine
                 │                    │                    │
                 ▼                    ▼                    ▼
          Script / SEO             ASR/VAD              FFmpeg
                                      │
                                      ▼
                             Semantic Segments
                                      │
                                      ▼
                              Visual Prompt Engine
                                      │
                                      ▼
                              ImageProvider
                                      │
                     ┌────────────────┴────────────────┐
                     │                                 │
                     ▼                                 ▼
                FlowProvider                    Local Providers
                     │
                     ▼
                FlowController
                     │
                     ▼
               Local WebSocket
                  Bridge
                     │
                     ▼
              Chrome Extension
                     │
                     ▼
               Real Chrome
                     │
                     ▼
              Google Flow
                     │
                     ▼
              Generated Image
                     │
                     ▼
              Project Storage
                     │
                     ▼
                Grid Editor
                     │
                     ▼
                 Timeline
                     │
                     ▼
              Karaoke Subtitle
                     │
                     ▼
                 FFmpeg
                     │
                     ▼
                Final MP4
```

---

# 63. CRITICAL ENGINEERING PRINCIPLES

The implementation must follow these rules:

```text
1. Keep UI separate from business logic.

2. Keep Google Flow-specific logic inside FlowController.

3. Keep browser automation inside Chrome Extension.

4. Keep Python ↔ Extension communication inside Local Bridge.

5. Keep image generation behind ImageProvider.

6. Keep AI generation behind AIProvider.

7. Keep video rendering behind RenderEngine.

8. Keep project data inside ProjectRepository.

9. Never depend on fixed screen coordinates when a better
   element-detection method is available.

10. Never store Google passwords or authentication secrets.

11. Never bypass Google authentication or platform restrictions.

12. Every long-running operation must be asynchronous/background.

13. Every important operation must be recoverable.

14. Every project must be autosaved.

15. Every expensive operation should be cacheable.

16. Important code sections must have Vietnamese comments.

17. Code identifiers must remain in English.

18. The application must work without Google Flow by using
    another ImageProvider.

19. Do not create fake implementations for production features.

20. Test every phase before continuing.
```

---

# 64. ACCEPTANCE CRITERIA

The application is considered functionally complete only when the following workflow works:

```text
1. User creates a project.

2. User enters a topic or article.

3. AI generates a complete script.

4. AI generates 5 titles.

5. AI generates SEO description.

6. AI generates tags and hashtags.

7. User imports a voice recording.

8. Application performs ASR.

9. Application creates meaningful voice segments.

10. Application generates a visual prompt for every segment.

11. User selects Google Flow as ImageProvider.

12. Chrome profile is selected.

13. Chrome opens the real Google Flow website.

14. Chrome Extension connects to the Local Bridge.

15. Flow calibration is available.

16. FlowController submits image-generation jobs.

17. Generated images are detected.

18. Images are downloaded automatically.

19. Images are mapped to the correct segments.

20. Images and voice segments appear in the Grid Editor.

21. User can modify image effects.

22. User can regenerate individual images.

23. Karaoke subtitles are generated.

24. Timeline synchronizes voice, image and subtitle.

25. User previews the result.

26. FFmpeg renders the final video.

27. Final MP4 is exported.

28. Project state is saved.

29. Application can reopen the project later.

30. Failed Flow jobs can be retried or resumed.
```

---

# 65. FINAL DEVELOPMENT INSTRUCTION

Start by implementing **Phase 1 only**.

Before writing the Phase 1 code:

1. Read this entire architecture.
2. Create the project directory.
3. Create `ARCHITECTURE.md`.
4. Create the initial module structure.
5. Create the dependency manager.
6. Create the configuration system.
7. Create the logging system.
8. Create the project model.
9. Create the PySide6 main window.
10. Create the Settings page.
11. Create the project creation/opening system.
12. Run the application.
13. Verify that it starts correctly.
14. Fix all errors.
15. Only after Phase 1 is stable, proceed to Phase 2.

Do not skip architecture.

Do not merge all modules into one file.

Do not create fake buttons that pretend to perform operations.

Do not implement Google Flow directly inside the UI.

Keep `FlowController`, `FlowProvider`, `Chrome Extension`, and `Local Bridge` as independent components.

The final objective is a reliable, maintainable, extensible Windows desktop application capable of transforming:

```text
TOPIC / ARTICLE
      ↓
AI SCRIPT
      ↓
VOICE
      ↓
SEMANTIC SEGMENTS
      ↓
VISUAL PROMPTS
      ↓
FLOW CONTROLLER
      ↓
CHROME EXTENSION
      ↓
REAL GOOGLE FLOW
      ↓
IMAGES
      ↓
GRID EDITOR
      ↓
EFFECTS
      ↓
KARAOKE SUBTITLES
      ↓
TIMELINE
      ↓
FFMPEG
      ↓
FINAL VIDEO
```

with all important code clearly commented in Vietnamese and all technical identifiers written in English.