# Major Refactoring Plan: Remove The Old Rule Engine From The Authoritative Path

**Status:** Design/implementation brief only. No code has been changed as part of this document.

**Audience:** Future implementation agent(s) working in this repository.

**Intent:** Cleanly cut the current deterministic rule engine out of the authoritative request path while keeping the old implementation on disk for future reference. The system should continue to function through extraction, memory, coaching reasoning, and response generation without any runtime dependence on the old rule-engine outputs.

## 1. Objective
Refactor the system so the old rule engine no longer influences:
- routing,
- coaching authority,
- planning authority,
- response-brief assembly,
- response generation,
- persisted athlete-facing plan state.

The old rule engine must remain in the repository for now, but it should become inactive implementation history rather than active runtime architecture.

## 2. Architectural Decision
This is a **hard cut**, not a shadow/pass-through mode.

Reason:
- shadow systems rot,
- dead-but-running scaffolding invites future accidental dependencies,
- partial detachment creates ambiguous authority,
- clean reinsertion of a future better engine is easier if the old one is fully out of the runtime path.

Therefore:
- keep the old modules,
- stop calling them in the request path,
- remove their contracts from downstream data flow,
- ensure the system works without them.

## 3. Target Interim Architecture

### 3.1 Authoritative Path
1. Inbound athlete message
2. Extraction / profile updates / memory updates
3. Coaching reasoning
4. Response generation
5. Persist athlete-facing state

### 3.2 Explicitly Non-Authoritative / Inactive
- `sam-app/email_service/rule_engine.py`
- `sam-app/email_service/rule_engine_orchestrator.py`
- rule-engine-derived weekly skeletons
- deterministic fallback skeletons
- deterministic hard limits
- deterministic plan adjustments
- rule-engine-computed reply strategy
- deterministic next-email payloads

## 4. Non-Negotiable Invariants
The implementation agent must preserve these invariants.

### 4.1 No Old Rule-Engine Output In Runtime Decision-Making
No request-time logic may use old rule-engine output to:
- select reply mode,
- constrain training structure,
- cap intensity,
- rewrite athlete preferences,
- alter response language,
- persist athlete-facing current-plan state.

### 4.2 No Weekly Skeleton In Athlete-Facing Contracts
`weekly_skeleton` must not be present in authoritative downstream contracts for:
- coaching reasoning inputs,
- response brief assembly,
- writer brief assembly,
- persisted athlete-facing plan truth.

### 4.3 No Hidden Transitional Dependence
Do not leave “temporary” reads of old rule-engine fields in place.

Bad examples:
- “only for safety”
- “only for reply strategy”
- “only for fallback wording”
- “only for plan_summary shaping”

If the old engine still changes runtime behavior in any way, the cut is incomplete.

## 5. Scope Of Work

### In Scope
- remove old rule-engine outputs from the request path,
- remove old rule-engine-derived fields from downstream contracts,
- stop persisting rule-engine plan artifacts as athlete-facing truth,
- preserve working coaching replies via memory + coaching reasoning + response generation,
- update tests to reflect the new authority boundary.

### Out Of Scope
- designing the new advanced rule engine,
- reintroducing deterministic planning authority,
- adding new planning abstractions beyond what is minimally required for a clean interim state,
- deleting the old rule-engine modules.

## 6. Interim Behavioral Model
Until a new engine is inserted, the system should behave as follows:

- athlete structure requests are admissible,
- coaching reasoning may challenge them in language,
- the system must not silently overwrite them,
- no deterministic fallback week should be injected,
- no old scaffold should be persisted as athlete-facing current truth.

Important:
- removing old rule-engine authority does **not** mean the coaching layer must endorse every athlete request,
- it means the old deterministic engine cannot secretly rewrite the athlete’s plan.

