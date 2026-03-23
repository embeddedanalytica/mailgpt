# Prompt Feedback Loop Task Cards

Status: in progress.

This file breaks the prompt feedback loop work into small execution units for coding agents. Each card is intended to be independently understandable, have a narrow write scope, and produce a concrete artifact or tested change.

## Task Card Format
- `ID`
- `Goal`
- `Why now`
- `Depends on`
- `Files to add`
- `Files to edit`
- `Files not to touch`
- `Implementation notes`
- `Tests required`
- `Done when`

---

## Card PFL1-M1-A

Status: DONE.

### ID
`PFL1-M1-A`

### Goal
Add a deterministic aggregation CLI that reads live athlete sim attempt JSONL files and writes `aggregate.json`.

### Why now
This is the smallest useful step and is the foundation for every later stage.

### Depends on
- none

### Files to add
- `tools/prompt_feedback_aggregate.py`
- `sam-app/email_service/test_prompt_feedback_aggregate.py`

### Files to edit
- none

### Files not to touch
- `sam-app/email_service/skills/response_generation/prompt.py`
- `sam-app/email_service/skills/coaching_reasoning/prompt.py`
- rule engine files
- business logic files

### Implementation notes
- Read `*.jsonl` files from an input directory.
- Parse JSON lines safely.
- Only process events where `phase == "judge_result"`.
- Group results by scenario and issue tag.
- Write one deterministic `aggregate.json` artifact.
- Keep the first version fully deterministic and offline.

### Tests required
- aggregates multiple attempt files
- ignores non-judge phases
- preserves scenario/attempt/turn references
- fails clearly on empty input directory

### Done when
- `tools/prompt_feedback_aggregate.py --input-dir <run_dir>` produces a stable aggregate artifact from a real run directory

---

## Card PFL1-M1-B

Status: DONE.

### ID
`PFL1-M1-B`

### Goal
Add optional markdown summary output for aggregated feedback.

### Why now
This improves operator usability without changing the core data contract.

### Depends on
- `PFL1-M1-A`

### Files to edit
- `tools/prompt_feedback_aggregate.py`
- `sam-app/email_service/test_prompt_feedback_aggregate.py`

### Files not to touch
- prompt files
- runtime business logic

### Implementation notes
- Keep `aggregate.json` as the source of truth.
- Markdown output is optional and secondary.
- Do not embed new analysis logic only in markdown output.

### Tests required
- markdown output path is created when requested
- markdown summary matches aggregate totals at a high level

### Done when
- operators can inspect recurring issues without opening raw JSON

---

## Card PFL1-M2-A

Status: DONE.

### ID
`PFL1-M2-A`

### Goal
Add one optional corrected-example field to the live judge schema and validator.

### Why now
Proposal tooling benefits from concrete rewrite evidence, not only negative feedback.

### Depends on
- none

### Files to edit
- `sam-app/email_service/athlete_simulation.py`
- `sam-app/email_service/test_athlete_simulation.py`

### Files not to touch
- proposal/regression tools
- prompt-pack files

### Implementation notes
- Use a stable field name.
- Keep it optional.
- Validate it as a short non-empty string when present.
- Do not require existing tests or runs to change.

### Tests required
- payload without field still validates
- payload with field validates
- invalid field type fails validation

### Done when
- the judge contract can carry corrected-example evidence without breaking existing payloads

---

## Card PFL1-M3-A

Status: DONE.

### ID
`PFL1-M3-A`

### Goal
Create prompt-pack `v1` files that mirror the current response-generation and coaching-reasoning prompt content.

### Why now
Later optimization steps need a file-based editing boundary.

### Depends on
- none

### Files to add
- `sam-app/email_service/prompt_packs/coach_reply/v1/manifest.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json`

### Files to edit
- none required if this card only creates artifacts

### Files not to touch
- runner logic
- proposal tools

### Implementation notes
- This card should be content extraction only.
- Keep the text functionally identical to current prompt strings.
- Do not change runtime loading yet if that complicates validation.

### Tests required
- optional content sanity checks if practical

### Done when
- prompt-pack `v1` exists on disk and reflects current prompt content

---

## Card PFL1-M3-B

Status: DONE.

