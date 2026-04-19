---
proposal_id: 2026-04-05-time-availability-sessions-gap
created_at: 2026-04-05T12:00:00Z
status: discarded
discarded_reason: Worth fixing, but it touches broader intake gating across sports and was lower priority than guaranteeing every athlete gets a reply.
issue_tags: [missed_fact, ignored_explicit_instruction]
affected_files:
  - sam-app/email_service/profile.py
  - sam-app/email_service/skills/planner/profile_extraction_prompt.py
  - sam-app/email_service/skills/planner/profile_extraction_validator.py
  - sam-app/email_service/coaching.py
  - sam-app/email_service/skills/coaching_reasoning/
confidence: 4
estimated_cx_impact: 4
---

## Source
Sim: n/a (user-reported thread) · Persona: cycling rebuild / general fitness · Turns: 1 (initial + boundaries) → 2 (coach asks sessions + injuries) → 3 (athlete answers injuries/goals; does not state sessions/week)

## Issue
The coach’s earlier email explicitly asked how many training sessions per week the athlete could commit to. The athlete answered injury status and FTP-related goals but never gave session frequency. The next reply advanced to full planning without re-asking or acknowledging that piece, so the athlete experiences the coach as not listening to the full prior question set.

Athlete sent: "I don't have any injuries... kinda inflexible... I want to improve my FTP and be able to sustain longer and harder rides."

Coach replied: (no mention of weekly session count; jumps to "easy 30-minute ride" and weekly zone/km targets.)

## Diagnosis
`profile.py` defines “meaningful” `time_availability` as any non-empty normalized slice of `time_availability`—including **`availability_notes` alone** (see `_normalize_time_availability` + `_has_meaningful_time_availability`). The planner extraction prompt steers the model to “prefer partial capture” and to put schedule caveats in `availability_notes`. When the athlete already stated weekly volume boundaries (e.g. 300 minutes in active zones, 100 km/week) in an earlier turn, those notes can satisfy the intake gate **without** ever capturing `sessions_per_week`. `get_missing_required_profile_fields` then clears `time_availability`, `_resolve_reply_mode` leaves intake, and coaching proceeds as if scheduling capacity were known. The failure is **not** primarily the final writer “forgetting” copy—it is the **contract** that weekly volume text counts as complete time availability, which is a different question than “how many rides/sessions per week.”

## Proposed change
Tighten the intake contract so “sessions per week or explicit unknown” is not implicitly satisfied by volume-only notes. Concretely: (1) Update profile gating so `_has_meaningful_time_availability` requires either a non-empty `sessions_per_week`, **or** structured evidence that the athlete cannot quantify sessions (e.g. allow a dedicated “unknown / flexible” sentinel via extraction), **or** keep `time_availability` missing when only volume targets exist without session cadence—whichever matches product intent; align `profile_extraction_prompt`/validator with the same rule. (2) In `coaching_reasoning` (directive stage), when `decision_context` still reflects partial scheduling intake or when inbound_body omits an answer to a clearly asked scheduling question from the thread, the directive should include a `content_plan` item that re-asks or acknowledges the gap **before** locking a weekly structure. (3) Optionally thread “pending questions” from outbound into memory/brief—only if you want defense-in-depth beyond field gating.

## Why this fixes it
The pipeline stops “closing” time availability on volume metrics alone, so reply mode and clarification machinery stay engaged until session cadence is explicit or explicitly deferred. The coach’s email then naturally follows up on the unanswered part of the prior message instead of jumping ahead.

## Risks
Stricter gating may prolong intake for athletes who only speak in weekly totals; mitigate with allowed “unknown/flexible” extraction and conversational one-line prompts. Touching `profile.py` affects all sports—verify extraction behavior with fixtures. Prompt edits in `coaching_reasoning` have **size impact** (small add unless you duplicate rules across sports).

## Verification
Suggested re-run: `/athlete-sim persona=cycling_rebuild focus=time_availability turns=3` (or a hand-built thread where message 1 states only weekly km/min and message 2 answers injury without sessions).
