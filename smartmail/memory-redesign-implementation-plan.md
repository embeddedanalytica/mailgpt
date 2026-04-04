# Memory Redesign Implementation Plan

Date: 2026-04-03
Design doc: `bug19-memory-design-proposal.md`

## What This Plan Is

This is an implementation plan for replacing the current flat 7-fact memory system with a sectioned durable memory store and deterministic prompt compiler. It is written for an LLM coding agent that has not seen the design discussion.

Read `bug19-memory-design-proposal.md` before starting any PR. It contains the full design rationale, boundary rules, compiler contract, and data model direction.

## Why This Change Exists

The current memory system stores durable athlete facts in a flat list of 7. When a new fact arrives and the list is full, the system destructively evicts the lowest-priority fact. That evicted fact is gone forever.

This means the coach can permanently forget important truths (primary goals, injury constraints) just because less important facts accumulated. That is bug 19, and it also causes bugs 2, 6, 8, 11.

The fix separates two concerns that are currently coupled:

- **Storage**: how many facts the system can retain (should be larger, sectioned, non-destructive)
- **Retrieval**: how many facts appear in the coaching prompt (should be bounded, deterministic)

## Architecture Overview

### Current system

```
LLM emits candidates → reducer validates + applies → flat active list (max 7) → response generation reads all 7
```

Storage budget = prompt budget. Eviction deletes facts permanently.

### New system

```
LLM emits candidates → reducer validates + applies → sectioned store (active + retired per section) → compiler selects bounded subset → response generation reads compiled output
```

Storage budget >> prompt budget. Active facts are never destructively evicted. Retired facts are bounded per section.

## Key Files Being Changed

These are the files that exist today and their role. Every PR should reference this map.

| File | Current Role | Change |
|---|---|---|
| `sam-app/email_service/athlete_memory_contract.py` | `DurableFact` dataclass, `normalize_fact_key()`, validation, constants | Replace with new `MemoryFact` model, section/subtype enums, new validation |
| `sam-app/email_service/athlete_memory_reducer.py` | `apply_candidate_refresh()`, budget eviction, supersede cleanup | Rewrite for sectioned store, retired bucket routing, section caps |
| `sam-app/email_service/skills/memory/unified/prompt.py` | LLM system prompt for candidate generation | Update to emit `section`/`subtype` instead of `fact_type`/`importance` |
| `sam-app/email_service/skills/memory/unified/schema.py` | JSON schema for LLM output | Update candidate schema for new fields |
| `sam-app/email_service/skills/memory/unified/validator.py` | Validates LLM candidate output | Update validation for sections, subtypes, new rules |
| `sam-app/email_service/skills/memory/unified/runner.py` | Orchestrates LLM call, reversal backstop | Update to work with new candidate format |
| `sam-app/email_service/coaching_memory.py` | Post-reply memory refresh orchestration | Update to persist sectioned memory |
| `sam-app/email_service/response_generation_assembly.py` | `_shape_memory_salience_v4()`, `build_response_brief()` | Replace salience shaping with compiler output consumption |
| `sam-app/email_service/dynamodb_models.py` | `get_memory_notes()`, `replace_memory()` | Update to read/write sectioned memory shape |

### New files to create

| File | Role |
|---|---|
| `sam-app/email_service/memory_compiler.py` | Deterministic prompt compiler |
| `sam-app/email_service/test_memory_compiler.py` | Compiler tests |

### Test files to update

| File | What it tests |
|---|---|
| `sam-app/email_service/test_athlete_memory_contract.py` | Data model, validation |
| `sam-app/email_service/test_athlete_memory_reducer.py` | Reducer logic |
| `sam-app/email_service/test_coaching_memory.py` | Orchestration |
| `sam-app/email_service/test_response_generation_assembly.py` | Response brief assembly |
| `sam-app/email_service/test_memory_group1_regressions.py` | Bug regression tests |

## Important Context for the Implementing Agent

### `supersedes_fact_keys` vs `supersedes` — two different fields

These are two distinct fields at different layers. Do not confuse them.

