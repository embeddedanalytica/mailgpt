# Last-Mile Obedience Implementation Plan - DONE

## Goal

Reduce failures where the coach broadly understands the situation but does not faithfully execute the athlete's latest instructions, exact ask, current-week constraints, or previously locked plan decisions.

This plan is intentionally phased. We do not want to rewrite prompt logic, memory shaping, and generation rules in one pass and lose track of where regressions come from.

## Problem Statement

Observed failure pattern:

- the athlete says "keep it short" or "just tell me this week," and the reply expands scope
- the athlete says "do not revisit X," and the reply reopens X
- the athlete updates a constraint or priority, and the reply partially answers from stale context
- the reply sounds generally reasonable, but is not fully aligned to the latest facts
- the reply introduces assumptions the athlete did not provide

This is not primarily a coaching-knowledge problem. It is a last-mile instruction-following and context-application problem.

## Delivery Principles

- Change one behavioral layer at a time
- Make failures measurable before changing prompts
- Prefer explicit contracts over prompt folklore
- Keep strategist and writer responsibilities clearly separated
- Add regression coverage before broadening scope

## Confirmed Design Decisions

- Conversation intelligence stays routing-only in the initial rollout.
  - It continues to emit intent, requested action, brevity preference, and complexity.
  - It does not gain explicit instruction fields in the first pass.
- Structured instruction extraction for items like forbidden topics, exact reply scope, and latest overrides will be derived in strategist input shaping first.
- The existing strategist `avoid` field is the first mechanism for "do not mention / do not reopen / do not expand" rules.
  - We will extend its semantics before introducing new directive schema fields.
- Settled topics remain per-turn inferred in the first pass.
  - No persistent settled-topics store is introduced initially.
- Continuity context is treated as a possible stale-source, not as unquestioned wording authority.
  - Athlete corrections in the current turn can override continuity-derived framing.
- Contradicted durable memory facts should not be silently dropped by default.
  - They should be included for the strategist as contradicted or superseded context, lower priority than the latest turn.
  - The writer should not receive raw contradiction sets directly.
- Phase 1 uses two fixture types:
  - classification fixtures
  - regression fixtures
  - LLM-judged evals are deferred until later phases.
- For prompt changes, context-shaping changes should land before prompt-pack behavior changes.

## Phase 1: Define The Failure Contract

### Objective

Turn subjective "this felt off" feedback into a stable taxonomy and reproducible benchmark cases.

### Work

- Define a canonical failure taxonomy:
  - `reopened_resolved_topic`
  - `ignored_latest_constraint`
  - `answered_from_stale_context`
  - `exceeded_requested_scope`
  - `introduced_unsupported_assumption`
  - `missed_exact_instruction`
- Review recent live E2E artifacts and classify failures using that taxonomy.
  - Use [sam-app/.cache/live-athlete-sim/20260327T041920Z](/Users/levonsh/Projects/smartmail/sam-app/.cache/live-athlete-sim/20260327T041920Z) for focused diagnosis of the current athlete-sim failure set.
  - Use [sam-app/e2e/artifacts](/Users/levonsh/Projects/smartmail/sam-app/e2e/artifacts) for broader recurrence sampling across historical live runs.
- Create a short design note with 2-3 concrete examples per failure type.
- Add two fixture types drawn from real conversations:
  - classification fixtures: turn excerpt plus human-labeled failure type
  - regression fixtures: turn excerpt plus expected reply properties
- Initial regression fixture properties should cover:
  - "keep it short"
  - "do not revisit X"
  - "just tell me this week"
  - "these anchors are locked"
  - "latest constraint overrides prior pattern"

### Likely Files

- [sam-app/e2e/test_live_coaching_workflow.py](/Users/levonsh/Projects/smartmail/sam-app/e2e/test_live_coaching_workflow.py)
- [test_bench/response_generation_quality_bench.md](/Users/levonsh/Projects/smartmail/test_bench/response_generation_quality_bench.md)
- new or updated project-level analysis markdown

### Exit Criteria

- Each failure can be named consistently.
- We have a small classification set for analysis.
- We have a small regression set with property-based expectations.

## Phase 2: Clarify Layer Ownership

### Objective

Make it explicit which layer is responsible for obedience vs phrasing vs routing.

### Desired Ownership

- Conversation intelligence:
  - classify intent
  - classify requested action
  - classify brevity preference
  - do not own rich instruction extraction in the first pass
- Strategist / coaching reasoning:
  - decide exact response scope
  - decide which topics are resolved and must stay closed
  - decide which latest instructions override prior context
  - decide whether extra options are allowed
- Writer / response generation:
  - phrase the directive cleanly
  - do not add strategy
  - do not expand scope

### Work

- Review current contracts and note where responsibilities are currently blurred.
- Document authoritative priority order:
  - latest athlete instruction
  - locked constraints / corrected facts
  - current-turn ask
  - durable context
  - general coaching doctrine
- Decide which athlete-local facts should be treated as hard constraints:
  - explicit "don't revisit" instructions
  - locked anchors
  - latest-week availability and risk constraints
  - direct corrections from the athlete

### Likely Files

- [sam-app/email_service/business.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/business.py)
- [sam-app/email_service/coaching.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/coaching.py)
- [sam-app/email_service/response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_assembly.py)

### Exit Criteria

- We can explain in one page which layer should prevent each failure type.
- It is explicit that conversation intelligence remains routing-only in the initial rollout.

## Phase 3: Improve Strategist Input Shaping

### Objective

Ensure coaching reasoning sees the most important athlete-local instructions as first-class inputs instead of weak background context.

