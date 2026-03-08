# Rule Engine Implementation Epics and User Stories

## Context and Scope Boundaries
- Epic 1 and Epic 2 in [BACKLOG.md](/Users/levonsh/Projects/smartmail/BACKLOG.md) are treated as implemented foundations.
- [spec.md](/Users/levonsh/Projects/smartmail/spec.md) is the source of truth for rule behavior.
- RE1 in this file is intentionally clean and complete (no follow-up split).
- Stories remain atomic; if a story expands, split it before implementation.
- LLM-as-a-judge remains deferred.

---

## Epic RE1 — Deterministic State Machine Core (Clean)

### Goal
Implement and stabilize deterministic rule-engine foundations: contracts, derivation rules, trend state, safety gates, and compatibility normalization.

### Stories

#### Story RE1.1 — Canonical Enums and Output Contract
As a developer, I need a canonical contract for phase, risk, track, plan status, and payload shape so engine outputs are valid and deterministic.

Story DoD:
- [x] Canonical constants/types exist for `phase`, `risk_flag`, `track`, `plan_update_status`.
- [x] Output contract validates required fields and rejects unknown fields.
- [x] Contract tests cover enum membership, schema round-trip, and strict validation.

#### Story RE1.2 — Event Date Validation + Clarification Status
As a coaching engine, I need safe handling for missing/invalid/past event dates so phase routing does not misfire.

Story DoD:
- [x] Event date validator returns `valid | invalid_missing | invalid_format | invalid_past`.
- [x] Invalid date paths preserve prior phase and set clarification status.
- [x] Tests cover all date statuses and guard behavior.

#### Story RE1.3 — Performance Intent Contract + Resolver
As a planner, I need explicit performance-intent fields and fallback resolution so intensity gating is deterministic.

Story DoD:
- [x] `performance_intent_default` and `performance_intent_this_week` are in contract.
- [x] Resolver implements fallback chain (`this_week -> profile -> false`).
- [x] Tests cover all fallback permutations and invalid inputs.

#### Story RE1.4 — Rule State Contract (Rolling History)
As a rules engine, I need a minimal persisted `rule_state` model to support trend logic and hysteresis.

Story DoD:
- [x] `rule_state` schema defined (`last_4`, `last_6`, deload counter, upgrade streak, switch state).
- [x] `load_rule_state()` and `update_rule_state()` contracts defined.
- [x] Tests cover empty bootstrap and rolling-window capping.

#### Story RE1.5 — Phase Derivation with Ordered Overrides
As a phase engine, I need deterministic phase derivation with explicit precedence rules.

Story DoD:
- [x] Calendar windows implemented (`base`, `build`, `peak_taper`).
- [x] Hard return context precedence implemented.
- [x] Conservative override order implemented (`red_b > red_a > return-context > yellow > new`).
- [x] `derive_phase` consumes derived `risk_flag` and `effective_performance_intent`.
- [x] Boundary tests and precedence collision tests pass.

#### Story RE1.6 — Return Context Inputs + Event Expectation Rules
As a phase engine, I need explicit return/event inputs to avoid ambiguous text inference.

Story DoD:
- [x] Added `has_upcoming_event`, `returning_from_break`, `recent_illness`, optional `break_days`.
- [x] Hard return triggers: `returning_from_break` OR `recent_illness=significant` OR `break_days>=10`.
- [x] Event expectation uses `has_upcoming_event`; null falls back to profile `goal_category`, never free text.
- [x] Tests cover explicit and derived paths.

#### Story RE1.7 — Risk Derivation + Deterministic Worsening
As a safety layer, I need unambiguous risk classification including trend escalation.

Story DoD:
- [x] `green/yellow/red_a/red_b` derivation implemented.
- [x] Yellow thresholds are explicit (`energy<=4`, `stress>=8`, `sleep<=4`, `stress>=7 && energy<=5`).
- [x] Deterministic worsening definition implemented for red escalation.
- [x] Red-tier precedence over yellow verified by tests.

#### Story RE1.8 — Inconsistent-Training Stabilization
As a coaching engine, I need anti-oscillation behavior so phases do not churn week-to-week.

