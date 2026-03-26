# Run Prompt Feedback Loop Spec

Status: planned.

This file defines the desired behavior of `tools/run_prompt_feedback_loop.py` as a true closed-loop optimizer entrypoint. It is separate from the epic and task cards because it describes the user-facing workflow shape the system should eventually satisfy with one command.

## Goal
The command:

```bash
python3 tools/run_prompt_feedback_loop.py --bench <path-to-bench>
```

should be enough to:
- evaluate the current prompt-pack baseline,
- learn from recurring failures,
- create a candidate prompt adjustment,
- test the candidate against the same suite,
- promote the candidate only when it is measurably better, and
- optionally repeat for multiple rounds until no further safe improvement is found.

The user should not need to manually:
- create run directories,
- generate `aggregate.json`,
- apply a proposal into a candidate prompt-pack,
- remember command ordering,
- or track version names by hand.

---

## Core User Experience

### Desired UX
The user runs one command and walks away.

The system should:
1. create its own working directory,
2. run the baseline suite,
3. aggregate failures,
4. generate and apply a candidate adjustment,
5. rerun the suite on the candidate,
6. compare baseline vs candidate,
7. promote if better,
8. repeat if warranted,
9. stop with a final evidence-backed result.

### Non-Goals
- The user should not be required to pass an existing `aggregate.json`.
- The user should not be required to run `live_athlete_sim_runner.py` separately.
- The user should not be required to create candidate prompt-pack versions manually.

---

## Entry Command

### Minimal Command
```bash
python3 tools/run_prompt_feedback_loop.py --bench <bench-path>
```

### Optional Flags
- `--scenario <id>` repeated
- `--runs-per-scenario <n>`
- `--min-turns <n>`
- `--max-turns <n>`
- `--max-parallel <n>`
- `--max-rounds <n>`
- `--athlete-model <model>`
- `--judge-model <model>`
- `--start-version <version>`
- `--auto-promote`
- `--activate`
- `--output-dir <dir>`

### Expected Defaults
- start from the active prompt-pack version if `--start-version` is omitted
- create a fresh workflow output directory automatically
- run a bounded number of rounds, default `3`
- auto-promote winning candidates by default or via a simple explicit flag
- activate the final promoted version only when requested

---

## Round Model

## Round 0 — Baseline Discovery
Round 0 establishes the baseline and creates the first evidence batch.

### Steps
1. Resolve the baseline prompt-pack version.
2. Run the eval suite for that version.
3. Aggregate the baseline run outputs into `aggregate.json`.

### Inputs
- baseline prompt-pack version
- bench config

### Outputs
- baseline live run directory
- baseline aggregate artifact

### Important Rule
Round 0 should not require a pre-existing `aggregate.json`.

## Round N — Candidate Optimization
Each later round attempts one prompt improvement against the current baseline.

### Steps
1. Use the current baseline aggregate to generate a `proposal.json`.
2. Automatically apply that proposal into a new candidate prompt-pack version.
3. Run the same eval suite against the candidate version.
4. Aggregate the candidate run outputs.
5. Compare baseline vs candidate using regression gates.
6. If candidate wins, promote it and make it the next baseline.
7. If candidate loses, stop or reject and continue only if future policy explicitly allows multiple candidate attempts per round.

### Inputs
- baseline prompt-pack version
- baseline aggregate artifact
- bench config

### Outputs
- `proposal.json`
- candidate prompt-pack version
- candidate live run directory
- candidate aggregate artifact
- `regression_report.json`
- optional promotion artifact

---

## Automatic Candidate Creation

### Required Behavior
The loop must automatically convert `proposal.json` into a real candidate prompt-pack version on disk.

### Why It Matters
Without this step, the system is not truly autonomous. It remains a semi-manual workflow that depends on a human or another script to materialize the candidate.

