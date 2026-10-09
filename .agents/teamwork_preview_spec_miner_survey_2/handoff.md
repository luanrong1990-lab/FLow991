# Handoff Report: Specification Mining Survey for R2 & R3

**Agent**: teamwork_preview_spec_miner_survey_2 (Specification Investigator)  
**Parent Conversation ID**: c24ef2c5-e625-4967-8e69-0738cb710185  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_spec_miner_survey_2`  
**Handoff Type**: Hard (Investigation complete)  

---

## 1. Observation

Direct observations from inspecting the codebase and specification:

1. **Manifest Permissions**:
   - In `d:/New folder (5)/extension/manifest.json` (lines 6–10):
     ```json
     "permissions": [
       "tabs",
       "activeTab",
       "storage"
     ]
     ```
     `nativeMessaging` and `downloads` permissions are missing.
   - In `d:/New folder (5)/flow-extension/manifest.json` (lines 6–11):
     ```json
     "permissions": [
       "tabs",
       "activeTab",
       "storage",
       "downloads"
     ]
     ```
     `nativeMessaging` permission is missing.

2. **IPC Transport Implementation**:
   - In `d:/New folder (5)/flow-extension/websocket.js` (lines 3–4, 23–26):
     ```javascript
     let socket = null;
     const WS_URL = "ws://127.0.0.1:5000/ws/extension";
     ...
     function connectSocket() {
         console.log("WebSocket Client: Connecting to Desktop App...");
         socket = new WebSocket(WS_URL);
     ```
   - In `d:/New folder (5)/app.py` (lines 15–18):
     ```python
     @app.websocket('/ws/extension')
     async def websocket_endpoint(websocket: WebSocket):
         await websocket.accept()
         print("Backend: Chrome Extension Bridge Connected via WebSocket.")
     ```
   - Across the entire workspace, zero occurrences of `sys.stdin.buffer.read`, `sys.stdout.buffer.write`, or `struct.pack`/`unpack` exist for native messaging binary framing.
   - Zero occurrences of `chrome.runtime.connectNative` exist within `extension/` or `flow-extension/`.

3. **Guided Mapping & Selector Extraction**:
   - In `d:/New folder (5)/flow-extension/content.js` (lines 211–267):
     The extension attaches an `input` event listener and a `click` event listener that saves three selectors to `chrome.storage.local`:
     - `learnedPromptSelector`
     - `learnedGenerateSelector`
     - `learnedDownloadSelector`
   - No interactive pointer, highlighter box, or step-by-step UI wizard exists.
   - No XPath extraction exists (only CSS path with `:nth-child`).
   - No serialization to `flow_adapter_config.json` exists anywhere in the repository.

4. **Run Mode DOM Executor**:
   - In `d:/New folder (5)/flow-extension/flow.js` (lines 17–39, 212–240, 263–274):
     Elements are located via fallback heuristic text matching (`t === 'dự án mới'`, `keywords = ['generate', 'run', 'create', 'tạo', 'submit', 'send', 'gửi', 'chạy']`).
     `flow_adapter_config.json` is never read or loaded.

5. **Windows Registry Installer**:
   - Searching for `NativeMessagingHosts`, `flow_bridge`, or registry installer scripts across the workspace returns zero installer scripts (`.bat`, `.ps1`, `.py`, `.reg`).
   - The key `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge` is not registered and no script exists to register it.

6. **Command and Response Schemas**:
   - `ORIGINAL_REQUEST.md` (lines 38–39) specifies commands: `generate_image`, `generate_video`, `enter_setup_mode`, `query_status`, and responses: `status_update`, `success`, `error`.
   - Current implementation (`flow-extension/websocket.js` lines 44–61 and `workers/browser_worker.py` lines 201–212) uses `action: "generate"` with ad-hoc payloads.

---

## 2. Logic Chain

1. **Premise 1 (Spec Requirements)**:
   `ORIGINAL_REQUEST.md` dictates that R2 must provide an interactive Guided Mapping overlay serializing selectors to `flow_adapter_config.json`, a Run Mode DOM executor reading that config, and R3 must provide a bidirectional Chrome Native Messaging host communicating via 32-bit length-prefixed JSON with an automated Windows Registry installer.
2. **Premise 2 (Observed Workspace State)**:
   Observations 1–6 show that the repository currently contains a prototype based on NiceGUI + WebSocket (`ws://127.0.0.1:5000/ws/extension`) with hardcoded Vietnamese/English keyword matching, partial `chrome.storage.local` caching, and zero Native Messaging framing, scripts, manifests, or registry keys.
3. **Inference 1 (Protocol Mismatch)**:
   Because Chrome Native Messaging requires stdin/stdout binary framing and `connectNative`, and the current code uses browser WebSockets to a local web server, the current IPC mechanism does not meet R3 requirements and will fail acceptance criteria (line 71: *"Native Messaging Host script correctly decodes incoming length-prefixed JSON and encodes outgoing responses"*).
4. **Inference 2 (DOM Automation Deficiencies)**:
   Because the DOM executor relies on hardcoded string heuristics and lacks XPath fallback and configuration loading, any change in Google Flow's DOM will break automation. The absence of an interactive pointer/highlighter prevents non-technical users from remapping elements when Google updates Flow's UI.
5. **Deduction (Implementation Roadmap)**:
   To satisfy R2 and R3 acceptance criteria, the system requires:
   - A dedicated Python Native Messaging Host script (`host.py` / `flow_bridge.py`) with binary 32-bit length-prefix framing.
   - A `.bat` launcher and host manifest `com.vqp.flow_bridge.json`.
   - A Windows Registry installer script targeting `HKCU\Software\Google\Chrome\NativeMessagingHosts\com.vqp.flow_bridge`.
   - Updating extension `manifest.json` with `nativeMessaging` permission.
   - Refactoring `background.js` to connect via `chrome.runtime.connectNative("com.vqp.flow_bridge")`.
   - Implementing the Guided Mapping visual overlay and selector extractor with XPath + CSS calculation, serializing to `flow_adapter_config.json`.
   - Refactoring `flow.js` / DOM executor to load selectors from `flow_adapter_config.json`.

---

## 3. Caveats

1. **Desktop GUI Alignment**:
   `ORIGINAL_REQUEST.md` specifies PySide6 Desktop GUI (R1), whereas the current workspace contains a NiceGUI/FastAPI web interface (`app.py`). This survey focused strictly on R2 and R3; the relationship between the desktop GUI and the native host will depend on whether the orchestrator replaces or wraps NiceGUI with PySide6.
2. **Dynamic Unpacked Extension IDs**:
   Chrome assigns an extension ID based on the absolute file path when loaded unpacked. In multi-account Playwright execution, if the extension is loaded from a clean copy path (e.g. `C:\Users\Public\media_ai_flow_extension`), the extension ID will be consistent as long as the path does not change. To ensure 100% deterministic Native Messaging origin authorization, `manifest.json` should specify a fixed `"key"` field.

---

## 4. Conclusion

- **R2 (Extension & DOM Engine)**: Currently has a functional WebSocket prototype with rudimentary heuristic selectors, but **fails R2 specifications** because it lacks Guided Mapping visual overlay, XPath generation, and `flow_adapter_config.json` serialization and consumption.
- **R3 (Native Messaging Host)**: Currently **0% implemented**. No host script, framing protocol, manifest, or Windows Registry installer exists.
- Complete specifications, protocol schemas for all 4 commands and 3 responses, and the canonical `flow_adapter_config.json` schema have been thoroughly researched, documented, and published in `d:/New folder (5)/.agents/teamwork_preview_spec_miner_survey_2/spec_report.md`.

---

## 5. Verification Method

To independently verify these findings:

1. **Verify Manifest Permissions**:
   Inspect `d:/New folder (5)/flow-extension/manifest.json` lines 6–11. Confirm that `"nativeMessaging"` is absent from `"permissions"`.
2. **Verify Native Messaging Host Absence**:
   Search project root for any file matching `*bridge*.json`, `*native*`, or containing `connectNative`:
   ```powershell
   Select-String -Path "d:\New folder (5)\*.py", "d:\New folder (5)\flow-extension\*.js" -Pattern "connectNative"
   ```
   Confirm zero matches outside `ORIGINAL_REQUEST.md`.
3. **Verify WebSocket Usage**:
   Inspect `d:/New folder (5)/flow-extension/websocket.js` line 4 and `d:/New folder (5)/app.py` line 15. Confirm reliance on `ws://127.0.0.1:5000/ws/extension`.
4. **Verify Selector Extraction**:
   Inspect `d:/New folder (5)/flow-extension/content.js` lines 211–267. Confirm absence of XPath computation and absence of `flow_adapter_config.json`.
5. **Review Detailed Specification Report**:
   Inspect `d:/New folder (5)/.agents/teamwork_preview_spec_miner_survey_2/spec_report.md` for the complete schema definitions and feature inventory.
