---
proposal_id: 2026-04-05-training-load-continuity
created_at: 2026-04-05T22:30:00Z
status: discarded
discarded_reason: Partially addressed by existing operational_rules long-run anchor line; full strategist schema + memory fields for canonical long-run minutes remains a larger change — defer to a dedicated story.
issue_tags: [missed_continuity, schedule_inconsistency]
affected_files:
  - sam-app/email_service/skills/coaching_reasoning/
  - sam-app/email_service/response_generation_assembly.py
  - sam-app/email_service/coaching_memory.py
confidence: 3
estimated_cx_impact: 3
---

## Source
Sim: sim-2026-04-05-combined · Persona: Raj — Data Maximalist · Turns: 10–12 (and related stride/long-run sequencing)

## Issue
After the athlete had progressed long runs to roughly **two hours** and discussed staged intensity, a later reply **reset the long run to 90 minutes** in a way that contradicted the agreed progression—exactly the kind of slip a **data-maximalist** athlete flags as “the coach isn’t tracking my plan.”

Athlete sent: (Turn 12, paraphrased) After a deload, asked whether to prioritize tempo vs strides; context included recent **~118 min** long run and recovery normalization.

Coach replied: (paraphrased) Instructed **strides** plus **hold long run at 90 minutes** this week—conflicting with the **~115–120 / ~118 minute** long-run level established turns earlier.

## Diagnosis
There is **no single structured, machine-checkable “current long-run prescription (minutes)”** that flows from persisted state → `coaching_reasoning` directive → `response_generation` as a hard fact. Weekly structure lives partly in **free-form strategist output**, partly in **rule_engine `today_action`**, and partly in **athlete memory notes**—none of which are guaranteed to carry **one canonical number** for “this week’s long run cap.”

Under load changes (deload, strides reintroduction), the **coaching_reasoning** stage can **re-default to conservative templates** (e.g. “90 min”) without reconciling against **recent coach commitments in the thread** or **memory**. `response_generation` is instructed to follow the directive, so it **faithfully renders** an internally inconsistent prescription.

## Proposed change
1. **Coaching reasoning (owning layer per CLAUDE.md)**  
   Extend the strategist schema / prompt so that when the topic is weekly load, it must emit explicit fields such as:
   - `prescription_anchors`: { `long_run_minutes`: int | null, `intensity_status`: str, ... }
   - Or a short **“Continuity check”** bullet in the directive: **must cite last agreed long-run duration** from memory or inbound before changing it.

2. **Memory refresh**  
   When the coach or athlete agrees a new long-run duration, ensure **sectioned memory** (or equivalent) stores **“Agreed long run: 118 min as of &lt;date&gt;”** so the next turn’s strategist sees it.

3. **Response generation**  
   Add a **directive constraint**: if the strategist’s numbers **conflict** with `prescription_anchors` / memory by more than a small tolerance, **surface a contradiction flag** upstream (validator) or **force reconciliation** in coaching_reasoning (preferred: fix upstream, not obedience hacks).

4. **Optional:** Obedience eval could flag “directive contradicts stated memory long run” only if the directive pack already exposes structured numbers—avoid regex on prose.

## Why this fixes it
A **single source of truth** for the current week’s key prescription makes **deload vs progression** a **state transition**, not a fresh draw from a generic template—so the coach stops **rewinding** long-run minutes without explanation.

## Risks
- **Prompt size:** coaching_reasoning prompts are already large; adding fields must be **tight** or **conditional** (only when training load is in scope). **Size impact: small add** if implemented as compact JSON fields + one reconciliation line.
- **Schema migration:** any new strategist output fields require validator + runner updates and tests.

## Verification
Suggested re-run: `/athlete-sim persona=Raj turns=12 spread=7d` with a scripted arc that escalates long run then **deloads**, and assert strategist output **does not** drop below last agreed duration without an explicit “reset because X” rationale in the directive.
