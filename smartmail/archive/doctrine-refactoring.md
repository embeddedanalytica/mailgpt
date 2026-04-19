# Doctrine Refactoring Plan

## Goal

Refactor doctrine loading so the strategist receives only the doctrine that is useful for the current coaching task.

The target state is:

- lower prompt size
- higher doctrine salience
- less irrelevant doctrine on simple turns
- better task-specific expertise on complex turns

This is **not** a plan to rewrite coaching strategy into deterministic code.
This is a plan to make doctrine loading more purpose-based, more selective, and easier to evolve.

## Problem Statement

The current selector is materially better than "load everything," but it still has two weaknesses:

- some doctrine is loaded too broadly for simple turns
- the selector is driven more by signals and sport than by the actual purpose of the turn

Examples:

- a simple running question can still load running methodology
- a lightweight interaction can load doctrine meant for actual plan construction
- broad backstop doctrine can arrive on turns where it is not necessary

The system should instead first answer:

1. What is the purpose of this turn?
2. What risks or special situations are active?
3. What doctrine is essential for that purpose?
4. What doctrine is only justified if risk or ambiguity is present?

## Design Principle

Doctrine loading should be layered:

1. `always_on`
2. `purpose_based`
3. `situation_based`
4. `backstop`
5. `enricher`

Each layer has a stricter inclusion bar than the one before it.

Simple-turn protection is a first-class invariant:

- if purpose is `simple_acknowledgment` or `lightweight_answer`, resist loading extra doctrine unless a safety/risk condition is clearly active

The selector may emit a small number of compact control hints in addition to doctrine file choices.
These should stay short and should not become a new prose-doctrine layer.

## Doctrine Loading Model

### 1. Always-On

Load on every strategist turn.

Use this only for true invariants.

Should remain small and stable.

Recommended files:

- [universal/core.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/core.md)
- [universal/authority_and_override_rules.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/authority_and_override_rules.md)

### 2. Purpose-Based

Load because of the operational purpose of the turn.

Examples:

- planning
- mutation
- lightweight answer
- clarification
- intake
- milestone/reflection

Purpose should become the primary routing concept.

### 3. Situation-Based

Load because a specific coaching situation is active.

Examples:

- setback
- illness
- travel disruption
- intensity return
- prescription

These are not the same as purpose.
A turn can have purpose `planning` with situation `travel`.

### 4. Backstop

Load only when risk, ambiguity, or contradiction risk is high enough that a final anti-pattern guard is useful.

This should not be a default doctrine bucket.

### 5. Enricher

Load only when explicitly relevant.

Examples:

- reading/resource recommendations
- optional educational content

This should be the rarest doctrine tier.

## Primary Turn Purposes

The selector should derive exactly one primary `turn_purpose`.

Suggested enum:

- `simple_acknowledgment`
- `lightweight_answer`
- `planning`
- `plan_mutation`
- `setback_management`
- `return_to_load`
- `milestone_or_reflection`
- `clarification`
- `intake`

These are operational labels, not psychological interpretations.

## Purpose Definitions

### `simple_acknowledgment`

Use when:

- confirmatory check-in
- "sounds good"
- "starting Monday"
- routine status update
- no new decision required

Doctrine target:

- cheapest possible path

### `lightweight_answer`

Use when:

- athlete asks a direct question
- answer is narrow
- no meaningful training reprogramming is required

Examples:

- session swap
- confirm a small choice
- answer a bounded logistics/training question

Doctrine target:

- answer the question well without loading plan-building doctrine

### `planning`

Use when:

- athlete asks what next week should look like
- athlete asks for session structure
- athlete asks for training composition
- strategist needs to shape a training week

Doctrine target:

- methodology and prescription quality

### `plan_mutation`

Use when:

- athlete wants to change the existing plan
- coach needs to adjust load, order, or structure
- mutation is more than a simple answer

Doctrine target:

- disciplined modification, not full rebuild by default

### `setback_management`

Use when:

- pain
- flare
- illness
- fatigue spike
- travel disruption
- unstable block dominates the turn

Doctrine target:

- conservative, risk-sensitive coaching

### `return_to_load`

Use when:

- athlete is improving after disruption
- question is about progression
- intensity reintroduction or load resumption is being considered

Doctrine target:

- prevent premature escalation

### `milestone_or_reflection`

Use when:

- race completion
- PR
- breakthrough
- "what have you learned about me?"
- high-value reflection moment

Doctrine target:

- relationship and meaning, not plan mechanics

### `clarification`

Use when:

- missing information blocks a good answer

Doctrine target:

- ask only what is necessary

### `intake`

Use when:

- building profile or gathering foundational context

Doctrine target:

- gather information, not coach forward

## Purpose Derivation Rules

Purpose derivation should be deterministic and ordered.
One turn gets one primary purpose.

Recommended priority:

1. `clarification` if `reply_mode == clarification`
2. `intake` if `reply_mode == intake`
3. `milestone_or_reflection` if strong milestone/reflection signal
4. `setback_management` if setback/illness/travel dominates the turn
5. `return_to_load` if comeback + progression/intensity signal
6. `plan_mutation` if explicit change to current plan is requested
7. `planning` if building/mapping/programming training
8. `lightweight_answer` if direct question without planning/mutation
9. `simple_acknowledgment` otherwise

This order should be encoded explicitly, not inferred ad hoc.

## Purpose Derivation Inputs

`derive_turn_purpose(brief)` should be defined against explicit brief fields.
Do not leave this to freeform interpretation during implementation.

Recommended inputs:

- `reply_mode`
- `delivery_context.inbound_body`
- `decision_context.clarification_needed`
- `decision_context.risk_flag`
- `decision_context.risk_recent_history`
- `memory_context.continuity_summary.open_loops`
- `athlete_context.constraints_summary`
- `athlete_context.primary_sport`

Optional future input:

- `decision_context.turn_purpose_hint`

If `turn_purpose_hint` is introduced later, it should act as a bounded upstream hint, not an unrestricted override.

### Deterministic Classification Rules

The first implementation should remain deterministic.

That means:

- `clarification`, `intake`, `planning`, `plan_mutation`, `setback_management`, and `return_to_load` should be derived deterministically
- `milestone_or_reflection` should also start deterministic using bounded milestone/reflection phrases
- do not rely on LLM interpretation to classify purpose in Phase 1

If later evaluation shows a recurring ambiguous class, add a narrow upstream `turn_purpose_hint` rather than weakening deterministic routing everywhere.

### Practical Mapping Guidance

Use these as initial rules:

- `reply_mode == clarification` → `clarification`
- `reply_mode == intake` → `intake`
- milestone/reflection phrases in inbound body → `milestone_or_reflection`
- setback/illness/travel signals dominating the turn and no clear planning ask → `setback_management`
- setback + progression/intensity request → `return_to_load`
- explicit requests to change existing plan structure/load/order → `plan_mutation`
- explicit requests to map/build/prescribe upcoming training → `planning`
- direct question without planning/mutation → `lightweight_answer`
- otherwise → `simple_acknowledgment`

Phase 1 implementation should ship with representative examples for each mapping.

## Situation Tags

In addition to primary purpose, derive zero or more `situation_tags`.

Suggested tags:

- `setback`
- `illness`
- `travel`
- `intensity_return`
- `prescription`
- `milestone`
- `reflection`
- `high_risk`
- `clarification_needed`

Purpose chooses the main doctrine lens.
Situation tags choose the specialized doctrine attachments.

Tags should carry signal strength, not just presence.

Recommended strength enum:

- `none`
- `weak`
- `strong`

Examples:

- isolated mention of `tempo` in a broad sentence may be `weak`
- explicit comeback/progression ask such as "Can I bring tempo back?" should be `strong`

Selector rule:

- lightweight purposes should require `strong` evidence before loading most situation doctrine
- planning and mutation purposes may accept `weak` evidence when the doctrine is directly relevant to the programming task

## Compact Selector Outputs

In addition to `turn_purpose`, `situation_tags`, and selected doctrine files, the selector may emit a few compact control hints.