Story DoD:
- [x] Flip detection without red-tier trigger implemented.
- [x] Upgrades require 2 consecutive qualifying check-ins.
- [x] Safety downgrades apply immediately.
- [x] Tests validate hysteresis and immediate downgrade behavior.

#### Story RE1.9 — Track Selection + Risk-Managed Override
As a planner, I need stable track routing with explicit safety override precedence.

Story DoD:
- [x] Track routing for general/main-sport paths implemented.
- [x] `return_or_risk_managed` override applied for return-to-training and red-tier risk.
- [x] Precedence and fallback tests pass.

#### Story RE1.10 — Main Sport Switching Guardrails
As a planner, I need anti-churn switching policy for hybrid athletes.

Story DoD:
- [x] Switch only on explicit request or `>=60%` alternate sport over 2 weeks with `>=120` minutes.
- [x] Transition guard enforces `<=1` quality session/week and `<=10%` weekly volume increase.
- [x] Post-switch freeze for 2 weeks except explicit request or `red_b` safety override.
- [x] Tests validate thresholds, freeze, and transition limits.

#### Story RE1.11 — Main-Sport Deload Trigger Rules
As a training engine, I need explicit deload logic for main-sport paths.

Story DoD:
- [x] Deload triggers at 3-5 week cadence and on sustained yellow (`2 consecutive` or `3 of last 4`).
- [x] Deload adjustments reduce volume and remove one quality session.
- [x] Taper precedence over standard deload verified by tests.

#### Story RE1.12 — Experience-Based Quality Archetypes
As a planner, I need deterministic quality templates by athlete experience.

Story DoD:
- [x] Archetypes exist for `new`, `intermediate`, `advanced`.
- [x] Risk/schedule gates applied to archetype selection.
- [x] Tests verify selection and suppression behavior.

#### Story RE1.13 — Payload Required Components + Hard Session Tags
As a message layer, I need stable output quality and enforceable intensity semantics.

Story DoD:
- [x] Required payload fields enforced (`plan_focus_line`, `technique_cue`, `recovery_target`, `if_then_rules`, `disclaimer_short`).
- [x] `red_b` requires non-empty disclaimer.
- [x] Hard-session tags are defined and validated for intensity budgeting.
- [x] Contract tests fail on missing required fields.

#### Story RE1.14 — Naming Canonicalization + Backward Compatibility
As a platform maintainer, I need canonical names with legacy normalization.

Story DoD:
- [x] Canonical track names enforced (`main_base`, `main_build`, `main_peak_taper`, etc.).
- [x] Goal field semantics standardized around `goal_category`.
- [x] Legacy aliases normalize correctly at contract boundary.
- [x] Compatibility tests pass.

### Epic RE1 Lightweight DoD
- [x] Deterministic same-input/same-output behavior validated.
- [x] Safety precedence and fallback behavior covered by automated tests.
- [x] Backward compatibility for legacy payloads/names is preserved.
- [x] No regressions in existing profile/plan/persistence flows.

---

## Epic RE2 — Weekly Skeleton Builder (Deterministic)

### Goal
Generate weekly skeletons that obey time bucket, risk constraints, intent gating, and feasibility rules.

### Stories

#### Story RE2.1 — General Fitness Skeleton Templates by Time Bucket
As a planner, I need deterministic general-fitness templates (`2_3h`, `4_6h`, `7_10h`, `10h_plus`) so outputs are predictable.

Story DoD:
- [x] Templates implemented per spec including `10h_plus` controlled add-ons.
- [x] Intensity in general fitness allowed only with green + `effective_performance_intent`.
- [x] Tests verify session mix/count per bucket.

#### Story RE2.2 — Main Sport Skeleton Templates by Time Bucket
As a planner, I need main-sport templates mapped by time bucket and risk rules so sessions align with phase and constraints.

Story DoD:
- [x] Templates implemented for `2_3h`, `4_6h`, `7_10h`, `10h_plus`.
- [x] `10h_plus` second quality session guarded by experience + green + stable schedule.
- [x] Tests verify quality-session gating.