### ID
`PFL1-M3-B`

### Goal
Update runtime prompt loading to read response-generation and coaching-reasoning prompts from prompt-pack `v1`.

### Why now
This makes prompt-pack versioning real without changing behavior.

### Depends on
- `PFL1-M3-A`

### Files to edit
- `sam-app/email_service/skills/response_generation/prompt.py`
- `sam-app/email_service/skills/coaching_reasoning/prompt.py`
- related prompt tests

### Files to add
- optional shared loader utility if needed

### Files not to touch
- optimizer proposal logic
- regression logic

### Implementation notes
- Preserve existing prompt behavior exactly.
- Fail clearly if prompt-pack files are missing.
- Keep active-version selection simple.

### Tests required
- response-generation prompt content preserved
- coaching-reasoning prompt content preserved
- missing file failure is explicit

### Done when
- runtime reads prompt-pack `v1` and existing prompt tests still pass

---

## Card PFL1-M4-A

Status: DONE.

### ID
`PFL1-M4-A`

### Goal
Define and implement the `proposal.json` contract for prompt-change proposals.

### Why now
Proposal output should be stable before any smarter generation logic is added.

### Depends on
- `PFL1-M1-A`
- `PFL1-M3-B`

### Files to add
- `tools/prompt_patch_proposer.py`
- `sam-app/email_service/test_prompt_patch_proposer.py`

### Files not to touch
- active prompt-pack version selection
- promotion logic

### Implementation notes
- The first version may be deterministic or stubbed.
- The important part is the artifact contract and surface restrictions.
- Proposal targets must be limited to allowed prompt-pack files.

### Tests required
- output has required fields
- target surfaces are constrained
- proposal references aggregate failures

### Done when
- one proposal artifact can be generated from one aggregate artifact and one base prompt-pack version

---

## Card PFL1-M4-B

Status: not started.

### ID
`PFL1-M4-B`

### Goal
Add optional LLM-assisted proposal text generation while preserving the structured proposal contract.

### Why now
This improves proposal quality after the contract is stable.

### Depends on
- `PFL1-M4-A`
- `PFL1-M2-A` preferred

### Files to edit
- `tools/prompt_patch_proposer.py`
- `sam-app/email_service/test_prompt_patch_proposer.py`

### Files not to touch
- business logic
- promotion logic

### Implementation notes
- LLM assistance should produce proposal content, not bypass the structured output schema.
- Keep allowed surfaces hardcoded or manifest-driven.

### Tests required
- LLM output is normalized into the proposal schema
- unsupported target surfaces are rejected

### Done when
- proposal quality improves without weakening contract enforcement

---

## Card PFL1-M5-A

Status: DONE.

### ID
`PFL1-M5-A`

### Goal
Implement deterministic regression gate logic for comparing base and proposed metrics.

### Why now
Gate logic should be testable separately from live reruns.

### Depends on
- `PFL1-M1-A`
- `PFL1-M4-A`

### Files to add
- `tools/prompt_patch_regression.py`
- `sam-app/email_service/test_prompt_patch_regression.py`

### Files not to touch
- active runtime prompt selection

### Implementation notes
- Start with metric comparison on supplied artifacts.
- Keep gate logic explicit:
  - average score up
  - safety not down
  - protected dimensions not materially down

### Tests required
- pass on clear improvement
- fail on safety drop
- fail on protected dimension regression

### Done when
- gate logic can produce a deterministic decision from two metric sets

---

## Card PFL1-M5-B

Status: DONE.

### ID
`PFL1-M5-B`

### Goal
Connect regression logic to actual old-vs-new suite execution with prompt-pack selection.

### Why now
This turns the gate from a pure comparison helper into a real workflow tool.

### Depends on
- `PFL1-M3-B`
- `PFL1-M5-A`

### Files to edit
- `tools/prompt_patch_regression.py`
- optional runner plumbing

### Files not to touch
- promotion logic
- rule engine logic

### Implementation notes
- Reuse existing suite-running infrastructure where possible.
- Keep suite shape identical across both versions.

### Tests required
- prompt-pack version selection is respected
- both runs are aggregated through the same path

### Done when
- one command can compare two prompt-pack versions using the same suite config

