# memory/ — Memory Subsystem (AM2)

## Architecture

**Sectioned store (current):** Durable facts live in `sectioned_memory_contract` buckets (`goals`, `constraints`, `schedule_anchors`, `preferences`, `context_notes`), each with `active` / `retired` lists. The LLM emits sectioned candidate ops; `sectioned_memory_reducer.apply_sectioned_refresh` applies them deterministically. Post-reply refresh: `skills/memory/sectioned/runner.py` → `coaching_memory.maybe_post_reply_memory_refresh`.

Shared helpers used by the sectioned runner (`prune_resolved_open_loops`, continuity cleanup, etc.) live in `refresh_helpers.py`. Shared errors: `errors.py` (`MemoryRefreshError`, `MemoryRefreshPromptError`).

## Key Files

| File | Role |
|---|---|
| `sectioned/prompt.py`, `schema.py`, `validator.py`, `runner.py`, `errors.py` | Sectioned candidate refresh skill |
| `refresh_helpers.py` | Continuity + text cleanup shared with sectioned runner |
| `errors.py` | `MemoryRefreshError` for refresh + persistence failures |
| `../../sectioned_memory_contract.py` | Buckets, `MemoryFact`, `ContinuitySummary`, validation |
| `../../sectioned_memory_reducer.py` | `apply_sectioned_refresh` |
| `../../memory_compiler.py` | Deterministic `compile_prompt_memory` for response generation |
| `../../coaching_memory.py` | Post-reply orchestration (`run_sectioned_memory_refresh` → `apply_sectioned_refresh` → `replace_memory`) |

## Design Rules

- **ID-based targeting**: `target_id` references `memory_id` (UUID string) for updates/retires
- **Section + subtype**: New creates specify `section` and `subtype` per `SUBTYPES_BY_SECTION`
- **Evidence authority**: `rule_engine_state` can only `confirm`, never create or retire
- **Per-bucket caps**: See `ACTIVE_CAP_BY_BUCKET` in `sectioned_memory_contract.py`
- **Continuity**: `ContinuitySummary` in `sectioned_memory_contract`; max `MAX_OPEN_LOOPS` open loops
