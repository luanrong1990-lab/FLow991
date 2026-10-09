# Milestone M1 (Iteration 2) Handoff Report: End-to-End Prompt Parsing Regex Remediation

**Agent**: `teamwork_preview_explorer_m1_it2_3`  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_it2_3`  
**Project Root**: `d:/New folder (5)`  
**Milestone**: M1 (Iteration 2) - Prompt Parsing Regex Remediation  
**Handoff Type**: Hard  

---

## 1. Observation

Direct code observations from investigation:

1. **Prompt Prefix Regex (`database/models.py`, lines 274–277)**:
   ```python
   PROMPT_PREFIX_REGEX = re.compile(
       r'^(?:\[\s*(?:scene\s*\d+|shot\s*\d+|\d+)\s*\]\s*[-:]?\s*|(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*)',
       re.IGNORECASE
   )
   ```
   - In Branch 1: `(?:scene\s*\d+|shot\s*\d+|\d+)` requires pure digits after `scene` or `shot`.
     - `"[Shot #42] - Futuristic drone"`: The `#` fails `\d+`, preventing the match. Result: unstripped.
     - `"[Scene #1]: Castle"`: Fails on `#`.
   - In Branch 2: `(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*`:
     - `"Scene #99: Cyberpunk street"`: Fails because `#` is not in `\d`.
     - `"1... Deep sea jellyfish"`: The delimiter character class `[:.\-\)\]]` is not followed by `+`. It consumes only the first dot `.` and zero whitespace characters, leaving `".. Deep sea jellyfish"`.
     - Parentheses prefixes such as `"(1) "` or `"(Scene 1) "` are entirely unhandled by both branches.

2. **Comment Line Regex (`database/models.py`, lines 279–281 & 306–307)**:
   ```python
   COMMENT_LINE_REGEX = re.compile(
       r'^(?:#|//|/\*|---|===|\*\*)'
   )
   ...
   if COMMENT_LINE_REGEX.match(cleaned):
       continue
   ```
   - Anchor `^#` matches any line starting with `#`.
   - For storyboard inputs numbered like `#1 A medieval knight` or `# 1 - An enchanted forest`, `COMMENT_LINE_REGEX.match('#1...')` returns a match object and silently discards the line.
   - If all prompts in a batch use `#1`, `#2`, ..., `parse_batch_prompts` raises:
     ```
     ValueError: No valid prompts found in input text after parsing and filtering.
     ```

3. **Character Boundary Sanitation (`database/models.py`, lines 294–320)**:
   - Linebreak normalization handles `\r\n` and `\r`.
   - However, UTF-8 Byte Order Marks (`\ufeff`), zero-width spaces (`\u200b`, `\u200c`, `\u200d`, `\u2060`), and null bytes (`\x00`) are not stripped before regex matching. If a user pastes text containing a leading BOM or zero-width character, the `^` regex anchor fails, causing prefix stripping to silently fail.

4. **UI Ingestion Bypass (`ui/image_page.py`, lines 10–33, and `ui/video_page.py`, lines 10–33)**:
   ```python
   lines = [line.strip() for line in prompt_text.split('\n') if line.strip()]
   if not lines:
       ui.notify("Vui lòng nhập ít nhất 1 dòng Prompt!", type='warning')
       return
       
   success_count = 0
   for p in lines:
       job_id = f"IMG-{str(uuid.uuid4())[:8].upper()}"
       job_data = {
           "id": job_id,
           "project": "Default",
           "media_type": "image",
           "prompt": p,
           "ratio": "Default",
           "model": "Default",
           "status": "PENDING",
           "progress": 0
       }
       try:
           models.add_job(job_data)
   ```
   - Both UI tabs completely bypass `models.create_prompt_batch` and `models.parse_batch_prompts`.
   - Neither prefix stripping nor comment filtering is applied when users input prompts via the UI.
   - No `prompt_batches` or `scenes` records are created in SQLite.

