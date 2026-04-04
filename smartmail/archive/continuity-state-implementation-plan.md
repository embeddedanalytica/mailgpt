# Continuity State Implementation Plan - DONE

We are adding a `continuity_state` system so the app can preserve coaching continuity across turns. The doctrine-backed LLM remains the decision-maker for coaching meaning. Deterministic code bootstraps, validates, persists, and derives structured continuity state.

`continuity_state` lives as a top-level attribute on `coach_profiles`, not inside the plan object and not in a new table.

---

## Phase 1: Contract, persistence, bootstrap

**Goal:** Define the data contract, add persistence, and deterministic bootstrap. No LLM changes, no orchestration changes.

### Stored fields

| Field | Type | Notes |
|-------|------|-------|
| `goal_horizon_type` | enum: `event`, `general_fitness`, `performance_block`, `return_to_training` | |
| `current_phase` | str | Canonical phase label from rule engine |
| `current_block_focus` | enum: `initial_assessment`, `rebuild_consistency`, `controlled_load_progression`, `maintain_fitness`, `maintain_through_constraints`, `event_specific_build`, `peak_for_event`, `taper_for_event`, `return_safely`, `recovery_deload` | Bounded. `peak_for_event` and `taper_for_event` are distinct — doctrine treats peak and taper as separate coaching intents. |
| `block_started_at` | ISO date | |
| `goal_event_date` | ISO date or None | Only when relevant |
| `last_transition_reason` | str | Short description |
| `last_transition_date` | ISO date | |

### Derived at runtime, not stored

- `weeks_in_current_block` — from `block_started_at` and today
- `weeks_until_event` — from `goal_event_date` and today, None when no event

### Files to create

- **`continuity_state_contract.py`** — Frozen dataclass with the 7 stored fields. Enum definitions for `goal_horizon_type` and `block_focus`. `from_dict()` / `to_dict()` round-trip with validation. Pure derivation helpers: `weeks_in_current_block(today)`, `weeks_until_event(today)`. Raises a typed error on validation failure.

- **`continuity_bootstrap.py`** — Pure function: `bootstrap_continuity_state(profile, rule_engine_phase, today_date) -> ContinuityState`. Logic:
  - `goal_horizon_type`: `event` if a valid event date exists in profile, else `general_fitness`
  - `current_phase`: from rule engine's derived phase
  - `current_block_focus`: `return_safely` when rule engine phase is `return_to_training` or injury/setback context is evident; otherwise `initial_assessment`
  - `block_started_at`: today
  - `goal_event_date`: from profile if present
  - `last_transition_reason`: `"bootstrap_initial_state"`
  - `last_transition_date`: today

### Files to modify

- **`dynamodb_models.py`** — Add `get_continuity_state(athlete_id) -> Optional[Dict]` and `update_continuity_state(athlete_id, state_dict) -> bool`. Follow the existing pattern used by `get_continuity_summary()` and `merge_coach_profile_fields()`. Reads/writes `continuity_state` as a top-level attribute on `coach_profiles`.

### Backward-compatibility read behavior (critical for safe rollout)

- Missing `continuity_state` attribute on read → return None (caller bootstraps)
- Partial or invalid stored object → log warning, return None (caller bootstraps)
- No data migration required for existing athletes — bootstrap happens on next coaching turn

### Tests

- Validation round-trip for all valid enum combinations
- Rejection of invalid enums, malformed dates, missing required fields
- `weeks_in_current_block` derivation math (same week, multi-week, edge cases)
- `weeks_until_event` derivation (with and without event date)
- Bootstrap for event athlete (has event date → `event` horizon, `initial_assessment` focus)
- Bootstrap for general-fitness athlete (no event date → `general_fitness`, `initial_assessment`)
- Bootstrap for return-from-injury athlete (rule engine phase is `return_to_training` → `return_safely` focus)
- Persistence read/write round-trip on `coach_profiles`
- Missing attribute returns None
- Corrupt attribute returns None with log warning

---

## Phase 2: Deterministic updater + guardrails

**Goal:** Build the pure function that applies a continuity recommendation to produce the next state. No LLM changes, no orchestration changes. Testable with synthetic recommendations.

### Files to create

