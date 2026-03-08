## Done Gate
Before marking a task done, run:

```bash
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

## Implementation Discipline
- YAGNI: build only what’s needed now.
- Prefer concrete implementations until a pattern repeats.
- Do not preserve backward compatibility for its own sake; prefer the simplest, cleanest implementation over historical behavior whenever there is a tradeoff.
