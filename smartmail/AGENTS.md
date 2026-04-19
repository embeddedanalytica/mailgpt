# Agents

**Invariants + principles:** [`CLAUDE.md`](CLAUDE.md) (edit there, not here).

**`email_service` (pipeline, modules, testing notes):** [`sam-app/email_service/CLAUDE.md`](sam-app/email_service/CLAUDE.md) — read when changing anything under `sam-app/email_service/`.

## Merge bar

Full suite before marking work done:

```bash
PYTHONPATH=sam-app/action_link_handler python3 -m unittest discover -v -s sam-app/tests/action_link_handler -p "test_*.py"
PYTHONPATH=sam-app/email_service python3 -m unittest discover -v -s sam-app/tests/email_service -p "test_*.py"
python3 -m unittest -v sam-app/tests/e2e/test_live_endpoints.py
```

**Inner loop:** run `sam-app/tests/email_service` (and `action_link_handler` when touched) often. `sam-app/tests/e2e/test_live_endpoints.py` = pre-merge / AWS-costly.

**email_service test conventions** (DynamoDB, `mock` patch points, runners): [`sam-app/email_service/CLAUDE.md#testing`](sam-app/email_service/CLAUDE.md#testing)

## Implementation discipline

- YAGNI.
- Simplest/cleanest over backward compatibility when they conflict.