| Field | Where it lives | Contains | Set by |
|---|---|---|---|
| `supersedes_fact_keys` | LLM candidate op (skill schema) | List of canonical `fact_key` strings (e.g., `["schedule_anchor:tuesday-swim"]`) | LLM proposes, validator checks |
| `supersedes` | Stored `MemoryFact` field | List of `memory_id` UUIDs (e.g., `["a3f7c2d1-..."]`) | Reducer resolves from `supersedes_fact_keys` at write time |

Flow: LLM emits `supersedes_fact_keys` (semantic, canonical keys) → reducer looks up matching active facts by canonical key → stores resolved `memory_id` list in `MemoryFact.supersedes` (stable identity).

The LLM never sees or emits `memory_id` values in `supersedes_fact_keys`. The stored `MemoryFact` never contains canonical keys in `supersedes`.

### This is a hard cut, not a migration

There are no live users. Do not write backward-compatible code, dual-write paths, or migration logic. Replace the old structures directly.

### The current `fact_type` maps to the new `section`

| Old `fact_type` | New `section` |
|---|---|
| `goal` | `goal` |
| `constraint` | `constraint` |
| `schedule` | `schedule_anchor` |
| `preference` | `preference` |
| `other` | `context` |

### The current `importance` field is removed

It is replaced by section-specific `subtype` fields that the compiler uses to derive priority. There is no stored `salience` or `importance` field.

### Subtypes are section-specific

Each section has its own subtype enum. Do not create one shared enum.

| Section | Subtypes |
|---|---|
| `goal` | `primary`, `secondary` |
| `constraint` | `injury`, `logistics`, `soft_limit`, `other` |
| `schedule_anchor` | `hard_blocker`, `recurring_anchor`, `soft_preference`, `other` |
| `preference` | `communication`, `planning_style`, `other` |
| `context` | `equipment`, `life_context`, `other` |

Invalid section/subtype combinations must be rejected at validation time.

### `ContinuitySummary` is unchanged

The continuity model (`summary`, `last_recommendation`, `open_loops`, `updated_at`) is not part of this redesign. Keep it as-is.

### The reversal backstop in `runner.py` should be preserved

The current `_has_reversal_cues()` and retry logic should continue to work, adapted for the new candidate format.

### DynamoDB storage shape changes

The `memory_notes` field on `coach_profiles` currently holds a flat list of fact dicts. After this change it should hold the new sectioned structure. The `replace_memory()` and `get_memory_notes()` functions in `dynamodb_models.py` need to serialize/deserialize the new shape.

Suggested persisted shape:

```json
{
  "goals": {
    "active": [...],
    "retired": [...]
  },
  "constraints": {
    "active": [...],
    "retired": [...]
  },
  "schedule_anchors": {
    "active": [...],
    "retired": [...]
  },
  "preferences": {
    "active": [...],
    "retired": [...]
  },
  "context_notes": {
    "active": [...],
    "retired": [...]
  }
}
```

### Existing test patterns

Tests use `unittest`. Test files live alongside source files in `sam-app/email_service/`. Tests should subclass `unittest.TestCase`. Run individual test files with `python3 -m unittest -v sam-app/email_service/test_<name>.py`. Run the full memory-related test suite with `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`. See `sam-app/email_service/CLAUDE.md` for test conventions including mock patching guidance.

### CLAUDE.md files must be updated

After implementation, update these guides to reflect the new system:

- `sam-app/email_service/skills/memory/CLAUDE.md`
- `sam-app/email_service/CLAUDE.md` (module map section)

---

## PR 1: New Data Model (Additive)

### Goal

Add the new `MemoryFact` model, section/subtype enums, and validation functions in a **new file** alongside the existing code. Do not modify any existing file. The old system continues to work unchanged.

### What to build

Create `sam-app/email_service/sectioned_memory_contract.py`:

1. **Define section enum** with values: `goal`, `constraint`, `schedule_anchor`, `preference`, `context`.

2. **Define subtype enums per section** (see table in context section above). Use a mapping dict from section to allowed subtypes, not one flat enum.

3. **Define status enum** with values: `active`, `retired`.

4. **Define retirement reason enum** with values: `replaced_by_newer_active_fact`, `completed`, `resolved`, `no_longer_relevant`.