5. **Downstream Worker & Extension Execution (`workers/browser_worker.py`, lines 201–217, `flow-extension/content.js`, lines 89–129, and `flow-extension/flow.js`, lines 93–130)**:
   - `browser_worker.py` dispatches the raw prompt from the `jobs` table over WebSocket to the Chrome Extension.
   - `flow.js: setPrompt()` injects `prompt` directly into the Google Flow input element (`input.innerText = prompt; input.value = prompt;`).
   - Unsanitized prefixes (`[Shot #42] - `, `.. `) directly reach Google Flow's AI models (Nano Banana 2 / Veo 3.1 Lite), altering image/video generation conditioning.

---

## 2. Logic Chain

1. **Adversarial Failure Attribution**:
   - Observations 1 & 2 directly confirm the failure modes discovered by Challenger (`teamwork_preview_challenger_m1_2`):
     - `PROMPT_PREFIX_REGEX` fails on `#` due to rigid `\d+` without `#` allowances, and fails on multiple delimiters due to lack of quantifier `+` on `[:.\-\)\]]`.
     - `COMMENT_LINE_REGEX` lacks a negative lookahead, misclassifying `#1` as a comment.
2. **Critical Number Preservation Requirement**:
   - While `1. `, `1... `, `#1 `, and `Scene 1: ` must be stripped, genuine numeric prompt descriptions like `"3 cats on a wooden fence"` or `"2024 futuristic Tokyo Olympic stadium"` must **NEVER** have `"3 "` or `"2024 "` stripped.
   - Therefore, a pure integer must require an explicit delimiter (`[:.\-\)]+`) to trigger stripping, whereas `#\s*\d+` or keyword prefixes (`scene`, `shot`) can be safely stripped even with flexible delimiters.
3. **End-to-End Vulnerability Identification**:
   - Fixing `database/models.py` alone is necessary but insufficient if the UI bypasses it. Observation 4 proves that `ui/image_page.py` and `ui/video_page.py` bypass `models.create_prompt_batch`.
   - By routing the UI through `models.create_prompt_batch`, prompts are sanitized via `parse_batch_prompts`, batched atomically, linked to `scenes`, and given correct priority before dispatching to Playwright workers (Observation 5).
4. **Remediation Plan Formulation**:
   - The unified strategy addresses the regexes, character sanitization, UI integration, and test suite.

---

## 3. Caveats

1. PySide6 desktop tabs (`ui/tabs/image_gen_tab.py`, `ui/tabs/video_gen_tab.py`) from PROJECT.md layout are slated for Milestone M5; the current running UI is NiceGUI (`ui/image_page.py`, `ui/video_page.py`). The remediation applies immediately to the active NiceGUI pages and establishes the exact pattern for M5 tabs.
2. Interactive command execution via `run_command` timed out waiting for human user permission in this session, consistent with the Challenger agent's findings. Analysis and verification were conducted via deterministic regex trace modeling and static analysis.

---

## 4. Conclusion

The remediation strategy is fully specified in `.agents/teamwork_preview_explorer_m1_it2_3/plan.md`. The Worker agent should execute the following 4 remediation steps:

### 1. In `database/models.py`:
- Replace `PROMPT_PREFIX_REGEX` (lines 274–277) with:
  ```python
  PROMPT_PREFIX_REGEX = re.compile(
      r'^(?:'
      r'[\[\(]\s*(?:(?:scene|shot)\s*#?\s*\d+|#?\s*\d+(?:\.\d+)*)\s*[\]\)]\s*[:.\-\s]*|'
      r'(?:scene|shot)\s*#?\s*\d+(?:\.\d+)*\s*[:.\-\)]*\s*|'
      r'#\s*\d+(?:\.\d+)*\s*[:.\-\)]*\s*|'
      r'\d+(?:\.\d+)*\s*[:.\-\)]+\s*'
      r')',
      re.IGNORECASE
  )
  ```
