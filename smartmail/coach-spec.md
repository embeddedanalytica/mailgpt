# Coaching Reasoning Skill + Doctrine System

## Context

E2e coaching test (30 turns) revealed the LLM coach misses critical coaching signals: premature intensity escalation after recovery (Turn 18 → injury), no celebration on goal completion (Turn 27), formulaic repetition, and inability to adapt to relationship maturity.

Root cause: The LLM has **no coaching methodology** and **no separation between coaching judgment and email writing**. The current response generation prompt (~1000 tokens) tries to do both — interpret the athlete's situation AND write a polished email — with zero sport coaching wisdom.

**User vision**: Build a coach grounded in real coaching methodology that can grow into world-class domain expertise (Friel for cycling, Daniels for running, Attia for health). The coach should recommend reading/watching materials. The knowledge system is the coach's identity.

## Non-goals

- **No planner logic changes.** This PR does not modify the planner skill, session check-in extraction, or any conversation intelligence classification.
- **No deterministic rule engine changes.** Risk derivation, phase selection, archetype mapping, and weekly skeleton building remain unchanged. The rule engine's outputs are authoritative — we're giving the LLM better judgment about how to *communicate* those outputs, not changing what they are.
- **No new DynamoDB tables or schema changes.** We expose an existing field (`created_at`) and pass new optional fields through existing open-dict contracts.
- **No changes to the memory subsystem.** AM3 backbone/context_notes/continuity model is untouched.

## Architecture: Two-Stage Pipeline

Split the current single-LLM response generation into two stages:

```
ResponseBrief + Coaching Doctrine
        ↓
[Coaching Reasoning Skill]  ← NEW: decides WHAT to say and WHY
        ↓
CoachingDirective + plan_data + delivery_context
        ↓
[Response Generation Skill] ← SIMPLIFIED: decides HOW to write it
        ↓
final_email_body
```

**Why split?**
- Doctrine is about coaching *reasoning*, not email *writing* — different concerns
- As doctrine grows (cycling, health, triathlon), it stays in stage 1 only
- Coaching quality can be evaluated independently from writing quality
- Response generation prompt gets simpler
- Coaching reasoning becomes reusable for non-email channels later

**Latency**: +1-2s per email. Total pipeline: 4-8.5s. Acceptable for email.

---

## User Stories

### Story 1: Doctrine loader and tests

**Goal**: Build the coaching knowledge base and the manifest-driven loader that selects sport-specific doctrine files. No LLM integration — just the file system and loader logic.

**Create**:
```
skills/coaching_reasoning/doctrine/
├── __init__.py           # Loader: build_doctrine_context(sport), list_loaded_files(sport)
├── manifest.py           # Sport → file mapping (UNIVERSAL_FILES, SPORT_FILES, SPORT_ALIASES)
├── universal/
│   ├── core.md           # Periodization, overload, recovery, psychological safety (~400 tokens)
│   ├── recovery_and_risk.md  # Post-setback coaching, "first good week is fragile" (~250 tokens)
│   └── relationship_arc.md   # Communication evolution: weeks 1-4 / 5-12 / 12+ (~200 tokens)
├── running/
│   ├── methodology.md    # Daniels, Pfitzinger, 80/20, taper, injury return (~350 tokens)
│   └── recommendations.md # Running books: Daniels' Running Formula, Advanced Marathoning, 80/20 Running (~150 tokens)
└── general/
    └── recommendations.md # Cross-sport: Outlive, Endure, Peak Performance (~100 tokens)
```

**Selective loading**: `build_doctrine_context("running")` loads `universal/*` + `running/*` + `general/*`. `build_doctrine_context("cycling")` would load `universal/*` + `cycling/*` + `general/*`. No cross-contamination.

**Token budget per sport**: ~1450 tokens (universal ~850 + sport ~500 + general ~100).