## 7. Authoritative Data Sources After The Cut
The implementation agent should treat the following as authoritative inputs:
- inbound athlete message,
- extracted profile updates,
- durable athlete memory / preferences / constraints,
- current athlete-facing plan if present,
- activity/history facts from non-rule-engine sources,
- coaching reasoning outputs.

The following are **not** authoritative:
- old deterministic planning envelope,
- fallback skeleton,
- hard-session budget,
- deterministic adjustments,
- rule-engine risk posture,
- deterministic next-email payload.

## 8. Module-Level Refactor Plan

This section describes the intended changes by subsystem. File names are indicative and should be verified against the current repo state before implementation.

### 8.1 Inbound Routing
Likely relevant areas:
- `sam-app/email_service/inbound_rule_router.py`
- `sam-app/email_service/business.py`
- `sam-app/email_service/coaching.py`

Goal:
- routing should determine only broad communication mode,
- routing should not depend on the old rule engine.

Allowed routing categories:
- intake
- clarification
- coaching reply
- lightweight non-planning
- off-topic redirect
- safety concern

Implementation intent:
- derive these categories from extraction, missing information, message intent, and explicit safety signals,
- do not ask the old rule engine to produce `reply_strategy`,
- do not use old engine payloads as routing context.

### 8.2 Plan Persistence
Likely relevant areas:
- `sam-app/email_service/dynamodb_models.py`
- `sam-app/email_service/coaching.py`
- `sam-app/email_service/business.py`
- any current-plan update helper currently fed by rule-engine orchestrator output

Goal:
- stop writing rule-engine-shaped artifacts into `current_plan`.

Requirements:
- do not persist `weekly_skeleton` as current athlete-facing truth,
- do not write deterministic fallback composition into plan state,
- do not let an old engine update overwrite athlete-negotiated structure.

Interim guidance:
- if a minimal current-plan object is needed, keep it intentionally thin.

Suggested interim fields:
- `plan_status`
- `plan_summary`
- `athlete_requested_structure`
- `coach_recommendation`
- `open_questions`
- `updated_at`

Do not invent richer structure unless required by existing code paths.

### 8.3 Response-Brief Assembly
Likely relevant areas:
- `sam-app/email_service/response_generation_assembly.py`
- `sam-app/email_service/response_generation_contract.py`

Goal:
- build response briefs entirely from athlete context, memory, delivery context, and coaching reasoning outputs.

Requirements:
- remove old rule-engine plan fields from the authoritative brief,
- no `weekly_skeleton`,
- no fallback scaffold,
- no deterministic `today_action`,
- no deterministic `adjustments`,
- no deterministic `next_email_payload`.

If a field exists only because the old engine produced it, it should be removed from authoritative use.

### 8.4 Coaching Reasoning
Likely relevant areas:
- `sam-app/email_service/skills/coaching_reasoning/*`
- `sam-app/email_service/coaching.py`

Goal:
- coaching reasoning becomes first-class authority.

Requirements:
- it must make decisions directly from athlete message + memory + current plan context,
- it must not inherit old rule-engine planning decisions,
- it may still express caution or disagreement in natural language.

Important:
- do not rebuild the old rule engine inside coaching reasoning,
- keep the interim behavior simple and legible.

### 8.5 Response Generation
Likely relevant areas:
- `sam-app/email_service/skills/response_generation/*`
- prompt packs under `sam-app/email_service/prompt_packs/coach_reply/*`

Goal:
- writer consumes only coach-authoritative direction plus athlete-facing context.

Requirements:
- no rule-engine-derived skeleton or payload shaping,
- no deterministic fallback wording,
- no scaffold tokens surviving into the writer brief.

### 8.6 Old Rule Engine Modules
Likely relevant areas:
- `sam-app/email_service/rule_engine.py`
- `sam-app/email_service/rule_engine_orchestrator.py`
- tests referencing them

Goal:
- keep them present but inactive.

Requirements:
- do not delete them,
- do not call them from the request path,
- update docs/tests as needed to reflect that they are not part of the active architecture.

