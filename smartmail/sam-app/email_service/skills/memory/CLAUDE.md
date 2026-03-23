# memory/ — Memory Subsystem (AM2)

## Architecture

Candidate-operation model: LLM emits ops (`upsert`, `confirm`, `retire`) targeting existing facts by `memory_note_id`. Deterministic reducer applies ops to current state. Silence preserves — facts not mentioned remain unchanged.

## Key Files

| File | Role |
|---|---|
| `unified/prompt.py` | Candidate-operation memory refresh prompt |
| `unified/schema.py` | Candidate-op JSON schema |
| `unified/validator.py` | Candidate validator (per-action rules, evidence authority) |
| `unified/runner.py` | Skill runner with reversal backstop |
| `unified/errors.py` | Error types |
| `../../coaching_memory.py` | Post-reply memory refresh orchestration |
| `../../athlete_memory_contract.py` | DurableFact contract, normalize_fact_key, validate_memory_notes |
| `../../athlete_memory_reducer.py` | Deterministic reducer: apply candidates, budget enforcement |

## Design Rules

- **ID-based targeting**: Operations on existing facts require `target_id` (memory_note_id)
- **Immutable identity**: `fact_type` and `fact_key` cannot change after creation
- **Evidence authority**: `rule_engine_state` can only `confirm`, never create or retire
- **Unknown target_id = batch rejection**: Not silent skip
- **Retire = delete**: No tombstone, no audit trail
- **Budget**: MAX_ACTIVE_FACTS=7, evict medium-importance first by oldest `last_confirmed_at`
- **Importance enforcement**: goal/constraint facts forced to "high"
- **Reversal backstop**: If athlete message has reversal cues but no retire/update emitted, retry once
