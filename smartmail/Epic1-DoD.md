# EPIC 1 Hardening — Definition of Done (DoD)

This DoD applies to:
- Story 1H.1 — Canonicalize Email Identity Keys
- Story 1H.2 — Prevent Manual Snapshot Collisions
- Story 1H.3 — Persist Immutable Plan History
- Story 1H.4 — Safe Plan Updates Under Retries & Concurrency

All items below must be satisfied before marking the patch complete.

---

# 1. Identity Integrity

## Functional Criteria

- [ ] Email identity lookup uses canonicalized email (trim + lowercase).
- [ ] `ensure_athlete_id_for_email()` returns the same `athlete_id` for casing/whitespace variants.
- [ ] `get_athlete_id_for_email()` also uses canonical form.
- [ ] No duplicate athlete records are created due to email formatting differences.

## Test Criteria

- [ ] Unit test verifies canonical mapping behavior.
- [ ] Regression test ensures old identity behavior still works.

---

# 2. Manual Activity Snapshot Safety

## Functional Criteria

- [ ] Two snapshots with the same timestamp do not overwrite each other.
- [ ] Multiple snapshots can exist within the same second.
- [ ] Retrieval by athlete_id and time range returns all snapshots.
- [ ] No data loss under retry conditions.

## Test Criteria

- [ ] Insert two snapshots with identical timestamps → both persist.
- [ ] Range query returns both entries.
- [ ] Retry simulation does not overwrite previous record.

---

# 3. Immutable Plan History

## Functional Criteria

- [ ] Every successful plan update appends a history entry.
- [ ] Plan history is persisted (not only logged).
- [ ] History entries are append-only (no mutation allowed).
- [ ] Each history entry includes:
  - [ ] plan_version
  - [ ] updated_at
  - [ ] rationale (if provided)
  - [ ] changes_from_previous (if provided)
- [ ] Current active plan remains separately retrievable.
- [ ] Historical records remain unchanged after future updates.

## Test Criteria

- [ ] Updating plan twice results in two distinct history records.
- [ ] Historical records are not overwritten or modified.
- [ ] History can be retrieved by athlete_id.

---

# 4. Plan Update Atomicity & Idempotency

## Functional Criteria

- [ ] Plan version increments are atomic per athlete.
- [ ] Retried identical update does NOT:
  - [ ] increment version twice
  - [ ] duplicate history entries
- [ ] Concurrent distinct updates result in:
  - [ ] consistent final current_plan
  - [ ] ordered plan history entries
- [ ] Logical update identifier exists (e.g., request/message id) to support idempotency.
- [ ] No user-visible errors occur during safe retries.

## Test Criteria

- [ ] Simulated retry of same update does not double-increment.
- [ ] Simulated concurrent updates result in consistent state.
- [ ] Version ordering remains monotonic.

---

# 5. No UX Regression

- [ ] Profile retrieval continues to work across threads.
- [ ] Current plan retrieval unchanged.
- [ ] Progress snapshot behavior unchanged.
- [ ] No changes required to existing Epic 1 business logic.
- [ ] Existing passing tests remain green.

---

# 6. Deployment Safety

- [ ] Infrastructure updated if new indexes/keys required.
- [ ] No destructive schema changes to existing data.
- [ ] Backward compatibility maintained for existing athlete records.
- [ ] Rollback plan documented (if applicable).

---

# Sign-Off Criteria

Epic 1 Hardening is considered complete when:

- All functional criteria are satisfied.
- All required tests pass.
- No regression in Epic 1 baseline behavior.
- Code review confirms append-only history and atomic plan updates.