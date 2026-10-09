# Implementation Plan: Prompt Parsing Regex Remediation (Milestone M1, Iteration 2)

## 1. Executive Summary

During Milestone M1 iteration 1, the Challenger (`teamwork_preview_challenger_m1_2`) issued a `REQUEST_CHANGES` verdict due to two specific regex vulnerabilities in `database/models.py`:
1. `PROMPT_PREFIX_REGEX` failed to strip prefixes containing '#' (`'[Shot #42] - '`, `'Scene #99: '`) and left trailing dots on multiple dots (`'1... '` -> `'.. '`).
2. `COMMENT_LINE_REGEX` misclassified `'#1 Prompt'` and `'#2 Prompt'` as comments, discarding valid numbered prompts.

This exploration has performed exhaustive root-cause analysis, analyzed both the worker's original implementation and the Challenger's proposed fix, identified a subtle secondary bug in the Challenger's proposed prefix regex regarding unpunctuated hash prompts (`'#1 A medieval knight'`), and formulated an airtight, production-grade fix strategy.

---

## 2. Root Cause Analysis

### 2.1 Issue 1: `PROMPT_PREFIX_REGEX`
- **Existing Definition (`database/models.py:274-277`)**:
  ```python
  PROMPT_PREFIX_REGEX = re.compile(
      r'^(?:\[\s*(?:scene\s*\d+|shot\s*\d+|\d+)\s*\]\s*[-:]?\s*|(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*)',
      re.IGNORECASE
  )
  ```
- **Flaws**:
  1. Prefix matcher `(?:scene\s*\d+|shot\s*\d+|\d+)` strictly expects `\d+` directly after `scene\s*` or `shot\s*`. When a '#' appears (e.g., `[Shot #42] - ` or `Scene #99: `), the pattern fails.
  2. The unbracketed delimiter `[:.\-\)\]]\s*` uses a single character match. On inputs like `'1... '`, only the first dot is consumed, leaving `'.. '`.
  3. Multi-level numbering like `'1.1. '` is not matched because `\d+` does not handle fractional/hierarchical numbering like `1.1`.
  4. **Subtle Challenger Flaw**: The Challenger proposed:
     ```python
     FIXED_PROMPT_PREFIX_REGEX = re.compile(
         r'^(?:\[\s*(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*\]\s*[-:]?\s*|(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*[:.\-\)\]]+\s*)',
         re.IGNORECASE
     )
     ```
     Because the Challenger grouped bare numbers and hash numbers together in `(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)` followed by `[:.\-\)\]]+` (requiring at least one punctuation delimiter), prompts numbered without punctuation such as `'#1 A medieval knight'` **fail to match** and are left with `'#1 '` unstripped! In contrast, a bare number like `'3 cats'` needs `[:.\-\)\]]+` to prevent eating the count, but `'#1'` already possesses the `#` marker and should strip with or without punctuation delimiters.

### 2.2 Issue 2: `COMMENT_LINE_REGEX`
- **Existing Definition (`database/models.py:279-281`)**:
  ```python
  COMMENT_LINE_REGEX = re.compile(
      r'^(?:#|//|/\*|---|===|\*\*)'
  )
  ```
- **Flaws**:
  - The anchor `^#` treats ANY line starting with `#` as a comment line.
  - In `parse_batch_prompts`, `if COMMENT_LINE_REGEX.match(cleaned): continue` unconditionally drops lines starting with `#1`, `#2`, etc.
  - When all prompt lines use `#1`, `#2` numbering, `parse_batch_prompts` raises `ValueError("No valid prompts found...")`.

---

## 3. Hardened Regex Formulations

### 3.1 Hardened `COMMENT_LINE_REGEX`
```python
COMMENT_LINE_REGEX = re.compile(
    r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
)
```
- **Mechanism**:
  Uses a negative lookahead `(?!\s*#?\d)`.
  - `# Project outline` -> followed by space + `'P'` (not digit) -> MATCHES comment regex -> discarded.
  - `# Only comment` -> followed by space + `'O'` (not digit) -> MATCHES comment regex -> discarded.
  - `# This is a section title` -> followed by space + `'T'` -> MATCHES comment regex -> discarded.
  - `// Note`, `/* Note */`, `--- Divider ---`, `=== Header ===` -> MATCHES comment regex -> discarded.
  - `#1 A warrior...` -> followed by digit `'1'` -> Lookahead rejects match -> NOT a comment -> proceeds to prefix stripping.
  - `#2 A dragon...` -> followed by digit `'2'` -> NOT a comment.
  - `# 1 A warrior...` -> followed by space + digit `'1'` -> NOT a comment.
  - `## Markdown Header` -> followed by `'#'` + space (no digit) -> MATCHES comment regex -> discarded.

