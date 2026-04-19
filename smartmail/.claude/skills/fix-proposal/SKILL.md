---
name: fix-proposal
description: Read an athlete-sim report and write fix proposals as markdown files. Does NOT change code. Each proposal is a hypothesis about a coaching quality issue and how to fix it, ready for /issue-fixer to evaluate and apply.
---

# Fix Proposal — Proposal Writer

You read an athlete-sim report, diagnose each issue to its code-level root cause, and write one markdown proposal file per issue. You do NOT change any code.

## Arguments

`$ARGUMENTS`

Accepted forms:
- `/fix-proposal` — reads latest report from `sam-app/.cache/athlete-sim-report.md`
- `/fix-proposal path/to/report.md` — reads a specific report

## Process

1. Read the sim report's "Issues for /fix-proposal" section.
2. For each issue, trace it through the pipeline to find the likely root cause:
   - Read relevant source files — prompts in `sam-app/email_service/skills/`, orchestration in `sam-app/email_service/business.py`, `coaching.py`, `conversation_intelligence.py`, `inbound_rule_router.py`, memory in `sectioned_memory_*.py`, `memory_compiler.py`
   - Read the CLAUDE.md sub-guides if needed
   - Identify the specific file, function or class, and mechanism that caused the issue
3. Write one markdown proposal file per issue to `sam-app/coach-proposals/`.
4. Print a summary of proposals written.

## Proposal filename

```
sam-app/coach-proposals/YYYY-MM-DD-<slug>.md
```

Where `<slug>` is 2-4 lowercase words describing the issue (e.g. `2026-04-05-generic-onboarding-reply.md`).

## Proposal format

```markdown
---
proposal_id: YYYY-MM-DD-<slug>
created_at: <ISO-8601 UTC>
status: open
issue_tags: [<tags>]
affected_files: [<file paths>]
confidence: <1-5>
estimated_cx_impact: <1-5>
---

## Source
Sim: <sim_id> · Persona: <name> · Turns: <numbers>

## Issue
<One sentence: what the athlete experienced and what trust damage it caused.>

Athlete sent: "<verbatim or close paraphrase>"

Coach replied: "<the problematic excerpt>"

## Diagnosis
<Which file, function, and mechanism caused this. Be specific about the mechanism — not just the module name, but what it does or fails to do that produces the bad output.>

## Proposed change
<Prose description precise enough that /issue-fixer can implement it without re-reading the source. No code. State what should change and where.>

## Why this fixes it
<Causal chain: change → behaviour change → trust impact.>

## Risks
<What could break or regress. Flag explicitly if touching coaching prompts (size impact) or rule_engine.py (high risk).>

## Verification
Suggested re-run: `/athlete-sim persona=<name> focus=<issue_tag> turns=<N>`
```

## Valid issue_tags

```
missed_fact, generic_reply, ignored_emotion, weak_guidance, hallucinated_context,
unsafe_push, missed_continuity, overloaded_reply, unclear_priority, too_vague,
ignored_explicit_instruction, reopened_resolved_topic, schedule_inconsistency,
communication_style_mismatch
```

## Guidelines

- One proposal per distinct root cause. If multiple turns share the same cause, list all turns in Source.
- If you cannot reach confidence >= 2, skip the proposal and explain why in your printed summary.
- Do not propose changes to `rule_engine.py` without flagging high risk in Risks.
- Do not propose DynamoDB schema changes — table structure is fixed.
- If the fix involves editing a prompt, note the size impact (adding, removing, or neutral).
