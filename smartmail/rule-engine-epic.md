# Rule Engine Implementation Epics and User Stories

## Context and Scope Boundaries
- Epic 1 and Epic 2 in [BACKLOG.md](/Users/levonsh/Projects/smartmail/BACKLOG.md) are treated as already implemented foundations.
- This document starts at deterministic rule-engine + AI-assisted planning integration.
- Stories are intentionally atomic and designed to minimize net-new code per story.
- If a story grows, it should be split before implementation.
- LLM-as-a-judge is intentionally deferred (placeholder only).

---

## Epic RE1 — Deterministic State Machine Core

### Goal
Implement the core state machine decisions (phase, risk, track) from [spec.md](/Users/levonsh/Projects/smartmail/spec.md) with deterministic outputs.

### Stories

#### Story RE1.1 — Add Rule-Engine Enums and Output Contract
As a developer, I need a single canonical type/enum contract for phase, risk, track, and plan update status so the engine cannot emit invalid states.

Story DoD:
- [ ] Canonical constants/types added for `phase`, `risk_flag`, `track`, `plan_update_status`.
- [ ] Engine output contract includes required fields only (no speculative fields).
- [ ] Unit test validates enum membership and output schema shape.

#### Story RE1.2 — Event Date Validation + Clarification Status
As a coach system, I need invalid/missing/past event dates to be ignored for routing and flagged for clarification so phase logic stays safe.

Story DoD:
- [ ] Validation function returns `valid | invalid_missing | invalid_format | invalid_past`.
- [ ] Invalid date paths set `plan_update_status=unchanged_clarification_needed` and avoid re-phasing.
- [ ] Unit tests cover all validation outcomes.

#### Story RE1.3 — Phase Derivation with Priority-Based Conservative Override
As a coaching engine, I need calendar phase + override priority (`red_b > red_a > return-context > yellow > new`) so transitions are deterministic.

Story DoD:
- [ ] Base calendar windows implemented: `base >12w`, `build 4-12w`, `peak_taper 0-3w`.
- [ ] Override caps applied with exact priority and cap behavior.
- [ ] Tests cover boundary weeks (`12/4/3`) and precedence collisions.

#### Story RE1.4 — Inconsistent-Training Stabilization
As a coaching engine, I need phase-upgrade hysteresis so week-to-week oscillation does not cause noisy plan shifts.

Story DoD:
- [ ] Detect flip conditions without red-tier trigger.
- [ ] Require 2 consecutive qualifying check-ins before phase upgrade.
- [ ] Downgrades on safety triggers remain immediate.

#### Story RE1.5 — Risk Derivation (`green/yellow/red_a/red_b`)
As a safety layer, I need risk tiering from check-in signals so downstream planning follows coaching boundaries.

Story DoD:
- [ ] `red_b` and `red_a` criteria implemented exactly per spec.
- [ ] `yellow` fallback logic excludes red-tier cases.
- [ ] Tests verify mutually exclusive tier assignment.

#### Story RE1.6 — Track Selection + Risk-Managed Override
As a planner, I need stable track routing with risk override so recommendations stay coherent with safety state.

Story DoD:
- [ ] Track selection works for general and main-sport paths.
- [ ] `return_or_risk_managed` override applied for `return_to_training` or red-tier risk.
- [ ] Tests verify precedence and expected track per scenario.

### Epic RE1 Lightweight DoD
- [ ] All RE1 stories merged with passing unit tests for phase/risk/track/status.
- [ ] Deterministic same-input/same-output behavior verified.
- [ ] No regression to existing onboarding/profile/plan persistence behavior.

---

## Epic RE2 — Weekly Skeleton Builder (Deterministic)

### Goal
Generate weekly session skeletons that obey time bucket, risk rules, and feasibility constraints.

### Stories

#### Story RE2.1 — General Fitness Skeleton Templates by Time Bucket
As a planner, I need deterministic general-fitness templates (`2_3h`, `4_6h`, `7_10h`, `10h_plus`) so outputs are predictable.

Story DoD:
- [ ] Templates implemented per spec including `10h_plus` controlled add-ons.
- [ ] Intensity in general fitness allowed only with green + explicit performance intent.
- [ ] Tests verify session mix/count per bucket.

#### Story RE2.2 — Main Sport Skeleton Templates by Time Bucket
As a planner, I need main-sport templates mapped by time bucket and risk rules so sessions align with phase and constraints.

Story DoD:
- [ ] Templates implemented for `2_3h`, `4_6h`, `7_10h`, `10h_plus`.
- [ ] `10h_plus` second quality session guarded by experience + green + stable schedule.
- [ ] Tests verify quality-session gating.

#### Story RE2.3 — Risk-Based Skeleton Overrides
As a safety layer, I need red/yellow/green override application on any skeleton so unsafe intensity is removed.

Story DoD:
- [ ] `red_a/red_b`: remove intensity, low-impact swap, volume reduction.
- [ ] `yellow`: intensity reduction without full collapse.
- [ ] Safety regression test proves red-tier never emits intensity.

#### Story RE2.4 — Infeasible Week Handling (No Plan Replacement)
As a planner, I need infeasible weeks to keep existing plan unchanged so the system avoids generating non-viable plans.

