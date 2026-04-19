---
proposal_id: 2026-04-05-swim-intensity-vs-weekly-cap
status: applied
applied_at: 2026-04-05T23:50:00Z
applied_summary: Added coaching_reasoning decision rule to label weekly swim total vs single hard-session yard cap explicitly; ban using "total" for per-session caps.
issue_tags: [unclear_priority, schedule_inconsistency]
confidence: 4
estimated_cx_impact: 4
---

## Source
Sim: sim-2026-04-05-1810Z · Persona: Keiko · Turns: 11, 12

## Issue
The coach used ~3,400 yards to mean a single high-intensity swim session in some turns, but another reply phrased it so it read like total weekly swim volume—dangerous until the athlete challenged it.

> "Weekly swim-volume guardrail: 2–3 sessions; ≤3,400 yds total"

## Diagnosis
`skills/response_generation/prompt.py` and `skills/coaching_reasoning/prompt.py` — the writer reuses shorthand for “one hard session capped at X yards” without always pairing it with an explicit weekly total line, so mobile readers can parse “total” as weekly yards.

## Proposed change
Whenever two caps appear, use a fixed template in the same paragraph: **Weekly swim total: A–B yds across N sessions.** **Hard session cap (single session only): ≤C yds.** Ban sentences that put “total” next to the intensity cap without the words “session” or “hard swim.” Add a self-check: weekly total must be ≥ hard-session cap unless explicitly in a taper.

## Why this fixes it
Session caps stop being mistaken for weekly caps on a quick scan.

## Risks
Slightly longer replies; minimal product risk.
