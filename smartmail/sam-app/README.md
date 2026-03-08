# SmartMail

Email-first coaching service built on AWS SAM. Inbound email is the primary UI. A small HTTP surface exists for registration, action links, and the Strava OAuth callback.

The current codebase goes beyond the original verification MVP. It now includes:

- Registration and inbox-possession verification gates before any LLM-capable path
- Cooldowns and verified-user hourly/daily quotas
- Athlete identity, profile, current-plan, plan-history, and progress-snapshot persistence
- LLM-driven conversation-intelligence classification and model routing
- Deterministic rule-engine foundations from `spec.md` / `rule-engine-epic.md` (RE1 and RE2)
- Strava connect flow and OAuth token storage

## Current Status

This is the code-accurate state as of the current repository:

- Roadmap Phase 0 and Phase 1.5 are implemented through `H2`
- Roadmap `I` is partially implemented:
  - Missing-profile prompting is live
  - Profile field extraction and persistence are live
  - Profile-based personalization exists in the coaching path, but not as a cleanly isolated roadmap story boundary
- Roadmap `J/K` are partially implemented in code:
  - `CONNECT_STRAVA` action links exist
  - `/oauth/strava/callback` exists
  - athlete connection metadata and encrypted provider tokens are stored
  - initial sync into `activities` is not wired as a finished product flow
- Rule engine:
  - RE1 is implemented
  - RE2 is implemented
  - RE3 is implemented
  - RE4 and later epics are not fully shipped

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
- Generate final coaching reply via OpenAI-backed responders

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

The deterministic rule engine in `sam-app/email_service` currently covers the RE1/RE2 foundation described in [`/Users/levonsh/Projects/smartmail/rule-engine-epic.md`](/Users/levonsh/Projects/smartmail/rule-engine-epic.md) and [`/Users/levonsh/Projects/smartmail/spec.md`](/Users/levonsh/Projects/smartmail/spec.md):

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

What is not fully shipped yet:

- RE4 AI-assisted constrained planning
- connector-driven activity sync feeding the rule engine

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
  - athlete profile plus `current_plan`
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
- `inbound_rule_router.py` - mutate/read-only rule-engine routing
- `rule_engine_*` - deterministic rule-engine implementation
- `dynamodb_models.py` - profile, plan, connector, and snapshot persistence helpers

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
- current-plan creation and versioned updates
- progress snapshots and manual activity snapshots
- RE1 and RE2 rule-engine behavior

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

- complete connector data ingestion into `activities` / `daily_metrics`
- RE3 session-routing and email-ready action payloads
- RE4 constrained AI planning
- stronger grounding of replies in synced activity data
- cleanup of historical assumptions in docs and deployment config
