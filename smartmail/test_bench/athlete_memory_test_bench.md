# Athlete Memory Test Bench

This file is a markdown fixture for validating live athlete-memory refresh behavior across sequential athlete communications.

## Scenario Contract

Each scenario in the machine-readable block includes:

- `id`
- `athlete_name`
- `sport`
- `profile_hint`
- `messages`
- `final_assertions`

Each scenario has exactly 5 messages. Each message includes:

- `step`
- `email`
- `synthetic_coach_reply`
- `durable_truths`
- `active_context`
- `active_context_mode`
- `retired_truths`
- `routine_noise`
- `coach_should_adjust_for`
- `coach_should_not_do`
- `message_intent`

Each fact is represented as a small phrase-set object:

- `label`
- `signals`
- optional `aliases`
- optional `semantic_signals`
- `importance`

Final assertions include:

- `final_durable_truths`
- `final_retrieval_support`
- `final_retired_truths`

---

## Optional machine-readable block

```json
[
  {
    "id": "AM-001",
    "athlete_name": "Maya Chen",
    "sport": "marathon running",
    "profile_hint": "Experienced marathoner training mostly before sunrise with childcare-driven weekend limits.",
    "messages": [
      {
        "step": 1,
        "email": "I'm building toward the Bay Crest Marathon this fall. On weekdays I need to be done before 7am because I have school drop-off, and Saturdays have been a no-go for training while my partner works. Most weeks I run five days and keep Sunday as my long run.",
        "synthetic_coach_reply": "Keep the weekday work early, protect Sunday for the long run, and we will build around the current Saturday family constraint.",
        "durable_truths": [
          {
            "label": "before 7am",
            "signals": [
              "before 7am"
            ],
            "importance": "high",
            "aliases": [
              "weekday workouts must finish by 7:00am for school drop-off",
              "finish by 7:00am due to school drop-off",
              "weekday workouts must finish before 7:00am due to school drop-off",
              "must finish before 7am due to school drop-off"
            ],
            "semantic_signals": []
          },
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "high",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          },
          {
            "label": "bay marathon",
            "signals": [
              "bay marathon"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for marathon",
            "signals": [
              "marathon"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for build",
            "signals": [
              "build"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sunday",
            "signals": [
              "sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses long",
            "signals": [
              "long"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses run",
            "signals": [
              "run"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: check, saturday, constraint",
            "signals": [
              "check saturday constraint"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Quick update: I hit the Tuesday tempo and Thursday easy run, and today's easy miles felt smooth. Nothing new schedule-wise, just wanted that on your radar.",
        "synthetic_coach_reply": "Good. Hold the same structure and let me know after Sunday's long run how the legs feel.",
        "durable_truths": [
          {
            "label": "before 7am",
            "signals": [
              "before 7am"
            ],
            "importance": "medium",
            "aliases": [
              "weekday workouts must finish by 7:00am for school drop-off",
              "finish by 7:00am due to school drop-off",
              "weekday workouts must finish before 7:00am due to school drop-off",
              "must finish before 7am due to school drop-off"
            ],
            "semantic_signals": []
          },
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "medium",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          },
          {
            "label": "bay marathon",
            "signals": [
              "bay marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: tempo",
            "signals": [
              "tempo"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: smooth",
            "signals": [
              "smooth"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for tempo",
            "signals": [
              "tempo"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for smooth",
            "signals": [
              "smooth"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: sunday, long, run",
            "signals": [
              "sunday long run"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Next week is temporary chaos because I'm in Denver for work and the hotel gym only has a treadmill. I won't have my usual route options or Sunday long-run loop just for that trip.",
        "synthetic_coach_reply": "Treat the Denver week as a short treadmill block and resume the normal marathon rhythm when you're home.",
        "durable_truths": [
          {
            "label": "before 7am",
            "signals": [
              "before 7am"
            ],
            "importance": "medium",
            "aliases": [
              "weekday workouts must finish by 7:00am for school drop-off",
              "finish by 7:00am due to school drop-off",
              "weekday workouts must finish before 7:00am due to school drop-off",
              "must finish before 7am due to school drop-off"
            ],
            "semantic_signals": []
          },
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "medium",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          },
          {
            "label": "bay marathon",
            "signals": [
              "bay marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "denver hotel",
            "signals": [
              "denver hotel"
            ],
            "importance": "high",
            "aliases": [
              "denver",
              "hotel treadmill"
            ],
            "semantic_signals": []
          },
          {
            "label": "treadmill",
            "signals": [
              "treadmill"
            ],
            "importance": "high",
            "aliases": [
              "hotel treadmill",
              "travel week"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: denver",
            "signals": [
              "denver"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: treadmill",
            "signals": [
              "treadmill"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for denver",
            "signals": [
              "denver"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for treadmill",
            "signals": [
              "treadmill"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses resume",
            "signals": [
              "resume"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, home",
            "signals": [
              "when home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "One thing that is probably here to stay: I joined a Tuesday lunch strength group at work, so that slot is now consistently available for a short lift after my run.",
        "synthetic_coach_reply": "Great. We'll treat Tuesday lunch strength as a durable part of the week alongside the early runs.",
        "durable_truths": [
          {
            "label": "before 7am",
            "signals": [
              "before 7am"
            ],
            "importance": "medium",
            "aliases": [
              "weekday workouts must finish by 7:00am for school drop-off",
              "finish by 7:00am due to school drop-off",
              "weekday workouts must finish before 7:00am due to school drop-off",
              "must finish before 7am due to school drop-off"
            ],
            "semantic_signals": []
          },
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "medium",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          },
          {
            "label": "bay marathon",
            "signals": [
              "bay marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday lunch strength",
            "signals": [
              "tuesday lunch strength"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "denver hotel",
            "signals": [
              "denver hotel"
            ],
            "importance": "high",
            "aliases": [
              "denver",
              "hotel treadmill"
            ],
            "semantic_signals": []
          },
          {
            "label": "treadmill trip",
            "signals": [
              "treadmill trip"
            ],
            "importance": "high",
            "aliases": [
              "hotel treadmill",
              "travel week"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: denver",
            "signals": [
              "denver"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: treadmill",
            "signals": [
              "treadmill"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for tuesday",
            "signals": [
              "tuesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for strength",
            "signals": [
              "strength"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: settles, in",
            "signals": [
              "settles in"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Good news: childcare shifted, so Saturdays are open again and I can train then if needed.",
        "synthetic_coach_reply": "Understood. We'll drop the old Saturday restriction and use Saturday when it supports the marathon build.",
        "durable_truths": [
          {
            "label": "before 7am",
            "signals": [
              "before 7am"
            ],
            "importance": "medium",
            "aliases": [
              "weekday workouts must finish by 7:00am for school drop-off",
              "finish by 7:00am due to school drop-off",
              "weekday workouts must finish before 7:00am due to school drop-off",
              "must finish before 7am due to school drop-off"
            ],
            "semantic_signals": []
          },
          {
            "label": "bay marathon",
            "signals": [
              "bay marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday lunch strength",
            "signals": [
              "tuesday lunch strength"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "denver hotel",
            "signals": [
              "denver hotel"
            ],
            "importance": "high",
            "aliases": [
              "denver",
              "hotel treadmill"
            ],
            "semantic_signals": []
          },
          {
            "label": "treadmill trip",
            "signals": [
              "treadmill trip"
            ],
            "importance": "high",
            "aliases": [
              "hotel treadmill",
              "travel week"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: denver",
            "signals": [
              "denver"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: treadmill",
            "signals": [
              "treadmill"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "high",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for saturdays",
            "signals": [
              "saturdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for open",
            "signals": [
              "open"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses drop",
            "signals": [
              "drop"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses old",
            "signals": [
              "old"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses restriction",
            "signals": [
              "restriction"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: use, saturday",
            "signals": [
              "use saturday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "no-go saturdays",
            "signals": [
              "no-go saturdays"
            ],
            "importance": "high",
            "aliases": [
              "saturdays unavailable for training",
              "saturdays unavailable while partner works",
              "current saturday family constraint"
            ],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "before 7am",
          "signals": [
            "before 7am"
          ],
          "importance": "high",
          "aliases": [
            "weekday workouts must finish by 7:00am for school drop-off",
            "finish by 7:00am due to school drop-off",
            "weekday workouts must finish before 7:00am due to school drop-off",
            "must finish before 7am due to school drop-off"
          ],
          "semantic_signals": []
        },
        {
          "label": "bay marathon",
          "signals": [
            "bay marathon"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday lunch strength",
          "signals": [
            "tuesday lunch strength"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "before 7am",
          "signals": [
            "before 7am"
          ],
          "importance": "medium",
          "aliases": [
            "weekday workouts must finish by 7:00am for school drop-off",
            "finish by 7:00am due to school drop-off",
            "weekday workouts must finish before 7:00am due to school drop-off",
            "must finish before 7am due to school drop-off"
          ],
          "semantic_signals": []
        },
        {
          "label": "bay marathon",
          "signals": [
            "bay marathon"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday lunch strength",
          "signals": [
            "tuesday lunch strength"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "no-go saturdays",
          "signals": [
            "no-go saturdays"
          ],
          "importance": "high",
          "aliases": [
            "saturdays unavailable for training",
            "saturdays unavailable while partner works",
            "current saturday family constraint"
          ],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-002",
    "athlete_name": "Luis Ortega",
    "sport": "triathlon",
    "profile_hint": "Age-group triathlete with a pool-heavy week and a standing masters session.",
    "messages": [
      {
        "step": 1,
        "email": "I'm training for an Olympic tri in late summer. Right now my week is pool-heavy because swimming is my limiter, and I do masters swim every Tuesday night. Bike work usually fits on Thursday and Sunday.",
        "synthetic_coach_reply": "Keep the swim emphasis, anchor Tuesday masters, and build the bike work around Thursday and Sunday.",
        "durable_truths": [
          {
            "label": "olympic tri",
            "signals": [
              "olympic tri"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "pool-heavy",
            "signals": [
              "pool-heavy"
            ],
            "importance": "high",
            "aliases": [
              "swimming is the limiting discipline",
              "swimming is my limiter",
              "swim-heavy",
              "swimming is the primary limiter"
            ],
            "semantic_signals": [
              "swim emphasis",
              "swim-first"
            ]
          },
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for swim",
            "signals": [
              "swim"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for emphasis",
            "signals": [
              "emphasis"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses tuesday",
            "signals": [
              "tuesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses masters",
            "signals": [
              "masters"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: bike, thursday, sunday",
            "signals": [
              "bike thursday sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week I got both swims done and squeezed in the Thursday bike even though work was busy. Nothing has really changed, just logging it.",
        "synthetic_coach_reply": "Nice. Stay with the same swim-first pattern and keep me posted after the weekend ride.",
        "durable_truths": [
          {
            "label": "olympic tri",
            "signals": [
              "olympic tri"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "pool-heavy",
            "signals": [
              "pool-heavy"
            ],
            "importance": "medium",
            "aliases": [
              "swimming is the limiting discipline",
              "swimming is my limiter",
              "swim-heavy",
              "swimming is the primary limiter"
            ],
            "semantic_signals": [
              "swim emphasis",
              "swim-first"
            ]
          },
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: both",
            "signals": [
              "both"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: swims",
            "signals": [
              "swims"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for both",
            "signals": [
              "both"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for swims",
            "signals": [
              "swims"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses swim-first",
            "signals": [
              "swim-first"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: weekend, ride",
            "signals": [
              "weekend ride"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary wrinkle: I'm at a conference next week and the hotel only has a tiny gym, no pool access at all. That's just for the travel week.",
        "synthetic_coach_reply": "Use the hotel gym for short maintenance work next week and return to the normal swim rhythm once you're back.",
        "durable_truths": [
          {
            "label": "olympic tri",
            "signals": [
              "olympic tri"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "pool-heavy",
            "signals": [
              "pool-heavy"
            ],
            "importance": "medium",
            "aliases": [
              "swimming is the limiting discipline",
              "swimming is my limiter",
              "swim-heavy",
              "swimming is the primary limiter"
            ],
            "semantic_signals": [
              "swim emphasis",
              "swim-first"
            ]
          },
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference hotel",
            "signals": [
              "conference hotel"
            ],
            "importance": "high",
            "aliases": [
              "conference next week",
              "hotel only has a tiny gym"
            ],
            "semantic_signals": []
          },
          {
            "label": "no pool access",
            "signals": [
              "no pool access"
            ],
            "importance": "high",
            "aliases": [
              "no pool",
              "hotel has no pool"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for conference",
            "signals": [
              "conference"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for hotel",
            "signals": [
              "hotel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses swim",
            "signals": [
              "swim"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: once, back",
            "signals": [
              "once back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Longer term, my office is opening a secure bike room, so commuting by bike twice a week is finally realistic and should stick.",
        "synthetic_coach_reply": "That's useful. We'll treat the bike commute as durable weekly volume, not just a one-off.",
        "durable_truths": [
          {
            "label": "olympic tri",
            "signals": [
              "olympic tri"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "pool-heavy",
            "signals": [
              "pool-heavy"
            ],
            "importance": "medium",
            "aliases": [
              "swimming is the limiting discipline",
              "swimming is my limiter",
              "swim-heavy",
              "swimming is the primary limiter"
            ],
            "semantic_signals": [
              "swim emphasis",
              "swim-first"
            ]
          },
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "bike commute",
            "signals": [
              "bike commute"
            ],
            "importance": "medium",
            "aliases": [
              "bike commuting twice per week",
              "regular bike commuting",
              "durable weekly volume"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference hotel",
            "signals": [
              "conference hotel"
            ],
            "importance": "high",
            "aliases": [
              "conference next week",
              "hotel only has a tiny gym"
            ],
            "semantic_signals": []
          },
          {
            "label": "no pool access",
            "signals": [
              "no pool access"
            ],
            "importance": "high",
            "aliases": [
              "no pool",
              "hotel has no pool"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for bike",
            "signals": [
              "bike"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for commute",
            "signals": [
              "commute"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses weekly",
            "signals": [
              "weekly"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses volume",
            "signals": [
              "volume"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: twice, a, week",
            "signals": [
              "twice a week"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Also, my masters group moved, so Tuesday nights are no longer the fixed swim slot. I can swim with them on Wednesdays now, so that Tuesday-only note is outdated.",
        "synthetic_coach_reply": "Got it. We'll retire the old Tuesday masters assumption and use the new midweek swim slot instead.",
        "durable_truths": [
          {
            "label": "olympic tri",
            "signals": [
              "olympic tri"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "pool-heavy",
            "signals": [
              "pool-heavy"
            ],
            "importance": "medium",
            "aliases": [
              "swimming is the limiting discipline",
              "swimming is my limiter",
              "swim-heavy",
              "swimming is the primary limiter"
            ],
            "semantic_signals": [
              "swim emphasis",
              "swim-first"
            ]
          },
          {
            "label": "bike commute",
            "signals": [
              "bike commute"
            ],
            "importance": "medium",
            "aliases": [
              "bike commuting twice per week",
              "regular bike commuting",
              "durable weekly volume"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference hotel",
            "signals": [
              "conference hotel"
            ],
            "importance": "high",
            "aliases": [
              "conference next week",
              "hotel only has a tiny gym"
            ],
            "semantic_signals": []
          },
          {
            "label": "no pool access",
            "signals": [
              "no pool access"
            ],
            "importance": "high",
            "aliases": [
              "no pool",
              "hotel has no pool"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for wednesdays",
            "signals": [
              "wednesdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for now",
            "signals": [
              "now"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses old",
            "signals": [
              "old"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses tuesday",
            "signals": [
              "tuesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: new, midweek, slot",
            "signals": [
              "new midweek slot"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "tuesday masters",
            "signals": [
              "tuesday masters"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "olympic tri",
          "signals": [
            "olympic tri"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "pool-heavy",
          "signals": [
            "pool-heavy"
          ],
          "importance": "high",
          "aliases": [
            "swimming is the limiting discipline",
            "swimming is my limiter",
            "swim-heavy",
            "swimming is the primary limiter"
          ],
          "semantic_signals": [
            "swim emphasis",
            "swim-first"
          ]
        },
        {
          "label": "bike commute",
          "signals": [
            "bike commute"
          ],
          "importance": "high",
          "aliases": [
            "bike commuting twice per week",
            "regular bike commuting",
            "durable weekly volume"
          ],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "olympic tri",
          "signals": [
            "olympic tri"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "pool-heavy",
          "signals": [
            "pool-heavy"
          ],
          "importance": "medium",
          "aliases": [
            "swimming is the limiting discipline",
            "swimming is my limiter",
            "swim-heavy",
            "swimming is the primary limiter"
          ],
          "semantic_signals": [
            "swim emphasis",
            "swim-first"
          ]
        },
        {
          "label": "bike commute",
          "signals": [
            "bike commute"
          ],
          "importance": "medium",
          "aliases": [
            "bike commuting twice per week",
            "regular bike commuting",
            "durable weekly volume"
          ],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "tuesday masters",
          "signals": [
            "tuesday masters"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-003",
    "athlete_name": "Erin Walsh",
    "sport": "gravel cycling",
    "profile_hint": "Gravel rider balancing outdoor rides with indoor trainer structure.",
    "messages": [
      {
        "step": 1,
        "email": "I'm targeting a 120-mile gravel race in September. During the week I rely on my indoor trainer before work, and outdoor gravel rides have mostly been Sunday-only because family stuff eats Saturdays.",
        "synthetic_coach_reply": "We'll protect the trainer routine on weekdays and keep Sunday as the current outdoor gravel anchor.",
        "durable_truths": [
          {
            "label": "120-mile gravel",
            "signals": [
              "120-mile gravel"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor trainer",
            "signals": [
              "indoor trainer"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "high",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for gravel",
            "signals": [
              "gravel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for anchor",
            "signals": [
              "anchor"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses trainer",
            "signals": [
              "trainer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses routine",
            "signals": [
              "routine"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: sunday, outdoor",
            "signals": [
              "sunday outdoor"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Check-in from this week: both trainer workouts happened and I felt decent on the longer one. No big life changes, just a normal update.",
        "synthetic_coach_reply": "Perfect. Keep the same trainer pattern and send me a note after the next outdoor ride.",
        "durable_truths": [
          {
            "label": "120-mile gravel",
            "signals": [
              "120-mile gravel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor trainer",
            "signals": [
              "indoor trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "medium",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: trainer",
            "signals": [
              "trainer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: workouts",
            "signals": [
              "workouts"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for trainer",
            "signals": [
              "trainer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for workouts",
            "signals": [
              "workouts"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses pattern",
            "signals": [
              "pattern"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, outdoor, ride",
            "signals": [
              "next outdoor ride"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm on a business trip next week and won't have a bike or trainer with me, just a hotel spin bike if it's free.",
        "synthetic_coach_reply": "Treat the business trip as a short maintenance week and get back to your normal bike setup when you return.",
        "durable_truths": [
          {
            "label": "120-mile gravel",
            "signals": [
              "120-mile gravel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor trainer",
            "signals": [
              "indoor trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "medium",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "business trip",
            "signals": [
              "business trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel spin bike",
            "signals": [
              "hotel spin bike"
            ],
            "importance": "high",
            "aliases": [
              "hotel spin bike if it is free",
              "spin bike if it is free"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: business",
            "signals": [
              "business"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for business",
            "signals": [
              "business"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for trip",
            "signals": [
              "trip"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses bike",
            "signals": [
              "bike"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses setup",
            "signals": [
              "setup"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, you, return",
            "signals": [
              "when you return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Long term, I finally bought a power meter for the gravel bike, so future outdoor rides will have better pacing data.",
        "synthetic_coach_reply": "Excellent. We'll treat the new power meter as durable equipment for your gravel work.",
        "durable_truths": [
          {
            "label": "120-mile gravel",
            "signals": [
              "120-mile gravel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor trainer",
            "signals": [
              "indoor trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "medium",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          },
          {
            "label": "power meter",
            "signals": [
              "power meter"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "business trip",
            "signals": [
              "business trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel spin bike",
            "signals": [
              "hotel spin bike"
            ],
            "importance": "high",
            "aliases": [
              "hotel spin bike if it is free",
              "spin bike if it is free"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: business",
            "signals": [
              "business"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for power",
            "signals": [
              "power"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for meter",
            "signals": [
              "meter"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses equipment",
            "signals": [
              "equipment"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: better, pacing, data",
            "signals": [
              "better pacing data"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "One correction: Sunday is not my only outdoor ride option anymore. My kids' schedule changed and I can ride outdoors on Saturdays too, so that old Sunday-only note isn't true now.",
        "synthetic_coach_reply": "Understood. We'll drop the Sunday-only assumption and open up Saturdays for outdoor gravel work.",
        "durable_truths": [
          {
            "label": "120-mile gravel",
            "signals": [
              "120-mile gravel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor trainer",
            "signals": [
              "indoor trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "power meter",
            "signals": [
              "power meter"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "business trip",
            "signals": [
              "business trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel spin bike",
            "signals": [
              "hotel spin bike"
            ],
            "importance": "high",
            "aliases": [
              "hotel spin bike if it is free",
              "spin bike if it is free"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: business",
            "signals": [
              "business"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "high",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for saturdays",
            "signals": [
              "saturdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for too",
            "signals": [
              "too"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses drop",
            "signals": [
              "drop"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sunday-only",
            "signals": [
              "sunday-only"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: open, up, saturdays",
            "signals": [
              "open up saturdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "sunday-only outdoor",
            "signals": [
              "sunday-only outdoor"
            ],
            "importance": "high",
            "aliases": [
              "does outdoor gravel rides mostly on sundays",
              "outdoor gravel rides mostly on sundays",
              "outdoor gravel rides are primarily on sunday",
              "primarily on sunday"
            ],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "120-mile gravel",
          "signals": [
            "120-mile gravel"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "indoor trainer",
          "signals": [
            "indoor trainer"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "power meter",
          "signals": [
            "power meter"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "120-mile gravel",
          "signals": [
            "120-mile gravel"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "indoor trainer",
          "signals": [
            "indoor trainer"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "power meter",
          "signals": [
            "power meter"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "sunday-only outdoor",
          "signals": [
            "sunday-only outdoor"
          ],
          "importance": "high",
          "aliases": [
            "does outdoor gravel rides mostly on sundays",
            "outdoor gravel rides mostly on sundays",
            "outdoor gravel rides are primarily on sunday",
            "primarily on sunday"
          ],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-004",
    "athlete_name": "Noah Brooks",
    "sport": "crossfit",
    "profile_hint": "CrossFit athlete working rotating shifts and guarding weekly training slots.",
    "messages": [
      {
        "step": 1,
        "email": "I'm prepping for a local CrossFit competition in June. My hospital shifts rotate, so I usually train after night shift blocks, and I've been avoiding Fridays because that's when I'm most cooked.",
        "synthetic_coach_reply": "We'll build around the rotating shifts and respect the current Friday avoidance while you prep for June.",
        "durable_truths": [
          {
            "label": "crossfit competition",
            "signals": [
              "crossfit competition"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "rotating shifts",
            "signals": [
              "rotating shifts"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "high",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for prep",
            "signals": [
              "prep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for june",
            "signals": [
              "june"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses respect",
            "signals": [
              "respect"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses friday",
            "signals": [
              "friday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses avoidance",
            "signals": [
              "avoidance"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: after, night, shift",
            "signals": [
              "after night shift"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week was standard: two class pieces and one strength session. Fatigue was normal and the schedule pattern is the same.",
        "synthetic_coach_reply": "Good. Keep the same rhythm and tell me if the shift fatigue starts spilling past one day.",
        "durable_truths": [
          {
            "label": "crossfit competition",
            "signals": [
              "crossfit competition"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "rotating shifts",
            "signals": [
              "rotating shifts"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "medium",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: fatigue",
            "signals": [
              "fatigue"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for fatigue",
            "signals": [
              "fatigue"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses rhythm",
            "signals": [
              "rhythm"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: shift, fatigue",
            "signals": [
              "shift fatigue"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary thing: the box is redoing the rig next week, so I won't have barbell access for a few days and will mostly be on dumbbells and cardio.",
        "synthetic_coach_reply": "Use next week as a temporary dumbbell-focused block and go back to normal barbell work once the gym is reset.",
        "durable_truths": [
          {
            "label": "crossfit competition",
            "signals": [
              "crossfit competition"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "rotating shifts",
            "signals": [
              "rotating shifts"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "medium",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "redoing rig",
            "signals": [
              "redoing rig"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "barbell access",
            "signals": [
              "barbell access"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: dumbbell-focused",
            "signals": [
              "dumbbell-focused"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for dumbbell-focused",
            "signals": [
              "dumbbell-focused"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses back",
            "signals": [
              "back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses to",
            "signals": [
              "to"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses barbell",
            "signals": [
              "barbell"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: gym, is, reset",
            "signals": [
              "gym is reset"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "This should stick: I started meeting a coworker for Monday mobility right after shift handoff, so that recovery slot is becoming part of the routine.",
        "synthetic_coach_reply": "Great. We'll treat Monday mobility after handoff as a durable recovery habit.",
        "durable_truths": [
          {
            "label": "crossfit competition",
            "signals": [
              "crossfit competition"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "rotating shifts",
            "signals": [
              "rotating shifts"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "medium",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          },
          {
            "label": "monday mobility",
            "signals": [
              "monday mobility"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "redoing rig",
            "signals": [
              "redoing rig"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "barbell access",
            "signals": [
              "barbell access"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: dumbbell-focused",
            "signals": [
              "dumbbell-focused"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for monday",
            "signals": [
              "monday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for mobility",
            "signals": [
              "mobility"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses recovery",
            "signals": [
              "recovery"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses habit",
            "signals": [
              "habit"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: part, of, routine",
            "signals": [
              "part of routine"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update on Fridays: my rotation changed and I actually can train then now, so the old 'avoid Fridays' rule doesn't apply anymore.",
        "synthetic_coach_reply": "Understood. We'll retire the Friday-avoidance note and use Friday when the new rotation supports it.",
        "durable_truths": [
          {
            "label": "crossfit competition",
            "signals": [
              "crossfit competition"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "rotating shifts",
            "signals": [
              "rotating shifts"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "monday mobility",
            "signals": [
              "monday mobility"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "redoing rig",
            "signals": [
              "redoing rig"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "barbell access",
            "signals": [
              "barbell access"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: dumbbell-focused",
            "signals": [
              "dumbbell-focused"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "high",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for can",
            "signals": [
              "can"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for train",
            "signals": [
              "train"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for friday",
            "signals": [
              "friday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses friday-avoidance",
            "signals": [
              "friday-avoidance"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: new, rotation",
            "signals": [
              "new rotation"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "avoiding fridays",
            "signals": [
              "avoiding fridays"
            ],
            "importance": "high",
            "aliases": [
              "avoids training on fridays due to fatigue"
            ],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "crossfit competition",
          "signals": [
            "crossfit competition"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "rotating shifts",
          "signals": [
            "rotating shifts"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "monday mobility",
          "signals": [
            "monday mobility"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "crossfit competition",
          "signals": [
            "crossfit competition"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "rotating shifts",
          "signals": [
            "rotating shifts"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "monday mobility",
          "signals": [
            "monday mobility"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "avoiding fridays",
          "signals": [
            "avoiding fridays"
          ],
          "importance": "high",
          "aliases": [
            "avoids training on fridays due to fatigue"
          ],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-005",
    "athlete_name": "Priya Raman",
    "sport": "masters swimming",
    "profile_hint": "Masters swimmer training before work with limited weekday lanes.",
    "messages": [
      {
        "step": 1,
        "email": "I'm a masters swimmer aiming for a summer 1500 free. I train before work, and right now I can only swim three weekday mornings because lane space is tight at my pool.",
        "synthetic_coach_reply": "We'll anchor the 1500 build around the three available mornings and keep the sessions before work.",
        "durable_truths": [
          {
            "label": "1500 free",
            "signals": [
              "1500 free"
            ],
            "importance": "high",
            "aliases": [
              "masters swimmer",
              "1500-meter freestyle"
            ],
            "semantic_signals": [
              "distance freestyle goal"
            ]
          },
          {
            "label": "before work",
            "signals": [
              "before work"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for 1500",
            "signals": [
              "1500"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for build",
            "signals": [
              "build"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses three",
            "signals": [
              "three"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses available",
            "signals": [
              "available"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses mornings",
            "signals": [
              "mornings"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: lane, space",
            "signals": [
              "lane space"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Normal update: all three swims happened and the pull set felt better than last week. No durable changes, just progress.",
        "synthetic_coach_reply": "Nice. Stay with the same morning pattern and let me know how the next threshold set feels.",
        "durable_truths": [
          {
            "label": "1500 free",
            "signals": [
              "1500 free"
            ],
            "importance": "medium",
            "aliases": [
              "masters swimmer",
              "1500-meter freestyle"
            ],
            "semantic_signals": [
              "distance freestyle goal"
            ]
          },
          {
            "label": "before work",
            "signals": [
              "before work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: pull",
            "signals": [
              "pull"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: set",
            "signals": [
              "set"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for pull",
            "signals": [
              "pull"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for set",
            "signals": [
              "set"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses morning",
            "signals": [
              "morning"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses pattern",
            "signals": [
              "pattern"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: threshold, set",
            "signals": [
              "threshold set"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary snag: I'm traveling for a wedding and the hotel pool is tiny, plus my shoulder is a little cranky, so next week will just be short easy swims if anything.",
        "synthetic_coach_reply": "Keep the travel week light, use only short easy swims if the shoulder stays calm, and resume your normal pool once you're back.",
        "durable_truths": [
          {
            "label": "1500 free",
            "signals": [
              "1500 free"
            ],
            "importance": "medium",
            "aliases": [
              "masters swimmer",
              "1500-meter freestyle"
            ],
            "semantic_signals": [
              "distance freestyle goal"
            ]
          },
          {
            "label": "before work",
            "signals": [
              "before work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel pool",
            "signals": [
              "hotel pool"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for travel",
            "signals": [
              "travel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for week",
            "signals": [
              "week"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses keep",
            "signals": [
              "keep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses light",
            "signals": [
              "light"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: once, youre, back",
            "signals": [
              "once youre back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Long term, I finally joined the Saturday coached stroke clinic, so I now have a reliable technical session every weekend.",
        "synthetic_coach_reply": "Great. We'll treat the Saturday stroke clinic as a durable part of your swim week.",
        "durable_truths": [
          {
            "label": "1500 free",
            "signals": [
              "1500 free"
            ],
            "importance": "medium",
            "aliases": [
              "masters swimmer",
              "1500-meter freestyle"
            ],
            "semantic_signals": [
              "distance freestyle goal"
            ]
          },
          {
            "label": "before work",
            "signals": [
              "before work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "saturday stroke clinic",
            "signals": [
              "saturday stroke clinic"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel pool",
            "signals": [
              "hotel pool"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for saturday",
            "signals": [
              "saturday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for stroke",
            "signals": [
              "stroke"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for clinic",
            "signals": [
              "clinic"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses swim",
            "signals": [
              "swim"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses week",
            "signals": [
              "week"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: technical, session",
            "signals": [
              "technical session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "And a correction: I can swim four weekday mornings now because another lane opened up, so the old three-mornings cap is outdated.",
        "synthetic_coach_reply": "Understood. We'll retire the three-morning limit and use the expanded weekday pool access.",
        "durable_truths": [
          {
            "label": "1500 free",
            "signals": [
              "1500 free"
            ],
            "importance": "medium",
            "aliases": [
              "masters swimmer",
              "1500-meter freestyle"
            ],
            "semantic_signals": [
              "distance freestyle goal"
            ]
          },
          {
            "label": "before work",
            "signals": [
              "before work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "saturday stroke clinic",
            "signals": [
              "saturday stroke clinic"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel pool",
            "signals": [
              "hotel pool"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for four",
            "signals": [
              "four"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for weekday",
            "signals": [
              "weekday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for mornings",
            "signals": [
              "mornings"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses three-morning",
            "signals": [
              "three-morning"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses limit",
            "signals": [
              "limit"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: expanded, pool, access",
            "signals": [
              "expanded pool access"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "three weekday mornings",
            "signals": [
              "three weekday mornings"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "1500 free",
          "signals": [
            "1500 free"
          ],
          "importance": "high",
          "aliases": [
            "masters swimmer",
            "1500-meter freestyle"
          ],
          "semantic_signals": [
            "distance freestyle goal"
          ]
        },
        {
          "label": "before work",
          "signals": [
            "before work"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "saturday stroke clinic",
          "signals": [
            "saturday stroke clinic"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "1500 free",
          "signals": [
            "1500 free"
          ],
          "importance": "medium",
          "aliases": [
            "masters swimmer",
            "1500-meter freestyle"
          ],
          "semantic_signals": [
            "distance freestyle goal"
          ]
        },
        {
          "label": "before work",
          "signals": [
            "before work"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "saturday stroke clinic",
          "signals": [
            "saturday stroke clinic"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "three weekday mornings",
          "signals": [
            "three weekday mornings"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-006",
    "athlete_name": "Derek Sloan",
    "sport": "powerlifting",
    "profile_hint": "Powerlifter using a garage gym and structured lift split.",
    "messages": [
      {
        "step": 1,
        "email": "I'm getting ready for a fall powerlifting meet. I train in my garage gym, and I avoid heavy deadlifts on Wednesdays because that lands in the middle of my longest workday.",
        "synthetic_coach_reply": "We'll keep the meet prep anchored in the garage gym and respect the no-heavy-deadlifts-on-Wednesday constraint.",
        "durable_truths": [
          {
            "label": "powerlifting meet",
            "signals": [
              "powerlifting meet"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "garage gym",
            "signals": [
              "garage gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for meet",
            "signals": [
              "meet"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for prep",
            "signals": [
              "prep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses respect",
            "signals": [
              "respect"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses wednesday",
            "signals": [
              "wednesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: longest, workday",
            "signals": [
              "longest workday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week was on script: squat, bench, then accessories. Nothing about the setup has changed.",
        "synthetic_coach_reply": "Good. Stay with the same split and report back after the next heavy lower session.",
        "durable_truths": [
          {
            "label": "powerlifting meet",
            "signals": [
              "powerlifting meet"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "garage gym",
            "signals": [
              "garage gym"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: split",
            "signals": [
              "split"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for split",
            "signals": [
              "split"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses report",
            "signals": [
              "report"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses back",
            "signals": [
              "back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: heavy, lower, session",
            "signals": [
              "heavy lower session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary restriction: I'm at a conference next week and the hotel gym only has dumbbells up to 50, so barbell work is off for that trip.",
        "synthetic_coach_reply": "Use the conference week for lighter hotel-gym work and return to the full barbell setup once you're home.",
        "durable_truths": [
          {
            "label": "powerlifting meet",
            "signals": [
              "powerlifting meet"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "garage gym",
            "signals": [
              "garage gym"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference week",
            "signals": [
              "conference week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel gym",
            "signals": [
              "hotel gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for conference",
            "signals": [
              "conference"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for week",
            "signals": [
              "week"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses full",
            "signals": [
              "full"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses barbell",
            "signals": [
              "barbell"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: once, youre, home",
            "signals": [
              "once youre home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "This one's permanent: I bought a combo rack for the garage, so setup is faster and I can bench safely without waiting for a spotter.",
        "synthetic_coach_reply": "Great. We'll keep the new combo rack in mind as durable equipment for your training setup.",
        "durable_truths": [
          {
            "label": "powerlifting meet",
            "signals": [
              "powerlifting meet"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "garage gym",
            "signals": [
              "garage gym"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "combo rack",
            "signals": [
              "combo rack"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference week",
            "signals": [
              "conference week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel gym",
            "signals": [
              "hotel gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for combo",
            "signals": [
              "combo"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for rack",
            "signals": [
              "rack"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses equipment",
            "signals": [
              "equipment"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: bench, safely",
            "signals": [
              "bench safely"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update on scheduling: Wednesdays opened up and I can deadlift then now, so that old rule about no Wednesday deadlifts is no longer true.",
        "synthetic_coach_reply": "Understood. We'll retire the Wednesday deadlift restriction and treat midweek pulling as available.",
        "durable_truths": [
          {
            "label": "powerlifting meet",
            "signals": [
              "powerlifting meet"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "garage gym",
            "signals": [
              "garage gym"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "combo rack",
            "signals": [
              "combo rack"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "conference week",
            "signals": [
              "conference week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel gym",
            "signals": [
              "hotel gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conference",
            "signals": [
              "conference"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: week",
            "signals": [
              "week"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for wednesdays",
            "signals": [
              "wednesdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for opened",
            "signals": [
              "opened"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for up",
            "signals": [
              "up"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses restriction",
            "signals": [
              "restriction"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: midweek, pulling",
            "signals": [
              "midweek pulling"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "deadlifts wednesdays",
            "signals": [
              "deadlifts wednesdays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "powerlifting meet",
          "signals": [
            "powerlifting meet"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "garage gym",
          "signals": [
            "garage gym"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "combo rack",
          "signals": [
            "combo rack"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "powerlifting meet",
          "signals": [
            "powerlifting meet"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "garage gym",
          "signals": [
            "garage gym"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "combo rack",
          "signals": [
            "combo rack"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "deadlifts wednesdays",
          "signals": [
            "deadlifts wednesdays"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-007",
    "athlete_name": "Sofia Alvarez",
    "sport": "soccer",
    "profile_hint": "Club soccer athlete balancing team sessions with strength work.",
    "messages": [
      {
        "step": 1,
        "email": "I'm in-season with my soccer club and also trying to keep two lift sessions each week. Team training is Tuesday and Thursday, and Sunday has usually been recovery-only because matches leave me trashed.",
        "synthetic_coach_reply": "We'll build around the club schedule and keep Sunday as recovery-only for now.",
        "durable_truths": [
          {
            "label": "soccer club",
            "signals": [
              "soccer club"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday thursday",
            "signals": [
              "tuesday thursday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for club",
            "signals": [
              "club"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for schedule",
            "signals": [
              "schedule"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sunday",
            "signals": [
              "sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses recovery-only",
            "signals": [
              "recovery-only"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: two, lift, sessions",
            "signals": [
              "two lift sessions"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Quick check-in: both team sessions happened and I squeezed in one lift. Felt pretty normal overall, no new constraints.",
        "synthetic_coach_reply": "Good. Keep the same in-season structure and update me after your next match.",
        "durable_truths": [
          {
            "label": "soccer club",
            "signals": [
              "soccer club"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday thursday",
            "signals": [
              "tuesday thursday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: in-season",
            "signals": [
              "in-season"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for in-season",
            "signals": [
              "in-season"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, match",
            "signals": [
              "next match"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: we're away for a tournament next week and there won't be any gym access at the hotel. That's just for the travel block.",
        "synthetic_coach_reply": "Treat the tournament trip as a no-gym week and return to the normal lift rhythm once the team is back.",
        "durable_truths": [
          {
            "label": "soccer club",
            "signals": [
              "soccer club"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday thursday",
            "signals": [
              "tuesday thursday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "tournament trip",
            "signals": [
              "tournament trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "no-gym week",
            "signals": [
              "no-gym week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: tournament",
            "signals": [
              "tournament"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for tournament",
            "signals": [
              "tournament"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for trip",
            "signals": [
              "trip"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses lift",
            "signals": [
              "lift"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: team, is, back",
            "signals": [
              "team is back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Long term, our trainer added a standing Monday lift for defenders, so I now have a reliable team strength slot every week.",
        "synthetic_coach_reply": "Perfect. We'll treat the Monday team lift as a durable part of your in-season setup.",
        "durable_truths": [
          {
            "label": "soccer club",
            "signals": [
              "soccer club"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday thursday",
            "signals": [
              "tuesday thursday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "monday team lift",
            "signals": [
              "monday team lift"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "tournament trip",
            "signals": [
              "tournament trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "no-gym week",
            "signals": [
              "no-gym week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: tournament",
            "signals": [
              "tournament"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for monday",
            "signals": [
              "monday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for team",
            "signals": [
              "team"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for lift",
            "signals": [
              "lift"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: every, week",
            "signals": [
              "every week"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Also, Sunday is not always recovery-only anymore. We moved matches to Saturdays for a while, so I can train some Sundays now.",
        "synthetic_coach_reply": "Understood. We'll retire the old Sunday recovery-only note and use Sunday when the match calendar allows it.",
        "durable_truths": [
          {
            "label": "soccer club",
            "signals": [
              "soccer club"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday thursday",
            "signals": [
              "tuesday thursday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "monday team lift",
            "signals": [
              "monday team lift"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "tournament trip",
            "signals": [
              "tournament trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "no-gym week",
            "signals": [
              "no-gym week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: tournament",
            "signals": [
              "tournament"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for train",
            "signals": [
              "train"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for some",
            "signals": [
              "some"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for sundays",
            "signals": [
              "sundays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses old",
            "signals": [
              "old"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sunday",
            "signals": [
              "sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: match, calendar",
            "signals": [
              "match calendar"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "recovery-only sunday",
            "signals": [
              "recovery-only sunday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "soccer club",
          "signals": [
            "soccer club"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday thursday",
          "signals": [
            "tuesday thursday"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "monday team lift",
          "signals": [
            "monday team lift"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "soccer club",
          "signals": [
            "soccer club"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday thursday",
          "signals": [
            "tuesday thursday"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "monday team lift",
          "signals": [
            "monday team lift"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "recovery-only sunday",
          "signals": [
            "recovery-only sunday"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-008",
    "athlete_name": "Jules Hart",
    "sport": "rock climbing",
    "profile_hint": "Climber splitting time between indoor bouldering and fingerboard work.",
    "messages": [
      {
        "step": 1,
        "email": "I'm focused on bouldering this season. Most of my training is indoors after work, and I also do a short fingerboard session on Wednesday mornings before meetings.",
        "synthetic_coach_reply": "We'll keep the indoor bouldering focus and leave room for the Wednesday fingerboard habit.",
        "durable_truths": [
          {
            "label": "bouldering",
            "signals": [
              "bouldering"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoors after work",
            "signals": [
              "indoors after work"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "fingerboard wednesday",
            "signals": [
              "fingerboard wednesday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for indoor",
            "signals": [
              "indoor"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for focus",
            "signals": [
              "focus"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses fingerboard",
            "signals": [
              "fingerboard"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses habit",
            "signals": [
              "habit"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: after, work",
            "signals": [
              "after work"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week was standard: two gym sessions and one fingerboard set. No long-term changes, just the usual check-in.",
        "synthetic_coach_reply": "Nice. Keep the same climbing rhythm and let me know when the current project moves.",
        "durable_truths": [
          {
            "label": "bouldering",
            "signals": [
              "bouldering"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoors after work",
            "signals": [
              "indoors after work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "fingerboard wednesday",
            "signals": [
              "fingerboard wednesday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: climbing",
            "signals": [
              "climbing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: rhythm",
            "signals": [
              "rhythm"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for climbing",
            "signals": [
              "climbing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for rhythm",
            "signals": [
              "rhythm"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses keep",
            "signals": [
              "keep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: current, project",
            "signals": [
              "current project"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm traveling to visit family and there won't be a climbing gym nearby, so next week is basically hangs and general strength only.",
        "synthetic_coach_reply": "Use the travel week for hangs and general strength, then return to normal climbing access when you're home.",
        "durable_truths": [
          {
            "label": "bouldering",
            "signals": [
              "bouldering"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoors after work",
            "signals": [
              "indoors after work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "fingerboard wednesday",
            "signals": [
              "fingerboard wednesday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "climbing gym",
            "signals": [
              "climbing gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for family",
            "signals": [
              "family"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for travel",
            "signals": [
              "travel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses climbing",
            "signals": [
              "climbing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, youre, home",
            "signals": [
              "when youre home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Permanent update: I built a small home wall in the garage, so I now have a reliable place for short technique sessions.",
        "synthetic_coach_reply": "That's durable. We'll treat the home wall as part of your climbing setup going forward.",
        "durable_truths": [
          {
            "label": "bouldering",
            "signals": [
              "bouldering"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoors after work",
            "signals": [
              "indoors after work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "fingerboard wednesday",
            "signals": [
              "fingerboard wednesday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "home wall",
            "signals": [
              "home wall"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "climbing gym",
            "signals": [
              "climbing gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for home",
            "signals": [
              "home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for wall",
            "signals": [
              "wall"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses of",
            "signals": [
              "of"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses setup",
            "signals": [
              "setup"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: technique, sessions",
            "signals": [
              "technique sessions"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "One note to remove: I don't only climb indoors anymore now that spring is here. Outdoor sessions are back in the mix, so that indoor-only idea is outdated.",
        "synthetic_coach_reply": "Got it — we'll plan for both indoor and outdoor sessions going forward.",
        "durable_truths": [
          {
            "label": "bouldering",
            "signals": [
              "bouldering"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "indoor and outdoor after work",
            "signals": [
              "after work",
              "outdoor"
            ],
            "importance": "medium",
            "aliases": [
              "indoor outdoor"
            ],
            "semantic_signals": [
              "trains both indoors and outdoors"
            ]
          },
          {
            "label": "fingerboard wednesday",
            "signals": [
              "fingerboard wednesday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "home wall",
            "signals": [
              "home wall"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "climbing gym",
            "signals": [
              "climbing gym"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for outdoor",
            "signals": [
              "outdoor"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for sessions",
            "signals": [
              "sessions"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for indoor and outdoor",
            "signals": [
              "indoor",
              "outdoor"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: available, again",
            "signals": [
              "available again"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "indoor-only assumption",
            "signals": [
              "indoor-only",
              "only indoors"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "durable_change",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "bouldering",
          "signals": [
            "bouldering"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "indoor and outdoor after work",
          "signals": [
            "after work",
            "outdoor"
          ],
          "importance": "high",
          "aliases": [
            "indoor outdoor"
          ],
          "semantic_signals": [
            "trains both indoors and outdoors"
          ]
        },
        {
          "label": "fingerboard wednesday",
          "signals": [
            "fingerboard wednesday"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "home wall",
          "signals": [
            "home wall"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "bouldering",
          "signals": [
            "bouldering"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "indoor and outdoor after work",
          "signals": [
            "after work",
            "outdoor"
          ],
          "importance": "medium",
          "aliases": [
            "indoor outdoor"
          ],
          "semantic_signals": [
            "trains both indoors and outdoors"
          ]
        },
        {
          "label": "fingerboard wednesday",
          "signals": [
            "fingerboard wednesday"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "home wall",
          "signals": [
            "home wall"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": []
    }
  },
  {
    "id": "AM-009",
    "athlete_name": "Hannah Pierce",
    "sport": "rowing",
    "profile_hint": "Rowing athlete mixing erg work with on-water sessions.",
    "messages": [
      {
        "step": 1,
        "email": "I'm rowing toward masters regionals. During the week I use the erg before sunrise, and Saturday has usually been my long erg session if weather keeps us off the water.",
        "synthetic_coach_reply": "We'll keep the before-sunrise erg work and protect Saturday as the long erg slot for now.",
        "durable_truths": [
          {
            "label": "masters regionals",
            "signals": [
              "masters regionals"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "erg before sunrise",
            "signals": [
              "erg before sunrise"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for rowing",
            "signals": [
              "rowing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for toward",
            "signals": [
              "toward"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for regionals",
            "signals": [
              "regionals"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses protect",
            "signals": [
              "protect"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses saturday",
            "signals": [
              "saturday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: off, the, water",
            "signals": [
              "off the water"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Standard update: two erg sessions and one water row this week. No real changes, just logging it.",
        "synthetic_coach_reply": "Good. Stay with the same rowing structure and tell me how the next water row feels.",
        "durable_truths": [
          {
            "label": "masters regionals",
            "signals": [
              "masters regionals"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "erg before sunrise",
            "signals": [
              "erg before sunrise"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: rowing",
            "signals": [
              "rowing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for rowing",
            "signals": [
              "rowing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses stay",
            "signals": [
              "stay"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, water, row",
            "signals": [
              "next water row"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary problem: I'm traveling for work and won't have erg access for several days, just a hotel bike. That's only for this trip.",
        "synthetic_coach_reply": "Treat the trip as a short no-erg block and return to the normal rowing setup once you're back.",
        "durable_truths": [
          {
            "label": "masters regionals",
            "signals": [
              "masters regionals"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "erg before sunrise",
            "signals": [
              "erg before sunrise"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-erg block",
            "signals": [
              "no-erg block"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel bike",
            "signals": [
              "hotel bike"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: for",
            "signals": [
              "for"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: work",
            "signals": [
              "work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for travel",
            "signals": [
              "travel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for for",
            "signals": [
              "for"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for work",
            "signals": [
              "work"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses rowing",
            "signals": [
              "rowing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: once, youre, back",
            "signals": [
              "once youre back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Longer term, I joined a Sunday doubles scull, so I now have a recurring technical water session every week.",
        "synthetic_coach_reply": "Excellent. We'll treat the Sunday doubles scull as a durable weekly rowing note.",
        "durable_truths": [
          {
            "label": "masters regionals",
            "signals": [
              "masters regionals"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "erg before sunrise",
            "signals": [
              "erg before sunrise"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday doubles scull",
            "signals": [
              "sunday doubles scull"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-erg block",
            "signals": [
              "no-erg block"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel bike",
            "signals": [
              "hotel bike"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: for",
            "signals": [
              "for"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: work",
            "signals": [
              "work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for sunday",
            "signals": [
              "sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for doubles",
            "signals": [
              "doubles"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for scull",
            "signals": [
              "scull"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses weekly",
            "signals": [
              "weekly"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses rowing",
            "signals": [
              "rowing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: technical, water, session",
            "signals": [
              "technical water session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update: Saturday isn't always my long erg day anymore because our club moved the long piece to Sunday water. That old Saturday-long-erg note should be retired.",
        "synthetic_coach_reply": "Understood. We'll retire the Saturday long-erg assumption and use the new Sunday long session instead.",
        "durable_truths": [
          {
            "label": "masters regionals",
            "signals": [
              "masters regionals"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "erg before sunrise",
            "signals": [
              "erg before sunrise"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday doubles scull",
            "signals": [
              "sunday doubles scull"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-erg block",
            "signals": [
              "no-erg block"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel bike",
            "signals": [
              "hotel bike"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: for",
            "signals": [
              "for"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: work",
            "signals": [
              "work"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for moved",
            "signals": [
              "moved"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for to",
            "signals": [
              "to"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for sunday",
            "signals": [
              "sunday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses saturday",
            "signals": [
              "saturday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses long-erg",
            "signals": [
              "long-erg"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: new, sunday, session",
            "signals": [
              "new sunday session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "long erg saturday",
            "signals": [
              "long erg saturday"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "masters regionals",
          "signals": [
            "masters regionals"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "erg before sunrise",
          "signals": [
            "erg before sunrise"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday doubles scull",
          "signals": [
            "sunday doubles scull"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "masters regionals",
          "signals": [
            "masters regionals"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "erg before sunrise",
          "signals": [
            "erg before sunrise"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday doubles scull",
          "signals": [
            "sunday doubles scull"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "long erg saturday",
          "signals": [
            "long erg saturday"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-010",
    "athlete_name": "Cole Mercer",
    "sport": "mountain biking",
    "profile_hint": "Trail rider with limited weekday ride windows and big weekend volume.",
    "messages": [
      {
        "step": 1,
        "email": "I'm training for a late-summer mountain bike stage race. My weekday rides usually have to stay under 60 minutes because of work, and most trail volume lands on the weekend.",
        "synthetic_coach_reply": "We'll protect the short weekday ride window and use the weekends for the bigger trail work.",
        "durable_truths": [
          {
            "label": "mountain bike stage",
            "signals": [
              "mountain bike stage"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "weekend trail volume",
            "signals": [
              "weekend trail volume"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for stage",
            "signals": [
              "stage"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for race",
            "signals": [
              "race"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses weekends",
            "signals": [
              "weekends"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses bigger",
            "signals": [
              "bigger"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses trail",
            "signals": [
              "trail"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: weekday, ride, window",
            "signals": [
              "weekday ride window"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Normal update: one short trainer ride, one short trail ride, and a solid weekend session. Nothing durable changed.",
        "synthetic_coach_reply": "Good. Stay with the same weekday cap and send me a note after the next long trail day.",
        "durable_truths": [
          {
            "label": "mountain bike stage",
            "signals": [
              "mountain bike stage"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "weekend trail volume",
            "signals": [
              "weekend trail volume"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: weekday",
            "signals": [
              "weekday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: cap",
            "signals": [
              "cap"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for weekday",
            "signals": [
              "weekday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for cap",
            "signals": [
              "cap"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses stay",
            "signals": [
              "stay"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, long, trail",
            "signals": [
              "next long trail"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I have a work trip next week and won't have my bike with me, so it'll just be hotel cardio for a few days.",
        "synthetic_coach_reply": "Use the travel block for hotel cardio only and resume bike-specific work when you get home.",
        "durable_truths": [
          {
            "label": "mountain bike stage",
            "signals": [
              "mountain bike stage"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "weekend trail volume",
            "signals": [
              "weekend trail volume"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "work trip",
            "signals": [
              "work trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: block",
            "signals": [
              "block"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for travel",
            "signals": [
              "travel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for block",
            "signals": [
              "block"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses resume",
            "signals": [
              "resume"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses bike-specific",
            "signals": [
              "bike-specific"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: get, home",
            "signals": [
              "get home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Permanent upgrade: I put in a smart trainer at home, so I now have a reliable weekday backup when trails are washed out.",
        "synthetic_coach_reply": "Great. We'll treat the smart trainer as durable equipment for your weekday riding.",
        "durable_truths": [
          {
            "label": "mountain bike stage",
            "signals": [
              "mountain bike stage"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "weekend trail volume",
            "signals": [
              "weekend trail volume"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "smart trainer",
            "signals": [
              "smart trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "work trip",
            "signals": [
              "work trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: block",
            "signals": [
              "block"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for smart",
            "signals": [
              "smart"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for trainer",
            "signals": [
              "trainer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses equipment",
            "signals": [
              "equipment"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: weekday, backup",
            "signals": [
              "weekday backup"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "One change: weekday rides do not always need to stay under 60 minutes anymore because my work hours shifted. That old cap is outdated.",
        "synthetic_coach_reply": "Understood. We'll retire the sub-60-minute weekday limit and use the extra room when needed.",
        "durable_truths": [
          {
            "label": "mountain bike stage",
            "signals": [
              "mountain bike stage"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "weekend trail volume",
            "signals": [
              "weekend trail volume"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "smart trainer",
            "signals": [
              "smart trainer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "work trip",
            "signals": [
              "work trip"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: travel",
            "signals": [
              "travel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: block",
            "signals": [
              "block"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for work",
            "signals": [
              "work"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for hours",
            "signals": [
              "hours"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for shifted",
            "signals": [
              "shifted"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses limit",
            "signals": [
              "limit"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: extra, room",
            "signals": [
              "extra room"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "under 60 minutes",
            "signals": [
              "under 60 minutes"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "mountain bike stage",
          "signals": [
            "mountain bike stage"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "weekend trail volume",
          "signals": [
            "weekend trail volume"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "smart trainer",
          "signals": [
            "smart trainer"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "mountain bike stage",
          "signals": [
            "mountain bike stage"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "weekend trail volume",
          "signals": [
            "weekend trail volume"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "smart trainer",
          "signals": [
            "smart trainer"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "under 60 minutes",
          "signals": [
            "under 60 minutes"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-011",
    "athlete_name": "Ava Sinclair",
    "sport": "tennis",
    "profile_hint": "League tennis player working around court bookings and doubles commitments.",
    "messages": [
      {
        "step": 1,
        "email": "I'm trying to sharpen up for summer tennis league play. Court access is easiest early mornings, and Thursday has been a fixed doubles night every week.",
        "synthetic_coach_reply": "We'll keep the early-morning court pattern and plan around Thursday doubles as the fixed evening commitment.",
        "durable_truths": [
          {
            "label": "tennis league",
            "signals": [
              "tennis league"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "early mornings",
            "signals": [
              "early mornings"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for summer",
            "signals": [
              "summer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for tennis",
            "signals": [
              "tennis"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for league",
            "signals": [
              "league"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses plan",
            "signals": [
              "plan"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses around",
            "signals": [
              "around"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses thursday",
            "signals": [
              "thursday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: court, pattern",
            "signals": [
              "court pattern"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week was normal: one serve session, one fitness block, and Thursday doubles. No lasting changes.",
        "synthetic_coach_reply": "Good. Keep the same setup and tell me if the shoulder load changes after doubles.",
        "durable_truths": [
          {
            "label": "tennis league",
            "signals": [
              "tennis league"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "early mornings",
            "signals": [
              "early mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: setup",
            "signals": [
              "setup"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for setup",
            "signals": [
              "setup"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses keep",
            "signals": [
              "keep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: shoulder, load",
            "signals": [
              "shoulder load"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm visiting family next week and won't have my racquet or court time, so it will just be some hotel mobility and band work.",
        "synthetic_coach_reply": "Treat the family trip as a no-court week and return to your usual tennis pattern when you're back.",
        "durable_truths": [
          {
            "label": "tennis league",
            "signals": [
              "tennis league"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "early mornings",
            "signals": [
              "early mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel mobility",
            "signals": [
              "hotel mobility"
            ],
            "importance": "high",
            "aliases": [
              "hotel mobility and band work",
              "band work"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for family",
            "signals": [
              "family"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for trip",
            "signals": [
              "trip"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses usual",
            "signals": [
              "usual"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses tennis",
            "signals": [
              "tennis"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, youre, back",
            "signals": [
              "when youre back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "This should stick: I booked a standing Sunday ball-machine hour, so I now have a reliable solo hitting slot every weekend.",
        "synthetic_coach_reply": "Excellent. We'll treat the Sunday ball-machine hour as a durable part of your tennis routine.",
        "durable_truths": [
          {
            "label": "tennis league",
            "signals": [
              "tennis league"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "early mornings",
            "signals": [
              "early mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday ball-machine",
            "signals": [
              "sunday ball-machine"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel mobility",
            "signals": [
              "hotel mobility"
            ],
            "importance": "high",
            "aliases": [
              "hotel mobility and band work",
              "band work"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for ball-machine",
            "signals": [
              "ball-machine"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for hour",
            "signals": [
              "hour"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: solo, hitting, slot",
            "signals": [
              "solo hitting slot"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update: Thursday is no longer the fixed doubles night because the league moved us to Tuesday. That Thursday note should be retired.",
        "synthetic_coach_reply": "Understood. We'll retire the Thursday doubles assumption and use the new Tuesday league slot.",
        "durable_truths": [
          {
            "label": "tennis league",
            "signals": [
              "tennis league"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "early mornings",
            "signals": [
              "early mornings"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday ball-machine",
            "signals": [
              "sunday ball-machine"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel mobility",
            "signals": [
              "hotel mobility"
            ],
            "importance": "high",
            "aliases": [
              "hotel mobility and band work",
              "band work"
            ],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for moved",
            "signals": [
              "moved"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for to",
            "signals": [
              "to"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for tuesday",
            "signals": [
              "tuesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses thursday",
            "signals": [
              "thursday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: new, tuesday, slot",
            "signals": [
              "new tuesday slot"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "thursday doubles",
            "signals": [
              "thursday doubles"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "tennis league",
          "signals": [
            "tennis league"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "early mornings",
          "signals": [
            "early mornings"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday ball-machine",
          "signals": [
            "sunday ball-machine"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "tennis league",
          "signals": [
            "tennis league"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "early mornings",
          "signals": [
            "early mornings"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday ball-machine",
          "signals": [
            "sunday ball-machine"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "thursday doubles",
          "signals": [
            "thursday doubles"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-012",
    "athlete_name": "Malik Johnson",
    "sport": "basketball",
    "profile_hint": "Basketball athlete combining skill sessions with conditioning and late-evening availability.",
    "messages": [
      {
        "step": 1,
        "email": "I'm training for summer rec league and trying to keep my first step sharp. I usually train after 8pm because of work, and most sessions are court skill work plus one conditioning day.",
        "synthetic_coach_reply": "We'll keep the late-evening schedule and balance the court work with one conditioning day.",
        "durable_truths": [
          {
            "label": "summer rec league",
            "signals": [
              "summer rec league"
            ],
            "importance": "high",
            "aliases": [
              "primary training goal: keep first-step quickness sharp",
              "first-step quickness sharp"
            ],
            "semantic_signals": []
          },
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm"
            ],
            "importance": "high",
            "aliases": [
              "after 8pm due to work",
              "training sessions after 8pm"
            ],
            "semantic_signals": []
          },
          {
            "label": "conditioning day",
            "signals": [
              "conditioning day"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for late-evening",
            "signals": [
              "late-evening"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for schedule",
            "signals": [
              "schedule"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses balance",
            "signals": [
              "balance"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses court",
            "signals": [
              "court"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses work",
            "signals": [
              "work"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: first, step",
            "signals": [
              "first step"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Normal week: two court sessions and one conditioning day. Nothing has changed beyond that.",
        "synthetic_coach_reply": "Good. Stay with the same late schedule and tell me how the legs feel after the next hard court session.",
        "durable_truths": [
          {
            "label": "summer rec league",
            "signals": [
              "summer rec league"
            ],
            "importance": "medium",
            "aliases": [
              "primary training goal: keep first-step quickness sharp",
              "first-step quickness sharp"
            ],
            "semantic_signals": []
          },
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm"
            ],
            "importance": "medium",
            "aliases": [
              "after 8pm due to work",
              "training sessions after 8pm"
            ],
            "semantic_signals": []
          },
          {
            "label": "conditioning day",
            "signals": [
              "conditioning day"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: late",
            "signals": [
              "late"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: schedule",
            "signals": [
              "schedule"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for late",
            "signals": [
              "late"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for schedule",
            "signals": [
              "schedule"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses stay",
            "signals": [
              "stay"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: hard, court, session",
            "signals": [
              "hard court session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: family trip next week, no court access, just hotel cardio and maybe some bodyweight work.",
        "synthetic_coach_reply": "Use the family trip as a no-court week and resume basketball-specific work when you're home.",
        "durable_truths": [
          {
            "label": "summer rec league",
            "signals": [
              "summer rec league"
            ],
            "importance": "medium",
            "aliases": [
              "primary training goal: keep first-step quickness sharp",
              "first-step quickness sharp"
            ],
            "semantic_signals": []
          },
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm"
            ],
            "importance": "medium",
            "aliases": [
              "after 8pm due to work",
              "training sessions after 8pm"
            ],
            "semantic_signals": []
          },
          {
            "label": "conditioning day",
            "signals": [
              "conditioning day"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for family",
            "signals": [
              "family"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for trip",
            "signals": [
              "trip"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses resume",
            "signals": [
              "resume"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses basketball-specific",
            "signals": [
              "basketball-specific"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, youre, home",
            "signals": [
              "when youre home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Permanent addition: I joined a Saturday morning shooting group, so I now have a regular high-rep session every weekend.",
        "synthetic_coach_reply": "Great. We'll treat the Saturday shooting group as a durable part of your basketball routine.",
        "durable_truths": [
          {
            "label": "summer rec league",
            "signals": [
              "summer rec league"
            ],
            "importance": "medium",
            "aliases": [
              "primary training goal: keep first-step quickness sharp",
              "first-step quickness sharp"
            ],
            "semantic_signals": []
          },
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm"
            ],
            "importance": "medium",
            "aliases": [
              "after 8pm due to work",
              "training sessions after 8pm"
            ],
            "semantic_signals": []
          },
          {
            "label": "conditioning day",
            "signals": [
              "conditioning day"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "saturday shooting group",
            "signals": [
              "saturday shooting group"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for shooting",
            "signals": [
              "shooting"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for group",
            "signals": [
              "group"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: every, weekend",
            "signals": [
              "every weekend"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update: I don't only train after 8pm anymore. My schedule changed and I can use some lunch breaks now, so that old timing note is outdated.",
        "synthetic_coach_reply": "Understood. We'll retire the after-8pm-only assumption and use the new midday windows when helpful.",
        "durable_truths": [
          {
            "label": "summer rec league",
            "signals": [
              "summer rec league"
            ],
            "importance": "medium",
            "aliases": [
              "primary training goal: keep first-step quickness sharp",
              "first-step quickness sharp"
            ],
            "semantic_signals": []
          },
          {
            "label": "conditioning day",
            "signals": [
              "conditioning day"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "saturday shooting group",
            "signals": [
              "saturday shooting group"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "no-court week",
            "signals": [
              "no-court week"
            ],
            "importance": "high",
            "aliases": [
              "no court access",
              "no-court week"
            ],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: family",
            "signals": [
              "family"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: trip",
            "signals": [
              "trip"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm only",
              "restricted to after 8pm"
            ],
            "importance": "high",
            "aliases": [
              "only train after 8pm",
              "no lunch-break availability"
            ],
            "semantic_signals": [
              "after-8pm-only"
            ]
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for lunch",
            "signals": [
              "lunch"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for breaks",
            "signals": [
              "breaks"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses after-8pm-only",
            "signals": [
              "after-8pm-only"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: midday, windows",
            "signals": [
              "midday windows"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "after 8pm",
            "signals": [
              "after 8pm only",
              "restricted to after 8pm"
            ],
            "importance": "high",
            "aliases": [
              "only train after 8pm",
              "no lunch-break availability"
            ],
            "semantic_signals": [
              "after-8pm-only"
            ]
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "summer rec league",
          "signals": [
            "summer rec league"
          ],
          "importance": "high",
          "aliases": [
            "primary training goal: keep first-step quickness sharp",
            "first-step quickness sharp"
          ],
          "semantic_signals": []
        },
        {
          "label": "conditioning day",
          "signals": [
            "conditioning day"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "saturday shooting group",
          "signals": [
            "saturday shooting group"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "summer rec league",
          "signals": [
            "summer rec league"
          ],
          "importance": "medium",
          "aliases": [
            "primary training goal: keep first-step quickness sharp",
            "first-step quickness sharp"
          ],
          "semantic_signals": []
        },
        {
          "label": "conditioning day",
          "signals": [
            "conditioning day"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "saturday shooting group",
          "signals": [
            "saturday shooting group"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "after 8pm",
          "signals": [
            "after 8pm only",
            "restricted to after 8pm"
          ],
          "importance": "high",
          "aliases": [
            "only train after 8pm",
            "no lunch-break availability"
          ],
          "semantic_signals": [
            "after-8pm-only"
          ]
        }
      ]
    }
  },
  {
    "id": "AM-013",
    "athlete_name": "Tessa Reed",
    "sport": "boxing",
    "profile_hint": "Boxer blending roadwork, bag work, and sparring.",
    "messages": [
      {
        "step": 1,
        "email": "I'm boxing amateur this year and building toward a June bout. My week usually includes roadwork, bag work, and sparring only on Fridays.",
        "synthetic_coach_reply": "We'll keep the June bout prep anchored around the current Friday sparring pattern.",
        "durable_truths": [
          {
            "label": "june bout",
            "signals": [
              "june bout"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "roadwork",
            "signals": [
              "roadwork"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for bout",
            "signals": [
              "bout"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for prep",
            "signals": [
              "prep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses friday",
            "signals": [
              "friday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sparring",
            "signals": [
              "sparring"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: bag, work",
            "signals": [
              "bag work"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week was standard: roadwork twice, bag rounds once, and Friday sparring. No durable changes.",
        "synthetic_coach_reply": "Good. Keep the same boxing rhythm and let me know how you recover after the next sparring day.",
        "durable_truths": [
          {
            "label": "june bout",
            "signals": [
              "june bout"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "roadwork",
            "signals": [
              "roadwork"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: boxing",
            "signals": [
              "boxing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: rhythm",
            "signals": [
              "rhythm"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for boxing",
            "signals": [
              "boxing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for rhythm",
            "signals": [
              "rhythm"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses keep",
            "signals": [
              "keep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, sparring, day",
            "signals": [
              "next sparring day"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm in a hotel for work next week and there won't be a heavy bag, so it will mostly be shadowboxing and conditioning.",
        "synthetic_coach_reply": "Use the hotel week for shadowboxing and conditioning, then return to the normal bag work when you're back.",
        "durable_truths": [
          {
            "label": "june bout",
            "signals": [
              "june bout"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "roadwork",
            "signals": [
              "roadwork"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel week",
            "signals": [
              "hotel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "heavy bag",
            "signals": [
              "heavy bag"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: shadowboxing",
            "signals": [
              "shadowboxing"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conditioning",
            "signals": [
              "conditioning"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for shadowboxing",
            "signals": [
              "shadowboxing"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for conditioning",
            "signals": [
              "conditioning"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses bag",
            "signals": [
              "bag"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, youre, back",
            "signals": [
              "when youre back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Long term, I switched to a gym with morning mitt sessions every Tuesday, so that's now a reliable technical slot.",
        "synthetic_coach_reply": "Excellent. We'll treat the Tuesday mitt session as a durable technical note.",
        "durable_truths": [
          {
            "label": "june bout",
            "signals": [
              "june bout"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "roadwork",
            "signals": [
              "roadwork"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday mitt session",
            "signals": [
              "tuesday mitt session"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel week",
            "signals": [
              "hotel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "heavy bag",
            "signals": [
              "heavy bag"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: shadowboxing",
            "signals": [
              "shadowboxing"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conditioning",
            "signals": [
              "conditioning"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for tuesday",
            "signals": [
              "tuesday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for mitt",
            "signals": [
              "mitt"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for session",
            "signals": [
              "session"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses technical",
            "signals": [
              "technical"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses note",
            "signals": [
              "note"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: reliable, technical, slot",
            "signals": [
              "reliable technical slot"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update: sparring is not Friday-only anymore. Coach moved our hard rounds to Wednesdays, so that old Friday note should be retired.",
        "synthetic_coach_reply": "Understood. We'll retire the Friday-only sparring assumption and use the new Wednesday hard-round slot.",
        "durable_truths": [
          {
            "label": "june bout",
            "signals": [
              "june bout"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "roadwork",
            "signals": [
              "roadwork"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "tuesday mitt session",
            "signals": [
              "tuesday mitt session"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "hotel week",
            "signals": [
              "hotel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "heavy bag",
            "signals": [
              "heavy bag"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: shadowboxing",
            "signals": [
              "shadowboxing"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: conditioning",
            "signals": [
              "conditioning"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for wednesdays",
            "signals": [
              "wednesdays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses friday-only",
            "signals": [
              "friday-only"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: wednesday, hard-round",
            "signals": [
              "wednesday hard-round"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "sparring fridays",
            "signals": [
              "sparring fridays"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "june bout",
          "signals": [
            "june bout"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "roadwork",
          "signals": [
            "roadwork"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday mitt session",
          "signals": [
            "tuesday mitt session"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "june bout",
          "signals": [
            "june bout"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "roadwork",
          "signals": [
            "roadwork"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "tuesday mitt session",
          "signals": [
            "tuesday mitt session"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "sparring fridays",
          "signals": [
            "sparring fridays"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-014",
    "athlete_name": "Grant Ellis",
    "sport": "skiing",
    "profile_hint": "Off-season skier using strength and cardio while waiting for snow.",
    "messages": [
      {
        "step": 1,
        "email": "I'm a skier in off-season prep right now. Mondays have usually been off-limits because of my commute, and the rest of the week is mostly strength plus easy cardio.",
        "synthetic_coach_reply": "We'll keep the off-season prep centered on strength and cardio while respecting the current no-Monday training constraint.",
        "durable_truths": [
          {
            "label": "off-season prep",
            "signals": [
              "off-season prep"
            ],
            "importance": "high",
            "aliases": [
              "off-season training focus",
              "off season training focus"
            ],
            "semantic_signals": []
          },
          {
            "label": "strength cardio",
            "signals": [
              "strength cardio"
            ],
            "importance": "high",
            "aliases": [
              "strength and easy cardio",
              "mostly strength plus easy cardio"
            ],
            "semantic_signals": []
          },
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "high",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for off-season",
            "signals": [
              "off-season"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for prep",
            "signals": [
              "prep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses respecting",
            "signals": [
              "respecting"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses no-monday",
            "signals": [
              "no-monday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: commute",
            "signals": [
              "commute"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "Normal update: two strength sessions and one easy bike this week. Nothing durable has changed.",
        "synthetic_coach_reply": "Good. Stay with the same off-season structure and update me after the next heavier lift.",
        "durable_truths": [
          {
            "label": "off-season prep",
            "signals": [
              "off-season prep"
            ],
            "importance": "medium",
            "aliases": [
              "off-season training focus",
              "off season training focus"
            ],
            "semantic_signals": []
          },
          {
            "label": "strength cardio",
            "signals": [
              "strength cardio"
            ],
            "importance": "medium",
            "aliases": [
              "strength and easy cardio",
              "mostly strength plus easy cardio"
            ],
            "semantic_signals": []
          },
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "medium",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: off-season",
            "signals": [
              "off-season"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for off-season",
            "signals": [
              "off-season"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for structure",
            "signals": [
              "structure"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses stay",
            "signals": [
              "stay"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: heavier, lift",
            "signals": [
              "heavier lift"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm traveling next week and won't have gym equipment, so it'll just be bodyweight work and hotel cardio until I get back.",
        "synthetic_coach_reply": "Use the travel week for bodyweight and hotel cardio only, then return to the normal gym setup at home.",
        "durable_truths": [
          {
            "label": "off-season prep",
            "signals": [
              "off-season prep"
            ],
            "importance": "medium",
            "aliases": [
              "off-season training focus",
              "off season training focus"
            ],
            "semantic_signals": []
          },
          {
            "label": "strength cardio",
            "signals": [
              "strength cardio"
            ],
            "importance": "medium",
            "aliases": [
              "strength and easy cardio",
              "mostly strength plus easy cardio"
            ],
            "semantic_signals": []
          },
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "medium",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: bodyweight",
            "signals": [
              "bodyweight"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: cardio",
            "signals": [
              "cardio"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for bodyweight",
            "signals": [
              "bodyweight"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for hotel",
            "signals": [
              "hotel"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for cardio",
            "signals": [
              "cardio"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses return",
            "signals": [
              "return"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses normal",
            "signals": [
              "normal"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses gym",
            "signals": [
              "gym"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: get, back",
            "signals": [
              "get back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "This is long term: I joined a Wednesday ski-erg group, so I now have a regular sport-specific conditioning session midweek.",
        "synthetic_coach_reply": "Great. We'll treat the Wednesday ski-erg group as a durable midweek note.",
        "durable_truths": [
          {
            "label": "off-season prep",
            "signals": [
              "off-season prep"
            ],
            "importance": "medium",
            "aliases": [
              "off-season training focus",
              "off season training focus"
            ],
            "semantic_signals": []
          },
          {
            "label": "strength cardio",
            "signals": [
              "strength cardio"
            ],
            "importance": "medium",
            "aliases": [
              "strength and easy cardio",
              "mostly strength plus easy cardio"
            ],
            "semantic_signals": []
          },
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "medium",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          },
          {
            "label": "wednesday ski-erg",
            "signals": [
              "wednesday ski-erg"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: bodyweight",
            "signals": [
              "bodyweight"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: cardio",
            "signals": [
              "cardio"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for ski-erg",
            "signals": [
              "ski-erg"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for group",
            "signals": [
              "group"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses midweek",
            "signals": [
              "midweek"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: sport-specific, conditioning",
            "signals": [
              "sport-specific conditioning"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "Update: Mondays are open now because I changed my commute, so the old no-Monday note is no longer true.",
        "synthetic_coach_reply": "Understood. We'll retire the no-Monday constraint and use Monday when it fits the ski prep.",
        "durable_truths": [
          {
            "label": "off-season prep",
            "signals": [
              "off-season prep"
            ],
            "importance": "medium",
            "aliases": [
              "off-season training focus",
              "off season training focus"
            ],
            "semantic_signals": []
          },
          {
            "label": "strength cardio",
            "signals": [
              "strength cardio"
            ],
            "importance": "medium",
            "aliases": [
              "strength and easy cardio",
              "mostly strength plus easy cardio"
            ],
            "semantic_signals": []
          },
          {
            "label": "wednesday ski-erg",
            "signals": [
              "wednesday ski-erg"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "travel week",
            "signals": [
              "travel week"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "hotel cardio",
            "signals": [
              "hotel cardio"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: bodyweight",
            "signals": [
              "bodyweight"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: hotel",
            "signals": [
              "hotel"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: cardio",
            "signals": [
              "cardio"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "high",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for mondays",
            "signals": [
              "mondays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for open",
            "signals": [
              "open"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses no-monday",
            "signals": [
              "no-monday"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: ski, prep",
            "signals": [
              "ski prep"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "mondays off-limits",
            "signals": [
              "mondays off-limits"
            ],
            "importance": "high",
            "aliases": [
              "mondays unavailable for training due to commute",
              "monday training unavailable due to commute"
            ],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "off-season prep",
          "signals": [
            "off-season prep"
          ],
          "importance": "high",
          "aliases": [
            "off-season training focus",
            "off season training focus"
          ],
          "semantic_signals": []
        },
        {
          "label": "strength cardio",
          "signals": [
            "strength cardio"
          ],
          "importance": "high",
          "aliases": [
            "strength and easy cardio",
            "mostly strength plus easy cardio"
          ],
          "semantic_signals": []
        },
        {
          "label": "wednesday ski-erg",
          "signals": [
            "wednesday ski-erg"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "off-season prep",
          "signals": [
            "off-season prep"
          ],
          "importance": "medium",
          "aliases": [
            "off-season training focus",
            "off season training focus"
          ],
          "semantic_signals": []
        },
        {
          "label": "strength cardio",
          "signals": [
            "strength cardio"
          ],
          "importance": "medium",
          "aliases": [
            "strength and easy cardio",
            "mostly strength plus easy cardio"
          ],
          "semantic_signals": []
        },
        {
          "label": "wednesday ski-erg",
          "signals": [
            "wednesday ski-erg"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "mondays off-limits",
          "signals": [
            "mondays off-limits"
          ],
          "importance": "high",
          "aliases": [
            "mondays unavailable for training due to commute",
            "monday training unavailable due to commute"
          ],
          "semantic_signals": []
        }
      ]
    }
  },
  {
    "id": "AM-015",
    "athlete_name": "Leah Foster",
    "sport": "pilates and running",
    "profile_hint": "Hybrid athlete mixing Pilates structure with a recreational running goal.",
    "messages": [
      {
        "step": 1,
        "email": "I'm balancing Pilates with running for a fall half marathon. I prefer to keep the harder work midweek, and reformer sessions are usually the anchor that keeps me feeling good.",
        "synthetic_coach_reply": "We'll keep the half-marathon build anchored by reformer work and use midweek for the harder sessions.",
        "durable_truths": [
          {
            "label": "half marathon",
            "signals": [
              "half marathon"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "reformer",
            "signals": [
              "reformer"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for half-marathon",
            "signals": [
              "half-marathon"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for build",
            "signals": [
              "build"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses midweek",
            "signals": [
              "midweek"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses harder",
            "signals": [
              "harder"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses sessions",
            "signals": [
              "sessions"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: feeling, good",
            "signals": [
              "feeling good"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "general",
        "active_context_mode": "acceptable"
      },
      {
        "step": 2,
        "email": "This week looked normal: one reformer class, two easy runs, and a short workout. No long-term changes.",
        "synthetic_coach_reply": "Good. Stay with the same hybrid pattern and tell me how the next workout lands.",
        "durable_truths": [
          {
            "label": "half marathon",
            "signals": [
              "half marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "reformer",
            "signals": [
              "reformer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [
          {
            "label": "routine update: same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: hybrid",
            "signals": [
              "hybrid"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "routine update: pattern",
            "signals": [
              "pattern"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_adjust_for": [
          {
            "label": "adjust for same",
            "signals": [
              "same"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for hybrid",
            "signals": [
              "hybrid"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for pattern",
            "signals": [
              "pattern"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses stay",
            "signals": [
              "stay"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: next, workout",
            "signals": [
              "next workout"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "routine_checkin",
        "active_context_mode": "acceptable"
      },
      {
        "step": 3,
        "email": "Temporary issue: I'm traveling for a few days and there won't be reformer access, so next week is mat work only plus short runs.",
        "synthetic_coach_reply": "Use the trip for mat work and short runs, then go back to reformer sessions when you're home.",
        "durable_truths": [
          {
            "label": "half marathon",
            "signals": [
              "half marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "reformer",
            "signals": [
              "reformer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "mat work only",
            "signals": [
              "mat work only"
            ],
            "importance": "high",
            "aliases": [
              "mat work plus short runs",
              "no reformer access"
            ],
            "semantic_signals": []
          },
          {
            "label": "travel",
            "signals": [
              "travel"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: short",
            "signals": [
              "short"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: runs",
            "signals": [
              "runs"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for short",
            "signals": [
              "short"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for runs",
            "signals": [
              "runs"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses go",
            "signals": [
              "go"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses back",
            "signals": [
              "back"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses reformer",
            "signals": [
              "reformer"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: when, youre, home",
            "signals": [
              "when youre home"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "temporary_disruption",
        "active_context_mode": "required"
      },
      {
        "step": 4,
        "email": "Long term, I joined a Sunday easy-run group in my neighborhood, so I now have a reliable social recovery run each week.",
        "synthetic_coach_reply": "Great. We'll treat the Sunday easy-run group as a durable part of the routine.",
        "durable_truths": [
          {
            "label": "half marathon",
            "signals": [
              "half marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "reformer",
            "signals": [
              "reformer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday easy-run group",
            "signals": [
              "sunday easy-run group"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "mat work only",
            "signals": [
              "mat work only"
            ],
            "importance": "high",
            "aliases": [
              "mat work plus short runs",
              "no reformer access"
            ],
            "semantic_signals": []
          },
          {
            "label": "travel",
            "signals": [
              "travel"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: short",
            "signals": [
              "short"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: runs",
            "signals": [
              "runs"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for easy-run",
            "signals": [
              "easy-run"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for group",
            "signals": [
              "group"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses durable",
            "signals": [
              "durable"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses part",
            "signals": [
              "part"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses routine",
            "signals": [
              "routine"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: social, recovery, run",
            "signals": [
              "social recovery run"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [],
        "message_intent": "durable_change",
        "active_context_mode": "acceptable"
      },
      {
        "step": 5,
        "email": "One change: I don't need all the hard work midweek anymore because my Fridays opened up. That old midweek-only preference is outdated.",
        "synthetic_coach_reply": "Understood. We'll retire the midweek-only hard-work note and use Friday when it helps the half-marathon build.",
        "durable_truths": [
          {
            "label": "half marathon",
            "signals": [
              "half marathon"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "reformer",
            "signals": [
              "reformer"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "sunday easy-run group",
            "signals": [
              "sunday easy-run group"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "active_context": [
          {
            "label": "mat work only",
            "signals": [
              "mat work only"
            ],
            "importance": "high",
            "aliases": [
              "mat work plus short runs",
              "no reformer access"
            ],
            "semantic_signals": []
          },
          {
            "label": "travel",
            "signals": [
              "travel"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: short",
            "signals": [
              "short"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "active context: runs",
            "signals": [
              "runs"
            ],
            "importance": "medium",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "retired_truths": [
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "routine_noise": [],
        "coach_should_adjust_for": [
          {
            "label": "adjust for fridays",
            "signals": [
              "fridays"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for opened",
            "signals": [
              "opened"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "adjust for up",
            "signals": [
              "up"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses retire",
            "signals": [
              "retire"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "recommendation uses midweek-only",
            "signals": [
              "midweek-only"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          },
          {
            "label": "open loop: friday, when, helps",
            "signals": [
              "friday when helps"
            ],
            "importance": "low",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "coach_should_not_do": [
          {
            "label": "harder midweek",
            "signals": [
              "harder midweek"
            ],
            "importance": "high",
            "aliases": [],
            "semantic_signals": []
          }
        ],
        "message_intent": "retirement",
        "active_context_mode": "expired"
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "half marathon",
          "signals": [
            "half marathon"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "reformer",
          "signals": [
            "reformer"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday easy-run group",
          "signals": [
            "sunday easy-run group"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retrieval_support": [
        {
          "label": "half marathon",
          "signals": [
            "half marathon"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "reformer",
          "signals": [
            "reformer"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        },
        {
          "label": "sunday easy-run group",
          "signals": [
            "sunday easy-run group"
          ],
          "importance": "medium",
          "aliases": [],
          "semantic_signals": []
        }
      ],
      "final_retired_truths": [
        {
          "label": "harder midweek",
          "signals": [
            "harder midweek"
          ],
          "importance": "high",
          "aliases": [],
          "semantic_signals": []
        }
      ]
    }
  }
]
```
