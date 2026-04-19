---
proposal_id: 2026-04-05-stale-plan-session-date
created_at: 2026-04-05T22:30:00Z
status: applied
applied_at: 2026-04-05T23:50:00Z
applied_summary: Added reference_date to fetch_current_plan_summary; roll next-session display date forward when behind inbound email calendar date; coaching passes effective_today.
issue_tags: [missed_continuity, schedule_inconsistency]
affected_files:
  - sam-app/email_service/dynamodb_models.py
  - sam-app/email_service/coaching.py
confidence: 4
estimated_cx_impact: 4
---

## Source
Sim: sim-2026-04-05-combined · Persona: Marcus — Anxious Beginner · Turns: 4, 8

## Issue
The coach told the athlete when the “next session” was using a **fixed calendar date that did not advance** with synthetic (or real) time, so replies said things like “Next session (2026-04-05)” many weeks later—breaking trust for anyone who notices the email’s own dates.

Athlete sent: (Turn 8) Vacation week recap; asking whether to add an extra day to catch up—synthetic thread time had moved well past early April.

Coach replied: (paraphrased from sim) Included guidance that referenced **“Next session (2026-04-05): 30 minutes easy effort”** (same anchor date as early in the relationship) despite later `date_received` values on inbound mail.

## Diagnosis
`fetch_current_plan_summary` in `dynamodb_models.py` builds a string from `get_current_plan` → `next_recommended_session`, whose **`date` field is set at plan creation** (`_build_default_current_plan` uses `_default_plan_start_date` from wall-clock time) and is **not recomputed per inbound message** using `effective_today`. That summary is injected into the LLM user payload via `build_llm_reply_body` in `coaching_reply_rendering.py` (“Current plan context: … Next session: &lt;date&gt;: …”).

The live harness **does** pass `effective_today` derived from the email `Date` header into `build_profile_gated_reply` / `_generate_llm_reply`, but **plan summary generation ignores it**. The model treats the embedded “Next session: YYYY-MM-DD” line as authoritative and repeats it in prose, producing **stale calendar references** that disagree with the athlete’s timeline.

## Proposed change
1. **Plumb `as_of` / `effective_today` into plan summary**  
   Extend `fetch_current_plan_summary(athlete_id, *, as_of_date: Optional[date] = None)` (or equivalent). When `as_of_date` is provided (from the same `effective_today` already passed through the coaching pipeline), **either**:
   - **Replace** the displayed `next_recommended_session.date` in the summary string with `as_of_date.isoformat()` when the stored plan date is **before** `as_of_date` and the plan has not been explicitly updated for a future session (simplest: “next session” means “today’s intended focus” in email-time), **or**
   - **Omit the absolute calendar date** from the human-readable summary and keep only type + target (e.g. “Next recommended session: easy — 30 minutes”) so the model does not anchor on a wrong day, **or**
   - **Roll forward** `next_recommended_session.date` in persisted `current_plan` when processing each inbound (heavier; touches plan mutation rules—only if product wants durable rolling dates).

2. **Call site**  
   In `coaching.py`, wherever `fetch_current_plan_summary(athlete_id)` is called, pass `effective_today` from the same closure that already feeds rule engine / continuity.

3. **Prompt-neutral guard (optional, small)**  
   If the summary still includes a date, add one line in the response-generation user assembly (not replacing rule-engine authority) that **“Plan context dates are bookkeeping; the athlete message’s timeline takes precedence.”** Prefer fixing data first to avoid prompt bloat.

## Why this fixes it
Aligning or removing stale **ISO dates** in `Current plan context` stops the writer model from **echoing impossible “next session” dates**. Athletes see replies that match the **email’s own clock**, restoring continuity and schedule credibility.

## Risks
- **Low–medium:** Changing summary text may affect tests that assert exact `plan_summary` strings; update fixtures.
- **Medium:** If you roll dates forward in DynamoDB without clear rules, you could conflict with `rule_engine` / planner expectations—prefer **summary-only** fixes first.
- **Not** `rule_engine.py` for the minimal fix.

## Verification
Suggested re-run: `/athlete-sim persona=Marcus turns=8 spread=7d` and confirm no reply embeds a **first-week-only** calendar date on later turns; or a focused sim that advances synthetic `Date` headers across months.
