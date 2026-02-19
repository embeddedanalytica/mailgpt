# SmartMail Coach Roadmap

Email-first coaching product (no UI) with a minimal web surface only for action links (verification, OAuth connect, etc.).

This roadmap tracks work as discrete stories with acceptance criteria. Each story is “DONE” only when:
1) code is implemented + deployed (or build+deploy verified),
2) acceptance tests pass,
3) ROADMAP checkboxes are updated.

---

## Core Principles (from DECISIONS.md)
- Personal data is only shared after inbox-possession verification.
- Unverified inbound requests never trigger LLM calls.
- Abuse must be economically unreasonable (cooldowns, rate limits).
- One action-link endpoint: `GET /action/{token}`.
- Action tokens are single-use and expiring.

---

## Current Status Summary
**Implemented through Story H2 (inclusive).**
- ✅ Action link endpoint with token validation and session creation
- ✅ Inbound verification gate (unverified -> verify email; verified -> continue)
- ✅ Verification-email cooldown with 30-minute window (anti-spam, anti-cost)
- ✅ Verified-user hourly/day quota gate before LLM-capable path
- ✅ Throttled rate-limit notices + fail-closed on quota storage errors

---

# Phase 0 — Foundations (DONE)

## A–F: Action Link Endpoint + Session Verification (DONE)
**Outcome:** `/action/{token}` supports token lookup, expiry, single-use, and `VERIFY_SESSION` writes to `verified_sessions`.

### Definition of Done
- [x] API Gateway route exists: `GET /action/{token}`.
- [x] Missing token -> `404` HTML “invalid or expired”.
- [x] Expired token -> `410` HTML “expired” and does NOT consume token.
- [x] Used token -> `409` HTML “already used”.
- [x] Valid token (first use) -> consumes token (race-safe conditional update).
- [x] `VERIFY_SESSION` action type writes/updates `verified_sessions` and returns ✅ Verified HTML.
- [x] Robustness must-fixes:
  - [x] `SESSION_TTL_DAYS` parsed safely with default.
  - [x] Missing/empty token path param returns `400` safe HTML.
  - [x] Consistent outcome logging in ActionLinkHandlerFunction.
  - [x] Session write failure returns `500` safe HTML (no retries, token remains consumed).

### Notes
- `action_tokens` TTL is based on `expires_at`.
- `verified_sessions` TTL is based on `session_expires_at`.

---

# Phase 1 — Email Coaching MVP (No connectors)

## G1: Inbound Verification Gate + Verify Email Issuance (DONE)
**Outcome:** Email is usable as the UI while preventing spoof-based data leakage and LLM cost abuse.

### Definition of Done
- [x] Inbound email processing checks `verified_sessions` for sender.
- [x] If sender is NOT verified:
  - [x] Do NOT call LLM.
  - [x] Create `VERIFY_SESSION` action token in `action_tokens` with `expires_at` = now + `VERIFY_TOKEN_TTL_MINUTES`.
  - [x] Send verification email with link: `${ACTION_BASE_URL}{token_id}`.
  - [x] Return / stop processing (no coaching response sent).
- [x] If sender is verified:
  - [x] Proceed to response generation path (placeholder acceptable at this stage; OpenAI responses “when implemented”).

### Acceptance tests
- [x] Unverified sender receives a verification email with link.
- [x] Clicking link creates session.
- [x] Next inbound email from same sender follows verified path.

---

## G2: Verification Email Cooldown (Anti-Spam / Anti-Cost) (DONE)
**Outcome:** Prevent repeated verify emails during spoof floods and keep the system economically hostile to attackers.

### Current configuration
- Cooldown env var: `VERIFY_EMAIL_COOLDOWN_MINUTES`
- Cooldown default: **30 minutes**
- Token TTL: `VERIFY_TOKEN_TTL_MINUTES` (default 30)

### Definition of Done
- [x] Unverified inbound requests never trigger LLM.
- [x] Verification emails are throttled per sender:
  - [x] At most 1 verification email per cooldown window.
  - [x] Cooldown is enforced using DynamoDB atomic update (race-safe).
  - [x] When cooldown active: drop silently (no email, no token, no LLM).
