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
**Status** Fixed
**Context:** In `AM-012 run 1` and `AM-012 run 2`, the athlete's goal of training for `summer rec league` was paraphrased in memory, but the durable goal did not remain stable enough to satisfy final durable memory and retrieval checks.
**Desired Behaviour** Season-goal facts should be canonicalized into a stable durable object so common paraphrases like `summer recreational basketball league` still preserve the athlete's core competitive goal at final retrieval.
**Verification:** Confirmed fixed on April 18, 2026 via `PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_memory_group1_regressions.py`; `test_bug10_basketball_season_goal_paraphrase_is_rejected_as_duplicate_goal_alias` passed, so the paraphrased create path no longer reproduces.

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
**Status** Fixed
**Context:** In [`sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl`](/Users/levonsh/Projects/smartmail/sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl), turn 2 gives an athlete with a recent layoff and mild Achilles tightness a first-week plan that includes `Session C — Short tempo`, even though the coach had just asked whether the athlete was pain-free and whether a clinician had cleared them to resume training. The same flow keeps reintroducing tempo on turns 4, 5, and 6 while the athlete is still in a cautious rebuild and clearance remains unconfirmed later in the run.
**Desired Behaviour** Early comeback plans for athletes reporting Achilles sensitivity or incomplete return-to-run clearance should default to easy aerobic and low-risk strength/mobility work until the athlete has demonstrated stable symptom response and any necessary clearance is known. The coach should not add tempo or other moderate-hard quality work merely because the athlete is intermediate or available four days per week.
**Verification:** Confirmed fixed on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; all `TestTurn18PostRecoveryEscalation` assertions passed, so the live strategist no longer reproduced premature post-rebuild intensity escalation.

## 14. Coaching reply can contradict its own “fully aerobic” guidance with harder prescribed work
**Status** Open
**Context:** In [`sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl`](/Users/levonsh/Projects/smartmail/sam-app/e2e/artifacts/live_coaching_turns_1774158829-678a6ff2.jsonl), turn 19 answers the athlete’s question about whether to keep the week fully aerobic by saying `keep this week fully aerobic`, but the same reply then prescribes a `Wednesday: Tempo session 20–30 minutes at a controlled effort (RPE 6–7)` and also allows optional strides after Monday’s easy run. That makes the guidance internally inconsistent and operationally confusing.
**Desired Behaviour** When the coach says a week should remain fully aerobic, the prescribed sessions should stay fully aerobic as well. If the system wants to introduce strides or tempo, it should say that explicitly and explain why, rather than mixing incompatible instructions in the same reply.
**Verification:** Reproduced on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; `TestTurn19FullyAerobicGuardrail.test_main_message_does_not_smuggle_in_quality` failed because the live directive still mentioned reintroducing `strides` inside the main message.

## 15. rule_engine_state can mutate durable memory instead of confirm-only
**Status** Fixed
**Context:** The AM2 durable-memory contract intends `rule_engine_state` to be confirm-only support evidence, but the current candidate validator/reducer path may still allow a targeted `upsert` sourced from `rule_engine_state` to rewrite an existing durable fact.
**Desired Behaviour** `rule_engine_state` should be allowed to confirm existing durable facts only. It should not create new durable facts, rewrite existing fact summaries, or retire facts.
**Verification:** Confirmed fixed on April 18, 2026 via `PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_memory_group1_regressions.py`; both `test_bug15_rule_engine_state_targeted_upsert_is_rejected` and `test_bug15_rule_engine_state_confirm_is_allowed` passed.

## 16. New-create upsert can bypass target_id and replace an existing fact by canonical key
**Status** Fixed
**Context:** The AM2 design is intended to make existing-fact mutation ID-based. But if the model emits a new-create `upsert` with the same canonical key as an existing active fact, the reducer's canonical-key backstop can effectively replace the old fact with the new one, losing stable identity semantics and bypassing the `target_id` requirement.
**Desired Behaviour** If an active fact with the same canonical key already exists, the system should require an explicit ID-targeted update path rather than allowing a create-and-dedupe fallback to mutate the fact implicitly.
**Verification:** Confirmed fixed on April 18, 2026 via `PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_memory_group1_regressions.py`; `test_bug16_new_create_upsert_with_existing_canonical_key_is_rejected` passed.

