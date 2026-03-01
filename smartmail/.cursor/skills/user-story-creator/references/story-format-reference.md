# Story Format Reference — Full Detail

Every story must use this structure. This document expands each section for when you need full guidance.

---

## 1) Title

`Story <ID> — <Short descriptive title>`

---

## 2) Why

1–4 sentences explaining value: UX, cost, privacy, reliability, or leverage for future work.

---

## 3) What

Behavioral requirements only:

- What the system must do
- When it must do it (ordering constraints)
- Invariants (e.g. "before any LLM call", "verified only")
- Any state transitions

**Avoid:** File names, functions, classes, explicit AWS API calls.

---

## 4) Preconditions / Dependencies

State what must already be true before implementation starts:

- Relevant prior stories or prerequisites
- Current constraints that must be preserved
- Assumptions from README/DECISIONS that this story depends on

---

## 5) Scope guardrails (Non-goals)

Mandatory. Explicitly list what must **not** be implemented.

---

## 6) Acceptance criteria

Observable, measurable statements. Prefer ≤6.

---

## 7) Minimal tests

Smallest set that proves the acceptance criteria. Prefer ≤6.

---

## 8) Definition of Done

- ACs met
- Tests pass
- ROADMAP.md updated (checkboxes)
- DECISIONS.md updated only if a new decision is introduced

---

## What/Why vs How Rules

**Do (behavioral):**

- "Enforce limits before any LLM call."
- "Ask one next best question per email."
- "Fail closed to protect cost."

**Don't (implementation):**

- "Create function X in file Y."
- "Use TransactWriteItems."
- "Write UpdateExpression like ..."

If a low-level constraint is essential, express it as behavior:

- "Must be race-safe under concurrent requests."
- "Must not double-send notices under concurrency."

When ordering matters, express What as numbered steps.

---

## Acceptance Criteria to Test Traceability

Each acceptance criterion must map clearly to at least one minimal test.

- Label criteria: `AC1`, `AC2`, ...
- Label tests: `T1`, `T2`, ...
- Include a short mapping (e.g. `AC1 -> T1`, `AC2 -> T2+T3`).
