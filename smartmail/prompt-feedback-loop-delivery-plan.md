# Prompt Feedback Loop Delivery Plan

Status: in progress.

This file is the execution companion to [prompt-feedback-loop-epic.md](/Users/levonsh/Projects/smartmail/prompt-feedback-loop-epic.md). The epic describes the architecture and scope. This file describes the implementation sequence, dependency order, and merge bars for coding work.

## Delivery Rules
- Work in milestone order unless an explicit dependency change is approved.
- Each milestone should be independently mergeable.
- Each milestone should preserve existing runtime behavior unless the milestone explicitly introduces a behavior change.
- Prefer small tasks with narrow write scopes.
- Do not combine prompt-pack refactoring and optimizer behavior changes in the same task.
- Do not start proposal, regression, or promotion work before read-only aggregation exists.

---

## Milestone Overview

### M1 — Read-Only Aggregation
Status:
- DONE
Goal:
- Turn existing live athlete simulator JSONL attempt artifacts into a deterministic aggregate artifact.

Why first:
- This creates the factual base for every later step.
- It is read-only and low-risk.

Depends on:
- existing `tools/live_athlete_sim_runner.py` output format

Main outputs:
- `tools/prompt_feedback_aggregate.py`
- `aggregate.json`
- unit tests for aggregation

Behavior change:
- none to production runtime

Merge bar:
- aggregation works against a real existing run directory
- unit tests pass

### M2 — Judge Contract Extension
Status:
- DONE
Goal:
- Add one optional corrected-example field to the judge output contract.

Why now:
- It extends the evidence quality before any optimizer proposal work begins.

Depends on:
- M1 complete or in progress

Main outputs:
- schema and validator update
- tests for optional field behavior

Behavior change:
- judge payload may include an extra optional field

Merge bar:
- old payloads still validate
- new payloads with corrected example validate

### M3 — Prompt-Pack Extraction
Status:
- DONE
Goal:
- Move editable prompt surfaces into versioned prompt-pack artifacts while preserving current behavior.

Why now:
- This creates the safe editing boundary for later proposal and promotion steps.

Depends on:
- none from M1/M2 at runtime, but should land before any proposal tooling

Main outputs:
- prompt-pack file structure
- prompt loader
- tests proving no behavior change

Behavior change:
- none intended

Merge bar:
- existing prompt behavior preserved
- runtime reads prompt-pack `v1`

### M4 — Proposal Artifact Generation
Status:
- `PFL1-M4-A` DONE
- `PFL1-M4-B` not started
Goal:
- Produce a structured prompt-change proposal from aggregate feedback and a base prompt-pack version.

Why now:
- This is the first optimizer-facing step, but still does not mutate active runtime behavior.

Depends on:
- M1
- M3
- M2 optional but preferred

Main outputs:
- `tools/prompt_patch_proposer.py`
- `proposal.json`
- tests for proposal artifact structure

Behavior change:
- none to active runtime prompts

Merge bar:
- can generate a constrained proposal referencing real aggregate failures

### M5 — Regression Comparison
Status:
- `PFL1-M5-A` DONE
- `PFL1-M5-B` DONE
Goal:
- Compare base and proposed prompt-pack versions on the same suite shape and emit a promotion decision.

Why now:
- This is the first real gate that determines whether prompt changes are better.

Depends on:
- M1
- M3
- M4

Main outputs:
- `tools/prompt_patch_regression.py`
- `regression_report.json`
- tests for gate logic
- real suite-execution support for base vs proposed versions
- artifact bundle from both runs plus comparison output

Behavior change:
- none to active runtime prompts unless promotion later occurs

Merge bar:
- can compare two prompt-pack versions deterministically
- explicit gates are enforced
- can optionally execute both versions against the same suite config instead of requiring precomputed aggregates

### M6 — Promotion and Active Version Selection
Status:
- `PFL1-M6-A` DONE
- `PFL1-M6-B` DONE
Goal:
- Persist a new prompt-pack version with lineage and metrics, and allow safe activation or rollback.

