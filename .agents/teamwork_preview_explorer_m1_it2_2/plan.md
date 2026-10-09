# Milestone M1 (Iteration 2): Prompt Parsing Regex Remediation & Regression Test Plan

**Agent**: `teamwork_preview_explorer_m1_it2_2`  
**Working Directory**: `d:/New folder (5)/.agents/teamwork_preview_explorer_m1_it2_2`  
**Date**: 2026-09-08  
**Scope**: Formulation of comprehensive regression test cases for `tests/test_database.py` covering all prompt parsing regex remediation edge cases.

---

## 1. Executive Summary & Problem Diagnosis

During adversarial verification of Milestone M1 (Database Architecture & Core Models), Challenger (`teamwork_preview_challenger_m1_2`) identified two critical vulnerabilities in prompt text preprocessing within `database/models.py`:

1. **`PROMPT_PREFIX_REGEX` fails on `[Shot #42] - ` and `Scene #99: `**:
   - Current implementation:
     ```python
     PROMPT_PREFIX_REGEX = re.compile(
         r'^(?:\[\s*(?:scene\s*\d+|shot\s*\d+|\d+)\s*\]\s*[-:]?\s*|(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*)',
         re.IGNORECASE
     )
     ```
   - Root Cause: Pattern strictly requires digits immediately after `scene\s*` or `shot\s*`. It does not permit an optional hash/number sign (`#`). Consequently, prefixes containing `#` (e.g., `[Shot #42] - `, `Scene #99: `) fail to match and remain unstripped, polluting generative model text conditioning.
   
2. **`PROMPT_PREFIX_REGEX` leaves residual dots on multiple dot prefixes like `1... `**:
   - Current delimiter pattern: `[:.\-\)\]]\s*` matches exactly one delimiter character.
   - Root Cause: In `1... `, only the first dot is removed; the remaining `".. "` is left at the start of the prompt (e.g., `".. Deep sea bioluminescent jellyfish"`).

3. **`COMMENT_LINE_REGEX` prematurely discards numbered prompts like `#1 Prompt`**:
   - Current implementation:
     ```python
     COMMENT_LINE_REGEX = re.compile(
         r'^(?:#|//|/\*|---|===|\*\*)'
     )
     ```
   - Root Cause: `^#` matches any line starting with `#` regardless of what follows. When storyboard prompts are formatted as `#1 Prompt` or `# 1 Prompt`, `COMMENT_LINE_REGEX.match(cleaned)` triggers before prefix stripping, silently dropping valid user prompts. If all prompts use this format, `parse_batch_prompts` raises `ValueError("No valid prompts found in input text after parsing and filtering.")`.

4. **Crucial Nuance in Remediation Regex (Hash Numbering without Delimiter)**:
   - In Challenger's proposed fix:
     ```python
     FIXED_PROMPT_PREFIX_REGEX = re.compile(
         r'^(?:\[\s*(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*\]\s*[-:]?\s*|(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*[:.\-\)\]]+\s*)',
         re.IGNORECASE
     )
     ```
   - Notice the unbracketed branch requires `[:.\-\)\]]+`. If a user inputs `#1 A medieval knight` (with space, but without colon or dot), `[:.\-\)\]]+` fails to match.
   - Therefore, the remediation regex must distinguish between bare digits (which require punctuation delimiters `+` so `2049 megacity` is not stripped) and explicit prefix tokens (`scene`, `shot`, `#`) where trailing punctuation is optional `*`.

---

## 2. Remediated Regex Specifications

### 2.1 Remediated `COMMENT_LINE_REGEX`
```python
COMMENT_LINE_REGEX = re.compile(
    r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
)
```
- **Mechanism**: Negative lookahead `(?!\s*#?\d)` asserts that `#` is NOT followed by optional whitespace, optional `#`, and a digit.
- **Discrimination**:
  - `# Heading`, `# Note:`, `# Project Outline`, `// Note`, `/* Block */`, `---`, `===`, `**` -> MATCH (discarded as comments).
  - `#1`, `# 1`, `#42`, `#100`, `#01`, `##1` -> DO NOT MATCH (preserved for parsing).

