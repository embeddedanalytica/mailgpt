# Remaining Groups Handoff

Date: 2026-04-03
Repo: `/Users/levonsh/Projects/smartmail`

This file is a handoff for the bug groups not covered by the completed Group 1 memory fixes.

## Group Overview

### Group 2: Continuity / In-Thread Memory
- Bugs: `20`, `29`

### Group 3: Strategist / Coaching Decision Logic
- Bugs: `13`, `14`, `26`, `32`
- Primary owner for `28`

### Group 4: Writer / Directive Fidelity
- Bugs: `24`
- Secondary owner for `28`

### Group 5: Athlete Simulator
- Bug: `30`

### Group 6: Judge / Scoring Calibration
- Bugs: `31`, `33`

## Group 2: Continuity / In-Thread Memory

### Bugs
- `20` Continuity bootstrap treats past event dates as active event horizons
- `29` Coach loses track of previously provided information in longer conversations

### Main Code Paths
- [sam-app/email_service/continuity_bootstrap.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/continuity_bootstrap.py)
- [sam-app/email_service/dynamodb_models.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/dynamodb_models.py)
- [sam-app/email_service/response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_assembly.py)
- [sam-app/email_service/skills/memory/unified/runner.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/memory/unified/runner.py)

### What I Found

#### Bug 20
- this is a clean deterministic bug
- `_parse_event_date()` in `continuity_bootstrap.py` accepts any syntactically valid ISO date
- it does not reject stale past event dates
- bootstrap can therefore produce `goal_horizon_type="event"` for an athlete whose event is already over

#### Bug 29
- likely not a single-file issue
- likely a continuity handoff bug between stored `continuity_summary`, open loops, and response assembly
- the bug backlog theory is plausible: already-resolved questions stay alive in `open_loops` or continuity context
- I did not find a deterministic regression for repeated concrete facts like travel dates being asked again

### Existing Useful Tests
- [sam-app/email_service/test_continuity_state_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_continuity_state_contract.py)
- [sam-app/email_service/test_response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_assembly.py)
- [sam-app/email_service/test_coaching_reasoning_eval.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching_reasoning_eval.py)

### Missing Tests
- no exact bootstrap regression for “past event date should be ignored”
- no deterministic regression for “dates already provided and acknowledged must not be re-asked”

### Recommended First Moves
1. Add a unit regression to `test_continuity_state_contract.py` for a past `event_date`
2. Fix `continuity_bootstrap.py` to ignore past dates during bootstrap
3. Add deterministic continuity/open-loop regressions for resolved facts before changing prompts

## Group 3: Strategist / Coaching Decision Logic

### Bugs
- `13` Achilles rebuild flow can prescribe tempo work too early
- `14` Coaching reply can contradict its own “fully aerobic” guidance
- `26` Coach repeats already-established constraints verbatim every turn
- `32` Coach produces vague or non-decisive guidance
- primary owner for `28`

### Main Code Paths
- [sam-app/email_service/skills/coaching_reasoning/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/prompt.py)
- [sam-app/email_service/skills/coaching_reasoning/runner.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/runner.py)
- [sam-app/email_service/prompt_packs/coach_reply/v1/constitution.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/constitution.json)
- [sam-app/email_service/prompt_packs/coach_reply/v1/operational_rules.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/operational_rules.json)
- [sam-app/email_service/prompt_packs/coach_reply/v1/reply_mode_rules.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/reply_mode_rules.json)

### What I Found

#### Bugs 13 and 14
- both are reflected in the live workflow fixture:
  - [sam-app/e2e/test_live_coaching_workflow.py](/Users/levonsh/Projects/smartmail/sam-app/e2e/test_live_coaching_workflow.py)
- there are relevant turns for:
  - Achilles rebuild / mild Achilles tightness
  - “keep everything fully aerobic for now?”
- but I did not find direct assertions that forbid tempo/strides in those cases

#### Bug 26
- partly strategist, partly continuity
- there is final-email obedience coverage for standing-rule repetition, but not direct strategist regression coverage
- likely source is strategist `content_plan` staying too broad when nothing changed

#### Bug 32
- mostly prompt behavior
- current repo has `too_vague` aggregation and prompt-patch tooling, but not a direct strategist regression requiring one clear recommendation

#### Bug 28
- strategist should be treated as the source of truth for coach capability
- writer should not override that truth later

### Existing Useful Tests
- [sam-app/email_service/test_coaching_reasoning_eval.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching_reasoning_eval.py)
- [sam-app/e2e/test_live_coaching_workflow.py](/Users/levonsh/Projects/smartmail/sam-app/e2e/test_live_coaching_workflow.py)
- [sam-app/email_service/test_obedience_eval.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_obedience_eval.py)

### Missing Tests
- no direct strategist regression for:
  - no tempo in early Achilles rebuild
  - no contradiction inside a “fully aerobic” directive
  - no repetitive recap of already-established constraints
  - one clear recommendation when athlete asks for direction

### Recommended First Moves
1. Add targeted live strategist regressions in `test_coaching_reasoning_eval.py`
2. Keep each fixture single-purpose
3. Change prompt-pack rules only after the regression exists

