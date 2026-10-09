# Specification Report: R2 (Chrome Extension & DOM Executor) & R3 (Chrome Native Messaging Host)

**Investigator**: teamwork_preview_spec_miner_survey_2 (Specification Investigator)  
**Date**: 2026-09-08  
**Scope**: R2 (Chrome Extension with Guided Mapping & Execution Engine) and R3 (Chrome Native Messaging Host)  
**Specification Sources**:
- `ORIGINAL_REQUEST.md` (lines 29–41, 70–74)
- Google Chrome Extension Manifest V3 Specifications & Chrome Native Messaging Protocol Standard
- Existing repository implementations under `extension/`, `flow-extension/`, `automation/`, `workers/`, `app.py`, `server.py`

---

## Executive Summary

A rigorous audit of the workspace reveals an **architectural divergence** between what is implemented in the repository and what is specified in `ORIGINAL_REQUEST.md`:
1. **Transport Mechanism Divergence**:
   - **Specified (R3)**: Chrome Native Messaging via 32-bit length-prefixed JSON frames over `stdin`/`stdout` connecting Python host and Chrome Extension (`chrome.runtime.connectNative("com.vqp.flow_bridge")`).
   - **Current Implementation**: A custom WebSocket bridge (`ws://127.0.0.1:5000/ws/extension`) managed by NiceGUI/FastAPI in `app.py` and connected via browser `WebSocket` in `flow-extension/websocket.js` and `extension/background.js`.
2. **Native Messaging Host & Registry**:
   - Completely absent. No Native Messaging Host script, no manifest file (`com.vqp.flow_bridge.json`), and no Windows Registry installer script (`HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`) exist in the repository.
3. **Manifest Permissions**:
   - `extension/manifest.json` specifies permissions `["tabs", "activeTab", "storage"]` (missing `nativeMessaging` and `downloads`).
   - `flow-extension/manifest.json` specifies permissions `["tabs", "activeTab", "storage", "downloads"]` (missing `nativeMessaging`).
4. **Guided Mapping & `flow_adapter_config.json`**:
   - `flow-extension/content.js` contains a rudimentary "self-healing" event listener that saves three CSS selectors to `chrome.storage.local` (`learnedPromptSelector`, `learnedGenerateSelector`, `learnedDownloadSelector`).
   - There is **no visual overlay with an interactive pointer/highlighter**, **no step-by-step guided mapping wizard**, **no XPath computation**, and **no serialization to `flow_adapter_config.json`**.
5. **DOM Executor**:
   - `flow-extension/flow.js` implements hardcoded keyword matching (e.g. searching for text `'dự án mới'`, `'tạo'`, `'create'`) rather than loading and executing from `flow_adapter_config.json`.

---

## Detailed Answers to Core Survey Questions

### 1. Does manifest.json meet Manifest V3 standards with correct permissions (nativeMessaging, storage, downloads)?

**Finding**: **PARTIAL / NON-COMPLIANT**

Two distinct extension folders exist:
- **Folder `extension/`**:
  - `manifest_version`: 3.
  - Permissions: `["tabs", "activeTab", "storage"]`.
  - **Missing**: `nativeMessaging` and `downloads`.
  - Service worker declared at `background.service_worker = "background.js"`.
  - Matches: `*://*.google.com/*`, `https://*.google.com/*`, `http://localhost/*`, `http://127.0.0.1/*`.
- **Folder `flow-extension/`**:
  - `manifest_version`: 3.
  - Permissions: `["tabs", "activeTab", "storage", "downloads"]`.
  - **Missing**: `nativeMessaging`.
  - Service worker declared at `background.service_worker = "background.js"`.
  - Matches: `https://labs.google/fx/*`.