- Replace `COMMENT_LINE_REGEX` (lines 279–281) with:
  ```python
  COMMENT_LINE_REGEX = re.compile(
      r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
  )
  ```
- In `parse_batch_prompts` (lines 283–329):
  - Strip BOM and null bytes: `raw_text = raw_text.lstrip('\ufeff').replace('\x00', '')`
  - Strip zero-width characters: `cleaned = line.strip().strip('\u200b\u200c\u200d\u2060\ufeff').strip()`

### 2. In `ui/image_page.py` (lines 10–36):
- Replace manual line splitting and `models.add_job` loop with `models.create_prompt_batch`:
  ```python
  try:
      batch_id = models.create_prompt_batch(
          name=f"Image Batch {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
          text=prompt_text,
          media_type="image",
          project_id="Default",
          strip_prefixes=True
      )
      batch = models.get_prompt_batch(batch_id)
      count = batch['total_count'] if batch else 0
      ui.notify(f"Đã thêm thành công {count} prompt vào hàng đợi! Hệ thống sẽ tự động phân phối xoay vòng cho các tài khoản.", type='positive')
      prompt_input_element.value = ''
  except ValueError as ve:
      ui.notify(f"Lỗi nhập liệu: {ve}", type='warning')
  except Exception as e:
      ui.notify(f"Lỗi hệ thống khi tạo lô prompt: {e}", type='negative')
  ```

### 3. In `ui/video_page.py` (lines 10–36):
- Replace manual line splitting and `models.add_job` loop with `models.create_prompt_batch`:
  ```python
  try:
      batch_id = models.create_prompt_batch(
          name=f"Video Batch {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
          text=prompt_text,
          media_type="video",
          project_id="Default",
          strip_prefixes=True
      )
      batch = models.get_prompt_batch(batch_id)
      count = batch['total_count'] if batch else 0
      ui.notify(f"Đã thêm thành công {count} prompt video vào hàng đợi! Hệ thống sẽ tự động phân phối xoay vòng cho các tài khoản.", type='positive')
      prompt_input_element.value = ''
  except ValueError as ve:
      ui.notify(f"Lỗi nhập liệu: {ve}", type='warning')
  except Exception as e:
      ui.notify(f"Lỗi hệ thống khi tạo lô prompt: {e}", type='negative')
  ```

### 4. In `tests/test_database.py`:
- Update `test_parse_batch_prompts_strips_numbering_and_comments` and add unit tests asserting:
  - `[Shot #42] - ` -> stripped
  - `Scene #99: ` -> stripped
  - `1... ` -> stripped
  - `#1 Prompt` -> preserved as prompt, stripped of `#1 `
  - `3 cats on a fence` -> preserved as `"3 cats on a fence"`
  - `2024 futuristic city` -> preserved as `"2024 futuristic city"`
  - `\ufeff1. Mountain` -> stripped to `"Mountain"`

---

## 5. Verification Method

1. **Empirical Regex Script**:
   Run `.agents/teamwork_preview_challenger_m1_2/verify_regex_empirical.py`. All cases must report PASS.
2. **Adversarial Test Harness**:
   Run `.agents/teamwork_preview_challenger_m1_2/test_harness_adversarial.py`. All 15 tests must pass with 0 failures.
3. **Database Test Suite**:
   Run `python tests/test_database.py`. All unit tests must pass.
4. **Invalidation Conditions**:
   - `parse_batch_prompts("[Shot #42] - A drone flying")[0] != "A drone flying"`
   - `parse_batch_prompts("1... Deep sea jellyfish")[0] != "Deep sea jellyfish"`
   - `parse_batch_prompts("#1 A knight")[0] != "A knight"`
   - `parse_batch_prompts("3 cats sitting on a wall")[0] != "3 cats sitting on a wall"`
   - Submitting prompts in `ui/image_page.py` fails to populate `prompt_batches` and `scenes`.
