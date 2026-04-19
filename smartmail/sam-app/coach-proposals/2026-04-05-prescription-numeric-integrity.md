---
proposal_id: 2026-04-05-prescription-numeric-integrity
status: applied
applied_at: 2026-04-05T20:00:00Z
applied_summary: Strengthened coaching_reasoning with numeric grounding rule (operational_rules.json) and added fabricated-number red flags to doctrine (common_prescription_errors.md, common_coaching_failures.md) — all changes in the strategist layer only
issue_tags: [hallucinated_context, weak_guidance]
confidence: 4
estimated_cx_impact: 5
---

## Source
Sim: sim-2026-04-05-1810Z · Persona: Raj; Keiko · Turns: 4, 9, 1

## Issue
Coach replies sometimes contained impossible or corrupted numeric prescriptions: weekly run mileage in the thousands, swim volumes in the hundreds of thousands of yards, stride reps described as thousands of seconds.

> "Aim for roughly 3036 miles total this week" / swim lines like "632,500 yds" / "6 x 2010 seconds" and "859% effort"

## Diagnosis
`skills/response_generation/prompt.py`, `validator.py`, and `prompt_packs/coach_reply/v1/operational_rules.json` — the coaching_reasoning → response_generation path emits final email text without a deterministic sanity pass on units and magnitudes. Digit concatenation and implausible totals are not rejected before send.

## Proposed change
Add hard prompt rules: cap weekly run mileage and swim yards to physiologically plausible bands; stride prescriptions must use integer seconds in a tight band (e.g. 10–40) and rep counts 4–12; when giving weekly total plus session splits, require a one-line sum check. In `validator.py`, add plausibility checks on the final body (e.g. huge comma-separated yard values, weekly miles > 200) and fail closed or trigger a one-shot correction pass. Prefer structured prescription fields in the schema where possible so numbers validate before prose.

## Why this fixes it
Garbled numbers are caught or never emitted as free-form prose drift, so data-focused athletes can trust the digits.

## Risks
Aggressive patterns could false-positive on legitimate historical examples; schema changes touch tests and token budget.
