# Recommendation Engine Spec (from `decision-tree.txt`)

## 1. Purpose
Translate weekly athlete check-in inputs into:
1. Athlete classification (stable profile + weekly risk state)
2. Plan track selection
3. Weekly skeleton (session mix)
4. Session-level "today" recommendation
5. Next email response payload

This spec is intentionally concrete and implementation-first (YAGNI).

## 2. Scope
In scope:
- Onboarding/intake classification
- Weekly check-in routing
- Risk-based auto-adjustments
- Deterministic decision outputs for coaching email generation

Out of scope (for v1):
- Adaptive ML scoring
- Wearable API integration
- Detailed periodization beyond phase labels
- Nutrition/supplement recommendations

## 3. Core Concepts
- Main sport: one dominant discipline for current block
- General fitness: no dominant discipline in current block
- Phase: `base | build | peak_taper | return_to_training`
- Risk flag: `green | yellow | red_a | red_b`
- Time bucket: `2_3h | 4_6h | 7_10h | 10h_plus`
- Experience: `new | intermediate | advanced`
- Goal category: intake-level classification, distinct from weekly phase windows

## 4. Data Model

### 4.1 Athlete Profile (persistent)
```json
{
  "athlete_id": "string",
  "goal_category": "general_consistency | event_8_16w | performance_16w_plus",
  "event_date": "YYYY-MM-DD | null",
  "training_identity": "casual_multi | single_discipline | hybrid_seasonal",
  "main_sport_current": "run | bike | swim | other | null",
  "experience_level": "new | intermediate | advanced",
  "time_bucket": "2_3h | 4_6h | 7_10h | 10h_plus",
  "injury_baseline": "none | recurring_niggles | current_pain",
  "schedule_variability": "low | medium | high",
  "performance_intent_default": false,
  "equipment_access": {
    "gym": true,
    "pool": true,
    "bike": true,
    "trainer": false
  },
  "structure_preference": "structure | flexibility | mixed"
}
```

### 4.2 Weekly Check-in (ephemeral)
```json
{
  "week_start": "YYYY-MM-DD",
  "goal_now": "string",
  "has_upcoming_event": null,
  "event_date": "YYYY-MM-DD | null",
  "performance_intent_this_week": null,
  "sports_last_week": [
    {"sport": "run", "minutes": 120}
  ],
  "days_available": 4,
  "pain_score": 2,
  "pain_location": "left knee",
  "pain_affects_form": false,
  "energy_score": 6,
  "stress_score": 7,
  "sleep_score": 5,
  "returning_from_break": false,
  "recent_illness": "none",
  "break_days": null,
  "free_note": "string",
  "missed_sessions_count": 1,
  "week_chaotic": false
}
```

Field constraints:
- `recent_illness` enum is fixed: `none | mild | significant`
- `has_upcoming_event`: `true | false | null` (null allows profile-based fallback)

### 4.3 Rule State (persistent, separate from profile)
```json
{
  "athlete_id": "string",
  "weekly_signals_last_4": [
    {
      "week_start": "YYYY-MM-DD",
      "pain_score": 2,
      "energy_score": 6,
      "sleep_score": 5,
      "stress_score": 7
    }
  ],
  "compliance_last_4": [
    {
      "week_start": "YYYY-MM-DD",
      "planned_sessions_count": 4,
      "completed_sessions_count": 3
    }
  ],
  "phase_risk_time_last_6": [
    {
      "week_start": "YYYY-MM-DD",
      "phase": "build",
      "risk_flag": "yellow",
      "time_bucket": "4_6h"
    }
  ],
  "weeks_since_deload": 2,
  "phase_upgrade_streak": 1,
  "last_updated_week_start": "YYYY-MM-DD"
}
```

Note:
- `rule_state` is a separate persisted contract.
- RE1-FU may initially define interface + in-memory fallback when persistence is not yet wired.