## 17. Reversal backstop can be satisfied by an unrelated targeted update
**Status** Fixed
**Context:** The AM2 reversal retry heuristic is meant to catch missed schedule/constraint reversals, but it may currently treat any targeted `upsert` or `retire` as sufficient, even when that operation does not touch the reversed schedule or constraint fact.
**Desired Behaviour** When explicit reversal language is present, the backstop should only be satisfied by a candidate that actually targets the relevant schedule or constraint fact, so unrelated durable-fact updates do not mask a missed retirement or rewrite.
**Verification:** Fixed on 2026-03-24. Replaced `_candidates_target_schedule_or_constraint` with `_candidates_address_reversal` in `skills/memory/unified/runner.py`. The new function takes existing facts into account: when reversal cues are present and the LLM creates a new schedule/constraint fact without retiring the conflicting existing fact of the same type, the backstop now correctly triggers a retry.

## 18. Stale schedule/constraint facts survive explicit replacement by athlete
**Status** Fixed
**Context:** In short-horizon memory bench scenarios (AM-002, AM-006, AM-007, AM-009, AM-011), when an athlete explicitly replaces a recurring schedule or constraint (e.g., "I switched from Tuesday masters to Wednesday nights"), the LLM sometimes creates the new schedule fact without emitting a `retire` candidate for the old one. Because "silence preserves" in AM2, the old stale fact remains active in memory and can influence downstream coaching decisions. A prompt-level "REPLACEMENT IS RETIREMENT" clause and improved reversal backstop were added on 2026-03-24, moving these from 0/3 pass rate toward 2/3, but the LLM still occasionally omits the retire — particularly when the replacement language is indirect or the old fact's phrasing differs from what the athlete references.
**Desired Behaviour** When an athlete describes switching, replacing, or moving from one schedule/constraint to another, the old fact must be reliably retired in the same candidate batch as the new upsert. The system should not leave stale scheduling assumptions active after an explicit replacement.
**Verification:** Confirmed fixed on April 18, 2026 via `PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_memory_group1_regressions.py`; `test_bug18_reversal_backstop_retries_when_replacement_omits_retire` passed, demonstrating the explicit replacement path now retries and emits the required retire+upsert pair.

## 19. Durable facts evicted under budget pressure despite high coaching value
**Status** Fixed
**Context:** In short-horizon memory bench scenarios (AM-005, AM-007, AM-012), important durable facts like primary event goals ("1500 free", "summer rec league") or key schedule anchors ("erg before sunrise", "soccer club") are evicted when the 7-fact budget fills up. The current eviction logic sorts by importance then fact_type then oldest `last_confirmed_at`, but goal and constraint facts forced to "high" importance are never evicted — the losses occur when facts are stored as `schedule` or `other` type at "medium" importance, even though they carry high coaching value. For example, AM-005 loses the athlete's primary competition goal ("1500 free") because it was stored as a medium-importance goal variant, and AM-012 loses "summer rec league" for the same reason.
**Desired Behaviour** Facts with high coaching value — particularly primary competition goals and core schedule anchors — should survive budget pressure ahead of secondary details. The eviction strategy should better account for coaching relevance, not just the mechanical importance label assigned at creation time.
**Verification:** Confirmed fixed on April 18, 2026 via `PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_memory_group1_regressions.py`; all Bug 19 regressions passed, including `test_bug19_am005_primary_goal_and_compiler_priority_under_sectioned_caps`, `test_bug19_am012_primary_season_goal_retained_compiler_covers_goals`, and `test_bug19_misfiled_goal_as_schedule_survives_schedule_anchor_pressure`.

