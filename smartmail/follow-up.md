# Follow-up Topics (Deferred)

These items were explicitly deferred and are not yet part of the implementation contract.

## RE5.1) Mixed-signal wearable-vs-email conflict policy (deferred placeholder)
- Status: `deferred placeholder`
- Source story: [RE5.1 in rule-engine-epic.md](/Users/levonsh/Projects/smartmail/rule-engine-epic.md)
- Deferred question: When wearable/device telemetry conflicts with athlete email self-report, which source should have precedence and under what confidence thresholds?
- Example conflicts to resolve later:
  - Wearable shows high HRV/readiness while email reports severe fatigue and poor sleep.
  - Wearable estimates low load while athlete reports an unrecorded hard session.
  - Wearable indicates low strain but athlete reports pain flare-up that should trigger conservative routing.
- Open decisions for later:
  - Should precedence be static (always safety-first self-report) or dynamic by signal reliability?
  - What minimum evidence should trigger clarification instead of automatic arbitration?
  - How should unresolved conflicts be represented in rule inputs/state for downstream planning?
- Non-goal in RE5: do not add production mixed-signal arbitration logic yet.

## RE5.2) LLM-as-a-judge scoring (deferred placeholder)
- Status: `deferred placeholder`
- Source story: [RE5.2 in rule-engine-epic.md](/Users/levonsh/Projects/smartmail/rule-engine-epic.md)
- Deferred question: Should judge-style scoring be added for plan quality ranking, and if so, where can it be advisory without becoming safety authority?
- Boundary rules (explicit non-goals):
  - Judge output is not planner validation authority.
  - Judge output does not gate deterministic safety decisions.
  - Judge output does not modify deterministic `phase`, `risk_flag`, `track`, clarification status, or persisted rule state.
- Potential future use (advisory only): offline evaluation/experimentation of plan readability, preference alignment, or perceived usefulness.

## 5) Risk trend requiring history (deferred)
- Status: `skip for now`
- Deferred question: Should worsening-detection depend on rolling 2-3 check-ins, and what minimum history is required before escalating from yellow to red_b?
- Potential future rule: add confidence levels when history is sparse.

## 7) Ambiguous main sport tie-breakers (deferred)
- Status: `skip for now`
- Deferred question: For hybrid athletes with near-equal volume split, should we lock main sport for a fixed window (for example 2-4 weeks) to prevent plan churn?
- Potential future rule: retain last declared main sport unless athlete explicitly changes it.

## 10) Idempotency/concurrency + double-session day semantics (deferred)
- Status: `do not implement yet`
- User scenario to support later: morning bike + evening swim on the same day is valid and should not be treated as duplication/conflict.
- Open decisions for later:
  - Should same-day two-session plans be allowed only when both are easy, or allow one quality + one easy?
  - How should hard-day spacing treat two sessions in one calendar day?
  - What storage keying policy distinguishes valid dual sessions from duplicate submissions?
- Proposed direction for discussion:
  - treat a day as one "load bucket" for hard-day spacing
  - allow dual sessions only if total daily intensity budget is respected
  - preserve modality diversity (for example bike + swim) as valid cross-training pattern