#### Story RE2.3 — Risk-Based Skeleton Overrides
As a safety layer, I need red/yellow/green override application on any skeleton so unsafe intensity is removed.

Story DoD:
- [x] `red_a/red_b`: remove intensity, low-impact swap, volume reduction.
- [x] `yellow`: intensity reduction without full collapse.
- [x] Safety regression test proves red-tier never emits intensity.

#### Story RE2.4 — Infeasible Week Handling (No Plan Replacement)
As a planner, I need infeasible weeks to keep existing plan unchanged so the system avoids generating non-viable plans.

Story DoD:
- [x] Infeasible condition detection implemented (`days_available<=1` or no viable sessions).
- [x] Output sets `plan_update_status=unchanged_infeasible_week`.
- [x] Existing plan object remains unchanged in this path.

#### Story RE2.5 — Integrate RE1 Decisions Into Skeleton Assembly
As a planner, I need RE1 switching, deload, and archetype decisions consumed by skeleton assembly so helper logic affects emitted plans.

Story DoD:
- [x] `should_switch_main_sport` is consumed during plan assembly.
- [x] Deload decisions are applied before final session mix emission.
- [x] Quality archetypes are selected via RE1 helpers/contracts (not ad-hoc logic).
- [x] Integration tests verify RE1 decision outputs are reflected in emitted skeletons.

### Epic RE2 Lightweight DoD
- [x] Weekly skeleton generation is deterministic and risk-compliant.
- [x] Infeasible and clarification paths never overwrite active plan.
- [x] Existing plan history/versioning behavior remains intact.
- [x] RE1 decisions are consumed by the orchestrator path.

---

## Epic RE3 — Session Routing and Email-Ready Actions

### Goal
Route daily/weekly adjustments from check-in signals and produce coherent coaching actions.

### Stories

#### Story RE3.1 — Signal Router (Pain -> Energy -> Missed -> Chaos)
As a coach engine, I need ordered signal routing so the highest-safety signal always wins first.

Story DoD:
- [x] Routing order enforced exactly: pain, energy, missed sessions, schedule chaos.
- [x] `red_b` emits clinician guidance; `red_a` emits monitor/update guidance.
- [x] Tests verify branch precedence and action output.

#### Story RE3.2 — Big-2 Anchor Prioritization for Chaotic Weeks
As an athlete, I need minimal viable priorities in chaotic weeks so I can stay consistent without overload.

Story DoD:
- [x] Big-2 anchor logic implemented (long easy + strength/mobility fallback).
- [x] Output clearly marks anchors as top priority.
- [x] Tests verify chaotic-week output downgrades correctly.

#### Story RE3.3 — Track/Message Consistency Guard
As a user, I need message language consistent with safety track so coaching advice is not contradictory.

Story DoD:
- [x] `return_or_risk_managed` suppresses peak/performance phrasing.
- [x] Email payload includes safety/consistency framing.
- [x] Tests assert no contradictory language tokens in risk-managed path.

#### Story RE3.4 — Integrate RE1 Payload + Naming Contracts Into Final Emission
As a messaging layer, I need RE1 payload requirements and canonical naming enforced in the final response path.

Story DoD:
- [x] Payload validator enforces required output fields before send.
- [x] `red_b` path always includes mandatory `disclaimer_short`.
- [x] Canonical naming is applied before serialization and logging.
- [x] Integration tests verify end-to-end payload compliance and legacy-name compatibility.

### Epic RE3 Lightweight DoD
- [x] Session routing produces one clear `today_action` per check-in.
- [x] Safety-first ordering is enforced.
- [x] Messaging consistency checks pass for risk-managed scenarios.
- [x] RE1 payload/naming contracts are enforced in final payload emission.

---

## Epic RE4 — AI-Assisted Planning (Bounded by Deterministic Rules)

### Goal
Use separate language-LLM and planning-LLM modules to improve extraction, plan quality, and reply quality while keeping the deterministic rule engine as final authority for state, safety, validation, and fallback.

### Stories

#### Story RE4.1 — Language LLM Structured Input Extractor with Confidence
As a system, I need a language LLM to parse free-text check-ins into structured signals with confidence so rule inputs are usable.

