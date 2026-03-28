# Advanced Rule Engine Spec - not implemented yet

**Authority:** This document is a forward-looking design spec for a more capable rule engine and planning pipeline. It does not describe current implemented behavior. If it conflicts with current code in `sam-app/email_service`, current code still wins until the design is implemented deliberately.

## 1. Purpose
Define a better planning architecture that:
- protects inexperienced or underspecified athletes from unsafe planning,
- gives advanced athletes more structural freedom when evidence supports it,
- preserves athlete preferences without blindly obeying bad training ideas,
- prevents coarse deterministic scaffolds from leaking into athlete-facing language.

This spec exists to fix the current failure mode where a generic weekly skeleton becomes too authoritative too deep in the stack.

## 2. Core Principle
The system must make two distinct judgments:
1. What is the athlete asking for?
2. How much planning authority should that request get?

Those are not the same thing.

An athlete can:
- have strong schedule preferences,
- have weak training judgment,
- have high execution capacity,
- have low demonstrated consistency,
- or be truly advanced and capable of handling a less rigid plan.

The engine must model those separately.

## 3. Current Problem To Eliminate
`weekly_skeleton` currently does too many jobs:
- internal safety scaffold,
- persisted plan representation,
- source material for athlete-facing response generation.

That is the wrong boundary.

Consequences:
- athlete-negotiated structure gets overwritten by generic fallback composition,
- deterministic intensity limits become plan truth too early,
- response generation mirrors scaffold tokens instead of communicating a resolved plan.

## 4. Target Planning Pipeline

### 4.1 Rule Engine Produces A Planning Envelope, Not The Final Athlete Week
The deterministic layer should emit:
- safety state,
- feasibility constraints,
- risk posture,
- progression bounds,
- intensity policy,
- fallback scaffold for internal use only.

It should not be treated as the final week that the athlete receives.

### 4.2 Preference Hydration Resolves Athlete-Specific Structure
A hydration layer must merge:
- athlete explicit preferences,
- durable schedule constraints,
- injury/risk constraints,
- continuity state,
- demonstrated capability,
- current-week feasibility,
- deterministic planning envelope.

This layer produces the athlete-shaped week.

### 4.3 Response Generation Only Sees The Resolved Plan
Response generation must not consume raw `weekly_skeleton`.

By the time a writer sees plan data, the plan should already reflect:
- the athlete’s real structure,
- safety overrides,
- conservative vs advanced freedom,
- exact recommendations for this week.

## 5. Athlete Intent Model
Every athlete-originated planning statement should be classified into one or more categories:

- `explicit_preference`
  Example: "I prefer 4 runs per week."

- `explicit_constraint`
  Example: "Weekday runs must end by 6:45am."

- `training_knowledge_signal`
  Example: "Keep quality to at most two sessions in a week."

- `performance_capacity_signal`
  Example: "I usually handle two workouts plus a long run in stable blocks."

- `risk_signal`
  Example: "My Achilles tightens when intensity ramps too quickly."

The system should not treat all athlete statements as equally authoritative.

## 6. Coaching Trust Model
The engine should carry separate trust dimensions.

### 6.1 Preference Trust
Should the system honor this structurally?

High examples:
- preferred days,
- session count preference,
- timing windows,
- optional vs required support work.

### 6.2 Training-Judgment Trust
Should the system trust the athlete’s training prescription instincts?

This should be lower by default than preference trust.

### 6.3 Execution-Capacity Trust
Does available evidence suggest the athlete can handle richer planning?

This depends on:
- demonstrated training history,
- consistency,
- experience level,
- quality tolerance,
- coherent self-reporting,
- connector data when available.

## 7. Capability Tiers
The engine should classify athlete planning freedom into capability tiers.

### Tier 0: Unknown
Not enough evidence.

Behavior:
- conservative default,
- honor hard schedule constraints,
- avoid giving full authority to ambitious intensity requests,
- communicate uncertainty clearly.

### Tier 1: Engaged But Unproven
Athlete gives useful details, but there is not yet strong evidence of sophisticated self-management.

Behavior:
- honor logistics,
- honor broad structure where safe,
- keep intensity and progression conservative,
- explain why the plan is narrower than the athlete’s theoretical maximum.

### Tier 2: Demonstrated Training Literacy
Athlete shows good training understanding and realistic tradeoff awareness.

Signals:
- coherent description of easy vs hard work,
- realistic progression expectations,
- awareness of fatigue and recovery,
- sensible self-limits.

Behavior:
- more freedom in structure,
- athlete quality preferences can materially shape the week,
- still bounded by safety and current risk.

### Tier 3: Demonstrated Advanced Capacity
The system has real evidence of advanced handling capacity.

Signals:
- strong training history,
- consistency,
- prior successful blocks,
- activity evidence,
- accurate self-monitoring,
- no pattern of reckless escalation.

Behavior:
- richer weekly structures are allowed,
- two quality sessions may be normal when context supports them,
- deterministic scaffolding should be much less prescriptive.

## 8. Evidence Sources For Capability
Capability tier must not come from one sentence alone.

Evidence may include:
- profile experience level,
- prior weekly consistency,
- event history,
- athlete memory facts,
- durable structure facts,
- activity connector data,
- quality session history,
- coherent descriptions of prior load,
- recovery awareness,
- injury self-management behavior.

Weak evidence:
- "I’m advanced."
- "I want more workouts."
- "I can handle doubles."

Strong evidence:
- specific prior structure,
- specific quality tolerance,
- realistic self-limiting language,
- observed consistency,
- confirmed training background.

## 9. Preference Precedence
The engine should prioritize athlete-originated information in this order:

