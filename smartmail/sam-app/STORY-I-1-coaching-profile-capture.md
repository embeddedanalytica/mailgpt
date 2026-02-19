# Story I-1 — Coaching profile capture: profile-status gate (goal, weekly time, sport)

## Why

Coaching advice should only start once the system has minimal context: goal, weekly time budget, and sport preferences. Until then, the user is not "ready for coaching"—we are still missing context. This story makes that gate explicit: every response is driven by the **state of the user's profile** (what's present, what's missing), not by reply order or email count. New users naturally get profile collection first because their profile is empty; the same logic applies to any user with an incomplete profile.

## What

1. Define the minimal set of profile fields required for "ready for coaching" (e.g. goal, weekly time budget in minutes, sport preferences). Coaching advice is not offered until all required fields are present (or explicitly skipped/unknown per product rule).
2. On the verified path (after verification and quota gates), before deciding what to reply, **read the sender's profile** and determine status: **ready for coaching** (all required fields present) vs **still missing context** (one or more required fields missing).
3. If **missing context:** the reply must only gather or clarify missing fields (e.g. ask for one or more missing values, or parse the inbound email into structured fields and persist). Do not generate coaching advice in this case.
4. If **ready for coaching:** the system may proceed to generate a coaching (or placeholder) response for this story; no obligation to ask profile questions.
5. Profile reads and writes are keyed by verified sender; only persist values that are derived from the current exchange (no overwriting with empty or unparsed data). Concurrent requests for the same sender must not corrupt the profile (defined merge or last-write behavior).
6. When using the LLM for profile-related work (e.g. deciding what's missing, parsing a reply into fields), apply the same cost and rate limits as the rest of the verified path; skip LLM when unverified or over quota.
7. Do not log full email body or full profile content; log only outcome markers and non-sensitive metadata.

## Preconditions / Dependencies

- Stories A–F (action link, session verification), G1–G2 (verification gate, cooldown), and H (verified-user quota gate) are done.
- Verified path exists: sender in verified_sessions and has passed the hourly/daily quota check before any LLM use.
- coach_profiles store exists and is writable; schema supports at least goal, weekly time budget (minutes), and sport preferences for the sender.
- README/DECISIONS: email as UI, unverified never calls LLM, verified path remains cost-controlled.

## Scope guardrails (do NOT do)

- Do not drive behavior by "first reply," "second reply," or any email/response counter; only by profile status (required fields present vs missing).
- Do not add new action link types or new endpoints for profile capture; capture happens in-reply via email only.
- Do not implement "use profile to personalize responses" in this story (that is I-2).
- Do not add retries/backoff for profile write beyond what is already in scope for the verified path.
- Do not log sensitive content (email body, full profile) in logs.

## Acceptance criteria

- **AC1:** For a verified sender whose profile is missing one or more required fields, the system does not send coaching advice; the reply is only for gathering or clarifying those fields (e.g. ask for missing value(s) or parse inbound and persist).
- **AC2:** For a verified sender whose profile has all required fields (or they are marked skipped/unknown), the system treats them as ready for coaching and may send a coaching or placeholder reply (no obligation to ask profile questions).
- **AC3:** The decision "ready for coaching" vs "missing context" is based solely on the current state of the profile (which required fields are present), not on reply count or email sequence.
- **AC4:** When the system parses inbound content into profile fields, it persists only derived/parsed values; profile updates are keyed by verified sender; concurrent requests for the same sender do not corrupt the profile.
- **AC5:** Over-quota or unverified senders never trigger LLM calls; behavior matches existing verified/quota gates.
- **AC6:** Outcome of each handling (e.g. profile_missing_context, profile_ready_for_coaching, profile_updated) is observable via a small fixed vocabulary of markers; no sensitive data in logs.

## Minimal tests

- **T1:** Verified sender, profile empty or missing required fields → reply does not contain coaching advice; reply only gathers/clarifies or parses and persists. (AC1)
- **T2:** Verified sender, profile has all required fields → reply may be coaching or placeholder; system does not force profile questions. (AC2)
- **T3:** Same sender: first request with empty profile → collection behavior; after profile is populated (e.g. in test), next request → ready-for-coaching behavior. Logic driven by profile state, not by "first vs second" email. (AC3)
- **T4:** Profile update from parsed content; concurrent requests for same sender → no corrupted profile. (AC4)
- **T5:** Verified sender over quota → no LLM call; same as existing quota-block behavior. (AC5)
- **T6:** Handler emits expected outcome markers and no sensitive content in logs. (AC6)

## AC-to-test mapping

- AC1 → T1  
- AC2 → T2  
- AC3 → T3  
- AC4 → T4  
- AC5 → T5  
- AC6 → T6  

## Definition of Done

- ACs met.
- Tests pass.
- ROADMAP updated (mark I-1 or profile-capture sub-item progress).
- DECISIONS updated only if a new decision is introduced (e.g. definition of "ready for coaching" or required minimal fields).

---

## LLM use (this story)

- **Role:** Onboarding (what to ask when context is missing); Extraction (parse reply into structured profile fields).
- **Output constraints:** Bounded set of fields (goal, weekly_time_budget_minutes, sports); low-confidence or unparseable → treat as unknown or ask to clarify; safe fallback = ask one clarifying question.
- **Model flexibility:** Model choice configurable by task type; swapping model must not require logic refactors.
- **Cost posture:** LLM invoked only on verified path after quota gate; skip when unverified, over quota, or storage/read failure.

---

## Observability

- Emit outcome markers (e.g. `profile_missing_context`, `profile_ready_for_coaching`, `profile_updated`) without logging email body or full profile content.

---

**Next story ID(s):** I-2 (use profile values to personalize responses).
