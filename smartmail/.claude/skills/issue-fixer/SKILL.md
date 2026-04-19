---
name: issue-fixer
description: Review all open fix-proposal markdown files, pick the best ones to implement, apply them as code changes, and mark the rest as discarded.
---

# Issue Fixer — Proposal Evaluator and Applier

You read all open proposals from `sam-app/coach-proposals/`, decide which to apply, implement the winners, and update every proposal's `status` field in its frontmatter.

## Arguments

`$ARGUMENTS`

Accepted forms:
- `/issue-fixer` — review all open proposals
- `/issue-fixer max=3` — apply at most N proposals in this run (default: no limit)
- `/issue-fixer filter=generic_reply` — only consider proposals with a matching issue_tag

## Process

### 0. Read project constraints first

Read `CLAUDE.md` (root) before touching anything. **True Invariants** and **Engineering Philosophy** are hard constraints — a proposal that violates them is discarded regardless of confidence or impact score.

### 1. Load all open proposals

Read every `*.md` file in `sam-app/coach-proposals/` where frontmatter `status: open`. Read all of them before making any decisions.

### 2. Evaluate and rank

Score each proposal on:
- `confidence` (1-5) — how certain is the root cause
- `estimated_cx_impact` (1-5) — how much does this hurt real athletes
- `affected_files` — well-scoped and low-risk, or touching something critical
- Risks section — any red flags

Discard without applying if:
- `confidence` <= 2 with no corroborating proposals
- Risks mention `rule_engine.py`, DynamoDB schema, or auth/security
- Two proposals describe the same fix — pick higher confidence, discard the duplicate

### 3. Apply winners

For each proposal you decide to apply:
1. Read the files listed in `affected_files`
2. **Diagnose the root cause yourself.** The proposal's "Proposed change" is a hypothesis, not an implementation spec. Trace the problem to the layer that owns it (see `skills/CLAUDE.md` Layer Ownership). Fix at the source — do not add downstream checks that compensate for an upstream failure.
3. Run unit tests: `PYTHONPATH=sam-app/email_service python3 -m unittest discover -v -s sam-app/tests/email_service -p "test_*.py"`
4. If tests pass — update frontmatter: `status: applied`, add `applied_at: <ISO-8601>` and `applied_summary: <one sentence of what you actually changed>`
5. If tests fail — revert, update frontmatter: `status: blocked`, add `blocked_reason: <what failed>`

### 4. Discard losers

Update frontmatter: `status: discarded`, add `discarded_reason: <brief reason>`.

### 5. Print a summary

```
Applied:   N
Discarded: N
Blocked:   N

Applied:
  - <proposal_id>: <one line of what changed>
  - Verification: <suggested re-run command from proposal>

Discarded:
  - <proposal_id>: <one line reason>
```

## Context routing by issue type

Start with the CLAUDE.md for the area, then follow the key files.

| Issue tag | Start here | Key files |
|---|---|---|
| `generic_reply` `too_vague` `weak_guidance` | `sam-app/email_service/skills/response_generation/CLAUDE.md` | `skills/response_generation/prompt.py`, `response_generation_contract.py`, `response_generation_assembly.py` |
| `missed_continuity` `missed_fact` | `sam-app/email_service/skills/memory/CLAUDE.md` | `skills/memory/sectioned/prompt.py`, `sectioned_memory_contract.py`, `memory_compiler.py`, `coaching_memory.py` |
| `hallucinated_context` | `sam-app/email_service/skills/memory/CLAUDE.md` | `sectioned_memory_reducer.py`, `sectioned_memory_contract.py`, `memory_compiler.py` |
| `ignored_explicit_instruction` `reopened_resolved_topic` | `sam-app/email_service/skills/CLAUDE.md` | `skills/obedience_eval/`, `skills/coaching_reasoning/`, `coaching.py` |
| `schedule_inconsistency` | `sam-app/email_service/skills/CLAUDE.md` | `skills/coaching_reasoning/`, `rule_engine.py` (read-only), `response_generation_assembly.py` |
| `overloaded_reply` `communication_style_mismatch` | `sam-app/email_service/skills/response_generation/CLAUDE.md` | `skills/response_generation/prompt.py`, `response_generation_contract.py` |
| `ignored_emotion` `unsafe_push` | `sam-app/email_service/skills/response_generation/CLAUDE.md` | `skills/response_generation/prompt.py`, `skills/coaching_reasoning/` |
| `unclear_priority` | `sam-app/email_service/skills/CLAUDE.md` | `skills/coaching_reasoning/`, `skills/response_generation/prompt.py` |

**If not in the above:** read `sam-app/email_service/CLAUDE.md` for the full pipeline module map.

**Never change without escalating:**
- `rule_engine.py` — sole authority on training state
- `auth.py`, `rate_limits.py` — security gates
- `template.yaml` — DynamoDB schema is fixed
- `email_copy.py` — transactional copy only

## Guidelines

- Never apply more than one change to the same file without running tests in between.
- Prefer targeted prompt changes in `skills/` over broad logic changes in `business.py` or `coaching.py`.
- If a proposal's Proposed change is ambiguous, discard with reason `"underspecified — re-run /fix-proposal with more context"`.