5. **Define the `MemoryFact` frozen dataclass** with fields:
   - `memory_id`: str (UUID, stable)
   - `section`: str (from section enum)
   - `subtype`: str (section-specific)
   - `fact_key`: str (canonical key, derived from `normalize_fact_key(section, raw_key)` at creation time, immutable after creation)
   - `summary`: str
   - `status`: str (`active` or `retired`)
   - `supersedes`: list[str] (list of memory_ids this fact replaced; can be empty)
   - `retirement_reason`: optional str (only set when status is `retired`)
   - `created_at`: int (unix epoch)
   - `updated_at`: int (unix epoch)
   - `last_confirmed_at`: int (unix epoch)
   - `retired_at`: optional int (unix epoch, only set when status is `retired`)

6. **Define a `normalize_fact_key(section, raw_key)` function** in this module. The canonical key format should be `"{section}:{slug}"`. This is the same logic as the existing `normalize_fact_key` in `athlete_memory_contract.py` but parameterized on `section` instead of `fact_type`.

7. **Define section size caps as constants:**
   - Active caps: `goals: 4`, `constraints: 8`, `schedule_anchors: 8`, `preferences: 4`, `context_notes: 4`
   - Retired caps: `5` per section (uniform)

8. **Define a helper to create an empty sectioned memory dict** with all sections present and empty active/retired lists.

9. **Write validation functions:**
   - `validate_memory_fact(fact_dict)` — validates a single fact dict, checks section/subtype validity, required fields, status consistency (retired facts must have `retirement_reason` and `retired_at`)
   - `validate_sectioned_memory(memory_dict)` — validates the full sectioned structure, checks per-section caps, no duplicate `memory_id`, no duplicate canonical key within active facts of a section
   - Keep validation strict: invalid section/subtype combinations rejected, not coerced

### What to test

Create `sam-app/email_service/test_sectioned_memory_contract.py`:

- `MemoryFact` creation with valid fields
- Rejection of invalid section values
- Rejection of invalid subtype for a given section (e.g., `hard_blocker` on a `goal`)
- Rejection of retired fact without `retirement_reason` or `retired_at`
- `normalize_fact_key()` with new section field
- `validate_sectioned_memory()` accepts valid structures
- `validate_sectioned_memory()` rejects duplicate `memory_id` across sections
- `validate_sectioned_memory()` rejects duplicate canonical key in active facts
- Section cap constants are defined and accessible
- Empty sectioned memory helper produces valid structure

### Definition of done

- New file `sectioned_memory_contract.py` exists with all types and validation
- New test file passes: `python3 -m unittest -v sam-app/email_service/test_sectioned_memory_contract.py`
- **No existing files modified. Old code and old tests still pass unchanged.**
- Full test suite passes: `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`

---

## PR 2: New Reducer (Additive)

### Goal

Build the new sectioned memory reducer in a **new file** alongside the existing reducer. Do not modify `athlete_memory_reducer.py`. The old system continues to work unchanged.

### Dependencies

PR 1 must be merged first.

### What to build

Create `sam-app/email_service/sectioned_memory_reducer.py`:

1. **Main function**: `apply_sectioned_refresh(validated_llm_output: dict, current_memory: dict, now_epoch: int) -> dict`
   - Input: validated candidates (new format with `section`/`subtype`), current sectioned memory, timestamp
   - Output: `{"sectioned_memory": {...}, "continuity_summary": {...}}`

2. **Process candidates against sectioned memory.** Each candidate specifies a `section`. Route operations to the correct section bucket.

