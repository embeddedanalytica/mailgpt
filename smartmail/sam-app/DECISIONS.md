# SmartMail Coach Decisions (ADR-lite)

This file records key design decisions so implementation stays consistent.
Update this only when we make a new decision (avoid noise).
This is an architectural-decision record, not an implementation-status tracker.
Current runtime status belongs in [README.md](/Users/levonsh/Projects/smartmail/sam-app/README.md).

---

## D1 — Email as UI
**Decision:** Product is email-first with minimal web surface for registration, action links, and provider OAuth callbacks.
**Why:** Lowest friction; aligns with SmartMail architecture.
**Implications:** Must enforce strict gates to prevent spoofing, spam, and LLM cost abuse.

---

## D2 — Inbox-Possession Verification via Magic Link Sessions
**Decision:** Personal coaching responses (and any sensitive info) require inbox-possession verification.
**Mechanism:**
- Inbound email from unverified sender -> send verification email with magic link.
- Clicking link hits `/action/{token}` with `VERIFY_SESSION`, which creates/updates `verified_sessions[email]`.
**Session TTL:** Configurable via `SESSION_TTL_DAYS` (default 14 days).
**Why:** Email headers alone aren’t reliable identity proof; inbox-possession is.

---

## D3 — Action Links Use Single-Use, Expiring Tokens
**Decision:** All action links are represented by DynamoDB `action_tokens` items:
- PK: `token_id` (high-entropy random string)
- TTL: `expires_at`
- Single-use: `used_at` set atomically via conditional update
**Why:** Prevent replay attacks; supports safe concurrency; re-usable for future actions (connectors, unsubscribe, etc.).

---

## D4 — One Action Endpoint
**Decision:** Use a single endpoint `GET /action/{token}` for all action links.
**Why:** Centralizes token validation/consumption logic and keeps email links stable.

---

## D5 — Unverified Inbound Emails Never Call LLM
**Decision:** Unverified inbound email requests must not trigger LLM calls.
**Why:** Prevent cost-bombing and data leakage (spoofers gain nothing; system cost stays near zero).

---

## D6 — Verification Email Cooldown (Anti-Spam)
**Decision:** Throttle verification emails per sender so spoof floods do not spam real users.
**Mechanism:** Store a per-email cooldown in `rate_limits` and enforce with atomic conditional updates.
**Config:** `VERIFY_EMAIL_COOLDOWN_MINUTES` (default 30 minutes).
**Behavior:** If cooldown is active, drop silently (no email, no token, no LLM).

---

## D7 — Safe Failure Handling (No Compensating Transactions)
**Decision:** If token consumption succeeds but session write fails, return a safe 500 HTML page.
**Do not:** attempt to “unconsume” token or implement retries/backoff in the action endpoint at this stage.
**Why:** Avoid complexity and scope creep; failures are rare and can be resolved by issuing a new link.

---

## D8 — Ignore Reply-To for Sensitive Routing
**Decision:** System routing should not depend on Reply-To for delivering sensitive responses.
**Why:** Prevent header tricks that attempt to redirect responses to an attacker.

---

## D9 — Scope Guardrails
**Decision:** Only implement what is explicitly in the current story acceptance criteria.
**Backlog items** (examples): message unification (404/410), retries/backoff, advanced auth scoring, extra action types.
**Why:** Maintain shipping velocity and reduce risk of unintended changes.

---

## D10 — Verified-User Cost Controls
**Decision:** Verified users are rate-limited before LLM calls via per-user hourly and daily quotas.
**Why:** Protect cost ceiling even for verified accounts or compromised inboxes.
**Status:** Implemented.

---

## D11 — Coaching Readiness Is Profile-State Driven
**Decision:** "Ready for coaching" is determined by profile completeness, not message order.
**Required fields:** `goal`, `weekly_time_budget_minutes`, `sports` (or explicit unknown/skip markers per field).
**Why:** Keeps behavior deterministic and robust across any email sequence.

---

## D12 — Recommendation Contract v1 Is Versioned and Strict
**Decision:** Recommendation generation and storage must use a shared versioned contract in code (`recommendation_contract.py`).
**Contract version:** `v1`
**Why:** Prevent field drift between connector ingestion, LLM generation, storage, and reply composition.
**Compatibility rule:** `v1` changes are additive-only. Existing required fields and meanings must remain stable.
**Validation rule:** Payloads are validated before use and before persistence; invalid payloads are rejected.

---

## D13 — Athlete Memory Stays Lightweight and Athlete-Scoped
**Decision:** Athlete memory is persisted only on `coach_profiles` as two bounded artifacts:
- `memory_notes` for durable or semi-durable athlete context
- `continuity_summary` for short-lived recent coaching continuity
**Storage rule:** Memory artifact timestamps use Unix seconds in storage. Human-readable dates are rendered only in LLM-facing prompts when needed.
**Retrieval rule:** Response-time retrieval is bounded to all active `high` notes plus up to 3 additional recent active notes.
**Refresh rule:** Memory refresh is LLM-assisted and may run both before reply generation and after a completed interaction, but only when the interaction meaningfully changes durable context, coaching recommendation, or coaching state.
**Guardrail rule:** At most 7 memory notes may remain active for one athlete.
**Why:** Preserve continuity without introducing a separate memory subsystem, semantic search, embeddings, or heavyweight history management.

---

## D14 — LLM Workflows Are Implemented as Skill Units
**Decision:** Implement LLM-powered workflows as separate skill units with dedicated prompts, strict schemas, validators, and eval hooks.
**Modeling rule:** A skill may use the same model as other skills or a different model; model selection is per-workflow and not the primary contract.
**Why:** Preserves isolation, testability, and contract stability while allowing flexible model routing by workflow.