### Work

- Audit `build_response_brief(...)` and current memory shaping.
- Separate context into distinct categories:
  - latest explicit ask
  - forbidden / resolved topics
  - latest overrides and corrections
  - locked durable constraints
  - contradicted durable facts
  - supporting history
- Treat continuity context as another candidate stale-source.
  - If the athlete corrects timeline, phase framing, or block framing in-turn, that override should outrank continuity-derived wording.
- Decide whether to introduce explicit strategist fields for:
  - `requested_scope`
  - `forbidden_topics`
  - `latest_overrides`
  - `settled_topics`
- Reduce low-value context that competes with current-turn instructions.
- For contradicted durable facts, prefer include-with-marking over silent omission:
  - prior fact remains visible to the strategist
  - contradiction is explicit
  - the latest turn remains authoritative

### Likely Files

- [sam-app/email_service/response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_assembly.py)
- [sam-app/email_service/response_generation_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_contract.py)
- [sam-app/email_service/test_response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_assembly.py)
- [sam-app/email_service/test_response_generation_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_contract.py)

### Exit Criteria

- A strategist brief for known failure cases clearly surfaces:
  - the exact ask
  - latest constraints and overrides
  - topics that must stay closed
  - contradicted prior facts marked as superseded rather than silently removed

## Phase 4: Tighten Strategist Output

### Objective

Make coaching directives more operational so the writer does not have to infer boundaries.

### Work

- First extend the semantics of the existing `avoid` field so it can reliably carry:
  - forbidden mentions
  - forbidden reopenings
  - forbidden scope expansion
- Strengthen expectations for directive outputs to explicitly encode:
  - what to answer
  - what not to mention
  - whether follow-up questions are allowed
  - whether extra options are forbidden
  - which latest constraint overrides prior assumptions
- Prefer narrow directives over broad intent descriptions.
- Only consider adding new directive schema fields after `avoid`-based tightening proves insufficient.
- Add tests that assert directives capture the right boundaries for known failure cases.

### Likely Files

- [sam-app/email_service/skills/coaching_reasoning/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/prompt.py)
- [sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json)
- [sam-app/email_service/test_coaching_reasoning_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching_reasoning_skill.py)
- [sam-app/email_service/test_coaching_reasoning_eval.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching_reasoning_eval.py)

### Exit Criteria

- For targeted fixtures, the strategist output itself clearly blocks reopening, scope expansion, and stale-context drift.
- The first pass does this using existing directive structure unless there is clear evidence that schema expansion is necessary.

## Phase 5: Constrain The Writer

### Objective

Prevent response generation from adding "reasonable extras" that violate athlete-local instructions.

### Work

- Tighten writer prompt rules around:
  - no reopening resolved topics
  - no extra options unless directive explicitly allows them
  - no restating unchanged logistics unless necessary for this turn
  - no assumption-making beyond the directive and bounded context
  - short means short
- Review whether continuity context should be omitted by default in narrow replies.
- Treat the prompt pack as the primary writer-behavior surface.
  - Change context shaping first.
  - Change prompt-pack behavior second.
  - Avoid simultaneous broad edits to both context shaping and prompt-pack instructions in the same step.
- Add response-generation fixtures where the writer is tempted to elaborate but must stay constrained.

### Likely Files

- [sam-app/email_service/skills/response_generation/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/response_generation/prompt.py)
- [sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json)
- [sam-app/email_service/test_response_generation_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_skill.py)

### Exit Criteria

- Known "extra but plausible" writer failures are suppressed in tests.

## Phase 6: Add A Final Obedience Check

### Objective

Catch violations after drafting without immediately introducing heavy regeneration logic.

### Work

- Add a lightweight post-draft check for:
  - exact ask answered
  - forbidden topics avoided
  - latest constraints respected
  - unsupported assumptions avoided
  - scope not exceeded
- Start in observe-only mode first:
  - log failures
  - attach structured issue tags
  - compare against existing live E2E judgments
- Defer block-or-regenerate behavior until false-positive rate is understood.

### Likely Files

- new validation helper in `sam-app/email_service`
- live E2E / bench reporting code

### Exit Criteria

- We can score obedience separately from general coaching quality.

## Phase 7: Expand Regression Coverage

### Objective

Raise confidence without masking regressions under broad prompt changes.

### Work

- Add unit coverage for:
  - strategist brief shaping
  - strategist directive boundaries
  - writer obedience boundaries
- Add E2E assertions for:
  - no reopening of settled topics
  - compliance with direct brevity asks
  - preservation of locked anchors
  - latest-turn constraints overriding stale context
- Re-run against archived live-sim artifacts and compare before/after.

### Exit Criteria

- The targeted benchmark improves materially.
- Core safety and coaching-quality behavior does not regress.

## Recommended Rollout Order

Do not implement all layers at once.

1. Phase 1: taxonomy and failure fixtures
2. Phase 2: ownership and priority contract
3. Phase 3: strategist input shaping
4. Phase 4: strategist output tightening
5. Phase 5: writer constraints
6. Phase 6: final obedience checker
7. Phase 7: broader regression expansion

## Why This Order

- First make the failures legible.
- Then improve the reasoning inputs.
- Then reduce writer freedom.
- Only after that add a final checker.

If we start by changing all prompts at once, we will not know which layer actually fixed or caused a regression.

## First Implementation Slice

Recommended first coding slice:

- Phase 1 benchmark fixtures
- Phase 2 ownership note
- Phase 3 changes to strategist input shaping only

That gives us measurable movement without simultaneously changing strategist behavior, writer behavior, and post-draft validation.
