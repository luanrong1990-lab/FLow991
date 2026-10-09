## 2026-09-08T04:02:26Z

You are teamwork_preview_worker_m1_remediate, an implementation engineer.
Your working directory is: d:/New folder (5)/.agents/teamwork_preview_worker_m1_remediate
Project root is: d:/New folder (5)

MANDATORY INTEGRITY WARNING:
DO NOT CHEAT. All implementations must be genuine. DO NOT hardcode test results, create dummy/facade implementations, or circumvent the intended task. A teamwork_preview_auditor will independently verify your work. Integrity violations WILL be detected and your work WILL be rejected.

MANDATORY: Read ORIGINAL_REQUEST.md at: d:/New folder (5)/ORIGINAL_REQUEST.md immediately.
Read PROJECT.md at: d:/New folder (5)/PROJECT.md.

Milestone M1: Prompt Regex Remediation
Exclusive Write Ownership:
- database/models.py
- tests/test_database.py

Implementation Steps:
1. In database/models.py (lines 274-281):
   Use replace_file_content to update PROMPT_PREFIX_REGEX and COMMENT_LINE_REGEX to:
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
2. In tests/test_database.py:
   Use replace_file_content to add test_parse_batch_prompts_adversarial_prefixes_and_hash_numbering() verifying:
   - '[Shot #42] - ' -> stripped cleanly
   - 'Scene #99: ' -> stripped cleanly
   - '1... ' -> stripped without trailing dots
   - '1.1. ' -> stripped hierarchical prefix
   - '#1 Prompt' -> preserved and prefix stripped
   - '#2: Prompt' and '#3 - Prompt' -> preserved and prefix stripped
   - '3 cats playing in garden' -> preserved intact
   - '# Comment title' -> discarded as comment
   Register the new test in the runner list.
3. Run tests using run_command:
   - python tests/test_database.py
   - python .agents/teamwork_preview_challenger_m1_2/verify_regex_empirical.py
   Ensure WaitMsBeforeAsync=10000.
4. Deliver your handoff report to d:/New folder (5)/.agents/teamwork_preview_worker_m1_remediate/handoff.md.