- **`continuity_recommendation_contract.py`** — Dataclass for the recommendation the LLM will emit. Fields:
  - `recommended_goal_horizon_type` (enum) — **required always, including on `keep`**
  - `recommended_phase` (str) — **required always, including on `keep`**
  - `recommended_block_focus` (enum) — **required always, including on `keep`**
  - `recommended_transition_action`: `keep`, `focus_shift`, `phase_shift`, `reset_block`
  - `recommended_transition_reason` (str)
  - `recommended_goal_event_date` (ISO date or None) — optional in the payload contract, because some athletes do not have an event goal

  All non-event fields are required in the schema. `recommended_goal_event_date` remains optional so non-event athletes are not forced to emit a meaningless placeholder. The updater decides which fields to act on based on `recommended_transition_action`. Validates enums, dates, required fields. This is the contract between coaching_reasoning output and the deterministic updater.

- **`continuity_updater.py`** — Pure function: `apply_continuity_recommendation(prior_state, recommendation, today_date) -> ContinuityState`. Semantics:
  - `keep`: preserve `block_started_at`, phase, focus, and all other fields unchanged. **Ignore** `recommended_phase`, `recommended_block_focus`, and `recommended_goal_horizon_type` even if they differ from prior state. Only `recommended_goal_event_date` may update the stored `goal_event_date`.
  - `focus_shift`: update `current_block_focus`, reset `block_started_at` to today, set `last_transition_reason` and `last_transition_date`.
  - `phase_shift`: update `current_phase` and optionally `current_block_focus`, reset `block_started_at` to today, set transition metadata.
  - `reset_block`: move into a new recovery/rebuild intent, reset `block_started_at` to today, set transition metadata.

  **Guardrails (narrow, not intelligence):**
  - Reject invalid enums / malformed dates → fall back to prior state
  - Reject impossible event-date transitions (e.g., event date in the past)
  - Veto `phase_shift` if `weeks_in_current_block < 2` **unless** the transition reason indicates injury, setback, return-from-break, or new event context
  - On veto: keep prior state, log the reason

  **Fallback when recommendation is missing or invalid:** retain prior state entirely. Never destroy continuity unnecessarily.

### Tests

- `keep` preserves `block_started_at` and all fields
- `keep` ignores differing `recommended_phase` and `recommended_block_focus`
- `keep` with updated event date only changes `goal_event_date`
- `focus_shift` resets `block_started_at` to today
- `phase_shift` resets `block_started_at` to today
- `reset_block` moves to recovery/rebuild focus and resets `block_started_at`
- `general_fitness` → `event` transition (horizon type change + event date)
- Event date update on existing event athlete
- Guardrail veto: `phase_shift` with `weeks_in_current_block` = 1, no injury → rejected, prior state retained
- Guardrail exception: `phase_shift` with `weeks_in_current_block` = 1, reason = injury → allowed
- Invalid recommendation → prior state retained, no error raised
- None recommendation → prior state retained

---

## Phase 3: Coaching reasoning emits `continuity_recommendation`

**Goal:** Extend the coaching_reasoning skill so the LLM sees current continuity context and emits a recommendation alongside the existing coaching directive.

### Scope definition

A "relevant coaching turn" is any turn that reaches the doctrine-backed coaching_reasoning skill in normal coaching flow. This excludes registration, verification, off-topic routing, rate-limited/no-op paths, and any turn that exits before coaching reasoning is invoked. On each such turn, coaching_reasoning emits a `continuity_recommendation`, with `keep` as the normal default.

### Files to modify

- **`skills/coaching_reasoning/schema.py`** — Add `continuity_recommendation` as an optional object in the JSON schema alongside the existing directive fields. Sub-schema matches the recommendation contract from Phase 2 (all 6 fields required within the object). Optional at the top level so that a missing recommendation is handled gracefully rather than failing validation.

- **`skills/coaching_reasoning/validator.py`** — The current `validate_coaching_directive()` rejects any fields not in `_ALL_FIELDS` (raises `CoachingReasoningError("Unexpected fields: ...")`). This validator **must** be updated to:
  1. Add `continuity_recommendation` to the set of allowed top-level fields (but not to `_REQUIRED_FIELDS` — it remains optional).
  2. When `continuity_recommendation` is present, validate its sub-fields against the recommendation contract enums and types.
  3. When absent, pass through without error.
  4. The normalized return dict should include `continuity_recommendation` when present, exclude it when absent.
  Without this change, the LLM output will be rejected before the runner ever sees it.