**Required Manifest V3 Permissions**:
To satisfy R2 and R3 acceptance criteria (`ORIGINAL_REQUEST.md` line 70), the extension manifest must be:
```json
{
  "manifest_version": 3,
  "name": "VQPVEO3PRO Flow Bridge",
  "version": "2.0.0",
  "description": "Chrome Extension Flow Adapter & Execution Engine for Google Flow automation",
  "permissions": [
    "nativeMessaging",
    "storage",
    "downloads",
    "tabs",
    "activeTab"
  ],
  "host_permissions": [
    "https://labs.google/fx/*",
    "https://*.google.com/*"
  ],
  "background": {
    "service_worker": "background.js",
    "type": "module"
  },
  "content_scripts": [
    {
      "matches": [
        "https://labs.google/fx/*"
      ],
      "js": [
        "guided_mapping.js",
        "dom_executor.js",
        "content.js"
      ],
      "css": [
        "overlay.css"
      ],
      "run_at": "document_end"
    }
  ]
}
```

---

### 2. Is the 32-bit length-prefixed JSON protocol implemented correctly on both Python host and Chrome extension sides?

**Finding**: **NOT IMPLEMENTED (0% Compliance)**

- **Python Host**:
  - There is no script in the project that implements the Chrome Native Messaging framing protocol.
  - The Native Messaging specification requires:
    1. Reading 4 bytes from `sys.stdin.buffer` formatted as an unsigned 32-bit integer in native/little-endian byte order (`struct.unpack('@I', length_bytes)`).
    2. Reading exactly `length` bytes of UTF-8 JSON payload.
    3. Writing response as 4-byte prefix (`struct.pack('@I', len(payload))`) followed by the UTF-8 payload to `sys.stdout.buffer`, followed by an immediate `sys.stdout.buffer.flush()`.
    4. Guarding against Windows standard IO text mode carriage return translation (`\r\n` vs `\n`) by operating strictly on binary buffers (`sys.stdin.buffer`, `sys.stdout.buffer`), or executing python with `-u` (unbuffered).
  - Instead, the current Python code uses a WebSocket endpoint inside `app.py`:
    ```python
    @app.websocket('/ws/extension')
    async def websocket_endpoint(websocket: WebSocket): ...
    ```
- **Chrome Extension Side**:
  - `extension/background.js` and `flow-extension/websocket.js` create a WebSocket connection via `new WebSocket("ws://127.0.0.1:5000/ws/extension")`.
  - Neither background script invokes `chrome.runtime.connectNative("com.vqp.flow_bridge")` or `chrome.runtime.sendNativeMessage(...)`.

---

### 3. Does Guided Mapping properly compute unique CSS/XPath selectors and serialize them?

**Finding**: **SEVERELY DEFICIENT / MISSING CRITICAL SPECIFICATION REQUIREMENTS**

