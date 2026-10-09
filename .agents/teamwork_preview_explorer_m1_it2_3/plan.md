# Milestone M1 (Iteration 2): Prompt Parsing Regex Remediation Strategy & Plan

**Agent**: `teamwork_preview_explorer_m1_it2_3`  
**Project**: VQPVEO3PRO - AI Video Generation Studio  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_it2_3`  
**Project Root**: `d:/New folder (5)`  
**Target Milestone**: M1 (Iteration 2) - Prompt Parsing Regex Remediation  
**Date**: 2026-09-08  

---

## 1. Executive Summary

During Milestone M1 adversarial verification by Challenger agent (`teamwork_preview_challenger_m1_2`), the database schema, migrations, priority queue, and cooldown system passed verification, but prompt parsing in `database/models.py` received a **REQUEST_CHANGES** verdict due to regex edge-case failures:
1. `[Shot #42] - ` and `Scene #99: ` are not stripped because `\d+` does not accommodate `#` or `#?\s*\d+`.
2. Multiple dots (`1... `) only strip the first dot, leaving leading dots (`.. `) that pollute the generative prompt.
3. Lines starting with `#1 ` or `# 1 ` are treated as comments by `COMMENT_LINE_REGEX` and discarded, which can cause entire user storyboard batches to fail.

Furthermore, an end-to-end trace from UI input through to Playwright workers revealed an additional **architectural bypass in the UI layer**:
- `ui/image_page.py` and `ui/video_page.py` perform a naive `prompt_text.split('\n')` and call `models.add_job` directly, completely bypassing `parse_batch_prompts`, `create_prompt_batch`, comment filtering, prefix stripping, constraint checking, and scene graph creation!

This document provides the comprehensive end-to-end investigation findings and formulates a bulletproof remediation plan for the Worker agent.

---

## 2. End-to-End Prompt Flow Architectural Trace

The lifecycle of a prompt progresses through 5 stages:

```
[1. UI Layer] (ui/image_page.py / ui/video_page.py)
   │  User inputs multi-line prompt batch into QTextArea / ui.textarea
   │  CURRENT FLAW: Calls prompt_text.split('\n') & models.add_job directly (bypassing sanitation!)
   ▼
[2. Parsing & Sanitization Layer] (database/models.py: parse_batch_prompts)
   │  Normalize linebreaks (\r\n, \r -> \n)
   │  Filter comment lines (COMMENT_LINE_REGEX)
   │  Strip storyboard numbering prefixes (PROMPT_PREFIX_REGEX)
   │  Enforce constraints (min_length=3, max_length=1500, max_prompts=100)
   ▼
[3. Persistence & Queue Layer] (database/models.py: create_prompt_batch)
   │  Atomic transaction:
   │    - INSERT INTO prompt_batches (raw_text, total_count, status='PENDING')
   │    - INSERT INTO scenes (batch_id, scene_number, prompt)
   │    - INSERT INTO jobs (batch_id, scene_id, prompt, priority, status='PENDING')
   ▼
[4. Dispatcher / Worker Layer] (workers/scheduler.py & workers/browser_worker.py)
   │  Scheduler polls pending jobs via get_pending_jobs() (ordered by priority DESC, created_at ASC)
   │  Worker picks up job, packages payload {"action": "generate", "job_id": ..., "prompt": ...}
   │  Transmits payload over WebSocket to Chrome Extension
   ▼
[5. Browser DOM Execution Layer] (flow-extension/content.js & flow-extension/flow.js)
   │  content.js receives payload and invokes adapter.setPrompt(data.prompt)
   │  flow.js sets input.innerText / input.value and triggers DOM input/change/keyup events
   │  Google Flow (Nano Banana 2 / Veo 3.1 Lite) receives prompt for generative AI execution
```

---

## 3. Gap & Vulnerability Analysis

### Gap 1: Incomplete Prefix Matching Pattern
- **Location**: `database/models.py`, lines 274–277.
- **Current Pattern**:
  ```python
  PROMPT_PREFIX_REGEX = re.compile(
      r'^(?:\[\s*(?:scene\s*\d+|shot\s*\d+|\d+)\s*\]\s*[-:]?\s*|(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*)',
      re.IGNORECASE
  )
  ```
- **Flaws**:
  1. `(?:scene\s*\d+|shot\s*\d+|\d+)` requires digits immediately after `scene` or `shot`. It fails when `#` is present (e.g., `[Shot #42] - `, `Scene #99: `, `[Scene #1]`).
  2. Does not accommodate parentheses delimiters `(1)`, `(Scene 1)`, `(Shot #2) - `.
  3. Does not accommodate hierarchical numbering `1.1. `, `1.2 `, `2.1.1: `.

### Gap 2: Single-Character Delimiter Consumption
- **Location**: `database/models.py`, line 275 (`[:.\-\)\]]\s*`).
- **Flaw**:
  Matches only one punctuation character. For `"1... Deep sea jellyfish"`, it matches `"1."`, leaving `".. Deep sea jellyfish"`. For `"1. - Prompt"`, it leaves `"- Prompt"`.
- **Impact**: Generative AI models conditioning on prompts starting with `".. "` or `"- "` produce degraded, off-target imagery or unwanted typographic artifacts.

### Gap 3: Comment Regex Collision with Numbered Prompts
- **Location**: `database/models.py`, lines 279–281:
  ```python
  COMMENT_LINE_REGEX = re.compile(
      r'^(?:#|//|/\*|---|===|\*\*)'
  )
  ```
- **Flaw**:
  Matches any line starting with `#`. Users numbering prompts as `#1 Prompt`, `#2 Prompt`, or `# 1 - Prompt` have their prompts silently discarded as comments. If all lines use this numbering, `parse_batch_prompts` raises `ValueError: No valid prompts found in input text after parsing and filtering.`

### Gap 4: Number Preservation Guardrail (Critical Distinguishing Rule)
- **Constraint**: Pure numbers must **NOT** be stripped unless followed by explicit punctuation delimiters (`.`, `:`, `-`, `)`).
  - `"3 cats on a wooden fence"` -> **MUST REMAIN** `"3 cats on a wooden fence"`. Stripping `"3 "` destroys the user's intent.
  - `"2024 futuristic Tokyo Olympic stadium"` -> **MUST REMAIN** `"2024 futuristic Tokyo Olympic stadium"`.
  - In contrast, `"100. A mountain"` or `"1... A mountain"` or `"#1 A mountain"` or `"Scene 1 A mountain"` represents storyboard metadata and must be stripped.

### Gap 5: Invisible Character & BOM Sanitization
- **Location**: `database/models.py`, line 297.
- **Flaw**:
  `normalized = raw_text.replace('\r\n', '\n').replace('\r', '\n')`.
  If input text contains UTF-8 Byte Order Mark (`\ufeff`) or zero-width spaces (`\u200b`, `\u200c`, `\u200d`, `\u2060`) at the start of a line (extremely common when copy-pasting from Notion, Discord, or rich web text), the regex start-of-line anchor `^` fails to match the prefix, causing prefix stripping to silently fail!
  Additionally, null bytes (`\x00`) can corrupt SQLite text storage or C-string lengths in downstream processes.

### Gap 6: UI Layer Architectural Bypass
- **Location**: `ui/image_page.py` (lines 10–33) and `ui/video_page.py` (lines 10–33).
- **Flaw**:
  ```python
  lines = [line.strip() for line in prompt_text.split('\n') if line.strip()]
  for p in lines:
      ...
      models.add_job(job_data)
  ```
  Neither page calls `models.create_prompt_batch` or `models.parse_batch_prompts`. As a result:
  - Raw prefixes and comments are fed directly into the `jobs` table.
  - No `prompt_batches` or `scenes` records are created.
  - Video jobs do not receive default priority 10 via the batch ingestion contract.
  - UI users never benefit from the M1 sanitization pipeline!

---

## 4. Comprehensive Remediation Strategy

### Component A: Hardened Regex Design

#### 1. Hardened `COMMENT_LINE_REGEX`:
Use a negative lookahead assertion on `#` to ensure lines beginning with `#` followed by a number (optional whitespace/hash and digits) are **NOT** discarded as comments:
```python
COMMENT_LINE_REGEX = re.compile(
    r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
)
```

#### 2. Hardened `PROMPT_PREFIX_REGEX`:
A robust 4-branch alternation regex that handles:
- Branch 1 (Brackets/Parentheses): `[\[\(]\s*(?:(?:scene|shot)\s*#?\s*\d+|#?\s*\d+(?:\.\d+)*)\s*[\]\)]\s*[:.\-\s]*`
- Branch 2 (Keyword prefixes): `(?:scene|shot)\s*#?\s*\d+(?:\.\d+)*\s*[:.\-\)]*\s*`
- Branch 3 (Hash-prefixed numbers): `#\s*\d+(?:\.\d+)*\s*[:.\-\)]*\s*`
- Branch 4 (Numbers with required delimiter): `\d+(?:\.\d+)*\s*[:.\-\)]+\s*`

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

**Verification Matrix for Regex**:
| Input | Result | Status |
|---|---|---|
| `"[Shot #42] - Futuristic drone"` | `"Futuristic drone"` | STRIPPED |
| `"Scene #99: Cyberpunk street"` | `"Cyberpunk street"` | STRIPPED |
| `"Scene 99: Cyberpunk street"` | `"Cyberpunk street"` | STRIPPED |
| `"1... Deep sea jellyfish"` | `"Deep sea jellyfish"` | STRIPPED |
| `"100. A majestic mountain"` | `"A majestic mountain"` | STRIPPED |
| `"1.1. Space shuttle launching"` | `"Space shuttle launching"` | STRIPPED |
| `"#1 A medieval knight"` | `"A medieval knight"` | STRIPPED (Not comment!) |
| `"# 1: A medieval knight"` | `"A medieval knight"` | STRIPPED (Not comment!) |
| `"(1) Flying eagle"` | `"Flying eagle"` | STRIPPED |
| `"(Shot 1) Flying eagle"` | `"Flying eagle"` | STRIPPED |
| `"3 cats on a wooden fence"` | `"3 cats on a wooden fence"` | PRESERVED |
| `"2024 futuristic Tokyo"` | `"2024 futuristic Tokyo"` | PRESERVED |
| `"# Project header outline"` | Discarded as comment | FILTERED |
| `"// Cut to scene 2"` | Discarded as comment | FILTERED |

### Component B: String & Character Sanitization Pipeline

In `database/models.py: parse_batch_prompts`:
1. Strip leading BOM: `raw_text = raw_text.lstrip('\ufeff')`
2. Remove null bytes: `raw_text = raw_text.replace('\x00', '')`
3. Normalize linebreaks: `.replace('\r\n', '\n').replace('\r', '\n')`
4. Strip zero-width spaces (`\u200b`, `\u200c`, `\u200d`, `\u2060`, `\ufeff`) when trimming lines:
   ```python
   ZERO_WIDTH_CHARS = '\u200b\u200c\u200d\u2060\ufeff'
   cleaned = line.strip().strip(ZERO_WIDTH_CHARS).strip()
   ```

### Component C: UI Hooking & Atomic Queue Ingestion

Refactor `ui/image_page.py` and `ui/video_page.py` to route through `models.create_prompt_batch`:

**In `ui/image_page.py`**:
```python
async def trigger_batch_image_jobs(prompt_text, prompt_input_element):
    if not prompt_text or not prompt_text.strip():
        ui.notify("Vui lòng điền mô tả hình ảnh (Mỗi dòng là 1 Prompt)!", type='warning')
        return
        
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

**In `ui/video_page.py`**:
```python
async def trigger_batch_video_jobs(prompt_text, prompt_input_element):
    if not prompt_text or not prompt_text.strip():
        ui.notify("Vui lòng điền mô tả video (Mỗi dòng là 1 Prompt)!", type='warning')
        return
        
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

### Component D: Test Suite Hardening

In `tests/test_database.py`:
1. Update `test_parse_batch_prompts_strips_numbering_and_comments` to include `[Shot #42] - `, `Scene #99: `, `1... `, `#1 `, `(1) `.
2. Add dedicated test `test_parse_batch_prompts_preserves_numeric_prompts` testing `"3 cats on a fence"` and `"2024 futuristic city"`.
3. Add dedicated test `test_parse_batch_prompts_bom_and_zero_width` testing `\ufeff` and `\u200b`.
4. Include all tests in `tests/test_database.py:run_all_tests()`.

---

## 5. Concrete Remediation Implementation Guide for Worker

### Step 1: Modify `database/models.py`
- Replace `PROMPT_PREFIX_REGEX` (lines 274–277) with the hardened pattern.
- Replace `COMMENT_LINE_REGEX` (lines 279–281) with the negative lookahead pattern.
- In `parse_batch_prompts` (lines 283–329):
  - Add BOM and null-byte cleanup at the start of `raw_text`.
  - Add zero-width character stripping on `line.strip()`.

### Step 2: Modify `ui/image_page.py`
- Replace manual line splitting and `models.add_job` loop with `models.create_prompt_batch(..., media_type="image", ...)`.
- Wrap in `try ... except ValueError as ve ... except Exception as e` with `ui.notify`.

### Step 3: Modify `ui/video_page.py`
- Replace manual line splitting and `models.add_job` loop with `models.create_prompt_batch(..., media_type="video", ...)`.
- Wrap in `try ... except ValueError as ve ... except Exception as e` with `ui.notify`.

### Step 4: Update `tests/test_database.py`
- Add test assertions for `[Shot #42] - `, `Scene #99: `, `1... `, `#1 `, `(1) `, numeric preservation (`3 cats...`), and BOM.
- Verify that `verify_regex_empirical.py` and `test_harness_adversarial.py` pass 100%.

---

## 6. Verification and Acceptance Criteria

1. `parse_batch_prompts("[Shot #42] - A drone flying") == ["A drone flying"]`
2. `parse_batch_prompts("Scene #99: Neon alley") == ["Neon alley"]`
3. `parse_batch_prompts("1... Deep sea jellyfish") == ["Deep sea jellyfish"]`
4. `parse_batch_prompts("#1 A medieval knight\n#2 A dragon") == ["A medieval knight", "A dragon"]`
5. `parse_batch_prompts("3 cats sitting on a wooden fence") == ["3 cats sitting on a wooden fence"]`
6. `parse_batch_prompts("2024 futuristic city") == ["2024 futuristic city"]`
7. Submitting batch prompts via `ui/image_page.py` and `ui/video_page.py` creates linked entries in `prompt_batches`, `scenes`, and `jobs` tables in SQLite with clean, sanitized prompt text.
8. Full pytest / database test suite passes with 0 failures.
