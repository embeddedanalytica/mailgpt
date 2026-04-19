---
proposal_id: 2026-04-06-reply-html-entity-corruption
created_at: 2026-04-06T00:00:00Z
status: discarded
discarded_reason: High-value hygiene issue, but a complete no-reply on normal athlete messages was more urgent for this run.
issue_tags: [hallucinated_context, unclear_priority]
affected_files:
  - sam-app/email_service/skills/response_generation/
  - sam-app/email_service/skills/obedience_eval/
  - sam-app/email_service/coaching_reply_rendering.py
confidence: 4
estimated_cx_impact: 4
---

## Source
Sim: athlete-sim-1775447077-3f6dc652@example.com · Persona: Priya (time-crunched runner) · Turns: multiple (e.g. week 2 “reality check” onward)

## Issue
Coach text included **broken HTML entities and merged tokens** where the athlete should see readable ranges and punctuation, e.g. `306ndash;45 minutes`, `RPE 36ndash;4`, `we6rsquo;re`, and later **nonsense duration tokens** like `30940 min` / `45960 min` in the same paragraph as “conversational run.” That reads like a corrupted template and destroys trust in any numbers in the email.

Athlete asked for three effort-based sessions; coach replied with garbled minute ranges and typos that look like **encoding or detokenization errors**, not coaching judgment.

## Diagnosis
Final body is produced by **`response_generation`** and validated by **`obedience_eval`** without a **deterministic post-pass** that rejects malformed numeric ranges and HTML entities in the **plain-text email channel**. The model sometimes emits:
- Partial HTML entities (`ndash`, `rsquo`) without `&` / `;` handling in plain text
- **Digit concatenation** adjacent to words (“30” + “6” + “ndash” merge paths) seen in `prescription-numeric-integrity` proposal but here specifically **looks like entity + dash corruption**
The failure is **output hygiene**, not rule-engine logic.

## Proposed change
(1) Add a **plain-text sanitizer** in the send path (or response_generation validator): decode or strip malformed `*ndash*`, `*rsquo*` patterns; reject or rewrite lines containing `ndash` / `rsquo` as literal substrings in athlete-facing bodies. (2) In **`obedience_eval`**, add a violation type for **entity garbage** or extend **`metadata_leak` / numeric integrity** checks to fail closed when `ndash` appears without proper context. (3) In **`coaching_reasoning`**, avoid emitting ranges with en-dash in structured fields if the writer layer mishandles them—prefer **hyphen or “to”** in directives for plain-text email (small prompt tweak, **neutral size** if ranges move to words).

## Why this fixes it
Athletes see human-readable durations and effort bands; compliance checks catch corruption before send.

## Risks
Over-aggressive stripping could remove legitimate technical terms—scope the rule to known bad patterns from traces.

## Verification
Re-run Priya-style sim turns; grep outbound for `ndash`, `rsquo`, `6rsquo`.
