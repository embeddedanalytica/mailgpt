# Athlete Memory Implementation Epic

## Context and Scope Boundaries
- The goal is lightweight, useful memory for coaching continuity, not a generalized knowledge system.
- Memory remains LLM-assisted; this epic does not introduce deterministic fact extraction or semantic retrieval.
- Stories should stay atomic. If implementation reveals a story is too large, split it before building.
- YAGNI applies: prefer the smallest concrete persistence and orchestration model that supports coaching quality.

---

## Epic AM1 — Athlete Memory and Conversation Continuity

### Goal
Enable the system to remember athlete-specific context and recent coaching continuity so future replies feel personalized, coherent, and operationally safe.

### Memory Model
- `memory_notes[]`: durable or semi-durable athlete context that may matter across future interactions. Each note carries a lightweight `memory_note_id` so the LLM can refer to existing notes consistently across refreshes.
- `continuity_summary`: a compact rolling summary of the most recent coaching context and follow-up state.
- Both `memory_notes` and `continuity_summary` are persisted on the athlete's `coach_profiles` record.

Example `memory_note`:

~~~json
{
  "memory_note_id": 2,
  "category": "schedule",
  "summary": "Can usually train only before 7am on weekdays",
  "active": true,
  "importance": "medium",
  "last_confirmed_at": "2026-03-08T00:00:00Z"
}
~~~

`category` is a short string label describing the type of durable context. Preferred categories are `injury`, `schedule`, `equipment`, `life_context`, `communication_preference`, and `other`. The LLM may introduce a new category when none of the preferred categories fit cleanly. New categories should be concise, lowercase, and reusable across future notes.

One note should represent one durable fact. Short-lived thread context belongs in `continuity_summary`, not `memory_notes`.

Example `continuity_summary`:

~~~json
{
  "summary": "Athlete is rebuilding after a week of missed training due to travel. Coach recommended two easy runs and one short strength session this week.",
  "last_recommendation": "Keep the week light and re-establish consistency before adding intensity.",
  "open_loops": [
    "Check whether travel schedule is over",
    "Confirm energy levels by next check-in"
  ],
  "updated_at": "2026-03-08T00:00:00Z"
}
~~~

`continuity_summary` holds short-lived conversational state and is overwritten on refresh. It should not be used to store durable athlete facts that belong in `memory_notes`.
Malformed `continuity_summary` payloads are rejected at validation time, and the previously persisted continuity state remains unchanged.

### Stories

#### Story AM1.1 — Athlete Memory Note Contract
As a developer, I need a concrete contract for athlete memory notes so memory persistence and retrieval stay simple and consistent.

Story DoD:
- [ ] A canonical `memory_note` shape is defined with only the required fields for current use.
- [ ] The contract includes a lightweight integer `memory_note_id` on each persisted note.
- [ ] The contract supports LLM-extensible note categorization, concise human-readable summaries, active/inactive state, and recency metadata.
- [ ] Validation rejects malformed notes or unknown required structure at the persistence boundary.
- [ ] Contract tests cover required fields, `memory_note_id`, and valid/invalid category and importance values.

#### Story AM1.2 — Persist Athlete Memory Notes Per Athlete
As a coaching system, I need athlete memory notes persisted per athlete so important context survives across threads and sessions.

Story DoD:
- [ ] Multiple `memory_notes` can be stored for a single athlete.
- [ ] `memory_notes` are stored on the athlete's `coach_profiles` record.
- [ ] Notes persist independently of any single email thread or conversation instance.
- [ ] Existing notes keep their `memory_note_id` when updated or deactivated.
- [ ] New notes can be added with the next available lightweight note ID without rewriting the full athlete record unnecessarily.

#### Story AM1.3 — Continuity Summary Contract and Storage
As a coaching system, I need one rolling continuity summary per athlete so the latest coaching context is always available.

Story DoD:
- [ ] A canonical `continuity_summary` shape is defined for current coaching context, recent recommendation, and open follow-up loops.
- [ ] Each athlete can have at most one active continuity summary record.
- [ ] `continuity_summary` is stored on the athlete's `coach_profiles` record.
- [ ] Continuity summaries persist across conversations and are overwritten intentionally when refreshed.

#### Story AM1.4 — Retrieval of Memory Context for Response Generation
As a response generator, I need athlete memory context loaded alongside the rest of the coaching context so replies can reference relevant history.

Response generation receives all active `high` importance memory notes plus up to `3` additional active notes ordered by `last_confirmed_at` descending.

