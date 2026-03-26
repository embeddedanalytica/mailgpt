# Run Prompt Feedback Loop Implementation Task

Status: planned.

This file is the coding-agent execution spec for implementing the autonomous closed-loop behavior described in [run-prompt-feedback-loop-spec.md](/Users/levonsh/Projects/smartmail/run-prompt-feedback-loop-spec.md).

Use this file for implementation. Use the spec file for product intent.

## Task Goal
Implement `tools/run_prompt_feedback_loop.py` so the user can start from zero and run the full prompt feedback loop with one command:

```bash
python3 tools/run_prompt_feedback_loop.py --bench <bench-path>
```

The command must:
- bootstrap its own baseline run,
- aggregate baseline failures,
- generate a proposal,
- automatically apply the proposal into a candidate prompt-pack,
- run the candidate,
- compare baseline vs candidate,
- promote if better,
- repeat for multiple rounds,
- and stop with a final summary artifact.

The user must not be required to manually provide:
- `aggregate.json`
- run directories
- candidate prompt-pack versions
- round-by-round commands

---

## Files In Scope

### Primary Files To Edit
- `tools/run_prompt_feedback_loop.py`
- `tools/prompt_feedback_loop.py` if the existing workflow should be adapted rather than replaced
- `tools/prompt_patch_apply.py`
- `tools/prompt_patch_regression.py`
- `tools/prompt_pack_promote.py`

### Likely Test Files To Add
- `sam-app/email_service/test_run_prompt_feedback_loop.py`

### Test Files That May Need Updates
- `sam-app/email_service/test_prompt_patch_regression.py`
- `sam-app/email_service/test_prompt_pack_promote.py`

### Files Not To Touch
- business logic in `sam-app/email_service/coaching.py`
- judge contract in `sam-app/email_service/athlete_simulation.py`
- prompt text content files unless strictly required
- unrelated rule engine logic

---

## Current Reusable Building Blocks
The implementation should reuse existing components instead of rebuilding them:

- `tools/live_athlete_sim_runner.py`
- `tools/prompt_feedback_aggregate.py`
- `tools/prompt_patch_proposer.py`
- `tools/prompt_patch_apply.py`
- `tools/prompt_patch_regression.py`
- `tools/prompt_pack_promote.py`
- `sam-app/email_service/prompt_pack_loader.py`

Do not create a second parallel workflow stack.

---

## Required CLI Contract

### Required Input
- `--bench`

### Optional Inputs
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

### Explicit Requirement
`--aggregate` must not be required for the autonomous loop entrypoint.

If the existing implementation supports `--aggregate` for resuming or manual workflows, that is acceptable, but the default path must bootstrap from zero.

---

## State Machine

The implementation should follow this state progression:

1. `INIT`
2. `BASELINE_RUN`
3. `BASELINE_AGGREGATE`
4. `PROPOSAL`
5. `APPLY_CANDIDATE`
6. `CANDIDATE_RUN`
7. `CANDIDATE_AGGREGATE`
8. `REGRESSION`
9. `PROMOTE`
10. `NEXT_ROUND`
11. `STOP`

Only `PROMOTE` and `NEXT_ROUND` are conditional.

### `INIT`
- resolve output root
- resolve baseline version from:
  1. `--start-version`
  2. active prompt-pack version
- initialize workflow summary state

### `BASELINE_RUN`
- run the live suite for the baseline version
- write artifacts into round-specific directory

### `BASELINE_AGGREGATE`
- aggregate baseline run output into `base-aggregate.json`

### `PROPOSAL`
- generate `proposal.json` from the baseline aggregate
- if proposal has zero changes, stop

### `APPLY_CANDIDATE`
- create a new candidate prompt-pack version automatically
- if candidate creation fails, stop with failure detail

### `CANDIDATE_RUN`
- run the same suite config against the candidate prompt-pack version

### `CANDIDATE_AGGREGATE`
- aggregate candidate run output into `candidate-aggregate.json`

