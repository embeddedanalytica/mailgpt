# SmartMail

Status: current state.

Email-first coaching service built on AWS SAM. Inbound email is the primary UI. A small HTTP surface exists for registration, action links, and the Strava OAuth callback.

## Document Map

Use the repository docs with these roles:

- This README is the current implementation and runtime overview.
- [`/Users/levonsh/Projects/smartmail/spec.md`](/Users/levonsh/Projects/smartmail/spec.md) is the source of truth for rule behavior.
- [`/Users/levonsh/Projects/smartmail/sam-app/DECISIONS.md`](/Users/levonsh/Projects/smartmail/sam-app/DECISIONS.md) records durable architectural decisions only.
- [`/Users/levonsh/Projects/smartmail/rule-engine-epic.md`](/Users/levonsh/Projects/smartmail/rule-engine-epic.md) is the completed implementation record for the rule engine.
- [`/Users/levonsh/Projects/smartmail/athlete-memory-epic.md`](/Users/levonsh/Projects/smartmail/athlete-memory-epic.md) is the implemented design record for athlete memory and conversation continuity.
- [`/Users/levonsh/Projects/smartmail/response-generation-epic.md`](/Users/levonsh/Projects/smartmail/response-generation-epic.md) is the planned replacement for the current MVP response-composition path.
- [`/Users/levonsh/Projects/smartmail/BACKLOG.md`](/Users/levonsh/Projects/smartmail/BACKLOG.md) is the early/foundational backlog and should not be treated as the current product spec.

The current codebase goes beyond the original verification MVP. It now includes:

- Registration and inbox-possession verification gates before any LLM-capable path
- Cooldowns and verified-user hourly/daily quotas
- Athlete identity, profile, current-plan, plan-history, and progress-snapshot persistence
- Athlete memory and continuity persistence on `coach_profiles`
- LLM-driven conversation-intelligence classification and model routing
- Deterministic + bounded AI-assisted rule-engine behavior from `spec.md` / `rule-engine-epic.md` (RE1 through RE4)
- Strava connect flow and OAuth token storage

## Current Status

This is the code-accurate state as of the current repository:

- Registration and inbox-possession verification are implemented.
- Cooldowns and verified-user hourly/daily quotas are implemented.
- Athlete identity, profile, current plan, plan history, progress snapshots, manual activity snapshots, and rule state persistence are implemented.
- Athlete memory notes and continuity summaries are implemented.
- Missing-profile prompting plus profile extraction/persistence are implemented.
- LLM-driven conversation intelligence and model routing are implemented.
- Strava connect links, OAuth callback handling, athlete connection metadata, and encrypted provider token storage are implemented.
- Initial connector sync into `activities` is not yet a finished end-user flow.
- Rule engine:
  - RE1 is implemented
  - RE2 is implemented
  - RE3 is implemented
  - RE4 is implemented
  - RE5 documentation placeholders are completed (deferred topics only; no production logic changes)

## Next Planned Area

The next major capability under active design is the dedicated response-generation layer. That design lives in [`/Users/levonsh/Projects/smartmail/response-generation-epic.md`](/Users/levonsh/Projects/smartmail/response-generation-epic.md). The current reply path is still MVP scaffolding and is expected to be replaced by RG1.

## LLM Skill Architecture

SmartMail uses specialized LLM workflow skills for bounded tasks in the coaching pipeline. A skill is defined by:
- a narrow responsibility
- a dedicated prompt
- a strict JSON schema
- validation/normalization logic
- isolated tests/eval hooks

A workflow may use the same model as other skills or a different model depending on task needs. Model choice is an implementation detail; the stable contract is the skill boundary plus prompt/schema.

Current athlete-memory skills:
- **Skill A**: extract atomic facts/events from athlete email
- **Skill B**: decide whether memory refresh should run
- **Skill C**: refresh `memory_notes` and `continuity_summary`

These skill boundaries keep athlete-memory behavior isolated, testable, and easier to evolve without changing the lightweight memory storage model.

## Runtime Architecture

### 1. `EmailServiceFunction` (`sam-app/email_service`)

