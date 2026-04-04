# Athlete Memory Stabilization Epic

Status: planned.

This file describes the next athlete-memory implementation epic after AM1. It is a planned design record, not current runtime behavior.

## Context and Scope Boundaries
- The goal is to make durable athlete memory stable over long horizons, not to build a generalized memory system.
- The split between durable memory and short-term continuity stays in place.
- Stories should stay atomic. If a story expands during implementation, split it before building.
- Refactoring is allowed. Backward compatibility in implementation is not a goal by itself.
- YAGNI applies: prefer the smallest concrete implementation that removes the current drift modes.
- This epic targets the main current failure mode only: omission or imprecision in long-term refresh. It does not expand scope to retrieval redesign, coach-reply contamination controls, or broad migration work unless implementation proves they are required.

---

## Epic AM2 — Durable Memory Stabilization (Lite)

### Goal
Make long-term athlete memory stable by removing omission-driven deletion and making final durable-memory state transitions deterministic, while keeping semantic interpretation narrowly LLM-assisted and the implementation as lightweight as possible.

### Core Design
- `memory_notes[]` remains the durable-memory field on `coach_profiles`.
- Each durable note becomes a typed durable fact with a stable `fact_key`.
- `fact_key` must be system-derived and deterministic so the same durable truth resolves to the same key across refreshes.
- `continuity_summary` remains the short-lived working set for the next 1 to 2 exchanges.
- Long-term memory refresh no longer returns a full revised note list.
- The primary long-term LLM step is limited to candidate-fact interpretation: it proposes structured durable-memory candidates and proposed actions.
- The primary long-term LLM step does not make final persistence decisions about worthiness, slot pressure, or state mutation.
- Deterministic code validates candidates, canonicalizes keys, enforces hard policy rules, and applies final state transitions.
- A deterministic reducer applies accepted operations to persisted durable memory.
- Durable memory may be updated only once per inbound interaction and only before reply generation.
- This epic allows only lightweight consolidation needed to avoid obviously redundant active facts. It does not introduce a broad memory-optimization subsystem.
- This epic does not change reply-time retrieval strategy unless implementation reveals a blocking issue.

### Stories

#### Story AM2.1 — Durable Fact Contract
As a developer, I need a stronger durable-memory contract so durable facts are stored as stable entities instead of anonymous note text.

Story DoD:
- [ ] `memory_notes` remains the persisted durable-memory field on `coach_profiles`.
- [ ] Each durable note requires:
  - `memory_note_id`
  - `fact_type`
  - `fact_key`
  - `summary`
  - `importance`
  - `created_at`
  - `updated_at`
  - `last_confirmed_at`
- [ ] `fact_type` is restricted to:
  - `goal`
  - `constraint`
  - `schedule`
  - `preference`
  - `other`
- [ ] `memory_note_id`, `created_at`, `updated_at`, and `last_confirmed_at` are system-owned fields.
- [ ] `fact_key` is a system-derived deterministic field, not a model-owned free-form identifier.
- [ ] The system defines one canonical `fact_key` generation policy used on every durable-memory write.
- [ ] `fact_key` generation is based on normalized durable fact identity and must produce the same key for semantically identical facts.
- [ ] The model may propose durable fact content, but the system is responsible for final `fact_key` derivation before persistence.
- [ ] Validation rejects malformed durable facts at the persistence boundary.

#### Story AM2.2 — Candidate-Fact Interpretation Contract
As a memory subsystem, I need the primary long-term LLM step to propose structured durable-memory candidates instead of a full replacement list so semantic interpretation stays narrow and omission cannot silently delete memory.

Story DoD:
- [ ] The primary long-term LLM output changes from `memory_notes[]` to `candidates[]`.
- [ ] Each candidate requires:
  - `action`
  - `fact_type`
  - `fact_key`
  - `summary`
  - `evidence_source`
  - `evidence_strength`
- [ ] `action` is restricted to `upsert`, `confirm`, or `retire`.
- [ ] `importance` is optional on `upsert` and ignored for `confirm` and `retire`.
- [ ] `evidence_strength` is restricted to `explicit`, `strong_inference`, or `weak_inference`.
- [ ] `retire` is valid only when `evidence_strength` is `explicit`.
- [ ] `retire` requires athlete-originated evidence that directly contradicts or explicitly ends the previously stored durable fact.
- [ ] `confirm` and `upsert` may use non-explicit athlete-originated evidence when the durable fact meaning is still clear.
- [ ] `evidence_source` is restricted to athlete-originated sources:
  - `athlete_email`
  - `profile_update`
  - `manual_activity`
  - `rule_engine_state`
- [ ] The primary long-term LLM step no longer emits note IDs, timestamps, or full next-state memory.
- [ ] The primary long-term LLM step may propose candidate durable facts and actions, but it does not decide final persistence, slot worthiness, or active-memory budget outcomes.

#### Story AM2.3 — Deterministic Durable Memory Reducer
As a coaching system, I need durable memory updates applied by deterministic code so stable facts survive routine churn and multi-turn drift.

