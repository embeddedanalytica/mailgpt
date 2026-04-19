---
proposal_id: 2026-04-05-micro-session-vs-weekly-floors
created_at: 2026-04-05T12:00:00Z
status: discarded
discarded_reason: Lower-confidence narrative mismatch than the no-reply failure, so it was not the top-priority single fix to apply now.
issue_tags: [schedule_inconsistency, unclear_priority]
affected_files:
  - sam-app/email_service/skills/coaching_reasoning/
  - sam-app/email_service/skills/response_generation/prompt.py
  - sam-app/email_service/response_generation_assembly.py
confidence: 3
estimated_cx_impact: 4
---

## Source
Sim: n/a (user-reported thread) · Persona: cycling rebuild · Turns: 3 (final coach reply)

## Issue
The athlete had already set personal weekly floors (300 minutes in active zones, ≥100 km/week). The coach simultaneously prescribed “an easy 30-minute ride” for the week and repeated the 300/100 km weekly expectations. That reads like either the week’s plan is only 30 minutes (contradicting the athlete’s stated training bandwidth) or the relationship between one prescribed session and weekly totals is unexplained—damaging trust for someone who gave clear volume boundaries.

Coach replied: "This week, you're set for an easy 30-minute ride... Let's ensure you hit your 300 minutes of active zones and 100km every week as planned."

## Diagnosis
The deterministic plan layer (`rule_engine` / weekly skeleton) often anchors early blocks with **conservative single-session prescriptions** (e.g. short easy work) while the athlete’s **stated constraints** live in profile notes as large weekly aggregates. `build_response_brief` passes athlete constraints and plan/decision context into the stack, but **`coaching_reasoning`** chooses the narrative emphasis and **`response_generation`** renders it. There is no enforced bridge that says: “this number is one session / anchor within a week that must still sum to your stated weekly floors,” or “your floors are athlete-owned; today’s prescription is X within that budget.” When both appear as flat sentences, the athlete infers a **schedule contradiction**.

## Proposed change
In **`coaching_reasoning`** directives for early-season or rebuild contexts, when `constraints_summary` or profile notes include explicit weekly minute/distance floors and the plan’s immediate prescription is a **small** session relative to those floors, require the directive to: (a) name the prescribed session as **one component** of the week (or the first step), not the whole week; (b) explicitly defer distribution of remaining volume to additional rides aligned with their floors, or ask how they want to split rides if still unknown; (c) avoid listing micro-prescription and macro-floors as parallel facts without one sentence linking them. In **`response_generation`** (`prompt.py` / directive constraint helpers), add a short rule: when both a single-session duration and athlete-stated weekly totals appear in the brief, the reply must use connective language (“within your 300/100 plan, start with…”, “in addition to other easy volume you already do…”) and must not imply the single session **is** the weekly plan unless the directive explicitly states that.

## Why this fixes it
Athletes stop interpreting a conservative anchor session as a cap that overrides their stated weekly architecture; the coach sounds aligned with their self-set boundaries.

## Risks
Slightly longer replies (mitigate with one tight bridge sentence). If the rule engine truly intends a **deload** week that conflicts with stated floors, the directive must surface that tension honestly—avoid automatic reconciliation that hides medical/deload intent (coordinate wording with `rule_engine` outputs, **without** changing engine semantics in this proposal).

## Verification
Suggested re-run: thread where athlete states high weekly floors and receives a short easy prescription from RE; check that output explicitly frames the short session inside the weekly envelope.