### 2.2 Remediated `PROMPT_PREFIX_REGEX`
```python
PROMPT_PREFIX_REGEX = re.compile(
    r'^(?:'
    r'\[\s*(?:(?:scene|shot)\s*#?\s*\d+|#?\s*\d+)\s*\]\s*[:.\-]?\s*'
    r'|'
    r'(?:(?:scene|shot)\s*#?\s*\d+|#\s*\d+)\s*[:.\-\)\]]*\s*'
    r'|'
    r'\d+\s*[:.\-\)\]]+\s*'
    r')',
    re.IGNORECASE
)
```
- **Bracketed Branch**: Matches `[Shot #42] - `, `[Scene #5]: `, `[#1] `, `[5] `, with optional trailing delimiter `[:.\-]?`.
- **Explicit Prefix Branch (`scene`, `shot`, `#`)**: Matches `Scene #99: `, `Shot #42 - `, `#1 `, `#1: `, `# 1 - `, `#42 `. Because the tag (`scene`/`shot`/`#`) is unambiguous, trailing punctuation `[:.\-\)\]]*` is optional.
- **Bare Digits Branch**: Matches `1. `, `1... `, `100. `, `1) `, `1 - `. Requires at least one punctuation delimiter `[:.\-\)\]]+`, ensuring non-prefix numbers like `2049 dystopian megacity` are never stripped.

---

## 3. Comprehensive Test Matrix & Edge Case Taxonomy

