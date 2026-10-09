"""
Adversarial Test Harness for M1: Database Architecture, Schema Migrations & Core Data Models
Focus Areas:
1. Adversarial Prompt Parsing:
   - Strange numbering prefixes ("100. ", "Scene 99: ", "[Shot #42] - ", multiple dots)
   - Unicode variations (CJK, Arabic, Vietnamese, Emoji, Zero-width spaces)
   - Linebreak normalization (\r, \r\n, mixed)
   - Extreme batch sizes (0, 1, 100, 101, oversized length)
   - SQL injection vectors in prompt text
2. Cooldown Boundary Conditions:
   - Clock skew (past/future mock times)
   - Negative cooldown durations and timestamps
   - Infinity (inf, -inf) and NaN behavior
   - Sub-millisecond float precision and exact boundary comparison
3. Priority Boundaries:
   - Negative priorities (-1, -100, -2147483648)
   - Extreme large priorities (10^6, 2^31-1, 2^63-1)
   - Priority ties and FIFO order preservation (created_at ASC)
   - Dynamic priority adjustments
"""

import os
import sys
import time
import math
import sqlite3
import tempfile
import traceback

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from database import db, models

class TestFailure(Exception):
    pass

def assert_equal(actual, expected, msg=""):
    if actual != expected:
        raise TestFailure(f"{msg} -> Expected {expected!r}, got {actual!r}")

def assert_true(cond, msg=""):
    if not cond:
        raise TestFailure(f"{msg} -> Condition was False")

def assert_raises(exc_type, func, *args, **kwargs):
    try:
        func(*args, **kwargs)
    except exc_type:
        return
    except Exception as e:
        raise TestFailure(f"Expected exception {exc_type.__name__}, but got {type(e).__name__}: {e}")
    raise TestFailure(f"Expected exception {exc_type.__name__}, but no exception was raised.")

