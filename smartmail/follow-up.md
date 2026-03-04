# Follow-up Topics (Deferred)

These items were explicitly deferred and are not yet part of the implementation contract.

## 5) Risk trend requiring history (deferred)
- Status: `skip for now`
- Deferred question: Should worsening-detection depend on rolling 2-3 check-ins, and what minimum history is required before escalating from yellow to red_b?
- Potential future rule: add confidence levels when history is sparse.

## 7) Ambiguous main sport tie-breakers (deferred)
- Status: `skip for now`
- Deferred question: For hybrid athletes with near-equal volume split, should we lock main sport for a fixed window (for example 2-4 weeks) to prevent plan churn?
- Potential future rule: retain last declared main sport unless athlete explicitly changes it.

## 10) Idempotency/concurrency + double-session day semantics (deferred)
- Status: `do not implement yet`
- User scenario to support later: morning bike + evening swim on the same day is valid and should not be treated as duplication/conflict.
- Open decisions for later:
  - Should same-day two-session plans be allowed only when both are easy, or allow one quality + one easy?
  - How should hard-day spacing treat two sessions in one calendar day?
  - What storage keying policy distinguishes valid dual sessions from duplicate submissions?
- Proposed direction for discussion:
  - treat a day as one "load bucket" for hard-day spacing
  - allow dual sessions only if total daily intensity budget is respected
  - preserve modality diversity (for example bike + swim) as valid cross-training pattern