## 21. Profile time_availability schema too narrow — daily time windows silently dropped
**Status** Fixed
**Context:** The profile extraction schema only supports `time_availability: { sessions_per_week: int, hours_per_week: number }`. When athletes provide daily time windows (e.g. "Mon 18:30-19:30, mornings 05:45-07:15"), the profile extraction LLM has no field to store this. The normalization in `profile.py` (line 66-76) silently drops anything that isn't `sessions_per_week`/`hours_per_week` as numeric values. Result: `time_availability` stays `{}` indefinitely, the strategist sees it as missing, and the coach re-asks for availability every turn even though the athlete has provided it multiple times.
**Verification:** Fixed — `profile.py` `_normalize_time_availability()` now accepts `sessions_per_week` (string), `daily_windows` (list of strings), and `availability_notes` (string). Confirmed in LAS-002 sim run (2026-03-28 evening) — `time_availability` populated on all turns with structured daily windows and notes.

## 20. Continuity bootstrap treats past event dates as active event horizons
**Status** Fixed
**Context:** In [`sam-app/email_service/continuity_bootstrap.py`](/Users/levonsh/Projects/smartmail/sam-app/email_service/continuity_bootstrap.py), `_parse_event_date()` currently accepts any syntactically valid ISO date from profile state, including stale past races. That means an athlete with an old `event_date` can bootstrap into `goal_horizon_type='event'` and carry `weeks_until_event=0`, which skews continuity context and prompt framing until some later transition corrects it.
**Desired Behaviour** Continuity bootstrap should only treat future-or-today event dates as active event horizons. Past event dates should be ignored during bootstrap so stale races do not force the athlete into event-mode continuity state.
**Verification:** Fixed on 2026-04-03 by ignoring past `goal_event_date` values during continuity bootstrap. Covered by `test_past_event_date_ignored` in `sam-app/email_service/test_continuity_state_contract.py`.

## 22. Strategist reopens resolved conversational topics
**Status** Open
**Context:** In LAS-002 sim (2026-03-28), the obedience judge flagged `reopened_resolved_topic` on T4, T8, T13. In LAS-003, it flagged T4, T12, T25. Independent analysis of the actual conversation flow shows the judge is miscalibrated — it treats any *mention* of a topic as "reopening" even when the coach is directly responding to the athlete's own words:
- **LAS-002 T4, T13:** Athlete explicitly asked "confirm you won't bring up the cleared calf again." Coach replied with a confirmation ("I won't revisit that topic" / "I acknowledge your request and will comply"). Acknowledging a request the athlete made is not reopening.
- **LAS-002 T8:** Judge flagged "Send the firm SFO/NYC dates when they lock" as re-asking for travel dates. But the athlete themselves said "I'll send the firm SFO/NYC dates as they lock" in the same turn — the topic was never resolved; the athlete kept it open across T3–T25.
- **LAS-003 T4:** Judge flagged "weekday morning runs" as referencing a forbidden time-of-day. The athlete established this as their own scheduling language in T1 and used it throughout.
- **LAS-003 T12:** Athlete reported "Hamstring: clear" as part of the agreed MP safety protocol. Coach responding "glad the hamstring is clear" is acknowledging a status update, not reopening.
- **LAS-003 T25:** Coach asked "did the Week 4 .ics/.csv import correctly?" after athlete said "I've got the files." Borderline — but download ≠ import, and verifying a distinct step is reasonable coaching.
**Verification:** Reproduced on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; `TestConfirmedDetailNotReopened.test_avoid_blocks_scheduling_re_ask` failed because the live directive's `avoid` list did not encode any guard against re-asking a confirmed scheduling detail.