---

## Card PFL1-M6-A

Status: DONE.

### ID
`PFL1-M6-A`

### Goal
Implement immutable prompt-pack promotion with lineage metadata.

### Why now
Promotion should only happen after comparison is in place.

### Depends on
- `PFL1-M3-B`
- `PFL1-M5-B`

### Files to add
- `tools/prompt_pack_promote.py`

### Files to edit
- prompt-pack manifest handling

### Files not to touch
- judge schema
- aggregation logic except for reading metadata if necessary

### Implementation notes
- Never edit an existing version in place.
- Promotion writes a new version with parent, proposal, and regression references.
- Active version switching should be simple and reversible.

### Tests required
- promotion requires a passing regression decision
- lineage metadata is persisted
- rollback path is explicit

### Done when
- a better prompt pack can be promoted and activated without mutating older versions

---

## Card PFL1-M5-B

Status: DONE.

### ID
`PFL1-M5-B`

### Goal
Connect regression logic to actual old-vs-new suite execution with prompt-pack selection.

### Why now
The current regression tool compares aggregate artifacts only. This card makes the comparison workflow real by running both versions against the same suite shape.

### Depends on
- `PFL1-M3-B`
- `PFL1-M5-A`

### Files to edit
- `tools/prompt_patch_regression.py`
- likely `tools/live_athlete_sim_runner.py` or a thin wrapper
- related regression tests

### Files not to touch
- prompt text content
- business logic
- judge schema

### Implementation notes
- Reuse existing suite-running infrastructure instead of creating a separate runner.
- Select base and proposed prompt-pack versions explicitly, likely through the existing env-driven loader path.
- Ensure both runs use identical suite config other than prompt-pack version.
- Aggregate both outputs through `tools/prompt_feedback_aggregate.py` or shared aggregation logic.
- Then apply the existing deterministic regression gate.

### Tests required
- both prompt-pack versions are exercised
- identical suite config is enforced across both runs
- generated regression report references actual aggregate outputs from both runs

### Done when
- one command can run base and proposed prompt-pack versions on the same suite config and produce a regression decision artifact

---

## Card PFL1-M6-B

Status: DONE.

### ID
`PFL1-M6-B`

### Goal
Add a top-level closed-loop workflow command that ties together proposal, dual suite execution, regression, and optional promotion.

### Why now
This is the last step needed to match the original end-to-end feedback loop shape rather than leaving the pieces as separate tools.

### Depends on
- `PFL1-M4-A`
- `PFL1-M5-B`
- `PFL1-M6-A`

### Files to add or edit
- likely a new workflow tool under `tools/`
- may edit:
  - `tools/prompt_patch_proposer.py`
  - `tools/prompt_patch_regression.py`
  - `tools/prompt_pack_promote.py`

### Files not to touch
- runtime business logic
- prompt-pack loader behavior unless strictly necessary

### Implementation notes
- The workflow may remain deterministic and file-based.
- Proposal generation can still be deterministic or human-reviewed.
- Promotion must remain gated on a passing regression decision.
- Keep the workflow explicit rather than overly clever.

### Tests required
- end-to-end workflow without promotion
- end-to-end workflow with promotion
- failing regression blocks promotion

### Done when
- the prompt feedback loop can run end to end with one workflow command from proposal through optional promotion

---

## Recommended Agent Assignment Pattern
- One agent per card.
- Do not assign overlapping write scopes in parallel.
- Safe parallelism examples:
  - `PFL1-M1-B` can run after `PFL1-M1-A`
  - `PFL1-M2-A` can run in parallel with `PFL1-M3-A`
- Avoid parallel work between:
  - `PFL1-M3-B` and any other card editing prompt loaders
  - `PFL1-M5-B` and any other card editing runner selection logic

---

## Review Checklist For Every Card
- Is the write scope narrow and respected?
- Are non-goals preserved?
- Does the task add or change exactly one contract?
- Are tests aligned with the contract?
- Does the change avoid hidden runtime behavior changes?

---

## Expected Use
Use this file as the direct input for coding agents. Use the epic for architectural context and the delivery plan for sequencing. Agents should not be asked to infer milestone order from the epic alone.