- **Current Implementation (`flow-extension/content.js` lines 211–267)**:
  - Only generates CSS selectors via a basic recursive DOM tree walk:
    ```javascript
    function getUniqueSelector(el) {
        if (!el) return null;
        if (el.id) return `#${el.id}`;
        let path = [];
        while (el && el.nodeType === Node.ELEMENT_NODE) {
            let selector = el.nodeName.toLowerCase();
            if (el.className) {
                let classes = Array.from(el.classList).filter(c => !c.includes('active') && !c.includes('focus')).join('.');
                if (classes) selector += `.${classes}`;
            }
            let siblings = Array.from(el.parentNode ? el.parentNode.children : []);
            let index = siblings.indexOf(el);
            if (siblings.length > 1 && index !== -1) {
                selector += `:nth-child(${index + 1})`;
            }
            path.unshift(selector);
            el = el.parentNode;
        }
        return path.join(' > ');
    }
    ```
- **Defects in Current Selector Computation**:
  1. **Dynamic / Mangled Class Names**: Modern Google web applications use hashed or utility classes containing colons, slashes, or dynamic tokens (e.g. `css-12a8b9`, `hover:bg-blue-500`). Concatenating them with dots creates invalid CSS selectors that throw syntax errors when evaluated with `document.querySelector()`.
  2. **No XPath Generation**: No XPath generation exists at all.
  3. **No Interactive Pointer / Highlighter**: There is no visual element inspector, hover highlight box, or crosshair pointer.
  4. **No Step-by-Step Guided Wizard**: The user is not guided through mapping the 5 mandatory elements:
     - Prompt Box
     - Generate Button
     - Download Link
     - Model Selector
     - Ratio Options
  5. **No `flow_adapter_config.json` Serialization**: Selectors are saved only to `chrome.storage.local` under separate keys (`learnedPromptSelector`, `learnedGenerateSelector`, `learnedDownloadSelector`).

---

### 4. Does Run Mode DOM executor properly read the config and automate Google Flow?

**Finding**: **DOES NOT READ CONFIG / HARDCODED FALLBACKS ONLY**

- **Configuration File Ingestion**:
  - `flow-extension/flow.js` does NOT read any configuration file (`flow_adapter_config.json`).
  - It checks `chrome.storage.local` for the 3 individual learned selector keys, and if missing, executes a series of hardcoded heuristic DOM queries (`div[contenteditable="true"]`, `button[type="submit"]`, text content matching keywords like `'dự án mới'`, `'tạo'`, `'chạy'`).
- **DOM Automation Capabilities**:
  - **Clearing Text**: Implemented via `document.execCommand('selectAll')` and `document.execCommand('delete')` for `contenteditable`, or `.value = ''` for inputs.
  - **Typing Prompt**: Sets `.innerText` or `.value` and dispatches `input`, `change`, and `keyup` events.
  - **Model / Ratio Selection**: Iterates through buttons looking for `'Nano Banana'`, `'16:9'`, `'1:1'`. It has no knowledge of Veo 3.1 Lite or other models/ratios specified in R1/R3.
  - **Completion Detection**: Polls for a download link/button every 1 second up to 60 seconds. Simulates a fake random progress percentage (`Math.random() * 15 + 5`).
  - **Downloading Output**: Clicks the download button; download completion is detected in `download.js` via `chrome.downloads.onChanged`.

---

### 5. What is the status of the Windows Registry installation script (`HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`)?

**Finding**: **COMPLETELY MISSING (0% Implemented)**

- No registration script exists in Python, PowerShell, Batch, or `.reg` format.
- No Native Messaging Host manifest file (`com.vqp.flow_bridge.json`) exists in the repository.
- **Specification for Registry Entry**:
  - **Registry Path**: `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`
  - **Registry Value Name**: `(Default)` (type `REG_SZ`)
  - **Value Content**: Full absolute path to `com.vqp.flow_bridge.json` (e.g. `d:\New folder (5)\native_host\com.vqp.flow_bridge.json`).
- **Specification for Host Manifest (`com.vqp.flow_bridge.json`)**:
  ```json
  {
    "name": "com.vqp.flow_bridge",
    "description": "VQPVEO3PRO Native Messaging Host Bridge",
    "path": "host_launcher.bat",
    "type": "stdio",
    "allowed_origins": [
      "chrome-extension://<EXTENSION_ID>/"
    ]
  }
  ```
  *(Note on Windows: `path` must be an absolute path or relative to the manifest file directory. If using Python on Windows, a `.bat` wrapper or compiled `.exe` is required because Chrome calls `CreateProcessW` without a shell).*

---

### 6. Enumerate all exact commands and response schemas

Below are the exact message schemas required by the R2/R3 Native Messaging specification.

#### A. Host Commands (Sent from Python Host -> Chrome Extension via Native Messaging Port)

##### 1. `generate_image`
Sent by the scheduler / desktop orchestrator to generate an image using Google Flow (Nano Banana 2).
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GenerateImageCommand",
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "const": "generate_image"
    },
    "job_id": {
      "type": "string",
      "description": "Unique identifier for the job (e.g. IMG-A1B2C3D4)"
    },
    "prompt": {
      "type": "string",
      "description": "Text prompt for the image generation"
    },
    "model": {
      "type": "string",
      "enum": ["Nano Banana 2", "Nano Banana Pro", "Nano Banana 2 Lite"],
      "default": "Nano Banana 2"
    },
    "ratio": {
      "type": "string",
      "enum": ["16:9", "1:1", "4:3", "3:4", "9:16"],
      "default": "16:9"
    },
    "quantity": {
      "type": "string",
      "enum": ["x1", "x2", "x3", "x4"],
      "default": "x1"
    },
    "delay": {
      "type": "integer",
      "minimum": 0,
      "default": 10,
      "description": "Pre-generation safety delay in seconds"
    },
    "project_id": {
      "type": "string",
      "description": "Optional Google Flow project UUID"
    }
  },
  "required": ["command", "job_id", "prompt"]
}
```

