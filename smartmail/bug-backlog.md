# Bug backlog

## 1. Garbage characters in email reply body
**Status** Fixed
**Context:** Replying to an email generates garbage characters in the reply body (e.g. - Ens\u06b6^\uc18b$ry\u01e2_`\u04d0Nhwi^r\u0628$rj)pznIMt\u.
**Desired Behaviour** If the email is not a follow up or a coaching adivce but a canned respose (e.g. invitiation to a registration etc) reply should not be included, otherwise reply should contain the orgiginal message.

## 2. Long-horizon memory drops core training backbone when medium-value details accumulate
**Status** Fixed
**Context:** In the long-horizon athlete-memory bench, the system can retain secondary facts such as equipment details or support habits while losing the core planning backbone that a coach actually needs. The clearest example is `AM-LH-003`, where the model preserved details like the power meter, fan, tire kit, garage skills setup, and mobility class while failing to reliably preserve the durable structure: weekday trainer pattern, weekend outdoor flexibility, and the athlete's main planning anchors after the schedule reversal.
**Desired Behaviour** Long-horizon memory should prioritize durable planning truths over medium-value descriptive details. When memory is under pressure, core schedule constraints, major goal anchors, and structurally important changes must survive ahead of convenience details or gear notes.
**Verification:** Confirmed fixed in fresh long-horizon reruns on March 23, 2026 from `/private/tmp/am-lh-002-finalcheck-20260323`: `AM-LH-002` passed 3/3 with `final_score=1.0`, no durable-truth misses, no stale-assumption risks, and no salience/compression failures. Earlier `AM-LH-003` reruns on March 23, 2026 from `/private/tmp/am2-rerun-20260323` also improved to 2/3 `ok` with the remaining mismatch traced to bench evaluation rather than memory loss; subsequent `AM-LH-002` artifacts showed the swim-limiter fact persisted in storage and retrieval context.

## 3. Durable schedule reversals do not fully retire the old coaching assumption
**Status** Fixed
**Context:** In the same long-horizon bench, once a durable constraint changes, the old rule can remain actionable instead of being cleanly retired. In `AM-LH-003`, the athlete moved from a Sunday-only outdoor rule to broader weekend flexibility, but the old Sunday-only assumption still appeared operationally relevant late in the scenario.
**Desired Behaviour** When the athlete explicitly replaces a durable scheduling rule with a new one, the old rule should be retired cleanly so it no longer influences planning or retrieval. The updated rule should become the active coaching assumption without stale fallback behavior.
**Verification:** Confirmed fixed in fresh long-horizon reruns on March 22, 2026 from `/private/tmp/am-lh-validate`: `AM-LH-003` reported `Stale Assumption Risks: none`, so the old schedule assumption did not remain operationally active in that rerun.

## 4. Gravel outdoor-ride availability broadening keeps the stale Sunday-only anchor
**Status** Fixed
**Context:** In the athlete-memory benchmark rerun, `AM-003 run 1` correctly captured the athlete's correction that outdoor gravel rides are no longer Sunday-only because Saturdays also opened up. But the stored memory merged the new fact into the old one (`mostly Sundays and now also possible on Saturdays`) instead of retiring the old Sunday-only planning assumption.
**Desired Behaviour** When an athlete broadens a recurring scheduling constraint, the old narrower rule should be retired. The durable memory should represent the new availability directly, without preserving the stale anchor that Sunday is the primary or default outdoor ride day.
**Verification:** Confirmed fixed in targeted reruns on March 22, 2026: `AM-003` passed 3/3 in `/tmp/am-short-targeted-rerun`.

## 5. Loosened swim-frequency cap leaves the old three-mornings limit operational
**Status** Fixed
**Context:** In `AM-005 run 1` and `AM-005 run 3`, the athlete explicitly said the old cap of three weekday morning swims was outdated because a fourth weekday morning opened up. The final memory still treated `three weekday mornings` as actionable.
**Desired Behaviour** When an athlete says an old training-frequency cap is no longer true, the system should retire the old limit and replace it with the new availability. Coaches should not continue planning against the obsolete cap.
**Verification:** Confirmed fixed in fresh short-horizon reruns on March 22, 2026 from `/private/tmp/am-short-validate`: `AM-005` still failed overall, but `Stale Assumption Risks: none`, so the old three-mornings cap did not remain operationally active in that rerun. Remaining failure was loss of `1500 free`, which is a separate retention issue.

## 6. Primary swim goal can disappear from final durable memory
**Status** Fixed
**Context:** In `AM-005 run 2`, the athlete's central long-term goal, `summer 1500 free`, was present early but missing from final durable memory and final retrieval support.
**Desired Behaviour** Primary event or goal anchors introduced by the athlete should remain pinned in durable memory unless explicitly retired or replaced. Final retrieval should reliably surface them for coaching decisions.
**Verification:** Confirmed fixed in targeted reruns on March 22, 2026: across 3 `AM-005` reruns, the primary swim goal remained present in final durable memory and retrieval support.

## 7. Corrected weekly recovery-day assumption can remain active after explicit reversal
**Status** Fixed
**Context:** In `AM-007 run 3`, the athlete updated the weekly structure, but the old `recovery-only sunday` assumption still appeared actionable in the final state.
**Desired Behaviour** When an athlete explicitly changes a recurring weekly recovery or training-day rule, the superseded assumption should be retired and no longer influence downstream planning or retrieval.
**Verification:** Confirmed fixed in fresh short-horizon reruns on March 22, 2026 from `/private/tmp/am-short-validate`: `AM-007` passed with `pass_rate=1.0`, `final_score_avg=1.0`, and no stale assumption risks.

## 8. New recurring strength session can fail to promote into durable memory
**Status** Fixed
**Context:** In `AM-007 run 3`, `monday team lift` should have become a durable recurring planning fact, but it was missing from final durable memory and retrieval support.
**Desired Behaviour** Newly introduced recurring weekly sessions that materially affect load and recovery should be promoted into durable memory and survive to final retrieval.
**Verification:** Confirmed fixed in targeted reruns on March 22, 2026: the `AM-007` reruns did not reproduce loss of the `monday team lift` durable fact.

## 9. Moved rowing anchor leaves the old long-erg Saturday assumption active
**Status** Fixed
**Context:** In `AM-009 run 2`, the athlete changed the weekly rowing structure, but the old `long erg saturday` assumption remained actionable in final retrieval.
**Desired Behaviour** When a recurring workout anchor moves to a different day or structure, the old anchor should be retired cleanly and replaced with the new one so coaching plans use the current weekly pattern.
**Verification:** Confirmed fixed in fresh short-horizon reruns on March 22, 2026 from `/private/tmp/am-short-validate`: `AM-009` passed with `pass_rate=1.0`, `final_score_avg=1.0`, and no stale assumption risks.

## 10. Basketball season-goal memory is not normalized robustly enough
**Status** Open
**Context:** In `AM-012 run 1` and `AM-012 run 2`, the athlete's goal of training for `summer rec league` was paraphrased in memory, but the durable goal did not remain stable enough to satisfy final durable memory and retrieval checks.
**Desired Behaviour** Season-goal facts should be canonicalized into a stable durable object so common paraphrases like `summer recreational basketball league` still preserve the athlete's core competitive goal at final retrieval.

## 11. New recurring ski-erg session can fail to become durable memory
**Status** Fixed
**Context:** In `AM-014 run 1`, the athlete added a permanent `Wednesday ski-erg group`, but that recurring sport-specific session never appeared in final durable memory or retrieval support.
**Desired Behaviour** New recurring sessions with clear long-term planning value should be promoted into durable memory, especially when they are sport-specific and explicitly described as permanent.
**Verification:** Confirmed fixed in targeted reruns on March 22, 2026: `AM-014` passed 3/3 and retained the `Wednesday ski-erg group` in durable memory and retrieval support.

## 12. Removed commute-based Monday block can remain active after schedule change
**Status** Fixed
**Context:** In `AM-014 run 1`, the athlete explicitly said Mondays were now open because their commute changed, but final memory still treated `mondays off-limits` as actionable.
**Desired Behaviour** When an athlete removes a commute-driven or logistics-driven schedule blocker, the old blocker should be retired so the coach can plan against the updated weekly availability.
**Verification:** Confirmed fixed in targeted reruns on March 22, 2026: `AM-014` passed 3/3 and did not keep the old Monday blocker active.

## 13. Achilles rebuild flow can prescribe tempo work before stability or clinical clearance is established
**Status** Open
**Context:** In [`sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl`](/Users/levonsh/Projects/smartmail/sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl), turn 2 gives an athlete with a recent layoff and mild Achilles tightness a first-week plan that includes `Session C — Short tempo`, even though the coach had just asked whether the athlete was pain-free and whether a clinician had cleared them to resume training. The same flow keeps reintroducing tempo on turns 4, 5, and 6 while the athlete is still in a cautious rebuild and clearance remains unconfirmed later in the run.
**Desired Behaviour** Early comeback plans for athletes reporting Achilles sensitivity or incomplete return-to-run clearance should default to easy aerobic and low-risk strength/mobility work until the athlete has demonstrated stable symptom response and any necessary clearance is known. The coach should not add tempo or other moderate-hard quality work merely because the athlete is intermediate or available four days per week.

## 14. Coaching reply can contradict its own “fully aerobic” guidance with harder prescribed work
**Status** Open
**Context:** In [`sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl`](/Users/levonsh/Projects/smartmail/sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl), turn 19 answers the athlete’s question about whether to keep the week fully aerobic by saying `keep this week fully aerobic`, but the same reply then prescribes a `Wednesday: Tempo session 20–30 minutes at a controlled effort (RPE 6–7)` and also allows optional strides after Monday’s easy run. That makes the guidance internally inconsistent and operationally confusing.
**Desired Behaviour** When the coach says a week should remain fully aerobic, the prescribed sessions should stay fully aerobic as well. If the system wants to introduce strides or tempo, it should say that explicitly and explain why, rather than mixing incompatible instructions in the same reply.

## 15. rule_engine_state can mutate durable memory instead of confirm-only
**Status** Open
**Context:** The AM2 durable-memory contract intends `rule_engine_state` to be confirm-only support evidence, but the current candidate validator/reducer path may still allow a targeted `upsert` sourced from `rule_engine_state` to rewrite an existing durable fact.
**Desired Behaviour** `rule_engine_state` should be allowed to confirm existing durable facts only. It should not create new durable facts, rewrite existing fact summaries, or retire facts.

## 16. New-create upsert can bypass target_id and replace an existing fact by canonical key
**Status** Open
**Context:** The AM2 design is intended to make existing-fact mutation ID-based. But if the model emits a new-create `upsert` with the same canonical key as an existing active fact, the reducer's canonical-key backstop can effectively replace the old fact with the new one, losing stable identity semantics and bypassing the `target_id` requirement.
**Desired Behaviour** If an active fact with the same canonical key already exists, the system should require an explicit ID-targeted update path rather than allowing a create-and-dedupe fallback to mutate the fact implicitly.

## 17. Reversal backstop can be satisfied by an unrelated targeted update
**Status** Open
**Context:** The AM2 reversal retry heuristic is meant to catch missed schedule/constraint reversals, but it may currently treat any targeted `upsert` or `retire` as sufficient, even when that operation does not touch the reversed schedule or constraint fact.
**Desired Behaviour** When explicit reversal language is present, the backstop should only be satisfied by a candidate that actually targets the relevant schedule or constraint fact, so unrelated durable-fact updates do not mask a missed retirement or rewrite.