These are intended to improve strategist quality without loading more doctrine prose.

Recommended fields:

- `posture`
- `trajectory`
- `purpose_micro_avoid`
- `response_shape`

These should be:

- short
- enumerable where possible
- easy to test
- cheap to inject

They should not become a second hidden strategist prompt.

### `posture`

`posture` is the default coaching stance for the turn.

Examples:

- `conservative_hold`
- `cautious_progress`
- `answer_and_release`
- `celebrate_then_pause`
- `clarify_only`
- `logistics_delivery`

Purpose:

- help the strategist land on the correct default stance before reading all doctrine
- reduce subtle failures where the model sounds cautious but prescribes aggressively
- reinforce the intended stance on counterintuitive turns, especially `return_to_load` and `setback_management`

### `trajectory`

`trajectory` is a compact interpretation of recent risk direction.

Recommended enum:

- `stable`
- `recovering`
- `declining`

Derived from:

- `decision_context.risk_recent_history`
- current `risk_flag`

Purpose:

- modulate doctrine interpretation without loading more doctrine
- distinguish:
  - stable green coaching
  - recovering after disruption
  - worsening/fragile situations

Example use:

- `recovering` should reinforce patience and resistance to premature progression
- `declining` should reinforce escalation of caution

### `purpose_micro_avoid`

`purpose_micro_avoid` is a tiny purpose-specific "what not to say" list.

This is not a doctrine file.
It is a compact selector-emitted behavioral guard.

Examples:

- `simple_acknowledgment`
  - do not offer unsolicited plan changes
  - do not surface old injury history
  - do not suggest progression
- `lightweight_answer`
  - do not expand scope beyond the question
  - do not re-derive the full training plan
- `milestone_or_reflection`
  - do not pivot immediately to next-week planning
  - do not undercut the moment with caveats

Purpose:

- reduce wrong-turn behavior even when doctrine content is technically correct

### `response_shape`

`response_shape` is a compact hint for directive structure and emphasis.

Examples:

- `answer_first_then_stop`
- `safety_then_next_step`
- `celebrate_then_synthesize`
- `structure_then_detail`
- `clarify_only`

Purpose:

- improve ordering and emphasis
- reduce cases where the strategist gives correct content in the wrong structure

## Control Hint Guardrails

Control hints should remain compact and bounded.

Rules:

- use enumerated values where possible
- do not emit long natural-language paragraphs
- do not duplicate doctrine prose
- do not let control hints replace strategist judgment
- strategist remains responsible for final coaching meaning and prioritization

## Target Doctrine Matrix

This is the intended file placement after refactor.

### Always-On

- [universal/core.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/core.md)
- [universal/authority_and_override_rules.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/authority_and_override_rules.md)

### Purpose-Based

`milestone_or_reflection`
- [universal/relationship_arc.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/relationship_arc.md)

`planning`
- [running/methodology.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/methodology.md)
- [running/common_prescription_errors.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/common_prescription_errors.md)

`plan_mutation`
- [running/methodology.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/methodology.md)
- [running/common_prescription_errors.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/common_prescription_errors.md)

`return_to_load`
- [universal/intensity_reintroduction.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/intensity_reintroduction.md)

### Situation-Based

`setback`
- [universal/return_from_setback.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/return_from_setback.md)
- [running/injury_return_patterns.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/injury_return_patterns.md)

`illness`
- [universal/illness_and_low_energy.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/illness_and_low_energy.md)

`travel`
- [universal/travel_and_disruption.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/travel_and_disruption.md)

`prescription`
- [running/common_prescription_errors.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/common_prescription_errors.md)

`intensity_return`
- [universal/intensity_reintroduction.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/intensity_reintroduction.md)

### Backstop

- [universal/common_coaching_failures.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/common_coaching_failures.md)

Load only when:

- yellow/red risk
- multiple risk conditions are active
- return-to-load decisions are being made under recent setback signals
- clarification is happening in a risk-sensitive context

### Backstop Conditions

For implementation, define backstop conditions as concrete boolean checks.

Recommended initial conditions:

- `risk_flag in {"yellow", "red"}`
- `len(active_situation_tags) >= 2` counting tags at any non-`none` strength
- `purpose == "return_to_load" and "setback" in active_situation_tags`
- `purpose in {"planning", "plan_mutation"} and "setback" in active_situation_tags and "prescription" in active_situation_tags`
- `reply_mode == "clarification" and any(tag in active_situation_tags for tag in {"setback", "illness", "travel", "intensity_return"})`

### Enricher

- [general/recommendations.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/general/recommendations.md)
- [running/recommendations.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/recommendations.md)

Load only when recommendation intent is explicit.

## Loading Rules By Purpose

Each purpose should eventually be formalized as:

- `must_load`
- `allowed_if`
- `must_not_load`

The prose rules below define the intended behavior.
Implementation and tests should turn them into enforceable assertions.

### `simple_acknowledgment`

Load:

- always-on only

Do not load:

- methodology
- relationship arc
- common failures
- setback doctrine unless a real setback signal is present

Formal target:

- `must_load`: `core`, `authority_and_override_rules`
- `allowed_if`: relevant situation doctrine only when safety/risk is clearly active
- `must_not_load`: `relationship_arc`, `methodology`, `common_coaching_failures` by default

### `lightweight_answer`

Load:

- always-on
- one situation doctrine only if the answer materially depends on it

Do not load by default:

- methodology
- common failures
- relationship arc

Goal:

- answer the question without dragging in full programming doctrine

Formal target:

- `must_load`: `core`, `authority_and_override_rules`
- `allowed_if`: one situation doctrine if it is materially required and signal strength is `strong`
- `must_not_load`: `relationship_arc`, `methodology`, `common_coaching_failures` by default

### `planning`

Load:

- always-on
- sport methodology
- prescription anti-patterns

Load conditionally:

- setback / illness / travel doctrine if that is shaping the plan
- common failures only if risk/ambiguity is present

Formal target:

- `must_load`: `core`, `authority_and_override_rules`, relevant sport methodology, relevant prescription anti-patterns
- `allowed_if`: situation doctrine shaping the plan, backstop doctrine when explicit backstop conditions are met
- `must_not_load`: `relationship_arc` unless milestone/reflection is also active

### `plan_mutation`

Load:

- always-on
- sport methodology when load or structure changes
- prescription anti-patterns

Load conditionally:

- setback doctrine if the mutation is driven by symptoms or recovery status
- travel/illness doctrine if they are the reason for the change
- common failures only when contradiction risk is real

Implementation note:

`plan_mutation` and `planning` may initially load the same doctrine.
That is acceptable in the first version.

Keep them separate as routing concepts for now because they are operationally distinct.
If implementation and evals show no meaningful difference, they can later be merged into:

- `planning` as the primary purpose
- `mutation` as a situation tag

Formal target:

- `must_load`: `core`, `authority_and_override_rules`, relevant mutation/planning doctrine
- `allowed_if`: risk doctrine when the mutation is driven by symptoms, disruption, or progression risk
- `must_not_load`: `relationship_arc` unless milestone/reflection is also active

### `setback_management`

Load:

- always-on
- relevant setback doctrine
- relevant sport return doctrine
- common failures backstop

Do not load by default:

- methodology unless actual plan structure is being prescribed

Formal target:

- `must_load`: `core`, `authority_and_override_rules`, relevant setback doctrine, relevant sport return doctrine
- `allowed_if`: methodology or prescription doctrine only when real re-prescription is happening
- `must_not_load`: enrichers by default

### `return_to_load`

Load:

- always-on
- return-from-setback doctrine
- intensity reintroduction
- sport return doctrine

Load conditionally:

- prescription anti-patterns if actual training is being prescribed
- common failures backstop

Formal target:

- `must_load`: `core`, `authority_and_override_rules`, `return_from_setback`, `intensity_reintroduction`, relevant sport return doctrine
- `allowed_if`: prescription anti-patterns, backstop doctrine
- `must_not_load`: `relationship_arc` unless milestone/reflection is also active

### `milestone_or_reflection`

Load:

- always-on
- relationship arc

Do not load by default:

- methodology
- prescription anti-patterns
- common failures

Unless the athlete is also asking for planning.

Formal target:

- `must_load`: `core`, `authority_and_override_rules`, `relationship_arc`
- `allowed_if`: planning doctrine only when the athlete is also asking for planning
- `must_not_load`: prescription and backstop doctrine by default

### `clarification`

Load:

- always-on only

Load conditionally:

- safety doctrine only if the clarification is safety-related

Formal target:

- `must_load`: `core`, `authority_and_override_rules`
- `allowed_if`: one safety/risk doctrine if the clarification is explicitly safety-related
- `must_not_load`: `relationship_arc`, `methodology`, `common_coaching_failures` by default

### `intake`

Load:

- always-on only

Formal target:

- `must_load`: `core`, `authority_and_override_rules`
- `allowed_if`: none by default
- `must_not_load`: purpose/situation/backstop/enricher doctrine by default

## Metadata Model

Doctrine files should be easy to move between loading tiers by editing metadata, not selector code.

Recommended frontmatter fields:

```yaml
---
priority: 70
scope: purpose
purposes: [planning, plan_mutation]
sports: [running]
situations: []
cost_tier: medium
---
```

Supported fields:

- `priority`
- `scope`: `always_on`, `purpose`, `situation`, `backstop`, `enricher`
- `purposes`
- `sports`
- `situations`
- `cost_tier`: `low`, `medium`, `high`

Optional later fields:

- `exclusive_with`
- `requires`
- `discouraged_with`

## Frontmatter Migration

The current doctrine files already use:

- `priority`
- `category`

The refactor should not drop these abruptly.

### Migration Rule

Phase 2 should:

- keep `priority`
- keep `category` for compatibility with the current selector during migration
- add the new metadata fields needed for purpose-based routing

Recommended migration table:

| Current field | Phase 2 status | Notes |
| --- | --- | --- |
| `priority` | keep | continues to support ordering/tie-breaks |
| `category` | keep temporarily | used by current category-budget selector until fully replaced |
| `scope` | add | new primary routing tier |
| `purposes` | add | new purpose-based routing field |
| `sports` | add | explicit sport applicability |
| `situations` | add | explicit situation applicability |
| `cost_tier` | add | later budget discipline |

`category` should only be removed or deprecated after the new selector fully replaces category-budget selection.

## Cost Discipline

Doctrine loading should observe prompt-budget discipline.

Recommended rules:

- `simple_acknowledgment`: only `low` cost doctrine
- `lightweight_answer`: `low`, plus at most one `medium`
- `planning`: several `medium` allowed
- `plan_mutation`: several `medium` allowed
- `setback_management`: multiple `medium`, possibly one `high`
- `return_to_load`: multiple `medium`, possibly one `high`
- `milestone_or_reflection`: mostly `low`

No turn should load doctrine just because it can.

## Proposed Selector API

Introduce a two-step selector:

```python
purpose = derive_turn_purpose(brief)
tags = derive_situation_tags(brief)
files = select_doctrine_for_turn(
    brief=brief,
    purpose=purpose,
    situation_tags=tags,
    sport=sport,
)
```

Recommended debug output:

```python
{
  "purpose": "planning",
  "sport": "running",
  "situation_tags": ["prescription"],
  "posture": "structure_then_detail",
  "trajectory": "stable",
  "purpose_micro_avoid": [
    "do not answer with a full recap before the structural decision",
  ],
  "response_shape": "structure_then_detail",
  "loaded_files": [
    "universal/core.md",
    "universal/authority_and_override_rules.md",
    "running/methodology.md",
    "running/common_prescription_errors.md",
  ],
  "skipped_files": {
    "universal/common_coaching_failures.md": "no backstop condition met",
    "universal/relationship_arc.md": "purpose mismatch",
  }
}
```

This should be a required selector output for traceability, not optional debug-only behavior.

Minimum trace payload:

- primary purpose
- situation tags with signal strength
- posture
- trajectory
- purpose-specific micro-avoid hints
- response shape
- loaded files
- why each loaded file loaded
- why top skipped files were skipped

