# Bug 19 Memory Design Proposal

Date: 2026-04-03  
Repo: `/Users/levonsh/Projects/smartmail`

## Purpose

This document proposes a cleaner memory architecture to address bug `19` and the broader durable-memory retention problem in the coaching system.

The target audience is another LLM agent or engineer reviewing memory design options.

## Problem We Are Solving

The coach must start each turn from persisted state and still behave like it remembers the athlete well.

The system currently fails this in one important way:

- important durable truths can disappear when memory is under budget pressure
- once lost, those truths are no longer available to future coaching turns
- the current design mixes up persistence limits with prompt limits

This shows up in bug `19`:

- primary event goals like `1500 free` or `summer rec league` can disappear
- core schedule anchors can also disappear under pressure from later-added medium facts
- this is a coaching failure, not just a storage failure

The real requirement is not “make a 7-item fact list work better.”

The real requirement is:

- retain all important truths needed for good coaching
- keep memory bounded and compact
- avoid conflicting active truths
- avoid brittle deterministic logic that tries to infer meaning from athlete wording

## Hard Requirements

These are the governing requirements, in priority order:

1. The coach cannot forget an important fact about the athlete.
2. The memory object cannot grow uncontrolled.
3. Memory cannot contain conflicting active notes.
4. The design cannot depend on simplistic word-matching determinism to decide what facts mean.

## Current Design

Relevant files:

- [athlete_memory_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/athlete_memory_contract.py)
- [athlete_memory_reducer.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/athlete_memory_reducer.py)
- [coaching_memory.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/coaching_memory.py)
- [runner.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/unified/runner.py)
- [validator.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/unified/validator.py)
- [response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_assembly.py)

### How AM2 currently works

1. Post-reply memory refresh runs after coaching.
2. The LLM emits candidate operations: `upsert`, `confirm`, `retire`.
3. Deterministic code validates and applies those operations.
4. Active durable facts are stored in a flat list.
5. The reducer hard-limits the active list using `MAX_ACTIVE_FACTS = 7`.
6. Response generation reads the surviving durable facts and uses them as memory context.

### Important current properties

- active memory is a single flat pool of durable facts
- facts have one coarse `importance` bit: `high` or `medium`
- goals and constraints are forced to `high`
- budget enforcement destructively evicts medium facts
- retirements delete facts completely from the active set
- prompt-time memory is effectively the same object as persisted durable memory

## Current Design Limitations

### 1. Persistence budget and prompt budget are coupled

This is the core architectural issue.

The current design treats the stored durable memory as if it must already be prompt-sized. That means the system is forced to delete truths from persistence just to keep prompt inputs small.

Effect:

- memory behaves like a lossy cache instead of a durable source of truth

### 2. Eviction is destructive

When a fact loses the budget competition, it is not merely omitted from one prompt. It is removed from persisted active memory.

Effect:

- an important truth can vanish permanently even though it is still true

### 3. The model is too flat

All durable facts compete in one pool:

- primary event goals
- recurring structure
- useful but secondary details
- preferences
- miscellaneous context

Effect:

- there is no structural protection for “must survive” truths other than a coarse importance label

### 4. One bit of importance is too weak as a retention model

The current system has only:

- `high`
- `medium`

This is not enough to express the difference between:

- a primary competition goal
- a durable weekly availability anchor
- a helpful detail
- a preference

Effect:

- retention depends too heavily on initial labeling

### 5. Conflict handling exists, but only partially solves the real problem

The current design already supports `retire` and replacement behavior, which is good. But this only solves explicit contradiction management. It does not solve the broader issue of safely retaining many true facts over time.

### 6. The design encourages false tradeoffs

Because memory must fit a tiny active set, the system is pushed toward brittle heuristics like:

- “promote this phrase to high”
- “treat this wording as a goal”
- “keep this kind of schedule fact”

These heuristics may patch symptoms but do not solve the underlying retention design.

## Historical Context From AM1 and AM2

Relevant archived design records:

- [athlete-memory-epic.md](/Users/levonsh/Projects/smartmail/archive/athlete-memory-epic.md)
- [athlete-memory-epic-m2.md](/Users/levonsh/Projects/smartmail/archive/athlete-memory-epic-m2.md)

The archived docs are useful because they show how the current system evolved and which tradeoffs were explicitly chosen.

### What AM1 optimized for

AM1 was intentionally lightweight.

Its design goals were:

- useful cross-thread coaching memory
- small implementation surface
- bounded prompt-safe memory
- no advanced retrieval or ranking

Important AM1 choices:

- `memory_notes[]` and `continuity_summary` were introduced together
- memory stayed LLM-assisted
- refresh returned a full revised memory state
- retrieval to response generation was explicitly bounded
- the system enforced an upper bound of `7` memory notes

This was a reasonable first system, but the archived AM1 doc makes one tradeoff very clear:

- storage boundedness and prompt boundedness were treated as the same problem

That tradeoff explains many of the later retention failures.

### What AM2 was trying to fix

The AM2 stabilization doc correctly identified several AM1 weaknesses:

- omission-driven deletion
- unstable durable state transitions
- over-reliance on the model for final state mutation
- the need for typed durable facts with stable identity
- the need for deterministic mutation and retirement rules

That is the origin of the current candidate-op + reducer architecture.

These AM2 ideas were valuable and remain correct:

- durable memory should not be replaced wholesale from one LLM payload
- omission should not delete facts
- the LLM should interpret evidence, not own final persistence decisions
- retirement and mutation rules should be deterministic
- contradiction handling should be explicit

### The most important historical lesson

The archived AM2 plan explicitly deferred retrieval redesign.

It says, in substance:

- fix durable memory stability first
- do not redesign reply-time retrieval unless it becomes necessary

That deferment appears to be the key historical reason the current system still has bug `19`.

The reducer and candidate-op model solved the AM1 full-state-rewrite problem, but the architecture still inherited AM1’s deeper coupling:

- the persisted active durable set is still forced to be prompt-sized

So the historical lesson is:

- AM2 correctly fixed state mutation mechanics
- but it intentionally stopped short of separating durable storage from prompt retrieval
- bug `19` is strong evidence that this deferred split is now required

### Another useful lesson from the archived AM2 doc

The AM2 plan repeatedly warns against brittle determinism:

- no deterministic NLP fact extraction from raw email
- no regex-heavy memory policy
- no broad freeform rewrite optimizer

That supports the current proposal.

The right next move is not:

- more phrase-level hardcoding

The right next move is:

- better structure around retention, consolidation, and retrieval

### One place where the archived AM2 plan was directionally right

The planned AM2 design included lightweight consolidation and structured compaction rather than broad freeform rewriting.

That is still valuable.

The current proposal keeps that spirit, but shifts the boundary:

- bounded active sections and bounded retired sets should keep the durable store controlled
- retrieval compilation should be used to keep prompts bounded

In other words:

- keep AM2’s narrow mutation model
- add the retrieval/storage separation that AM2 intentionally deferred

## Root Cause of Bug 19

Bug `19` is not fundamentally an “eviction ordering bug.”

It is a memory model bug:

- the system stores durable truths directly in a tiny prompt-sized active set
- anything not protected strongly enough can be deleted
- the system has no separate durable source of truth from which to recompile prompt context later

Even if eviction ordering improves, the architecture still allows important truths to be forgotten.

## Design Goal

Replace “flat active fact list with destructive budget eviction” with:

- a bounded durable memory store
- explicit contradiction resolution
- a separate prompt-time memory compiler
- controlled compression rather than destructive forgetting

## Proposed Design

## Overview

Split memory into two parts:

1. Structured active durable memory with a small bounded retired set per section
2. Prompt memory compiler

### Part 1: Structured Active Durable Memory

This is the persisted source of truth for what is currently true and currently relevant to coaching.

It should:

