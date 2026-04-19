# Bug 19 Handover

## Goal

Troubleshoot and fix the remaining bug `19` class issue in the redesigned sectioned memory system.

Bug `19` should **not** be marked fixed yet.

The remaining confirmed failure is in long-horizon scenario `AM-LH-004`, where a durable goal is still lost under pressure and the expected reject-at-cap behavior does not occur.

## Current State

### What is already done

- The memory redesign from [memory-redesign-implementation-plan.md](./memory-redesign-implementation-plan.md) is implemented.
- The long-horizon bench runner is now aligned with the sectioned memory runtime.
- Live schema issues were fixed.
- Multiple runner-only bugs were fixed:
  - missing `_note_texts`
  - missing `_normalize_text`
  - missing `_normalize_signal`
  - refresh failures now record structured error fields in `results.json`
- `AM-LH-002` was failing because the model emitted update-upserts with `target_id` plus echoed `section` / `fact_key`, and the validator hard-failed that.
  - This is now fixed by making update-upserts ignore echoed immutable fields.
  - Prompt was also tightened to tell the model not to emit them.

### What is still broken

- `AM-LH-004` still fails as a real product issue.
- `AM-LH-003` and `AM-LH-005` also still show real memory-quality failures, but bug `19` should focus first on `AM-LH-004`.

## Confirmed Remaining Failure

### `AM-LH-004`

Artifact:

- [summary.md](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-am-lh-004-20260405T0017/summary.md)
- [results.json](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-am-lh-004-20260405T0017/results.json)

Observed result:

- Scenario status: `assertion_failed`
- Final score: `1.0` but final assertions still failed

Important findings:

- `healthy full-build goal` is missing in `goal_overflow_and_prompt_pressure`
- expected rejection `fifth goal rejected at cap` is missing
- expected compiled prompt trimming did not happen:
  - lower-priority detail was still included

Bench summary wording:

- `core durable truths dropped under pressure: healthy full-build goal`
- `expected rejections missing: fifth goal rejected at cap`
- `expected_compiled_prompt unexpectedly included: lower-priority detail trimmed before backbone`

Interpretation:

- This is the current best reproduction of bug `19` in the redesigned system.
- The system is still not reliably protecting active durable goals under pressure.
- Either:
  - the refresh LLM is not preserving the goal correctly,
  - the reducer is not enforcing reject-at-cap as intended,
  - or the compiler is surfacing the wrong set after storage.

## Important Nuance From The Live Artifact

Do not assume this is already proven to be a literal active-goal eviction.

In the clean live artifact for `AM-LH-004`, step-level stored memory still shows the `healthy full-build` goal present in the `goal.active` bucket throughout the pressure steps that were inspected (`11` through `20`).

That means the current failing signal is more precise than "the goal was definitely deleted from active storage."

What is definitely true from the artifact:

- no `rejected_candidates` were recorded on the pressure steps
- the checkpoint evaluator still reported:
  - `missing healthy full-build goal`
  - `expected rejections missing: fifth goal rejected at cap`
  - `expected_compiled_prompt unexpectedly included: lower-priority detail trimmed before backbone`

So the next agent should verify which of these is actually wrong:

1. bench evaluation logic is flattening the wrong storage shape
2. reducer never emitted the expected rejection signal
3. compiler or retrieval context still contains lower-priority detail that violates the design
4. some later step changed the live object shape in a way the checkpoint evaluator interprets incorrectly

In other words: `AM-LH-004` is still the best bug `19` repro, but the exact failing layer is not yet proven to be "active durable goal eviction."

## Result Schema Notes

The long-horizon `results.json` shape is:

- top-level: `list[scenario_result]`
- each scenario result has:
  - `step_results`
  - `checkpoint_results`
  - `final_evaluation`
  - `retrieval_context`

Useful implementation detail:

- failing checkpoint results live under `checkpoint_results`, not `checkpoints`
- step records use `step`, not `step_index`
- current step records do **not** persist compiled prompt output; `retrieval_context` on individual steps may be `null`
- final scenario-level retrieval context is stored on the scenario result itself

This matters because a quick read of `results.json` can easily target the wrong keys and produce a false conclusion.

## Other Relevant Reruns

### `AM-LH-002`

Artifact:

- [summary.md](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-am-lh-002-20260405T0026/summary.md)

Status:

- `ok`
- Final score `1.0`

This was previously a refresh failure caused by:

- `SectionedMemoryRefreshError: candidates[0]: section is forbidden on upsert with target_id`

That issue is fixed and should not distract from bug `19`.

### `AM-LH-001`

Artifact:

- [summary.md](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-debug-001-002-004-20260404T2345/summary.md)

Status in latest debug rerun:

- `ok`
- Final score `1.0`

So its earlier refresh failure appears non-deterministic / flaky, not currently the main blocker.

### `AM-LH-003`

Artifact:

- [summary.md](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-20260404T2315/summary.md)

Real issues still visible there:

- durable schedule anchor loss: `Sunday outdoor gravel`
- routine noise over-retention: `fan detail`, `garage drill setup`

Useful, but secondary to `AM-LH-004` for bug `19`.

### `AM-LH-005`