##### 2. `generate_video`
Sent by the scheduler / desktop orchestrator to generate an 8s 720p 16:9 video using Veo 3.1 Lite.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "GenerateVideoCommand",
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "const": "generate_video"
    },
    "job_id": {
      "type": "string",
      "description": "Unique identifier for the job (e.g. VID-E5F6G7H8)"
    },
    "prompt": {
      "type": "string",
      "description": "Motion and scene prompt for Veo 3.1 Lite"
    },
    "model": {
      "type": "string",
      "enum": ["Veo 3.1 Lite", "Veo 3.1 Pro", "Veo Fast"],
      "default": "Veo 3.1 Lite"
    },
    "duration": {
      "type": "integer",
      "enum": [5, 8],
      "default": 8,
      "description": "Duration in seconds (Veo 3.1 Lite standard is 8s)"
    },
    "ratio": {
      "type": "string",
      "enum": ["16:9", "9:16", "1:1"],
      "default": "16:9"
    },
    "resolution": {
      "type": "string",
      "enum": ["720p", "1080p"],
      "default": "720p"
    },
    "first_frame_image_path": {
      "type": "string",
      "description": "Absolute path or URI of completed reference image for image-to-video generation"
    },
    "delay": {
      "type": "integer",
      "default": 10
    },
    "project_id": {
      "type": "string"
    }
  },
  "required": ["command", "job_id", "prompt"]
}
```

##### 3. `enter_setup_mode`
Triggered from the PySide6 UI to activate Guided Mapping on the active Google Flow tab.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "EnterSetupModeCommand",
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "const": "enter_setup_mode"
    },
    "target_step": {
      "type": "string",
      "enum": ["ALL", "prompt_box", "generate_button", "download_link", "model_selector", "ratio_selector"],
      "default": "ALL"
    },
    "existing_config": {
      "type": "object",
      "description": "Current flow_adapter_config.json contents to allow selective remapping"
    }
  },
  "required": ["command"]
}
```

##### 4. `query_status`
Polls or verifies the extension's execution status, current DOM readiness, and active job.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "QueryStatusCommand",
  "type": "object",
  "properties": {
    "command": {
      "type": "string",
      "const": "query_status"
    },
    "job_id": {
      "type": "string"
    }
  },
  "required": ["command"]
}
```

---

#### B. Extension Responses (Sent from Chrome Extension -> Python Host via Native Messaging Port)

##### 1. `status_update`
Emitted during automation to inform Python of state changes and progress percentage.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "StatusUpdateResponse",
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "const": "status_update"
    },
    "job_id": {
      "type": "string"
    },
    "state": {
      "type": "string",
      "enum": [
        "INITIALIZING",
        "NAVIGATING",
        "APPLYING_SETTINGS",
        "INPUTTING_PROMPT",
        "DELAYING",
        "TRIGGERING_GENERATE",
        "GENERATING",
        "DOWNLOADING",
        "SETUP_MODE_ACTIVE",
        "IDLE"
      ]
    },
    "progress": {
      "type": "number",
      "minimum": 0,
      "maximum": 100
    },
    "message": {
      "type": "string"
    },
    "timestamp": {
      "type": "string",
      "format": "date-time"
    }
  },
  "required": ["type", "job_id", "state", "progress"]
}
```

