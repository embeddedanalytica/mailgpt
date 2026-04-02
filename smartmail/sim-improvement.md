# Athlete Sim Reliability Plan

## Goal

Make the simulated athlete produce useful 20-25 turn conversations instead of stalling in repetitive loops.

A reliable run should:

- avoid obvious repetition loops
- follow through on explicit promises
- progress through a believable training conversation arc
- preserve enough variability that the judge is still measuring coach quality, not simulator failure

## Current failure

The current athlete sim can get stuck repeating near-identical follow-up messages for many turns. The clearest failure is LAS-001 repeatedly saying some version of "I'll send the check-in tomorrow" instead of sending data and moving the conversation forward.

The likely causes are straightforward:

- the athlete reaction prompt has no explicit anti-loop or follow-through rules
- the runner passes only transcript context, with no lightweight steering state
- the scenario briefs still describe a 100-turn relationship even though the actual runs are 20-25 turns
- the runner does not compute reliability metrics, so validation is mostly manual

## Design constraints

This plan should fit the code as it exists today:

- scenario fixtures are schema-validated and reject unknown fields
- the athlete simulator currently accepts only the existing payload fields unless we extend that contract
- the runner currently records transcript, judge output, and summary stats, but not repetition or commitment metrics

That means any structural additions must include fixture-loader, simulator-payload, and runner-summary changes together.

## Implementation order

### Layer 1: Prompt guardrails and brief cleanup

**Effort:** small

Add explicit rules to `ATHLETE_REACTION_SYSTEM_PROMPT`:

1. Follow-through rule:
   "If you told the coach you would send data, logs, splits, dates, or a check-in, you should usually deliver it within the next 1-2 turns instead of repeating the promise."

2. Anti-repeat rule:
   "Do not send a message that is substantially the same as your previous message. If the coach acknowledged your last note, move the conversation forward with data, a new concern, a concrete answer, or the next training question."

Update the scenario briefs in `test_bench/athlete_agent_bench.md` at the same time:

- remove references to "100 turns"
- align pacing instructions with 20-25 turn runs
- tell the athlete to start reporting concrete training results early, not stay in intake too long
- give simple guidance for invented training data ranges so the model has something concrete to generate

This layer is the cheapest improvement and should be attempted first.

### Layer 2: Deterministic repetition guard

**Effort:** moderate

Add a runner-side repetition detector before each athlete reaction call.

Recommended scope:

- inspect the last 3 athlete messages only
- normalize text aggressively enough to catch superficial wording changes
- compute a simple similarity score
- when all 3 are above threshold, inject a short override instruction into the athlete reaction payload

Example override:

```text
ANTI-REPETITION OVERRIDE:
Your recent messages are too similar. Change direction now.
- If you promised data, send it now
- If you already confirmed something, stop reconfirming it
- If the exchange has stalled, introduce a concrete update, complication, or next-step question
```

Implementation notes:

- add a runner helper such as `_detect_repetition(transcript) -> str | None`
- extend `AthleteSimulator.react_to_coach_reply(...)` to accept an optional `conversation_directive`
- update the athlete prompt so the model knows to obey `conversation_directive` when present

This layer should be treated as a hard backstop, not the primary behavior model.

### Layer 3: Explicit conversation phases, but turn-window based only

**Effort:** moderate to large

Keep this simple. Do not mix turn-based phases with semantic `advance_when` rules in the first version.

Add an optional `conversation_phases` field to each scenario, but make phase selection deterministic by turn window only.

Example shape:

```json
{
  "conversation_phases": [
    {
      "label": "intake",
      "start_turn": 1,
      "end_turn": 3,
      "objective": "Share key constraints and get an initial plan",
      "suggested_reveals": ["work schedule", "weekday time cap", "injury history"]
    },
    {
      "label": "early_execution",
      "start_turn": 4,
      "end_turn": 6,
      "objective": "Report first training results with concrete data",
      "suggested_actions": ["send check-in with sleep, duration, effort, and how the plan felt"]
    },
    {
      "label": "complication_or_adjustment",
      "start_turn": 7,
      "end_turn": 10,
      "objective": "Introduce a realistic snag, constraint, or adjustment need"
    },
    {
      "label": "progression",
      "start_turn": 11,
      "end_turn": 16,
      "objective": "Show adaptation, ask for progression, or clarify next training focus"
    },
    {
      "label": "resolution",
      "start_turn": 17,
      "end_turn": 25,
      "objective": "Close the current arc naturally and set up the next one"
    }
  ]
}
```

