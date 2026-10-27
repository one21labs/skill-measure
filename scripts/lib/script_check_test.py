#!/usr/bin/env python3
"""Tests for script_check.py: real /bin/sh checks, no CLI or network."""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(__file__))
import script_check as sc  # noqa: E402


def sh(script):
    return ["/bin/sh", "-c", script]


class TestScriptCheck(unittest.TestCase):
    def test_exit_0_is_met_and_exit_1_is_not(self):
        self.assertIs(sc.run_check(sh("grep -q answer"), "the answer is 42"), True)
        self.assertIs(sc.run_check(sh("grep -q answer"), "no idea"), False)

    def test_reply_arrives_on_stdin_and_at_the_output_file(self):
        self.assertTrue(sc.run_check(sh('[ "$(cat)" = "$(cat "$BENCH_OUTPUT_FILE")" ]'), "x\ny"))

    def test_runs_in_a_fresh_dir_that_is_removed_after(self):
        seen = []
        orig = sc.subprocess.run

        def spy(argv, **kw):
            seen.append(kw["cwd"])
            return orig(argv, **kw)
        sc.subprocess.run = spy
        try:
            self.assertTrue(sc.run_check(sh('[ "$(ls)" = output.txt ]'), "x"))
        finally:
            sc.subprocess.run = orig
        self.assertFalse(os.path.exists(seen[0]))

    def test_any_other_outcome_is_an_error_never_not_met(self):
        # A broken check is not evidence the arm missed the expectation.
        for argv, kw in ((sh("echo boom >&2; exit 2"), {}), (sh("sleep 5"), {"timeout": 0.2}),
                         (["/nonexistent/check"], {})):
            with self.assertRaises(sc.CheckError, msg=argv):
                sc.run_check(argv, "x", **kw)
        with self.assertRaises(sc.CheckError) as ctx:
            sc.run_check(sh("echo boom >&2; exit 2"), "x")
        self.assertIn("boom", str(ctx.exception))

    def test_check_of_and_text_of_read_both_expectation_shapes(self):
        self.assertIsNone(sc.check_of("plain"))
        self.assertIsNone(sc.check_of({"text": "judged"}))
        self.assertEqual(sc.check_of({"text": "t", "check": ["c"]}), ["c"])
        self.assertEqual(sc.text_of("plain"), "plain")
        self.assertEqual(sc.text_of({"text": "t", "check": ["c"]}), "t")


if __name__ == "__main__":
    unittest.main()