3. **Implement candidate actions on the new model:**

   - **`upsert` without `target_id` (new fact):**
     - Validate section and subtype
     - Generate new `memory_id` (UUID)
     - Derive canonical key via `normalize_fact_key(section, raw_key)`
     - Check for canonical key conflicts within the section's active list
     - Set `status: active`, all timestamps to `now_epoch`
     - If `supersedes_fact_keys` is provided: resolve each canonical key to the matching active fact's `memory_id`, retire those facts (see retire logic), and store the resolved `memory_id` list in the new fact's `supersedes` field
     - Add to section's active list
   
   - **`upsert` with `target_id` (update existing):**
     - Find fact by `memory_id` in the correct section's active list
     - Update `summary`, `updated_at`, `last_confirmed_at`
     - Optionally update `subtype` (must be valid for the section)
     - `section` and canonical key are immutable
   
   - **`confirm`:**
     - Find fact by `memory_id`
     - Update `last_confirmed_at` only
   
   - **`retire`:**
     - Find fact by `memory_id` in the section's active list
     - Port the existing fuzzy matching fallback (`_resolve_retire_target_id` from the old reducer) for robustness
     - Set `status: retired`, `retired_at: now_epoch`
     - Set `retirement_reason` based on context (if superseded by another candidate in the same batch → `replaced_by_newer_active_fact`; otherwise use the reason from the candidate or default to `no_longer_relevant`)
     - Route to retired bucket or drop (see routing rules below)

4. **Implement retired fact routing.** After each retirement, decide destination:
   - **Drop** if: the fact is low-value (`context` section with subtype `other`, or `preference` with subtype `other`) and not recently superseded by a current active fact
   - **Retired bucket** otherwise, if section's retired cap allows
   - If retired bucket is over cap after insertion: evict using the retired-retention sort key

5. **Implement retired-cap enforcement sort key** (ascending, weakest first):
   - `explains_active_truth`: 1 if any active fact in the section has this fact's `memory_id` in its `supersedes` list, else 0
   - `retire_reason_priority`: `no_longer_relevant: 0`, `resolved: 1`, `completed: 2`, `replaced_by_newer_active_fact: 3`
   - `retired_at`: older is weaker (ascending)
   - `last_confirmed_at`: older is weaker (ascending)
   - `memory_id`: stable tie-breaker (ascending)

6. **Implement active section cap enforcement via reject-at-cap.** When processing a new-create upsert, if the target section's active list is already at cap:
   - **If the upsert supersedes an existing active fact** (i.e., the candidate includes `supersedes_fact_keys` that resolve to one or more active facts in the section): allow it. The net active count stays the same or decreases.
   - **If the upsert does not supersede any existing active fact**: reject the new upsert. Log a warning with the rejected candidate details. Do not store the fact.
   - This policy is deterministic and bounded: existing active truths are never evicted, but new facts cannot overflow the section either.
   - The rejected fact is not lost permanently — the LLM will likely propose it again on the next turn, and by then a retirement may have freed a slot.
   - **Processing order matters**: within a single candidate batch, process all retirements and superseding upserts before non-superseding upserts, so that slots freed by retirements are available for new admissions in the same batch.
   - Update upserts (with `target_id`) and confirms are always allowed regardless of cap — they modify existing facts, not add new ones.

7. **Implement canonical key uniqueness backstop** within each section's active list.

8. **Implement supersede cleanup** (removing references to retired facts from summaries/continuity). Port the logic from the old reducer.

### What to test

Create `sam-app/email_service/test_sectioned_memory_reducer.py`:

- New fact upsert lands in correct section's active list
- Update upsert modifies existing fact in correct section
- Confirm updates only `last_confirmed_at`
- Retire moves fact from active to retired bucket with correct metadata
- Retire via `supersedes_fact_keys` on the replacing upsert sets `retirement_reason: replaced_by_newer_active_fact`
- Retired fact routing: low-value facts are dropped, meaningful facts are kept
- Retired cap enforcement: oldest/weakest retired facts evicted first when over cap
- `explains_active_truth` gives retention boost to retired facts referenced by active `supersedes`
- New upsert rejected when section is at active cap and upsert does not supersede
- New upsert allowed when section is at cap but upsert includes `supersedes_fact_keys` resolving to an existing active fact (net count stays same or decreases)
- Retirements and superseding upserts processed before non-superseding upserts within a batch
- Update upserts and confirms always allowed regardless of cap
- Canonical key uniqueness within section
- Fuzzy retire target resolution works
- Supersede cleanup removes retired fact references from summaries

### Definition of done

- New file `sectioned_memory_reducer.py` exists and is fully tested
- New test file passes: `python3 -m unittest -v sam-app/email_service/test_sectioned_memory_reducer.py`
- **No existing files modified. Old reducer and old tests still pass unchanged.**
- Full test suite passes: `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`

