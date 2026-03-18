# SmartMail — Claude Working Guide

## What This Is

SmartMail is an **email-first AI coaching service** built on AWS SAM. Inbound email is the primary UI. A coach-like AI pipeline handles inbound athlete emails, applies deterministic rule-engine logic, and generates personalized coaching replies via LLM skill workflows.

---

## Layer 1 — Orientation (Read First)

### Key Document Map

| Document | Role |
|---|---|
| `sam-app/README.md` | Current implementation and runtime state |
| `spec.md` | Source of truth for rule behavior |
| `sam-app/DECISIONS.md` | Durable architectural decisions (ADR-lite) |
| `response-generation-epic.md` | Design record for the response-generation layer |
| `athlete-memory-epic.md` | Design record for athlete memory / continuity |
| `rule-engine-epic.md` | Completed implementation record for RE1–RE4 |
| `bug-backlog.md` | Open bugs (mostly long-horizon memory issues) |

### Three Lambda Functions

```
EmailServiceFunction       sam-app/email_service/       Python — inbound email pipeline
mailgptregistration        sam-app/email_registration/  Node.js — POST /register
ActionLinkHandlerFunction  sam-app/action_link_handler/ Python — GET /action/{token}, Strava OAuth
```

### Inbound Email Pipeline (high-level)

```
SES → SNS → EmailServiceFunction
  app.py          parse + auth + rate-limit gate
  business.py     orchestration entrypoint
  coaching.py     profile gate + reply generation   ← under refactoring
  skills/*        bounded LLM workflows              ← under refactoring
```

`business.py` is the current orchestration entrypoint. Its public surface can evolve but it should remain the coordination hub for inbound handling.

---

## Layer 2 — Module Map

### `sam-app/email_service/` — Key Files

| Module | Responsibility | Stability |
|---|---|---|
| `app.py` | Lambda handler: parse → auth → quota → dispatch | **stable** |
| `auth.py` | Registration / inbox-possession verification gating | **stable** |
| `rate_limits.py` | Verified-user hourly/daily quota enforcement | **stable** |
| `rule_engine.py` | Deterministic rule engine (RE1–RE4) | **stable** |
| `rule_engine_orchestrator.py` | Orchestrates rule-engine calls and plan-update persistence | **stable** |
| `rule_engine_state.py` | Rule state persistence helpers | **stable** |
| `dynamodb_models.py` | DynamoDB persistence helpers | **stable** (table schema is fixed) |
| `business.py` | Orchestration: conversation intelligence, model routing, rule engine, coaching | refactoring target |
| `coaching.py` | Profile gate, profile/snapshot extraction, LLM reply generation | **refactoring target** |
| `response_generation_assembly.py` | Assembles `ResponseBrief` from coaching artifacts | **refactoring target** |
| `response_generation_contract.py` | Contracts: `ResponseBrief`, `FinalEmailResponse`, reply modes | **refactoring target** |
| `athlete_memory_contract.py` | Memory note and continuity summary contracts | **refactoring target** |
| `athlete_memory_reducer.py` | Memory note trimming/reduction logic | **refactoring target** |
| `coaching_memory.py` | Pre/post reply memory refresh orchestration | **refactoring target** |
| `profile.py` | Profile update parsing and required-field checks | **refactoring target** |
| `inbound_rule_router.py` | Routes mutate vs read-only requests to the rule engine | refactoring target |
| `conversation_intelligence.py` | Conversation intelligence storage/routing helpers | refactoring target |
| `ai_extraction_contract.py` | AI extraction output contracts and validation | refactoring target |
| `email_copy.py` | Transactional outbound copy only — not prompts | stable |
| `openai_responder.py` | **Dead shim** — no active logic, safe to delete | delete candidate |

### `sam-app/email_service/skills/` — Skill Packages

Each skill has: `prompt.py`, `schema.py`, `validator.py`, `runner.py`, and `eval.py` (or `errors.py`).

| Package | Skill | Stability |
|---|---|---|
| `skills/planner/` | Conversation intelligence, profile extraction, session check-in | refactoring target |
| `skills/response_generation/` | Final email body generation, reply-mode prompting, clarification copy | **refactoring target** |
| `skills/memory/eligibility/` | Memory refresh eligibility classification | **refactoring target** |
| `skills/memory/refresh/` | Memory notes + continuity refresh | **refactoring target** |
| `skills/memory/router/` | Memory routing decision | **refactoring target** |
| `skills/memory/long_term/` | Long-term (durable) memory note extraction | **refactoring target** |
| `skills/memory/short_term/` | Short-term continuity extraction | **refactoring target** |

---

## Layer 3 — True Invariants (Do Not Break)

These are the things that must survive any refactoring. Everything else is fair game.

### Security Gates

These must always execute in order before any LLM call. Never bypass, reorder, or weaken them.

1. Unregistered senders → registration-required reply, no LLM (D5)
2. Registered but unverified senders → verification email with cooldown, no LLM (D6)
3. Verified senders → hourly + daily quota claim before any LLM call (D10)

Owned by `auth.py` and `rate_limits.py`. Do not inline or restructure this gate sequence in `app.py`.

### Rule Engine Authority