- keep active durable truths that materially affect current or near-future coaching decisions
- contain no contradictions
- support explicit retirements and replacements
- stay bounded by section caps
- be small enough that a compiler can reliably turn it into prompt context

This structure should directly influence coaching decisions. Retired facts are preserved only in a small bounded per-section set for lineage and recent reversal visibility, not as a separate historical reasoning tier.

### Part 2: Prompt Memory Compiler

This is generated on each turn from structured active durable memory and continuity.

It should:

- select bounded prompt memory for the current coaching turn
- enforce a small prompt budget
- prefer active truths only
- ignore retired facts by default
- never silently delete persisted truths from storage

Important v1 requirement:

- the compiler should be deterministic in the hot path
- it should not be a separate per-turn LLM call in v1
- it should not do freeform compile-time summarization in v1

## Recommended Memory Shape

Instead of one flat active fact pool, use a structured persisted memory store with per-section active and retired buckets.

Suggested sections:

- `goals`
- `constraints`
- `schedule_anchors`
- `preferences`
- `context_notes`

Each section should hold structured memory objects, not raw text blobs.

Each object should preserve:

- stable identity
- summary
- status such as active or retired
- replacement links or supersession links where relevant
- timestamps
- retirement metadata when applicable

Important note on `supersedes`:

- `supersedes` is not part of normal prompt retrieval
- it exists to support deterministic state mutation and bounded retired-lineage handling
- if a fact has never replaced another fact, `supersedes` can be empty or omitted

### Specific Boundary Rules

These boundaries are important enough to implement explicitly.

#### What belongs in active memory

Keep a fact in hot active memory only if all of the following are true:

- it is currently true
- it materially affects coaching decisions now or in the near future
- losing it would plausibly cause the coach to make a worse recommendation

Typical examples:

- current primary goals
- current injury/health constraints
- current recurring availability or blockers
- current durable training-structure anchors
- current communication preferences that materially affect delivery
- current equipment facts only when they materially affect coaching decisions

#### What should leave active memory

A fact should leave hot active memory when any of the following become true:

- it is explicitly no longer true
- it has been clearly superseded by a newer active fact
- it is still true historically but no longer materially affects coaching
- it is a low-level detail better represented by a broader current summary

When a fact leaves active memory, it should go to one of two places:

- the section’s bounded retired bucket if short-term lineage is useful
- nowhere if it no longer has meaningful coaching value

#### What belongs in retired memory

Retired memory is not a full historical tier.

It exists only to preserve a small amount of recent lineage and replacement context per section.

Keep a retired fact only if at least one of the following is true:

- it was recently superseded by an active fact
- it was a meaningful recently completed goal
- it is useful to explain a current active fact
- it helps prevent rapid contradictory flip-flopping

Do not keep retired facts just because they used to be true.

#### Runtime role of `supersedes`

The runtime role of `supersedes` should be explicit and narrow.

It should be read only for these purposes:

1. deterministic contradiction handling at write time
2. deterministic routing of replaced facts into the retired bucket
3. retired-cap eviction ordering when deciding which retired facts still explain current active truth
4. narrow consolidation where one object explicitly replaces another

It should not be used for:

- normal prompt retrieval
- semantic ranking
- freeform historical reasoning

In other words:

- `supersedes` is load-bearing for mutation and lineage
- it is not load-bearing for normal coaching prompt assembly

#### What does not belong in retired memory

Do not keep these in the bounded retired set:

- low-value historical detail
- old transient disruptions
- old incidental equipment facts
- stale preferences with no ongoing relevance
- old details that do not explain any current active truth

### Suggested Size Targets

These are design targets, not hard-coded numbers, but they should be concrete enough for implementation planning.

Suggested active caps:

- `goals`: 2 to 4 active objects
- `constraints`: 4 to 8 active objects
- `schedule_anchors`: 4 to 8 active objects
- `preferences`: 2 to 4 active objects
- `context_notes`: 2 to 4 active objects

Suggested retired caps:

