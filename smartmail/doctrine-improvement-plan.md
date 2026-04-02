# Doctrine Improvement Plan

This document is the **content roadmap** for doctrine quality improvement.

It is no longer the top-level architecture plan for how doctrine should be injected into prompts.
That role now belongs to [doctrine-redesign.md](./doctrine-redesign.md), which defines the redesigned delivery model:

- compact policy compilation instead of large prose injection
- explicit boundaries around what can be deterministic
- preservation of LLM ownership over nuanced coaching judgment

Use this document to decide **what doctrine knowledge the system should contain**.
Use `doctrine-redesign.md` to decide **how that doctrine should be represented, compiled, and delivered**.

This document outlines the highest-impact improvements to the coaching doctrine system, ordered by expected effect on coaching quality.

The main goal is not to add more text indiscriminately. The goal is to make doctrine more operational so the coaching system makes better decisions under ambiguity, disruption, injury risk, and changing athlete context.

## How To Use This Document

This document answers:

- which doctrine domains should be expanded first
- which coaching situations deserve the most attention
- what kinds of doctrine content are likely to improve coaching quality most

For runtime architecture, retrieval strategy, doctrine artifact types, policy compilation, and implementation boundaries, use [doctrine-redesign.md](./doctrine-redesign.md).
For the practical near-term implementation order, also use the `Immediate Implementation Track` section in [doctrine-redesign.md](./doctrine-redesign.md).

## Priority 1. Add situation doctrine for common failure modes

This is the highest-leverage improvement.

Current doctrine is strongest at general principles and running methodology. The biggest coaching-quality failures observed so far are not caused by missing abstract principles. They happen in recurring situations where the system needs sharper judgment under uncertainty.

Add universal situation modules such as:

- `universal/return_from_setback.md`
- `universal/illness_and_low_energy.md`
- `universal/travel_and_disruption.md`
- `universal/race_week_and_taper.md`
- `universal/post_race_recovery.md`
- `universal/missed_training_and_reentry.md`
- `universal/hot_streak_risk.md`
- `universal/plateau_and_stagnation.md`

Why this matters:

- Many of the observed failures are situational, not sport-methodology failures.
- Situational doctrine helps the system handle the exact moments where athletes are most vulnerable to bad coaching decisions.
- These modules will generalize across many sports.
- These modules become high-value sources for policy rules, retrieval chunks, and counterexamples.

Expected impact:

- Better risk-aware coaching after setbacks
- Better handling of illness, travel, and interrupted weeks
- Better consistency during return-to-intensity decisions
- Fewer contradictions between stated caution and prescribed work

## Priority 2. Add explicit decision rules and progression logic

Doctrine should contain more concrete conditional rules, not just descriptive explanations.

Examples of the kind of rules to add:

- If an athlete is in the first green week after repeated yellow or red weeks, do not add intensity unless explicit safety criteria are met.
- If pain is improving but still present during warm-up or the next morning, progress duration before intensity.
- If the athlete expresses eagerness after time off, treat eagerness as a risk signal rather than proof of readiness.
- If an athlete explicitly updates or reverses a prior constraint, the current athlete report takes precedence over stored memory.

Why this matters:

- Models are better at following explicit operational rules than vague principles.
- This directly improves behavior in ambiguous coaching situations.
- These rules can later inform deterministic validation and safety guards.
- Explicit rules are also the best raw material for atomic policy records.

Expected impact:

- Better conservative decision-making under uncertainty
- More consistent intensity progression
- Better retirement of stale assumptions
- Clearer authority ordering between current report, memory, and prior plan

## Priority 3. Add counterexample doctrine for bad coaching patterns

Doctrine should teach both what good coaching looks like and what bad coaching looks like.

Add a module such as:

- `universal/common_coaching_failures.md`

Include counterexamples like:

- Prescribing intensity because the athlete sounds optimistic
- Using stale injury caveats after the athlete explicitly says the issue improved or resolved
- Saying the week should stay fully aerobic and then prescribing tempo or strides
- Letting enthusiasm after a good week override recovery logic
- Treating support details as more important than core planning truths

Why this matters:

- Counterexamples are often more memorable and actionable for the model than principle statements alone.
- This directly targets the failure patterns already seen in benches and live sims.
- Counterexamples are especially valuable as selectively retrieved strategist support.

Expected impact:

- Fewer self-contradictions
- Better safety posture
- Better consistency between plan logic and wording

## Priority 4. Add sport-specific doctrine for the sports that actually appear in real usage

Running is the only real sport-specific doctrine currently wired.

Add sport-specific doctrine for the sports that show up most often in actual coaching traffic and evals. Likely candidates:

- `cycling`
- `swimming`
- `triathlon`
- `strength`
- `rowing`
- `basketball`
- `tennis`
- `skiing`

For each sport, include:

- methodology and load distribution
- common injury-return patterns
- event-specific session priorities
- common athlete mistakes
- when not to prescribe intensity

Why this matters:

