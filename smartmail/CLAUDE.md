# SmartMail — agent

`SES→SNS→app→business→coaching→skills→reply` (SAM). Lambdas: `email_service` (Python), `action_link_handler` (Python), `email_registration` (Node).

## Invariants

| | |
|---|---|
| **Gates** | Before any LLM: unregistered→reg; unverified→verify; verified→quota (`auth.py`, `rate_limits.py`). |
| **Rule engine** | `rule_engine.py` owns plan/state/tracks/deload. LLM output must not override. |
| **Data** | DynamoDB shape/access = `template.yaml` only. |
| **Prompts** | `email_service/skills/**` only. `email_copy.py` = transactional copy, not prompts. |

## Principles

- **Coaching quality:** fix in the **LLM layer** (prompt, schema, memory, routing). **Do not** default to regex, heuristics, or other deterministic logic—use that only after LLM-path options are exhausted.
- **Prompt size:** coaching + doctrine prompts are already **large**; treat size as a **hard constraint**. New/expanded sections need justification; **deleting or tightening** copy is as valid as adding.
- **Layer boundaries:** `coaching_reasoning`→directive/facts · `response_generation`→surface text · `obedience_eval`→compliance. Fix the owning layer.
- **Tests:** passing ≠ shipped; behavior must improve.

**Merge bar / inner loop / discipline:** [`AGENTS.md`](AGENTS.md#merge-bar)

**On demand:** [`sam-app/CLAUDE.md`](sam-app/CLAUDE.md) · [`sam-app/email_service/CLAUDE.md`](sam-app/email_service/CLAUDE.md) · [`skills/CLAUDE.md`](sam-app/email_service/skills/CLAUDE.md) · [`skills/memory/CLAUDE.md`](sam-app/email_service/skills/memory/CLAUDE.md) · [`skills/response_generation/CLAUDE.md`](sam-app/email_service/skills/response_generation/CLAUDE.md)
