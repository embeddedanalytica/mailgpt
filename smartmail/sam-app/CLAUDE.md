# sam-app — Build, Deploy, Data Reference

Docs: `README.md` (runtime state), `DECISIONS.md` (arch decisions), `../bug-backlog.md` (open bugs)

## Build & Deploy

```bash
cd sam-app && sam build
sam deploy --guided          # first time
sam deploy                   # subsequent
sam local start-api
sam local invoke EmailServiceFunction --event events/sns-email-event.json
```

## DynamoDB Tables

| Table | PK | SK | Notes |
|---|---|---|---|
| `coach_profiles` | `athlete_id` | — | Profile, plan, memory, continuity |
| `athlete_identities` | `email` | — | Maps email → athlete_id |
| `action_tokens` | `token_id` | — | TTL: `expires_at` |
| `verified_sessions` | `email` | — | TTL: `session_expires_at` |
| `rate_limits` | `email` | — | Quota + verification cooldown |
| `rule_state` | `athlete_id` | — | Rule-engine state |
| `plan_history` | `athlete_id` | `plan_version` | Immutable |
| `activities` | `athlete_id` | `provider_activity_key` | Connector-synced |
| `manual_activity_snapshots` | `athlete_id` | `snapshot_key` | Manual activity |
| `progress_snapshots` | `athlete_id` | — | Current progress |
| `users` | `email_address` | — | Manual table — not in template.yaml |
