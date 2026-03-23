# Prompt Feedback Loop Epic

Status: in progress.

This file describes a small, batch-based prompt improvement loop built on top of the existing live athlete simulator artifacts. It is a planned design record, not current runtime behavior.

## Context and Scope Boundaries
- The goal is to improve prompt and rubric quality using structured judge feedback from batch eval runs.
- The loop must be batch-based. The system must not self-edit after each individual conversation.
- Existing live athlete simulator artifacts are the starting point. This epic builds on them rather than replacing them.
- Prompt optimization is restricted to prompt-pack content only:
  - system prompt sections
  - coaching rubric text
  - retrieval instructions
  - few-shot examples
- Prompt optimization must not change:
  - business logic
  - rule engine logic
  - schemas unrelated to prompt artifacts
  - application code outside prompt-pack loading and orchestration
- YAGNI applies. Prefer the smallest implementation that closes the loop end to end.
- The first implementation should be deterministic wherever possible. Use LLM assistance only where structured semantic grouping or patch proposal is actually needed.
- Human review is allowed in the first versions. Full autonomous promotion is not required up front.

---

## Epic PFL1 — Batch Prompt Feedback Loop (Lite)

### Goal
Turn existing live athlete simulator judge outputs into a simple prompt improvement loop with five controlled stages:
- run suite
- aggregate recurring failures
- propose prompt-only changes
- rerun regression on old vs new prompt pack
- promote only when metrics are better

### Core Design
- The live athlete simulator JSONL attempt artifacts are the source of truth for optimization input.
- `results.json` remains a coarse run summary and should not be treated as the canonical source for optimizer inputs.
- Feedback aggregation is read-only and deterministic in the first version.
- Prompt optimization is versioned through prompt-pack artifacts, not by editing inline prompt strings ad hoc.
- Prompt-pack versions are immutable once written.
- Regression compares two prompt-pack versions on the same suite shape.
- Promotion is gated by explicit score and safety rules.
- The first implementation should support manual review between proposal and promotion.

### Stories

#### Story PFL1.1 — Batch Manifest and Aggregation Contract
As a developer, I need a deterministic batch aggregation step so recurring issues can be identified from existing live sim runs without manually reading raw transcripts.

Story DoD:
- [x] Add a standalone batch aggregation tool.
- [x] The tool accepts a live athlete simulator output directory as input.
- [x] The tool reads per-attempt `*.jsonl` files as the primary source.
- [x] The tool extracts every `judge_result` event.
- [x] The tool records, at minimum:
  - `scenario_id`
  - `attempt`
  - `turn`
  - `scores`
  - `what_missed`
  - `issue_tags`
  - `strength_tags`
  - `headline`
  - `athlete_likely_experience`
- [x] The tool writes a deterministic `aggregate.json` artifact.
- [x] The aggregation includes:
  - average scores overall
  - average scores by scenario
  - issue-tag counts
  - strength-tag counts
  - `what_missed` examples grouped by issue tag
  - source references back to scenario, attempt, and turn
- [x] The first implementation does not require any LLM clustering step.
- [x] The first implementation ignores `results.json` except for optional metadata display.

#### Story PFL1.2 — Judge Contract Extension for Corrected Example
As an optimizer pipeline, I need the judge output to optionally include a compact improved example so later prompt proposals can use rewrite evidence instead of complaint text alone.

Story DoD:
- [x] Extend the live judge contract with one optional short-form corrected-example field.
- [x] The field name is explicit and stable.
- [x] The field is optional so existing runs remain valid.
- [x] Validation accepts runs with or without the field.
- [x] The aggregation step captures the field when present.
- [x] The field is constrained to a short example and is not treated as a full policy rewrite.

#### Story PFL1.3 — Prompt-Pack Versioning Layer
As a system maintainer, I need editable prompt surfaces moved into versioned prompt-pack artifacts so prompt optimization can be constrained to allowed files and rolled back safely.