---

## PR 3: Prompt Compiler (Additive)

### Goal

Create the deterministic prompt compiler in a **new file**. This is an entirely new module with no existing counterpart to modify.

### Dependencies

PR 1 must be merged first.

### What to build

Create `sam-app/email_service/memory_compiler.py`:

1. **Main function**: `compile_prompt_memory(sectioned_memory: dict, continuity: Optional[dict]) -> dict`

2. **Output shape:**
   ```python
   {
       "priority_facts": [],      # all active goals + all active constraints
       "structure_facts": [],     # bounded active schedule_anchors
       "preference_facts": [],    # bounded active preferences
       "context_facts": [],       # bounded active context_notes
       "continuity_focus": "..."  # continuity.summary or None
   }
   ```

3. **Compiler budget (constants):**
   - Goals: include ALL active (no cap at compiler level)
   - Constraints: include ALL active (no cap at compiler level)
   - Schedule anchors: up to 4
   - Preferences: up to 2
   - Context notes: up to 1

4. **Safety rule:** If total active goals + constraints exceeds the combined budget of lower-priority sections, the compiler still includes all goals and constraints. It trims context_notes first, then preferences, then schedule_anchors. Goals and constraints are never trimmed.

5. **Selection logic within each bounded section** (deterministic sort, highest priority first):
   - Derive compiler priority from subtype:
     - `schedule_anchor`: `hard_blocker: 0` > `recurring_anchor: 1` > `soft_preference: 2` > `other: 3`
     - `preference`: `communication: 0` > `planning_style: 1` > `other: 2`
     - `context`: `life_context: 0` > `equipment: 1` > `other: 2`
   - Then `last_confirmed_at` descending (newer first)
   - Then `updated_at` descending (newer first)
   - Then `memory_id` ascending (stable tie-breaker)

6. **Active-only rule:** The compiler reads only `status: active` facts. It ignores all retired facts.

7. **Output format:** Each fact in the output lists should be the dict representation of the `MemoryFact`, not just the summary string. The response generation layer can extract what it needs.

### What to test

Create `sam-app/email_service/test_memory_compiler.py`:

- All active goals always present in `priority_facts` regardless of count
- All active constraints always present in `priority_facts` regardless of count
- Schedule anchors bounded to 4, sorted by subtype priority then recency
- Preferences bounded to 2
- Context notes bounded to 1
- When goals + constraints are large, lower sections are trimmed (not goals/constraints)
- Empty sections produce empty lists (not errors)
- Retired facts are excluded
- Continuity is passed through
- Deterministic output: same input always produces same output
- Sorting is correct: `hard_blocker` schedule anchor before `soft_preference`

### Definition of done

- `compile_prompt_memory()` exists and is fully tested
- Compiler is purely deterministic: no LLM call, no randomness
- All compiler tests pass: `python3 -m unittest -v sam-app/email_service/test_memory_compiler.py`
- Module has no dependency on response generation or coaching_memory (it is a pure function)
- **No existing files modified. Full test suite passes.**

---

## PR 4: New Memory Skill (Additive)

### Goal

Create the new LLM-facing memory skill that emits candidates with `section` and `subtype` in a **new skill package** alongside the existing one. Do not modify `skills/memory/unified/`.

### Dependencies

PR 1 must be merged first.

### What to build

Create `sam-app/email_service/skills/memory/sectioned/` with standard skill structure:

#### `skills/memory/sectioned/__init__.py`

Empty init.

#### `skills/memory/sectioned/prompt.py`

Write the system prompt to teach the LLM:

- **Sections** replace `fact_type`: `goal`, `constraint`, `schedule_anchor`, `preference`, `context`
- **Subtypes** replace `importance`: section-specific (see subtype table in context section)
- **Actions remain**: `upsert`, `confirm`, `retire`
- **`supersedes_fact_keys` field**: list of canonical `fact_key` strings being replaced. This stays as canonical keys in the LLM contract (not `memory_id`) because:
  - Canonical keys are semantically meaningful — the LLM can reason about `"schedule_anchor:tuesday-evening-swim"` but not `"a3f7c2d1-..."`
  - The current system already uses `supersedes_fact_keys` successfully
  - The reducer resolves canonical keys to `memory_id` internally before storing on the `MemoryFact.supersedes` field
  - This keeps the LLM interface semantic and the storage layer identity-stable