Python Lambda triggered by SNS notifications from SES inbound mail.

Current responsibilities:

- Parse inbound email
- Require sender to exist in the manual `users` table
- Require verified inbox possession via `verified_sessions`
- Throttle verification emails for unverified users
- Enforce verified-user hourly and daily quotas
- Ensure `athlete_id` and baseline profile/progress state exist
- Classify inbound message intent and complexity
- Route mutate/read-only coaching requests through the rule engine when extraction is good enough
- Persist current plan updates and immutable plan history for rule-engine plan changes
- Extract and store profile updates from free-form email
- Extract and store manual activity snapshots from email
- Retrieve bounded athlete memory context for LLM-generated replies
- Refresh athlete memory artifacts before and/or after meaningful interactions
- Generate final coaching reply via skill-owned response-generation workflows

### 2. `mailgptregistration` (`sam-app/email_registration`)

Node.js Lambda behind API Gateway.

Current responsibilities:

- `POST /register`
- Write the email into `users`
- Create a `VERIFY_SESSION` token in `action_tokens`
- Send the registration verification email

### 3. `ActionLinkHandlerFunction` (`sam-app/action_link_handler`)

Python Lambda behind API Gateway.

Current responsibilities:

- `GET /action/{token}`
- Validate single-use expiring action tokens
- Handle `VERIFY_SESSION`
- Handle `CONNECT_STRAVA`
- `GET /oauth/strava/callback`
- Exchange Strava auth code for tokens
- Encrypt provider tokens with KMS
- Store athlete connection metadata and encrypted provider tokens
- Send the post-verification welcome email

## End-to-End Flows

### Inbound Email

```text
SES inbound -> SNS -> EmailServiceFunction
  -> registration gate (`users`)
  -> verification gate (`verified_sessions`)
  -> unverified path: cooldown claim (`rate_limits`) + verify token + verify email
  -> verified path: quota claim (`rate_limits`)
  -> athlete/profile bootstrap
  -> conversation intelligence + model routing
  -> optional rule-engine orchestration + current-plan update
  -> profile/manual-activity extraction
  -> optional pre-reply memory refresh when durable context changed
  -> bounded athlete-memory retrieval for LLM reply path
  -> optional post-reply memory refresh for meaningful interactions
  -> final reply via SES
```

### Registration

```text
POST /register
  -> write `users`
  -> create `VERIFY_SESSION` token
  -> send verification email
```

### Action Link / Verification

```text
GET /action/{token}
  -> token lookup
  -> expiry / used checks
  -> atomic consume
  -> route by action_type
  -> for VERIFY_SESSION: upsert `verified_sessions`
```

### Strava Connect

```text
ready-for-coaching reply
  -> create `CONNECT_STRAVA` token
  -> GET /action/{token}
  -> redirect to Strava authorize URL with one-time OAuth state token
  -> GET /oauth/strava/callback
  -> exchange code for tokens
  -> ensure athlete identity
  -> upsert `athlete_connections`
  -> encrypt + store `provider_tokens`
```

## Rule Engine Scope

The deterministic rule engine in `sam-app/email_service` currently covers RE1-RE4 described in [`/Users/levonsh/Projects/smartmail/rule-engine-epic.md`](/Users/levonsh/Projects/smartmail/rule-engine-epic.md) and [`/Users/levonsh/Projects/smartmail/spec.md`](/Users/levonsh/Projects/smartmail/spec.md):

- canonical contracts and validation
- event-date guards
- performance-intent resolution
- persisted `rule_state`
- phase derivation
- return-to-training precedence
- risk derivation
- anti-oscillation stabilization
- track selection and switching guardrails
- deload logic
- archetype selection
- deterministic weekly skeleton generation
- infeasible-week handling
- orchestrator integration with plan updates
- RE3 signal-first daily action routing and email-ready payload framing
- RE4 planner brief generation, planning-LLM bounded proposals, deterministic validation/repair/fallback, and language rendering guardrails

What is not fully shipped yet:

- connector-driven activity sync feeding the rule engine
- policy decisions for deferred RE5 placeholders (mixed-signal arbitration and LLM-as-a-judge)

