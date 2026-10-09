"""
Empirical Verification of Regular Expression Edge Cases in database/models.py
Demonstrating exact failure modes for:
1. "[Shot #42] - "
2. "Scene #99: "
3. "1... " (multiple dots)
4. "#1 Prompt" (treated as comment)
"""

import re

# Worker M1's exact regexes from database/models.py lines 274-281:
WORKER_PROMPT_PREFIX_REGEX = re.compile(
    r'^(?:\[\s*(?:scene\s*\d+|shot\s*\d+|\d+)\s*\]\s*[-:]?\s*|(?:scene\s*\d+|shot\s*\d+|\d+)\s*[:.\-\)\]]\s*)',
    re.IGNORECASE
)

WORKER_COMMENT_LINE_REGEX = re.compile(
    r'^(?:#|//|/\*|---|===|\*\*)'
)

# Proposed Hardened Regexes:
FIXED_PROMPT_PREFIX_REGEX = re.compile(
    r'^(?:\[\s*(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*\]\s*[-:]?\s*|(?:scene\s*#?\s*\d+|shot\s*#?\s*\d+|#?\s*\d+)\s*[:.\-\)\]]+\s*)',
    re.IGNORECASE
)

# Comment regex that does not treat "#1" or "# 1" prompt numbering as a comment
FIXED_COMMENT_LINE_REGEX = re.compile(
    r'^(?:#(?!\s*#?\d)|//|/\*|---|===|\*\*)'
)

def test_case(name, input_text, expected_cleaned):
    # Worker M1 regex test
    is_comment = bool(WORKER_COMMENT_LINE_REGEX.match(input_text))
    if is_comment:
        worker_res = "[DISCARDED_AS_COMMENT]"
    else:
        worker_res = WORKER_PROMPT_PREFIX_REGEX.sub('', input_text).strip()
        
    # Fixed regex test
    is_comment_fixed = bool(FIXED_COMMENT_LINE_REGEX.match(input_text))
    if is_comment_fixed:
        fixed_res = "[DISCARDED_AS_COMMENT]"
    else:
        fixed_res = FIXED_PROMPT_PREFIX_REGEX.sub('', input_text).strip()
        
    print(f"Test: {name}")
    print(f"  Input:    {input_text!r}")
    print(f"  Worker:   {worker_res!r}  --> {'PASS' if worker_res == expected_cleaned else 'FAIL'}")
    print(f"  Fixed:    {fixed_res!r}   --> {'PASS' if fixed_res == expected_cleaned else 'FAIL'}")
    print()

if __name__ == "__main__":
    print("=== EMPIRICAL REGEX VERIFICATION ===")
    test_case("100. prefix", "100. A majestic mountain", "A majestic mountain")
    test_case("Scene 99: prefix", "Scene 99: Cyberpunk street", "Cyberpunk street")
    test_case("[Shot #42] - prefix", "[Shot #42] - Drone flying", "Drone flying")
    test_case("Scene #99: prefix", "Scene #99: Neon alley", "Neon alley")
    test_case("Multiple dots 1... ", "1... Deep sea jellyfish", "Deep sea jellyfish")
    test_case("Hash prompt numbering #1", "#1 A medieval knight", "A medieval knight")
    test_case("Legitimate # comment", "# This is a section title", "[DISCARDED_AS_COMMENT]")
