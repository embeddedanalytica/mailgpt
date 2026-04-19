---
proposal_id: 2026-04-05-reply-metadata-leak
status: discarded
discarded_reason: Proposes deterministic post-pass (regex stripping) which violates Engineering Philosophy #1 (LLM-first). Low CX impact (2). Existing metadata_leak violation type in obedience_eval already covers this via LLM evaluation.
issue_tags: [generic_reply]
confidence: 3
estimated_cx_impact: 2
---

## Source
Sim: sim-2026-04-05-1810Z · Persona: Raj · Turns: 5, 10

## Issue
Some coach replies appended a quoted email block (`From:` / `Sent:` / `Subject:`) after a `---` separator, so the body looked like a forward inside the message—not the HTML thread wrapper alone.

> "---\nFrom: athlete-sim-…@example.com\nSent: …\nSubject: …"

## Diagnosis
`coaching.py`, `skills/obedience_eval/runner.py`, `skills/obedience_eval/prompt.py` — the final LLM sometimes echoes thread-style quoting; `metadata_leak` exists in obedience taxonomy but may not always fire or correct, so bad text can still send.

## Proposed change
Add a deterministic post-pass on outbound body: if content after `---` matches email-header patterns (`^From:\s`, `^Sent:\s`), strip from `---` to EOF. Run even when obedience passes. Optionally run a parallel metadata_leak check not gated on directive content.

## Why this fixes it
Removes duplicate junk without relying on the writer model to behave.

## Risks
Edge case: legitimately teaching header literacy is nearly zero for this product.