Story DoD:
- [x] Introduce a prompt-pack directory for coach-reply prompt artifacts.
- [x] Version `v1` exists and preserves current runtime behavior.
- [x] Prompt-pack content is file-based and versioned.
- [x] The first prompt pack includes at least:
  - response-generation system prompt content
  - coaching-reasoning prompt content
- [x] A prompt-pack manifest defines:
  - version
  - created_at
  - parent_version
  - editable surfaces
  - optional notes
- [x] Runtime prompt loading reads from the active prompt pack rather than hardcoded inline strings alone.
- [x] Existing behavior remains unchanged after the refactor.
- [x] Prompt optimization is limited to prompt-pack content only.

#### Story PFL1.4 — Prompt Patch Proposal Contract
As a prompt optimizer pipeline, I need a structured proposal artifact so suggested prompt changes are reviewable and constrained before any promotion happens.

Story DoD:
- [x] Add a standalone prompt proposal tool.
- [x] The proposal tool consumes:
  - an aggregate feedback artifact
  - a base prompt-pack version
- [x] The proposal tool writes a structured `proposal.json` artifact.
- [x] The proposal contract includes:
  - base version
  - proposed version
  - target surfaces
  - rationale
  - expected benefit
  - risks
  - exact text patch operations or replacement sections
- [x] Every proposal change references the issue tags or recurring misses it is intended to address.
- [x] The proposal tool is not allowed to edit code or business logic.
- [x] The first implementation may require human review before applying a proposal.

#### Story PFL1.5 — Old vs New Regression Gate
As a maintainer, I need explicit regression checks so prompt changes only promote when they improve quality without reducing safety or breaking known strengths.

Story DoD:
- [x] Add a regression runner that compares a base prompt-pack version against a proposed prompt-pack version.
- [x] The regression runner executes the same suite shape for both versions.
- [x] The regression runner aggregates both result sets using the same aggregation logic.
- [x] The regression report includes:
  - overall average score comparison
  - per-dimension score comparison
  - issue-tag delta
  - strength-tag delta
  - promotion decision
  - failed gates
- [x] Promotion gates require, at minimum:
  - average score improvement
  - no safety score drop
  - no material regression on protected strengths or dimensions already working
- [x] The first implementation keeps gates explicit and simple rather than statistically sophisticated.

#### Story PFL1.6 — Versioned Promotion and Metrics Persistence
As a system operator, I need prompt-pack promotion to write immutable versioned artifacts with metrics so improvements are auditable and reversible.

Story DoD:
- [x] Add a promotion step that only runs after a successful regression report.
- [x] Promotion creates a new immutable prompt-pack version rather than editing an existing version in place.
- [x] Each promoted version stores:
  - parent version
  - source proposal artifact
  - source regression report
  - metrics summary
  - created_at
- [x] The promoted version can be marked active through a simple runtime selection mechanism.
- [x] The implementation supports rollback by switching the active version back to an earlier prompt pack.

### Epic PFL1 DoD
- [x] The system can run a batch eval suite and produce reusable batch artifacts.
- [x] The system can aggregate recurring failures from per-attempt JSONL judge outputs.
- [x] The system can optionally capture a corrected-example field from the judge.
- [x] Editable prompt surfaces are versioned in prompt-pack artifacts.
- [x] Prompt optimization is constrained to prompt-pack files only.
- [x] The system can generate a structured prompt-change proposal from aggregated feedback.
- [x] The system can compare old vs new prompt-pack versions on the same suite shape.
- [x] The system promotes a prompt-pack version only when improvement gates pass.
- [x] Prompt-pack versions persist metrics and lineage metadata.
- [x] The implementation remains batch-based and does not self-edit after every conversation.

### Implementation Notes
- Start from the existing artifact shape in `sam-app/.cache/live-athlete-sim/<timestamp>/`.
- Treat each attempt JSONL file as canonical because it contains turn-level `judge_result` events and richer evidence than `results.json`.
- Keep the first aggregation pass deterministic and tag-based. Do not add semantic clustering until basic aggregation is already useful.
- If semantic clustering is added later, it should sit on top of the deterministic aggregate output rather than replacing it.
- Keep the first prompt-pack small. Only move the prompt surfaces that actually need optimization.
- Preserve current behavior when introducing prompt-pack loading. This refactor is infrastructure, not behavior change.
- Keep proposal artifacts explicit enough that a human can review:
  - what changed
  - why it changed
  - which recurring failures it targets