### 4.4 Engine Output (deterministic)
```json
{
  "classification_label": "event_8_16w / hybrid_seasonal / intermediate / 4_6h / recurring_niggles / high_variability",
  "track": "main_build",
  "phase": "build",
  "risk_flag": "yellow",
  "weekly_skeleton": [
    "easy_aerobic_main",
    "easy_aerobic_main",
    "reduced_intensity_or_easy",
    "strength_or_cross_train"
  ],
  "today_action": "do planned but conservative",
  "plan_update_status": "updated | unchanged_clarification_needed | unchanged_infeasible_week",
  "adjustments": [
    "reduce intensity",
    "no make-up intensity"
  ],
  "next_email_payload": {
    "subject_hint": "This week: stay consistent, reduce intensity",
    "summary": "...",
    "sessions": ["..."],
    "plan_focus_line": "...",
    "technique_cue": "...",
    "recovery_target": "...",
    "if_then_rules": ["..."],
    "disclaimer_short": "...",
    "safety_note": "..."
  }
}
```

## 5. Intake Classification Logic (Layer 1)

### 5.1 Inputs
- Goal timeframe
- Training identity
- Experience
- Time bucket
- Injury baseline
- Schedule variability

### 5.2 Output label format
`<goal_category> / <training_identity> / <experience> / <time_bucket> / <injury_baseline> / <schedule_variability>`

### 5.3 Mapping rules
- Q1 goal timeframe -> `goal_category`:
  - no event date -> `general_consistency`
  - event date within 8-16 weeks -> `event_8_16w`
  - event date >16 weeks OR performance-focused ongoing -> `performance_16w_plus`
- Q2 identity:
  - "bit of everything" -> `casual_multi`
  - mostly one sport -> `single_discipline`
  - seasonal shifts + real cross-train -> `hybrid_seasonal`
- Q3 experience:
  - 0-6 months consistent -> `new`
  - 6-24 months -> `intermediate`
  - 2+ years + structured history -> `advanced`
- Q4 constraints:
  - time -> `2_3h | 4_6h | 7_10h | 10h_plus`
  - injury -> `none | recurring_niggles | current_pain`
  - variability -> `low | medium | high`

## 6. Weekly Plan Selection Logic (Layer 2)

### 6.1 Main branch
If `main_sport_current != null` -> `main_sport_plan`
Else -> `general_fitness_plan`

### 6.2 Performance intent resolution
`effective_performance_intent` resolution order:
1. Use `performance_intent_this_week` when not null
2. Else use `performance_intent_default`
3. Else default to `false`

Intensity is allowed only when `effective_performance_intent == true` and other risk/safety gates permit it.

### 6.3 General fitness plan templates
- `2_3h` (3 sessions):
  - 1 easy aerobic (engine)
  - 1 strength/mobility
  - 1 fun/variety
- `4_6h` (4 sessions):
  - 2 aerobic
  - 1 strength
  - 1 optional intensity OR skills (intensity only when `effective_performance_intent`)
- `7_10h` (5-6 sessions base):
  - 3 aerobic
  - 1 intensity (only when `effective_performance_intent`)
  - 1 strength
  - 1 optional skills/recovery
- `10h_plus` (controlled add-ons, not free volume):
  - base structure (same anchors):
    - 3 aerobic
    - 1 intensity (green + `effective_performance_intent` only)
    - 1 strength
    - 1 recovery/skills
  - add-ons (choose 1-2 max):
    - +1 easy aerobic OR
    - +1 skills/mobility OR
    - +1 short recovery (20-40 min easy)
  - cap/progression:
    - weekly volume increase max 5-10%
    - every 3-5 weeks include lighter week (~20% volume reduction)

General fitness global rules:
- Keep intensity low unless `effective_performance_intent` is true.
- Rotate modalities when possible to reduce overuse risk.

### 6.4 Main sport phase selection
Calendar windows:
- `base`: event >12 weeks away OR no event
- `build`: event 4-12 weeks away (inclusive)
- `peak_taper`: event 0-3 weeks away (inclusive)

Hard return context is true when any:
- `returning_from_break == true`
- `recent_illness == significant`
- `break_days >= 10` (explicit or derived)

`phase` derivation order:
1. Validate event date input:
   - if `has_upcoming_event == true` and `event_date` missing/invalid -> dismiss date from routing, keep existing plan unchanged, emit clarification flag
   - if `has_upcoming_event == null`, infer event expectation from `goal_category == event_8_16w` (do not infer from `goal_now` text)
   - if `event_date` is in the past -> dismiss date from routing, keep existing plan unchanged, emit clarification flag
