# Response Generation Quality Bench

This benchmark captures realistic outgoing coaching emails from the response-generation module.
It is designed for manual semantic review, not deterministic scoring.

## Scenario contract

Each scenario in the machine-readable block includes:

- `id`
- `name`
- `response_brief`
- optional `review_focus`
- optional `notes`

```json
[
  {
    "id": "RG-001",
    "name": "new_user_no_profile_clarification",
    "response_brief": {
      "reply_mode": "clarification",
      "athlete_context": {},
      "decision_context": {
        "clarification_needed": true,
        "clarification_questions": [
          "- Your primary goal (e.g., first marathon, improve 10k time)",
          "- Days available to train each week",
          "- Any current pain or injury concerns"
        ]
      },
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "Need help getting started",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Does the reply ask only for missing data?",
      "Does it avoid pretending a plan already exists?"
    ],
    "notes": "Brand new registered athlete."
  },
  {
    "id": "RG-002",
    "name": "new_user_partial_profile_clarification",
    "response_brief": {
      "reply_mode": "clarification",
      "athlete_context": {
        "goal_summary": "Half marathon this spring",
        "experience_level": "beginner"
      },
      "decision_context": {
        "clarification_needed": true,
        "clarification_questions": [
          "- Event date",
          "- Current longest run in the last 14 days",
          "- Any pain during or after running"
        ]
      },
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "I signed up for a race",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Question quality for missing data",
      "Clarity and brevity"
    ]
  },
  {
    "id": "RG-003",
    "name": "new_user_first_plan_normal_coaching_with_connect_link",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "General consistency and better energy",
        "experience_level": "beginner",
        "structure_preference": "flexibility"
      },
      "decision_context": {
        "track": "general_low_time",
        "phase": "base",
        "risk_flag": "green",
        "today_action": "keep_load_light_and_repeatable",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: three repeatable sessions with one simple strength day.",
        "weekly_skeleton": [
          "easy_aerobic",
          "strength",
          "easy_aerobic"
        ],
        "session_guidance": [
          "Keep all runs conversational this week",
          "Use a short bodyweight strength circuit once"
        ],
        "adjustments_or_priorities": [
          "Consistency beats intensity in week one",
          "Leave each session feeling able to do one more"
        ],
        "if_then_rules": [
          "If soreness exceeds mild discomfort, replace the next run with brisk walking"
        ]
      },
      "delivery_context": {
        "inbound_subject": "Can you make me a first week plan?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email",
        "connect_strava_link": "https://geniml.com/action/tok_new001"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Coach-like tone for first-week guidance",
      "Useful action framing without overloading details"
    ]
  },
  {
    "id": "RG-004",
    "name": "mid_build_no_memory_green_risk",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "10k in 7 weeks",
        "experience_level": "intermediate",
        "structure_preference": "structure"
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "green",
        "today_action": "execute_key_workouts_as_planned",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: one threshold session, one interval session, and protected recovery.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "strength",
          "easy_aerobic",
          "intervals"
        ],
        "session_guidance": [
          "Keep threshold effort controlled, not all-out",
          "Treat interval day as quality with full recoveries"
        ],
        "adjustments_or_priorities": [
          "Protect easy-day pace between quality sessions",
          "Keep strength short and clean, no max lifts"
        ],
        "if_then_rules": [
          "If interval mechanics deteriorate, stop the set early"
        ]
      },
      "delivery_context": {
        "inbound_subject": "How should this week look?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": true,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Does it prioritize what matters this week?",
      "Does it avoid robotic rendering of plan fields?"
    ]
  },
  {
    "id": "RG-005",
    "name": "mid_build_with_schedule_constraint_memory",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Half marathon in 9 weeks",
        "experience_level": "intermediate",
        "constraints_summary": "Weekday sessions must finish before 7am."
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "yellow",
        "today_action": "do_planned_but_conservative",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: keep one quality run but reduce total stress.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "easy_aerobic",
          "strength"
        ],
        "session_guidance": [
          "One controlled tempo only if legs feel steady",
          "Keep easy runs fully conversational"
        ],
        "adjustments_or_priorities": [
          "Protect recovery sleep over volume",
          "Do not stack hard days"
        ],
        "if_then_rules": [
          "If morning readiness is poor, replace tempo with easy aerobic"
        ],
        "safety_note": "Back off intensity if pain trends upward."
      },
      "delivery_context": {
        "inbound_subject": "I feel a bit flat this week",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 1,
            "fact_type": "constraint",
            "fact_key": "weekday_before_7am_cutoff",
            "summary": "Weekday sessions need to finish before 7am due to school drop-off.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Athlete has been consistent but reports lower morning freshness.",
          "last_recommendation": "Keep quality controlled and prioritize easy-day recovery.",
          "open_loops": [
            "How did the controlled tempo feel?"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true,
        "continuity_focus": "Consistency is good; preserve freshness with conservative quality.",
        "priority_memory_notes": [
          {
            "memory_note_id": 1,
            "fact_type": "constraint",
            "fact_key": "weekday_before_7am_cutoff",
            "summary": "Weekday sessions need to finish before 7am due to school drop-off.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ]
      }
    },
    "review_focus": [
      "Personalization from memory without overfitting",
      "Continuity across current and prior guidance"
    ]
  },
  {
    "id": "RG-006",
    "name": "travel_week_temporary_disruption",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Marathon in 12 weeks",
        "experience_level": "intermediate",
        "structure_preference": "mixed"
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "yellow",
        "today_action": "consolidate_load_for_travel_week",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: simplify quality and preserve rhythm during travel.",
        "weekly_skeleton": [
          "easy_aerobic",
          "strength",
          "easy_aerobic",
          "recovery"
        ],
        "session_guidance": [
          "Use treadmill incline blocks instead of outdoor intervals",
          "Keep long run shorter this travel week"
        ],
        "adjustments_or_priorities": [
          "Temporary reduction is strategic, not a setback"
        ],
        "if_then_rules": [
          "If travel fatigue spikes, replace quality with easy aerobic"
        ]
      },
      "delivery_context": {
        "inbound_subject": "I am traveling next week",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 2,
            "fact_type": "schedule",
            "fact_key": "sunday_long_run_anchor",
            "summary": "Sunday is usually the long-run anchor.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "One-week travel disruption with limited equipment.",
          "last_recommendation": "Keep training simple and resume normal structure after travel.",
          "open_loops": [
            "Confirm access to treadmill and dumbbells"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true
      }
    },
    "review_focus": [
      "Temporary disruption framing",
      "Clear return-to-normal expectation"
    ]
  },
  {
    "id": "RG-007",
    "name": "injury_history_yellow_controlled_push",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Olympic triathlon in 10 weeks",
        "experience_level": "intermediate",
        "constraints_summary": "Right Achilles has flared after back-to-back hard sessions before."
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "yellow",
        "today_action": "single_quality_session_only",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: hold progression with one quality bike session and controlled run load.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "easy_aerobic",
          "strength",
          "recovery"
        ],
        "session_guidance": [
          "Limit run intensity this week",
          "Use bike quality for primary stimulus"
        ],
        "adjustments_or_priorities": [
          "Protect Achilles tendon load",
          "Favor consistency over forcing progression"
        ],
        "if_then_rules": [
          "If Achilles pain rises above mild, remove run intensity immediately"
        ],
        "safety_note": "Do not run through tendon pain escalation."
      },
      "delivery_context": {
        "inbound_subject": "Can I push harder this week?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 3,
            "fact_type": "constraint",
            "fact_key": "achilles_reacts_to_back_to_back_intensity",
            "summary": "Right Achilles tends to flare after two hard run days in a row.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Recent progression was positive but tendon history remains the primary limiter.",
          "last_recommendation": "Keep one quality run and one quality bike session separated.",
          "open_loops": [
            "Report next-morning Achilles response"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true
      }
    },
    "review_focus": [
      "Risk-constrained coaching clarity",
      "Appropriate safety posture without panic tone"
    ]
  },
  {
    "id": "RG-008",
    "name": "red_a_safety_managed_pause",
    "response_brief": {
      "reply_mode": "safety_risk_managed",
      "athlete_context": {
        "goal_summary": "Marathon in 6 weeks",
        "experience_level": "intermediate"
      },
      "decision_context": {
        "track": "return_or_risk_managed",
        "phase": "risk_management",
        "risk_flag": "red_a",
        "today_action": "pause_training_and_seek_medical_guidance",
        "plan_update_status": "unchanged"
      },
      "validated_plan": {
        "plan_summary": "Current plan paused pending symptom evaluation.",
        "safety_note": "No intensity until cleared by a clinician."
      },
      "delivery_context": {
        "inbound_subject": "Sharp chest pain during run",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Unmistakable caution and escalation language",
      "No normal training encouragement"
    ]
  },
  {
    "id": "RG-009",
    "name": "red_b_safety_managed_with_history",
    "response_brief": {
      "reply_mode": "safety_risk_managed",
      "athlete_context": {
        "goal_summary": "Half marathon in 8 weeks",
        "experience_level": "beginner"
      },
      "decision_context": {
        "track": "return_or_risk_managed",
        "phase": "risk_management",
        "risk_flag": "red_b",
        "today_action": "stop_training_and_get_clinical_assessment",
        "plan_update_status": "unchanged"
      },
      "validated_plan": {
        "plan_summary": "Training load is paused due to elevated symptom risk.",
        "safety_note": "Do not resume hard sessions without medical guidance."
      },
      "delivery_context": {
        "inbound_subject": "Dizziness and severe fatigue",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": false,
        "memory_notes": [
          {
            "memory_note_id": 4,
            "fact_type": "other",
            "fact_key": "prior_episode_of_dizziness_under_load",
            "summary": "Athlete previously reported dizziness during a hard run.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Prior similar symptom episode increases concern level.",
          "last_recommendation": "Escalate to medical guidance before training decisions.",
          "open_loops": [
            "Share clinician guidance before next step"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true
      }
    },
    "review_focus": [
      "Safety-first communication",
      "Appropriate use of continuity without speculation"
    ]
  },
  {
    "id": "RG-010",
    "name": "lightweight_question_easy_run_pace",
    "response_brief": {
      "reply_mode": "lightweight_non_planning",
      "athlete_context": {
        "goal_summary": "5k progression",
        "experience_level": "beginner"
      },
      "decision_context": {},
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "How easy should easy runs feel?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": true,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Direct answer without full weekly rewrite",
      "Coach-like simplicity"
    ]
  },
  {
    "id": "RG-011",
    "name": "lightweight_milestone_update_acknowledgement",
    "response_brief": {
      "reply_mode": "lightweight_non_planning",
      "athlete_context": {
        "goal_summary": "10k in 6 weeks",
        "experience_level": "intermediate"
      },
      "decision_context": {},
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "I hit a PR today",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 5,
            "fact_type": "preference",
            "fact_key": "prefers_short_actionable_replies",
            "summary": "Athlete prefers concise guidance over long explanations.",
            "importance": "medium",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Athlete has two weeks of steady progress and positive check-ins.",
          "last_recommendation": "Protect recovery day after quality progress.",
          "open_loops": [
            "Confirm recovery-day effort stayed easy"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true
      }
    },
    "review_focus": [
      "Balanced acknowledgment + immediate actionable cue",
      "Avoid unnecessary planning complexity"
    ]
  },
  {
    "id": "RG-012",
    "name": "off_topic_redirect_supplement_question",
    "response_brief": {
      "reply_mode": "off_topic_redirect",
      "athlete_context": {
        "goal_summary": "Half marathon",
        "experience_level": "beginner"
      },
      "decision_context": {},
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "Which supplement brand should I buy?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Polite redirect to coaching scope",
      "Non-dismissive tone"
    ]
  },
  {
    "id": "RG-013",
    "name": "off_topic_redirect_non_training_request",
    "response_brief": {
      "reply_mode": "off_topic_redirect",
      "athlete_context": {
        "goal_summary": "General fitness",
        "experience_level": "beginner"
      },
      "decision_context": {},
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "Can you review my startup pitch deck?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Clean scope boundary",
      "Effective redirection prompt for a training-related follow-up"
    ]
  },
  {
    "id": "RG-014",
    "name": "late_build_with_strong_memory_continuity",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Marathon in 5 weeks",
        "experience_level": "advanced",
        "structure_preference": "structure"
      },
      "decision_context": {
        "track": "main_build",
        "phase": "specific_prep",
        "risk_flag": "green",
        "today_action": "execute_long_run_specificity_block",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: race-specific long run plus controlled mid-week quality.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "easy_aerobic",
          "strength",
          "long_progression"
        ],
        "session_guidance": [
          "Keep mid-week quality at marathon-to-threshold control",
          "Long run includes final segment at goal rhythm"
        ],
        "adjustments_or_priorities": [
          "Fuel rehearsal is mandatory this week",
          "Protect sleep ahead of long-run day"
        ],
        "if_then_rules": [
          "If long-run HR drifts unusually early, cut the progression segment"
        ]
      },
      "delivery_context": {
        "inbound_subject": "How should I handle this key week?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 6,
            "fact_type": "schedule",
            "fact_key": "sunday_long_run_anchor",
            "summary": "Sunday is the long-run anchor and usually has best compliance.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          },
          {
            "memory_note_id": 7,
            "fact_type": "preference",
            "fact_key": "prefers_clear_priority_ordering",
            "summary": "Athlete prefers explicit priority order for key sessions.",
            "importance": "medium",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Three consistent weeks completed with improved long-run execution.",
          "last_recommendation": "Hold structure and execute one race-specific long run this week.",
          "open_loops": [
            "Report fuel tolerance during long progression"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true,
        "continuity_focus": "Continue race-specific work while keeping load controlled.",
        "priority_memory_notes": [
          {
            "memory_note_id": 6,
            "fact_type": "schedule",
            "fact_key": "sunday_long_run_anchor",
            "summary": "Sunday is the long-run anchor and usually has best compliance.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "supporting_memory_notes": [
          {
            "memory_note_id": 7,
            "fact_type": "preference",
            "fact_key": "prefers_clear_priority_ordering",
            "summary": "Athlete prefers explicit priority order for key sessions.",
            "importance": "medium",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ]
      }
    },
    "review_focus": [
      "High-quality continuity in wording",
      "Practical guidance for race-specific build week"
    ]
  },
  {
    "id": "RG-015",
    "name": "conflicting_memory_priority_resolution",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Marathon in 11 weeks",
        "experience_level": "intermediate",
        "structure_preference": "mixed"
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "green",
        "today_action": "keep_standard_progression",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: normal progression with one long aerobic anchor.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "easy_aerobic",
          "long_aerobic"
        ],
        "session_guidance": [
          "One moderate quality session and one long aerobic session",
          "No second hard run this week"
        ],
        "adjustments_or_priorities": [
          "Use the current schedule constraint as primary reality"
        ]
      },
      "delivery_context": {
        "inbound_subject": "Can we keep my old Wednesday double?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 8,
            "fact_type": "constraint",
            "fact_key": "new_weekday_meeting_blocks_early_double",
            "summary": "New recurring weekday meeting blocks the old Wednesday double-session pattern.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          },
          {
            "memory_note_id": 9,
            "fact_type": "schedule",
            "fact_key": "historical_wednesday_double",
            "summary": "Historically completed Wednesday doubles during prior block.",
            "importance": "medium",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Schedule changed recently; old double-day pattern is no longer reliable.",
          "last_recommendation": "Anchor quality around feasible single-session days.",
          "open_loops": [
            "Confirm feasible replacement day for short strength"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true,
        "priority_memory_notes": [
          {
            "memory_note_id": 8,
            "fact_type": "constraint",
            "fact_key": "new_weekday_meeting_blocks_early_double",
            "summary": "New recurring weekday meeting blocks the old Wednesday double-session pattern.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "supporting_memory_notes": [
          {
            "memory_note_id": 9,
            "fact_type": "schedule",
            "fact_key": "historical_wednesday_double",
            "summary": "Historically completed Wednesday doubles during prior block.",
            "importance": "medium",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ]
      }
    },
    "review_focus": [
      "Priority note should dominate over stale supporting context",
      "No contradictory recommendation"
    ]
  },
  {
    "id": "RG-016",
    "name": "return_to_training_low_load_rebuild",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Back to consistent training after illness",
        "experience_level": "beginner",
        "structure_preference": "structure"
      },
      "decision_context": {
        "track": "return_or_risk_managed",
        "phase": "return_to_training",
        "risk_flag": "yellow",
        "today_action": "low_load_consistency_rebuild",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: low-load rebuild with conservative progression.",
        "weekly_skeleton": [
          "easy_aerobic",
          "recovery",
          "easy_aerobic",
          "strength"
        ],
        "session_guidance": [
          "Short easy sessions only for the first week back",
          "Skip intensity entirely this week"
        ],
        "if_then_rules": [
          "If fatigue rebounds the day after a session, reduce next session duration by half"
        ],
        "safety_note": "No hard work until easy sessions feel stable again."
      },
      "delivery_context": {
        "inbound_subject": "Ready to train again after being sick",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Conservative progression tone",
      "Clear short-term action priorities"
    ]
  },
  {
    "id": "RG-017",
    "name": "clarification_event_date_and_availability_only",
    "response_brief": {
      "reply_mode": "clarification",
      "athlete_context": {
        "goal_summary": "First sprint triathlon",
        "experience_level": "beginner"
      },
      "decision_context": {
        "clarification_needed": true,
        "clarification_questions": [
          "- Confirm your race date",
          "- Confirm how many training days you can commit each week"
        ]
      },
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "I want to start tri training",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": false,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "Tight question set",
      "No invented assumptions"
    ]
  },
  {
    "id": "RG-018",
    "name": "normal_coaching_with_connect_strava_optional_mention",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "10k race in 10 weeks",
        "experience_level": "beginner",
        "structure_preference": "flexibility"
      },
      "decision_context": {
        "track": "general_moderate_time",
        "phase": "base",
        "risk_flag": "green",
        "today_action": "start_consistency_block",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: simple consistency block with one technique-focused quality stimulus.",
        "weekly_skeleton": [
          "easy_aerobic",
          "strength",
          "easy_aerobic",
          "strides"
        ],
        "session_guidance": [
          "Keep all runs conversational except brief strides",
          "Use strength to support running mechanics"
        ],
        "adjustments_or_priorities": [
          "Track consistency first, pace second"
        ]
      },
      "delivery_context": {
        "inbound_subject": "Can you set my first month?",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email",
        "connect_strava_link": "https://geniml.com/action/tok_connect_018"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": false,
        "post_reply_refresh_eligible": true,
        "memory_notes": [],
        "continuity_summary": null,
        "memory_available": false
      }
    },
    "review_focus": [
      "High-signal weekly framing",
      "Optional action link mention should be brief and natural"
    ]
  },
  {
    "id": "RG-019",
    "name": "lightweight_followup_with_memory_open_loop",
    "response_brief": {
      "reply_mode": "lightweight_non_planning",
      "athlete_context": {
        "goal_summary": "Marathon in 9 weeks",
        "experience_level": "intermediate"
      },
      "decision_context": {},
      "validated_plan": {},
      "delivery_context": {
        "inbound_subject": "Yesterday's tempo felt too hard",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 10,
            "fact_type": "preference",
            "fact_key": "prefers_rpe_based_cues",
            "summary": "Athlete responds better to RPE cues than fixed pace targets.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Recent quality sessions are landing a bit too hard relative to target effort.",
          "last_recommendation": "Use RPE and breathing cues to cap intensity.",
          "open_loops": [
            "Confirm next tempo effort target felt sustainable"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true,
        "continuity_focus": "Keep intensity calibrated by feel, not pace."
      }
    },
    "review_focus": [
      "Useful immediate answer",
      "Continuity-aware language in lightweight mode"
    ]
  },
  {
    "id": "RG-020",
    "name": "post_travel_return_to_normal_structure",
    "response_brief": {
      "reply_mode": "normal_coaching",
      "athlete_context": {
        "goal_summary": "Marathon in 10 weeks",
        "experience_level": "intermediate",
        "structure_preference": "mixed"
      },
      "decision_context": {
        "track": "main_build",
        "phase": "build",
        "risk_flag": "green",
        "today_action": "resume_standard_structure",
        "plan_update_status": "updated"
      },
      "validated_plan": {
        "plan_summary": "Current plan: return from travel to normal structure with controlled re-entry.",
        "weekly_skeleton": [
          "easy_aerobic",
          "tempo",
          "easy_aerobic",
          "strength",
          "long_aerobic"
        ],
        "session_guidance": [
          "Resume one quality session and one long aerobic anchor",
          "Keep first quality session conservative after travel"
        ],
        "adjustments_or_priorities": [
          "Restore rhythm before increasing load"
        ],
        "if_then_rules": [
          "If residual travel fatigue remains on day two, shift quality by 24 hours"
        ]
      },
      "delivery_context": {
        "inbound_subject": "Back from travel and ready to resume",
        "selected_model_name": "gpt-5-mini",
        "response_channel": "email"
      },
      "memory_context": {
        "pre_reply_refresh_attempted": true,
        "post_reply_refresh_eligible": true,
        "memory_notes": [
          {
            "memory_note_id": 11,
            "fact_type": "schedule",
            "fact_key": "sunday_long_run_anchor",
            "summary": "Sunday long run remains the best compliance anchor.",
            "importance": "high",
            "status": "active",
            "created_at": 1773273600,
            "updated_at": 1773273600,
            "last_confirmed_at": 1773273600
          }
        ],
        "continuity_summary": {
          "summary": "Travel phase is complete; athlete is transitioning back to normal structure.",
          "last_recommendation": "Use one conservative quality session in the first week back.",
          "open_loops": [
            "Report fatigue trend after first two sessions back"
          ],
          "updated_at": 1773273600
        },
        "memory_available": true
      }
    },
    "review_focus": [
      "Transition language from disruption to normal training",
      "Actionability and confidence without overpromising"
    ]
  }
]
```
