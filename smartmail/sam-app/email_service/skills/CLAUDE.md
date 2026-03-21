# skills/ — Skill Unit Model

## Skill Structure (D14)

Each skill package has: `prompt.py`, `schema.py`, `validator.py`, `runner.py`, `errors.py` (or `eval.py`).
Narrow responsibility. Isolated tests. Strict schema validation before output propagates.

## Packages

| Package | Role | Status |
|---|---|---|
| `planner/` | Conversation intelligence, profile extraction, session check-in | refactoring target |
| `response_generation/` | Final email body generation, reply-mode prompting | refactoring target |
| `memory/unified/` | Unified memory notes + continuity refresh | refactoring target |

## Design Rules

- **Prompt ownership:** prompts belong here, never in `email_copy.py`.
- **LLM authority boundary:** LLM output shapes communication only — it never sets state, overrides rule-engine decisions, or modifies persisted data without a deterministic validation step.
- **Fail closed:** invalid LLM output must not reach the send path. Log and suppress.
- **No raw DynamoDB documents in LLM input:** assemble a bounded, validated artifact first.
