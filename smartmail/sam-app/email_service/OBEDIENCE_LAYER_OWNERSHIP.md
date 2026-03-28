# Obedience Layer Ownership

Which layer is responsible for preventing each last-mile obedience failure.

## Layers

| Layer | Module | Role |
|-------|--------|------|
| **Conversation Intelligence (CI)** | `planner/conversation_intelligence_prompt.py` | Classify intent, requested action, brevity preference, complexity. Routing only. |
| **Input Shaping (IS)** | `response_generation_assembly.py` | Build the ResponseBrief. Decide what the strategist sees and how it is prioritized. |
| **Strategist (ST)** | `coaching_reasoning/prompt.py` + prompt pack | Decide WHAT to communicate: scope, boundaries, forbidden topics, tone. Emit the coaching directive. |
| **Writer (WR)** | `response_generation/prompt.py` + prompt pack | Turn the directive into a polished email. No strategy. No scope expansion. |

## Authoritative Priority Order

When signals conflict, the higher-numbered source wins:

1. General coaching doctrine (lowest)
2. Durable context (memory facts, continuity state)
3. Current-turn ask (what the athlete wants answered)
4. Locked constraints / corrected facts
5. Latest athlete instruction (highest)

This means: if memory says "athlete trains 4 days/week" but the latest message says "I can now do 5 days," the latest instruction wins. If doctrine says "always mention safety reminders" but the athlete says "stop bringing up the Achilles," the athlete instruction wins.

## Failure Type Ownership

### `reopened_resolved_topic`

| Layer | Responsibility |
|-------|---------------|
| IS | Not currently responsible. **Gap:** No mechanism to mark topics as resolved before they reach the strategist. |
| ST | **Primary owner.** Must detect resolved topics from conversation flow and add them to `avoid`. Prompt pack already says "If a topic has been answered or resolved, include it in the avoid list." |
| WR | **Secondary owner.** Must respect `avoid`. Prompt pack says "When the avoid list names a resolved topic, do not reference it." |

**Current gap:** The strategist prompt tells it to avoid resolved topics, but has no structured input that flags which topics are resolved. It must infer this from `inbound_body` alone. Phase 3 should surface resolved/settled topics as a structured input.

---

### `ignored_latest_constraint`

| Layer | Responsibility |
|-------|---------------|
| IS | Not currently responsible. Forwards `brevity_preference` only. **Gap:** Does not extract explicit instructions like "only reply if there's a concern" or "three lines max" as structured fields. |
| ST | **Primary owner.** Must read the latest constraint from `inbound_body` and encode it in the directive (via `avoid`, `content_plan`, or `reply_action`). The suppress rule in the prompt pack partially covers "no reply unless needed" but is complex and easy to misfire. |
| WR | **Secondary owner.** Must follow `avoid` and respect directive brevity. Cannot add items not in `content_plan`. |

**Current gap:** Explicit athlete instructions (format rules, reply suppression, specific phrasing) are buried in `inbound_body` with no priority signal. The strategist must parse them from raw text. Phase 3 should elevate these to first-class brief fields. The suppress rule is also over-qualified — it requires checking multiple conditions simultaneously, which the LLM sometimes fails to apply.

---

### `answered_from_stale_context`

| Layer | Responsibility |
|-------|---------------|
| IS | **Primary owner.** Assembles `memory_context` and `continuity_context`. If stale facts are included without contradiction marking, the strategist has no signal to deprioritize them. |
| ST | **Secondary owner.** Must prefer `inbound_body` facts over memory/continuity when they conflict. Prompt says to read the athlete's message, but doesn't explicitly say "latest turn overrides memory." |
| WR | Not responsible. Uses only the directive and plan data. |

**Current gap:** Memory facts (`priority_facts`, `structure_facts`) are presented as equally authoritative regardless of freshness. Continuity context (`weeks_in_current_block`, `current_block_focus`) is labeled as "authoritative source of truth" in the writer prompt, which means it can override even explicit athlete corrections. Phase 3 must: (a) mark contradicted memory facts, (b) stop treating continuity context as unquestionable when the athlete explicitly overrides it.

---

### `exceeded_requested_scope`

