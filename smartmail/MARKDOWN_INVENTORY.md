# Markdown Inventory

Purpose: categorize Markdown files in this repo for cleanup, archiving, and LLM-agent context management.

## Category Definitions

- `LLM-useful`: current docs that materially help an agent understand architecture, constraints, specs, test surfaces, or prompt assets.
- `TBD / active planning`: planned, in-progress, or backlog docs that still drive future implementation work.
- `Stale / historical`: retired, completed, archived, or date-bound docs that should not drive new implementation directly.
- `Generated / third-party`: build outputs, cached summaries, or license files. Exclude from doc reviews and agent context by default.

## LLM-useful

These are the highest-value files to keep available when asking an agent to change code.

| File | Why it is useful |
|---|---|
| `AGENTS.md` | Merge-bar commands, inner loop, implementation discipline; points to [`CLAUDE.md`](CLAUDE.md) for invariants. |
| `CLAUDE.md` | Root working guide and invariants. |
| `sam-app/README.md` | Best current runtime overview and document map. |
| `sam-app/DECISIONS.md` | Durable architectural decisions. |
| `sam-app/EMAIL_COPY_MAP.md` | Source-of-truth map for outbound copy and prompt-owned text. |
| `sam-app/CLAUDE.md` | Build, deploy, and data reference. |
| `sam-app/email_service/CLAUDE.md` | Pipeline and module map for the main service. |
| `sam-app/email_service/TEST_COVERAGE.md` | Test surface map and gaps. |
| `sam-app/email_service/OBEDIENCE_LAYER_OWNERSHIP.md` | Ownership model for last-mile obedience failures. |
| `sam-app/tests/e2e/README.md` | Live E2E setup and constraints. |
| `test_bench/plan_test_bench.md` | Planner fixture contract and scenarios. |
| `test_bench/intent_classification_test_bench.md` | Intent-classification fixture contract. |
| `test_bench/athlete_memory_test_bench.md` | Short-horizon memory fixture contract. |
| `test_bench/athlete_memory_long_horizon_bench.md` | Long-horizon memory fixture contract. |
| `test_bench/athlete_agent_bench.md` | Live athlete-sim benchmark and judge rubric. |
| `test_bench/response_generation_quality_bench.md` | Realistic response-generation review set. |
| `test_bench/last_mile_obedience_classification.md` | Failure taxonomy for obedience issues. |
| `.cursor/skills/deslop/SKILL.md` | Agent workflow for de-slopping code in this repo. |
| `.cursor/skills/deslop/references/slop-signals.md` | Reference for identifying code bloat. |
| `.cursor/skills/intent-debugger/SKILL.md` | Agent workflow for local intent debugging. |
| `.cursor/skills/user-story-creator/SKILL.md` | Story-authoring workflow for SmartMail. |
| `.cursor/skills/user-story-creator/references/story-format-reference.md` | Required story shape. |
| `.cursor/skills/user-story-creator/references/llm-story-requirements.md` | LLM-specific story constraints. |
| `.cursor/skills/user-story-creator/references/smartmail-invariants.md` | Security/concurrency/observability invariants. |
| `sam-app/email_service/skills/CLAUDE.md` | Skill package structure and status. |
| `sam-app/email_service/skills/memory/CLAUDE.md` | Memory subsystem architecture. |
| `sam-app/email_service/skills/response_generation/CLAUDE.md` | Response-generation skill map. |
| `sam-app/email_service/skills/coaching_reasoning/doctrine/**/*.md` | Active doctrine/prompt assets used by coaching reasoning. |

## TBD / active planning

These should not be treated as implemented truth, but they still matter for roadmap and near-term work.

| File | Why it is TBD / active |
|---|---|
| `bug-backlog.md` | Active bug list with current desired behavior and verification notes. |

## Stale / historical

These should not be used as the main instruction source for new implementation.

| File | Why it is stale / historical |
|---|---|
| `archive/BACKLOG.md` | Explicitly marked `historical/foundational backlog`; README says not for current prioritization. |
| `archive/athlete-memory-epic.md` | Historical implementation record for athlete memory and continuity. |
| `archive/athlete-memory-epic-m2.md` | Historical planned follow-up epic; no longer treated as active planning authority. |
| `archive/bug19-memory-design-proposal.md` | Historical memory redesign design proposal. |
| `archive/doctrine-improvement-plan.md` | Explicitly retired; superseded by archived `archive/doctrine-refactoring.md`. |
| `archive/doctrine-redesign.md` | Explicitly retired; superseded by archived `archive/doctrine-refactoring.md`. |
| `archive/doctrine-refactoring.md` | Doctrine implementation plan; moved to archive as historical reference. |
| `archive/group1-memory-handoff.md` | Historical handoff notes. |
| `archive/handover19.md` | Historical handoff notes. |
| `archive/intent_clasification_refactroing.md` | Historical routing/refactor plan. |
| `archive/major-refactoring.md` | Historical refactoring brief; no longer treated as active planning authority. |
| `archive/memory-redesign-implementation-plan.md` | Historical memory redesign implementation plan. |
| `archive/prompt-feedback-loop-delivery-plan.md` | Historical prompt-feedback-loop delivery sequencing. |
| `archive/prompt-feedback-loop-epic.md` | Historical epic; was in-progress planning, now archived. |
| `archive/prompt-feedback-loop-task-cards.md` | Historical task breakdown. |
| `archive/remaining-groups-handoff.md` | Historical handoff notes. |
| `archive/response-generation-epic.md` | Historical response-generation design; not current production behavior. |
| `archive/rule-engine-epic.md` | Historical implementation record for rule-engine work; no longer treated as active guidance. |
| `archive/run-prompt-feedback-loop-implementation-task.md` | Historical implementation task spec. |
| `archive/run-prompt-feedback-loop-spec.md` | Historical closed-loop spec. |
| `archive/sim-improvement.md` | Historical reliability plan for the athlete simulator. |
| `archive/spec.md` | Former rule-engine spec; archived because it is no longer accurate enough to be authoritative. |
| `archive/continuity-state-implementation-plan.md` | Marked `DONE`; historical implementation record. |
| `archive/last-mile-obedience-implementation-plan.md` | Marked `DONE`; historical implementation record. |
| `archive/sam-app/email_service/current-context.md` | Date-bound session snapshot (`Last updated: 2026-03-19`); useful only as temporary local context, not durable repo guidance. |
| `archive/advanced-rule-engine.md` | Archived speculative design input; not source of truth. |
| `archive/coach-spec.md` | Archived parallel design doc; use only for historical reference. |

## Generated / third-party

These should usually be excluded from cleanup decisions, search, and LLM context windows.

| Path pattern | Notes |
|---|---|
| `sam-app/.aws-sam/**/*.md` | Build artifacts and copied docs. |
| `sam-app/.cache/**/*.md` | Generated benchmark summaries and run artifacts. |
| `sam-app/vendor/**/*.md` | Third-party license files. |
| `sam-app/.aws-sam/deps/**/*.md` | Third-party license files copied into build deps. |

## Recommended Manipulation Order

1. Archive or clearly banner the stale/historical files so they stop competing with active docs.
2. Keep the `LLM-useful` set concise and current; these are the files worth prioritizing in agent prompts and repo navigation.
3. For each `TBD / active planning` file, either keep it actively maintained or demote it to historical once superseded.
4. Exclude `Generated / third-party` paths from future doc audits and agent indexing by default.

## Borderline Cases

- `archive/advanced-rule-engine.md`: archived because it is speculative and may conflict with current architecture.
- `archive/coach-spec.md`: archived because it acts as a parallel design doc rather than current implementation authority.