##### 2. `success`
Emitted when a generation job completes and the downloaded file is verified on disk.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "SuccessResponse",
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "const": "success"
    },
    "job_id": {
      "type": "string"
    },
    "command": {
      "type": "string",
      "enum": ["generate_image", "generate_video", "enter_setup_mode"]
    },
    "downloaded_file_path": {
      "type": "string",
      "description": "File name or absolute path of the downloaded artifact"
    },
    "duration_seconds": {
      "type": "number"
    },
    "config_data": {
      "type": "object",
      "description": "Serialized flow_adapter_config.json object if command was enter_setup_mode"
    }
  },
  "required": ["type", "job_id", "command"]
}
```

##### 3. `error`
Emitted whenever an unrecoverable failure or timeout occurs during execution.
```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ErrorResponse",
  "type": "object",
  "properties": {
    "type": {
      "type": "string",
      "const": "error"
    },
    "job_id": {
      "type": "string"
    },
    "command": {
      "type": "string"
    },
    "error_code": {
      "type": "string",
      "enum": [
        "PROMPT_ELEMENT_NOT_FOUND",
        "GENERATE_BUTTON_NOT_FOUND",
        "DOWNLOAD_TIMEOUT",
        "RATE_LIMITED",
        "SESSION_EXPIRED",
        "INVALID_CONFIG",
        "TAB_CRASHED",
        "SETUP_CANCELLED"
      ]
    },
    "error_message": {
      "type": "string"
    },
    "stack": {
      "type": "string"
    },
    "screenshot_base64": {
      "type": "string",
      "description": "Optional debug screenshot captured at time of error"
    }
  },
  "required": ["type", "error_code", "error_message"]
}
```

---

## `flow_adapter_config.json` Specification

The specification requires that Guided Mapping automatically extracts robust CSS and XPath selectors and serializes them into `flow_adapter_config.json`. The required canonical schema is:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "FlowAdapterConfig",
  "type": "object",
  "properties": {
    "version": {
      "type": "string",
      "default": "1.0.0"
    },
    "updated_at": {
      "type": "string",
      "format": "date-time"
    },
    "domain": {
      "type": "string",
      "default": "labs.google"
    },
    "elements": {
      "type": "object",
      "properties": {
        "prompt_box": {
          "type": "object",
          "properties": {
            "css": { "type": "string" },
            "xpath": { "type": "string" },
            "tag": { "type": "string" },
            "strategy": { "type": "string", "enum": ["contenteditable", "textarea", "input"] }
          },
          "required": ["css", "xpath"]
        },
        "generate_button": {
          "type": "object",
          "properties": {
            "css": { "type": "string" },
            "xpath": { "type": "string" }
          },
          "required": ["css", "xpath"]
        },
        "download_link": {
          "type": "object",
          "properties": {
            "css": { "type": "string" },
            "xpath": { "type": "string" }
          },
          "required": ["css", "xpath"]
        },
        "model_selector": {
          "type": "object",
          "properties": {
            "dropdown_trigger": {
              "type": "object",
              "properties": {
                "css": { "type": "string" },
                "xpath": { "type": "string" }
              },
              "required": ["css", "xpath"]
            },
            "options": {
              "type": "object",
              "additionalProperties": {
                "type": "object",
                "properties": {
                  "css": { "type": "string" },
                  "xpath": { "type": "string" }
                },
                "required": ["css", "xpath"]
              }
            }
          },
          "required": ["dropdown_trigger"]
        },
        "ratio_selector": {
          "type": "object",
          "properties": {
            "dropdown_trigger": {
              "type": "object",
              "properties": {
                "css": { "type": "string" },
                "xpath": { "type": "string" }
              }
            },
            "options": {
              "type": "object",
              "additionalProperties": {
                "type": "object",
                "properties": {
                  "css": { "type": "string" },
                  "xpath": { "type": "string" }
                },
                "required": ["css", "xpath"]
              }
            }
          }
        },
        "quantity_selector": {
          "type": "object",
          "properties": {
            "options": {
              "type": "object",
              "additionalProperties": {
                "type": "object",
                "properties": {
                  "css": { "type": "string" },
                  "xpath": { "type": "string" }
                }
              }
            }
          }
        }
      },
      "required": [
        "prompt_box",
        "generate_button",
        "download_link",
        "model_selector",
        "ratio_selector"
      ]
    }
  },
  "required": ["version", "elements"]
}
```

---

## Features Discovered & Specification Inventory

