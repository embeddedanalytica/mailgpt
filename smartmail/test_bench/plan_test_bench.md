# Planner LLM Test Bench

This file is a markdown fixture for validating PlannerLLM outputs against deterministic RE4 rule guardrails.

## Scenario Contract

Each scenario in the machine-readable block includes:

- `id`
- `name`
- `profile`
- `checkin`
- `phase`
- `risk_flag`
- `track`
- `effective_performance_intent`
- `fallback_skeleton`
- `required_goal_tokens`
- optional `adjustments`
- optional `today_action`
- optional `routing_context`

---

## Scenarios

### PS-001
New athlete constrained start (yellow risk) with simple consistency focus.

### PS-002
New athlete with chaotic week and flexible structure preference.

### PS-003
Experienced marathon athlete in build phase with green risk.

### PS-004
High-availability experienced build week with strong performance intent.

### PS-005
Experienced athlete with yellow risk where ambition should be controlled.

### PS-006
Risk-managed return-to-training week with red-tier guardrails.

---

## Optional machine-readable block

```json
[
  {
    "id": "PS-001",
    "name": "new_athlete_constrained_start",
    "profile": {
      "goal_category": "general_consistency",
      "main_sport_current": "run",
      "time_bucket": "2_3h",
      "structure_preference": "structure"
    },
    "checkin": {
      "days_available": 3,
      "structure_preference": "structure",
      "has_upcoming_event": false
    },
    "phase": "base",
    "risk_flag": "yellow",
    "track": "general_low_time",
    "effective_performance_intent": false,
    "fallback_skeleton": ["easy_aerobic", "strength", "easy_aerobic"],
    "required_goal_tokens": ["easy_aerobic", "strength"]
  },
  {
    "id": "PS-002",
    "name": "new_athlete_chaotic_feasible",
    "profile": {
      "goal_category": "general_consistency",
      "main_sport_current": "run",
      "time_bucket": "4_6h",
      "structure_preference": "flexibility"
    },
    "checkin": {
      "days_available": 3,
      "week_chaotic": true,
      "structure_preference": "flexibility",
      "has_upcoming_event": false
    },
    "phase": "base",
    "risk_flag": "green",
    "track": "general_moderate_time",
    "effective_performance_intent": false,
    "fallback_skeleton": ["easy_aerobic", "strength", "easy_aerobic"],
    "required_goal_tokens": ["easy_aerobic", "strength"]
  },
  {
    "id": "PS-003",
    "name": "experienced_marathon_8w_green",
    "profile": {
      "goal_category": "event_8_16w",
      "main_sport_current": "run",
      "time_bucket": "7_10h",
      "structure_preference": "structure"
    },
    "checkin": {
      "days_available": 5,
      "has_upcoming_event": true,
      "event_date": "2026-05-07"
    },
    "phase": "build",
    "risk_flag": "green",
    "track": "main_build",
    "effective_performance_intent": true,
    "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals"],
    "required_goal_tokens": ["tempo", "intervals", "easy_aerobic"]
  },
  {
    "id": "PS-004",
    "name": "experienced_high_availability_build",
    "profile": {
      "goal_category": "performance_16w_plus",
      "main_sport_current": "run",
      "time_bucket": "10h_plus",
      "structure_preference": "mixed"
    },
    "checkin": {
      "days_available": 6,
      "has_upcoming_event": true,
      "event_date": "2026-06-15"
    },
    "phase": "build",
    "risk_flag": "green",
    "track": "main_build",
    "effective_performance_intent": true,
    "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals", "easy_aerobic"],
    "required_goal_tokens": ["tempo", "intervals", "easy_aerobic"]
  },
  {
    "id": "PS-005",
    "name": "experienced_yellow_controlled_push",
    "profile": {
      "goal_category": "event_8_16w",
      "main_sport_current": "run",
      "time_bucket": "7_10h",
      "structure_preference": "structure"
    },
    "checkin": {
      "days_available": 5,
      "has_upcoming_event": true,
      "event_date": "2026-05-01"
    },
    "phase": "build",
    "risk_flag": "yellow",
    "track": "main_build",
    "effective_performance_intent": true,
    "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "recovery"],
    "required_goal_tokens": ["tempo", "easy_aerobic"]
  },
  {
    "id": "PS-006",
    "name": "risk_managed_red_tier",
    "profile": {
      "goal_category": "general_consistency",
      "main_sport_current": "run",
      "time_bucket": "4_6h",
      "structure_preference": "structure"
    },
    "checkin": {
      "days_available": 4,
      "has_upcoming_event": false
    },
    "phase": "return_to_training",
    "risk_flag": "red_b",
    "track": "return_or_risk_managed",
    "effective_performance_intent": false,
    "fallback_skeleton": ["easy_aerobic", "strength", "recovery", "easy_aerobic"],
    "required_goal_tokens": ["easy_aerobic", "recovery", "strength"]
  }
]
```