- `goals`: up to 5 retired objects
- `constraints`: up to 5 retired objects
- `schedule_anchors`: up to 5 retired objects
- `preferences`: up to 5 retired objects
- `context_notes`: up to 5 retired objects

### Retired Fact Lifecycle

This section should be implemented explicitly. Retired facts should not remain as an unbounded pile of raw retired objects.

#### Step 1: Retirement event

When an active fact is replaced, resolved, completed, or explicitly no longer true:

- mark the hot fact inactive
- record why it left the active set
- record whether it was:
  - replaced by a newer active fact
  - completed
  - resolved
  - no longer relevant

At this point, the system must make a second decision:

- keep in the section’s retired bucket
- drop entirely

Retirement alone is not enough. The post-retirement destination must be explicit.

#### Step 2: Immediate routing after retirement

Each retired fact should go to exactly one of these destinations:

1. `dropped`
2. `retired_bucket`

Recommended routing rules:

- `dropped`
  Use when the retired fact has no meaningful future coaching value and is not needed for history.

- `retired_bucket`
  Use when the retired fact still provides recent lineage value and the section’s retired cap allows it.

#### Step 3: When retired facts stay atomic

Retired facts should remain atomic only while they are still individually useful.

Examples:

- a recently completed major race goal
- a recent injury episode that still affects current caution
- a recently changed life constraint that may still be discussed directly

These should remain atomic only while they are still individually useful. Once they stop needing retained treatment, they should be dropped.

#### Step 4: When retired facts are dropped entirely

A retired fact should be dropped when all of the following are true:

- it is no longer active
- it has no meaningful future coaching value on its own
- it does not materially improve the athlete’s long-term historical picture
- it is not needed to explain a current active fact or recent replacement lineage

Example:

- an old note about a short-lived pool lane-space issue from two years ago

#### Step 5: Retired cap enforcement

Each section keeps at most 5 retired facts.

If a new retired fact is admitted and the section is over cap:

- drop the least useful retired fact first
- use a deterministic retired-retention sort key

Suggested retired-retention sort key, strongest kept last and weakest dropped first:

1. `explains_active_truth`
2. `retire_reason_priority`
3. `retired_at`
4. `last_confirmed_at`
5. stable tie-breaker such as `memory_id`

Definitions:

- `explains_active_truth`
  - `1` if any active fact explicitly lists this retired fact in its `supersedes`
  - `0` otherwise

- `retire_reason_priority`
  - `0` for `no_longer_relevant`
  - `1` for `resolved`
  - `2` for `completed`
  - `3` for `replaced_by_newer_active_fact`

- `retired_at`
  - older retired facts are weaker than more recently retired facts

- `last_confirmed_at`
  - older last confirmation is weaker than newer last confirmation

Concrete eviction behavior:

- sort retired facts ascending by the key above
- evict from the front until the section is back at cap

Specific use of `supersedes` here:

- if an active fact explicitly supersedes a retired fact, that retired fact gets a temporary retention boost
- once the replacement is no longer recent and the retired fact no longer explains anything operationally useful, the retired fact can be dropped

In this design:

- active memory is for current truth
- retired memory is for a small amount of recent lineage only

## Key Design Principles

### 1. Bounded durable store, not tiny durable store

The durable store should still have limits, but they should be section-based and materially larger than today’s 7-fact pool.

The durable store should be bounded by:

- explicit active section caps
- explicit retired section caps

The main point is:

- bounded by category and small retained lineage
- not bounded by one tiny flat pool

### 2. Contradiction is resolved structurally

When a new truth replaces an old truth:

- the old truth should move out of the active set
- the new truth should point to what it superseded when possible

This keeps active memory non-conflicting without relying on word matching.

### 3. Compression replaces destructive forgetting

When the store grows too large:

- active truth should remain protected
- only retired lineage should be trimmed under retired caps

This is different from flat eviction because active truths are not competing with retired facts or incidental history.

### 4. Retrieval is turn-specific

Prompt memory should be selected per turn from the durable store.

The compiler should decide what to surface for:

- planning
- risk management
- schedule decisions
- tone/personalization

This is where prompt-budget control belongs.

## Compiler V1 Contract

This section is intentionally concrete because the compiler is the main new risk surface.

### Non-goals for compiler v1

Compiler v1 should not:

- make a separate LLM call per turn
- perform semantic freeform ranking from raw athlete wording
- rewrite memory summaries during prompt assembly
- invent a new interpretation of facts

Compiler v1 is a selector, not a reasoner.

### Compiler v1 inputs

Compiler v1 should consume:

- active durable memory
- continuity
- current reply mode or planning mode if available

Compiler v1 should not depend on parsing the current athlete email for meaning beyond already-available routing/context signals.

### Compiler v1 outputs

Compiler v1 should emit a bounded prompt-ready memory payload with explicit sections.

Suggested output shape:

```json
{
  "priority_facts": [],
  "structure_facts": [],
  "preference_facts": [],
  "context_facts": [],
  "continuity_focus": "..."
}
```

### Compiler v1 budget

The prompt budget should be section-based, not one flat global competition.

Suggested v1 compiled prompt caps:

- include all active goals treated as compiler-core
- include all active constraints treated as compiler-core
- include up to 4 `schedule_anchors`
- include up to 2 `preferences`
- include up to 1 `context_note`
- always include continuity

Important safety rule:

- if the number of active goals and active constraints is larger than expected, the compiler should still include them all and trim lower-priority sections first

That means the first trim targets are:

- context notes
- preferences
- lower-priority schedule anchors

The compiler should never trim active goals or active constraints in v1.

### Compiler v1 selection logic

Within each section, selection should be deterministic and conservative.

Suggested ordering:

1. compiler priority derived from section + subtype + active state
2. `last_confirmed_at`: newer before older
3. `updated_at`: newer before older
4. stable tie-breaker such as `memory_id`

Important design rule:

- compiler priority should be derived, not stored as a general `salience` field
- v1 should not persist `core | supporting` on each fact by default
- if two facts in the same broad section need different treatment, model that through a narrow structural subtype, not a free-floating salience label
- subtypes should be section-specific, not one shared cross-section enum

Examples:

- a `goal` may have subtype `primary` or `secondary`
- a `schedule_anchor` may have subtype `hard_blocker`, `recurring_anchor`, or `soft_preference`
- a `constraint` may have subtype `injury`, `logistics`, or `soft_limit`

These subtypes are more specific and less drift-prone than storing generic salience directly.

### Compiler v1 and summarization

The phrase “summarize related truths when necessary” should not apply to compiler v1.

For v1:

- compiler selects existing objects only
- compiler does not synthesize new summary text at read time

Any summarization or merging should happen in write-time compaction, not prompt assembly.

This is an intentional safety choice.

### Compiler v1 failure model

Compiler omission is still a risk, so the design should constrain where omission can happen.

Desired omission boundary:

- omission is allowed only for lower-priority context
- omission is not allowed for active goals
- omission is not allowed for active constraints

This is safer than the current model because:

- omitted facts remain persisted
- compiler mistakes are recoverable on later turns
- omission no longer destroys durable truth

### Compiler v1 testing requirements

Compiler tests should verify:

- all active goals are always present
- all active constraints are always present
- lower-priority sections are trimmed before goals and constraints
- stable ordering is deterministic

This compiler should be easy to reason about and easy to unit test.

## Proposed Data Model Direction

This proposal does not require the exact schema below, but it suggests the intended shape.

Each active memory object should look conceptually like:

```json
{
  "memory_id": "stable-id",
  "section": "goal | constraint | schedule_anchor | preference | context",
  "subtype": "section-specific enum",
  "summary": "compact normalized coaching truth",
  "status": "active | retired",
  "supersedes": ["older-id"],
  "created_at": 1710700000,
  "updated_at": 1710700100,
  "last_confirmed_at": 1710700100
}
```

Conceptual subtype sets:

- `goal`
  - `primary`
  - `secondary`