## 9. Contract Cleanup Requirements

The implementation agent should explicitly remove old rule-engine fields from authoritative runtime contracts where possible.

Fields to eliminate from active downstream use:
- `weekly_skeleton`
- `fallback_skeleton`
- `hard_limits`
- `today_action`
- `adjustments`
- `priority_sessions`
- `track` when only sourced from old rule-engine classification
- `risk_flag` when only sourced from old rule-engine classification
- `next_email_payload`
- `reply_strategy` when produced by the old engine

If some contract fields must temporarily remain for compatibility, they must:
- not be read in runtime logic,
- not alter behavior,
- be marked as deprecated in comments/tests/docs.

## 10. Testing Strategy

### 10.1 Core Acceptance Tests
After implementation, tests should prove:
- a coaching reply can be generated without calling the old rule engine,
- response briefs contain no old rule-engine planning artifacts,
- current-plan writes are not sourced from deterministic skeletons,
- routing still works for intake / clarification / coaching / off-topic / safety,
- athlete-facing responses still render correctly.

### 10.2 Regression Focus
Add or update tests for:
- no rule-engine output in response brief assembly,
- no rule-engine output in writer brief assembly,
- no `weekly_skeleton` in athlete-facing runtime contracts,
- no old-engine-derived plan writes,
- coaching reasoning still operates when rule-engine modules are not invoked.

### 10.3 Keep Old Tests Intentionally
Do not delete old rule-engine tests unless they are tightly coupled to active-path assumptions.

Preferred approach:
- keep them as tests of dormant implementation modules,
- separate them conceptually from active-path behavior.

## 11. Implementation Sequence
The implementation agent should follow this order to minimize confusion:

1. Map all current reads of old rule-engine output in the request path.
2. Remove downstream dependence first:
   - response generation
   - response-brief assembly
   - current-plan persistence
3. Remove upstream dependence next:
   - routing
   - orchestration hooks
4. Ensure request-time flow functions without any rule-engine invocation.
5. Mark old engine modules as inactive architecture in docs/comments if helpful.
6. Run focused tests, then full merge-bar tests.

Do not begin by deleting files.

## 12. Safety During The Interim State
This refactor changes where safety enforcement lives.

Since the old deterministic engine is being removed from authority:
- safety language must come from coaching reasoning,
- explicit medical/safety escalations should remain possible,
- do not claim deterministic safety guarantees that no longer exist.

Implementation guidance:
- keep interim safety behavior narrow and explicit,
- avoid recreating a hidden deterministic rule layer through ad hoc checks scattered across the codebase.

## 13. Anti-Patterns To Avoid

Do not do any of the following:
- keep the old engine running “just for now” in request-time logic,
- retain `weekly_skeleton` in the response path for convenience,
- silently map old engine outputs into renamed fields,
- treat rule-engine persistence as athlete-facing plan truth,
- rebuild old safety logic piecemeal across multiple files,
- add a new abstraction layer unless it removes complexity rather than moving it.

## 14. Deliverables Expected From The Implementation Agent
When implementing this refactor, the agent should produce:
- code changes that remove old rule-engine outputs from the authoritative runtime path,
- updated tests,
- a concise explanation of what runtime authority remains after the cut,
- clear notes about any fields/contracts intentionally left in place for compatibility.

## 15. Definition Of Done
The refactor is done when all of the following are true:
- request-time coaching replies work without the old rule engine,
- no old rule-engine output is used in authoritative routing/planning/response logic,
- no old deterministic skeleton is persisted as the athlete-facing current plan,
- runtime contracts no longer rely on old rule-engine planning artifacts,
- the old rule-engine code remains in the repo but can be deleted later without changing current runtime behavior.

## 16. Merge-Bar Requirement
Per repo instructions, before marking the refactor complete, run:

```bash
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

If any of these cannot be run, the implementation agent must say so explicitly.