- **Key behavioral rules to preserve in the prompt:**
  - Silence preserves: facts not mentioned remain unchanged
  - Replacement is retirement: when athlete switches patterns, old fact must be retired AND new fact upserted
  - Retire requires explicit evidence
  - Rule engine state can only confirm
  - Section/subtype assignment guidance: explain what belongs in each section and how to choose subtypes

#### `skills/memory/sectioned/schema.py`

Define the JSON schema and typed dicts:

- `CandidateOp`:
  - `action`: `upsert`, `confirm`, `retire`
  - `section`: section enum value (required for new upsert)
  - `subtype`: section-specific (required for new upsert)
  - `target_id`: existing `memory_id` (required for update/confirm/retire)
  - `fact_key`: raw key, system will canonicalize (required for new upsert)
  - `summary`: fact text
  - `supersedes_fact_keys`: list of canonical `fact_key` strings being replaced (reducer resolves to `memory_id` before storage)
  - `evidence_source`, `evidence_strength`: same as current

- `CandidateMemoryRefreshInput`:
  - `current_memory`: sectioned structure (so LLM sees the section grouping)
  - Plus interaction context fields (same as current)

- `CandidateMemoryRefreshOutput`:
  - `candidates`: list of new `CandidateOp`
  - `continuity`: unchanged

#### `skills/memory/sectioned/validator.py`

Write `validate_sectioned_candidate_response()`:

- Validate `section` is a valid section enum value
- Validate `subtype` is valid for the given `section`
- New upsert (no `target_id`): requires `section`, `subtype`, `fact_key`, `summary`
- Update upsert (with `target_id`): `section` and `fact_key` are immutable (forbidden). `subtype` and `summary` can be updated.
- Confirm: unchanged
- Retire: `evidence_strength: explicit` still required
- Rule engine restrictions: still can only confirm
- Cross-candidate checks: no duplicate `target_id`, no duplicate canonical key in new-create upserts within the same section

#### `skills/memory/sectioned/runner.py`

Write `run_sectioned_memory_refresh()`:

- Build user payload from sectioned memory + continuity + interaction context
- Call LLM via `execute_json_schema()`
- Validate via `validate_sectioned_candidate_response()`
- Port reversal backstop logic from `skills/memory/unified/runner.py`: `_has_reversal_cues()` and retry logic, adapted for new section names (`schedule_anchor` and `constraint` instead of `schedule` and `constraint`)
- Port supersede cleanup logic (same canonical-key-based approach as current system)

#### `skills/memory/sectioned/errors.py`

Define `SectionedMemoryRefreshError` (or reuse the existing `MemoryRefreshError` from the unified package via import).

### What to test

Create `sam-app/email_service/skills/memory/sectioned/test_sectioned_skill.py` (or `sam-app/email_service/test_sectioned_memory_skill.py` to match existing test location patterns):

- Valid candidate with correct section/subtype accepted
- Invalid section rejected
- Invalid subtype for section rejected
- New upsert requires section, subtype, fact_key, summary
- Update upsert forbids section and fact_key
- Retire still requires explicit evidence
- Rule engine state still restricted to confirm only
- Reversal backstop works with new section names

### Definition of done

- New skill package `skills/memory/sectioned/` exists with prompt, schema, validator, runner
- All new skill tests pass
- **No existing files modified. Old skill and old tests still pass unchanged.**
- Full test suite passes: `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`

---

## PR 5: Cutover — Swap All Call Sites

### Goal

This is the single PR that switches the live pipeline from the old flat memory system to the new sectioned memory system. It modifies existing files to rewire call sites, updates DynamoDB accessors, and removes the old code paths. **After this PR, the old system is dead.**

This is the largest and riskiest PR. It should be reviewed carefully.

### Dependencies

PRs 1-4 must all be merged first. All new modules must exist and have passing tests.

### What to change

#### `dynamodb_models.py`

