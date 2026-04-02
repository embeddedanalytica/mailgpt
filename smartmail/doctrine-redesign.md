# Doctrine Redesign Plan

## Goal

Redesign the `coaching_directive` generation path so coaching quality improves while prompt size and token cost drop substantially.

The objective is **not** to replace nuanced coaching judgment with deterministic code.

The objective is to:

- remove prompt redundancy
- compile stable constraints and doctrine into a compact per-turn policy
- preserve LLM ownership over subtle human interpretation and coaching strategy

## Current State Acknowledgment

This redesign is a **north-star architecture document**, not a claim that the current system lacks structure.

The current implementation already has several important layers in place:

- a strategist LLM that produces a `CoachingDirective`
- a separate writer LLM that renders the final athlete-facing message
- selective doctrine loading based on deterministic signal matching
- partial validation infrastructure

What is missing is not basic architecture. What is missing is a more compact and higher-salience representation of doctrine once relevant doctrine has been selected.

The immediate problem is therefore not "all doctrine is loaded all the time."
The more accurate problem statement is:

- the base prompt is too large and mixes permanent invariants with operational rules
- selected doctrine is still injected as raw prose
- multiple doctrine files can activate without explicit priority resolution
- doctrine growth still scales linearly with prompt size

The redesign below describes the desired long-term architecture.
It should not be interpreted as a recommendation to rewrite the whole pipeline immediately.

## North Star

Build a `policy-compilation` layer that:

- removes prompt redundancy
- converts stable constraints into compact structured inputs
- leaves subtle interpretation and coaching strategy to the LLM

The LLM should remain the decision-maker for:

- what the athlete most needs to hear
- how to weigh conflicting signals
- how cautious or assertive to be
- whether the moment calls for celebration, synthesis, reassurance, directness, or restraint
- how to frame coaching so it builds trust

## Recommended Enhancement Model

The best path is not to keep expanding prompt-injected doctrine prose.

The better model is a layered coaching enhancement system with four distinct sources of intelligence:

1. Stable coach philosophy
2. Turn-specific situational policy
3. Athlete-specific memory and continuity
4. LLM strategic reasoning

The current prompt design asks doctrine to do all four jobs at once. That creates prompt bloat and weakens signal quality.

The redesigned target is:

- small always-on coach constitution
- structured doctrine knowledge base off-prompt
- selective retrieval or compilation of only the relevant doctrine for a turn
- LLM strategist retains ownership over nuanced coaching judgment

## Target Runtime Architecture

The intended runtime stack is:

1. `Coach Constitution`
2. `Scenario Interpreter`
3. `Policy Compiler`
4. `Strategist LLM`
5. `Validator`
6. `Writer LLM`

### 1. Coach Constitution

This is the only always-on doctrine-like prompt content.

It should remain very small and encode only the permanent invariants:

- coach identity and non-human boundaries
- instruction fidelity
- safety over ambition
- current athlete report over stale memory
- no invented facts
- strategist decides meaning, writer only renders

This layer should stay short, stable, and highly curated.

### 2. Scenario Interpreter

This layer identifies what kind of coaching situation the current turn represents.

Examples:

- setback rebuild
- illness uncertainty
- travel disruption
- direct question
- milestone celebration
- reflection request
- return-to-intensity consideration
- constrained training week
- continuity transition checkpoint

The interpreter should not make final coaching judgments.
Its job is only to identify which doctrine tools are relevant.

### 3. Policy Compiler

This layer takes structured doctrine knowledge and compiles a small per-turn coaching packet.

The compiled packet should contain only the most relevant:

- active rules
- active risks
- relevant avoid patterns
- style hints
- continuity constraints
- athlete instruction constraints

The policy compiler should reduce doctrine to a small, high-salience decision packet.

### 4. Strategist LLM

The strategist remains the core decision-maker.

The strategist should still own:

- strategic meaning
- prioritization of what matters most
- ambiguity resolution
- tradeoff handling
- nuanced continuity recommendations
- athlete-specific synthesis

Doctrine should improve the strategist's judgment environment, not replace its judgment.

### 5. Validator

The validator enforces hard boundaries only.

Examples:

- banned-topic violations
- explicit instruction violations
- invalid schema fields
- contradiction with corrected facts
- obvious scope breaches

The validator must not rewrite coaching strategy because it disagrees with the strategist.

### 6. Writer LLM

The writer turns the strategist directive into the final athlete-facing message.

The writer should remain downstream from the strategist and must not regain strategic authority.

## Immediate Implementation Track

The recommended near-term path is an incremental compression strategy, not a full architectural rewrite.

This immediate track should preserve the current pipeline shape and improve the highest-impact bottlenecks first.

### Priority A: Split The Base Prompt

Refactor the current strategist base prompt into:

- `coach constitution`
- `operational rules`

The constitution should contain only stable invariants.
Operational rules should contain reply-mode logic, behavioral guidance, and other turn-shaping instructions that do not belong in the permanent identity layer.

Expected effect:

- smaller always-on prompt
- clearer signal hierarchy
- less competition between invariants and operational guidance

### Priority B: Convert Doctrine Prose Into Structured Summaries

Keep canonical doctrine markdown for humans, but add a more compact runtime form for each doctrine file.

Each selected doctrine module should compile to a small structured payload, such as:

- `rules`
- `avoid_patterns`
- `style_hints`
- `priority`

The runtime should inject these structured summaries instead of full markdown prose wherever possible.

Expected effect:

- better token efficiency
- higher salience per token
- less doctrine-vs-doctrine competition inside the strategist prompt

### Priority C: Add Priority-Based Doctrine Selection And Capping

The current selector already activates relevant doctrine based on signals.
The next improvement is to rank the activated doctrine by relevance and cap how much doctrine is injected.

That means:

- score selected doctrine modules by current-turn relevance
- prefer top-ranked modules when total injected doctrine would become too large
- make precedence more explicit when multiple guidance sources are active

Expected effect:

- bounded prompt growth
- less contradictory guidance
- better scaling as doctrine coverage expands

### Priority D: Add Strategist-Side Hard Guardrails

Keep the strategist as the owner of coaching meaning, but add narrow post-strategist validation where objective violations can be detected.

Examples:

- banned-topic violations
- explicit format violations
- contradiction with corrected facts
- invalid continuity fields

Expected effect:

- stronger safety and obedience without collapsing strategy into deterministic logic

## Recommended Execution Order

For the current scale of the system, the recommended order is:

1. split the strategist base prompt into constitution and operational rules
2. add structured runtime summaries for doctrine modules
3. add doctrine relevance scoring and injection caps
4. strengthen strategist-side hard guardrails
5. expand eval coverage
6. reassess whether richer policy compilation or retrieval is still needed

This sequence is intentionally smaller than the full target architecture.
It should be treated as the active implementation plan for the current doctrine footprint.

## Hard Boundaries

Do not move these into deterministic code:

- emotional interpretation
- trust or relationship meaning beyond coarse operational staging
- readiness judgment under ambiguous signals
- tradeoff resolution between competing coaching goals
- prioritization of what matters most to communicate
- synthesis of athlete-specific insight
- nuanced continuity transitions when multiple interpretations are plausible

Deterministic code may only do:

- bounded extraction
- normalization
- routing
- compact policy assembly
- hard guardrails
- post-generation validation of explicit constraints

If a function starts making assumptions that require reading between the lines, it belongs back in the LLM layer.

## Hard Boundary: What Must Remain LLM-Owned

Do not move these into deterministic code or rigid retrieval-only systems:

- emotional interpretation
- trust calibration beyond coarse operational staging
- readiness judgment when signals are mixed
- tradeoff resolution between caution, momentum, celebration, and progression
- deciding what matters most to say first
- personalized synthesis of what the coach has learned about the athlete
- nuanced handling of emotionally loaded ambiguity

If the task requires reading between the lines, resolving ambiguity, or choosing between plausible interpretations, it belongs in the strategist LLM.

## Doctrine Artifact Model

Doctrine should exist in multiple forms, each optimized for a different job.

### 1. Canonical Doctrine Docs

Human-authored longform source of truth.

Purpose:

- knowledge development
- editorial review
- doctrine quality iteration
- preserving richer coaching philosophy and examples