This should be loggable in tests and trace tooling.

## Implementation Phases

Do **not** implement this as one bucket.
Each phase should be reviewable and reversible.

### Phase 1: Add Purpose Classification

Goal:

- add `turn_purpose` derivation without changing doctrine loading yet

Work:

- add `derive_turn_purpose(brief)`
- add `derive_situation_tags(brief)`
- document the exact fields and rules used for classification
- add tests for representative briefs
- add optional debug logging

Done when:

- purpose and tags are deterministic
- tests prove stable classification across representative cases
- phase review confirms the classification outputs are understandable and useful on representative real turns

### Phase 2: Add Metadata For Purpose-Based Loading

Goal:

- extend doctrine metadata to express purpose/scope/cost

Work:

- update frontmatter parser
- add metadata to all currently active doctrine files
- preserve existing `priority` and `category` fields during migration
- keep old selector behavior intact for now
- add integrity tests for new metadata fields

Done when:

- every active doctrine file has valid metadata
- no loading behavior has changed yet
- phase review confirms metadata can express the intended routing cleanly

### Phase 3: Move Obvious Over-Broad Files First

Goal:

- eliminate the clearest unnecessary doctrine loads with minimal risk

Work:

- audit [universal/relationship_arc.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/relationship_arc.md) for any truly universal guidance
- if needed, extract universally-needed tone/relationship guidance into [universal/core.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/core.md)
- then move the remainder of [universal/relationship_arc.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/relationship_arc.md) out of always-on and into `milestone_or_reflection`
- make [running/methodology.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/methodology.md) load only for `planning` and `plan_mutation`

Done when:

- simple acknowledgments and lightweight running questions no longer load these files
- planning turns still do
- phase review confirms prompt reduction happened on simple turns without obvious quality loss

### Phase 4: Refactor Selector To Purpose + Situation Routing

Goal:

- make purpose the primary doctrine routing mechanism

Work:

- replace the current mostly signal-driven optional selector with a purpose-aware selector
- preserve existing risk and sport signals as situation tags
- incorporate signal strength into situation-tag handling
- derive and wire compact control hints (`posture`, `trajectory`, `purpose_micro_avoid`, `response_shape`) into selector output and prompt usage
- add explainable skip reasons in debug output

Done when:

- selector chooses files by purpose first, situation second
- lightweight turns require stronger evidence before situation doctrine is loaded
- file movement is driven by metadata rather than hardcoded special cases where possible
- phase review confirms the selector trace clearly explains why files loaded or were skipped

### Phase 5: Restrict Backstop Doctrine

Goal:

- stop loading anti-pattern doctrine too often

Work:

- make [universal/common_coaching_failures.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/common_coaching_failures.md) a true backstop
- implement the explicit boolean backstop conditions defined in this document
- verify risky turns still load it
- verify simple turns do not

Done when:

- common failures loads only on ambiguity/risk-heavy turns
- phase review confirms the backstop is no longer appearing on simple turns

### Phase 6: Add Cost-Aware Selection

Goal:

- bound doctrine growth within each purpose

Work:

- enforce `cost_tier` budgets by purpose
- preserve must-load files
- log what was dropped and why

Implementation note:

Phase 6 is where `cost_tier` should become concrete.
Do not block earlier phases on perfect budget math.
Early phases should focus on better routing first.

Done when:

- doctrine selection is purpose-aware and budget-aware
- simple turns stay cheap even as doctrine grows
- phase review confirms cost rules are reducing prompt size without dropping clearly-needed doctrine

### Phase 7: Evaluate And Tune

Goal:

- verify the refactor improved prompt relevance without harming coaching quality

Work:

- compare loaded doctrine sets before and after
- compare strategist prompt size before and after
- assess whether the loaded doctrine set appears sufficient and minimal for reviewed turns
- review representative outputs for:
  - simple acknowledgments
  - lightweight answers
  - planning turns
  - mutation turns
  - setback turns
  - return-to-load turns
  - milestone/reflection turns

Done when:

- prompt size drops on simple turns
- complex turns still receive the right doctrine support
- no material regressions in coaching quality are found