1. **Update `get_memory_notes()`** (rename to `get_sectioned_memory()`):
   - Read `memory_notes` field from `coach_profiles`
   - Deserialize into the sectioned memory structure
   - Validate via `validate_sectioned_memory()` from `sectioned_memory_contract`
   - Return empty sectioned structure on missing or invalid data (graceful handling for fresh profiles)

2. **Update `replace_memory()`:**
   - Accept sectioned memory dict instead of flat list
   - Serialize and write to `memory_notes` field on `coach_profiles`
   - Validate before writing

3. **Update `get_memory_context_for_response_generation()`:**
   - Return sectioned memory instead of flat notes list

#### `coaching_memory.py`

1. **Update `maybe_post_reply_memory_refresh()`:**
   - Fetch current memory via `get_sectioned_memory()`
   - Call `run_sectioned_memory_refresh()` from the new skill package instead of `run_candidate_memory_refresh()` from the old one
   - Call `apply_sectioned_refresh()` from the new reducer instead of `apply_candidate_refresh()`
   - Persist via updated `replace_memory()`

2. **Update `build_memory_refresh_context()`:**
   - Format sectioned memory for the new skill's input shape

3. **Keep `should_attempt_memory_refresh()` unchanged.**

#### `response_generation_assembly.py`

1. **Remove `_shape_memory_salience_v4()`.**

2. **Update `build_response_brief()`:**
   - Call `compile_prompt_memory(sectioned_memory, continuity)` from the compiler
   - The compiler returns full `MemoryFact` dicts in each list. The `memory_payload` on `ResponseBrief` must extract **summary strings only** to match what the response generation skill prompt expects.
   - The exact `memory_payload` shape passed into `ResponseBrief` should be:
     ```python
     {
         "memory_available": bool,
         "continuity_summary": dict or None,  # unchanged from current
         "priority_facts": ["summary string", ...],      # from compiled goals + constraints
         "structure_facts": ["summary string", ...],      # from compiled schedule_anchors
         "preference_facts": ["summary string", ...],     # from compiled preferences (new key)
         "context_facts": ["summary string", ...],        # from compiled context_notes
         "continuity_focus": "string" or None,            # from continuity.summary
     }
     ```
   - This preserves the existing contract with the response generation skill prompt: `priority_facts`, `structure_facts`, and `context_facts` remain lists of plain strings.
   - The new `preference_facts` key is added because preferences are now a separate compiler section rather than grouped into `context_facts`. If the response generation prompt does not yet reference `preference_facts`, add it alongside the existing keys.
   - `memory_available` is true if any of the fact lists or `continuity_focus` is non-empty.
   - Conditional inclusion: only add each key to the payload if the list is non-empty (matches current behavior).

3. **Update `detect_contradicted_facts()`:**
   - Build the `all_memory_summaries` list from the compiled summary strings (same as today, just sourced from compiler output instead of `_shape_memory_salience_v4`)

4. **The response generation skill prompt** (`skills/response_generation/`) should already work because the memory payload keys and value types are the same (lists of strings). Verify and update if needed, particularly to handle the new `preference_facts` key.

#### `coaching.py` (or wherever response generation is called)

- Pass sectioned memory to `build_response_brief()`

#### Old files to remove

- `sam-app/email_service/athlete_memory_contract.py` — replaced by `sectioned_memory_contract.py`. **Exception:** if `ContinuitySummary` is defined here and still used, either move it to `sectioned_memory_contract.py` or keep the file with only `ContinuitySummary`. Check imports before deleting.
- `sam-app/email_service/athlete_memory_reducer.py` — replaced by `sectioned_memory_reducer.py`
- `sam-app/email_service/skills/memory/unified/` — replaced by `skills/memory/sectioned/`

#### Old test files to remove or rewrite

- `test_athlete_memory_contract.py` — replaced by `test_sectioned_memory_contract.py`
- `test_athlete_memory_reducer.py` — replaced by `test_sectioned_memory_reducer.py`

#### Test files to update

- `test_coaching_memory.py` — update to use new function signatures, sectioned memory shapes, new skill/reducer imports
- `test_response_generation_assembly.py` — update to use compiler output, remove `_shape_memory_salience_v4` tests
- `test_memory_group1_regressions.py` — update to use new data model and reducer

