# SmartMail Invariants — Security, Concurrency, Observability

Use this reference when a story touches verification, cooldowns, rate limits, tokens, or gating. These rules are always-on unless the story explicitly says otherwise.

---

## Always-On Security and Privacy Defaults

### 1. Unverified inbound

- Never triggers LLM calls
- Never returns personal data
- May send verification link subject to cooldown

### 2. Verified inbound

- May proceed but remains cost-controlled (rate limits)
- Must avoid logging sensitive content

### 3. Email as UI

- Identity is untrusted until inbox-possession verified
- Sensitive actions require verification or safe action links

---

## Concurrency and Idempotency Trigger Rules

If a story touches any of the following, it **must** include explicit concurrency/idempotency requirements:

- Action links or one-time tokens
- Cooldown windows or send suppression
- Counters, quotas, or rate limits
- Ingestion / de-duplication flows

For these stories, explicitly state:

- Which state transitions must be single-use or conditional
- What must happen under concurrent requests
- Which actions are safe to retry without harmful side effects

---

## Observability Requirements

If the story affects gating, abuse prevention, or LLM usage, include:

- Required outcome markers (e.g. `allowed`, `blocked`, `notice_sent`)
- Requirement to log outcomes without logging sensitive content

Do not prescribe exact log formats. Keep marker vocabulary small and stable; add new markers only when needed.
