# Evidence: what the measurements of one21tools found

This folder holds the write-ups of every measurement run on the
[one21tools](https://github.com/one21labs/one21tools) plugins between July and October 2026: 32
dated runs. (Two more, `2026-07-08-ep-loophole-oos-retest` and `2026-07-08-grading-bias-audit`,
left raw output but no write-up.) They were moved here on 23-Nov-2026, when one21tools was cut down to the
parts these results support.

Only the write-ups are here. The raw run output (about 21 MB of transcripts, grades and result
files) stays in one21tools' history, in the `benchmarks/` folder of commit `0a1834d`, under the
same directory names. A write-up that names `results.jsonl` or `metadata.json` means the file at
that commit. Write-ups also cite "ADR NNNN" and "#NNN": those are one21tools' decision records
(`docs/decisions/` at the same commit) and its issues.

## What the results say, taken together

**1. Most of the gain disappeared on cases written without the skill in view.**
Across the shipped skills, cases written by someone looking at the skill showed a gain of +0.37
over the bare model (interval +0.23 to +0.50). Cases written blind showed +0.04 (interval -0.03
to +0.11), with the bare model already scoring 0.82. A skill's author writes cases that reward
what the skill says. The current model already does most of what these skills asked for.
See `2026-10-12-g8-shortfall/README.md`.

**2. A panel of agents did not decide better than one agent told to think carefully.**
The `/decide` panel (several advisors, a decider, a verifier) was compared with a single prompt
given the same token budget. The difference in decision quality was +0.01 (interval -0.18 to
+0.20), at about four times the cost of a bare decision, and the panel did worse on two planted
traps. Its one real edge was anticipating how the decision would actually fail: 0.42, against
0.25 for the bare agent and 0.08 for one agent arguing with itself. Structure bought tokens, not
judgment; independence bought foresight.
See `2026-07-12-pdca-decide-outcome/README.md`, and the two follow-ups
`2026-07-13-pdca-decide-armd/` and `2026-07-14-pdca-decide-poker/`.

**3. Short rules for a specific situation moved behaviour. Definitions and doctrine did not.**
The `engineering-principles` skill was split into its operational content (what to do, when)
and its conceptual content (what the principles are and where they come from). The operational
half alone reproduced the whole skill's effect (+0.21). The conceptual half added nothing
(+0.06), and the full skill scored slightly below the operational half. One case carried most of
it: told a plan was "already approved", the bare model scored 0.00, and the model given the
rule that approval is not completeness scored 0.80.
See `2026-07-18-ep-partition/README.md`.

The same pattern shows in project instruction files: a short, concrete "Shipping" section in a
`CLAUDE.md` scored +0.83 (interval +0.51 to +1.16). See `2026-07-09-claude-md-sections/README.md`.

**4. One skill held up under a judge from a different vendor.**
`code-standards` beat the bare model by +0.44 (interval +0.19 to +0.69) when graded by another
vendor's model. Read with finding 1: it reliably applies a house style, which is not the same as
writing better code. See `2026-07-17-code-standards-remeasure/README.md`.

What followed from these: one21tools kept `code-standards`, a four-rule `engineering-principles`,
and two small skills built on independence (`/advise` and `/fresh-check`), and removed the rest.

## Cautions

Every run here denied tools, was a single turn of plain text, and put the skill's text directly
in front of the model. None measures whether a skill gets picked up by itself in a real working
session. Sample sizes are small (4 to 10 cases per skill), which is why most intervals are wide.
The two October runs are marked provisional in their own titles.

## Index

| Subject | Runs |
|---|---|
| Skills against the bare model | `2026-07-08-skills-hermetic`, `2026-07-09-three-skills-remeasure`, `2026-07-17-crossjudge-regrade`, `2026-10-12-skill-vs-bare-two-models`, `2026-10-12-g8-shortfall` |
| `code-standards` | `2026-07-17-code-standards-remeasure` |
| `engineering-principles` | `2026-07-09-ep-remeasure-hermetic`, `2026-07-10-ep-loophole-oos-hermetic`, `2026-07-18-ep-partition`, `2026-07-18-ep-slim-remeasure`, `2026-10-18-ep-one-meaning` |
| `building-skills` | `2026-07-09-bs-iter2-remeasure`, `2026-07-18-bs-iter3-remeasure` |
| Skill descriptions and triggering | `2026-07-07-toolkit-grid`, `2026-07-09-description-ablation`, `2026-07-10-description-ablation` |
| `CLAUDE.md` content | `2026-07-08-claude-md-template-ablation`, `2026-07-08-claude-md-template-ablation-hermetic`, `2026-07-09-claude-md-sections` |
| The decision panel | `2026-07-12-pdca-plumbing-pilot`, `2026-07-12-pdca-decide-outcome`, `2026-07-13-pdca-decide-armd`, `2026-07-14-pdca-decide-poker`, `2026-07-14-pdca-dod-phase0`, `2026-07-17-ceremony-cuts-outcome` |
| The retrospective | `2026-07-12-pdca-retrospect-recall`, `2026-07-13-pdca-retrospect-recall-v2`, `2026-07-15-pdca-retrospect-friction-phase0` |
| Model tiers and routing | `2026-07-10-routing-escalation`, `2026-07-10-tiered-execution`, `2026-07-10-tiered-execution-fullgrid` |
| Third-party skills | `2026-07-17-thirdparty-writing-plans` |

## Adding a run

A new measurement adds a new dated folder holding its write-up. Do not edit an old one: a re-run
is a new folder. Keep raw run output out of this repository. It is installed as a plugin, so
every megabyte here is downloaded by every user.