- `constraint`
  - `injury`
  - `logistics`
  - `soft_limit`
  - `other`

- `schedule_anchor`
  - `hard_blocker`
  - `recurring_anchor`
  - `soft_preference`
  - `other`

- `preference`
  - `communication`
  - `planning_style`
  - `other`

- `context`
  - `equipment`
  - `life_context`
  - `other`

Important note:

- compiler priority should be derived from:
  - section
  - subtype
  - active state
  - timestamps
- the system should avoid storing a generic `salience` field unless real implementation pressure proves that a persisted override is necessary
- `supersedes` should be treated as lineage metadata for deterministic mutation and retired-bucket management, not as a general retrieval feature
- section/subtype combinations should be validated deterministically; invalid combinations must be rejected at validation time rather than tolerated

## Proposed Pipeline

### Step 1: Candidate generation

The LLM still proposes memory operations from the turn.

This remains useful because semantic interpretation is hard and should stay model-driven.

### Step 2: Deterministic application

Code still applies operations deterministically:

- create
- update
- confirm
- retire
- supersede

This preserves identity and keeps mutation auditable.

### Step 3: Section-level reconciliation

After applying operations:

- resolve conflicts within each section
- ensure active items do not contradict each other
- collapse obviously redundant items where identity is already known

### Step 4: Bounded consolidation and retired-cap enforcement

If an active or retired section exceeds its target size:

- run a narrow consolidation step only for clearly redundant or strictly subsumed objects
- preserve truth while reducing object count
- only drop retired items that are truly obsolete or not worth preserving

This step should not be a general “rewrite this section into fewer objects” pass.

Allowed consolidation cases should be narrow and explicit:

- merge facts with the same durable identity
- merge facts with the same canonical key
- merge facts where one explicitly supersedes or strictly subsumes the other

The operation should be explicit and reviewable:

- input: a small candidate set of already-linked objects
- output: one surviving object plus explicit source-to-target supersession mapping

Important safety rules:

- consolidation must never silently drop a fact
- every source object must either:
  - remain unchanged
  - or point to a surviving replacement object explicitly
- if the mapping cannot be made explicit, consolidation is invalid
- section-wide freeform rewriting is out of scope
- consolidation should be deterministic in v1 unless a later implementation proves a narrower assisted mode is necessary

### Step 5: Prompt compilation

On each coaching turn:

- compile a small prompt-ready memory object from active durable memory and continuity
- include all active goals and constraints
- include bounded lower-priority sections by deterministic section order
- do not synthesize new summary text in the compiler

## Why This Solves Bug 19 Better

Under this design:

- a true primary goal does not need to survive a 7-item active-fact eviction contest
- a later-added schedule detail does not delete a durable goal from storage
- the coach can still receive a compact prompt because retrieval is bounded separately
- conflict resolution still removes outdated truths from the active set

In short:

- bug `19` stops being a “medium facts evict important truths” problem
- it becomes a retrieval and consolidation problem, which is the correct abstraction

## Options Considered

## Option A: Keep current architecture, improve eviction logic

Description:

- keep flat active fact store
- tweak eviction ordering
- maybe add more retention labels or protections

### Pros

- smallest code change
- lowest implementation surface area
- preserves current mental model

### Cons

- does not solve persistence-budget coupling
- still allows destructive forgetting
- likely leads to more heuristics and special cases
- bug `19` may recur in new forms
- brittle under long-horizon conversations

### Recommendation

Not recommended as the main fix.

## Option B: Keep flat store, increase fact limit

Description:

- raise `MAX_ACTIVE_FACTS`
- reduce eviction pressure without changing architecture

### Pros

- very easy to implement
- probably reduces immediate bug frequency

### Cons

- does not solve the design problem
- memory still couples storage and prompt budget
- prompt size will eventually grow again
- conflict handling remains flat and under-modeled

### Recommendation

Useful only as a temporary mitigation, not as the real solution.

## Option C: Two-layer memory with bounded durable store and prompt compiler