These docs should not be injected in full during normal runtime.

### 2. Atomic Policy Rules

Short machine-usable rules derived from canonical doctrine.

Purpose:

- compact policy compilation
- routing
- high-salience strategist support

Suggested fields:

- `id`
- `category`
- `sport`
- `scenario_tags`
- `priority`
- `rule_text`
- `avoid_text`
- `style_hint`
- `counterexample_ref`

### 3. Retrieval Chunks

Doctrine fragments sized for semantic retrieval.

Purpose:

- fetching 1-3 highly relevant doctrine snippets for hard or unusual turns
- surfacing examples or edge-case guidance without loading everything

### 4. Counterexample Library

A structured set of bad coaching patterns and why they fail.

Purpose:

- helping the strategist avoid common failure modes
- strengthening evals
- enabling targeted retrieval for dangerous situations

### 5. Eval Fixtures

Known hard turns and expected strategist behavior.

Purpose:

- regression protection
- doctrine quality measurement
- rollout confidence

## Retrieval And Compilation Strategy

The preferred runtime behavior is:

1. interpret the scenario
2. compile active policy rules
3. retrieve extra doctrine only when needed
4. send a compact coaching packet to the strategist

This means:

- most turns should not retrieve long doctrine prose
- complex or unusual turns may retrieve a small number of relevant examples or chunks
- doctrine cost should scale with turn complexity, not with total doctrine size

### Retrieval Should Be Used For

- rare edge cases
- nuanced archetypes
- emotionally loaded coaching moments
- reflection requests
- milestone responses
- sport-specific edge conditions

### Retrieval Should Not Be Used For

- basic always-on coaching invariants
- explicit athlete instructions
- stable rule selection logic
- simple bounded constraints

## Recommended Prompting Strategy

The strategist prompt should contain:

- short coach constitution
- compact compiled policy
- athlete context, memory, and continuity
- optionally 1-2 highly relevant retrieved doctrine snippets or examples

The strategist prompt should not contain:

- large prose doctrine bundles
- broad generic doctrine not relevant to the turn
- duplicate expressions of the same coaching rule

## Recommended Example Strategy

Examples are high value but expensive.

Use them selectively.

Maintain a library of strong coaching examples for:

- reflection requests
- milestone celebration
- setbacks with optimism
- travel disruption
- injury return
- direct question under risk
- ambiguous progression readiness

At runtime:

- retrieve examples only when scenario complexity justifies them
- cap retrieved examples aggressively
- prefer one strong example over many weak ones

## Recommended Future Fine-Tuning Strategy

Fine-tuning may eventually help, but only after:

- doctrine is structured
- strategist contracts are stable
- evals are strong
- counterexamples are well-curated

Fine-tuning is most useful for:

- tone consistency
- prioritization patterns
- more reliable coach-like sequencing
- improved handling of recurring nuanced situations

Fine-tuning is not a substitute for:

- doctrine structure
- policy compilation
- scenario interpretation
- evaluation discipline

## Agent Execution Guidance

Agents working on this system should follow these principles:

1. Do not solve prompt bloat by adding more prose.
2. Prefer structured doctrine artifacts over larger prompt text.
3. Preserve LLM ownership of nuanced coaching judgment.
4. Add deterministic logic only for bounded extraction, routing, compilation, and hard validation.
5. If a proposed rule requires interpreting subtext, leave it in the strategist LLM.
6. Prefer one strong active rule over several redundant paraphrases.
7. Prefer one strong retrieved example over many loosely relevant examples.
8. Judge success by coaching quality and robustness, not token reduction alone.

## Phase 1: Audit And Partition

Define three buckets for every current prompt and doctrine rule.

### Bucket A: Safe For Deterministic Handling

- explicit athlete instructions
- banned topics
- format constraints like "3 lines max"
- obvious contradiction handling
- continuity enum and value normalization
- doctrine module activation
- deduplication of repeated rules

### Bucket B: Hybrid

- reply suppression candidate
- scenario tagging like setback, travel, illness
- relationship stage as a coarse communication hint
- risk posture as a bounded summary

### Bucket C: LLM-Only

- strategic meaning
- tone or stance selection
- recommendation priority
- ambiguity resolution
- personalized synthesis

