# Last-Mile Obedience: Classification Fixtures

Failure taxonomy for coaching response obedience issues, drawn from live athlete-sim run `20260327T041920Z`.

## Failure Taxonomy

| Code | Name | Description |
|------|------|-------------|
| `reopened_resolved_topic` | Reopened Resolved Topic | Coach reopens a topic the athlete explicitly closed or already decided |
| `ignored_latest_constraint` | Ignored Latest Constraint | Coach fails to follow a specific instruction the athlete gave this turn or recently |
| `answered_from_stale_context` | Answered From Stale Context | Coach uses outdated facts when current-turn info contradicts them |
| `exceeded_requested_scope` | Exceeded Requested Scope | Coach expands beyond what the athlete asked for (length, breadth, extras) |
| `introduced_unsupported_assumption` | Introduced Unsupported Assumption | Coach states something as fact that was never provided or confirmed |
| `missed_exact_instruction` | Missed Exact Instruction | Coach fails to do what the athlete literally asked for |

---

## Classification Fixtures

### `reopened_resolved_topic`

**RT-1: Re-asked a choice the athlete already made (LAS-001, Turn 15)**

- Athlete: "I prefer next Tue. Counting starts from the Alfredson session last Saturday. I'll report morning stiffness next Tue AM as planned and keep this week's microcycle unchanged."
- Coach: "To lock in the week, please confirm whether the midweek easy-run should be next Tue or next Thu."
- Failure: Athlete already chose Tue. Coach asked again.

**RT-2: Reintroduced calendar dates after athlete flagged them as errors (LAS-001, Turn 13)**

- Athlete had flagged earlier calendar dates as inconsistent with the timeline.
- Coach: Reintroduced explicit dates (2026-03-31 / 2026-04-02) that the athlete had already identified as problematic.
- Failure: Reopened a resolved source of confusion.

**RT-3: Reintroduced week labels after athlete asked to stop (LAS-002, Turns 17, 20, 22)**

- Athlete (Turn 18): "Please stop labeling weeks (no 'Week 17' or 'initial_assessment') — just reference the locked 8‑week build to 24 Sep 2026."
- Coach (Turn 20): "You're in Week 20 of your initial assessment block."
- Coach (Turn 22): "You're in Week 22 of your initial_assessment block."
- Failure: Repeatedly reintroduced a label format the athlete explicitly asked to stop.

---

### `ignored_latest_constraint`

**IC-1: Violated three-line format request (LAS-002, Turn 9)**

- Athlete: "Send the three lines I asked for now: 1) Two must-not-miss sessions. 2) Confirm caps. 3) Calf flare rule."
- Coach: Sent four lines with a standalone "Acknowledged." opener.
- Failure: Athlete specified exact format. Coach exceeded it.

**IC-2: Replied when told not to unless safety concern (LAS-003, Turn 17)**

- Athlete: "Please only reply if you see a safety concern."
- Coach: "Week 11 hamstring check-in: no safety concerns detected. No safety concerns observed at this time. Please continue with your Monday status update."
- Failure: Athlete explicitly asked for no reply. Coach replied anyway with no safety concern to report.

**IC-3: Replied again when told not to, with no new info (LAS-001, Turn 21)**

- Athlete: "Please only reply if there's a change or concern."
- Coach: Sent a largely redundant acknowledgement restating the unchanged plan.
- Failure: Violated the communication boundary the athlete set.

---

### `answered_from_stale_context`

**SC-1: Claimed Garmin link not shared when it was in the same message (LAS-001, Turn 4)**

- Athlete: "Here's the read-only Garmin link: [link]. Ran Tue easy 35 min..."
- Coach: "I'll review the read-only Garmin link once you share it."
- Failure: Coach referenced a stale state (link not yet shared) when the current message contained it.

**SC-2: Hallucinated stale calendar date (LAS-001, Turns 7, 12, 25)**

- Coach repeatedly referenced "2026-03-27" as a future session date across multiple turns.
- The date was inconsistent with the thread timeline and appeared to come from an earlier, outdated context.
- Failure: Used a stale date instead of computing from current state.

**SC-3: Contradicted calf-swap specification with stale/altered values (LAS-002, Turn 13)**

- Athlete had established: Wed swap = 45–60 min easy trainer spin.
- Coach: Set Wed as 40 min easy spin with a contingency to swap to an easy run.
- Failure: Changed both the duration and the swap direction from what the athlete had locked.

---

### `exceeded_requested_scope`

**ES-1: Verbose reply when athlete asked for one-line confirm (LAS-002, Turn 12)**