- **Coaching reasoning prompt** (wire into the existing prompt assembly path — do not assume function names are stable). Add:
  - A `## Continuity context` section in the system prompt showing the current continuity state: `goal_horizon_type`, `current_phase`, `current_block_focus`, `weeks_in_current_block`, `weeks_until_event` (when present), `last_transition_reason`.
  - Instructions for emitting the recommendation. Emphasize: `keep` is the normal default. Only recommend `focus_shift`, `phase_shift`, or `reset_block` when the athlete's situation genuinely warrants a transition. Provide the bounded enum list for `block_focus` so the LLM picks from it.
  - All non-event recommendation fields are required (including on `keep`). `recommended_goal_event_date` should be emitted when relevant and may be null or omitted for non-event athletes depending on the schema contract.

- **`skills/coaching_reasoning/runner.py`** — Extract `continuity_recommendation` from validated LLM output. Return it alongside `directive` and `doctrine_files_loaded`. If the recommendation is missing from LLM output, return None for that field (not an error).

### Tests

- Schema accepts valid recommendation alongside directive
- Schema accepts directive with no recommendation (backward compat)
- Schema rejects invalid enum values in recommendation
- Validator accepts payload with valid `continuity_recommendation` (no `Unexpected fields` error)
- Validator accepts payload without `continuity_recommendation` (backward compat)
- Validator rejects `continuity_recommendation` with invalid enum values or missing sub-fields
- Runner returns recommendation when present
- Runner returns None for recommendation when absent

---

## Phase 4: Wire into orchestration

**Goal:** Connect phases 1-3 in the main coaching flow. This is the integration point.

### Sequencing (critical — response generation must see the updated state)

1. Load `continuity_state` from `coach_profiles` (or bootstrap if missing/invalid)
2. Derive runtime fields (`weeks_in_current_block`, `weeks_until_event`)
3. Pass **current** continuity context into coaching reasoning (so the LLM sees where the athlete is *now*)
4. Coaching reasoning returns `coaching_directive` + `continuity_recommendation`
5. Run `apply_continuity_recommendation(current_state, recommendation, today)` → `next_continuity_state`
6. Derive runtime fields on `next_continuity_state`
7. Pass **next** continuity context into response generation (so the reply reflects the coaching decision just made)
8. Persist `next_continuity_state` to `coach_profiles`

Step 7 is the key sequencing requirement: the response writer must see the *post-decision* state, not the pre-turn state. If coaching reasoning decides "we are now in a return block," the reply must be written from that perspective.

### Files to modify

- **`coaching.py` — `_generate_llm_reply()`** — This is the main integration point. Insert continuity load/bootstrap between memory context load and response brief build. After coaching reasoning returns, run the updater. Thread `next_continuity_state`-derived context into response generation input. Persist after response generation input is assembled.
- **`coaching.py` — `_generate_llm_reply()`** — This is the main integration point. Insert continuity load/bootstrap between memory context load and response brief build. After coaching reasoning returns, run the updater. Thread `next_continuity_state`-derived context into response generation input. Persist after response generation input is assembled.
  - Note: for coaching reasoning, `continuity_context` may be passed as orchestration-provided prompt enrichment rather than embedded directly inside the assembled `ResponseBrief`. The key requirement is that coaching reasoning sees the current continuity context before making its recommendation.

- **`response_generation_assembly.py`** — Modify the response-generation assembly path so `continuity_context` can be carried forward as a bounded dict: `goal_horizon_type`, `current_phase`, `current_block_focus`, `weeks_in_current_block`, `weeks_until_event`, `last_transition_reason`. Wire into the existing assembly path — do not create a parallel assembly function.
  - For coaching reasoning specifically, this context may be supplied as a separate orchestration argument instead of being embedded in the `ResponseBrief` object, as long as the strategist prompt receives the same bounded continuity fields.

- **`response_generation_contract.py`** — The current `ResponseBrief` and `WriterBrief` contracts are strict. Both `validate_response_brief()` and `validate_writer_brief()` reject unknown top-level fields. These **must** be updated:
  1. **`ResponseBrief`**: Add `continuity_context` as an optional top-level field. Update `_REQUIRED_TOP_LEVEL_FIELDS` or add it to an allowed-optional set so `validate_response_brief()` does not reject it. Update the `from_dict()` and `to_dict()` methods on the dataclass. When absent, default to None.
  2. **`WriterBrief`**: Add `continuity_context` as an optional top-level field. Update `_WRITER_BRIEF_TOP_LEVEL_FIELDS` or add it to an allowed-optional set so `validate_writer_brief()` does not reject it. Update `from_dict()` and `to_dict()`. When absent, default to None.
  Without these changes, adding `continuity_context` to the assembly path will cause `ResponseGenerationContractError` at runtime.

### Missing coaching reasoning handling