### `REGRESSION`
- compare base vs candidate using the existing regression gate

### `PROMOTE`
- if regression decision is `promote`, create immutable promoted version
- optionally activate it if requested

### `NEXT_ROUND`
- if promoted and rounds remain, promoted version becomes new baseline
- increment round counter and continue

### `STOP`
- write final `workflow_summary.json`
- exit cleanly with clear status

---

## Round Semantics

### Round 0
Round 0 establishes the first baseline.

Required outputs:
- `round-0/base-run/`
- `round-0/base-aggregate.json`

### Round N >= 1
Each later round should contain:
- `proposal.json`
- candidate prompt-pack info
- candidate run dir
- candidate aggregate
- regression report
- optional promotion artifact

The promoted version from round `N` becomes the baseline for round `N+1`.

---

## Artifact Layout

The workflow must create one root per invocation:

- `sam-app/.cache/prompt-feedback-loop/<timestamp>/`

Expected contents:
- `workflow_summary.json`
- `round-0/`
- `round-1/`
- `round-2/`

Expected round contents:
- `base-run/`
- `base-aggregate.json`
- `proposal.json`
- `candidate-pack-info.json`
- `candidate-run/`
- `candidate-aggregate.json`
- `regression-report.json`
- `promotion.json`

The exact file names may vary slightly, but:
- each round must be self-contained
- baseline and candidate artifacts must be obvious
- the final summary must point to the winning artifacts

---

## Stop Conditions

The loop must stop when any of these is true:
- proposal has zero supported changes
- candidate fails regression
- safety regresses
- max rounds reached
- candidate creation fails
- suite run fails

Recommended default:
- `max_rounds = 3`

---

## Required Final Summary

The final summary must include:
- start version
- final version
- rounds attempted
- rounds promoted
- final decision
- winning score deltas
- failed gates for rejected rounds
- paths to key artifacts

This is the main artifact the user should inspect after the workflow completes.

---

## Acceptance Tests

The implementation is not done without tests that cover the main workflow states.

### Required Tests
- starts from zero without requiring `--aggregate`
- creates baseline run dir automatically
- creates baseline aggregate automatically
- generates proposal from the baseline aggregate
- applies proposal into a candidate prompt-pack automatically
- runs candidate on the same suite config
- emits regression report
- promotes candidate only on passing regression
- stops after rejected candidate
- stops after `max_rounds`
- writes final workflow summary

### Good Test Strategy
Stub external suite execution and artifact generation where possible.
Do not require live network calls for unit coverage.

The heavy live behavior should stay exercised through existing suite layers rather than new test-only orchestration complexity.

---

## Behavioral Constraints

### Preserve Determinism Where Possible
- artifact naming should be structured and stable
- state transitions should be explicit
- promotion must remain gate-driven

### Do Not Mutate Baselines In Place
- always create new candidate or promoted versions
- never overwrite the active baseline version contents

### Do Not Hide Safety Regressions
- safety regression is a hard stop

### Do Not Rebuild Existing Tools
- call or reuse current tools
- do not duplicate their logic into a new code path unless necessary for clean orchestration

---

## Suggested Implementation Order
1. Add round/state orchestration scaffold to `tools/run_prompt_feedback_loop.py`.
2. Teach it to bootstrap baseline run and aggregation without `--aggregate`.
3. Integrate automatic proposal application into candidate prompt-pack creation.
4. Reuse existing regression tool for candidate comparison.
5. Reuse existing promotion tool for winning candidates.
6. Add looping across rounds.
7. Add final summary artifact.
8. Add focused unit tests.
9. Run full merge bar.

---

## Definition of Done
This task is done when:
- the user can run one command from zero,
- the loop can execute at least one full optimization round autonomously,
- promotion happens only when the candidate is better,
- multiple rounds are supported,
- and the workflow leaves behind a clear evidence-backed summary without requiring manual artifact choreography.