Story DoD:
- [ ] A deterministic gate validates and normalizes `candidates[]` against current active durable facts before reducer apply.
- [ ] The deterministic gate rejects invalid enum values, malformed payloads, and conflicting candidate actions on the same canonical `fact_key`.
- [ ] The deterministic gate rejects any `retire` candidate that does not meet the explicit-evidence requirement.
- [ ] The deterministic gate derives the final canonical `fact_key` before persistence.
- [ ] The deterministic gate, not the primary LLM step, decides whether a candidate is eligible for durable-memory persistence under policy rules.
- [ ] The reducer applies only candidates accepted by the deterministic gate.
- [ ] `confirm` refreshes metadata on an existing fact and never creates a new fact.
- [ ] `upsert` updates an existing fact when the canonical `fact_key` already exists, otherwise creates a new fact.
- [ ] `retire` marks the matching fact inactive on the same durable note instead of creating a separate tombstone structure.
- [ ] The reducer, not the model, assigns new `memory_note_id` values.
- [ ] The reducer stamps `created_at`, `updated_at`, and `last_confirmed_at`.
- [ ] Active durable-memory cap remains lightweight and implementation-defined, with no new deterministic eviction policy introduced in this epic unless needed to preserve existing behavior.

#### Story AM2.4 — Slot Worthiness and Constraint Reversal Rules
As a system designer, I need explicit memory-slot guidance so active durable memory is reserved for coaching-relevant truths rather than literal but low-value facts.

Story DoD:
- [ ] Slot worthiness is enforced outside the primary long-term LLM step.
- [ ] The long-term prompt may describe the concept of memory worthiness, but final worthiness enforcement is deterministic.
- [ ] `upsert` is eligible for durable persistence only for facts that represent a meaningful goal, constraint, recurring structure, preference, or other coaching-relevant truth.
- [ ] The deterministic gate rejects or ignores low-value durable facts that do not clear the memory-worthiness bar, even if they are literally true.
- [ ] The deterministic gate discourages storing trivial positive restatements that merely remove a prior constraint without creating a meaningful recurring planning advantage.
- [ ] When a previously stored restrictive fact is no longer true, the preferred behavior is to `retire` the old fact rather than automatically store the positive opposite.
- [ ] Schedule facts are eligible for durable persistence only when they represent a durable constraint, recurring structure, or unusual opportunity that materially affects planning.
- [ ] The active durable-memory budget remains 7 facts.
- [ ] Slot-worthiness rules are the first line of defense against memory bloat, before any consolidation logic is applied.

#### Story AM2.5 — LLM-Proposed Memory Consolidation
As a memory subsystem, I need the LLM to explicitly propose lightweight consolidation when two active durable facts are clearly redundant so memory can stay compact without brittle rule-based matching.

Story DoD:
- [ ] The long-term memory contract supports a minimal consolidation path in addition to `upsert`, `confirm`, and `retire`.
- [ ] Consolidation operations are limited to structured actions such as:
  - `merge_into`
- [ ] A consolidation proposal references durable facts by canonical `fact_key`.
- [ ] The LLM may propose consolidation only when one durable fact is clearly redundant because another fact subsumes it.
- [ ] Consolidation proposals are optional and are used only when slot pressure or obvious redundancy exists.
- [ ] The contract does not allow the LLM to rewrite the full durable-memory state in one pass.

#### Story AM2.6 — Deterministic Application of Consolidation Ops
As a coaching system, I need consolidation proposals applied by a reducer so semantic judgment stays model-assisted but final state changes stay controlled.

Story DoD:
- [ ] The reducer accepts structured consolidation ops and applies them against the current active durable facts.
- [ ] `merge_into` updates the target fact summary and marks the source fact inactive.
- [ ] The reducer never allows two active facts with the same canonical `fact_key`.
- [ ] The reducer preserves `memory_note_id` for surviving facts after consolidation.
- [ ] The reducer remains the only component that mutates stored durable memory.

#### Story AM2.7 — Active Memory Budget Enforcement
As a platform maintainer, I need bounded active durable memory so new important facts can be retained without low-value redundancy crowding them out.

Story DoD:
- [ ] The reducer enforces an active durable-memory budget.
- [ ] If the budget is exceeded, the system first applies valid consolidation proposals before considering retirement of low-value facts.
- [ ] Inactive facts do not count against the active memory budget.
- [ ] The reducer refuses to keep redundant active facts when a valid merge target already exists.
- [ ] The budget resolution order is lightweight and explicit:
  - reject low-worth candidates first
  - apply valid consolidation proposals second
  - if still over budget, preserve currently active facts and drop the weakest newly proposed additions first
  - if newly proposed additions are tied, break ties by `importance`, then `evidence_strength`, then canonical `fact_key`
- [ ] The budget policy is based on structured fact state and consolidation proposals, not regex or raw-string matching.