1. Hard safety constraints
2. Feasibility constraints
3. Demonstrated capability
4. Athlete structural preferences
5. Athlete intensity preferences
6. Generic deterministic fallback

Implication:
- days, timing windows, and run-count preferences should usually be honored strongly,
- intensity density should never be governed by preference alone.

## 10. Deterministic Intensity Policy Must Be Loosened
The current deterministic logic is too eager to turn caution into a hard ban on quality.

### 10.1 Absolute Intensity Bans
Absolute bans should be reserved for true safety cases:
- red-tier risk,
- explicit pain/injury escalation,
- infeasible week,
- strong return-from-break constraints,
- other clear safety stop conditions.

### 10.2 Yellow / Conservative States
Yellow or caution states should usually mean:
- lower quality probability,
- lower quality ceiling,
- more spacing,
- safer quality types,
- smaller progression,
- not automatic zero quality in all cases.

### 10.3 Replace A Single Hard-Session Budget With An Intensity Policy
Instead of one early field like `max_hard_sessions_per_week`, the engine should emit a richer policy such as:
- `quality_allowed`
- `quality_ceiling`
- `quality_floor`
- `allowed_quality_types`
- `minimum_easy_separation_days`
- `back_to_back_hard_forbidden`
- `progression_posture`

This gives the planner room to decide between zero, one, or two quality touches based on athlete capability and week context.

## 11. Athlete-Facing Resolved Plan Contract
The hydrator should produce a resolved weekly plan object. Example fields:

```json
{
  "session_count_target": 4,
  "run_count_target": 4,
  "quality_session_cap": 2,
  "quality_session_recommended_this_week": 1,
  "strength_policy": "optional_short_separate_from_runs",
  "long_run_preference": "saturday",
  "weekday_constraints": ["finish_by_06_45"],
  "session_slots": [
    {
      "slot_label": "Tue",
      "session_type": "easy_run",
      "duration_minutes": [30, 35],
      "constraints": ["finish_by_06_45"]
    }
  ],
  "plan_rationale": [
    "athlete prefers four runs per week",
    "recent Achilles sensitivity argues for one controlled quality session this week"
  ],
  "safety_rules": [
    "stop or downgrade if Achilles symptoms rise",
    "no back-to-back hard days"
  ]
}
```

This object should already include athlete overrides.

It should not require the writer to reverse-engineer athlete intent from generic session tokens.

## 12. Persistence Boundary
The system should persist the resolved athlete-shaped plan, not only the coarse scaffold.

Persisted plan state should include:
- structural commitments,
- current week recommendations,
- rationale,
- open questions if any,
- safety notes,
- confidence/provisional status where relevant.

Persisting only a generic `weekly_skeleton` invites regression on later turns.

## 13. Response Generation Boundary
Response generation should never receive raw `weekly_skeleton` for normal coaching replies.

It should receive:
- what changed,
- what remains stable,
- what the athlete should do this week,
- why the plan fits them,
- safety/if-then rules,
- what not to reopen.

If internal scaffold terms survive to the writer, the architecture is still wrong.

## 14. Communication Rules When Overriding Athlete Preference
When the system narrows or overrides an athlete’s requested structure, it should sound like coaching judgment, not refusal.

Good pattern:
- acknowledge the athlete’s stated preference,
- explain the narrower choice using concrete evidence,
- preserve agency for later progression.

Example:
"I heard that two quality sessions can fit your normal training. I’m keeping this block to one for now because the recent inconsistency and Achilles sensitivity matter more than theoretical capacity."

For advanced athletes:
"Given your history handling two quality touches well, that remains available in this block, but this week still only needs one."

## 15. Required Engine Outputs
The advanced rule engine should emit, at minimum:
- `athlete_capability_tier`
- `preference_authority`
- `training_judgment_trust`
- `execution_capacity_trust`
- `quality_policy`
- `structure_flexibility`
- `reason_codes`
- `deterministic_fallback_scaffold`

Example `reason_codes`:
- `unknown_training_history`
- `demonstrated_quality_tolerance`
- `injury_risk_present`
- `advanced_self_management_signals`
- `recent_inconsistency`

## 16. Key Invariants
- `weekly_skeleton` is allowed as an internal scaffold.
- `weekly_skeleton` is not the athlete-facing weekly contract.
- athlete structural preferences and safety constraints must be resolved before response generation.
- deterministic caution should narrow the feasible envelope, not flatten every week into the same generic template.
- advanced athletes should gain planning freedom only from evidence, not from assertive language alone.

## 17. Non-Goals
This spec does not require:
- adaptive ML scoring,
- opaque athlete scoring,
- removing deterministic safety guardrails,
- trusting athletes blindly,
- writing code immediately.

## 18. Implementation Sequencing
Recommended order:

1. Audit all current uses of `weekly_skeleton`.
2. Introduce the resolved athlete-facing week contract.
3. Add capability tier and trust outputs to the deterministic planning envelope.
4. Replace early absolute intensity suppression with bounded intensity policy except in true safety cases.
5. Add a preference hydration layer that resolves athlete overrides before persistence.
6. Persist the resolved plan.
7. Remove raw scaffold access from response generation for normal coaching flows.
8. Add end-to-end tests covering advanced-vs-unknown athlete freedom, negotiated structure persistence, and non-regression across later turns.

## 19. Success Criteria
The design is successful when:
- advanced athletes no longer get flattened into beginner-safe generic weeks without evidence,
- unknown athletes still get protective planning,
- athlete-negotiated structure does not regress on later turns,
- response generation sounds like coaching tailored to the athlete rather than a restatement of internal planning tokens.