2. If hard return context true -> `return_to_training`
   - precedence rule: hard return context always wins over calendar phase
3. Else derive calendar phase from valid event window
4. Else if no event and performance chase active -> `build`; otherwise `base`
5. Apply priority-based conservative override (highest active trigger wins):
   - Priority 1: `red_b` -> phase cap `base`
   - Priority 2: `red_a` -> phase cap `build`
   - Priority 3: return-context (`newly returning` but not hard return phase) -> phase cap `build`
   - Priority 4: `yellow` -> phase cap `build`
   - Priority 5: `new` athlete -> phase cap `base`
6. Enforce cap rule:
   - if computed phase is later than cap, downgrade to cap
   - do not downgrade below `base`
7. Inconsistent-training stabilization rule:
   - if computed phase flips week-to-week without a red-tier safety trigger, mark `inconsistent_training`
   - require 2 consecutive qualifying check-ins before upgrading to a later phase
   - downgrades for safety triggers apply immediately

### 6.5 Risk flag derivation
Worsening definition (deterministic):
- pain_score increased by >=2 points vs previous week, OR
- pain moved from [0-3] to >=4, OR
- `pain_affects_form` flipped from false to true

- `red_b` (explicit clinician recommendation) if any:
  - sharp pain
  - sudden onset pain
  - swelling
  - numbness/tingling
  - pain affects gait/form
  - night pain
  - worsening week-to-week (per deterministic worsening definition)
- `red_a` (modify + monitor) if not `red_b` and:
  - pain score >= 4, non-sharp, does not alter form, not worsening
- `yellow` if not red-tier and any:
  - recurring niggles
  - energy_score <= 4
  - stress_score >= 8
  - sleep_score <= 4
  - stress_score >= 7 and energy_score <= 5
- `green` otherwise

### 6.6 Main sport switching governance (hybrid safety)
Switch `main_sport_current` only when:
- explicit athlete request, OR
- last 2 weeks show >=60% minutes in another sport AND total minutes across 2 weeks >= 120

Switch transition guard (first 2 weeks after switch):
- cap intensity to max 1 quality session/week
- cap weekly volume increase at <=10%
- freeze `main_sport_current` for 2 weeks post-switch unless:
  - athlete explicitly requests a change, or
  - `red_b` safety condition requires immediate change

### 6.7 Main sport skeleton by time bucket
- `2_3h` (3 sessions):
  - 1 long/easy main-sport
  - 1 short quality OR hills/tempo (green only)
  - 1 strength/mobility OR easy cross-train
- `4_6h` (4 sessions):
  - 2 easy aerobic main-sport
  - 1 quality (type by experience)
  - 1 strength OR cross-train
- `7_10h` (5-6 sessions):
  - 3 easy aerobic
  - 1 long
  - 1 quality
  - 1 strength or skills
- `10h_plus`:
  - add second quality day only when:
    - experience in `intermediate | advanced`
    - risk is `green`
    - schedule variability is not `high`

Main sport deload rule:
- every 3-5 weeks OR earlier when sustained yellow risk:
  - reduce weekly volume by ~15-25%
  - remove one quality session
- `peak_taper` supersedes standard deload cadence.
- sustained yellow definition:
  - yellow for 2 consecutive weeks, OR
  - yellow in 3 of last 4 weeks

Quality archetypes by experience:
- `new`:
  - strides/hills or short tempo blocks
  - no VO2 prescriptions
- `intermediate`:
  - tempo/threshold intervals
  - occasional VO2 capped at 1 session/week (green only)
- `advanced`:
  - event-specific interval sets
  - still bounded by risk/schedule/intensity-spacing rules

### 6.8 Risk-based overrides (track-level)
- `red_a`:
  - remove all intensity
  - swap to low-impact modality
  - reduce total volume by 20-50%
  - include: "stop intensity, switch to easy/low impact, update coach within 24h"
- `red_b`:
  - all `red_a` rules
  - include explicit line: "Please stop training and consult a clinician/physio."
- `yellow`:
  - keep volume approximately stable
  - reduce intensity (or replace quality with easy)
