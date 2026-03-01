# EPIC 1 — Hardening Patch Backlog

These are small, high-ROI follow-up stories to make Epic 1 durable under retries, concurrency, and real-world email input variation.  
They do **not** add new product UX—only correctness and stability.

---

# EPIC 1H — Data Integrity & Reliability

---

## Story 1H.1 — Canonicalize Email Identity Keys

### Why
Email casing/whitespace differences can create duplicate athletes and break cross-thread continuity.

### What
Ensure athlete identity mapping uses a canonicalized email format for all reads/writes.

### Acceptance Criteria
- All identity lookups and writes use `canonical_email`, defined as:
  - trimmed (no leading/trailing spaces)
  - lowercased
- `ensure_athlete_id_for_email(email)` must return the same `athlete_id` for:
  - `User@Email.com`
  - ` user@email.com `
  - `USER@EMAIL.COM`
- `get_athlete_id_for_email(email)` uses the canonical form as well.
- No user-facing behavior changes.

---

## Story 1H.2 — Prevent Manual Snapshot Collisions

### Why
Using `(athlete_id, timestamp)` risks overwriting snapshots when multiple events share the same second or when retries occur.

### What
Ensure manual activity snapshots are uniquely recorded even when timestamps collide.

### Acceptance Criteria
- Inserting two manual snapshots for the same athlete with the same timestamp must not overwrite or drop one.
- The data model supports multiple snapshots within the same second.
- Snapshot retrieval by time range continues to work.
- No connector requirements introduced.

Notes:
- Exact key strategy is implementation-defined (e.g., higher-resolution timestamp or composite SK).

---

## Story 1H.3 — Persist Immutable Plan History

### Why
Plan continuity and explainability require a durable, append-only record of plan changes across threads.

### What
Persist plan history as an immutable append-only record for every plan update.

### Acceptance Criteria
- Every successful plan update appends a new history entry.
- History entries are persisted (not only in logs) and retrievable by athlete_id.
- History is append-only (no in-place mutation of existing entries).
- Each history entry includes at minimum:
  - `plan_version`
  - `updated_at`
  - `rationale` (optional allowed but stored if provided)
  - `changes_from_previous` (optional allowed but stored if provided)
- Current plan remains retrievable as the “active” plan.
- No changes to plan generation logic are required in this story.

---

## Story 1H.4 — Make Plan Updates Safe Under Retries and Concurrency

### Why
Email/message processing can retry. Concurrent updates can cause duplicate increments, conflicting current plans, or duplicated history entries.

### What
Make `update_current_plan` safe and consistent under retries and concurrent invocations for the same athlete.

### Acceptance Criteria
- Plan version increments must be atomic per athlete.
- Under repeated identical update attempts (e.g., retry), the system must not:
  - increment plan_version twice for the same logical update
  - create duplicate plan history entries for the same logical update
- If two different updates occur near-simultaneously:
  - final current_plan is consistent and reflects a valid last-write order
  - plan_history records both updates in correct order (by plan_version or timestamp)
- A deterministic mechanism exists to associate an update with a “logical request” (e.g., request id / message id) for idempotency.
- No user-facing behavior changes.

---

# Recommended Tests (Additions)

These tests harden behavior and prevent regressions.

## Identity
- Canonical email mapping returns same athlete_id for casing/whitespace variants.

## Manual Snapshots
- Two snapshots with same timestamp are both stored (no overwrite).
- Range query returns both.

## Plan History
- Updating plan appends exactly one new immutable history entry.
- History entries include required metadata fields.

## Plan Update Safety
- Retry of the same logical update does not double-increment plan_version.
- Concurrent updates result in consistent current_plan and ordered history.

---