## Group 4: Writer / Directive Fidelity

### Bugs
- `24` Writer hallucinates week numbers and drops directive details
- secondary owner for `28`

### Main Code Paths
- [sam-app/email_service/skills/response_generation/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/response_generation/prompt.py)
- [sam-app/email_service/skills/response_generation/runner.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/response_generation/runner.py)
- [sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json)

### What I Found
- current tests mostly verify prompt assembly, scope lock, and narrow-directive detection
- they do not prove output-level fidelity to:
  - week numbers from `continuity_context`
  - all items in `content_plan`
  - exact structural details in `main_message`
- important behavior:
  - if `_is_narrow_directive()` returns true, continuity prompt section is omitted
  - this matches the backlog suspicion for week-number drift

### Existing Useful Tests
- [sam-app/email_service/test_response_generation_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_skill.py)
- [sam-app/email_service/test_response_generation_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_contract.py)
- [sam-app/email_service/test_response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_assembly.py)

### Missing Tests
- no deterministic output-level regression for wrong week number
- no direct check that generated output contains all required directive items
- no writer-side capability consistency regression for `28`

### Recommended First Moves
1. Add deterministic tests around prompt selection and week anchoring
2. If needed, add a post-generation validator for week labels / required items
3. Add focused writer regressions after that

## Group 5: Athlete Simulator

### Bug
- `30` Simulated athlete gets stuck in degenerate repetition loops

### Main Code Paths
- [sam-app/email_service/athlete_simulation.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/athlete_simulation.py)
- [sam-app/e2e/test_live_athlete_sim_runner.py](/Users/levonsh/Projects/smartmail/sam-app/e2e/test_live_athlete_sim_runner.py)

### What I Found
- prompt text already includes anti-loop guidance:
  - do not get stuck in loops
  - do not repeat substantially the same message
  - follow through within 1-2 turns
- current tests mostly validate schema/prompt text, not actual multi-turn behavior

### Existing Useful Tests
- [sam-app/email_service/test_athlete_simulation.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_athlete_simulation.py)
- [sam-app/e2e/test_live_athlete_sim_runner.py](/Users/levonsh/Projects/smartmail/sam-app/e2e/test_live_athlete_sim_runner.py)

### Missing Tests
- no regression proving that after repeated promises, the simulator actually advances state

### Recommended First Moves
1. Add a short multi-turn regression around promised check-in data
2. Check material progression, not exact wording

## Group 6: Judge / Scoring Calibration

### Bugs
- `31` Judge over-rewards trivial acknowledgment turns
- `33` Judge scoring is inflated relative to athlete signal

### Main Code Paths
- [sam-app/email_service/athlete_simulation.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/athlete_simulation.py)
- [sam-app/email_service/test_prompt_feedback_aggregate.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_prompt_feedback_aggregate.py)

### What I Found
- judge schema/rubric exists in `athlete_simulation.py`
- current tests validate:
  - schema shape
  - allowed tags
  - aggregation math
- they do not validate actual calibration behavior
- no tests currently force:
  - score caps for trivial stalled turns
  - meaningful penalty for `too_vague`
  - hard cap for `hallucinated_context`

### Existing Useful Tests
- [sam-app/email_service/test_athlete_simulation.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_athlete_simulation.py)
- [sam-app/email_service/test_prompt_feedback_aggregate.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_prompt_feedback_aggregate.py)
- [sam-app/email_service/test_prompt_feedback_loop.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_prompt_feedback_loop.py)

### Missing Tests
- no targeted judge regressions with transcript + reply + expected score ceilings/floors

### Recommended First Moves
1. Add targeted judge regressions with fixed transcript snippets
2. Assert score bounds and required issue tags
3. Only then adjust the judge prompt/rubric

## Cross-Group Note: Bug 28

### Bug
- `28` Coach contradicts its own capabilities mid-conversation

### Ownership
- strategist is primary owner
- writer is enforcement owner

### Main Files
- [sam-app/email_service/prompt_packs/coach_reply/v1/constitution.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/constitution.json)
- [sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json)
- [sam-app/email_service/skills/coaching_reasoning/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/prompt.py)
- [sam-app/email_service/skills/response_generation/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/response_generation/prompt.py)

### What I Found
- bug `27` already established that strategist could invent delivery mechanisms and writer would comply
- that grounding fix exists, but `28` is broader and cross-turn:
  - first turn says no files/calendar actions
  - later turn pretends files were attached or released

### Recommended First Moves
1. Add a short cross-turn strategist+writer regression
2. Assert capability consistency across turns before changing prompts further

## Suggested Execution Order

If continuing from here, I would do:

1. Group 2, bug `20`
2. Group 2, bug `29`
3. Group 3 regressions for `13`, `14`, `26`, `32`
4. Group 4 regressions for `24`
5. Bug `28` cross-turn capability regression
6. Group 5, bug `30`
7. Group 6, bugs `31`, `33`

## Dirty Worktree Note

The repo has many unrelated uncommitted changes.

Do not revert unrelated files.

The completed Group 1 memory work lives separately and is summarized in:
- [group1-memory-handoff.md](/Users/levonsh/Projects/smartmail/group1-memory-handoff.md)
