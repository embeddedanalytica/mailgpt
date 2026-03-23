# email_service — Pipeline + Module Map

Pipeline: `SES → SNS → app.py → business.py → coaching.py → skills/* → reply`

| Module | Responsibility | Status |
|---|---|---|
| `app.py` | Lambda handler: parse → auth → quota → dispatch | stable |
| `auth.py` | Registration / verification gating | stable |
| `rate_limits.py` | Hourly/daily quota enforcement | stable |
| `rule_engine.py` + orchestrator + state | Deterministic rule engine (RE1–RE4) | stable |
| `dynamodb_models.py` | DynamoDB persistence helpers | stable |
| `email_copy.py` | Transactional outbound copy (not prompts) | stable |
| `business.py` | Orchestration entrypoint | refactor |
| `coaching.py` | Profile gate + LLM reply generation | refactor |
| `response_generation_*.py` | ResponseBrief assembly + contracts | refactor |
| `athlete_memory_*.py` / `coaching_memory.py` | Memory contracts + refresh | refactor |
| `profile.py` / `ai_extraction_contract.py` | Profile parsing + AI extraction | refactor |
| `conversation_intelligence.py` / `inbound_rule_router.py` | Classification + routing | refactor |

## Testing

```bash
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py   # requires live AWS
```

Do not mock DynamoDB in unit tests. See `skills/CLAUDE.md` for skill-level testing.

**Merge bar vs inner loop:** Full gate (including live e2e) is defined in repo `AGENTS.md`. During edits, prefer running the `email_service` discovery command above often; run e2e before merge or when validating AWS-facing behavior.

**Refactors and `unittest.mock`:** Many tests patch symbols on `coaching` (e.g. `coaching.get_coach_profile`), not on helper modules. If you move orchestration into another module (`coaching_phases.py`, etc.), either keep those entrypoints on `coaching` and pass callables into helpers, or update tests to patch the new import paths—otherwise patches silently stop applying.

**Shared skill runners:** Central wrappers (e.g. `skills/runtime.run_validated_json_schema_workflow`) should expose optional hooks (such as `on_raw_llm_response`) when a workflow needs extra logging between the raw LLM response and schema validation.
