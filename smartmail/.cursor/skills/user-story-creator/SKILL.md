---
name: user-story-creator
description: Writes atomic, implementation-ready SmartMail user stories grounded in ROADMAP.md, DECISIONS.md, and README.md. Use when the user asks to create or generate a "user story", "story packet", "acceptance criteria", "split roadmap item", "story from ROADMAP", or "implementation-ready story". Do NOT use for writing code or implementing features—only for authoring story packets.
---

# High-Quality User Story Writing (SmartMail)

## Purpose

This skill defines how to write implementation-ready user stories that are atomic, clear, testable, and scope-safe for SmartMail (email-first, verification-gated, rate-limited, LLM-assisted).

Use this skill whenever generating new stories from `ROADMAP.md` + `DECISIONS.md` + `README.md`.

## Critical rules (before you start)

- **One primary outcome per story.** If multiple outcomes, split into sub-stories (e.g. H-1, H-2).
- **Mandatory sections:** Preconditions/Dependencies, Scope guardrails (Non-goals), Acceptance criteria, Minimal tests, AC-to-test mapping.
- **What/Why only.** No file names, function names, or AWS/API details; express constraints as behavior (e.g. "race-safe under concurrency").
- **Ground every story** in ROADMAP.md, DECISIONS.md, and README.md. If they conflict, align to repo reality first; propose a decision-change story only when necessary.

## Steps (workflow)

1. **Read** ROADMAP.md, DECISIONS.md, and README.md for the item you are storyifying.
2. **Decide** whether the item is one story or must be split (one outcome, ≤10 What bullets, ≤6 ACs, ≤6 tests).
3. **Draft** the story using the required format below (Why, What, Preconditions, Non-goals, AC, tests, AC-to-test mapping).
4. **Apply** concurrency/LLM/observability rules if the story touches tokens, cooldowns, quotas, or LLM.
5. **Run** the Quality checklist and "Before you output" checklist; fix until both pass.
6. **Output** the story and state the next story ID(s) you would produce after this one.

## Core Philosophy

A good story is a contract:
- Why: the value and the risk it reduces.
- What: the required behaviors and invariants.
- How: left to the coding agent.

The story writer must produce requirements and guardrails, not code instructions.

## Inputs You Must Use

When writing any story, always ground it in:
1. `ROADMAP.md` (what's next)
2. `DECISIONS.md` (constraints)
3. `README.md` (current reality)

If something conflicts with these, either:
- adjust the story to match repo reality (preferred), or
- propose a decision change (rare; should be its own story).

## Story Sizing Rules (Prevent Mega-Stories)

Stories must be small enough that an implementation agent can execute reliably.

### Hard Caps

A single story should:
- deliver one primary outcome
- have <= 10 "What" bullets (behavioral requirements); if more, split the story
- have <= 6 acceptance criteria
- have <= 6 tests (include concurrency/abuse tests only when relevant)

### Split Rule

If a story contains multiple outcomes, split it into sub-stories:
- `H-1`, `H-2`, ... (preferred)

### Atomic Definition

Atomic means:
- implementable, reviewable, and testable in isolation
- no unrelated refactors or cleanup
- minimal blast radius

## Required Story Format

Every story must use: **Title** → **Why** → **What** → **Preconditions** → **Scope guardrails (Non-goals)** → **Acceptance criteria** → **Minimal tests** → **Definition of Done**. Use behavioral language only (no file/function/API names). For full detail and What/Why vs How rules, see [story-format-reference.md](references/story-format-reference.md).

## When to use reference docs

- **Security, concurrency, observability** (verification, cooldowns, tokens, quotas, gating): see [smartmail-invariants.md](references/smartmail-invariants.md).
- **Stories that use an LLM** (routing, onboarding, extraction, coaching): see [llm-story-requirements.md](references/llm-story-requirements.md).

## Before you output a story

- [ ] Grounded in ROADMAP + DECISIONS + README?
- [ ] One primary outcome (or explicitly split as H-1, H-2)?
- [ ] Preconditions, Non-goals, AC, Minimal tests, and AC-to-test mapping present?
- [ ] Concurrency/idempotency rules applied if story touches tokens, cooldowns, quotas, or ingestion?
- [ ] LLM and observability rules applied if story involves LLM or gating?
- [ ] Quality checklist below satisfied?

## Quality Checklist (Must Pass)

A story is acceptable only if:
- one primary outcome
- explicit meaningful non-goals
- implementable without follow-ups
- ACs map cleanly to tests
- consistent with README and DECISIONS
- no hidden refactors

## Copy/Paste Story Template

Story  — 

Why:

What:

Preconditions/Dependencies:

Scope guardrails (do NOT do):

Acceptance criteria:

Minimal tests:

AC-to-test mapping:

Definition of Done:
- ACs met
- tests pass
- ROADMAP updated
- DECISIONS updated only if needed

## Examples

**Example 1: Split a large roadmap item**

- **User says:** "Turn the 'Verified quota gate' item in ROADMAP into stories."
- **Actions:** Read ROADMAP.md and DECISIONS.md; identify the item; split into e.g. H-1 (quota check + block) and H-2 (observability + tests). For each, output full format with Preconditions, Non-goals, AC, tests, mapping.
- **Result:** Two story packets, each with one outcome, ≤6 ACs, ≤6 tests, and clear next story IDs.

**Example 2: Single story from a small item**

- **User says:** "Write a story for: send verification email with cooldown."
- **Actions:** Read DECISIONS/README for cooldown and verification rules; write one story with Why, What (ordered: check cooldown then send), Preconditions (e.g. session table exists), Non-goals, AC, tests; include concurrency rule (no double-send).
- **Result:** One story packet; "Next: [next logical story ID]."

## Troubleshooting

| Symptom | Cause | Solution |
|--------|--------|----------|
| Story too large; >6 ACs or >6 tests | One story contains multiple outcomes | Split into sub-stories (H-1, H-2, …). |
| Agent or human implements code in the story | What section drifted into "how" (files, APIs) | Rewrite as behavioral requirements only; remove file/function/API names. |
| Missing non-goals | Scope guardrails skipped | Add mandatory "Scope guardrails (do NOT do)" with explicit out-of-scope items. |
| ROADMAP and DECISIONS conflict | Divergent docs | Prefer aligning story to current repo (README/DECISIONS). If impossible, note that a separate decision-change story may be needed. |

## Additional resources

- Full format and What/Why rules: [references/story-format-reference.md](references/story-format-reference.md)
- SmartMail invariants (security, concurrency, observability): [references/smartmail-invariants.md](references/smartmail-invariants.md)
- LLM story checklist: [references/llm-story-requirements.md](references/llm-story-requirements.md)
