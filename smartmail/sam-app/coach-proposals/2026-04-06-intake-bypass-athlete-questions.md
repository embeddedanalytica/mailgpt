---
proposal_id: 2026-04-06-intake-bypass-athlete-questions
created_at: 2026-04-06T00:00:00Z
status: discarded
discarded_reason: Strong coaching-quality issue, but the response-generation silence bug was a more immediate trust breaker and narrower fix for this run.
issue_tags: [ignored_explicit_instruction, generic_reply]
affected_files:
  - sam-app/email_service/coaching.py
  - sam-app/email_service/skills/coaching_reasoning/
  - sam-app/email_service/response_generation_assembly.py
confidence: 4
estimated_cx_impact: 5
---

## Source
Sim: athlete-sim-1775444391-d7ad11a3@example.com · Persona: semi-retired cyclist (synthetic sim) · Turns: 13–19 (send records in trace)

## Issue
Across many consecutive turns the athlete asked specific, answerable coaching questions (best day for a longer ride, fueling disclosure, structured vs accidental surges, knee-friendly cadence cues, volume vs bad day, etc.) while also giving rich ride context. The coach reply repeatedly **restarted a long intake checklist** (primary goal, weekly volume, knee details, etc.) and **did not answer the question in the subject line**, so the athlete experiences the product as a broken form, not a coach.

Athlete sent: e.g. "If I'm semi-retired, is there a 'best' day for a longer ride or does it not matter?"

Coach replied: "I can give you a precise answer… but I need a couple quick profile details first…" followed by a long bullet list, without answering the scheduling question.

## Diagnosis
When `reply_mode` stays **`intake`** or **`clarification`** because `missing_profile_fields` or `clarification_needed` remains true, **`coaching_reasoning`** and/or the directive contract **prioritize profile completion** over **thread Q&A**. The writer is steered to collect fields (see `build_response_brief` `decision_context` with `clarification_questions`) and may produce **intake-only** directives with **no `content_plan` slot for the athlete’s explicit question**. There is no enforced **hybrid**: “answer this turn’s question in ≤N sentences, then ask for missing fields,” so multi-turn sims stall in a **repeated intake template** even when the athlete is not a first-time sender.

## Proposed change
In **`coaching_reasoning`** (directive schema / operational rules): when inbound contains a **clear question** (scheduling, fueling, technique) and the system is still in intake/clarification, require the directive to include **at least one `content_plan` item that answers or partially answers that question** within safe bounds (no medical diagnosis), **then** one item for remaining profile gaps—unless the question truly cannot be answered without a specific missing field (e.g. primary goal), in which case the directive must **say so in one sentence** before asking. In **`response_generation`**, add a short rule: if `delivery_context.inbound_body` contains a question and `decision_context.clarification_needed` is true, **do not** emit a reply that is only a checklist; the opening must acknowledge or answer the question. Optionally cap **intake bullet count** per turn (e.g. max 4 asks) to reduce wall-of-questions fatigue.

## Why this fixes it
Athletes stay engaged: they get value each turn while profile still completes. The sim no longer reads like infinite onboarding.

## Risks
Prompt size **increase** (small addition). Over-answering without profile could worsen safety in edge cases—keep “must have goal before pacing targets” as an explicit exception path.

## Verification
Suggested re-run: `/athlete-sim` with a persona that asks specific questions while profile incomplete; confirm each reply answers at least one question or states why it cannot yet.
