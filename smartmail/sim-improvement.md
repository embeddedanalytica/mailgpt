# Athlete Sim Reliability Plan

## Problem

The simulated athlete degenerates into repetitive loops in longer conversations, producing useless test data. LAS-001 repeats "I'll send the check-in tomorrow" for 20 straight turns. LAS-002/003 have milder but similar stalls. Root cause: no state tracking, no narrative structure, no anti-repetition mechanism — the LLM gets the full transcript + brief and freewheels.

## Layers (in implementation order)

### Layer 1: Prompt guardrails
**Effort:** 15 min | **Impact:** Eliminates worst degenerate loops

Add two rules to `ATHLETE_REACTION_SYSTEM_PROMPT` in `athlete_simulation.py`:

1. **Follow-through rule:** "When you have promised to send data (check-in, logs, files, dates), you MUST follow through within 1-2 turns by generating realistic invented data. Real athletes send the data — they don't email their coach 10 times saying 'I'll send it tomorrow.'"

2. **Advance rule:** "Never send a message that is substantially the same as your previous message. If the coach acknowledged your last message, advance: report results, introduce a new concern, ask a new question, or move to the next phase of your training."

### Layer 2: Deterministic anti-repetition guard
**Effort:** 30 min | **Impact:** Hard backstop that catches any remaining loops

Before calling the athlete LLM, compare the last 3 athlete messages for similarity (simple word-overlap ratio). If >60% similar, inject an override instruction into the payload:

```
ANTI-REPETITION OVERRIDE: Your last 3 messages were very similar. You MUST change direction:
- If you promised data, generate realistic invented numbers NOW
- If you're confirming something already confirmed, STOP and introduce a new topic
- If the conversation has stalled, escalate, introduce a complication, or jump to your next goal
```

Implementation: add a `_check_repetition(transcript)` function in the runner that returns an optional override string. Pass it into the athlete payload as a new field `conversation_directive` that the system prompt instructs the LLM to obey.

### Layer 3: Conversation phase scripts
**Effort:** 1-2 hrs per scenario | **Impact:** Structured narrative arc, realistic progression

Add a `conversation_phases` list to each scenario in `athlete_agent_bench.md`. Each phase defines what the athlete should be doing and when to advance:

```json
{
  "conversation_phases": [
    {
      "label": "intake",
      "turns": "1-3",
      "objective": "Share key constraints, get an initial plan from coach",
      "reveal": ["work schedule", "6:45am cap", "Achilles history", "4 runs/week preference"],
      "advance_when": "coach delivers a first-week plan"
    },
    {
      "label": "week1_execution",
      "turns": "4-6",
      "objective": "Report Week 1 results with real data, give feedback on plan fit",
      "actions": ["Send check-in: invent realistic HR, sleep, RPE, duration numbers"],
      "reveal": ["sleep variability pattern", "preferred RPE range"],
      "advance_when": "coach responds to data with adjustments or confirmation"
    },
    {
      "label": "complication",
      "turns": "7-10",
      "objective": "Introduce a disruption (travel, niggle, schedule change, life stress)",
      "reveal": ["upcoming travel", "mild hip tightness or Achilles flare"],
      "advance_when": "coach adjusts plan for the disruption"
    },
    {
      "label": "progression",
      "turns": "11-15",
      "objective": "Report improving fitness, push for next phase or race-specific work",
      "actions": ["Send Week 3-4 data showing positive adaptation"],
      "reveal": ["race selection reasoning", "fueling preferences"],
      "advance_when": "coach transitions to next training phase"
    },
    {
      "label": "resolution",
      "turns": "16-20",
      "objective": "Taper, race, debrief, set up next goal cycle",
      "reveal": ["race result", "post-race recovery needs", "next goal hints"],
      "advance_when": "natural conversation end"
    }
  ]
```

The runner determines the current phase by turn number and injects it into the athlete payload as `current_phase`. The system prompt tells the LLM: "Follow the phase objective. When the advance condition is met, move to the next phase's behavior."

This replaces the vague "100-turn" pacing instructions in the briefs with concrete structure that fits the actual 20-25 turn runs.

### Layer 4: Open-commitment tracker
**Effort:** 1 hr | **Impact:** Prevents the "promise but never deliver" failure mode

The runner maintains a simple list of open commitments extracted from the athlete's messages. Before each athlete turn, scan the last athlete message for commitment patterns ("I'll send", "I'll confirm", "will upload", "by Friday") and add them to a `pending_commitments` list.

Inject into the athlete payload:
```json
{
  "pending_commitments": [
    {"what": "send check-in data (HR, sleep, RPEs)", "promised_turn": 5, "turns_ago": 3}
  ]
}
```

System prompt instruction: "If pending_commitments shows something you promised 2+ turns ago, fulfill it NOW by generating realistic data. Do not promise again."

Implementation: keyword-based extraction is sufficient — no LLM needed. Look for "I'll", "I will", "will send", "by [day]" patterns in athlete messages and track them until the athlete sends a message that plausibly fulfills the commitment (contains numbers, data, or "here is/are").

## Fix the scenario briefs

Independent of the layers above, update the three scenario briefs:

1. **Remove "100 turns" references** — the runs are 20-25 turns. Pacing instructions should match actual run length.
2. **Add concrete data generation instructions** — "When reporting training data, invent realistic numbers: HR 55-75 resting, RPE 4-8, session durations matching the plan, sleep 5.5-8 hrs. Make the numbers tell a story (gradual adaptation, occasional bad night, one session cut short)."
3. **Add phase transition cues** — even without Layer 3, the briefs should say "By turn 5-6 you should be reporting actual training results, not still in intake."

## Sequencing

| Step | What | Validates |
|---|---|---|
| 1 | Layer 1 (prompt) + brief cleanup | Run LAS-001 — should break the repetition loop |
| 2 | Layer 2 (anti-repetition guard) | Run all 3 — deterministic backstop catches any remaining loops |
| 3 | Layer 3 (phase scripts) for LAS-001 | Run LAS-001 — should show realistic 25-turn progression |
| 4 | Layer 3 for LAS-002 and LAS-003 | Run all 3 — full validation |
| 5 | Layer 4 (commitment tracker) | Run all 3 — verify commitments are fulfilled |

Each step is independently testable. Layer 1 alone should fix the worst case (LAS-001). Layers 3+4 make the sim structurally reliable.

## Success criteria

A sim run is "reliable" when:
- No 3+ consecutive athlete messages are substantially the same topic/content
- Promised data is delivered within 2 turns of the promise
- The conversation covers at least 3 distinct coaching phases (intake → execution → complication or progression)
- Judge scores show variance that tracks real coaching quality, not artificial stalls