Implementation notes:

- first extend fixture validation to allow `conversation_phases`
- validate phase objects strictly
- in the runner, derive `current_phase` from `turn_number`
- pass `current_phase` into the athlete reaction payload
- update the athlete prompt to treat `current_phase` as guidance, not a rigid script

Do not add semantic phase transitions yet. The runner has no reliable state machine for "advance when coach does X," and adding one would be a separate project.

### Layer 4: Narrow commitment tracker

**Effort:** moderate

Track only explicit promises the athlete makes, and only for a narrow set of commitment verbs.

Recommended detection:

- "I'll send"
- "I will send"
- "I'll upload"
- "I'll share"
- "I'll confirm"
- "by Friday" or similar date promises only when tied to sending or confirming something

Recommended fulfillment rule:

- mark fulfilled only when the later athlete message plausibly addresses the promised item
- do not treat random numbers alone as fulfillment
- require either lexical overlap with the promised item or a stronger cue such as "here's the check-in", "here are the splits", "attaching", "my week looked like"

Payload addition:

```json
{
  "pending_commitments": [
    {
      "what": "send weekly check-in",
      "promised_turn": 5,
      "turns_outstanding": 2
    }
  ]
}
```

Prompt rule:

"If `pending_commitments` contains something you promised 2 or more turns ago, fulfill it now unless the coach's latest reply clearly made it irrelevant."

This should stay intentionally narrow. The goal is to stop the most obvious "I’ll send it later" loops, not build a full promise-understanding system.

## Validation and observability

The runner should compute explicit reliability metrics so each step can be judged consistently.

Add summary metrics such as:

- `max_consecutive_similar_athlete_messages`
- `repetition_alert_count`
- `open_commitments_created`
- `open_commitments_fulfilled`
- `max_commitment_age_turns`
- `phase_coverage`

These should be produced in the run summary, not inferred manually from raw transcripts.

## Scenario brief changes

Update all three scenarios with the same baseline cleanup:

1. Replace "100 turns" framing with language that matches the real 20-25 turn runs.
2. Tell the athlete to move from intake to actual reported training within the first quarter of the run.
3. Add lightweight invented-data guidance:
   - resting HR in a plausible range
   - sleep in a plausible range
   - session duration and effort that match the stated plan
   - occasional imperfect sessions so the data tells a story

If `conversation_phases` is added, keep the prose brief aligned with those phases instead of duplicating an entirely separate pacing model.

## Sequencing

| Step | Change | Validation |
|---|---|---|
| 1 | Layer 1 prompt changes + scenario brief cleanup | Run LAS-001 and confirm the obvious repetition loop is reduced or gone |
| 2 | Layer 2 repetition guard + repetition metrics | Run all 3 scenarios and inspect repetition metrics in summaries |
| 3 | Layer 3 turn-window phase support for LAS-001 | Run LAS-001 and confirm the conversation progresses through the intended arc |
| 4 | Layer 3 rollout for LAS-002 and LAS-003 | Run all 3 scenarios and compare phase coverage across runs |
| 5 | Layer 4 narrow commitment tracker + commitment metrics | Run all 3 scenarios and verify explicit promises are usually fulfilled within 2 turns |

## Success criteria

A run is reliable when all of the following are usually true:

- there are no obvious 3-message repetition loops
- explicit "I'll send/share/upload" promises are usually fulfilled within 2 turns
- the conversation reaches at least 3 distinct phases in a 20-25 turn run
- judge score patterns vary with coach behavior instead of collapsing because the athlete stalled

## Non-goals

This plan does not attempt to:

- build a full semantic state machine for conversation progression
- infer every implied commitment the athlete might make
- make the athlete maximally realistic at the cost of determinism

The target is simpler: remove the known failure modes with the minimum structure needed to make the benchmark useful.
