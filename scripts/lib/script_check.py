#!/usr/bin/env python3
"""Script-graded expectations for /bench skill: an executable check in place of the judge.

An expectation written as {"text": ..., "check": [argv...]} is met when its check exits 0 and not
met when it exits 1. The check reads the arm's reply on stdin and finds it again at
$BENCH_OUTPUT_FILE (for tools that want a path). It runs in a fresh empty temp dir with a timeout
and the parent session detached, and the dir is deleted after. Nothing more is isolated: a check
that runs model-written code owns any deeper sandbox (wrap it in docker, say). Any other exit, a
timeout, or a check that will not launch is a CheckError: the cell is recorded and excluded, never
scored as not met, the same rule the judge's failures follow. An executable check has no family
bias at all (skills/bench/references/empirical-evals.md, "Mechanize first").
"""
import os, shutil, subprocess, tempfile
from hermetic_driver import detached_env


class CheckError(RuntimeError):
    pass


def check_of(expectation):
    """Pure: the check argv of an expectation, or None when the judge grades it."""
    return expectation.get("check") if isinstance(expectation, dict) else None


def text_of(expectation):
    """Pure: the expectation's text, whether it is a bare string or a {"text": ...} object."""
    return expectation.get("text", "") if isinstance(expectation, dict) else expectation


def run_check(argv, output, timeout=120):
    """Run one check against an arm's reply -> True (exit 0) / False (exit 1); else CheckError."""
    d = tempfile.mkdtemp(prefix="bench-check-")
    try:
        path = os.path.join(d, "output.txt")
        with open(path, "w") as f:
            f.write(output)
        env = {**detached_env(), "BENCH_OUTPUT_FILE": path}
        try:
            r = subprocess.run(argv, input=output, capture_output=True, text=True,
                               timeout=timeout, cwd=d, env=env)
        except subprocess.TimeoutExpired:
            raise CheckError(f"check {argv[0]} timeout after {timeout}s")
        except OSError as e:
            raise CheckError(f"check did not launch: {e}")
        if r.returncode in (0, 1):
            return r.returncode == 0
        raise CheckError(f"check {argv[0]} exit {r.returncode} (0 = met, 1 = not met): "
                         f"{(r.stderr or r.stdout).strip()[-200:]}")
    finally:
        shutil.rmtree(d, ignore_errors=True)