### Epic AM2 DoD
- [ ] Durable memory no longer relies on model-generated full next-state list replacement.
- [ ] Omission from an LLM response can no longer delete a durable fact.
- [ ] Durable memory is mutated at most once per inbound interaction.
- [ ] Durable memory updates occur only before reply generation.
- [ ] Durable memory updates use athlete-originated evidence only.
- [ ] The primary long-term LLM step is limited to candidate-fact interpretation rather than final memory mutation decisions.
- [ ] Final durable-memory persistence decisions are enforced by deterministic code.
- [ ] Durable memory keys are system-derived with one deterministic canonicalization policy.
- [ ] Retirement of a durable fact requires explicit contradictory or explicit no-longer-true athlete evidence.
- [ ] The implementation supports LLM-proposed consolidation of redundant durable facts without allowing full-state LLM rewrites.
- [ ] Active durable-memory slots are reserved for coaching-relevant facts through structured compaction rather than regex or raw-string matching.
- [ ] Model-owned IDs and timestamps are removed from memory persistence contracts.
- [ ] The implementation remains lightweight and does not introduce separate tombstones, retrieval redesign, or broad migration work in this epic.

### Implementation Notes
- The main current failure mode is durable-memory omission and mis-prioritization, not temporary-context leakage. Durable truths are getting dropped under pressure; temporary travel or disruption context is usually not the primary problem.
- The practical risk is functional wrongness through omission. The system may keep plausible memory, but if it drops enough core facts a human coach could make bad decisions from the incomplete state.
- `AM-LH-002` has been the most consistently weak benchmark scenario and should be treated as the primary regression case after implementation. `AM-LH-001` is the key sanity check for durable reversals and slot-worthiness behavior.
- In this epic, “deterministic” means code owns validation, canonical key derivation, state transitions, retire safety rules, slot-worthiness enforcement, and final persistence decisions. It does not mean regex-heavy or brittle string matching.
- The primary LLM step is intentionally narrow. Its job is candidate-fact interpretation from athlete-originated evidence, not final memory mutation, slot management, or freeform optimization.
- Lightweight consolidation in this epic is intentionally narrow. The only consolidation path allowed is `merge_into` for clearly redundant active facts. It is not a separate memory-optimizer service.
- `rewrite` is intentionally out of scope because it is the most likely path back to semantic drift. Do not reintroduce freeform summary rewriting as part of this epic.
- Planning-structure abstraction is intentionally deferred. Do not add a broader abstraction layer unless implementation shows a concrete need beyond lightweight merge-based redundancy removal.
- The most important outcome is reliable durable-memory state, not maximum recall of every true fact.
- A durable fact is worth a slot only if losing it would materially hurt future coaching decisions. Favor a small set of high-value facts over storing every plausible detail.
- When a prior restrictive fact is no longer true, first ask whether the old fact should be retired. Store the positive opposite only if it creates meaningful recurring coaching value.
- Temporary travel, short-lived disruption, and one-off schedule changes should not retire durable structure unless athlete evidence explicitly shows the old durable fact is no longer true.
- The system should never keep both sides of a durable reversal active at the same time.
- Before implementation, define a small canonical `fact_key` reference set in code and documentation. At minimum include examples for a hard schedule constraint, a recurring anchor, a durable reversal, a meaningful flexibility fact, and routine noise that should be rejected.
- Benchmark examples such as `AM-LH-001` and `AM-LH-002` are acceptance guidance and regression checks, not hidden hardcoded templates.
- The implementation should make it easy to explain why a candidate was accepted, rejected, merged, or retired.
- Keep the model contract narrow and the reducer behavior explicit enough that unit tests can verify the main safety properties without relying on prompt behavior alone.
- Common implementation traps to avoid:
  - letting the LLM own final `fact_key`
  - allowing routine churn to create durable facts
  - allowing temporary disruption to retire durable structure
  - accepting `retire` from weak or inferred evidence
  - expanding consolidation into broad freeform rewriting
  - keeping both sides of a reversal active at once

---

## Non-Goals
- Embeddings or semantic search.
- A generalized knowledge or reasoning memory system.
- Free-form historical audit trails beyond current coaching needs.
- Deterministic NLP fact extraction from raw email.
- Reply-time retrieval redesign.
- Coach-reply contamination controls beyond keeping durable refresh pre-reply only.
- Legacy migration or write-forward normalization unless implementation reveals an immediate need.
- Complex ranking or eviction algorithms.
- A broad or standalone memory-optimization subsystem.
- Canonical planning-structure abstractions beyond lightweight merge-based redundancy removal.
- A single monolithic LLM prompt that both interprets athlete evidence and makes final durable-memory persistence decisions.

---

## Expected Result
After Epic AM2 is implemented, the system should be able to:
- preserve core durable athlete truths through long-horizon churn,
- prevent omission in long-term refresh from deleting valid memory,
- keep durable memory updates deterministic and bounded, and
- improve reliability without introducing an overly rigid or over-engineered memory model.