### Deliverable

A rule inventory doc mapping each current prompt section and doctrine file into Bucket A, B, or C.

## Phase 2: Replace Prose Doctrine With Atomic Rule Records

Convert doctrine files into rule records with small fields, for example:

- `id`
- `category`
- `trigger_type`
- `priority`
- `rule_text`
- `avoid_text`
- `style_hint`
- `safety_level`

Important boundary:

- rule records must express constraints and heuristics
- rule records must not encode final coaching conclusions for ambiguous situations

Example:

- acceptable: "First good week after yellow/red is not progression proof"
- not acceptable: "If athlete says they feel good after 2 bad weeks, hold intensity"

The second example is too interpretive and must stay in the strategist LLM.

### Deliverable

Create `coaching_policy_rules.py` or `policy_rules.json` as the new doctrine source of truth for strategist policy compilation.

## Phase 3: Build A Deterministic Policy Compiler

Create a compiler that:

- extracts bounded facts from the brief
- activates relevant rule records
- dedupes overlapping doctrine
- emits a compact decision packet

Compiler output should contain only:

- `hard_constraints`
- `scenario_tags`
- `risk_posture`
- `relationship_stage`
- `priority_rules`
- `avoid_rules`
- `style_hints`
- `reply_action_candidate`
- `continuity_constraints`
- `contradicted_facts`

Boundary:

- compiler can summarize the situation
- compiler cannot decide the coaching meaning of the situation

### Deliverable

Implement `compile_coaching_policy(response_brief, continuity_context)`.

## Phase 4: Shrink The Strategist Prompt

Replace the current long strategist prompt with:

- short role definition
- explicit statement that the LLM owns coaching judgment
- compact compiled policy
- response contract and schema reminder

The new prompt should communicate:

- deterministic inputs provide constraints and active coaching rules
- the LLM must still interpret the athlete and decide what matters most

Boundary:

- do not stuff old prose back into the prompt in compressed paragraph form
- if a rule cannot fit as a short atomic instruction, it probably belongs in the LLM reasoning domain, not deterministic code

### Deliverable

Replace `build_system_prompt()` so it uses compiled policy instead of raw doctrine essays.

## Phase 5: Add Guardrails Without Expanding Determinism

Post-generation validators should only enforce hard failures, such as:

- banned topic violations
- explicit instruction violations
- invalid continuity fields
- contradiction with known corrected facts
- obvious scope breaches

Validators must not override legitimate coaching judgment unless a hard rule was broken.

Boundary:

- validator may reject or repair explicit contract violations
- validator must not rewrite strategy because it "disagrees" with the LLM

### Deliverable

Implement `post_validate_directive()` with narrow scope.

## Phase 6: Eval Strategy

Run old and new systems side-by-side on:

- existing coaching reasoning evals
- obedience fixtures
- known bad live turns
- milestone, setback, reflection, clarification, suppression, and direct-question cases

Measure:

- prompt size
- doctrine or rule coverage
- directive quality
- violation rate
- regression rate in nuanced coaching cases

Boundary:

- token reduction alone is not success
- a cheaper system that gets more brittle is a failure

### Deliverable

Produce a comparison report with pass or fail thresholds before rollout.

## Phase 7: Safe Rollout

1. Ship behind a feature flag.
2. Log compiled policy and matched rule ids.
3. Compare outputs silently first.
4. Promote only after eval parity or improvement on nuanced cases.
5. Keep doctrine markdown during migration as source material, but stop injecting it directly into strategist prompts.

## Decision Rule For Future Changes

Before adding deterministic logic, ask:

1. Is this a hard constraint or bounded extraction problem?
2. Can it be implemented without interpreting subtext?
3. Would two strong human coaches almost always agree on this as a rule?
4. Can failure be detected objectively in tests?

Only if all answers are yes should it move into deterministic code.

If not, keep it in the strategist LLM.

## Recommended End State

- deterministic layer: compiler and guardrails
- strategist LLM: meaning and coaching judgment
- deterministic validation: hard-boundary enforcement
- writer LLM: rendering

This preserves subtle coaching where it matters while removing prompt bloat from areas that should not consume model attention every turn.
