# Live E2E Tests

These tests validate deployed SmartMail endpoints against production routing and token flows.

## Run

```bash
cd /Users/levonsh/Projects/smartmail/sam-app
python3 -m unittest tests/e2e/test_live_endpoints.py
```

## Requirements

- AWS CLI configured for the target account (`us-west-2`)
- Access to DynamoDB tables:
  - `action_tokens`
  - `verified_sessions`
- Public endpoint `https://geniml.com` reachable

## CI

Workflow file:

- `.github/workflows/e2e-live-endpoints.yml`

It runs:

- On-demand (`workflow_dispatch`)
- Nightly at `09:00 UTC`

Configure one auth mode in repo secrets:

- Preferred OIDC: `AWS_ROLE_TO_ASSUME`
- Or access keys: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
