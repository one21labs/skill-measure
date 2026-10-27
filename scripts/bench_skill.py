#!/usr/bin/env python3
"""/bench-skill — paired with/without value benchmark for a skill, cross-family judged (ADR 0055).

Generate each eval task under two arms (skill-loaded vs bare) via the rented substrate, grade each
output against pre-registered expectations with the cross-family judge, and report the with-without
fraction-met delta + KEEP/CUT verdict (ADR 0025 shape). Reuses benchstats for the math.

Eval file: JSON list of {"id","task","expectations":[...]}. An expectation is a string the judge
grades, or {"text", "check": [argv...]} that a script grades instead (lib/script_check.py). Arms: {"with":[argv...],"without":[argv...]}
where the task text is appended as the final CLI arg. Substrate + judge are injected so the
orchestration core (grade_all/aggregate) is unit-testable offline (see bench_skill_test.py).

Prints a cost estimate and refuses to spend without --yes (the refusal ADR 0016 made the
condition for /bench being model-invocable at all).
"""
import argparse, json, os, re, sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lib"))
import rubric, benchstats  # noqa: E402
from judge import make_judge, met_map, JudgeError, BACKENDS  # noqa: E402
from substrate import make_substrate  # noqa: E402
from spend_guard import add_spend_flag, require_yes  # noqa: E402
from bench_io import report_json  # noqa: E402
from script_check import CheckError, check_of, text_of, run_check  # noqa: E402


def grade_all(gen_rows, evals_by_id, judge, run_check=run_check):
    """gen_rows: [{prompt_id, arm, output[, error]}] -> (cells: [{bid, arm, scenario, met}], errors).
    Expectations with a "check" are graded by their script, run first; the judge sees only the
    rest, renumbered 1..k, and is not called when there are none. A generation that failed (row
    carries "error") or a cell its judge or a check cannot grade is recorded in errors and
    EXCLUDED, never graded: scoring it would charge a CLI, judge, or check failure to the arm, and
    one bad call must not end the run."""
    cells, errs = [], []
    for r in gen_rows:
        ev = evals_by_id[r["prompt_id"]]
        exps = ev["expectations"]
        bid = f'{ev["id"]}:{r["arm"]}:r{r.get("rep", 1)}'
        if r.get("error"):
            errs.append({"bid": bid, "error": "generation: " + r["error"][:200]})
            continue
        judged = [i for i, e in enumerate(exps, 1) if not check_of(e)]
        try:
            met = {i: run_check(check_of(e), r["output"])
                   for i, e in enumerate(exps, 1) if check_of(e)}
            if judged:
                m = met_map(judge.grade(rubric.skill_grade_prompt(
                    ev["task"], r["output"], [text_of(exps[i - 1]) for i in judged]),
                    rubric.GRADE_SCHEMA), len(judged))  # strict met_map: exactly ids 1..k
                met.update({i: m[k] for k, i in enumerate(judged, 1)})
        except (JudgeError, CheckError) as e:  # parse_reply makes a non-JSON reply a JudgeError
            errs.append({"bid": bid, "error": str(e)[:200]})
            continue
        met = {i: met[i] for i in range(1, len(exps) + 1)}
        cells.append({"bid": bid, "arm": r["arm"], "scenario": str(ev["id"]), "met": met})
    return cells, errs


PATH_FLAG = re.compile(r"(dir|file|path|settings|config)$")
FILE_EXT = re.compile(r"\.[A-Za-z]\w*$")  # cfg.json, notes.md; not a version like 4.5