def run_all_tests():
    results = {"passed": 0, "failed": 0, "failures": []}
    
    def execute(name, fn):
        print(f"[*] Running: {name} ...", end=" ")
        try:
            fn()
            print("PASS")
            results["passed"] += 1
        except Exception as e:
            print("FAIL")
            results["failed"] += 1
            results["failures"].append((name, str(e), traceback.format_exc()))

    # Temporary database fixture
    temp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(temp_dir, "adversarial_m1_test.db")
    import config
    config.DB_PATH = test_db_path
    db.init_db(test_db_path)

    # -------------------------------------------------------------
    # SECTION 1: Adversarial Prompt Parsing Tests
    # -------------------------------------------------------------

    def test_prompt_numbering_prefixes():
        # "100. "
        p100 = models.parse_batch_prompts("100. A majestic mountain range at sunset")[0]
        assert_equal(p100, "A majestic mountain range at sunset", "Failed to strip '100. '")
        
        # "Scene 99: "
        p99 = models.parse_batch_prompts("Scene 99: Cyberpunk street market with flying cars")[0]
        assert_equal(p99, "Cyberpunk street market with flying cars", "Failed to strip 'Scene 99: '")

        # "[Shot #42] - " -> Challenge: does it handle '#' in prefix?
        try:
            p_shot42 = models.parse_batch_prompts("[Shot #42] - Futuristic drone flying through a neon canyon")[0]
            assert_equal(p_shot42, "Futuristic drone flying through a neon canyon", "Failed to strip '[Shot #42] - '")
        except TestFailure as tf:
            raise tf

        # Multiple dots ("1... ")
        try:
            p_dots = models.parse_batch_prompts("1... Deep sea bioluminescent jellyfish")[0]
            assert_equal(p_dots, "Deep sea bioluminescent jellyfish", "Failed to strip multiple dots '1... '")
        except TestFailure as tf:
            raise tf

        # Multiple numbering ("1.1. ")
        try:
            p_multinum = models.parse_batch_prompts("1.1. Space shuttle launching into the cosmos")[0]
            assert_equal(p_multinum, "Space shuttle launching into the cosmos", "Failed to strip '1.1. '")
        except TestFailure as tf:
            raise tf

    execute("Prompt Numbering Prefixes ('100. ', 'Scene 99: ', '[Shot #42] - ', multiple dots)", test_prompt_numbering_prefixes)

    def test_prompt_hash_numbering_vs_comments():
        # What if a user numbers prompts as "#1 Prompt" vs a comment?
        # A prompt starting with "#1 Prompt":
        # Does COMMENT_LINE_REGEX eat "#1 Prompt"?
        raw = "#1 A warrior holding a glowing sword\n#2 A dragon perched on a castle"
        try:
            prompts = models.parse_batch_prompts(raw)
            # If prompts are parsed, verify content
            assert_equal(len(prompts), 2, "Expected 2 prompts from '#1 ...' and '#2 ...'")
        except ValueError as ve:
            raise TestFailure(f"Prompt starting with '#1' was mistakenly treated as comment and discarded: {ve}")

    execute("Prompt Hash Numbering ('#1 Prompt' vs comment lines)", test_prompt_hash_numbering_vs_comments)

    def test_prompt_unicode_handling():
        # Vietnamese with tones, Japanese Kanji/Kana, Chinese, Arabic (RTL), Emoji
        raw_unicode = (
            "1. Đạo diễn Hoàng hôn tuyệt đẹp trên bãi biển Nha Trang với sóng vỗ rì rào 🌊\n"
            "Scene 2: 東京の夜景、ネオン街を歩くサイボーグ少女 🌸\n"
            "3. 故宫雪景，红墙白雪，金顶辉煌，电影级光影 🏮\n"
            "4) مشهد سينمائي لمدينة مستقبلية في الصحراء وقت الغروب 🐪\n"
            "5. Quantum portal emitting ✨✨ glowing particles and cosmic nebulae 🚀"
        )
        prompts = models.parse_batch_prompts(raw_unicode)
        assert_equal(len(prompts), 5, "Unicode batch prompt count mismatch")
        assert_true("🌊" in prompts[0], "Emoji preserved in prompt 1")
        assert_true("東京" in prompts[1], "Japanese characters preserved in prompt 2")
        assert_true("故宫" in prompts[2], "Chinese characters preserved in prompt 3")
        assert_true("مشهد" in prompts[3], "Arabic characters preserved in prompt 4")

        # Test storing unicode prompts in SQLite
        batch_id = models.create_prompt_batch("Unicode Batch", raw_unicode, media_type="image")
        scenes = models.get_scenes_by_project("Default")
        assert_true(len(scenes) >= 5, "Scenes not created for unicode batch")
        db_prompt = scenes[-5]['prompt'] # one of the created prompts
        assert_true(any("🌊" in s['prompt'] for s in scenes), "Emoji not preserved in SQLite scene prompt")

    execute("Prompt Unicode Handling (Vietnamese, CJK, Arabic RTL, Emoji)", test_prompt_unicode_handling)

    def test_prompt_weird_linebreaks():
        # \r (old Mac), \r\n (Windows), \n (Unix), mixed
        raw_mixed = "Line one: prompt 1\rLine two: prompt 2\r\nLine three: prompt 3\n\r\nLine four: prompt 4\r\rLine five: prompt 5"
        prompts = models.parse_batch_prompts(raw_mixed)
        assert_equal(len(prompts), 5, "Weird linebreaks failed to normalize properly")

    execute("Prompt Linebreaks Normalization (\\r, \\r\\n, mixed)", test_prompt_weird_linebreaks)

    def test_prompt_extreme_batch_sizes_and_lengths():
        # Empty string
        assert_raises(ValueError, models.parse_batch_prompts, "")
        # Whitespace only
        assert_raises(ValueError, models.parse_batch_prompts, "   \t  \n  \r\n  ")
        # Exactly 1 prompt
        p1 = models.parse_batch_prompts("A single valid prompt for testing")
        assert_equal(len(p1), 1)

        # Batch with 100 prompts (max allowed default)
        text_100 = "\n".join([f"Prompt number {i:03d} for testing batch capacity" for i in range(100)])
        p100 = models.parse_batch_prompts(text_100, max_prompts=100)
        assert_equal(len(p100), 100)

        # Batch with 101 prompts (exceeding default limit)
        text_101 = "\n".join([f"Prompt number {i:03d} for testing overflow" for i in range(101)])
        assert_raises(ValueError, models.parse_batch_prompts, text_101, max_prompts=100)

        # Truncation of prompt exceeding max_length (e.g. 2000 chars)
        long_prompt = "A" * 2000
        parsed_long = models.parse_batch_prompts(long_prompt, max_length=1500)
        assert_equal(len(parsed_long[0]), 1500, "Prompt was not clamped to max_length")

        # Short prompt under min_length (e.g. 2 chars) should be ignored
        short_and_good = "Ab\nA valid prompt line here"
        p_short = models.parse_batch_prompts(short_and_good, min_length=3)
        assert_equal(len(p_short), 1)
        assert_equal(p_short[0], "A valid prompt line here")

    execute("Prompt Extreme Batch Sizes and Length Limits", test_prompt_extreme_batch_sizes_and_lengths)

    def test_prompt_sql_injection_resistance():
        # Highly adversarial SQL injection vectors in prompt text
        sqli_prompts = (
            "'); DROP TABLE accounts; --\n"
            "' OR '1'='1' UNION SELECT id, name, email FROM accounts --\n"
            "'; UPDATE jobs SET priority = 999 WHERE 1=1; --\n"
            "\" OR \"\"=\"\n"
            "<script>alert('XSS')</script> -- SQLite text payload"
        )
        batch_id = models.create_prompt_batch(
            name="SQLi Test Batch",
            text=sqli_prompts,
            media_type="image",
            project_id="SQLi_Proj"
        )
        assert_true(isinstance(batch_id, int) and batch_id > 0)
        
        # Verify accounts table still exists and is untouched
        accounts = models.get_all_accounts()
        assert_true(len(accounts) >= 2, "Accounts table was compromised by SQL injection!")

        # Verify prompt text is stored exactly as entered without evaluation
        pending = models.get_pending_jobs(media_type="image")
        prompts_stored = [j['prompt'] for j in pending if j['batch_id'] == batch_id]
        assert_equal(len(prompts_stored), 5)
        assert_true("'); DROP TABLE accounts; --" in prompts_stored)
        assert_true("' OR '1'='1' UNION SELECT id, name, email FROM accounts --" in prompts_stored)

    execute("Prompt SQL Injection Resistance (Parameterized Queries)", test_prompt_sql_injection_resistance)

    # -------------------------------------------------------------
    # SECTION 2: Cooldown Boundary Conditions Tests
    # -------------------------------------------------------------

    def test_cooldown_boundary_and_precision():
        # Microsecond precision: 2000.000001 vs 2000.000002
        acc_id = models.save_account({
            'id': 'acc_precision',
            'name': 'Precision Acc',
            'email': 'prec@test.com',
            'profile_path': 'p',
            'status': 'ACTIVE',
            'health_status': 'READY',
            'cooldown_until': 2000.000005
        })
        acc = models.get_account_by_id(acc_id)
        
        # Exact boundary check: cooldown_until <= now
        # 1 microsecond before: NOT ready
        assert_true(not models.is_account_ready(acc, current_time=2000.000004), "Should NOT be ready before boundary")
        # Exact boundary: READY
        assert_true(models.is_account_ready(acc, current_time=2000.000005), "Should be ready at exact boundary")
        # 1 microsecond after: READY
        assert_true(models.is_account_ready(acc, current_time=2000.000006), "Should be ready after boundary")

    execute("Cooldown Boundary & Microsecond Precision", test_cooldown_boundary_and_precision)

    def test_cooldown_negative_values():
        # What if negative cooldown duration or negative timestamp is set?
        acc_id = models.save_account({
            'id': 'acc_neg_cd',
            'name': 'Neg Acc',
            'email': 'neg@test.com',
            'profile_path': 'p',
            'status': 'ACTIVE',
            'health_status': 'READY',
            'cooldown_until': -100.0
        })
        acc = models.get_account_by_id(acc_id)
        # Negative timestamp is in the distant past (1969 epoch), so account must be ready now
        assert_true(models.is_account_ready(acc, current_time=100.0), "Account with negative cooldown_until should be ready")

        # set_account_cooldown with negative seconds
        # e.g., cooldown_seconds = -5.0 -> target = time.time() - 5.0 (in the past)
        target = models.set_account_cooldown(acc_id, -5.0)
        assert_true(target < time.time(), "Negative cooldown target should be in the past")
        updated_acc = models.get_account_by_id(acc_id)
        assert_true(models.is_account_ready(updated_acc), "Account with negative cooldown duration should be immediately ready")

    execute("Cooldown Negative Values & Durations", test_cooldown_negative_values)

    def test_cooldown_infinity_and_nan():
        # Setting cooldown to +infinity should mean the account NEVER becomes ready
        acc_id = models.save_account({
            'id': 'acc_inf',
            'name': 'Inf Acc',
            'email': 'inf@test.com',
            'profile_path': 'p',
            'status': 'ACTIVE',
            'health_status': 'READY',
            'cooldown_until': float('inf')
        })
        acc = models.get_account_by_id(acc_id)
        assert_true(not models.is_account_ready(acc, current_time=1e12), "Account with +inf cooldown should NEVER be ready")
        
        # Test SQLite query with +inf
        avail = models.get_available_accounts(current_time=1e12)
        assert_true(acc_id not in [a['id'] for a in avail], "+inf account must not be selected by get_available_accounts")

        # Setting cooldown to -infinity: should be immediately ready
        models.update_account_status(acc_id, cooldown_until=float('-inf'))
        acc_neg = models.get_account_by_id(acc_id)
        assert_true(models.is_account_ready(acc_neg, current_time=0.0), "Account with -inf cooldown should be ready")

        # NaN cooldown handling
        models.update_account_status(acc_id, cooldown_until=float('nan'))
        acc_nan = models.get_account_by_id(acc_id)
        # In Python and IEEE 754: nan <= x is always False
        assert_true(not models.is_account_ready(acc_nan, current_time=1e9), "Account with NaN cooldown must NOT be ready")

    execute("Cooldown Infinity (+inf, -inf) and NaN Boundaries", test_cooldown_infinity_and_nan)

    def test_cooldown_clock_skew_simulation():
        # Scenario: Clock jumps backward by 1 hour (3600 seconds)
        # Job completed at t = 5000, cooldown 60s -> cooldown_until = 5060
        acc_id = models.save_account({
            'id': 'acc_skew',
            'name': 'Skew Acc',
            'email': 'skew@test.com',
            'profile_path': 'p',
            'status': 'ACTIVE',
            'health_status': 'READY',
            'cooldown_until': 5060.0
        })
        acc = models.get_account_by_id(acc_id)
        
        # Clock shifts backward to t = 4000:
        assert_true(not models.is_account_ready(acc, current_time=4000.0), "Under backward clock skew, cooldown must not expire prematurely")
        
        # Clock shifts forward to t = 6000:
        assert_true(models.is_account_ready(acc, current_time=6000.0), "Under forward clock skew, cooldown naturally expires")

    execute("Cooldown Clock Skew Simulation (Past/Future Drift)", test_cooldown_clock_skew_simulation)

    # -------------------------------------------------------------
    # SECTION 3: Priority Boundaries Tests
    # -------------------------------------------------------------

    def test_priority_negative_and_extreme_values():
        # Clear existing jobs
        for j in models.get_all_jobs(500):
            models.delete_job(j['id'])
            
        # Add jobs with negative priorities, 0, high priorities, extreme 64-bit priorities
        p_extremes = [
            ("j_neg_huge", -2147483648, "2026-01-01T00:00:01"),
            ("j_neg_one", -1, "2026-01-01T00:00:02"),
            ("j_zero", 0, "2026-01-01T00:00:03"),
            ("j_ten", 10, "2026-01-01T00:00:04"),
            ("j_thousand", 1000, "2026-01-01T00:00:05"),
            ("j_max_int32", 2147483647, "2026-01-01T00:00:06"),
            ("j_huge_int64", 9223372036854775807, "2026-01-01T00:00:07")
        ]
        
        for jid, prio, created in p_extremes:
            models.add_job({
                'id': jid,
                'media_type': 'image',
                'prompt': f'Prompt {jid}',
                'priority': prio,
                'created_at': created
            })
            
        pending = models.get_pending_jobs(priority_first=True)
        assert_equal(len(pending), len(p_extremes), "Not all extreme priority jobs retrieved")
        
        # Order should be strictly descending priority:
        expected_order = [
            "j_huge_int64",
            "j_max_int32",
            "j_thousand",
            "j_ten",
            "j_zero",
            "j_neg_one",
            "j_neg_huge"
        ]
        actual_order = [j['id'] for j in pending]
        assert_equal(actual_order, expected_order, "Priority queue ordering failed on extreme values")

    execute("Priority Extreme Values (-2^31, 0, 10, 2^31-1, 2^63-1)", test_priority_negative_and_extreme_values)

    def test_priority_ties_fifo_preservation():
        # Clear existing jobs
        for j in models.get_all_jobs(500):
            models.delete_job(j['id'])

        # Add 5 jobs with identical priority 10, but sequential timestamps
        for i in range(1, 6):
            models.add_job({
                'id': f'job_tie_{i}',
                'media_type': 'video',
                'prompt': f'Prompt tie {i}',
                'priority': 10,
                'created_at': f'2026-01-01T12:00:0{i}'
            })

        pending = models.get_pending_jobs(priority_first=True)
        tie_order = [j['id'] for j in pending]
        expected_fifo = [f'job_tie_{i}' for i in range(1, 6)]
        assert_equal(tie_order, expected_fifo, "FIFO order broken on priority ties")

        # Atomic claim must claim exactly in FIFO order
        for i in range(1, 6):
            claimed = models.claim_next_job(account_id="acc_tie_worker")
            assert_true(claimed is not None, f"Failed to claim job {i}")
            assert_equal(claimed['id'], f'job_tie_{i}', f"Claimed job out of FIFO order at step {i}")

    execute("Priority Ties FIFO Preservation (created_at ASC)", test_priority_ties_fifo_preservation)

    def test_dynamic_reprioritization():
        # Clear existing jobs
        for j in models.get_all_jobs(500):
            models.delete_job(j['id'])

        models.add_job({'id': 'job_a', 'media_type': 'image', 'prompt': 'Job A', 'priority': 0, 'created_at': '2026-01-01T00:00:01'})
        models.add_job({'id': 'job_b', 'media_type': 'image', 'prompt': 'Job B', 'priority': 0, 'created_at': '2026-01-01T00:00:02'})

        # Initially Job A comes before Job B (FIFO)
        assert_equal(models.get_pending_jobs()[0]['id'], 'job_a')

        # Elevate Job B to priority 50
        models.set_job_priority('job_b', 50)
        assert_equal(models.get_pending_jobs()[0]['id'], 'job_b')

        # Demote Job B to -10
        models.set_job_priority('job_b', -10)
        assert_equal(models.get_pending_jobs()[0]['id'], 'job_a')
        assert_equal(models.get_pending_jobs()[1]['id'], 'job_b')

    execute("Dynamic Job Reprioritization (set_job_priority)", test_dynamic_reprioritization)

    # -------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------
    print("\n=======================================================")
    print(f"ADVERSARIAL HARNESS SUMMARY: {results['passed']} Passed, {results['failed']} Failed")
    print("=======================================================")
    if results["failures"]:
        print("\nFAILURES ENCOUNTERED:")
        for name, err, tb in results["failures"]:
            print(f"[-] {name}: {err}")
            # print(tb)
    return results

if __name__ == "__main__":
    res = run_all_tests()
    sys.exit(0 if res["failed"] == 0 else 1)