- `green`:
  - proceed as planned

## 7. Session-Level Routing (Layer 3)
Evaluate these signals each email/check-in, in this order:

### 7.1 Signal 1: Pain
- If risk is `red_b`:
  - today action: stop training intensity immediately; low-impact only if pain-free
  - include explicit clinician/physio recommendation
  - apply 3-7 day adjustment window minimum
- If risk is `red_a`:
  - today action: stop intensity, easy cross-train
  - request update within 24 hours
  - apply 3-7 day adjustment window
- If `pain_score in [1..3]` and stable:
  - easy only, no intensity, monitor

### 7.2 Signal 2: Energy
(Only if not already red-tier pain action)
- `<=4`: minimum effective dose session
- `5-7`: planned but conservative
- `8-10`: planned; optional slight upgrade if risk `green`

### 7.3 Signal 3: Missed sessions
- Missed 1: resume plan, do not make up intensity
- Missed 2+: rebuild week around easy volume first, delay intensity

### 7.4 Signal 4: Schedule reality
If chaotic week, prioritize Big 2:
1. one long/easy aerobic (or longest available)
2. one strength (or short mobility if very tight)

If week is infeasible (`days_available <= 1` or constraints make all candidate sessions non-viable):
- do not create a new plan
- keep existing plan unchanged
- emit `plan_update_status = unchanged_infeasible_week`
- send fallback guidance: one optional short mobility/recovery touch only

## 8. Track Catalog (exactly 6)
1. `general_low_time`
2. `general_moderate_time`
3. `main_base`
4. `main_build`
5. `main_peak_taper`
6. `return_or_risk_managed`

Track assignment logic:
- No main sport + low time (`2_3h`) -> `general_low_time`
- No main sport + `4_6h` or above -> `general_moderate_time`
- Main sport + phase `base` -> `main_base`
- Main sport + phase `build` -> `main_build`
- Main sport + phase `peak_taper` -> `main_peak_taper`
- Any `return_to_training` OR risk in `red_a | red_b` -> `return_or_risk_managed` (highest priority override)
- Messaging consistency rule:
  - if track is `return_or_risk_managed`, suppress performance/peak language in email payload
  - prefer safety + consistency framing only

## 9. Universal Weekly Intake Questions (exact set)
1. Main goal right now + event date (if any)
2. Sports completed last week + minutes
3. Realistic training days available this week
4. Pain 0-10 + location
5. Energy/stress/sleep (1-10 + quick note)
6. Preference: structure vs flexibility

## 10. API/Function Boundaries (implementation contract)

### 10.1 Required functions
- `classify_intake(profile_input) -> profile`
- `resolve_effective_performance_intent(profile, checkin) -> bool`
- `derive_phase(profile, checkin, today_date, rule_state, risk_flag, effective_performance_intent) -> phase`
- `derive_risk(profile, checkin, rule_state) -> risk_flag`
- `select_track(profile, phase, risk_flag) -> track`
- `should_switch_main_sport(profile, rule_state, explicit_request) -> bool`
- `build_weekly_skeleton(profile, track, phase, risk_flag, effective_performance_intent, rule_state) -> session_template[]`
- `route_today_action(checkin, risk_flag, track) -> today_action + adjustments[]`
- `compose_email_payload(profile, checkin, engine_output) -> email_payload`
- `format_weekly_output_mode(profile.structure_preference, weekly_skeleton) -> ordered_plan | priority_menu`
- `validate_event_date(checkin, today_date) -> valid | invalid_missing | invalid_format | invalid_past`
- `load_rule_state(athlete_id) -> rule_state`
- `update_rule_state(athlete_id, weekly_inputs, decisions) -> rule_state`
- `detect_inconsistent_training(phase_history, current_phase, risk_flag) -> bool`
- `derive_yellow_thresholds(checkin, rule_state) -> bool`
- `enforce_flexible_mode_intensity_budget(plan_menu) -> validated_menu`

### 10.2 Processing order
1. Normalize inputs
2. Load rule state
3. Update/derive profile fields
4. Resolve `effective_performance_intent`
5. Determine risk
6. Determine phase (using derived `risk_flag` and `effective_performance_intent`)
7. Assign track
8. Build weekly skeleton
9. Apply session-level routing overrides
10. Emit email payload
11. Update rule state