Why now:
- Promotion should only exist after comparison is trustworthy.

Depends on:
- M3
- M5

Main outputs:
- `tools/prompt_pack_promote.py`
- version lineage metadata
- active version selection mechanism

Behavior change:
- active prompt-pack version can change through a controlled path

Merge bar:
- promotion writes immutable version data
- rollback path is explicit

---

## Dependency Graph
- M1 is the foundation for optimization data.
- M2 can land any time after M1 starts, but before proposal quality work matters.
- M3 must land before M4, M5, or M6.
- M4 depends on M1 and M3.
- M5 depends on M1, M3, and M4.
- M6 depends on M3 and M5.

In short:
- M1 -> M4 -> M5
- M3 -> M4 -> M5 -> M6
- M2 feeds M4 quality but is not a hard blocker for the first proposal contract

---

## Milestone Details

## M1 — Read-Only Aggregation

### Scope
- Read attempt JSONL files from a live sim output directory.
- Extract `judge_result` events only.
- Write deterministic aggregate output.

### Files to Add
- `tools/prompt_feedback_aggregate.py`
- `sam-app/email_service/test_prompt_feedback_aggregate.py`

### Files to Edit
- none required

### Files Not To Touch
- prompt files
- rule engine files
- business logic files

### Required CLI Shape
- `--input-dir`
- optional `--output`

### Required Output Shape
- `run_id`
- `input_dir`
- `attempt_files`
- `average_scores`
- `score_by_scenario`
- `issue_tag_counts`
- `strength_tag_counts`
- `misses_by_issue_tag`
- `examples`

### Required Tests
- multiple attempt files aggregate correctly
- non-judge phases are ignored
- empty directory fails clearly
- malformed line handling is explicit

### Done When
- a real run directory can be aggregated without manual transcript reading

## M2 — Judge Contract Extension

### Scope
- Add one optional field for a corrected example to judge output.

### Files to Edit
- `sam-app/email_service/athlete_simulation.py`
- `sam-app/email_service/test_athlete_simulation.py`

### Files Not To Touch
- proposal tools
- regression tools

### Required Field Behavior
- optional
- short text only
- validator accepts missing field

### Required Tests
- valid without field
- valid with field
- invalid wrong-type field rejected

### Done When
- aggregation can read the field if present and old runs still remain valid

## M3 — Prompt-Pack Extraction

### Scope
- Extract editable prompt surfaces into file-based prompt-pack artifacts.
- Preserve current runtime behavior.

### Files to Add
- `sam-app/email_service/prompt_packs/coach_reply/v1/manifest.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json`
- optional loader helper file if needed

### Files to Edit
- `sam-app/email_service/skills/response_generation/prompt.py`
- `sam-app/email_service/skills/coaching_reasoning/prompt.py`
- related tests that assert prompt text content

### Files Not To Touch
- proposal/regression logic beyond loading active prompt pack

### Required Tests
- current prompt text preserved
- missing prompt-pack file fails clearly
- active version loading is deterministic

### Done When
- runtime loads prompt-pack `v1` and existing prompt behavior is unchanged

## M4 — Proposal Artifact Generation

### Scope
- Generate a structured proposal artifact from aggregated failures.

### Files to Add
- `tools/prompt_patch_proposer.py`
- `sam-app/email_service/test_prompt_patch_proposer.py`

### Files to Edit
- optional shared prompt-pack loader utilities

### Files Not To Touch
- active runtime prompt selection
- business logic

### Required Output Shape
- `base_version`
- `proposed_version`
- `target_surfaces`
- `changes`
- `summary`
- `risks`

### Required Tests
- proposal references aggregate failures
- proposal only targets allowed surfaces
- proposal artifact is deterministic when LLM is stubbed or proposal input is fixed

### Done When
- a reviewer can inspect one proposal artifact and understand exactly what is being suggested

## M5 — Regression Comparison

### Scope
- Run or compare two prompt-pack versions using the same suite shape.
- Emit a regression decision artifact.