| Layer | Responsibility |
|-------|---------------|
| CI | Partially responsible. Emits `brevity_preference` ("brief"/"normal"), but this is coarse — it doesn't distinguish "short" from "narrow scope." |
| ST | **Primary owner.** Must constrain `content_plan` to what was asked. Prompt says "ask: What here is actually new? Keep only that." Good instruction, but no structural enforcement. |
| WR | **Secondary owner.** Must match email length to directive weight. Prompt says "A short directive should produce a short email" and "if you write a long email a kitten will die." These are soft instructions. |

**Current gap:** `brevity_preference` is the only structured scope signal. An athlete who says "just tell me this week" gets `brevity_preference: normal` (their message isn't terse). The scope narrowing instruction is in the raw body only. Phase 3 should add a `requested_scope` field. Phase 5 should add explicit writer rules for narrow replies.

---

### `introduced_unsupported_assumption`

| Layer | Responsibility |
|-------|---------------|
| IS | Partially responsible. Provides `continuity_context` with week numbers and block labels. If continuity state is wrong, the strategist will propagate the error. |
| ST | **Primary owner.** Must not assert facts not present in the brief. Prompt says to use continuity context week numbers exactly. But when continuity context is missing or stale, the strategist sometimes invents labels. |
| WR | **Secondary owner.** Writer prompt says "NEVER calculate, guess, or invent week numbers." Good rule, but the writer can still propagate assumptions from the directive. |

**Current gap:** When continuity context is absent, neither the strategist nor writer has a clear rule for what to do. They sometimes fill the gap with guesses. Phase 4 should add an explicit strategist rule: "If no continuity context is provided, do not reference week numbers or block labels."

---

### `missed_exact_instruction`

| Layer | Responsibility |
|-------|---------------|
| IS | Not responsible. |
| ST | **Primary owner.** Must follow exact instructions in `inbound_body`. The prompt says "read the athlete's message and determine what it accomplishes" but doesn't say "follow exact instructions literally." |
| WR | **Secondary owner.** Must follow the directive faithfully. If the directive misses the instruction, the writer can't fix it. |

**Current gap:** The strategist prompt is oriented around coaching decisions, not instruction compliance. It says "determine what it accomplishes" (analytical) but not "do exactly what it says" (obedient). An athlete who says "start from Week 2" gets interpreted rather than followed. Phase 4 should tighten the strategist prompt to treat explicit athlete instructions as hard constraints that override coaching judgment.

---

## Summary: Where Responsibilities Are Currently Blurred

| Blurred boundary | What happens | What should happen |
|------------------|-------------|-------------------|
| CI does not extract instructions | Explicit requests like "3 lines max" or "don't revisit X" are not structured | Phase 3: IS derives them; later: CI may emit them |
| IS does not mark contradictions | Stale memory facts look identical to current ones | Phase 3: IS marks contradicted facts |
| IS presents continuity as unquestionable | Writer prompt says continuity is "ONLY authoritative source" | Phase 3: IS + ST treat athlete corrections as override |
| ST has coaching orientation, not obedience orientation | Strategist optimizes for coaching quality, not instruction compliance | Phase 4: Add explicit "athlete instruction is a hard constraint" rule |
| WR can't fix strategist misses | If the directive misses an instruction, the writer propagates the miss | Phases 3-4: Fix at strategist level first |

## Conversation Intelligence: Confirmed Routing-Only

CI stays routing-only in the initial rollout. It emits:
- `intent` (coaching, question, off_topic, safety_concern)
- `requested_action` (plan_update, answer_question, checkin_ack, clarify_only)
- `brevity_preference` (brief, normal)
- `complexity_score` (1-5)

It does **not** extract explicit instructions, forbidden topics, or scope constraints. That work belongs to input shaping (Phase 3) and strategist reasoning (Phase 4).

## Hard Constraints (Athlete-Local Facts That Override Everything)

These are treated as hard constraints that override coaching doctrine and durable context:

1. **Explicit "don't revisit" instructions** — "stop bringing up X" means X is forbidden
2. **Locked anchors** — "Saturday long run is locked" means it cannot be moved
3. **Latest-week availability and risk constraints** — "I can only do 3 days" overrides memory
4. **Direct corrections** — "start from Week 2, not Week 3" is a factual override
5. **Format and reply instructions** — "3 lines max" or "only reply if concern" are hard rules
6. **Explicit phrasing requests** — "say 'Friday protected' not 'forced-easy'" must be followed literally