- Universal doctrine alone is not enough for sports with different session meanings and different progression norms.
- Sport-specific doctrine makes recommendations more precise and believable.
- Sport doctrine should be represented as both policy rules and retrieval-ready chunks.

Expected impact:

- Better specificity in coaching decisions
- Better sport-appropriate progression logic
- Less generic coaching language

## Priority 5. Add progression ladders for return and rebuild scenarios

Add doctrine modules that define staged progressions instead of leaving the model to invent them.

Useful examples:

- `universal/return_to_intensity_ladder.md`
- `running/achilles_return_to_run.md`
- `universal/return_after_illness.md`
- `universal/rebuild_after_disruption.md`

Why this matters:

- Staged ladders are easier for models to apply consistently than free-form judgment.
- They help prevent premature progression.
- They support more coherent next-step coaching.
- Ladders are especially good candidates for compact active policy snippets.

Expected impact:

- Better recovery-to-build transitions
- Safer rebuild flows
- More reliable handling of medium-risk returns

## Priority 6. Add athlete archetype doctrine

Add doctrine modules for recurring athlete patterns rather than treating all athletes as generic.

Useful archetypes:

- injury-prone but motivated
- time-crunched professional
- anxious beginner
- experienced self-coached athlete
- high-compliance overreacher
- inconsistent restart athlete
- masters athlete

For each archetype, describe:

- default coaching posture
- progression aggressiveness
- what signals matter most
- common coaching mistakes
- communication style calibration

Why this matters:

- Athlete differences are not just sport differences.
- Communication and progression logic should depend on who the athlete is.
- Archetypes should be treated carefully: use them as soft doctrine context, not rigid deterministic classification.

Expected impact:

- Better personalization
- Better tone matching without losing coaching quality
- Better risk calibration for different athlete types

## Priority 7. Add sport-specific session meaning doctrine

For each supported sport, define what major session types are actually for and when they are appropriate.

Example for running:

- easy run = aerobic support and recovery-compatible volume
- tempo = threshold stimulus with meaningful cost
- long run = endurance and event specificity
- strides = neuromuscular stimulus, but still not automatically safe in injury-sensitive phases

Why this matters:

- Many contradictions happen because the system treats sessions as labels instead of physiological tools.
- Session meaning doctrine improves consistency between risk posture and prescription.
- Session meaning doctrine should feed both rule compilation and sport-specific retrieval.

Expected impact:

- Fewer inappropriate session choices
- Better alignment between stated coaching intent and actual prescription

## Priority 8. Add explicit authority and override doctrine

The doctrine should define what takes precedence when signals conflict.

Examples:

- Current athlete report overrides stale memory.
- Safety doctrine overrides aggressiveness.
- Recovery state overrides generic build logic.
- Explicit athlete correction retires prior assumptions.
- Durable planning backbone outranks medium-value support details.

Why this matters:

- Several observed failures are really authority-ordering failures.
- Without explicit precedence rules, the system can make locally coherent but globally wrong decisions.
- Authority rules belong in the always-on coaching policy layer, not repeated as long prose.

Expected impact:

- Better memory correction behavior
- Better handling of reversals and updated constraints
- Better preservation of top-tier planning truths

## Recommended doctrine file structure

Each doctrine file should use a consistent operational structure:

1. `When this applies`
2. `Primary coaching goals`
3. `What to prioritize`
4. `What to avoid`
5. `Progression rules`
6. `Red flags`
7. `Example good response logic`
8. `Example bad response logic`

Why this structure:

- It is more usable than long free-form essays.
- It pushes doctrine toward decision support rather than reference prose.
- It makes future prompt retrieval and modular composition easier.
- It is also easier to convert into atomic policy records, retrieval chunks, and counterexample sets.

## Recommended first implementation batch

If only a small number of doctrine improvements are added first, start with these:

1. `universal/return_from_setback.md`
2. `universal/travel_and_disruption.md`
3. `universal/intensity_reintroduction.md`
4. `running/injury_return_patterns.md`
5. `running/common_prescription_errors.md`

Why this batch first:

- It directly targets the most important failure patterns already observed.
- It improves both safety and coaching precision.
- It gives the system better judgment in high-value, high-risk scenarios.

## Implementation notes

- Prefer adding doctrine only for sports and situations that appear in real evals or production traffic.
- Keep doctrine concrete and operational.
- When adding doctrine, decide up front which parts belong in canonical docs, atomic rules, retrieval chunks, and counterexamples.
- Do not assume every doctrine addition should become prompt text.
- Prefer doctrine that improves strategist judgment in real ambiguous cases rather than doctrine that merely sounds comprehensive.
- Avoid broad educational writing that does not change decisions.
- When possible, align doctrine modules with future deterministic validators and safety checks.

## Important system-design note

Doctrine alone will not solve every coaching-quality problem if upstream plan generation can still overpower it.

The strongest long-term architecture is:

1. planner creates candidate direction
2. doctrine-informed strategist decides what should actually be communicated
3. deterministic guardrails block contradictions and unsafe prescriptions

That means doctrine improvement should be paired with later work on authority split, validation, and safety enforcement.