Story DoD:
- [x] Language LLM extractor returns required weekly fields + per-field confidence.
- [x] Low-confidence critical fields trigger clarification path (no unsafe state transition).
- [x] Tests include ambiguous pain/event-date examples.

#### Story RE4.2 — Clarification Gating and Language-LLM Boundary
As a system, I need extraction confidence and clarification to remain outside planner logic so unsafe state transitions are blocked before plan generation.

Story DoD:
- [x] Low-confidence critical fields trigger clarification before planner execution.
- [x] Language LLM is documented as extraction/clarification/reply-rendering only, not state authority.
- [x] Tests verify clarification gating prevents unsafe phase/risk changes.

#### Story RE4.3 — Planner Brief from Decision Envelope
As a planner, I need a planner brief derived from deterministic rule output so the planning LLM is bounded without being reduced to pure template rendering.

Story DoD:
- [x] Rule engine emits `hard_limits`, `weekly_targets`, allowed session budget, disallowed patterns, track-specific goals, structure preference, and messaging guardrails for planner input.
- [x] Planner brief includes deterministic `fallback_skeleton`.
- [x] Tests verify planner-brief contract presence and completeness.

#### Story RE4.4 — Planning LLM Plan Proposal Inside Bounds
As a planner, I need a planning LLM to generate structured weekly plan proposals within the planner brief so plans are flexible but still compliant.

Story DoD:
- [x] Planning LLM consumes only the planner brief, not raw mutable rule-state authority.
- [x] Planning LLM may emit rationale and non-binding state suggestions.
- [x] Tests verify multiple valid plan shapes can pass against the same deterministic envelope.

#### Story RE4.5 — Plan Validator and Auto-Repair
As a safety layer, I need validation of planning-LLM output so non-compliant plans are rejected, repaired, or replaced before send.

Story DoD:
- [x] Validator checks intensity budget, spacing, risk constraints, track compatibility, and messaging-guardrail compliance.
- [x] Invalid outputs are repaired deterministically or downgraded to fallback template.
- [x] Planner suggestions cannot change `phase`, `risk_flag`, `track`, clarification status, or persisted state.
- [x] Tests verify reject/repair/fallback behavior.

#### Story RE4.6 — Language LLM Reply Renderer with Guardrails
As a messaging layer, I need a language LLM to render athlete-facing copy from validated plans without reintroducing unsafe or contradictory language.

Story DoD:
- [x] Language LLM renders from validated plan artifact + deterministic messaging guardrails.
- [x] `return_or_risk_managed` suppresses peak/performance phrasing in rendered copy.
- [x] Tests verify render output stays aligned with validated plan and deterministic track framing.

#### Story RE4.7 — Flexibility Mode Output Formatter
As an athlete preferring flexibility, I need anchor/filler/optional menu output instead of strict sequence.

Story DoD:
- [x] Formatter emits 2 anchors, 1-2 fillers, 1 optional session format.
- [x] Enforces no back-to-back hard days and max hard-session budget.
- [x] Tests verify menu structure and constraints.

### Epic RE4 Lightweight DoD
- [x] Language LLM and planning LLM are separate module boundaries even if they share the same vendor/model family.
- [x] AI planner cannot bypass deterministic safety/rule constraints.
- [x] Low-confidence parsing cannot trigger unsafe transitions.
- [x] Deterministic rule engine remains final authority for state, validation, repair, and fallback.
- [x] Planning-LLM state suggestions are advisory only.
- [x] Flexible and structured outputs both validate successfully.

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
- [ ] LLM-as-a-judge is not part of planner validation authority.
- [ ] Non-goal states judge does not gate deterministic safety decisions.
- [ ] No code changes required in this epic.

### Epic RE5 Lightweight DoD
- [ ] Deferred topics are documented and visible to future implementation passes.
- [ ] No accidental scope creep into deferred logic.

---

## Suggested Implementation Sequence (Low Risk)
1. Epic RE2
2. Epic RE3
3. Epic RE4
4. Epic RE5 (documentation placeholders only)

This order keeps deterministic safety/state logic in place before any AI planning behavior is expanded.