### What to test

Every test in the repo must pass after this PR. Specifically:

- `test_sectioned_memory_contract.py` — still passes (no changes to new contract)
- `test_sectioned_memory_reducer.py` — still passes (no changes to new reducer)
- `test_memory_compiler.py` — still passes (no changes to compiler)
- New/updated skill tests — pass with new skill package
- `test_coaching_memory.py` — updated tests pass with new orchestration
- `test_response_generation_assembly.py` — updated tests pass with compiler integration. Specifically verify:
  - `memory_payload` on `ResponseBrief` contains `priority_facts`, `structure_facts`, `preference_facts`, `context_facts` as lists of summary strings (not full dicts)
  - `memory_available` is correctly derived
  - `detect_contradicted_facts` receives flat summary strings
  - Empty sections are omitted from payload (conditional inclusion preserved)
- `test_memory_group1_regressions.py` — updated regression tests pass

### Definition of done

- All call sites use new modules (sectioned contract, sectioned reducer, sectioned skill, compiler)
- DynamoDB reads/writes sectioned memory
- Response generation consumes compiler output
- Old flat memory code is removed (contract, reducer, unified skill)
- **Full test suite passes: `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`**
- No import errors, no dead code referencing old types

---

## PR 6: Documentation and Regression Tests

### Goal

Update documentation and add targeted regression tests for the bugs this redesign addresses.

### Dependencies

PR 5 must be merged.

### What to do

1. **Update CLAUDE.md files:**
   - `sam-app/email_service/skills/memory/CLAUDE.md`: describe sectioned memory model, compiler, new candidate format, retired bucket lifecycle, section caps, reject-at-cap policy
   - `sam-app/email_service/CLAUDE.md`: update module map to mention compiler, sectioned memory contract, sectioned reducer, new skill package

2. **Add regression tests** in `test_memory_group1_regressions.py` (or a new `test_memory_redesign_regressions.py`):
   - **Bug 19 regression**: Create scenario where many facts exist across sections (more than old 7-fact limit). Verify no active fact is destructively evicted. Verify compiler produces bounded output with all goals and constraints present.
   - **Bug 6 regression**: Create primary swim goal + many schedule facts filling the section. Verify goal survives in storage and in compiled output.
   - **Bug 2 regression**: Simulate long-horizon fact accumulation across multiple reducer passes. Verify core training backbone (goals, constraints) survives every pass.
   - **Reject-at-cap regression**: Fill a section to cap, then attempt a new upsert without supersession. Verify it is rejected. Then attempt one with supersession. Verify it succeeds.

3. **Verify full test suite passes.**

### Definition of done

- CLAUDE.md files reflect new system
- Regression tests for bugs 19, 6, 2 pass
- Full test suite passes: `python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service`

---

## Implementation Order Summary

```
PR 1: New Data Model       [no dependencies]        — additive, new file only
PR 2: New Reducer          [depends on PR 1]         — additive, new file only
PR 3: Prompt Compiler      [depends on PR 1]         — additive, new file only
PR 4: New Memory Skill     [depends on PR 1]         — additive, new file only
PR 5: Cutover              [depends on PRs 1-4]      — modifies existing files, removes old code
PR 6: Docs + Regressions   [depends on PR 5]         — documentation and regression tests
```

PRs 2, 3, and 4 can be developed in parallel after PR 1 merges. PR 5 is the single atomic cutover. PR 6 is documentation and regression coverage.

**Critical invariant: every PR leaves the full test suite green.** PRs 1-4 are purely additive — they create new files and tests without touching existing code. PR 5 is the only PR that modifies existing files, and it does so as one atomic cutover.

## What This Plan Does Not Cover

- Continuity redesign (separate concern, not part of this epic)
- LLM-assisted compaction (intentionally deferred)
- Warm/cold historical tiers (intentionally deferred)
- Replacement detection improvements (bugs 3-5, 7, 9, 12, 18 — needs memory refresh prompt work, not architecture)
- Writer/strategist behavior fixes (bugs 13, 14, 22, 23-28, 30-33)
- Profile schema changes (bug 21)
