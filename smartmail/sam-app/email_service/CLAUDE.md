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
| `openai_responder.py` | Dead shim | delete |

## Testing

```bash
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py   # requires live AWS
```

Do not mock DynamoDB in unit tests. See `skills/CLAUDE.md` for skill-level testing.