## 23. Response-generation failures cause multi-turn silence
**Status** Fixed
**Context:** In LAS-002 sim (2026-03-28), turns 19-24 (6 consecutive turns) all failed with "No reply sent due to response-generation failure." The athlete kept sending simple confirmatory messages and got zero replies for 6 simulated weeks. `felt_understood` dropped to 1. The root cause is not the suppress rule (that's T21 in LAS-003, which is correct) — it's the response generation skill failing when the strategist directive is minimal/thin.
**Observed in:** LAS-002 T19-T24 — all "response-generation failure", not strategist suppress.
**Desired Behaviour** The response generation skill should never fail silently on a thin directive. When the directive is minimal (brief ack, no plan change), the writer should produce a minimal 1-2 line reply rather than crashing. A short reply is infinitely better than silence. If the writer truly cannot produce anything, the system should fall back to a canned acknowledgment rather than sending nothing.
**Fix scope:** Response generation skill (fallback for thin directives), possibly `coaching.py` (canned fallback when response-gen fails).

## 24. Writer hallucinates week numbers and drops directive details
**Status** Fixed
**Context:** The response-generation writer systematically outputs wrong week/plan numbers and omits structural details from the strategist directive. In LAS-003, the obedience layer corrected `missed_exact_instruction` 10 times across 9 turns (T1–T5, T9, T13, T15, T25). The violations fall into two categories:
- **Week-number hallucination (5 violations):** Writer outputs the wrong week label — e.g. "Week 2" instead of "Week 1" (T2), "Week 3" (T3), "Week 5" (T5), "Week 15" instead of "Week 4" (T25). The continuity prompt section (`response_generation/prompt.py:79-121`) explicitly injects the correct week number from `continuity_context.weeks_in_current_block`, but the writer ignores or overrides it. A contributing factor: when `_is_narrow_directive()` returns `True` (content_plan ≤2 items and main_message <120 chars), the continuity section is suppressed entirely from the system prompt (`runner.py:36-37`), so the writer has no week guidance in the prompt even though `continuity_context` is in the JSON input.
- **Dropped plan elements (5 violations):** Writer omits specific structural details that appear in the directive — only 1 strength session instead of 2 (T1), missing confirmation prompt (T4), missing "follow the plan as written" instruction (T9), missing injury-area name and confirmation request (T13), missing MP test details (T15). These are details present in `content_plan` or `main_message` that the writer fails to reproduce.
**Observed in:** LAS-003 (2026-03-28). LAS-002 evidence previously cited here was invalid (sim artifacts and Bug #23 response-gen failures, not a handoff issue).
**Desired Behaviour** The writer must faithfully reproduce week numbers from `continuity_context` and all structural details from the directive's `content_plan` and `main_message`. Week numbers must never be invented or guessed.
**Fix scope:**
1. `response_generation/prompt.py` — strengthen week-number anchoring: consider always injecting a minimal continuity line (e.g. "You are writing about Week N") even when `_is_narrow_directive()` is true, so the writer always has an authoritative week reference in the system prompt.
2. `response_generation/prompt.py` — add an explicit instruction: "reproduce every item in content_plan; do not omit or summarize any item."
3. Consider a post-generation validator that checks the output text against `continuity_context.weeks_in_current_block` and flags week-number mismatches before the obedience layer.
**Verification:** Fixed on 2026-04-03 by preserving continuity context for narrow directives that mention week or block position in `skills/response_generation/prompt.py` and `skills/response_generation/runner.py`. Covered by `test_narrow_week_anchored_directive_keeps_continuity` in `sam-app/email_service/test_response_generation_skill.py`.

## 25. Communication style preferences not enforced as hard constraints
**Status** Open
**Context:** Original claim: LAS-002 and LAS-003 athletes stated formatting preferences (bullets, concise) that were intermittently ignored. Investigation of LAS-002 (2026-03-30) found this to be a judge calibration issue, not a real bug. The athlete in LAS-002 asked for "3-5 bullet items" specifically when requesting a weekly plan (T1). On the turns flagged as violations (T4, T6, T25), the athlete's own `communication_style_fit` scores were consistently 4-5, and the athlete never complained about prose vs. bullet format. The judge over-indexed on "must use bullets" for every reply type including short confirmations and acknowledgments where paragraph format is natural and appropriate. T25's issue was a missing control character (U+0014 sim artifact), not a style violation. LAS-003 T4's `comm_style_fit=2` from the judge was contradicted by the athlete's own `communication_style_fit=5`.
**Verification:** Reproduced on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; `TestFormatConstraint.test_avoid_mentions_length_constraint` failed, so the live strategist still does not reliably treat an explicit output-format constraint (`3 lines max`) as a hard instruction.

## 26. Coach repeats already-established constraints verbatim every turn
**Status** Open
**Context:** In LAS-002 sim (2026-03-28), from T4 through T18 (~15 consecutive turns), the coach recites the full constraint list in every reply — treadmill/brick caps (45'/45'+20'), nudged intensity on travel days, long-ride fueling (1 bottle + ~2 gels/hr, salt every 45–60min), Friday easy day, 3.5h ceiling — even though nothing changed and no new information was exchanged. The conversation doesn't advance for 15 turns. A real coach would say "Got it, waiting on your dates" in 1-2 lines once constraints are agreed.
**Observed in:** LAS-002 T4–T18 (2026-03-28).
**Desired Behaviour** Once constraints are established and acknowledged by the athlete, the coach should not re-state them unless the athlete asks for a recap or something changes. Subsequent replies should advance the conversation, not parrot previously agreed terms.
**Fix scope:** Likely a coaching_reasoning (strategist) issue — the `content_plan` keeps including constraint recaps as plan items. The strategist prompt should recognize when constraints are already established and avoid re-listing them. Alternatively, the writer prompt could instruct: "do not repeat information the athlete has already confirmed unless they ask."
**Progress (2026-04-03):** Added a structural strategist backstop for existing `answer_first_then_stop` turns in `skills/coaching_reasoning/validator.py` and `skills/coaching_reasoning/runner.py`: when the doctrine trace already classifies a turn as narrow-answer, directives with `content_plan > 2` are rejected and retried once with structural feedback only. This closed the live `TestAnswerOnlyDirective` regression in `sam-app/email_service/test_coaching_reasoning_eval.py`, but `TestOneChangeNoRecap` still fails because that brief is currently classified by existing doctrine as `plan_mutation` / `structure_then_detail`, so bug 26 remains open.
**Verification:** Reproduced again on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; both `TestOneChangeNoRecap.test_avoid_blocks_recap_of_standing_constraints` and `TestOneChangeNoRecap.test_content_plan_stays_tight` failed.

## 27. Writer fabricates URLs and portal infrastructure
**Status** Fixed
**Context:** In LAS-003 sim (2026-03-28), the writer invented fake download URLs when the athlete asked for ICS/CSV files. T12: `https://portal.example.com/downloads/maya/week2`. T13: `https://portal.example.com/week2/ics_csv`. These URLs point to nonexistent infrastructure — SmartMail has no training portal or file-hosting service. The coach confidently presented these as real, actionable links.
**Root cause:** The strategist (coaching_reasoning) is the primary source — it invents delivery mechanisms (portals, exports, download paths) in its `content_plan` and `main_message`, and the writer faithfully executes. Confirmed via targeted test (`test_bug27_url_fabrication.py`).
**Fix:** Added a general anti-hallucination grounding rule to both prompt packs:
- `prompt_packs/coach_reply/v1/coaching_reasoning.json` (strategist): "Only reference information present in your input context. If the athlete asks for something you don't have — a file, a link, a resource, a specific fact — say you cannot provide it rather than inventing an answer."
- `prompt_packs/coach_reply/v1/response_generation.json` (writer): "Only reference information present in your input. If a file, link, or resource is not in the writer_brief, do not invent one — say you cannot provide it."
**Verification:** Zero fabricated URLs, portals, or download links across 3 full sim runs (LAS-001, LAS-002, LAS-003) on 2026-04-01. Also verified in 6 targeted test runs via `test_bug27_url_fabrication.py`. Details in `bug-fix27.md`.

## 28. Coach contradicts its own capabilities mid-conversation
**Status** Open
**Context:** In LAS-003 sim (2026-03-28), the coach's self-model is inconsistent across turns. At T5, the coach says "I can't load Week 1 into your calendar or send invites as I'm a remote coach." By T12, the same coach claims to have attached ICS/CSV files, provides a portal download URL, and says "files have been released." These are contradictory — the coach first says it can't do calendar operations, then pretends it did them.
**Observed in:** LAS-003 T5 vs T12–T13 (2026-03-28).
**Desired Behaviour** The coach should have a consistent self-model of its capabilities. If it cannot attach files or load calendars, that should remain consistent. The correct behavior is to provide the training plan in email text and let the athlete manually create calendar entries.
**Fix scope:** Coaching persona / system prompt — the coach's capabilities (email-only, no file attachments, no calendar integration) should be stated clearly and consistently. The writer prompt should include: "you communicate via email only; you cannot attach files, send calendar invites, or provide download links."
**Verification:** Reproduced on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_capability_consistency_eval.py`; `test_cross_turn_does_not_invent_file_or_calendar_actions` failed because the writer still offered to attach an `.ics`/`.csv` file after the coach had established the email-only capability boundary.

## 29. Coach loses track of previously provided information in longer conversations
**Status** Fixed
**Context:** In LAS-003 sim (2026-04-01), the coach re-asks for travel dates the athlete already provided — sometimes in the immediately preceding turn. T19: coach says "I didn't receive the actual mid-March dates" after the athlete said "I'm sending exact mid-March travel dates now." T21: coach asks "Please paste the exact mid-March travel start and end dates" after the athlete provided them in T20 and the coach acknowledged receipt. T23: coach re-asks for dates again. T24: coach says "I will not ask for these dates again" — then T25: asks for dates again. In LAS-002, T15 and T19 the coach reopens settled workflow questions (review timing, alert format) that were already locked in prior turns.
**Observed in:** LAS-003 T19, T21, T23, T25; LAS-002 T15, T19 (2026-04-01 sim runs).
**Desired Behaviour** Once the athlete provides information that the coach acknowledges receiving, the coach must not re-ask for it. The continuity/memory pipeline should retain key facts provided within the same conversation thread, especially concrete data like dates, confirmed protocols, and locked decisions.
**Fix scope:** Likely a memory/continuity pipeline issue. The `continuity_summary` and `open_loops` may not be capturing intra-conversation facts reliably, causing the strategist to treat already-answered questions as still open. Investigate whether `memory/unified` retains mid-conversation facts or only cross-session facts.
**Verification:** Fixed on 2026-04-03 by pruning resolved `open_loops` when the athlete answers them and the coach does not explicitly re-ask. Covered by `test_answered_open_loop_is_pruned_when_coach_moves_on` and `test_open_loop_stays_when_coach_explicitly_reasks_for_same_topic` in `sam-app/email_service/test_memory_refresh_runner.py`.

## 30. Simulated athlete gets stuck in degenerate repetition loops
**Status** Fixed
**Context:** In LAS-001 sim (2026-04-01), the simulated athlete gets stuck from T6 onward — every single message for 20 consecutive turns is a variation of "I'll send the full check-in first thing tomorrow AM" listing the same data items (resting HR, sleep, durations, RPEs, HR/HRV, Achilles/hip). The athlete never actually sends the check-in data. A real athlete would either send the data or stop emailing. In LAS-002, the athlete gets into a similar loop around T15-T22 re-confirming the Sunday review window. In LAS-003, mid-turn repetition around travel date confirmations.
**Observed in:** LAS-001 T6-T25, LAS-002 T15-T22, LAS-003 mid-turns (2026-04-01 sim runs).
**Desired Behaviour** The simulated athlete should advance the conversation state — send the actual data it promised, introduce new complications, or move to a new topic. After 2-3 turns on the same topic, the athlete should either escalate, provide the data, or shift focus. Degenerate loops produce useless test data and inflate judge scores artificially (the judge gives 4.7-5.0 on trivial ack turns).
**Fix scope:** Athlete sim prompt or state machine — needs anti-repetition guardrails and a mechanism to advance state (e.g., actually generate check-in data after promising it, move to next week's plan, introduce a new concern).
**Verification:** Fixed on 2026-04-03 by rejecting stale promise-only athlete replies once a pending commitment has been outstanding across multiple turns. Covered by `test_validate_reaction_rejects_repeated_stale_promise_loop`, `test_validate_reaction_allows_fulfilling_stale_commitment`, and `test_react_to_coach_reply_rejects_stale_promise_loop` in `sam-app/email_service/test_athlete_simulation.py`.

## 31. Judge over-rewards trivial acknowledgment turns with perfect scores
**Status** Fixed
**Context:** In LAS-001 sim (2026-04-01), from T9 through T19 the judge consistently awards 4.7-5.0 average scores on turns where the coach says nothing more than "Got it — I'll review your check-in tomorrow" and the athlete repeats the same promise. These turns have zero coaching value — no plan adjustments, no new information, no coaching insight — yet the judge treats them as near-perfect. This inflates the overall sim score and masks real quality issues. The judge correctly catches actual problems (T20: missed Achilles flag, avg=2.9; T22: missing numeric baseline, avg=3.0) but the signal is drowned out by 10+ turns of artificial 5.0s.
**Observed in:** LAS-001 T9-T19 (2026-04-01 sim run).
**Desired Behaviour** The judge should penalize stalled conversations where no coaching progress is being made. A turn where the coach merely acknowledges a repeated promise without advancing the coaching relationship should score lower (e.g., 3.0-3.5) to reflect the lack of value delivered. The judge should also flag when the conversation has stalled and the coach should be proactively advancing it.
**Fix scope:** Judge prompt — add criteria for "conversation progress" as a scoring dimension. A perfect score should require the coach to actually advance the coaching relationship, not just acknowledge a repeated message correctly.
**Verification:** Fixed on 2026-04-03 by capping judge scores for trivial acknowledgment turns tagged `too_vague`. Covered by `test_validate_judge_output_caps_vague_trivial_ack_turn` in `sam-app/email_service/test_athlete_simulation.py`.

## 32. Coach produces vague or non-decisive guidance when athlete asks for clear direction
**Status** Open
**Context:** Across LAS-001, LAS-002, and LAS-003 simulation runs (2026-04-01 / 2026-04-03), the coach frequently defaults to safe, generic, or hedged responses instead of making a clear recommendation when the athlete asks for direction. This is reflected in repeated `too_vague` issue tags across all three runs and lower athlete-perceived understanding (~4.0–4.2) despite high judge scores (~4.4–4.5 coaching_quality). Typical pattern: athlete asks for a concrete choice or next step (e.g., device selection, weekly structure, progression decision), and the coach responds with multiple options, defers the decision back to the athlete, or asks for additional clarification that is not strictly required to act.

Concrete failure modes observed:
- Responding with 2–4 equivalent options without a clear default recommendation
- Asking follow-up questions instead of making a reasonable assumption and acting
- Providing general principles (“keep it conservative”, “listen to your body”) without translating them into an actionable session or decision
- Avoiding commitment on progression (e.g., whether to introduce intensity, how to adjust volume)

**Desired Behaviour** When the athlete asks for direction, the coach should default to decisive, actionable guidance:
- Provide one clear recommended option (default) and at most one alternative if necessary
- Translate guidance into concrete actions (sessions, durations, intensities, schedule changes)
- Only ask follow-up questions if the answer materially changes the recommendation; otherwise make a reasonable assumption and state it
- Avoid generic coaching phrases unless paired with a specific action

**Elite Coach Reference:** A high-quality human coach will make a call under uncertainty: “Use Polar H10. It’s the most reliable for your use case. Only consider X if you specifically need Y.” or “Keep this week fully easy: 4 runs, 30–45 minutes, no strides. We’ll reassess after you report back.”

**Fix scope:** Primarily strategist (coaching_reasoning) prompt — enforce a “decisive default” rule and limit option branching. Secondarily writer prompt — ensure recommendations are expressed as concrete actions, not abstract guidance.
**Verification:** Reproduced on April 18, 2026 via `ENABLE_LIVE_LLM_CALLS=true PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_coaching_reasoning_eval.py`; both `TestPickOneOption.test_main_message_makes_a_choice` and `TestPickOneOption.test_avoid_blocks_both_sides_vagueness` failed.

## 33. Judge scoring is inflated relative to athlete signal and fails to penalize coaching defects
**Status** Fixed
**Context:** Across LAS-001, LAS-002, and LAS-003 runs, judge scores remain consistently high (coaching_quality ~4.3–4.5, tone_trust ~4.8–5.0) even when objective defects are present: vagueness (`too_vague` in all runs), hallucinated context (LAS-002), missed continuity, and unfulfilled commitments. At the same time, athlete-reported “felt understood” is materially lower (~4.0–4.2), indicating a gap between perceived and actual coaching quality.

The judge currently:
- Correctly identifies some issues via tags (e.g., `too_vague`, `hallucinated_context`) but does not reflect them proportionally in numeric scores
- Overweights tone and stylistic correctness relative to decision quality and coaching effectiveness
- Does not sufficiently penalize lack of progress, weak guidance, or failure to close loops

**Observed in:**
- LAS-002: `hallucinated_context` present while coaching_quality still ~4.48
- All runs: repeated `too_vague` tags without meaningful score degradation
- Persistent gap between judge scores (~4.5+) and athlete felt-understood (~4.0)

**Desired Behaviour** Judge scoring should reflect coaching effectiveness, not just correctness of tone:
- Penalize vague or non-decisive guidance (e.g., reduce coaching_quality when `too_vague` is present)
- Apply strong penalties for hallucinated context or incorrect references to prior facts
- Incorporate athlete signal (felt_understood, communication_style_fit) as a moderating factor
- Introduce a “decision quality / usefulness” dimension: high scores require the coach to move the plan forward, not just respond correctly
- Ensure that repeated minor defects (e.g., vagueness across multiple turns) compound into lower overall scores

**What judge should catch (examples):**
- If the coach provides multiple options without a recommendation → score reduction for decision quality
- If the coach asks unnecessary clarifying questions instead of acting → score reduction for usefulness
- If hallucinated context is detected → hard cap on coaching_quality for that turn

**Fix scope:** Judge prompt and scoring rubric — rebalance weights toward decision quality and coaching impact, and explicitly tie issue tags (e.g., `too_vague`, `hallucinated_context`) to score penalties. Optionally incorporate athlete feedback as a calibration signal during scoring.
**Verification:** Fixed on 2026-04-03 by applying deterministic score caps when `hallucinated_context` or severe `too_vague` patterns are present. Covered by `test_validate_judge_output_caps_hallucinated_context_scores` in `sam-app/email_service/test_athlete_simulation.py` and confirmed compatible with `sam-app/email_service/test_prompt_feedback_aggregate.py`.

## 34. Strategist still broadens narrow answer-first questions and triggers duplicate `coaching_directive` calls
**Status** Open
**Context:** On complete-profile lightweight question turns, the strategist still often produces an over-broad first draft, fails structural validation, and retries once. The retry usually returns a deliverable answer, but it still broadens beyond the athlete's explicit ask. This adds an extra `coaching_directive` prompt and degrades answer quality. Reproduced on 2026-04-15 with `tools/debug_turn.py` using `me-debug@example.com` and trace file `sam-app/.cache/debug_turn_trace/me-debug_at_example.com.jsonl`, line 34.

Repro message:
`What else I can try to keep my heartrate under control? For example I noticed that if I watch a movie my heartrate my spike just because the movie is taking an interesting turn. Is this bad for my training? Is the making the signal less reliable?`

Observed behavior:
- log prints `coaching_reasoning retrying after structural validation failure: directive too broad for answer-first turn`
- turn fires `coaching_directive` twice
- final reply still adds adjacent tactics and stale caveats not strictly required by the ask (warm-up routine, search suggestions, knee-soreness caveat, pause-pedaling protocol)

**Desired Behaviour** For `answer_first_then_stop` / lightweight-answer turns, the strategist should answer only the explicit question(s) in the latest athlete message. Prior context may support correctness or safety, but it should not expand the response agenda. A narrow question should result in one strategist call and a narrow answer.

**What was already tried**
- Validator tightening beyond the existing `content_plan > 2` backstop was attempted and reverted. It exposed worse failure modes, including suppressed blank replies when both strategist attempts failed.
- The active strategist prompt was already consolidated into the monolithic `v1/coaching_reasoning.json` prompt, but the duplicate-call / over-broad behavior persists.
- The issue appears to be primarily in strategist scope control, not in memory refresh or validator strictness.

**Fix scope:** `sam-app/email_service/skills/coaching_reasoning` prompt / retry behavior for lightweight answer-first turns.