## Required Test Coverage

Add explicit doctrine-selection tests for each purpose.

At minimum:

- `simple_acknowledgment` loads only always-on
- `lightweight_answer` does not load methodology by default
- `planning` loads methodology and prescription anti-patterns
- `plan_mutation` loads planning doctrine only when the turn actually changes structure/load
- `setback_management` loads setback doctrine and backstop doctrine
- `return_to_load` loads setback + intensity doctrine
- `milestone_or_reflection` loads relationship arc and does not load methodology by default
- recommendation doctrine loads only when recommendation intent is explicit

Also add:

- metadata integrity tests
- purpose derivation tests
- control-hint derivation tests
- debug output shape tests if logging/debug payload is formalized

## Follow-On Ideas (Not Required For Initial Refactor)

These are promising extensions, but they should not block the selector refactor:

- single counter-example injection on risky turns as a possible future replacement or supplement for some backstop doctrine
- strategist reasoning-discipline guidance for LLM-specific failure modes such as sycophancy, recency bias, over-hedging, and scope creep

These should be considered only after purpose-based doctrine routing is stable.

## Relationship To Doctrine Redesign

This refactoring should be sequenced ahead of the broader redesign work in [doctrine-redesign.md](/Users/levonsh/Projects/smartmail/archive/doctrine-redesign.md).

Recommended sequencing:

1. complete doctrine selector refactoring first
2. keep doctrine files as prose during selector refactoring
3. once routing is stable, revisit structured summaries / policy compilation

Reason:

- changing doctrine routing and doctrine representation at the same time is higher risk
- selector refactoring gives the routing infrastructure that later structured doctrine work will also need
- prompt relevance can improve materially before any prose-to-structured conversion

## Agent Implementation Rules

Agents following this plan should observe these rules:

- do not combine multiple phases in one PR
- do not rewrite doctrine prose while changing loader semantics unless explicitly needed
- preserve current behavior first, then narrow behavior in later phases
- treat simple-turn prompt reduction as the first measurable win
- add or update tests in the same PR as loader changes
- prefer moving doctrine by metadata over hardcoding more special-case logic

## Immediate Recommended First PR

The first implementation PR should do only Phase 1.

Why:

- lowest risk
- creates the routing abstraction needed for later phases
- gives immediate visibility into how turns should be classified
- does not yet change prompt behavior

The second PR should do only Phase 3 for the two most obvious over-broad files:

- [universal/relationship_arc.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/universal/relationship_arc.md)
- [running/methodology.md](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/doctrine/running/methodology.md)

That should produce the first meaningful prompt reduction on simple turns.

## Intended End State

The final selector should behave like this:

- always load stable coaching invariants
- load doctrine primarily because of the task the strategist is solving
- add situation doctrine only when that situation is truly active
- reserve backstop doctrine for contradiction-prone turns
- reserve enrichers for explicit requests

That should make the coach feel more expert for the actual task at hand, while reducing doctrine noise on simple turns.

## Implementation Context

This section maps plan concepts to current code locations so the implementing agent does not need to rediscover the codebase.

### Code Location Map

