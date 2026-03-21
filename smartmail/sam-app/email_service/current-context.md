SmartMail — Current Session Context
Last updated: 2026-03-19

## What Has Been Built

### AM3 Three-Tier Memory Model
Replaced the old 7-note bounded model. Three tiers stored in `coach_profiles` DynamoDB:

- **Backbone** (4 fixed slots, always present): `primary_goal`, `weekly_structure`, `hard_constraints`, `training_preferences`
- **Context notes** (max 4 free-form): recent signals that don't fit backbone
- **Continuity** (ephemeral, next 1–2 turns): `summary`, `last_recommendation`, `open_loops` (max 3)

Key files: `athlete_memory_contract.py`, `athlete_memory_reducer.py`, `coaching_memory.py`, `skills/memory/unified/`

### inbound_body Fix (Previous Session — Done)
Root cause: `delivery_context` in `ResponseBrief` had `inbound_subject` but NOT `inbound_body`. LLM fell back on stale `open_loops` from the previous turn.

Fix applied (362 tests passing):
- `response_generation_contract.py`: Added `inbound_body` to `_DELIVERY_CONTEXT_FIELDS`
- `response_generation_assembly.py`: Added `inbound_body` param to `build_response_brief()`, forwarded with 4000-char truncation
- `coaching.py`: Passes `inbound_body=inbound_body` to `build_response_brief()`
- `skills/response_generation/prompt.py`: Instructs LLM to read `inbound_body` first; demoted `continuity_focus` from "primary cue" to "context from previous exchange"
- `test_response_generation_skill.py`: Updated prompt assertion

## Current State — After E2E Run 1773818718-e5e4b504 (18 turns)

The `inbound_body` fix helped but stale continuity is still leaking. Remaining failures:

| Turn | Athlete says | Coach says | Problem |
|------|-------------|-----------|---------|
| 10 | "24:50 tune-up 5k, felt controlled, no big pain" | "keeping plan to three easy sessions" | Ignores milestone; references stale T9 plan |
| 11 | "Still doing four days per week" | "this week we'll run three easy sessions" | Directly contradicts athlete's stated pattern |
| 15 | "Saturday is open again, four days per week" | Asks for clarification again | Shouldn't need clarification — athlete just confirmed |
| 18 | "Better week. 3 runs: 35m/50m/80m, felt good, Achilles quiet" | "To finalize this week's two-session plan" | Leaks T17's deload continuity into T18 |

Root cause: Two compounding prompt weaknesses:
1. **Memory refresh LLM** doesn't rewrite continuity from scratch each turn — `last_recommendation` and `open_loops` persist even when the athlete's situation has changed.
2. **Response generation LLM** treats continuity as authoritative coaching state rather than stale background.

## Next Steps — Stale Continuity Fix (Planned, Ready to Implement)

Plan is in `/Users/levonsh/.claude/plans/magical-singing-pine.md`. Three changes:

**Change 1 — Memory refresh prompt** (`skills/memory/unified/prompt.py`):
Add "Continuity writing rules" subsection after existing Continuity block:
- Rewrite all three fields from scratch every turn (no copy-paste from previous)
- `last_recommendation` must reflect THIS turn's `coach_reply`, not prior advice
- Drop `open_loops` that `inbound_email` already answers

**Change 2 — Response generation prompt** (`skills/response_generation/prompt.py`):
Replace weak "do NOT let it override" guidance with an explicit numbered priority hierarchy (inbound_body → validated_plan → backbone → continuity).

**Change 3 — Assembly staleness annotation** (`response_generation_assembly.py`):
Prefix `continuity_focus` string with `[previous turn context]` as an in-band staleness signal.

**Test updates required** (5 assertions):
- `test_response_generation_skill.py:188` — prompt text assertion
- `test_response_generation_assembly.py:114,243` — continuity_focus prefix
- `test_coaching.py:409,547` — continuity_focus prefix

## Test Commands

```bash
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
# 362 tests, all passing as of end of last session

python3 -m unittest -v sam-app/e2e/test_live_coaching_workflow.py
# Requires live AWS — generates turn artifacts in sam-app/e2e/artifacts/
```

## Architecture Invariants (Do Not Break)

- Security gates in `app.py` / `auth.py` / `rate_limits.py` — no LLM before quota claim
- `rule_engine.py` is sole authority on training state, plan decisions, track selection
- DynamoDB table schema is fixed (provisioned in `template.yaml`)
- Prompts live in skill packages only — never in `email_copy.py`
- Fail closed: invalid LLM output must not propagate to the send path
- `ResponseBrief` is the bounded validated artifact passed to response generation LLM (never raw DynamoDB)
- Memory refresh happens post-reply (previous turn's state is read before generation, updated after)
