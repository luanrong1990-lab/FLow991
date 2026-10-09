# VQPVEO3PRO Architecture Document

## 1. System Architecture
The application is a PySide6-based Windows desktop application designed to operate completely locally without a central backend server. It orchestrates a complete script-to-video pipeline by coordinating multiple specialized subsystems: AI text generation, local audio processing (ASR), Chrome-based image generation (via Google Flow), and FFmpeg-based video rendering.

## 2. Module Responsibilities
- **`app/main.py`**: Application entry point, initializes database, threading pools, and the main PySide6 event loop.
- **`config/`**: Manages environment variables, API keys, and user settings securely.
- **`ui/`**: PySide6 user interface components (Main Window, Grid Editor, Timeline, Settings).
- **`ai/`**: Abstracted AI providers (Gemini, OpenAI, OpenRouter) for script generation and visual prompt translation.
- **`audio/`**: Local audio processing using `faster-whisper`, voice activity detection (VAD), and semantic segmentation.
- **`visual/`**: Prompts generation and integration with image generation providers.
- **`chrome/`**: Chrome profile management, browser automation, and local bridge to the Chrome Extension.
- **`video/`**: Timeline engine, image effects (Ken Burns, Pan/Zoom), karaoke subtitle generation, and FFmpeg rendering pipeline.
- **`project/`**: State management, JSON-based project saving, and automatic recovery.
- **`utils/`**: Shared utilities (logging, FFmpeg detection, dependency management).

## 3. Data Flow
1. **Input**: User provides Topic/Article text/URL.
2. **AI Text**: `ai/` module generates the script, SEO metadata, and translates the script into visual prompts.
3. **Audio**: User provides a Voice file. `audio/` module runs ASR and splits the audio into meaningful `VoiceSegments`.
4. **Visual Generation**: `visual/` and `chrome/` modules push visual prompts to Google Flow via the Chrome Extension and download the generated images.
5. **Editing**: User interacts with the `ui/` Grid Card interface to adjust images, text, and effects.
6. **Rendering**: `video/` module compiles timelines and orchestrates FFmpeg to render the final MP4.

## 4. AI Provider Architecture
Abstract `AIProvider` base class with specific implementations (`GeminiProvider`, `OpenAIProvider`). The UI will allow users to select their preferred provider, model, and input API keys, which are stored securely. 

## 5. Chrome Extension Architecture
A Manifest V3 extension responsible for injecting a `flow_controller.js` content script into `flow.google.com`. It handles DOM manipulation and element observation. A background service worker maintains the connection to the Desktop App. A Calibration Overlay guides the user if Flow UI changes occur.

## 6. Local Bridge Protocol
Communication between PySide6 (Local Python Server) and Chrome Extension via WebSockets on localhost. 
Message format is JSON-based, e.g., `{"type": "GENERATE_IMAGE", "prompt": "..."}`. State transitions include `WAITING`, `IMAGE_READY`, `DOWNLOAD_COMPLETE`.

## 7. Google Flow Integration Strategy
Hybrid DOM-based approach. The extension prioritizes stable semantic selectors and accessibility attributes rather than raw screen coordinates. Coordinate-based interaction is a fallback. The desktop application manages a queue and assigns tasks to available Chrome profiles to respect rate limits.

## 8. Project Structure
Projects are stored on disk as folders:
```
Projects/
└── [Project Name]/
    ├── project.json
    ├── source/
    ├── voice/
    ├── segments/
    ├── images/
    └── output/
```

## 9. Database Structure
Local SQLite database (`project.db`) tracks metadata that spans across projects or tracks application-wide settings, chrome profiles, and job queues to ensure continuity across restarts.

## 10. Threading Strategy
PySide6 UI thread remains non-blocking. Heavy tasks (ASR, FFmpeg, Image Downloading, AI API calls) are offloaded to `QThread` or `QRunnable` workers within a `QThreadPool`. Progress signals are emitted back to the UI thread to update progress bars.

## 11. Error Recovery Strategy
If a process (e.g., Chrome, FFmpeg, or Network) crashes, the job is marked as `FAILED` in the queue and the state is preserved. Upon restart, the application resumes from the last successfully completed segment rather than starting over.

## 12. Rendering Pipeline
Images, Voice Segments, Subtitles (SRT/ASS), and Effects (JSON parameter sets) are compiled into a timeline. The `video_renderer.py` constructs complex FFmpeg filtergraphs (e.g., `zoompan`, `drawtext`) to render the final output efficiently, adding transitions and optional background music ducking.