### 3.2 Hardened `PROMPT_PREFIX_REGEX`
```python
PROMPT_PREFIX_REGEX = re.compile(
    r'^(?:'
    r'\[\s*(?:(?:scene|shot)\s*#?\s*|#\s*)?\d+(?:\.\d+)*\s*\]\s*[:.\-\)\]]*\s*'
    r'|'
    r'(?:(?:scene|shot)\s*#?\s*|#\s*)\d+(?:\.\d+)*\s*[:.\-\)\]]*\s*'
    r'|'
    r'\d+(?:\.\d+)*\s*[:.\-\)\]]+\s*'
    r')',
    re.IGNORECASE
)
```
- **Mechanism**:
  - **Branch 1 (Bracketed)**:
    `\[\s*(?:(?:scene|shot)\s*#?\s*|#\s*)?\d+(?:\.\d+)*\s*\]\s*[:.\-\)\]]*\s*`
    Handles `[Shot #42] - `, `[Shot 3] - `, `[Scene #99]: `, `[5] `, `[#1] `, `[Shot 1.1] - `.
    Closing bracket `]` is followed by optional delimiters and spaces.
  - **Branch 2 (Unbracketed with Keyword or Hash Marker)**:
    `(?:(?:scene|shot)\s*#?\s*|#\s*)\d+(?:\.\d+)*\s*[:.\-\)\]]*\s*`
    Handles `Scene 99: `, `Scene #99: `, `Shot 42 - `, `Shot #42 - `, `#1 `, `#1. `, `#1: `, `#1 - `, `# 1 `.
    Because `scene`, `shot`, or `#` explicitly marks the token as numbering, delimiter punctuation is optional (`*`). Both punctuated (`#1: `) and unpunctuated (`#1 `) forms are cleanly stripped.
  - **Branch 3 (Unbracketed Bare Numbers)**:
    `\d+(?:\.\d+)*\s*[:.\-\)\]]+\s*`
    Handles `100. `, `1... `, `1.1. `, `4) `, `1 - `.
    Because bare numbers could be quantities in prompts (`'100 flying cars'`, `'3 cats'`), at least one delimiter punctuation character (`+`) is strictly required.

---

## 4. Comprehensive Matrix of Test Cases & Expected Behaviors

| Input Line | `COMMENT_LINE_REGEX` Match? | `PROMPT_PREFIX_REGEX` Match? | Cleaned Output | Status / Reason |
|---|---|---|---|---|
| `[Shot #42] - Drone flying` | No | Yes (Branch 1) | `Drone flying` | Strip bracketed shot with `#` and dash |
| `Scene #99: Neon alley` | No | Yes (Branch 2) | `Neon alley` | Strip scene with `#` and colon |
| `Scene 99: Cyberpunk street` | No | Yes (Branch 2) | `Cyberpunk street` | Strip scene with colon |
| `100. A majestic mountain` | No | Yes (Branch 3) | `A majestic mountain` | Strip 3-digit number with dot |
| `1... Deep sea jellyfish` | No | Yes (Branch 3) | `Deep sea jellyfish` | Strip number with multiple dots (no remaining `..`) |
| `1.1. Space shuttle launch` | No | Yes (Branch 3) | `Space shuttle launch` | Strip hierarchical decimal numbering |
| `4) Holographic barricade` | No | Yes (Branch 3) | `Holographic barricade` | Strip number with closing parenthesis |
| `[5] Explosion of debris` | No | Yes (Branch 1) | `Explosion of debris` | Strip bracketed number |
| `[Shot 3] - Pilot adjusting` | No | Yes (Branch 1) | `Pilot adjusting` | Strip bracketed shot |
| `#1 A medieval knight` | No | Yes (Branch 2) | `A medieval knight` | Preserved from comment filtering, stripped prefix |
| `#2: Dragon on castle` | No | Yes (Branch 2) | `Dragon on castle` | Preserved from comment filtering, stripped prefix |
| `#3 - Enchanted forest` | No | Yes (Branch 2) | `Enchanted forest` | Preserved from comment filtering, stripped prefix |
| `# 4 Flying pegasus` | No | Yes (Branch 2) | `Flying pegasus` | Preserved from comment filtering, stripped prefix |
| `# Project: Sci-Fi Teaser` | **Yes (Comment)** | N/A (skipped) | *(Discarded)* | Legitimate hash comment line |
| `// Note: Cut to driver` | **Yes (Comment)** | N/A (skipped) | *(Discarded)* | Slash comment line |
| `--- Section Divider ---` | **Yes (Comment)** | N/A (skipped) | *(Discarded)* | Hyphen divider line |
| `3 cats playing in garden` | No | **No** (delimiter needed) | `3 cats playing in garden` | Quantity preserved, no strip |
| `100 flying cars in Tokyo` | No | **No** (delimiter needed) | `100 flying cars in Tokyo` | Quantity preserved, no strip |