`rule_engine.py` is the sole authority on:
- training state, safety classification, plan validation
- anti-oscillation, track selection, deload logic, archetype selection
- weekly skeleton generation (RE1–RE4)

No LLM output — including from any refactored response or memory layer — may override rule-engine decisions.

### DynamoDB Table Schema

The table structure (keys, indexes, TTLs) is provisioned by `template.yaml` and cannot be changed by code refactoring alone. The `users` table is manual. Any new access patterns must work within the existing schema unless a schema migration is explicitly planned.

### Prompt Ownership

LLM prompt text must not live in `email_copy.py`. `email_copy.py` is transactional outbound copy only (verification emails, rate-limit notices, registration replies). Prompts belong in skill packages.

---

## Layer 4 — Areas Under Active Refactoring

The following areas are **failing user acceptance tests** and are the primary refactoring targets. The current implementations are the starting point for understanding what exists — not a constraint on what the refactored design must look like.

### Memory Management

Current files: `athlete_memory_contract.py`, `athlete_memory_reducer.py`, `coaching_memory.py`, `skills/memory/*`

Current bugs (see `bug-backlog.md`): long-horizon memory loses core training backbone, stale scheduling rules are not retired when replaced, primary goals can disappear from durable memory. The current 7-note bounded model and refresh trigger logic are **not working well enough** and should be reconsidered.

### Response Generation

Current files: `response_generation_contract.py`, `response_generation_assembly.py`, `skills/response_generation/*`, `coaching.py._generate_llm_reply()`

Known gap: RG1.8 (fallback behavior) is unimplemented — failures fail-closed with logging. The `ResponseBrief → FinalEmailResponse` contract and the reply-mode system are implementation choices, not invariants.

### Profile Completeness Gate

Current files: `coaching.py.build_profile_gated_reply()`, `profile.py`, `ai_extraction_contract.py`

The current profile gate controls the reply path based on whether required fields are present. The fields, logic, and gating behavior are all refactorable. Required profile fields and "ready for coaching" determination (D11) are defined in `sam-app/DECISIONS.md` — but the implementation of how the gate works can change.

### Conversation Intelligence and Routing

Current files: `business.py`, `conversation_intelligence.py`, `inbound_rule_router.py`, `skills/planner/conversation_intelligence_*`

The current classification → model routing → rule engine orchestration sequence is a refactoring target. The intent is for the system to correctly classify and route inbound messages, but the current shape of that pipeline can change.

---

## Layer 5 — Design Principles for Refactored Code

When building the replacement for any of the above areas, follow these:

- **Skill unit model (D14):** narrow responsibility, dedicated prompt, strict schema, validator, isolated tests/eval hooks.
- **LLM authority boundary:** LLM output shapes communication; it never sets state, overrides rule-engine decisions, or modifies persisted athlete data without a deterministic validation step.
- **Fail closed:** invalid LLM output must not propagate to the send path. Log and suppress rather than send corrupted content.
- **No raw mutable state in LLM input:** assemble a bounded, validated input artifact before any LLM call. The LLM should never receive a raw DynamoDB document.
- **YAGNI (D9):** build the minimum that satisfies the acceptance criteria. Do not design for hypothetical futures.

---

## Layer 6 — Testing

### Run All Tests

```bash
# Email service unit tests
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service

# Action link handler unit tests
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"

# Live endpoint e2e tests (requires live AWS)
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

### Test Philosophy

- Do not mock DynamoDB in unit tests — mocked persistence has caused silent prod divergence before
- Each skill package should have isolated tests and eval hooks
- Bench fixtures (`*_bench_fixture.py`) drive offline LLM eval; bench runners invoke them against live models
- When refactoring a module, update or replace its tests — do not keep tests that validate the old (broken) behavior

---

## Layer 7 — DynamoDB Quick Reference

| Table | PK | SK | Notes |
|---|---|---|---|
| `coach_profiles` | `athlete_id` | — | Profile, `current_plan`, `memory_notes`, `continuity_summary` |
| `athlete_identities` | `email` | — | Maps email → athlete_id |
| `action_tokens` | `token_id` | — | Single-use expiring tokens (TTL: `expires_at`) |
| `verified_sessions` | `email` | — | TTL: `session_expires_at` |
| `rate_limits` | `email` | — | Quota + verification cooldown |
| `rule_state` | `athlete_id` | — | Persisted rule-engine state |
| `plan_history` | `athlete_id` | `plan_version` | Immutable plan history |
| `activities` | `athlete_id` | `provider_activity_key` | Connector-synced activities |
| `manual_activity_snapshots` | `athlete_id` | `snapshot_key` | Manual activity from email |
| `progress_snapshots` | `athlete_id` | — | Current progress snapshot |
| `users` | `email_address` | — | **Manual table** — not in template.yaml |

---

## Layer 8 — Build and Deploy

```bash
# Build
cd sam-app && sam build

# First deploy
sam deploy --guided

# Subsequent deploys
sam deploy

# Local API
sam local start-api

# Local Lambda invoke
sam local invoke EmailServiceFunction --event events/sns-email-event.json
```

Credentials (OpenAI key, Strava secret, KMS config) must never be committed — inject via env or secrets manager.