Story DoD:
- [ ] Response-generation context includes memory notes according to the explicit lightweight selection rule above.
- [ ] Response-generation context includes the current `continuity_summary` when present.
- [ ] Retrieval works across thread boundaries and does not assume the current thread contains the full history.
- [ ] Missing memory artifacts degrade gracefully without blocking normal response generation.

#### Story AM1.5 — LLM-Driven Memory Refresh After Meaningful Interactions
As a coaching system, I need memory artifacts refreshed after meaningful exchanges so memory evolves with the athlete.

Memory refresh runs only when the interaction introduces or changes durable athlete context, produces a coaching recommendation, or changes coaching state. Greetings, acknowledgements, and clarification-only exchanges do not trigger a refresh unless they add new durable context.

The memory-refresh LLM returns the full revised `memory_notes` list and the refreshed `continuity_summary` in one payload.

Story DoD:
- [ ] A post-interaction memory-refresh step runs only for interactions that meet the explicit trigger boundary above.
- [ ] The LLM receives prior `memory_notes`, prior `continuity_summary`, and the latest interaction context.
- [ ] Existing notes are returned to the LLM with their `memory_note_id`s so the model can revise or deactivate the right note.
- [ ] The LLM returns the full revised `memory_notes` list and refreshed `continuity_summary` in one pass.
- [ ] The write path replaces persisted memory artifacts only after a valid full-payload update is returned.
- [ ] Invalid refresh payloads are rejected and the previously persisted memory state remains unchanged.

#### Story AM1.6 — Memory Size and Quality Guardrails
As a platform maintainer, I need memory guardrails so athlete memory stays useful and does not bloat prompt context.

Story DoD:
- [ ] The system enforces an upper bound of `5` active memory notes per athlete.
- [ ] Notes and continuity summaries are constrained to concise, prompt-safe lengths.
- [ ] Stale or superseded notes are deactivated during refresh instead of accumulating forever.
- [ ] Duplicate or conflicting note IDs within one athlete's memory set are rejected at validation time.
- [ ] Guardrails keep total memory context small enough for routine response generation.

#### Story AM1.7 — Prompting and Behavioral Guidance for Memory Updates
As a system designer, I need explicit prompting guidance for memory creation and refresh so the LLM updates memory consistently.

Story DoD:
- [ ] The memory-update prompt distinguishes durable athlete context from short-lived conversational continuity.
- [ ] Prompt instructions discourage speculative facts and duplicate notes.
- [ ] Prompt instructions require existing notes to keep their `memory_note_id` and new notes to use the next lightweight integer ID.
- [ ] Prompt instructions prefer updating or deactivating existing notes over creating redundant new ones.
- [ ] Prompt instructions direct short-lived context into `continuity_summary` instead of `memory_notes`.
- [ ] Tests or fixtures cover representative outputs for injury, schedule, equipment, and life-context cases.

### Epic AM1 DoD
- [ ] Athlete-specific memory survives across threads and conversations.
- [ ] Each persisted memory note carries a stable lightweight `memory_note_id` that remains unchanged across updates and deactivation.
- [ ] Memory refresh runs only when the explicit trigger boundary is met and does not run for greetings, acknowledgements, or clarification-only exchanges unless they add new durable context.
- [ ] Response generation receives bounded memory context: all active `high` importance notes plus up to `3` additional recent active notes.
- [ ] At most `5` memory notes remain active after a refresh.
- [ ] Stale or superseded notes can be deactivated so active memory stays relevant and compact over time.
- [ ] Memory updates remain LLM-assisted but bounded by simple contracts, prompt instructions, and validation.
- [ ] Invalid memory-refresh payloads fail closed and do not overwrite the previously persisted memory state.
- [ ] `continuity_summary` and `memory_notes` are used for different purposes: short-lived conversational state vs durable athlete context.
- [ ] No semantic search, embeddings, or rule-based extraction pipelines are introduced.

---

## Non-Goals
- Embeddings or semantic search.
- Complex fact extraction pipelines.
- Deterministic rule-based memory inference.
- Advanced ranking or retrieval algorithms.
- Rich historical audit trails beyond what is needed for current coaching continuity.

---

## Expected Result
After Epic AM1 is implemented, the system should be able to:
- remember athlete-specific context that matters for coaching,
- carry forward recent coaching continuity between conversations,
- personalize responses without depending on thread-local history, and
- evolve memory over time without introducing heavyweight memory infrastructure.