## Athlete Memory Scope

Athlete memory is now implemented as lightweight continuity state on `coach_profiles`:

- `memory_notes`
  - durable or semi-durable athlete context
  - each note has a stable integer `memory_note_id`
  - stored with Unix timestamps
- `continuity_summary`
  - short-lived recent coaching context and follow-up state
  - stored as one rolling record per athlete

Current behavior:

- at most 7 memory notes may remain active for one athlete
- retrieval is bounded to all `high` notes plus up to 3 additional recent notes
- retrieval degrades gracefully on missing or invalid persisted memory artifacts
- memory refresh is LLM-assisted and runs only for interactions classified as meaningful
- memory refresh may run before reply generation when newly observed durable context should shape the current reply
- memory refresh may also run after reply generation so persisted continuity stays current for future exchanges
- invalid refresh payloads fail closed and do not overwrite stored memory
- readable date strings are rendered only in LLM-facing prompts; storage remains Unix timestamps

## API Surface

### `POST /register`

Request:

```json
{
  "email": "user@example.com"
}
```

Behavior:

- stores the email in `users`
- creates a `VERIFY_SESSION` token
- sends the verification email

Notes:

- `OPTIONS` is supported for CORS
- non-`POST` methods return `405`

### `GET /action/{token}`

Supported action types in code:

- `VERIFY_SESSION`
- `CONNECT_STRAVA`
- `UNSUBSCRIBE` (stub HTML only)
- `PAUSE_COACHING` (placeholder / not implemented)

Typical response codes:

- `200` success
- `400` invalid token input or unsupported action
- `404` token missing
- `409` token already used
- `410` token expired
- `500` session write failure or callback failure

### `GET /oauth/strava/callback`

Behavior:

- validates OAuth state token
- atomically consumes the state token
- exchanges code with Strava
- stores encrypted provider tokens and connection metadata

## DynamoDB Tables

### Provisioned by `template.yaml`

- `coach_profiles`
  - PK: `athlete_id`
  - athlete profile plus `current_plan`, `memory_notes`, and `continuity_summary`
- `athlete_identities`
  - PK: `email`
  - maps email to `athlete_id`
- `action_tokens`
  - PK: `token_id`
  - TTL: `expires_at`
- `verified_sessions`
  - PK: `email`
  - TTL: `session_expires_at`
- `rate_limits`
  - PK: `email`
- `athlete_connections`
  - PK: `athlete_id`
  - SK: `provider`
  - GSI: `ProviderAthleteLookupIndex`
- `provider_tokens`
  - PK: `connection_id`
- `activities`
  - PK: `athlete_id`
  - SK: `provider_activity_key`
  - GSI: `ActivitiesByAthleteStartTs`
- `daily_metrics`
  - PK: `athlete_id`
  - SK: `metric_date`
- `plan_history`
  - PK: `athlete_id`
  - SK: `plan_version`
- `plan_update_requests`
  - PK: `athlete_id`
  - SK: `logical_request_id`
- `recommendation_log`
  - PK: `athlete_id`
  - SK: `created_at`
- `manual_activity_snapshots`
  - PK: `athlete_id`
  - SK: `snapshot_key`
- `progress_snapshots`
  - PK: `athlete_id`
- `conversation_intelligence`
  - PK: `athlete_id`
  - SK: `message_id`
- `rule_state`
  - PK: `athlete_id`

### Still manual

- `users`
  - PK: `email_address`

### Optional / legacy

- `response_evaluations`
  - referenced by `response_evaluator.py`
  - not provisioned by `template.yaml`
  - current send path has evaluation storage commented out, so this table is not required for the default runtime path

## Manual AWS Setup Outside SAM

SAM provisions the Lambdas, API routes, SNS topic, and DynamoDB tables listed above. You still need to configure:

- SES verified sending identities
- SES inbound receipt rule
- SES receipt rule action that publishes to the SAM-created SNS topic
- optional S3 storage for raw inbound emails if you want SES to archive them
- the manual `users` table