| # | Category | Feature | Description | Inputs | Outputs | Error Behavior | Discovered Via |
|---|----------|---------|-------------|--------|---------|----------------|----------------|
| 1 | R2 Manifest | Extension Manifest MV3 (`extension/`) | Manifest V3 file for legacy bridge extension | `manifest.json` | Chrome MV3 metadata | Missing `nativeMessaging` & `downloads` | `extension/manifest.json` |
| 2 | R2 Manifest | Extension Manifest MV3 (`flow-extension/`) | Manifest V3 file for modular flow bridge | `manifest.json` | Chrome MV3 metadata | Missing `nativeMessaging` | `flow-extension/manifest.json` |
| 3 | R2 Extension | Dynamic Manifest Version Sync | Copies extension to clean public path (`C:\Users\Public\media_ai_flow_extension`) and bumps version timestamp to invalidate Chrome cache | Source folder path | Copied folder path | Falls back to source if copy fails | `automation/browser.py:82-132` |
| 4 | R2 Setup Mode | Self-Healing Selector Listener | Passive DOM event listener on `input` and `click` learning 3 selectors | User interaction events | Keys in `chrome.storage.local` | Fails on hashed/mangled CSS class names | `flow-extension/content.js:210-267` |
| 5 | R2 Setup Mode | Guided Mapping Overlay & Wizard | Interactive pointer, step-by-step element click guidance, CSS/XPath extraction | DOM hover/click | `flow_adapter_config.json` | **UNIMPLEMENTED** | `ORIGINAL_REQUEST.md:30-31` |
| 6 | R2 Run Mode | FlowAdapter DOM Automation Engine | DOM query routines for prompt typing, settings configuration, generation click, and download | Prompt, model, ratio, quantity | DOM state mutation, button clicks | Throws Error if element not found | `flow-extension/flow.js:3-311` |
| 7 | R2 Run Mode | Overlay HUD UI | Dark-themed floating panel showing connection status, account email, project name, current job, and counters | Status messages from background | Rendered floating HUD DOM | Ignores if `#media-ai-flow-overlay` already exists | `flow-extension/overlay.js:3-157` |
| 8 | R2 Run Mode | Download Completion Monitor | Uses `chrome.downloads` API to intercept file download initiation and completion | `chrome.downloads.onCreated`, `onChanged` | Status messages (`downloading`, `done`) | Relies on default filename if stripped | `flow-extension/download.js:4-42` |
| 9 | R2 Run Mode | Service Worker Heartbeat | 10s interval pinging background worker to prevent MV3 worker termination | Timer interval | `chrome.runtime.sendMessage({type: "HEARTBEAT"})` | Catches and ignores errors | `flow-extension/content.js:269-272` |
| 10 | R3 Transport | Chrome Native Messaging Host Script | Python script implementing 32-bit length-prefixed JSON stdin/stdout framing | 4-byte prefix + UTF-8 JSON on `stdin` | 4-byte prefix + UTF-8 JSON on `stdout` | **UNIMPLEMENTED** (uses WebSocket instead) | `ORIGINAL_REQUEST.md:34-40` |
| 11 | R3 Transport | Extension Native Messaging Client | Extension service worker connecting to host via `chrome.runtime.connectNative` | `connectNative("com.vqp.flow_bridge")` | Native port messaging | **UNIMPLEMENTED** (uses WebSocket client) | `ORIGINAL_REQUEST.md:37` |
| 12 | R3 Installer | Windows Registry Native Host Installer | Script writing manifest location to `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge` | Manifest file path | Registry DWORD/SZ entry | **UNIMPLEMENTED** | `ORIGINAL_REQUEST.md:40` |
| 13 | R3 Commands | Command: `generate_image` | Dispatches image generation prompt, model, ratio, quantity to Google Flow | `job_id`, `prompt`, `model`, `ratio`, `quantity` | `status_update`, `success`, `error` | Timeout / failure response | `ORIGINAL_REQUEST.md:38-39` |
| 14 | R3 Commands | Command: `generate_video` | Dispatches video generation prompt to Veo 3.1 Lite (8s, 720p, 16:9) | `job_id`, `prompt`, `model`, `duration`, `ratio` | `status_update`, `success`, `error` | Timeout / failure response | `ORIGINAL_REQUEST.md:38-39` |
| 15 | R3 Commands | Command: `enter_setup_mode` | Switches extension to visual guided mapping mode | Setup configuration | Updated `flow_adapter_config.json` | Cancellation error | `ORIGINAL_REQUEST.md:38-39` |
| 16 | R3 Commands | Command: `query_status` | Returns current worker status, queue state, and health | Query parameters | Current status object | Error if worker offline | `ORIGINAL_REQUEST.md:38-39` |
| 17 | Current IPC | WebSocket Relay Server | NiceGUI/FastAPI endpoint at `/ws/extension` handling worker registration and job progress | JSON messages over WebSocket | Status updates to SQLite / UI | Worker disconnect de-registers worker | `app.py:15-97` |
| 18 | Current IPC | WebSocket Client | Extension background service worker connecting to `ws://127.0.0.1:5000/ws/extension` | WebSocket connection | Message relay to active tabs | Retries connection every 3s on close | `flow-extension/websocket.js:23-81` |