Artifact:

- [summary.md](/Users/levonsh/Projects/smartmail/sam-app/.cache/athlete-memory-bench/long-horizon/live-rerun-am-lh-005-20260404T2338/summary.md)

Real issue:

- retired-cap trimming / retired lineage shape is wrong

Useful for later, but not the first bug `19` target.

## Files Most Relevant To Fixing `AM-LH-004`

- [tools/athlete_memory_long_horizon_bench_runner.py](/Users/levonsh/Projects/smartmail/tools/athlete_memory_long_horizon_bench_runner.py)
- [test_bench/athlete_memory_long_horizon_bench.md](/Users/levonsh/Projects/smartmail/test_bench/athlete_memory_long_horizon_bench.md)
- [sam-app/email_service/skills/memory/sectioned/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/sectioned/prompt.py)
- [sam-app/email_service/skills/memory/sectioned/validator.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/sectioned/validator.py)
- [sam-app/email_service/skills/memory/sectioned/runner.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/sectioned/runner.py)
- [sam-app/email_service/sectioned_memory_reducer.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/sectioned_memory_reducer.py)
- [sam-app/email_service/memory_compiler.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/memory_compiler.py)
- [sam-app/email_service/test_sectioned_memory_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_sectioned_memory_skill.py)

## Likely Failure Surfaces

### 1. Reducer reject-at-cap enforcement

Question:

- When the goal section is full, is the reducer actually rejecting a new non-superseding goal create-upsert?

Things to inspect:

- step-level `rejected_candidates`
- active goal counts before and after the overflow turn
- reducer decision path in [sectioned_memory_reducer.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/sectioned_memory_reducer.py)
- whether the live candidate batch actually hit the reject-at-cap branch

### 2. Checkpoint / bench evaluation shape

Question:

- Is the benchmark claiming the goal is "missing" because it is reading the wrong storage or retrieval shape?

Things to inspect:

- how the long-horizon runner flattens sectioned memory into assertion text
- whether `durable_memory_quality` and `salience_under_pressure` are reading:
  - active storage
  - final retrieval context
  - or some mixed surrogate
- whether the scenario expectation `lower-priority detail trimmed before backbone` is being evaluated against true compiler output or only against raw active storage

### 3. Compiler behavior

Question:

- Is the compiler surfacing lower-priority detail when the bench expects backbone-first output?

Expected design:

- compiler v1 should keep goals and constraints guaranteed-included, then trim lower-priority sections deterministically

What to inspect:

- [memory_compiler.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/memory_compiler.py)
- scenario-level `retrieval_context`
- whether the failing expectation is about:
  - stored active memory
  - or prompt memory selection

### 4. Refresh LLM candidate behavior

Question:

- Around `AM-LH-004` steps 11-20, is the model proposing the wrong mix of creates / confirms / supersedes?

Things to inspect:

- candidate ops produced on overflow-pressure steps
- whether the model is proposing:
  - a new non-superseding goal that should have been rejected
  - low-value detail that should stay out of the core retrieval set
  - missing confirms for already-active backbone goals

## Recommended Debugging Order

1. Re-run only `AM-LH-004` live:

```bash
ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO=true python3 tools/athlete_memory_long_horizon_bench_runner.py --scenario AM-LH-004
```

2. Inspect the generated `results.json` for:
   - `checkpoint_results`
   - step-level `memory_notes`
   - `rejected_candidates`
   - scenario-level `retrieval_context`

3. For the first failing pressure checkpoint, determine which of these is true:
   - benchmark is reading the wrong shape
   - goal is present in active storage but absent from retrieval context
   - new non-superseding goal/detail was admitted when it should have been rejected
   - expected rejection path never fired even though the section was at cap

4. Fix the smallest wrong layer:
   - reducer reject-at-cap logic
   - benchmark / evaluator shape
   - compiler inclusion logic
   - prompt / candidate behavior

## Strong Current Hypothesis

The most likely remaining issue is still not another large architecture problem.

The cleanest current hypothesis is:

- the reducer’s reject-at-cap behavior for goal pressure is not actually being exercised or surfaced the way the design expects
- and/or the benchmark is partially evaluating against raw storage instead of true compiled prompt output

Only after ruling those out should the next agent assume the refresh model itself is losing the backbone goal.

## Commands That Were Useful

Run a single long-horizon scenario live:

```bash
ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO=true python3 tools/athlete_memory_long_horizon_bench_runner.py --scenario AM-LH-004
```

Run the full long-horizon bench live:

```bash
ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO=true python3 tools/athlete_memory_long_horizon_bench_runner.py
```

Focused tests:

```bash
python3 -m unittest -v sam-app/email_service/test_sectioned_memory_skill.py
python3 -m unittest -v sam-app/email_service/test_athlete_memory_long_horizon_bench_runner.py
```

Merge bar:

```bash
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

## Bottom Line

- Bug `19` is still open.
- `AM-LH-004` is the best current repro in the redesigned system.
- `AM-LH-002` contract failure is fixed.
- The next agent should trace `AM-LH-004` step-by-step through candidate generation, reducer behavior, and compiler output, then patch the smallest wrong layer.