- [x] Resend behavior works with 30-minute TTL/cooldown expectations.

### Acceptance tests
- [x] Spoof flood (many unverified emails) results in only one verification email within cooldown.
- [x] Concurrency test: two simultaneous unverified requests -> only one verification email sent.

---

# Phase 1.5 — Cost & Safety Controls (DONE)

## H: Verified User Rate Limiting (DONE)
**Goal:** Cap LLM calls for verified users (hour/day) and throttle rate-limit notices.

### Definition of Done
- [x] Enforce per-user limits before calling LLM.
- [x] Concurrency-safe counter updates in `rate_limits`.
- [x] Rate-limit notices throttled (avoid spamming users).
- [x] Over-limit requests do NOT call LLM.

### H-1: Verified user quota gate (hour + day) (DONE)
- [x] Hourly and daily per-sender quotas enforced on verified path.
- [x] Quota check happens before any LLM-capable path.
- [x] UTC bucket rollover implemented:
  - [x] `hour_bucket = YYYYMMDDHH`
  - [x] `day_bucket = YYYYMMDD`
- [x] Race-safe claim when quota remaining is 1 (at most one request proceeds).
- [x] Tests: under-limit allow, hourly block, daily block, rollover reset, concurrency.

### H-2: Throttled notices + fail-closed on Dynamo issues (DONE)
- [x] Optional rate-limit notice email for blocked verified requests.
- [x] Notice sending throttled per sender via cooldown window.
- [x] Concurrency-safe notice cooldown claim (at most one notice/window).
- [x] Non-conditional Dynamo errors fail closed (blocked, no LLM) and are logged.
- [x] Tests: first notice send, cooldown suppression, notice concurrency, Dynamo-error blocked path.

---

## I: Coaching Profile Capture (TODO)
**Goal:** Capture goal + weekly time budget + sport preferences via email and store in `coach_profiles`.

### Definition of Done
- [x] For verified users, prompt for missing profile fields.
- [x] Parse simple replies and persist to `coach_profiles`.
- [ ] Use profile values to personalize responses.

---

# Phase 2 — Connectors MVP (Strava first)

## J: CONNECT_STRAVA Action Link + OAuth Start (TODO)
- [ ] Create `CONNECT_STRAVA` tokens and route in `/action/{token}`.
- [ ] Redirect to Strava OAuth authorize URL.

## K: OAuth Callback + Token Storage (TODO)
- [ ] Implement callback endpoint to exchange code for tokens.
- [ ] Store tokens securely (encrypted) in a provider token store.

## L: Initial Sync + Normalized Activity Storage (TODO)
- [ ] Fetch last N days of activities (e.g., 30).
- [ ] Normalize and store in `activities` table.
- [ ] Avoid duplicates.

---

# Phase 3 — Insights Delivery

## M: Weekly Digest (TODO)
- [ ] EventBridge weekly schedule sends summary email.
- [ ] Digest includes 1–3 insights + suggested next step.

## N: Reply Q&A Grounded in Recent Data (TODO)
- [ ] User replies with questions; system uses recent activities + profile.
- [ ] Responses thread correctly.

## O: Post-Activity Insight (TODO)
- [ ] On new activity ingestion, send short insight + suggestion.

---

# Phase 4 — Training Recommendations

## P: 7-Day Plan Generator (TODO)
- [ ] Generate weekly plan using goal + time + recent load.
- [ ] User can reply “harder/easier/adjust”.

## Q: Weekly Adaptation Loop (TODO)
- [ ] Compare plan vs actual and adapt next plan.
- [ ] Show adherence + load trend.

---

# Edge Cases / Hardening (Later)
- DMARC/SPF/DKIM scoring / inbound auth signals
- Global circuit breaker / incident mode
- Caching + dedupe
- Privacy modes (verify every time)
- Export/delete flows
- Garmin connector (after Strava is stable)