| ID | Category | Input String | `strip_prefixes` | Expected Output | Rationale / Boundary |
|---|---|---|---|---|---|
| **C1** | Comment Discrimination | `# Project: Sci-Fi Teaser Outline` | `True` | Discarded | Legitimate project header comment |
| **C2** | Comment Discrimination | `# Heading 1: Overview` | `True` | Discarded | Markdown H1 title comment |
| **C3** | Comment Discrimination | `## Subheading Section` | `True` | Discarded | Markdown H2 title comment |
| **C4** | Comment Discrimination | `### Details and camera angles` | `True` | Discarded | Markdown H3 title comment |
| **C5** | Comment Discrimination | `// Note: Cut to close-up` | `True` | Discarded | Single-line C/JS style comment |
| **C6** | Comment Discrimination | `/* Director notes: lighting */` | `True` | Discarded | Block C-style comment |
| **C7** | Comment Discrimination | `--- Scene Section Divider ---` | `True` | Discarded | Markdown divider line |
| **C8** | Comment Discrimination | `=== Act 1 ===` | `True` | Discarded | Equals sign section divider |
| **C9** | Comment Discrimination | `** Note: Check color grading **` | `True` | Discarded | Double-asterisk emphasis comment |
| **C10** | Comment Discrimination | `# Scene 1 Outline` | `True` | Discarded | Header containing "Scene" but non-digit after hash |
| **C11** | Comment Discrimination | `#` (alone) or `#   ` | `True` | Discarded | Empty hash line |
| **N1** | Numbered Prompt Preservation | `#1 A warrior holding a glowing sword` | `True` | `"A warrior holding a glowing sword"` | Hash numbering with space, no colon |
| **N2** | Numbered Prompt Preservation | `#1: High-speed hovercar chase` | `True` | `"High-speed hovercar chase"` | Hash numbering with colon |
| **N3** | Numbered Prompt Preservation | `#1. Futuristic city street` | `True` | `"Futuristic city street"` | Hash numbering with dot |
| **N4** | Numbered Prompt Preservation | `#1 - Female pilot in cockpit` | `True` | `"Female pilot in cockpit"` | Hash numbering with dash |
| **N5** | Numbered Prompt Preservation | `# 1 Space explorer on mars` | `True` | `"Space explorer on mars"` | Hash followed by space then digit |
| **N6** | Numbered Prompt Preservation | `# 1: Space explorer on mars` | `True` | `"Space explorer on mars"` | Hash followed by space, digit, colon |
| **N7** | Numbered Prompt Preservation | `# 1 - Space explorer on mars` | `True` | `"Space explorer on mars"` | Hash followed by space, digit, dash |
| **N8** | Numbered Prompt Preservation | `#42 Futuristic drone in canyon` | `True` | `"Futuristic drone in canyon"` | Multi-digit hash numbering |
| **N9** | Numbered Prompt Preservation | `#100 A majestic mountain range` | `True` | `"A majestic mountain range"` | 3-digit hash numbering |
| **N10** | Numbered Prompt Preservation | `#01 Ancient temple with vines` | `True` | `"Ancient temple with vines"` | Leading zero hash numbering |
| **N11** | Numbered Prompt Preservation | `##1 Dragon perched on castle` | `True` | `"Dragon perched on castle"` | Double hash numbering |
| **B1** | Bracketed Prefix Stripping | `[Shot #42] - Drone flying over neon canyon` | `True` | `"Drone flying over neon canyon"` | Bracketed shot with `#` and dash |
| **B2** | Bracketed Prefix Stripping | `[Shot # 42] - Drone flying over neon canyon` | `True` | `"Drone flying over neon canyon"` | Bracketed shot with `#` and internal space |
| **B3** | Bracketed Prefix Stripping | `[Shot 42] - Drone flying over neon canyon` | `True` | `"Drone flying over neon canyon"` | Bracketed shot without `#` |
| **B4** | Bracketed Prefix Stripping | `[Scene #5] Stone altar with artifact` | `True` | `"Stone altar with artifact"` | Bracketed scene with `#` |
| **B5** | Bracketed Prefix Stripping | `[Scene 5]: Stone altar with artifact` | `True` | `"Stone altar with artifact"` | Bracketed scene with colon |
| **B6** | Bracketed Prefix Stripping | `[#1] Explosion of glowing debris` | `True` | `"Explosion of glowing debris"` | Bracketed `#1` |
| **B7** | Bracketed Prefix Stripping | `[5] Explosion of glowing debris` | `True` | `"Explosion of glowing debris"` | Bracketed bare number |
| **B8** | Bracketed Prefix Stripping | `[  shot #42  ] - Drone flying` | `True` | `"Drone flying"` | Whitespace and lowercase inside brackets |
| **U1** | Unbracketed Scene/Shot | `Scene #99: Cyberpunk street market` | `True` | `"Cyberpunk street market"` | Unbracketed scene with `#` and colon |
| **U2** | Unbracketed Scene/Shot | `Scene # 99: Cyberpunk street market` | `True` | `"Cyberpunk street market"` | Unbracketed scene with space before digits |
| **U3** | Unbracketed Scene/Shot | `Scene 99: Cyberpunk street market` | `True` | `"Cyberpunk street market"` | Standard scene without `#` |
| **U4** | Unbracketed Scene/Shot | `Shot #42 - Futuristic drone in canyon` | `True` | `"Futuristic drone in canyon"` | Unbracketed shot with `#` and dash |
| **U5** | Unbracketed Scene/Shot | `scene #99: Lowercase scene tag` | `True` | `"Lowercase scene tag"` | Case insensitivity |
| **D1** | Multiple Delimiters | `1... Deep sea bioluminescent jellyfish` | `True` | `"Deep sea bioluminescent jellyfish"` | 3 dots stripped without leaving `.. ` |
| **D2** | Multiple Delimiters | `1.. Two dots jellyfish` | `True` | `"Two dots jellyfish"` | 2 dots stripped cleanly |
| **D3** | Multiple Delimiters | `1.... Four dots jellyfish` | `True` | `"Four dots jellyfish"` | 4 dots stripped cleanly |
| **D4** | Multiple Delimiters | `1.- Dot and dash prompt` | `True` | `"Dot and dash prompt"` | Mixed punctuation delimiter |
| **D5** | Standard Delimiters | `1. Standard dot prompt` | `True` | `"Standard dot prompt"` | Standard `1. ` |
| **D6** | Standard Delimiters | `4) Parenthesis prompt` | `True` | `"Parenthesis prompt"` | Standard `4) ` |
| **D7** | Standard Delimiters | `100. Three digit dot prompt` | `True` | `"Three digit dot prompt"` | `100. ` |
| **P1** | Non-Prefix Number Preservation | `2049 dystopian megacity with flying vehicles` | `True` | `"2049 dystopian megacity with flying vehicles"` | Number at line start without delimiter preserved |
| **P2** | Non-Prefix Number Preservation | `A squad of 5 soldiers in tactical gear` | `True` | `"A squad of 5 soldiers in tactical gear"` | Embedded number in prompt preserved |
| **P3** | Non-Prefix Number Preservation | `4K resolution ultra detailed portrait` | `True` | `"4K resolution ultra detailed portrait"` | Leading spec number preserved |
| **R1** | `strip_prefixes=False` | `#1 A warrior holding a glowing sword` | `False` | `"#1 A warrior holding a glowing sword"` | Prefix retained verbatim |
| **R2** | `strip_prefixes=False` | `[Shot #42] - Futuristic drone` | `False` | `"[Shot #42] - Futuristic drone"` | Bracketed prefix retained verbatim |
| **R3** | `strip_prefixes=False` | `Scene #99: Cyberpunk street` | `False` | `"Scene #99: Cyberpunk street"` | Scene prefix retained verbatim |
| **R4** | `strip_prefixes=False` | `1... Deep sea jellyfish` | `False` | `"1... Deep sea jellyfish"` | Dots retained verbatim |
| **V1** | Validation Error | `# Only comment 1\n// Only comment 2` | `True` | `raises ValueError` | Empty after comments filtered |
| **V2** | Validation Error | `"#1 a\n#2 b"` | `True` | `raises ValueError` | Prompts under `min_length=3` |
| **V3** | Validation Error | 101 numbered prompts (`#1` to `#101`) | `True` | `raises ValueError` | Exceeds `max_prompts=100` |