If coaching reasoning fails (LLM error, fallback path, feature flag off):
- Continuity state remains unchanged
- No mutation is applied
- Persistence may be skipped if the state is identical to what was loaded

### Tests

- First coaching turn for new athlete: bootstrap happens, continuity_state is persisted
- Second turn with no change: `keep` recommendation, `block_started_at` unchanged
- Turn where coaching reasoning recommends `focus_shift`: persisted state reflects the shift
- Response generation input contains continuity context from `next_continuity_state`, not the pre-turn state
- Missing coaching reasoning result: continuity state remains unchanged, no write occurs
- Continuity context fields are present in the response brief
- `ResponseBrief.from_dict()` accepts payload with `continuity_context` present
- `ResponseBrief.from_dict()` accepts payload with `continuity_context` absent (backward compat)
- `WriterBrief.from_dict()` accepts payload with `continuity_context` present
- `WriterBrief.from_dict()` accepts payload with `continuity_context` absent (backward compat)

---

## Phase 5: Thread continuity into response generation prompt

**Goal:** The response writer uses continuity context to write coherent replies that reference the training arc.

### Files to modify

- **Response generation prompt** — Add a small section presenting the continuity context. Example framing: "The athlete is in week N of a [block_focus] block. [If event: N weeks until their event on DATE.]" The writer does not decide continuity — it uses the structured context to write coherently.

- **Response generation assembly path** — The `continuity_context` dict was threaded through the contracts in Phase 4. This phase ensures the prompt template renders it. Handle the case where continuity context is None (backward compat / fallback path) — omit the section rather than rendering empty fields.

### Tests

- Response generation prompt includes continuity section when context is present
- Response generation prompt omits section when context is None
- Rendered prompt correctly formats `weeks_in_current_block` and `weeks_until_event`

---

## Phase 6: Thread continuity into planner input

**Goal:** Give the planner visibility into the multi-week arc so weekly skeleton decisions are informed by block context.

### Architectural constraint

In the current flow, the planner runs inside `run_rule_engine_for_week()` (via `rule_engine_orchestrator.py`), which executes *before* `_generate_llm_reply()` where coaching reasoning lives. Therefore, the planner consumes **previously persisted** continuity state, not the same-turn updated state. This is correct behavior — planner shapes the weekly skeleton from existing context, coaching reasoning then makes the continuity judgment for the current turn. Do not reorder to create a circular dependency between planner and coaching reasoning.

### Files to modify

- **`skills/planner/validator.py`** — Two changes required:
  1. **`build_planner_brief()`** — Add optional `continuity_context` fields to the planner brief. Same bounded dict as Phase 4. When `continuity_state` is absent (not yet bootstrapped, or first turn), omit these fields.
  2. **Planner brief validator/schema** — Explicitly update the validation contract to allow the new `continuity_context` fields. Both the builder and the validator must be updated — updating only the builder will cause validation failures.

- **Planner prompt** — Add context about current block focus and progression. The planner does not decide transitions — it shapes this week's sessions knowing where they sit in the arc.

- **`rule_engine_orchestrator.py`** or **`inbound_rule_router.py`** — Load previously persisted `continuity_state` and pass it through to planner brief construction. If absent, planner brief is built without it.

### Tests

- Planner brief includes continuity context when state exists
- Planner brief works correctly when `continuity_state` is absent (backward compat)
- Planner brief validation accepts the new continuity fields
- Planner brief validation still passes when continuity fields are omitted

---

## Phase summary

| Phase | What | LLM changes | Persistence | Independently testable |
|-------|------|-------------|-------------|----------------------|
| 1 | Contract + persistence + bootstrap | None | New attribute on coach_profiles | Yes — pure data layer |
| 2 | Updater + guardrails | None | None | Yes — pure functions with synthetic input |
| 3 | Coaching reasoning extension | Schema + prompt | None | Yes — skill unit tests |
| 4 | Orchestration wiring | None | Read/write in flow | Needs 1-3 |
| 5 | Response generation threading | Prompt section | None | Needs 4 |
| 6 | Planner threading | Prompt section | None | Needs 4 |

Phases 1-3 are independently testable with no orchestration changes. Phase 4 is the integration point. Phases 5-6 are incremental prompt improvements that can each be verified independently.

## Key architectural rule

Deterministic code owns continuity memory, timestamps, validation, and derivation. The doctrine-backed LLM owns the nuanced coaching decision about what the athlete's situation means. Deterministic logic should never silently replace that judgment with a simplistic rule except for bounded safety guardrails and bootstrap defaults.