def relative_path_args(argv):
    """The args of an arm argv that only resolve from the caller's cwd. Arms run from an empty
    temp dir (NativeSubstrate), where these silently miss (the skill not loaded) or fail to
    launch. argv[0] resolves through PATH, so only a slash makes it cwd-relative. A later arg,
    or the value of `--flag=value`, counts when it exists here and looks like a path: it has a
    slash, starts with `.`, ends in a file extension (`-c cfg.json`), or follows a flag named like
    a path (`--plugin-dir myplug`); a plain option value such as `--model sonnet` never does."""
    out = []
    for i, a in enumerate(argv):
        if i == 0:
            if "/" in a and not os.path.isabs(a):
                out.append(a)
            continue
        flag, val = (a.split("=", 1) if a.startswith("-") and "=" in a else (argv[i - 1], a))
        pathlike = ("/" in val or val.startswith(".") or FILE_EXT.search(val)
                    or PATH_FLAG.search(flag.lstrip("-")))
        if val and not os.path.isabs(val) and os.path.exists(val) and pathlike:
            out.append(a)
    return out


LOCKDOWN_FLAGS = ("--disable-slash-commands", "--strict-mcp-config")
USER_CONTEXT_FILES = ("settings.json", "CLAUDE.md")


def config_dir_of(argv, environ=os.environ):
    """The CLAUDE_CONFIG_DIR an arm runs under: an `env CLAUDE_CONFIG_DIR=...` prefix in its argv
    (the first non-assignment ends env's prefix), else the caller's (substrate.arm_env)."""
    if argv and os.path.basename(argv[0]) == "env":
        for a in argv[1:]:
            if "=" not in a:
                break
            if a.startswith("CLAUDE_CONFIG_DIR="):
                return a.split("=", 1)[1]
    return environ.get("CLAUDE_CONFIG_DIR")


def lockdown_gaps(arms, environ=os.environ):
    """Why the arms may not be isolated from the caller's own setup; [] when they match the
    SKILL.md recipe. A credentials-only CLAUDE_CONFIG_DIR alone is not enough: the CLI syncs
    account plugins and skills into it on first use, so each arm also needs LOCKDOWN_FLAGS.
    Checks the recipe, not the outcome — a warning, never a refusal (one21labs/skill-measure#1)."""
    gaps = []
    for arm in arms:
        missing = [f for f in LOCKDOWN_FLAGS if f not in arm["cmd"]]
        if missing:
            gaps.append(f"{arm['name']} arm lacks {' '.join(missing)}")
    dirs = {arm["name"]: config_dir_of(arm["cmd"], environ) for arm in arms}
    if None in dirs.values():
        gaps.append("CLAUDE_CONFIG_DIR unset for an arm: it reads your own ~/.claude")
    elif len(set(dirs.values())) > 1:
        gaps.append(f"arms use different CLAUDE_CONFIG_DIRs: {dirs}")
    else:
        d = next(iter(dirs.values()))
        found = [f for f in USER_CONTEXT_FILES if os.path.exists(os.path.join(d, f))]
        if found:
            gaps.append(f"CLAUDE_CONFIG_DIR {d} holds {found}, which every arm loads")
    return gaps


