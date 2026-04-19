# skills/ — Skill Unit Model

## Skill Structure (D14)

Each skill package has: `prompt.py`, `schema.py`, `validator.py`, `runner.py`, `errors.py` (or `eval.py`).
Narrow responsibility. Isolated tests. Strict schema validation before output propagates.

## Packages

| Package | Role | Status |
|---|---|---|
| `planner/` | Conversation intelligence, profile extraction, session check-in | refactoring target |
| `response_generation/` | Final email body generation, reply-mode prompting | refactoring target |
| `coaching_reasoning/` | Coaching strategy (stage 1): decides WHAT to say using doctrine | new |
| `coaching_reasoning/doctrine/` | Sport-specific coaching methodology files + manifest loader | new |
| `memory/unified/` | Unified memory notes + continuity refresh | refactoring target |
| `obedience_eval/` | LLM-based last-line compliance checker + correction | new |

## Layer Ownership

Each skill owns a specific domain. Do not bleed knowledge across layers.

| Layer | Owns | Must NOT contain |
|---|---|---|
| `coaching_reasoning/` + `doctrine/` | Coaching knowledge: what to say, what numbers are plausible, what's safe, training methodology | Prose style rules, formatting, compliance checks |
| `response_generation/` | Prose: turning a directive into a polished email | Coaching decisions, plausibility judgments, domain-specific ranges |
| `obedience_eval/` | Directive compliance: did the writer follow the directive's content_plan, avoid list, and constraints | Coaching knowledge, domain-specific validation, anything not derivable from the directive |

When a coaching quality problem surfaces, diagnose which layer is producing bad output and fix it there. Do not add downstream checks that duplicate upstream responsibility.

## Design Rules

- **Prompt ownership:** prompts belong here, never in `email_copy.py`.
- **LLM authority boundary:** LLM output shapes communication only — it never sets state, overrides rule-engine decisions, or modifies persisted data without a deterministic validation step.
- **Fail closed:** invalid LLM output must not reach the send path. Log and suppress.
- **No raw DynamoDB documents in LLM input:** assemble a bounded, validated artifact first.