- Athlete: "Quick one‑line confirm that (1) Friday stays protected easy and (2) you'll enforce the 20‑min travel brick cap next week."
- Coach: Sent a multi-sentence reply restating the same confirmation twice.
- Failure: Athlete asked for one line. Coach gave a paragraph.

**ES-2: Redundant plan restatement when nothing changed (LAS-001, Turns 17-20)**

- Across turns 17-20, athlete sent minimal check-ins. Coach responded each time with full plan restatements, week numbers, and monitoring rules.
- Failure: Coach repeated the full plan when the athlete only needed acknowledgement.

**ES-3: Did not deliver the short plan, asked for more info instead (LAS-002, Turn 1)**

- Athlete: "Prioritize ruthlessly; keep replies short." Listed top priorities and asked for two must-not-miss sessions.
- Coach: Asked for daily availability and travel schedule instead of providing the requested actionable.
- Failure: Expanded the scope of the interaction when the athlete wanted a narrow, immediate answer.

---

### `introduced_unsupported_assumption`

**UA-1: Asserted wrong current week number (LAS-003, Turns 3-9)**

- Athlete anchored Week 2 = week starting Mon 2026-03-02. Asked coach to compute current week from that anchor.
- Coach gave: Week 3, Week 4, Week 5, Week 6, Week 7, Week 8, Week 9 — all incorrect.
- Correct answer: Week 11 (as of 2026-05-08).
- Failure: Repeatedly asserted a week number without correct computation.

**UA-2: Labeled a new training block unprompted (LAS-001, Turn 24)**

- Coach: "You're in Week 1 of your controlled-load progression block."
- Athlete had not introduced or agreed to this block label.
- Failure: Introduced a planning construct the athlete didn't provide.

**UA-3: Claimed coach would detect athlete's calf symptoms (LAS-002, Turn 24)**

- Athlete: "I'll ping if the calf flares."
- Coach: "I'll inform you if the calf flares."
- Failure: Assumed the coach has observational access to the athlete's body. Reversed agency.

---

### `missed_exact_instruction`

**MI-1: Did not provide requested plan, deferred instead (LAS-003, Turn 1)**

- Athlete: Asked for "a single short, decisive 8‑week plan" with specific constraints.
- Coach: Asked multiple clarifying questions instead of providing a provisional plan.
- Failure: Athlete asked for the plan. Coach asked for more information instead.

**MI-2: Changed start week despite explicit correction (LAS-003, Turn 3)**

- Athlete: "you referenced starting from my 'Week 2'... earlier you said 'Week 1'... confirm you will start from Week 2."
- Coach: "Confirmed: I will start your 8-week conservative rebuild from Week 3 of the assessment, as you requested."
- Failure: Athlete said Week 2. Coach said Week 3 and claimed it was what the athlete requested.

**MI-3: Altered the athlete's two-run trigger to a one-run trigger (LAS-001, Turn 24)**

- Athlete: "If the post-run stiffness stays around ~30–40 minutes for the next two long runs..."
- Coach: Set a "reassess after the next long run" threshold (one run).
- Failure: Changed the athlete's explicit decision rule.

---

## Cross-Scenario Patterns

### Most damaging failures

1. **Repeated instruction violations** (LAS-002 week labels, LAS-003 week numbers, LAS-001 re-asking resolved choices): the coach fails to internalize an explicit correction and repeats the same error across turns.
2. **Reply when told not to** (LAS-001 Turn 21, LAS-003 Turns 17, 19): the coach cannot stay silent even when the athlete explicitly requests no reply.
3. **Scope expansion on narrow asks** (LAS-002 Turn 1, Turn 12): the coach defers or elaborates when the athlete wants a direct, constrained answer.

### Failure frequency by scenario

| Scenario | Athlete | Total Flagged Turns | Most Common Failure |
|----------|---------|---------------------|---------------------|
| LAS-001 | Runner rebuilding | 6 | `answered_from_stale_context`, `reopened_resolved_topic` |
| LAS-002 | Triathlete (Marcus) | 9 | `ignored_latest_constraint`, `exceeded_requested_scope` |
| LAS-003 | Marathoner (Maya) | 8 | `introduced_unsupported_assumption`, `missed_exact_instruction` |

### Root cause hypothesis

Most failures trace to the strategist or writer not treating the athlete's latest explicit instructions as hard constraints. Instead, they are treated as soft preferences that can be overridden by general coaching patterns (elaborate, restate, add context, use week labels).

---

## Source

All examples drawn from: `sam-app/.cache/live-athlete-sim/20260327T041920Z/`
- LAS-001: `las-001-attempt1-1774585160-616f79ed.jsonl`
- LAS-002: `las-002-attempt1-1774588978-1d0c425b.jsonl`
- LAS-003: `las-003-attempt1-1774593286-2d723467.jsonl`
