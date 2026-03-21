# SmartMail — Claude Working Guide

Email-first AI coaching service on AWS SAM. Inbound email is the primary UI.
Pipeline: `SES → SNS → app.py (auth + quota) → business.py → coaching.py → skills/* → reply`

**Lambdas:** `EmailServiceFunction` (email_service/, Python), `mailgptregistration` (email_registration/, Node.js), `ActionLinkHandlerFunction` (action_link_handler/, Python)

## True Invariants (Never Break)

1. **Security gates** — in order: unregistered → registration reply; unverified → verification email; verified → quota claim. All before any LLM call. Owned by `auth.py` + `rate_limits.py`.
2. **Rule engine authority** — `rule_engine.py` is sole authority on training state, plan validation, track/deload/archetype selection. No LLM output may override it.
3. **DynamoDB schema** — table structure is fixed by `template.yaml`. Access patterns must work within existing schema.
4. **Prompt ownership** — LLM prompts live in skill packages only. `email_copy.py` is transactional copy only.

## Sub-Guides

| Area | Guide |
|---|---|
| Build, deploy, DynamoDB reference | `sam-app/CLAUDE.md` |
| Email service pipeline + module map | `sam-app/email_service/CLAUDE.md` |
| Skill unit model + package index | `sam-app/email_service/skills/CLAUDE.md` |
| Memory subsystem | `sam-app/email_service/skills/memory/CLAUDE.md` |
| Response generation skill | `sam-app/email_service/skills/response_generation/CLAUDE.md` |