| Plan concept | Current code location | Notes |
| --- | --- | --- |
| Selector entry point | `doctrine/__init__.py:select_doctrine_files()` | Returns ordered, deduped list of paths |
| Core file list | `manifest.py:CORE_UNIVERSAL_FILES` | Currently 3 files including `relationship_arc.md` — Phase 3 must edit this |
| File registry + sport aliases | `manifest.py` | All doctrine files must be registered here |
| Signal blob builder | `doctrine/__init__.py:_signal_blob()` | Concatenates `reply_mode`, `constraints_summary`, `inbound_body`, `risk_flag`, `clarification_needed`, `risk_recent_history` into lowercase string |
| Trigger phrase lists | `doctrine/__init__.py` lines 119-220 | `_SETBACK_PHRASES`, `_ILLNESS_PHRASES`, `_TRAVEL_PHRASES`, `_INTENSITY_PHRASES`, `_PRESCRIPTION_PHRASES` — reuse as starting point for `derive_situation_tags()` |
| Signal detection functions | `doctrine/__init__.py` | `_has_setback_signals()`, `_has_illness_signals()`, `_has_travel_signals()`, `_has_intensity_signals()`, `_has_prescription_signals()` |
| Optional file selection | `doctrine/__init__.py:_select_optional_candidates()` | Signal-driven; this is the function Phase 4 replaces |
| Category budget system | `doctrine/__init__.py:_apply_category_budgets()` + `CATEGORY_BUDGETS` | `safety_protocol: 3`, `anti_pattern: 2`, `guidance: 2`, `resource: 1` — lives alongside new system until Phase 6 |
| Scoring / tie-breaking | `doctrine/__init__.py:_score_file()` | Base priority + body-match boost (+15) + risk-flag boost (+10) |
| Frontmatter parser | `doctrine/__init__.py:_parse_frontmatter()` | Currently only parses `priority` (int) and `category` (enum) — Phase 2 must extend this |
| File content cache | `doctrine/__init__.py:_CACHE`, `_META_CACHE` | Module-level dicts, cached for Lambda lifetime |
| Prompt assembly | `prompt.py:build_system_prompt()` | `base + "\n\nCoaching methodology:\n" + doctrine + continuity + contradicted` |
| Tiered base prompt | `prompt.py:_build_tiered_base_prompt(reply_mode)` | Already varies by `reply_mode` using constitution + operational rules + mode-specific rules from prompt packs |
| Control hint injection point | `prompt.py:build_system_prompt()` | Does not exist yet — control hints need a new injection site, likely between base prompt and doctrine |
| Integration / orchestration | `runner.py:run_coaching_reasoning_workflow()` | Calls `build_system_prompt()` and `list_loaded_files()` |
| Observability logging | `coaching.py` ~line 458 | Logs `doctrine_files_loaded` from runner result |
| Test file | `test_coaching_doctrine.py` | Uses `_base_brief(**overrides)` helper |
| Test brief helper | `test_coaching_doctrine.py:_base_brief()` | Creates valid brief with sport=running, risk=green, reply_mode=normal_coaching — extend for new test cases |

### Brief Structure

The `response_brief` dict passed to the selector has this shape:

```python
{
    "reply_mode": "normal_coaching",  # also: "clarification", "intake", others
    "athlete_context": {
        "primary_sport": "running",
        "constraints_summary": "...",
        "goal_summary": "...",
        "experience_level": "...",
        "structure_preference": "...",
    },
    "decision_context": {
        "risk_flag": "green",           # green / yellow / red
        "risk_recent_history": ["green", "green", "green"],
        "clarification_needed": False,
        "track": "main_build",
        "phase": "build",
        "today_action": "do planned",
        "weeks_in_coaching": 4,
    },
    "delivery_context": {
        "inbound_body": "...",          # primary signal source for phrase matching
    },
    "memory_context": {
        "contradicted_facts": [...],
        # continuity_summary, open_loops, etc.
    },
    "validated_plan": {},
}
```

### Key Implementation Details

**`relationship_arc.md` is in `CORE_UNIVERSAL_FILES`:**
Moving it in Phase 3 requires editing `manifest.py:CORE_UNIVERSAL_FILES`, not just selector logic. If the agent only changes the selector function, this file will still always load.

**`running/methodology.md` always loads for running athletes:**
In `_select_optional_candidates()`, the `methodology` key has no condition — it appends unconditionally when `sport == "running"`. Phase 3 must add a condition gate here.

**Prompt pack system:**
`prompt.py` loads prompt packs via `prompt_pack_loader.py`. The base prompt is split into `constitution`, `operational_rules`, and `reply_mode_rules` loaded from JSON files in `prompt_packs/coach_reply/v1/`. This is separate from doctrine and should not be modified during this refactor.

**Test patterns:**
All existing tests follow: build brief → call `select_doctrine_files(brief)` → assert file presence/absence. New tests should follow this pattern. Tests import internal functions directly (`_signal_blob`, `_parse_frontmatter`, etc.) — the agent can add new internal functions and test them the same way.