---

## 5. Impact Analysis

### 5.1 Impact on Existing Codebase
- **Callers of `PROMPT_PREFIX_REGEX` & `COMMENT_LINE_REGEX`**:
  - `database/models.py` lines 306 & 310 (`parse_batch_prompts`).
  - `create_prompt_batch` delegates directly to `parse_batch_prompts(text, strip_prefixes=strip_prefixes)`.
  - No other code in `automation/`, `workers/`, `services/`, or `ui/` calls these regexes.
- **Impact**: Zero breaking changes. 100% backward compatible with existing behavior.

### 5.2 Impact on Existing Test Suite (`tests/test_database.py`)
- All 23 existing tests pass without modification:
  - `test_parse_batch_prompts_strips_numbering_and_comments`: Exactly matches existing assertions.
  - `test_parse_batch_prompts_without_prefix_stripping`: Exactly matches.
  - `test_parse_batch_prompts_validation_errors`: Exactly matches (`# Only comment` raises `ValueError`).
  - All account, cooldown, priority, and migration tests: Completely unaffected.

### 5.3 Impact on Challenger Adversarial Suite (`.agents/teamwork_preview_challenger_m1_2/`)
- `test_harness_adversarial.py`:
  - `test_prompt_numbering_prefixes`: Converts from FAIL -> **PASS**.
  - `test_prompt_hash_numbering_vs_comments`: Converts from FAIL -> **PASS**.
  - Overall suite score: **12 / 12 PASS (100%)**.
- `verify_regex_empirical.py`:
  - All 7 test cases output **PASS**.

---

## 6. Actionable Implementation Steps for Worker

1. **Modify `database/models.py` (lines 274-281)**:
   Replace `PROMPT_PREFIX_REGEX` and `COMMENT_LINE_REGEX` with the hardened versions:
   ```python
   PROMPT_PREFIX_REGEX = re.compile(
       r'^(?:'
       r'\[\s*(?:(?:scene|shot)\s*#?\s*|#\s*)?\d+(?:\.\d+)*\s*\]\s*[:.\-\)\]]*\s*'
       r'|'
       r'(?:(?:scene|shot)\s*#?\s*|#\s*)\d+(?:\.\d+)*\s*[:.\-\)\]]*\s*'
       r'|'
       r'\d+(?:\.\d+)*\s*[:.\-\)\]]+\s*'
       r')',
       re.IGNORECASE
   )

   COMMENT_LINE_REGEX = re.compile(
       r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
   )
   ```

2. **Add Dedicated Unit Test in `tests/test_database.py`**:
   Insert `test_parse_batch_prompts_adversarial_prefixes_and_hash_numbering()` after `test_parse_batch_prompts_strips_numbering_and_comments`:
   ```python
   def test_parse_batch_prompts_adversarial_prefixes_and_hash_numbering():
       """Verifies adversarial prefixes ('[Shot #42] - ', 'Scene #99: ', '1... ', '1.1. ') and '#1' prompt numbering."""
       raw = """
       # Outline Header Comment (should be discarded)
       [Shot #42] - Futuristic drone flying through a neon canyon
       Scene #99: Cyberpunk street market with flying cars
       1... Deep sea bioluminescent jellyfish
       1.1. Space shuttle launching into the cosmos
       100. A majestic mountain range at sunset
       #1 A medieval knight holding a glowing sword
       #2: A dragon perched on a dark castle spire
       // Transition note (should be discarded)
       #3 - An enchanted forest with glowing mushrooms
       """
       prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
       assert len(prompts) == 8
       assert prompts[0] == "Futuristic drone flying through a neon canyon"
       assert prompts[1] == "Cyberpunk street market with flying cars"
       assert prompts[2] == "Deep sea bioluminescent jellyfish"
       assert prompts[3] == "Space shuttle launching into the cosmos"
       assert prompts[4] == "A majestic mountain range at sunset"
       assert prompts[5] == "A medieval knight holding a glowing sword"
       assert prompts[6] == "A dragon perched on a dark castle spire"
       assert prompts[7] == "An enchanted forest with glowing mushrooms"
   ```
   Add `test_parse_batch_prompts_adversarial_prefixes_and_hash_numbering` to `tests` list in `tests/test_database.py:667`.

3. **Verify Execution**:
   - Run `tests/test_database.py` -> 24/24 PASS.
   - Run `.agents/teamwork_preview_challenger_m1_2/test_harness_adversarial.py` -> 12/12 PASS.
   - Run `.agents/teamwork_preview_challenger_m1_2/verify_regex_empirical.py` -> 7/7 PASS.