### Files to Add
- `tools/prompt_patch_regression.py`
- `sam-app/email_service/test_prompt_patch_regression.py`

### Files to Edit
- optional runner plumbing for selecting prompt-pack version

### Files Not To Touch
- business logic

### Required Gates
- average score must improve
- safety must not decline
- protected dimensions must not materially regress

### Required Tests
- better proposed metrics pass
- safety drop fails
- protected-dimension regression fails

### Done When
- the system can answer “is this prompt pack actually better?” with one artifact

## M6 — Promotion and Active Version Selection

### Scope
- Persist a new prompt-pack version with lineage and metrics.
- Allow controlled activation and rollback.

### Files to Add
- `tools/prompt_pack_promote.py`

### Files to Edit
- prompt-pack manifest handling
- active version resolution logic if needed

### Files Not To Touch
- unrelated runtime code

### Required Tests
- promoted version persists lineage metadata
- promotion requires successful regression decision
- active version can switch back to prior version

### Done When
- a better prompt pack can be promoted without editing existing versions in place

## M5-B — Real Old vs New Suite Execution

### Scope
- Extend regression from aggregate-only comparison to actual dual suite execution.
- Run the same suite shape against both prompt-pack versions.
- Aggregate both result sets and then apply the existing regression gate.

### Files to Edit
- `tools/prompt_patch_regression.py`
- likely `tools/live_athlete_sim_runner.py` or a thin wrapper around it

### Files Not To Touch
- business logic
- prompt text content

### Required Behavior
- select prompt-pack version for base run
- select prompt-pack version for proposed run
- run the same suite config for both
- aggregate both runs through the existing aggregation path
- emit one regression artifact bundle

### Required Tests
- base and proposed prompt-pack versions are both exercised
- suite config is identical across both runs
- regression report references the actual generated aggregate artifacts

### Done When
- one command can compare two prompt-pack versions by actually running both suites, not only by reading precomputed aggregates

## M6-B — Closed-Loop Workflow Command

### Scope
- Add one top-level command that ties together proposal, dual execution, regression, and optional promotion.

### Files to Add or Edit
- likely a new top-level tool or an expanded workflow entrypoint
- may reuse:
  - `tools/prompt_patch_proposer.py`
  - `tools/prompt_patch_regression.py`
  - `tools/prompt_pack_promote.py`

### Files Not To Touch
- unrelated runtime logic

### Required Behavior
- take aggregate feedback and a base version
- generate or read proposal
- execute base and proposed runs
- compare with regression gates
- optionally promote if gates pass

### Required Tests
- happy-path workflow without promotion
- happy-path workflow with promotion
- regression failure blocks promotion

### Done When
- the prompt feedback loop can run end to end from proposal through optional promotion with one workflow command

---

## Merge Sequence
1. Merge M1 first.
2. Merge M2 next or alongside M1 if cleanly isolated.
3. Merge M3 before any optimizer-facing tooling.
4. Merge M4 after M1 and M3 are stable.
5. Merge M5 after M4.
6. Merge M5-B after M5.
7. Merge M6 after M5-B.
8. Merge M6-B last.

---

## Testing Sequence
- Inner loop during M1-M4:
  - run focused unit tests for new files and affected prompt modules
  - run `sam-app/email_service` unit tests often
- Before marking any code task done:
  - run the full merge bar from `AGENTS.md`

Required full suite:
```bash
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

---

## Risks To Watch
- Mixing data aggregation and prompt-editing logic too early.
- Refactoring prompt loading while accidentally changing prompt behavior.
- Letting proposal tooling edit code or runtime logic.
- Defining gates that are too fuzzy to test reliably.
- Overfitting to one run directory or one scenario.

---

## Expected Delivery Result
After following this delivery plan, the codebase should have:
- a reliable read-only batch aggregation stage,
- versioned prompt-pack artifacts,
- constrained proposal artifacts,
- explicit old-vs-new regression gates, and
- a controlled prompt-pack promotion path.