Description:

- separate durable persistence from prompt-time selection
- keep contradiction resolution explicit
- use narrow consolidation instead of flat destructive eviction

### Pros

- directly matches the product requirements
- durable truths stop competing with prompt budget
- boundedness is maintained through structure and consolidation
- conflict handling becomes cleaner
- easier to reason about long-horizon retention
- better foundation for multilingual and variable athlete language

### Cons

- requires schema and pipeline changes
- introduces a new compiler/consolidation layer
- requires careful testing so consolidation does not distort facts or silently omit lineage

### Recommendation

Recommended.

This is the cleanest and most durable design direction.

## Open Design Questions

These need resolution before implementation:

1. What should the durable store size targets be per section?
2. Should consolidation be fully deterministic, LLM-assisted, or hybrid?
Current recommendation: deterministic and very narrow in v1.
3. Should prompt compilation be one generic selector or task-specific by consumer?

Question explicitly closed for v1:

- keep atomic facts only
- do not introduce higher-level section summaries as first-class active memory objects

Reason:

- compiler v1 does no summarization
- consolidation is intentionally narrow
- first-class summary objects would expand scope and reintroduce ambiguity too early

## Implementation Stance

This proposal assumes a hard cut, not a compatibility-preserving migration.

Reason:

- there are no live users to preserve
- the new design is simpler if it is treated as the new source of truth directly
- avoiding dual-write or compatibility layers reduces code complexity and testing burden

Implementation guidance:

- replace the current flat active-fact persistence model rather than layering the new design beside it
- redesign prompt assembly against the new persisted structure directly
- avoid transitional compatibility fields unless implementation reveals a truly blocking need

## Testing Implications

The test strategy should change along with the design.

Instead of primarily testing “which fact gets evicted,” the system should test:

- important truths remain present in durable storage across long conversations
- contradictory truths do not remain active together
- prompt compiler returns a compact but sufficient coaching context
- consolidation reduces size without deleting active truth or silently dropping lineage
- retrieval still surfaces the right goal/constraint/schedule anchors for planning

## Recommendation Summary

Bug `19` should be fixed by redesigning memory around two separate concerns:

- durable truth retention
- bounded prompt-time retrieval

The current flat 7-fact active set is too lossy for reliable coaching memory.

The recommended direction is:

- keep a bounded but larger structured durable store
- resolve conflicts explicitly through retire/supersede semantics
- compile a small prompt memory object on each turn
- use narrow explicit consolidation instead of destructive eviction for still-true facts

This is a cleaner solution than adding more deterministic phrase-based logic, and it better satisfies the actual product requirements.

## Backlog Coverage

This section checks whether the proposed design would address memory-related defects beyond bug `19`.

### Defects this design would address directly

These are cases where the current architecture is itself a major cause of the bug.

#### Bug 19. Durable facts evicted under budget pressure despite high coaching value

Directly addressed.

Reason:

- the proposed design removes the destructive flat-budget eviction model
- durable truths no longer compete directly with prompt budget
- important truths can remain in durable storage while prompt-time selection stays bounded

#### Bug 2. Long-horizon memory drops core training backbone when medium-value details accumulate

Directly addressed in principle.

Reason:

- this is the same architectural class as bug `19`
- a bounded durable store plus prompt compiler is a cleaner version of the retention strategy this bug already needed
- consolidation is a better answer than keeping everything in one small active pool

#### Bug 6. Primary swim goal can disappear from final durable memory

Directly addressed in principle.

Reason:

- if durable goals are no longer stored in a tiny destructively-evicted active list, they should not disappear simply because later details arrive

#### Bug 8. New recurring strength session can fail to promote into durable memory

Partially to directly addressed, depending on root cause.

Reason:

- if the issue is primarily retention under pressure, the new design helps directly
- if the issue is candidate-generation failure to create the memory item at all, the new design helps less and candidate generation still needs work

#### Bug 11. New recurring ski-erg session can fail to become durable memory

Same assessment as bug `8`.