def aggregate(cells, with_arm="with", without_arm="without", practical=0.0):
    delta = benchstats.clustered_delta(cells, with_arm, without_arm)
    # matched-scenario, scenario-weighted: these subtract to the verdict's mean
    return {"arm_means": {a: round(v, 3) for a, v in delta["arm_means"].items()},
            "with_minus_without": benchstats.keep_verdict(delta, practical),
            "per_scenario": {k: round(v, 3) for k, v in delta["per_scenario"].items()}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--evals", required=True, help="JSON list of {id, task, expectations[]}")
    arm_note = ("; arms run from an empty temp dir, so every path in it must be absolute")
    ap.add_argument("--with-cmd", required=True,
                    help="argv (JSON list) for the skill-loaded arm" + arm_note)
    ap.add_argument("--without-cmd", required=True, help="argv (JSON list) for the bare arm" + arm_note)
    # Derived from judge.BACKENDS, never restated — see the same note in bench_verdict.py.
    ap.add_argument("--judge", choices=["auto", *sorted(BACKENDS)], default="auto",
                    help="auto = the first reachable backend in judge.AUTO_ORDER, preferring "
                         "cross-family")
    ap.add_argument("--substrate", choices=["native", "promptfoo"], default="native")
    ap.add_argument("--reps", type=int, default=3,
                    help="generations per task x arm (a single pass cannot separate reliably-good "
                         "from lucky; ADR 0019/0058 — set 1 only for a smoke run)")
    ap.add_argument("--practical", type=float, default=0.0,
                    help="pre-registered minimum difference worth having; KEEP needs the CI's "
                         "lower bound above it (benchstats.keep_verdict)")
    ap.add_argument("--out", default="-")
    add_spend_flag(ap, "paid generation")
    a = ap.parse_args()
    if a.reps < 1:
        sys.exit("--reps must be >= 1")

    evals = json.load(open(a.evals))
    evals_by_id = {e["id"]: e for e in evals}
    arms = [{"name": "with", "cmd": json.loads(a.with_cmd)},
            {"name": "without", "cmd": json.loads(a.without_cmd)}]
    for arm in arms:
        rel = relative_path_args(arm["cmd"])
        if rel:
            sys.exit(f"--{arm['name']}-cmd: {rel} are relative paths; arms run from an empty temp "
                     f"dir, where they would not resolve — make them absolute")
    for ev in evals:  # checks also run from an empty temp dir; refuse before any spend
        for e in ev["expectations"]:
            c = check_of(e)
            if isinstance(e, dict) and "check" in e and not (
                    isinstance(c, list) and c and all(isinstance(x, str) for x in c)):
                sys.exit(f"eval {ev['id']}: a check must be a non-empty argv list of strings")
            if c and relative_path_args(c):
                sys.exit(f"eval {ev['id']}: check {relative_path_args(c)} are relative paths; "
                         f"checks run from an empty temp dir — make them absolute")
    n_judged = sum(any(not check_of(e) for e in ev["expectations"]) for ev in evals)
    gaps = lockdown_gaps(arms)
    for g in gaps:  # before the spend prompt, so a dry run shows it
        print("WARNING: arms not locked down — " + g, file=sys.stderr)
    n_gen = len(evals) * 2 * a.reps
    require_yes(a.yes, f"{len(evals)} tasks x 2 arms x {a.reps} reps = {n_gen} generations + "
                       f"{n_judged * 2 * a.reps} judge calls (judge={a.judge}, "
                       f"substrate={a.substrate})")

    sub = make_substrate(a.substrate)
    # 'auto' resolves per judge.AUTO_ORDER; raises with remedy if none. Script checks only: no judge.
    judge = make_judge(a.judge) if n_judged else None
    if judge and judge.fallback_note:
        print("NOTE: " + judge.fallback_note, file=sys.stderr)
    tasks = [e["task"] for e in evals]
    gen = []
    for rep in range(1, a.reps + 1):
        rows = sub.run(tasks, arms)
        for g in rows:
            g["rep"] = rep
        gen.extend(rows)
    # resolve prompt_id (task index from the substrate) back to the eval id; promptfoo may echo it as
    # a string, native as an int. A non-numeric value is assumed to already be an eval id.
    for g in gen:
        pid = g["prompt_id"]
        if isinstance(pid, int):
            g["prompt_id"] = evals[pid]["id"]
        elif isinstance(pid, str) and pid.isdigit():
            g["prompt_id"] = evals[int(pid)]["id"]
    cells, errs = grade_all(gen, evals_by_id, judge)
    report = {"skill_evals": a.evals, "judge": judge.name if judge else "none (script checks only)",
              "n_tasks": len(evals),
              "n_reps": a.reps, "errors": errs, **aggregate(cells, practical=a.practical)}
    if judge and judge.fallback_note:  # same-family judge: the caveat travels with the numbers
        report["judge_fallback"] = judge.fallback_note
    if gaps:  # unverified isolation: same pattern, a possible confounded null
        report["arm_isolation_unverified"] = gaps
    js = report_json(report)
    print(js) if a.out == "-" else open(a.out, "w").write(js)


if __name__ == "__main__":
    main()