### Rules
- never edit the baseline version in place
- always create a distinct candidate version
- candidate version names must be deterministic and human-readable
- candidate prompt-pack creation must be traceable back to the proposal artifact

### Example Version Names
- baseline: `v1`
- candidate round 1: `v1-r1-candidate`
- promoted round 1: `v1-r1`
- candidate round 2: `v1-r1-r2-candidate`

The exact naming can change, but the distinction between baseline, candidate, and promoted versions must remain explicit.

---

## Regression and Gating

### Candidate Must Beat Baseline
The candidate should only be promoted if:
- overall average quality improves,
- safety does not regress,
- protected dimensions do not regress beyond tolerance,
- and the comparison is based on the same suite shape.

### Protected Dimensions
At minimum:
- `memory_continuity`
- `tone_trust`

### Hard Safety Rule
Any safety regression must block promotion immediately.

### Comparison Discipline
The baseline run and candidate run must use:
- the same bench,
- the same scenario filters,
- the same run counts,
- the same turn limits,
- the same athlete model and judge model,
- and differ only by prompt-pack version.

---

## Stop Conditions
The loop should stop when any of the following occurs:
- candidate fails regression gates
- proposal produces no supported changes
- no meaningful recurring issues remain
- max rounds reached
- safety regresses
- improvement is too small to matter

### Recommended Defaults
- `max_rounds = 3`
- stop immediately when `overall_average_score <= 0` improvement
- stop immediately on safety regression
- stop when proposal has zero changes

---

## Artifact Layout

## Workflow Root
The system should create one working directory per invocation:

- `sam-app/.cache/prompt-feedback-loop/<timestamp>/`

### Required Contents
- `workflow_summary.json`
- `round-0/`
- `round-1/`
- `round-2/`
- etc.

## Round Directory Layout
Example:

- `round-0/base-run/`
- `round-0/base-aggregate.json`
- `round-1/proposal.json`
- `round-1/candidate-pack-info.json`
- `round-1/candidate-run/`
- `round-1/candidate-aggregate.json`
- `round-1/regression-report.json`
- `round-1/promotion.json`

### Principles
- artifacts should be grouped by round
- baseline and candidate artifacts should be easy to inspect
- the layout should be deterministic and reviewable

---

## Final Summary

### Required Final Output
At the end of the workflow, the system should write a single summary artifact that tells the user:
- start version
- final version
- rounds attempted
- rounds promoted
- winning metric deltas
- rejected rounds and failed gates
- paths to the most important artifacts

### Why
The user’s goal is not just “the system changed something.”
The user wants to come back and see:
- a version that is ready to push,
- plus evidence that it improved quality safely.

---

## Required Logging
The script should print concise progress updates while running, for example:
- `round 0: running baseline v1`
- `round 0: aggregating baseline`
- `round 1: generating proposal`
- `round 1: applying proposal into v1-r1-candidate`
- `round 1: running candidate`
- `round 1: comparing baseline vs candidate`
- `round 1: promoted v1-r1`
- `done: final version v1-r1`

The logging should help the operator understand progress without exposing low-level file choreography.

---

## Definition of Done
`tools/run_prompt_feedback_loop.py` is done when:
- it can start from zero with no pre-existing aggregate artifact,
- it can run the baseline suite automatically,
- it can generate and apply a candidate adjustment automatically,
- it can compare baseline vs candidate using explicit gates,
- it can promote a winning candidate,
- it can repeat for multiple rounds,
- it can stop safely without manual intervention,
- and it leaves behind a final evidence-backed summary.

---

## Current Gap Relative To This Spec
If the implementation still requires any of the following, the script is not yet at the desired end-state:
- manual `aggregate.json` bootstrap
- manual candidate prompt-pack creation
- manual version choreography between proposal and regression
- manual round management

The biggest functional gap to watch is:
- `proposal.json` must be automatically converted into a candidate prompt-pack artifact as part of the loop.

That is the step that turns the current collection of tools into a true self-running optimizer workflow.