#### Bug 29. Coach loses track of previously provided information in longer conversations

Partially to directly addressed.

Reason:

- the proposal explicitly separates durable truth retention from turn-level prompt packing
- it also implies stronger treatment of bounded short-lived context and better prompt compilation
- this should help prevent re-asking for already-provided dates, protocols, and locked decisions

Important caveat:

- bug `29` also depends on continuity design, not just durable memory design
- if the missing information is tactical, thread-local, or time-scoped rather than truly durable, it likely belongs in a better continuity layer in parallel with this redesign

### Defects this design would help, but not fully solve by itself

These are cases where the proposed architecture reduces pressure or creates a better foundation, but another mechanism still matters.

#### Bug 10. Basketball season-goal memory is not normalized robustly enough

Partially addressed.

Reason:

- the new design would reduce the chance that paraphrased goals get lost due to destructive eviction
- but it does not by itself solve identity stability across paraphrases
- some form of semantic identity resolution or better candidate/update behavior is still needed

#### Bugs 3, 4, 5, 7, 9, 12, 18. Stale schedule or constraint facts remain active after explicit replacement

Partially addressed.

Reason:

- the proposed design makes contradiction handling more first-class with supersede/retire semantics
- that is a better foundation for preventing conflicting active truths
- but the actual detection of replacement still depends on the memory refresh interpretation step

So:

- the new architecture helps prevent contradictory active memory from lingering
- it does not eliminate the need for strong replacement detection

#### Bug 17. Reversal backstop can be satisfied by an unrelated targeted update

Only indirectly helped.

Reason:

- this is primarily a reversal-detection and retry-validation bug in the refresh pipeline
- a better durable store does not remove the need for correct reversal detection

#### Bug 20. Continuity bootstrap treats past event dates as active event horizons

Only indirectly helped.

Reason:

- the two-layer design makes it easier to keep durable memory and continuity conceptually separate
- but this specific bug is a continuity bootstrap logic bug, not a memory-retention architecture bug

#### Bug 21. Profile time_availability schema too narrow

Only indirectly helped.

Reason:

- if profile and memory are reconsidered together, richer structured scheduling data may fit better in the system overall
- but the actual issue is a profile schema gap, not durable memory retention

#### Bug 22. Strategist reopens resolved conversational topics

Partially addressed.

Reason:

- a stronger continuity-plus-memory model should reduce accidental reopening of settled topics
- but strategist behavior and prompt discipline still matter

#### Bug 26. Coach repeats already-established constraints verbatim every turn

Partially addressed.

Reason:

- a prompt compiler that selects and compresses memory can reduce overexposure of unchanged constraints
- but the strategist and writer still need instruction not to restate every known fact every turn

### Defects this design does not meaningfully solve

These are outside the core memory-retention problem.

#### Bug 13. Achilles rebuild flow can prescribe tempo too early

Not directly addressed.

Reason:

- this is primarily a coaching reasoning / safety policy issue

#### Bug 14. Coaching reply contradicts its own “fully aerobic” guidance

Not directly addressed.

Reason:

- this is primarily an intra-reply planning/writing consistency issue

#### Bugs 23, 24, 27, 28, 30, 31, 32, 33

Not directly addressed.

Reason:

- these are mainly writer, strategist, simulation, or judging problems

## Backlog Coverage Summary

The proposed design is not just a fix for bug `19`.

It would also improve the system’s foundation for at least these memory/continuity problems:

- bug `2`
- bug `6`
- bug `8`
- bug `10`
- bug `11`
- bug `19`
- bug `22`
- bug `26`
- bug `29`

It would also provide a cleaner structural basis for contradiction-related bugs:

- bug `3`
- bug `4`
- bug `5`
- bug `7`
- bug `9`
- bug `12`
- bug `18`

But it is not a universal fix.

It does not replace the need for:

- strong replacement detection
- better continuity handling
- better strategist behavior
- better writer obedience
- better profile schemas where information belongs in profile rather than memory