## 11. Guardrails
- Never prescribe intensity on `red_a` or `red_b` risk.
- Never "make up" missed intensity sessions.
- If pain worsens week-to-week, auto-escalate to `red_b`.
- If constraints conflict (e.g., no equipment), choose feasible alternatives.
- Deterministic output: same input must produce same plan output.
- If output mode is flexible, never schedule hard days back-to-back.
- If event date is invalid/missing/past when needed, do not re-phase; keep current plan and request clarification.
- If no feasible week can be constructed, do not replace existing plan.
- In flexibility mode, enforce intensity budget: max 2 hard sessions/week and never on adjacent days.
- Hard session definition (for intensity budget):
  - hard tags: `quality | intervals | tempo | threshold | vo2 | race_sim | hills_hard`
  - not hard: `easy_aerobic | recovery | skills | mobility | strength`
- When in risk-managed track, never emit conflicting peak/performance wording.
- `disclaimer_short` is mandatory for `red_b` payloads.

## 12. Minimal Test Matrix (must-have)
- Intake mapping tests for each Q1-Q4 bucket
- `effective_performance_intent` fallback tests (`this_week` -> profile -> default false)
- Rule-state bootstrap/rolling-window tests (`last_4`/`last_6` behavior)
- Event-intent validation tests for `has_upcoming_event` true/null behavior
- Phase derivation tests (`base/build/peak_taper/return_to_training`) including inclusive boundary checks at weeks 12/4/3 and conservative override behavior
- Conservative-override priority tests confirming precedence: `red_b > red_a > return-context > yellow > new`
- Risk derivation tests (`green/yellow/red_a/red_b`) including yellow threshold boundaries and deterministic worsening checks
- Track assignment tests including override precedence
- Main-sport switch governance tests (explicit request, 60%/2-week + 120 min floor, anti-churn freeze behavior)
- Skeleton generation by time bucket + plan type, including 10h+ add-on caps
- Main-sport deload cadence tests + sustained-yellow trigger tests + taper-supersedes-deload tests
- Quality archetype mapping tests by experience + risk gates
- Session routing tests for pain/energy/missed/chaotic branches
- Flexibility output tests: anchor/filler/optional menu and no back-to-back hard day recommendation
- Flexible-mode intensity budget tests (max hard-session count and spacing)
- Safety regression test: red-tier risk never emits quality/intensity session
- Event-date validation tests: missing/invalid/past date keep prior plan and emit clarification status
- Return-context precedence tests over calendar-derived phase
- Infeasible-week tests: no new plan emitted; existing plan unchanged
- Track/message consistency tests: risk-managed track suppresses performance language
- Inconsistent-training stabilization tests: requires 2 consecutive check-ins for phase upgrade
- Email payload contract tests for required fields and mandatory red_b disclaimer

## 13. Example Mappings

### 13.1 Intermediate runner, hybrid seasonal, 4-6h
Input: main sport run, event in 9 weeks, intermediate, 4_6h, recurring niggles, `performance_intent_this_week=true`
Output:
- phase: `build`
- risk: `yellow`
- track: `main_build`
- skeleton: easy run, easy run, reduced quality/easy, strength or easy swim

### 13.2 Casual mixed athlete, 2-3h
Input: no main sport, general consistency goal, new, 2_3h, `performance_intent_this_week=null`, `performance_intent_default=false`
Output:
- phase: n/a (general)
- risk: typically `green` unless symptoms reported
- track: `general_low_time`
- skeleton: easy aerobic, strength/mobility, fun/variety

## 14. Output Mode Rules (structure vs flexibility)
- If `structure_preference == structure`:
  - emit ordered weekly plan
- If `structure_preference == flexibility`:
  - emit priority menu:
    - Priority 1 (anchor): long easy aerobic
    - Priority 2 (anchor): strength session
    - Choose 1-2 fillers: easy aerobic OR skills OR short tempo (green only)
    - Optional: recovery session (walk/mobility/easy spin)
- If `structure_preference == mixed`:
  - emit ordered anchors + flexible fillers
- Global rule: never recommend two hard days back-to-back.