- The first promotion workflow can remain partially manual. Automatic promotion is not required for the initial implementation.
- Simple gates are better than clever gates in the first version.
- Keep safety as a hard gate, not a weighted tradeoff.
- Protect already-working strengths such as continuity and tone from regression, even if another dimension improves slightly.
- Avoid overfitting to one scenario or one lucky batch. Batch size and suite shape should be visible in the regression report.
- The first implementation does not need:
  - a database
  - a generalized optimizer service
  - online learning
  - per-conversation adaptation
- A useful first milestone is read-only:
  - aggregate a real run
  - identify recurring issues
  - produce a reviewable proposal artifact
- Suggested implementation order:
  - build aggregation
  - extend judge contract with optional corrected example
  - introduce prompt-pack versioning with no behavior change
  - build proposal artifact generation
  - build regression compare
  - build promotion

### Suggested File Plan
- `tools/prompt_feedback_aggregate.py`
- `tools/prompt_patch_proposer.py`
- `tools/prompt_patch_regression.py`
- `tools/prompt_pack_promote.py`
- `sam-app/email_service/test_prompt_feedback_aggregate.py`
- `sam-app/email_service/test_prompt_patch_proposer.py`
- `sam-app/email_service/test_prompt_patch_regression.py`
- `sam-app/email_service/prompt_packs/coach_reply/v1/manifest.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json`
- `sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json`

### Minimal Runtime Function Shape
- `runSuite(config) -> BatchManifest`
- `aggregateFeedback(batch_manifest) -> AggregateFeedbackReport`
- `proposePromptPatch(aggregate_report, prompt_pack_version) -> PromptPatchProposal`
- `rerunRegression(base_version, proposed_version, suite_config) -> RegressionReport`
- `promoteIfBetter(regression_report) -> PromptPackVersion | None`

### Minimal Artifact Shape
- `BatchManifest`
  - `run_id`
  - `output_dir`
  - `bench_path`
  - `prompt_pack_version`
  - `attempt_files`
- `AggregateFeedbackReport`
  - `run_id`
  - `prompt_pack_version`
  - `average_scores`
  - `score_by_scenario`
  - `issue_tag_counts`
  - `strength_tag_counts`
  - `misses_by_issue_tag`
  - `examples`
- `PromptPatchProposal`
  - `base_version`
  - `proposed_version`
  - `changes`
  - `notes`
- `RegressionReport`
  - `base_version`
  - `proposed_version`
  - `base_metrics`
  - `proposed_metrics`
  - `decision`
  - `failed_gates`

### Step-by-Step Build Order
1. Implement `prompt_feedback_aggregate.py` and its tests.
2. Add the optional judge corrected-example field and tests.
3. Extract response-generation and coaching-reasoning prompts into prompt-pack `v1` with no behavior change.
4. Implement `prompt_patch_proposer.py` and its tests.
5. Implement `prompt_patch_regression.py` and its tests.
6. Implement `prompt_pack_promote.py`.

---

## Non-Goals
- Per-conversation prompt self-editing.
- Real-time online learning.
- Automatic code or business-logic mutation.
- A generalized autonomous prompt optimization platform.
- Statistical significance machinery in the first version.
- Replacing the existing live athlete simulator runner.
- Broad retrieval-system redesign unless implementation proves a prompt-surface split is required.

---

## Expected Result
After Epic PFL1 is implemented, the system should be able to:
- run a batch eval suite and retain structured judge feedback,
- identify recurring prompt-level failures from existing live artifacts,
- generate constrained prompt-only proposals,
- compare old vs new prompt versions safely, and
- promote better prompt packs without introducing self-editing behavior or code mutation.