---

## Edge Cases & Protocol Nuances

| # | Feature | Input / Condition | Observed / Documented Behavior |
|---|---------|-------------------|--------------------------------|
| 1 | Native Messaging Binary Framing | Windows newline translation (`\r\n`) | If stdin/stdout is opened in text mode on Windows, bytes `0x0A` are converted to `0x0D 0x0A`, corrupting the 4-byte length header or JSON byte stream. Must use `sys.stdin.buffer` and `sys.stdout.buffer`. |
| 2 | Native Messaging Protocol | Message size > 1024 * 1024 bytes (1 MB) | Chrome Native Messaging protocol strictly enforces a 1 MB limit. Messages exceeding this cause Chrome to abruptly kill the host process and fire `port.onDisconnect`. |
| 3 | Native Messaging Host Launch | Windows `.py` vs `.bat`/`.exe` | On Windows, Chrome invokes `CreateProcessW` directly on the `path` field without a command shell. Passing a `.py` file fails unless registered with an executable wrapper (`.bat` / `.cmd` / `.exe`). |
| 4 | Chrome Extension Unpacked ID | Reloading unpacked extension | Unpacked extensions change their extension ID whenever the directory changes unless a fixed `"key"` is provided in `manifest.json`. The Native Messaging host manifest `allowed_origins` must match this exact ID. |
| 5 | Chrome MV3 Service Worker Lifespan | Idle service worker terminates after 30s | In Manifest V3, background service workers terminate if idle for 30s. A persistent Native Messaging port (`chrome.runtime.connectNative`) keeps the service worker alive during an active job. |
| 6 | Selector Extraction | Classes containing colons (Tailwind `hover:bg-amber-500`) | Standard CSS `querySelector` fails with syntax error on unescaped colons or dynamic component hashes. Selector generator must escape special characters or prefer semantic attributes (`data-testid`, `role`, `placeholder`). |
| 7 | Prompt Injection | Rich text `contenteditable` `<div>` vs `<textarea>` | React/Lexical editor in Google Flow does not trigger state change on simple `.innerText = ...`. It requires dispatching `beforeinput`, `input`, and keyboard events or using `document.execCommand('insertText')`. |
| 8 | Download Detection | File download dialog prompt or rename conflict | If Chrome displays a "Save As" dialog or renames duplicates (e.g. `scene (1).png`), `download.js` filename extraction must handle the delta correctly and verify the file exists on disk. |
| 9 | Windows Registry Permissions | HKCU vs HKLM | Writing to `HKLM` requires elevated administrator privileges, which fails in user-space execution. Writing to `HKCU\Software\Google\Chrome\NativeMessagingHosts` succeeds without UAC elevation. |
| 10 | Path with Spaces in Extension Load | `--load-extension="d:\New folder (5)\flow-extension"` | Spaces in folder names can cause Playwright/Chrome CLI argument parser bugs. The workaround discovered in `automation/browser.py` syncs the extension to `C:\Users\Public\media_ai_flow_extension`. |