**Loader design**: See [Appendix A: Doctrine Loader](#appendix-a-doctrine-loader).

**Test**: `test_coaching_doctrine.py`
- `build_doctrine_context("running")` includes running methodology, excludes cycling
- `build_doctrine_context(None)` includes only universal + general
- `list_loaded_files("half marathon")` resolves alias → running
- Files load once and are cached
- All referenced .md files exist and are non-empty

---

### Story 2: Coaching reasoning skill (schema, validator, runner) — no integration

**Goal**: Build the full coaching reasoning skill package that can produce CoachingDirectives from ResponseBriefs. Testable in isolation.

**Create**:
```
skills/coaching_reasoning/
├── __init__.py    # Exports run_coaching_reasoning_workflow, CoachingReasoningError
├── prompt.py      # System prompt + build_system_prompt(sport)
├── schema.py      # CoachingDirective JSON schema
├── validator.py   # Validates LLM output against CoachingDirective contract
├── runner.py      # Calls execute_json_schema(), returns {directive, doctrine_files_loaded}
└── errors.py      # CoachingReasoningError
```

**CoachingDirective schema** (output of stage 1):
```json
{
  "opening": "string — how to open the email",
  "main_message": "string — core coaching message",
  "content_plan": ["string — ordered content items"],
  "avoid": ["string — things to NOT say"],
  "tone": "string — tone guidance",
  "recommend_material": "string | null — book/video if relevant",
  "rationale": "string — internal reasoning (for eval, NOT forwarded to writer)"
}
```

**Runner returns a wrapper** (not the raw LLM output):
```python
{"directive": validated_directive, "doctrine_files_loaded": ["universal/core.md", ...]}
```
`doctrine_files_loaded` comes from `list_loaded_files()` in code, not from the LLM (schema has `additionalProperties: False`).

**System prompt**: See [Appendix B: Coaching Reasoning Prompt](#appendix-b-coaching-reasoning-prompt).

**Test**: `test_coaching_reasoning_skill.py`
- Schema validation: valid directive passes, missing required fields fail
- Validator strips/normalizes correctly
- Runner calls `execute_json_schema` with sport-aware prompt (mock LLM)
- Runner wraps output with `doctrine_files_loaded` metadata

---

### Story 3: Evaluation tests for coaching directives on known bad turns

**Goal**: Build an eval harness that feeds known-problematic turns (from the e2e sim) through the coaching reasoning skill and asserts the directive addresses the issue.

**Test cases** (from `live_coaching_turns_1774065024-9ab4d50b.jsonl`):
- **Turn 18** (post-recovery escalation): directive should acknowledge recovery arc in `opening`, `avoid` should include premature intensity language
- **Turn 27** (race completion): directive `opening` should lead with celebration, `content_plan[0]` should be milestone recognition
- **Turn 20+** (relationship maturity): with `weeks_in_coaching >= 12`, directive should NOT repeat basic technique cues in `content_plan`
- **Turn 25** (reflection question): directive `main_message` should synthesize personalized insight, not default to plan

These tests require live LLM calls (or representative fixtures). They serve as the quality gate for doctrine content tuning.

---

### Story 4: Response generation directive contract support (preserving old path)

**Goal**: Enable response generation to accept either a `WriterBrief` (from coaching reasoning) or the existing `ResponseBrief` (fallback). Both paths produce `final_email_body`.

**Modify** [response_generation_contract.py](sam-app/email_service/response_generation_contract.py):
- Add `WriterBrief` dataclass + `validate_writer_brief()` + `_WRITER_BRIEF_TOP_LEVEL_FIELDS`
- Add `is_directive_input()` using **exact top-level key-set matching** (not single-key presence)
- Expand `_ATHLETE_CONTEXT_FIELDS` to include `primary_sport`
- Expand `_DECISION_CONTEXT_FIELDS` to include `risk_recent_history` (list[str]) and `weeks_in_coaching` (int)
- Update `_validate_decision_context()` for new types

**Modify** [validator.py](sam-app/email_service/skills/response_generation/validator.py):
- Branch on `is_directive_input()` → validate as `WriterBrief` or `ResponseBrief`

**Modify** [prompt.py](sam-app/email_service/skills/response_generation/prompt.py):
- Add `DIRECTIVE_SYSTEM_PROMPT` (writing-focused, no authority-split)
- Keep existing `SYSTEM_PROMPT` unchanged (used by fallback path)

**Modify** [runner.py](sam-app/email_service/skills/response_generation/runner.py):
- Select prompt based on `is_directive_input(brief)`

**Add** to [response_generation_assembly.py](sam-app/email_service/response_generation_assembly.py):
- `build_response_generation_input()` — reshapes directive + brief into WriterBrief, **strips `rationale`**

**Test**: existing tests pass + new tests for WriterBrief validation, prompt selection, rationale stripping

---

### Story 5: Wire two-stage orchestration behind a feature flag

**Goal**: Integrate coaching reasoning → response generation in `coaching.py`, gated by `ENABLE_COACHING_REASONING` flag.

**Modify** [config.py](sam-app/email_service/config.py):
- Add `ENABLE_COACHING_REASONING = os.environ.get("ENABLE_COACHING_REASONING", "").strip().lower() == "true"`

**Modify** [coaching.py](sam-app/email_service/coaching.py) — `_generate_llm_reply()`:
```python
coaching_result = None
if ENABLE_COACHING_REASONING:
    try:
        coaching_result = run_coaching_reasoning_workflow(brief, model_name=...)
        logger.info("coaching_directive athlete_id=%s rationale=%s doctrine_files=%s", ...)
    except CoachingReasoningError as exc:
        logger.warning("coaching_reasoning_fallback athlete_id=%s error=%s", ...)

if coaching_result is not None:
    rg_input = build_response_generation_input(directive=coaching_result["directive"], brief=response_brief)
else:
    rg_input = response_brief.to_dict()  # existing path, unchanged

generated_response = run_response_generation_workflow(rg_input, model_name=...)
```

Fallback lives in `coaching.py` orchestration only — runner never knows about it.

**Modify** [skills/CLAUDE.md](sam-app/email_service/skills/CLAUDE.md):
- Add `coaching_reasoning/` to package index

**Test**: test with flag on (directive path) and flag off (fallback path) both produce valid replies

---

### Story 6: Add risk-trend and sport fields needed by stage 1

**Goal**: Thread `risk_recent_history`, `weeks_in_coaching`, and `primary_sport` into the ResponseBrief so the coaching reasoning skill can use them.

**Modify** [rule_engine.py](sam-app/email_service/rule_engine.py):
- Add `risk_recent_history: List[str]` to `RuleEngineOutput`
- Update `to_dict()`, `from_dict()`, `validate_rule_engine_output()`

**Modify** [rule_engine_orchestrator.py](sam-app/email_service/rule_engine_orchestrator.py):
- Extract from `rule_state.get("phase_risk_time_last_6")` before building output

**Modify** [dynamodb_models.py](sam-app/email_service/dynamodb_models.py):
- Expose `created_at` in `normalize_profile_record()` (already in DynamoDB, just stripped on read)

**Modify** [response_generation_assembly.py](sam-app/email_service/response_generation_assembly.py):
- Thread `risk_recent_history` from engine output → `decision_context`
- Compute `weeks_in_coaching` from `profile_after.get("created_at")` → `decision_context`
- Thread `primary_sport` from `profile_after.get("main_sport_current")` → `athlete_context`

Note: Contract expansion from Story 4 must land first (otherwise these fields get rejected by `_validate_allowed_fields()`).

**Test**: `test_rule_engine.py` for new RuleEngineOutput fields, `test_response_generation_assembly.py` for threading

---

### Story 7: Run e2e and tune prompts/doctrine

**Goal**: Run the full e2e sim with coaching reasoning enabled and iterate on doctrine content and prompt wording.

**Steps**:
1. Set `ENABLE_COACHING_REASONING=true` in test environment
2. Run e2e sim: `python3 sam-app/e2e/test_live_coaching_workflow.py`
3. Evaluate against known bad turns:
   - Turn 18: recovery arc acknowledged?
   - Turn 27: milestone celebrated?
   - Turns 20+: repetition decreased?
   - Turn 25: personalized synthesis?
4. Tune doctrine `.md` files based on results
5. Verify fallback path still works with flag off

---

## Appendix A: Doctrine Loader

**`manifest.py`**:
```python
UNIVERSAL_FILES = [
    "universal/core.md",
    "universal/recovery_and_risk.md",
    "universal/relationship_arc.md",
]
GENERAL_FILES = ["general/recommendations.md"]
SPORT_FILES: dict[str, list[str]] = {
    "running": ["running/methodology.md", "running/recommendations.md"],
}
SPORT_ALIASES: dict[str, str] = {
    "running": "running", "marathon": "running", "half marathon": "running",
    "5k": "running", "10k": "running", "trail running": "running",
    "trail": "running", "ultramarathon": "running",
}
```

**`__init__.py`**:
```python
from pathlib import Path
from typing import Optional
from .manifest import UNIVERSAL_FILES, GENERAL_FILES, SPORT_FILES, SPORT_ALIASES

_DIR = Path(__file__).parent
_CACHE: dict[str, str] = {}

def _load(relative_path: str) -> str:
    if relative_path not in _CACHE:
        _CACHE[relative_path] = (_DIR / relative_path).read_text().strip()
    return _CACHE[relative_path]

def _resolve_sport(sport: Optional[str]) -> Optional[str]:
    normalized = (sport or "").strip().lower()
    if not normalized:
        return None
    for keyword, canonical in SPORT_ALIASES.items():
        if keyword in normalized:
            return canonical
    return None

def build_doctrine_context(sport: Optional[str] = None) -> str:
    sections = [_load(f) for f in UNIVERSAL_FILES]
    sport_key = _resolve_sport(sport)
    if sport_key and sport_key in SPORT_FILES:
        sections.extend(_load(f) for f in SPORT_FILES[sport_key])
    sections.extend(_load(f) for f in GENERAL_FILES)
    return "\n\n".join(sections)

def list_loaded_files(sport: Optional[str] = None) -> list[str]:
    files = list(UNIVERSAL_FILES)
    sport_key = _resolve_sport(sport)
    if sport_key and sport_key in SPORT_FILES:
        files.extend(SPORT_FILES[sport_key])
    files.extend(GENERAL_FILES)
    return files
```

## Appendix B: Coaching Reasoning Prompt

```python
_BASE_PROMPT = """You are an expert coaching strategist. Given the athlete's situation, training
context, and coaching history, determine the optimal coaching approach for this turn.

Your job is NOT to write the email — a separate writing step handles that. Your job is to
decide WHAT the coach should communicate and WHY, using your coaching expertise.

The input is a response_brief JSON object containing:
- reply_mode: the communication objective (normal_coaching, intake, clarification, etc.)
- athlete_context: who the athlete is (goal, experience level, sport, constraints)
- decision_context: rule engine decisions, risk_recent_history (recent weekly risk flags),
  weeks_in_coaching (how long you've been coaching this athlete)
- validated_plan: the training plan to communicate (weekly skeleton, sessions, adjustments)
- memory_context: what you remember about this athlete (backbone facts, context notes, continuity)
- delivery_context: the athlete's actual message this turn (read it carefully for emotional state)

Guidelines:
- Read the athlete's message first. Understand what they said and what they need emotionally.
- Use risk_recent_history to understand trajectory — a single green after yellows is fragile.
- Use weeks_in_coaching to calibrate: early weeks need more explanation, later weeks need directness.
- When the athlete reports a milestone (race, PR, breakthrough), lead with celebration.
- Only recommend materials when contextually relevant — never as filler.
- The rationale field is for your internal reasoning — be honest about your coaching logic.
- For intake mode: plan information gathering, not coaching advice.
- For clarification mode: identify exactly what to ask, nothing more.

Return a coaching_directive JSON matching the provided schema."""

def build_system_prompt(sport: str | None = None) -> str:
    doctrine = build_doctrine_context(sport)
    return f"{_BASE_PROMPT}\n\nCoaching methodology:\n{doctrine}"
```

## Appendix C: Key Contract Details

**WriterBrief** (new, for directive path):
- Top-level fields: `{reply_mode, coaching_directive, plan_data, delivery_context}` — exact set, strict matching
- `is_directive_input()` uses `set(payload.keys()) == _WRITER_BRIEF_TOP_LEVEL_FIELDS`
- `rationale` stripped by `build_response_generation_input()` before reaching writer

**ResponseBrief** (existing, expanded):
- `_ATHLETE_CONTEXT_FIELDS` += `primary_sport`
- `_DECISION_CONTEXT_FIELDS` += `risk_recent_history` (list[str]), `weeks_in_coaching` (int)
- `_validate_decision_context()` updated for non-string types

**`created_at`**: Already in DynamoDB for every profile. Expose in `normalize_profile_record()`. Compute `weeks_in_coaching = max(1, int((now - created_at) / 604800))`.

## Files to create

| File | Story |
|------|-------|
| `skills/coaching_reasoning/__init__.py` | 2 |
| `skills/coaching_reasoning/prompt.py` | 2 |
| `skills/coaching_reasoning/schema.py` | 2 |
| `skills/coaching_reasoning/validator.py` | 2 |
| `skills/coaching_reasoning/runner.py` | 2 |
| `skills/coaching_reasoning/errors.py` | 2 |
| `skills/coaching_reasoning/doctrine/__init__.py` | 1 |
| `skills/coaching_reasoning/doctrine/manifest.py` | 1 |
| `skills/coaching_reasoning/doctrine/universal/core.md` | 1 |
| `skills/coaching_reasoning/doctrine/universal/recovery_and_risk.md` | 1 |
| `skills/coaching_reasoning/doctrine/universal/relationship_arc.md` | 1 |
| `skills/coaching_reasoning/doctrine/running/methodology.md` | 1 |
| `skills/coaching_reasoning/doctrine/running/recommendations.md` | 1 |
| `skills/coaching_reasoning/doctrine/general/recommendations.md` | 1 |

## Files to modify

| File | Story | What changes |
|------|-------|-------------|
| [response_generation_contract.py](sam-app/email_service/response_generation_contract.py) | 4, 6 | WriterBrief + is_directive_input + expand allowed fields |
| [validator.py](sam-app/email_service/skills/response_generation/validator.py) | 4 | Branch on is_directive_input |
| [prompt.py](sam-app/email_service/skills/response_generation/prompt.py) | 4 | Add DIRECTIVE_SYSTEM_PROMPT |
| [runner.py](sam-app/email_service/skills/response_generation/runner.py) | 4 | Prompt selection |
| [response_generation_assembly.py](sam-app/email_service/response_generation_assembly.py) | 4, 6 | build_response_generation_input + thread new fields |
| [coaching.py](sam-app/email_service/coaching.py) | 5 | Two-stage orchestration behind flag |
| [config.py](sam-app/email_service/config.py) | 5 | ENABLE_COACHING_REASONING flag |
| [rule_engine.py](sam-app/email_service/rule_engine.py) | 6 | risk_recent_history in RuleEngineOutput |
| [rule_engine_orchestrator.py](sam-app/email_service/rule_engine_orchestrator.py) | 6 | Extract risk history |
| [dynamodb_models.py](sam-app/email_service/dynamodb_models.py) | 6 | Expose created_at in normalizer |
| [skills/CLAUDE.md](sam-app/email_service/skills/CLAUDE.md) | 5 | Add coaching_reasoning to index |

## Verification

```bash
cd sam-app && python3 -m unittest discover -v -p "test_*.py" -s email_service
```