Story DoD:
- [ ] Infeasible condition detection implemented (`days_available<=1` or no viable sessions).
- [ ] Output sets `plan_update_status=unchanged_infeasible_week`.
- [ ] Existing plan object remains unchanged in this path.

### Epic RE2 Lightweight DoD
- [ ] Weekly skeleton generation is deterministic and risk-compliant.
- [ ] Infeasible and clarification paths never overwrite active plan.
- [ ] Existing plan history/versioning behavior remains intact.

---

## Epic RE3 — Session Routing and Email-Ready Actions

### Goal
Route daily/weekly adjustments from check-in signals and produce coherent coaching actions.

### Stories

#### Story RE3.1 — Signal Router (Pain -> Energy -> Missed -> Chaos)
As a coach engine, I need ordered signal routing so the highest-safety signal always wins first.

Story DoD:
- [ ] Routing order enforced exactly: pain, energy, missed sessions, schedule chaos.
- [ ] `red_b` emits clinician guidance; `red_a` emits monitor/update guidance.
- [ ] Tests verify branch precedence and action output.

#### Story RE3.2 — Big-2 Anchor Prioritization for Chaotic Weeks
As an athlete, I need minimal viable priorities in chaotic weeks so I can stay consistent without overload.

Story DoD:
- [ ] Big-2 anchor logic implemented (long easy + strength/mobility fallback).
- [ ] Output clearly marks anchors as top priority.
- [ ] Tests verify chaotic-week output downgrades correctly.

#### Story RE3.3 — Track/Message Consistency Guard
As a user, I need message language consistent with safety track so coaching advice is not contradictory.

Story DoD:
- [ ] `return_or_risk_managed` suppresses peak/performance phrasing.
- [ ] Email payload includes safety/consistency framing.
- [ ] Tests assert no contradictory language tokens in risk-managed path.

### Epic RE3 Lightweight DoD
- [ ] Session routing produces one clear `today_action` per check-in.
- [ ] Safety-first ordering is enforced.
- [ ] Messaging consistency checks pass for risk-managed scenarios.

---

## Epic RE4 — AI-Assisted Planning (Constrained by Rules)

### Goal
Use AI for plan construction/adaptation quality while keeping deterministic rule engine as final authority.

### Stories

#### Story RE4.1 — Structured Input Extractor with Confidence
As a system, I need AI to parse free-text check-ins into structured signals with confidence so rule inputs are usable.

Story DoD:
- [ ] Extractor returns required weekly fields + per-field confidence.
- [ ] Low-confidence critical fields trigger clarification path (no unsafe state transition).
- [ ] Tests include ambiguous pain/event-date examples.

#### Story RE4.2 — Planner Contract from Rule Output (`hard_limits`)
As a planner, I need AI generation constrained by rule-engine outputs so plans remain compliant.

Story DoD:
- [ ] Rule engine emits explicit `hard_limits` and weekly targets for planner input.
- [ ] Planner prompt/context includes only allowed session budget/intensity constraints.
- [ ] Tests verify planner input contract presence and completeness.

#### Story RE4.3 — Plan Validator and Auto-Repair
As a safety layer, I need validation of AI-generated plans so non-compliant plans are rejected or repaired before send.

Story DoD:
- [ ] Validator checks intensity budget, spacing, risk constraints, and track compatibility.
- [ ] Invalid outputs are repaired deterministically or downgraded to fallback template.
- [ ] Tests verify reject/repair behavior.

#### Story RE4.4 — Flexibility Mode Output Formatter
As an athlete preferring flexibility, I need anchor/filler/optional menu output instead of strict sequence.

Story DoD:
- [ ] Formatter emits 2 anchors, 1-2 fillers, 1 optional session format.
- [ ] Enforces no back-to-back hard days and max hard-session budget.
- [ ] Tests verify menu structure and constraints.

### Epic RE4 Lightweight DoD
- [ ] AI planner cannot bypass deterministic safety/rule constraints.
- [ ] Low-confidence parsing cannot trigger unsafe transitions.
- [ ] Flexible and structured outputs both validate successfully.

---

## Epic RE5 — Open Follow-Ups and Placeholders

### Goal
Track deferred items without blocking core implementation.

### Stories

#### Story RE5.1 — Mixed-Signal Resolution Policy Placeholder
As a team, we need a placeholder for wearable-vs-email conflicts so implementation can proceed while policy is undecided.

Story DoD:
- [ ] Placeholder section added and linked to [follow-up.md](/Users/levonsh/Projects/smartmail/follow-up.md).
- [ ] No production logic added for mixed-signal arbitration yet.
- [ ] Open questions documented with examples.

#### Story RE5.2 — LLM-as-a-Judge Placeholder (Deferred)
As a team, we need a backlog placeholder for judge-scoring so we can defer this work explicitly.

Story DoD:
- [ ] Placeholder story exists with "deferred" status.
- [ ] Non-goal states judge does not gate deterministic safety decisions.
- [ ] No code changes required in this epic.

### Epic RE5 Lightweight DoD
- [ ] Deferred topics are documented and visible to future implementation passes.
- [ ] No accidental scope creep into deferred logic.

---

## Suggested Implementation Sequence (Low Risk)
1. Epic RE1
2. Epic RE2
3. Epic RE3
4. Epic RE4
5. Epic RE5 (documentation placeholders only)

This order keeps deterministic safety/state logic in place before any AI planning behavior is expanded.