## Key Behavior That Is Live Today

- Unregistered senders do not reach the coaching path
- Registered but unverified senders do not reach the coaching path
- Unverified senders receive at most one verification email per cooldown window
- Verified senders are blocked by concurrency-safe hourly/day quotas before the coaching path
- Conversation intelligence classifies intent and routes between lightweight and advanced response models
- Rule-engine updates can mutate the stored current plan and append plan history
- Missing profile fields trigger a profile-collection reply
- Manual activity snapshots can be extracted from email and roll into progress snapshots
- Athlete memory survives across threads and can personalize the current LLM reply path
- Memory refresh updates durable notes and rolling continuity around meaningful interactions when the trigger boundary is met
- Ready-for-coaching replies can include a Strava connect link

## Project Layout

```text
sam-app/
├── action_link_handler/      # Action links + Strava OAuth callback
├── email_registration/       # Registration API
├── email_service/            # Inbound email pipeline, coaching flow, rule engine
├── e2e/                      # Live endpoint tests
├── template.yaml             # SAM template
└── README.md
```

Inside `email_service/`, the most relevant modules are:

- `app.py` - Lambda entrypoint
- `auth.py` - registration/verification gating
- `rate_limits.py` - verified quota and notice throttling
- `business.py` - conversation intelligence and routing orchestration
- `coaching.py` - profile gate, manual snapshots, final reply path
- `athlete_memory_contract.py` - memory-note and continuity-summary contracts/guardrails
- `memory_refresh_eligibility.py` - refresh trigger classification
- `inbound_rule_router.py` - mutate/read-only rule-engine routing
- `rule_engine_*` - deterministic rule-engine implementation
- `skills/planner/*` - planner and coach-like inference skill workflows (classification/extraction/planning)
- `skills/response_generation/*` - communication and response-generation workflows/prompts
- `openai_responder.py` - compatibility shims only (legacy import surface)
- `dynamodb_models.py` - profile, memory, plan, connector, and snapshot persistence helpers

## Local Development

Prerequisites:

- SAM CLI
- Python 3.13
- Node.js 22
- Docker if you build with containers
- AWS credentials with SES, Lambda, API Gateway, DynamoDB, SNS, and KMS access

Build:

```bash
cd sam-app
sam build --use-container
```

Run the local API:

```bash
sam local start-api
```

Available local routes:

- `POST http://localhost:3000/register`
- `GET http://localhost:3000/action/{token}`
- `GET http://localhost:3000/oauth/strava/callback`

Invoke the inbound email Lambda directly:

```bash
sam local invoke EmailServiceFunction --event events/sns-email-event.json
```

## Testing

Before considering a change done, run:

```bash
python3 -m unittest discover -v -s sam-app/action_link_handler -p "test_*.py"
python3 -m unittest discover -v -p "test_*.py" -s sam-app/email_service
python3 -m unittest -v sam-app/e2e/test_live_endpoints.py
```

Useful focused areas already covered by tests:

- action-link verification and Strava callback behavior
- verified-user quota gate
- conversation intelligence storage/routing
- athlete memory contracts, persistence, retrieval, and refresh guardrails
- current-plan creation and versioned updates
- progress snapshots and manual activity snapshots
- RE1-RE4 rule-engine behavior

## Deployment Notes

Typical deploy flow:

```bash
cd sam-app
sam build --use-container
sam deploy --guided
```

After first deploy:

```bash
sam build --use-container
sam deploy
```

Do not rely on committed secrets in `template.yaml`. Production credentials such as OpenAI keys, Strava secrets, and KMS configuration should be injected through environment-specific deployment config or a secret manager.

## Gaps / Next Likely Work

Based on the roadmap and the current implementation, the main unfinished areas are:

- replace the MVP reply path with the dedicated RG1 response-generation layer
- complete connector data ingestion into `activities` / `daily_metrics`
- formalize policy for deferred RE5 topics (mixed-signal conflicts, LLM-as-a-judge boundaries if ever adopted)
- stronger grounding of replies in synced activity data and the future response brief
- cleanup of historical assumptions in docs and deployment config
