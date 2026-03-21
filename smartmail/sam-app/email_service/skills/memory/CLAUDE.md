# memory/ — Memory Subsystem

## Current State

Old sub-skills (`eligibility/`, `long_term/`, `short_term/`, `refresh/`, `router/`) have been deleted.
Replaced by a single `unified/` skill.

## Key Files

| File | Role |
|---|---|
| `unified/prompt.py` | Memory refresh prompt |
| `unified/schema.py` | Output schema |
| `unified/validator.py` | Output validation |
| `unified/runner.py` | Skill runner |
| `unified/errors.py` | Error types |
| `../../coaching_memory.py` | Pre/post reply memory refresh orchestration |
| `../../athlete_memory_contract.py` | Memory note + continuity summary contracts |
| `../../athlete_memory_reducer.py` | Memory note trimming/reduction |

## Known Bugs (see `bug-backlog.md`)

- Long-horizon memory loses core training backbone over time
- Stale scheduling rules are not retired when replaced
- Primary goals can disappear from durable memory

The old 7-note bounded model and refresh trigger logic are not working — consider reconsidering both.
