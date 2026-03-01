# LLM-Driven Story Requirements

When a story introduces or uses an LLM, it **must** specify the following. Use this checklist when the story involves routing, onboarding, extraction, or coaching.

---

## A) Role of the LLM

Choose one (or state which combination):

- **routing** — what to do next
- **onboarding** — ask next best question
- **extraction** — structured profile updates
- **coaching** — response generation

---

## B) Output constraints

- Bounded output (allowed intents/fields)
- "Unknown" / "low confidence" behavior
- Safe fallback (e.g. ask one clarifying question)

---

## C) Model flexibility

- Model choice is configurable by task type
- Swapping models does not require logic refactors

---

## D) Cost posture

- When LLM is invoked
- When LLM **must** be skipped (e.g. unverified, blocked, rate-limited)