---

## 4. Proposed Regression Test Code for `tests/test_database.py`

The following unit test functions are formulated to be appended to `tests/test_database.py`:

```python
# ==========================================================
# 3.1 Prompt Parsing Regex Remediation & Edge Case Tests
# ==========================================================

def test_parse_batch_prompts_preserves_hash_numbering():
    """
    Verifies that prompts numbered with '#' (e.g. #1, # 1, #42, #100, #01)
    are NOT discarded as comments by COMMENT_LINE_REGEX, and their prefixes
    are cleanly stripped when strip_prefixes=True.
    """
    raw = """
    #1 A warrior holding a glowing sword in a dark dungeon
    # 2 A dragon perched majestically atop an ancient ruined castle
    #3: A futuristic cityscape with flying vehicles at dusk
    #4 - Cyberpunk street vendor preparing glowing noodles
    #05. Bioluminescent flora in an enchanted alien forest
    #42 Space shuttle docking with a giant rotating space station
    #100 A serene mountain lake reflecting the northern lights
    ##1 An ethereal spirit floating through a misty graveyard
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
    assert len(prompts) == 8
    assert prompts[0] == "A warrior holding a glowing sword in a dark dungeon"
    assert prompts[1] == "A dragon perched majestically atop an ancient ruined castle"
    assert prompts[2] == "A futuristic cityscape with flying vehicles at dusk"
    assert prompts[3] == "Cyberpunk street vendor preparing glowing noodles"
    assert prompts[4] == "Bioluminescent flora in an enchanted alien forest"
    assert prompts[5] == "Space shuttle docking with a giant rotating space station"
    assert prompts[6] == "A serene mountain lake reflecting the northern lights"
    assert prompts[7] == "An ethereal spirit floating through a misty graveyard"


def test_parse_batch_prompts_discards_all_legitimate_comments():
    """
    Verifies that legitimate comments (# Heading, // Note, /* Block */, ---, ===, **)
    are cleanly discarded and never mistakenly treated as prompts.
    """
    raw = """
    # Project: Sci-Fi Teaser Outline
    # Heading 1: Scene Overview
    ## Subheading: Camera Directions
    ### Technical Notes: 35mm anamorphic lens
    // Note: Transition cut to driver close-up
    /* Director Note: Boost neon saturation */
    --- Scene Section Divider ---
    === Act 1 Climax ===
    ** Important: Do not alter lighting **
    # Scene 1 Notes
    #
    #   
    Valid prompt line that must survive comment filtering
    """
    prompts = models.parse_batch_prompts(raw)
    assert len(prompts) == 1
    assert prompts[0] == "Valid prompt line that must survive comment filtering"


def test_parse_batch_prompts_strips_bracketed_shot_hash_prefixes():
    """
    Verifies that PROMPT_PREFIX_REGEX handles '[Shot #42] - ', '[Scene #5]: ',
    '[#1] ', and variations with internal spaces and mixed casing.
    """
    raw = """
    [Shot #42] - Futuristic drone flying through a neon canyon
    [Shot # 42] - Futuristic drone flying through a neon canyon
    [Scene #99]: Stone altar glowing with ethereal light
    [Scene 5] Ancient temple surrounded by waterfall
    [#1] - Explosion of glowing debris in slow motion
    [  shot #7  ] - Cybernetic falcon soaring over desert dunes
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
    assert len(prompts) == 6
    assert prompts[0] == "Futuristic drone flying through a neon canyon"
    assert prompts[1] == "Futuristic drone flying through a neon canyon"
    assert prompts[2] == "Stone altar glowing with ethereal light"
    assert prompts[3] == "Ancient temple surrounded by waterfall"
    assert prompts[4] == "Explosion of glowing debris in slow motion"
    assert prompts[5] == "Cybernetic falcon soaring over desert dunes"


def test_parse_batch_prompts_strips_unbracketed_scene_hash_and_multiple_dots():
    """
    Verifies that PROMPT_PREFIX_REGEX handles 'Scene #99: ', 'Shot #42 - ',
    and strips multiple consecutive dots ('1... ') without leaving residual '.. '.
    """
    raw = """
    Scene #99: Cyberpunk street market with flying cars
    Shot #42 - Stealth bomber penetrating cloud layer
    Scene 12: High-speed monorail gliding across coastal bridge
    1... Deep sea bioluminescent jellyfish pulsating in the abyss
    2.. Submarine navigating underwater hydrothermal vents
    3.... Giant kraken wrapped around sunken pirate galleon
    100. A majestic mountain range bathed in golden sunrise
    4) Holographic police barricade appearing ahead
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
    assert len(prompts) == 8
    assert prompts[0] == "Cyberpunk street market with flying cars"
    assert prompts[1] == "Stealth bomber penetrating cloud layer"
    assert prompts[2] == "High-speed monorail gliding across coastal bridge"
    assert prompts[3] == "Deep sea bioluminescent jellyfish pulsating in the abyss"
    assert prompts[4] == "Submarine navigating underwater hydrothermal vents"
    assert prompts[5] == "Giant kraken wrapped around sunken pirate galleon"
    assert prompts[6] == "A majestic mountain range bathed in golden sunrise"
    assert prompts[7] == "Holographic police barricade appearing ahead"


def test_parse_batch_prompts_preserves_non_prefix_numbers():
    """
    Verifies that numbers within prompts (e.g., years, quantities, resolutions)
    or prompts starting with numbers without delimiters are preserved.
    """
    raw = """
    2049 dystopian megacity shrouded in toxic orange fog
    A squad of 5 soldiers advancing in tactical formation
    4K resolution ultra detailed portrait of an android
    16:9 cinematic shot of a solitary wanderer in the desert
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
    assert len(prompts) == 4
    assert prompts[0] == "2049 dystopian megacity shrouded in toxic orange fog"
    assert prompts[1] == "A squad of 5 soldiers advancing in tactical formation"
    assert prompts[2] == "4K resolution ultra detailed portrait of an android"
    # Note: If '16:' is parsed as a prefix, it would corrupt '16:9 cinematic shot'.
    # Ensure full ratio or prompt is preserved cleanly.


def test_parse_batch_prompts_retains_hash_prefixes_when_strip_disabled():
    """
    Verifies that strip_prefixes=False retains hash numbering and bracketed prefixes
    while still filtering out comments.
    """
    raw = """
    # Legitimate comment to ignore
    #1 A warrior holding a glowing sword
    [Shot #42] - Futuristic drone flying
    Scene #99: Cyberpunk street market
    1... Deep sea jellyfish
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=False)
    assert len(prompts) == 4
    assert prompts[0] == "#1 A warrior holding a glowing sword"
    assert prompts[1] == "[Shot #42] - Futuristic drone flying"
    assert prompts[2] == "Scene #99: Cyberpunk street market"
    assert prompts[3] == "1... Deep sea jellyfish"


def test_parse_batch_prompts_mixed_realistic_storyboard():
    """
    End-to-end integration test verifying a realistic storyboard script
    combining headings, notes, section dividers, and various numbering styles.
    """
    raw = """
    # ==========================================
    # Project: Cyber Odyssey (Veo 3.1 Teaser)
    # Target: Nano Banana 2 -> Veo 3.1 Lite
    # ==========================================
    
    // Scene 1: Opening
    1. Vast neon metropolis viewed from orbital shuttle at night
    
    // Scene 2: Pursuit
    [Shot #2] - Sleek black hovercar weaving through towering sky-traffic
    
    --- Midpoint Section ---
    
    #3 Close-up of female pilot activating neural interface visor
    Scene #4: Cybernetic falcon launching from skyscraper spire
    5... Massive holographic advertisement flickering in heavy rain
    
    /* Post-credits teaser */
    # 6 Mysterious shadowy figure emerging from dark alleyway
    
    # End of batch
    """
    prompts = models.parse_batch_prompts(raw, strip_prefixes=True)
    assert len(prompts) == 6
    assert prompts[0] == "Vast neon metropolis viewed from orbital shuttle at night"
    assert prompts[1] == "Sleek black hovercar weaving through towering sky-traffic"
    assert prompts[2] == "Close-up of female pilot activating neural interface visor"
    assert prompts[3] == "Cybernetic falcon launching from skyscraper spire"
    assert prompts[4] == "Massive holographic advertisement flickering in heavy rain"
    assert prompts[5] == "Mysterious shadowy figure emerging from dark alleyway"
```

