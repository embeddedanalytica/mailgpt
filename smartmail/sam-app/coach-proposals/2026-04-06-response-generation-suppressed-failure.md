---
proposal_id: 2026-04-06-response-generation-suppressed-failure
created_at: 2026-04-06T00:00:00Z
status: applied
applied_at: 2026-04-06T07:24:36Z
applied_summary: Returned a short transactional fallback reply from `email_copy.py` whenever response generation fails or yields an empty body, and locked the behavior in with tests.
issue_tags: [missed_continuity, generic_reply]
affected_files:
  - sam-app/email_service/coaching.py
  - sam-app/email_service/skills/response_generation/
  - sam-app/email_service/email_copy.py
confidence: 4
estimated_cx_impact: 5
---

## Source
Sim: (1) athlete-sim-1775447071-017f752c@example.com · Tommy — turn with `suppressed: true`, `lambda_body: "No reply sent due to response-generation failure."` (2) athlete-sim-1775449612-559f8b6a@example.com · Tommy XC — week 25 weather/gear question, same suppression pattern.

## Issue
The athlete sent a normal follow-up (5k plan clarification; regionals gear). **No coach reply was sent** due to response-generation failure. The next turn had to be a **“did my email go through?”** style message or skip a week, breaking continuity and eroding trust (“the coach ghosted me”).

## Diagnosis
Documented gap **RG1.8** in `skills/response_generation/CLAUDE.md`: on failure the pipeline **fails closed with no user-visible fallback**. `suppressed: true` in sim traces confirms the handler chose **silence** over a safe minimal ack. This is **`coaching.py` / send path** behavior when the LLM path returns empty or invalid.

## Proposed change
Implement a **tiered fallback**: (1) retry once with a **smaller model or shorter directive** if configurable; (2) if still failing, send a **transactional, non-coaching** message from **`email_copy.py`** (already the home for non-prompt copy) that says the coach could not generate a full reply and asks the athlete to resend or reply with one fact—**without** fabricating training. (3) Log and metric the failure with `response_generation_failure` for ops. Keep copy **short** to respect prompt boundaries (no coaching claims in fallback).

## Why this fixes it
Athletes always get a human-legible signal; silence is interpreted as abandonment.

## Risks
Fallback could feel cold if overused—monitor rate. Ensure fallback **never** prescribes workouts.

## Verification
Force a response-generation failure in test harness; assert outbound non-empty and obedience-safe.
