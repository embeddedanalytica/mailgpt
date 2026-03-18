# Bug backlog

## 1. Garbage characters in email reply body
**Status** Fixed
**Context:** Replying to an email generates garbage characters in the reply body (e.g. - Ens\u06b6^\uc18b$ry\u01e2_`\u04d0Nhwi^r\u0628$rj)pznIMt\u.
**Desired Behaviour** If the email is not a follow up or a coaching adivce but a canned respose (e.g. invitiation to a registration etc) reply should not be included, otherwise reply should contain the orgiginal message.

## 2. Long-horizon memory drops core training backbone when medium-value details accumulate
**Status** Open
**Context:** In the long-horizon athlete-memory bench, the system can retain secondary facts such as equipment details or support habits while losing the core planning backbone that a coach actually needs. The clearest example is `AM-LH-003`, where the model preserved details like the power meter, fan, tire kit, garage skills setup, and mobility class while failing to reliably preserve the durable structure: weekday trainer pattern, weekend outdoor flexibility, and the athlete's main planning anchors after the schedule reversal.
**Desired Behaviour** Long-horizon memory should prioritize durable planning truths over medium-value descriptive details. When memory is under pressure, core schedule constraints, major goal anchors, and structurally important changes must survive ahead of convenience details or gear notes.

## 3. Durable schedule reversals do not fully retire the old coaching assumption
**Status** Open
**Context:** In the same long-horizon bench, once a durable constraint changes, the old rule can remain actionable instead of being cleanly retired. In `AM-LH-003`, the athlete moved from a Sunday-only outdoor rule to broader weekend flexibility, but the old Sunday-only assumption still appeared operationally relevant late in the scenario.
**Desired Behaviour** When the athlete explicitly replaces a durable scheduling rule with a new one, the old rule should be retired cleanly so it no longer influences planning or retrieval. The updated rule should become the active coaching assumption without stale fallback behavior.

## 4. Gravel outdoor-ride availability broadening keeps the stale Sunday-only anchor
**Status** Open
**Context:** In the athlete-memory benchmark rerun, `AM-003 run 1` correctly captured the athlete's correction that outdoor gravel rides are no longer Sunday-only because Saturdays also opened up. But the stored memory merged the new fact into the old one (`mostly Sundays and now also possible on Saturdays`) instead of retiring the old Sunday-only planning assumption.
**Desired Behaviour** When an athlete broadens a recurring scheduling constraint, the old narrower rule should be retired. The durable memory should represent the new availability directly, without preserving the stale anchor that Sunday is the primary or default outdoor ride day.

## 5. Loosened swim-frequency cap leaves the old three-mornings limit operational
**Status** Open
**Context:** In `AM-005 run 1` and `AM-005 run 3`, the athlete explicitly said the old cap of three weekday morning swims was outdated because a fourth weekday morning opened up. The final memory still treated `three weekday mornings` as actionable.
**Desired Behaviour** When an athlete says an old training-frequency cap is no longer true, the system should retire the old limit and replace it with the new availability. Coaches should not continue planning against the obsolete cap.

## 6. Primary swim goal can disappear from final durable memory
**Status** Open
**Context:** In `AM-005 run 2`, the athlete's central long-term goal, `summer 1500 free`, was present early but missing from final durable memory and final retrieval support.
**Desired Behaviour** Primary event or goal anchors introduced by the athlete should remain pinned in durable memory unless explicitly retired or replaced. Final retrieval should reliably surface them for coaching decisions.

## 7. Corrected weekly recovery-day assumption can remain active after explicit reversal
**Status** Open
**Context:** In `AM-007 run 3`, the athlete updated the weekly structure, but the old `recovery-only sunday` assumption still appeared actionable in the final state.
**Desired Behaviour** When an athlete explicitly changes a recurring weekly recovery or training-day rule, the superseded assumption should be retired and no longer influence downstream planning or retrieval.

## 8. New recurring strength session can fail to promote into durable memory
**Status** Open
**Context:** In `AM-007 run 3`, `monday team lift` should have become a durable recurring planning fact, but it was missing from final durable memory and retrieval support.
**Desired Behaviour** Newly introduced recurring weekly sessions that materially affect load and recovery should be promoted into durable memory and survive to final retrieval.

## 9. Moved rowing anchor leaves the old long-erg Saturday assumption active
**Status** Open
**Context:** In `AM-009 run 2`, the athlete changed the weekly rowing structure, but the old `long erg saturday` assumption remained actionable in final retrieval.
**Desired Behaviour** When a recurring workout anchor moves to a different day or structure, the old anchor should be retired cleanly and replaced with the new one so coaching plans use the current weekly pattern.

## 10. Basketball season-goal memory is not normalized robustly enough
**Status** Open
**Context:** In `AM-012 run 1` and `AM-012 run 2`, the athlete's goal of training for `summer rec league` was paraphrased in memory, but the durable goal did not remain stable enough to satisfy final durable memory and retrieval checks.
**Desired Behaviour** Season-goal facts should be canonicalized into a stable durable object so common paraphrases like `summer recreational basketball league` still preserve the athlete's core competitive goal at final retrieval.

## 11. New recurring ski-erg session can fail to become durable memory
**Status** Open
**Context:** In `AM-014 run 1`, the athlete added a permanent `Wednesday ski-erg group`, but that recurring sport-specific session never appeared in final durable memory or retrieval support.
**Desired Behaviour** New recurring sessions with clear long-term planning value should be promoted into durable memory, especially when they are sport-specific and explicitly described as permanent.

## 12. Removed commute-based Monday block can remain active after schedule change
**Status** Open
**Context:** In `AM-014 run 1`, the athlete explicitly said Mondays were now open because their commute changed, but final memory still treated `mondays off-limits` as actionable.
**Desired Behaviour** When an athlete removes a commute-driven or logistics-driven schedule blocker, the old blocker should be retired so the coach can plan against the updated weekly availability.
