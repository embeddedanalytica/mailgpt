---
proposal_id: 2026-04-05-multi-part-question-answering
status: applied
applied_at: 2026-04-05T23:50:00Z
applied_summary: Added coaching_reasoning decision rule requiring content_plan to cover each distinct sub-question in multi-part inbound mail.
issue_tags: [hallucinated_context, missed_fact, ignored_explicit_instruction]
confidence: 3
estimated_cx_impact: 3
---

## Source
Sim: sim-2026-04-05-1810Z · Persona: Keiko · Turns: 8, 9

## Issue
The coach mis-described the athlete’s swim session (e.g. claimed a ~3,200-yard “CSS portion” that didn’t match her 12×100-style main set) and did not directly answer whether a disclosed 6×800 track workout violated an earlier “easy runs only” period—the athlete had to re-ask.

> "Session 3 included a ~3,200-yard CSS portion" (misaligned with what she actually ran)

## Diagnosis
`skills/response_generation/prompt.py` and `skills/coaching_reasoning/prompt.py` — the generator collapses multi-part inbound mail into a narrative and sometimes affirms numbers that do not match the athlete’s text instead of answering (1)(2)(3) explicitly.

## Proposed change
If inbound has multiple questions or a correction plus a question, require `content_plan` to carry one bullet per question and the final email to use numbered items or short subheads so none are skipped. Add a self-check: when repeating athlete numbers, quote them exactly; when adjudicating rules (e.g. easy-only), state yes/no with one sentence of reasoning.

## Why this fixes it
Stops confident wrong summaries and forces clear compliance answers on multi-part check-ins.

## Risks
More structured tone unless wording is kept conversational.