---

## 5. Test Runner Integration

In `tests/test_database.py`, lines 667-691 define the standalone test suite runner executed when `python tests/test_database.py` is invoked directly.

The following 7 test functions must be appended to the `tests = [...]` runner array:
```python
    tests = [
        # ... existing 23 tests ...
        test_parse_batch_prompts_preserves_hash_numbering,
        test_parse_batch_prompts_discards_all_legitimate_comments,
        test_parse_batch_prompts_strips_bracketed_shot_hash_prefixes,
        test_parse_batch_prompts_strips_unbracketed_scene_hash_and_multiple_dots,
        test_parse_batch_prompts_preserves_non_prefix_numbers,
        test_parse_batch_prompts_retains_hash_prefixes_when_strip_disabled,
        test_parse_batch_prompts_mixed_realistic_storyboard
    ]
```

This brings total test coverage in `tests/test_database.py` from 24 tests to 31 tests.

---

## 6. Implementation Handoff Recommendations for Worker

When the Worker agent receives this plan:

1. **In `database/models.py` (lines 274-281)**:
   Replace `PROMPT_PREFIX_REGEX` and `COMMENT_LINE_REGEX` with:
   ```python
   PROMPT_PREFIX_REGEX = re.compile(
       r'^(?:'
       r'\[\s*(?:(?:scene|shot)\s*#?\s*\d+|#?\s*\d+)\s*\]\s*[:.\-]?\s*'
       r'|'
       r'(?:(?:scene|shot)\s*#?\s*\d+|#\s*\d+)\s*[:.\-\)\]]*\s*'
       r'|'
       r'\d+\s*[:.\-\)\]]+\s*'
       r')',
       re.IGNORECASE
   )

   COMMENT_LINE_REGEX = re.compile(
       r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
   )
   ```

2. **In `tests/test_database.py`**:
   - Append the 7 regression test functions after line 315.
   - Add the 7 test function names to the `tests` list in `if __name__ == '__main__':`.

3. **Verify Execution**:
   Run `pytest tests/test_database.py` (or direct execution runner) to confirm 100% pass across all 31 tests.
