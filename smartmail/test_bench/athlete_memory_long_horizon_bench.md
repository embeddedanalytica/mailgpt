# Long-Horizon Athlete Memory Test Bench

This file is a markdown fixture for validating long-horizon athlete-memory behavior across extended coach-athlete relationships.

## Scenario Contract

Each scenario in the machine-readable block includes:

- `id`
- `athlete_name`
- `sport`
- `profile_hint`
- `phases`
- `final_assertions`

Each phase includes:

- `phase_id`
- `phase_goal`
- `messages`
- `checkpoint_assertions`

Each message includes:

- `step`
- `email`
- `synthetic_coach_reply`
- optional `event_tags`

Checkpoint assertions use the same human-centric fact schema as the short athlete-memory bench:

- `label`
- `durable_truths`
- `active_context`
- `retired_truths`
- `routine_noise`
- `coach_should_adjust_for`
- `coach_should_not_do`

Checkpoint assertions may also include optional architecture-specific checks for the redesigned memory system:

- `expected_active_storage`
- `expected_retired_storage`
- `expected_compiled_prompt`
- `expected_rejections`

Each fact uses:

- `label`
- `signals`
- `importance`

Final assertions include:

- `final_durable_truths`
- `final_retrieval_support`
- `final_retired_truths`

Final assertions may also include optional architecture-specific checks:

- `final_active_storage`
- `final_retired_storage`
- `final_compiled_prompt`
- `final_rejections`

Optional architecture-specific assertion shapes:

- `expected_active_storage`
  - `must_include`
  - `must_exclude`
  - `max_active_counts`
- `expected_retired_storage`
  - `must_include`
  - `must_exclude`
  - `max_retired_counts`
- `expected_compiled_prompt`
  - `must_include`
  - `must_exclude`
- `expected_rejections`
  - list of objects with:
    - `label`
    - `signals`
    - `reason`

```json
[
  {
    "id": "AM-LH-001",
    "athlete_name": "Maya Chen",
    "sport": "marathon running",
    "profile_hint": "Experienced marathoner with an early weekday schedule and shifting weekend childcare constraints.",
    "phases": [
      {
        "phase_id": "onboarding",
        "phase_goal": "Establish the core marathon goal and recurring schedule constraints.",
        "messages": [
          {
            "step": 1,
            "email": "I'm building toward the Bay Crest Marathon this fall. Weekdays have to finish before 7am because of school drop-off.",
            "synthetic_coach_reply": "We'll keep weekday sessions early and build the marathon plan around that morning cutoff."
          },
          {
            "step": 2,
            "email": "Most weeks I run five days, and Sunday is usually my long run.",
            "synthetic_coach_reply": "Great, we'll protect Sunday as the long-run anchor and keep the rest of the week flexible."
          },
          {
            "step": 3,
            "email": "Right now Saturdays are mostly unavailable because my partner works.",
            "synthetic_coach_reply": "Understood, we'll avoid depending on Saturday for key sessions while that constraint is active."
          },
          {
            "step": 4,
            "email": "That setup has been pretty consistent for the last month.",
            "synthetic_coach_reply": "Good, we'll treat the early mornings, Sunday long run, and current Saturday limit as the working structure."
          }
        ],
        "checkpoint_assertions": {
          "label": "onboarding checkpoint",
          "durable_truths": [
            {
              "label": "Bay Crest Marathon goal",
              "signals": [
                "bay crest marathon",
                "marathon this fall"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 7am cutoff",
              "signals": [
                "before 7am",
                "finish before 7am"
              ],
              "importance": "high"
            },
            {
              "label": "Sunday long run anchor",
              "signals": [
                "sunday long run",
                "sunday is usually my long run"
              ],
              "importance": "high"
            },
            {
              "label": "Saturday unavailable",
              "signals": [
                "saturdays unavailable",
                "saturday mostly unavailable"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "plan around early weekdays",
              "signals": [
                "keep weekday sessions early",
                "build around that morning cutoff"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "normal_churn",
        "phase_goal": "Ignore routine training logs without rewriting durable structure.",
        "messages": [
          {
            "step": 5,
            "email": "Quick update: Tuesday tempo went well and Thursday easy miles felt smooth.",
            "synthetic_coach_reply": "Nice, keep the same overall structure and let me know how Sunday's long run feels."
          },
          {
            "step": 6,
            "email": "No schedule changes, just logging that the legs are responding well.",
            "synthetic_coach_reply": "Perfect, we'll stay with the same setup unless something real changes."
          },
          {
            "step": 7,
            "email": "Another normal week so far, nothing new on family logistics.",
            "synthetic_coach_reply": "Good, maintain the same cadence and keep protecting the long run."
          },
          {
            "step": 8,
            "email": "Today's recovery jog was uneventful. That's all from me.",
            "synthetic_coach_reply": "Sounds good. We'll keep the plan steady."
          }
        ],
        "checkpoint_assertions": {
          "label": "normal churn checkpoint",
          "durable_truths": [
            {
              "label": "Bay Crest Marathon goal",
              "signals": [
                "bay crest marathon",
                "marathon this fall"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 7am cutoff",
              "signals": [
                "before 7am",
                "finish before 7am"
              ],
              "importance": "high"
            },
            {
              "label": "Sunday long run anchor",
              "signals": [
                "sunday long run"
              ],
              "importance": "high"
            },
            {
              "label": "Saturday unavailable",
              "signals": [
                "saturday mostly unavailable",
                "saturdays unavailable"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [
            {
              "label": "smooth Tuesday/Thursday update",
              "signals": [
                "tempo went well",
                "easy miles felt smooth"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "keep same structure",
              "signals": [
                "keep the same overall structure",
                "stay with the same setup"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "temporary_disruption",
        "phase_goal": "Carry travel context in continuity while keeping durable truths intact.",
        "messages": [
          {
            "step": 9,
            "email": "Next week I'm in Denver for work and the hotel only has a treadmill.",
            "synthetic_coach_reply": "We'll treat Denver as a treadmill week and keep the marathon work simple while you're away."
          },
          {
            "step": 10,
            "email": "I also won't have my usual Sunday long-run loop while I'm there.",
            "synthetic_coach_reply": "That's fine. We'll shorten the long-run expectation for the travel week and resume normal rhythm at home."
          },
          {
            "step": 11,
            "email": "This is definitely temporary, just the one trip.",
            "synthetic_coach_reply": "Perfect, we'll keep it in the short-term plan only and not change the bigger marathon structure."
          },
          {
            "step": 12,
            "email": "Once I'm back, things should go right back to normal.",
            "synthetic_coach_reply": "Great, we'll plan to return to the normal setup as soon as the Denver trip is over."
          }
        ],
        "checkpoint_assertions": {
          "label": "temporary disruption checkpoint",
          "durable_truths": [
            {
              "label": "Bay Crest Marathon goal",
              "signals": [
                "bay crest marathon",
                "marathon structure"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 7am cutoff",
              "signals": [
                "before 7am",
                "finish before 7am"
              ],
              "importance": "high"
            },
            {
              "label": "Saturday unavailable",
              "signals": [
                "saturday mostly unavailable",
                "saturdays unavailable"
              ],
              "importance": "high"
            }
          ],
          "active_context": [
            {
              "label": "Denver treadmill trip",
              "signals": [
                "denver",
                "hotel treadmill",
                "travel week"
              ],
              "importance": "high"
            }
          ],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "resume normal rhythm after travel",
              "signals": [
                "resume normal rhythm",
                "return to the normal setup"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "durable_change",
        "phase_goal": "Capture a durable new opportunity and retire the stale Saturday restriction.",
        "messages": [
          {
            "step": 13,
            "email": "Back home now. I also joined a Tuesday lunch strength group at work and that should stick.",
            "synthetic_coach_reply": "Excellent, we'll treat Tuesday lunch strength as a durable part of your week."
          },
          {
            "step": 14,
            "email": "More importantly, childcare shifted and Saturdays are open again if we want them.",
            "synthetic_coach_reply": "That's a meaningful change. We'll retire the old no-Saturday assumption and use Saturday when it helps the marathon build."
          },
          {
            "step": 15,
            "email": "The early weekday limit is still true though. That part hasn't changed.",
            "synthetic_coach_reply": "Good to know. We'll keep the early-morning weekday cutoff but add Saturday flexibility."
          },
          {
            "step": 16,
            "email": "I think this new setup is the one we'll be on for a while.",
            "synthetic_coach_reply": "Great, we'll treat both the Saturday opening and Tuesday strength slot as durable structure."
          }
        ],
        "checkpoint_assertions": {
          "label": "durable change checkpoint",
          "durable_truths": [
            {
              "label": "Bay Crest Marathon goal",
              "signals": [
                "bay crest marathon",
                "marathon build"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 7am cutoff",
              "signals": [
                "before 7am",
                "early-morning weekday cutoff"
              ],
              "importance": "high"
            },
            {
              "label": "Saturday available",
              "signals": [
                "saturdays are open",
                "saturday opening"
              ],
              "importance": "high"
            },
            {
              "label": "Tuesday lunch strength",
              "signals": [
                "tuesday lunch strength",
                "tuesday strength slot"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Saturday restriction",
              "signals": [
                "no-saturday",
                "saturday mostly unavailable"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "use Saturday when helpful",
              "signals": [
                "use Saturday when it helps",
                "add Saturday flexibility"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "Keep old no-Saturday assumption",
              "signals": [
                "no-saturday",
                "saturday mostly unavailable"
              ],
              "importance": "high"
            }
          ]
        }
      },
      {
        "phase_id": "late_retrieval",
        "phase_goal": "Ensure the oldest core truths survive late in the relationship under memory pressure.",
        "messages": [
          {
            "step": 17,
            "email": "A few months later: the Tuesday lunch strength habit is still going.",
            "synthetic_coach_reply": "Great, we'll keep treating that as a stable weekly support session."
          },
          {
            "step": 18,
            "email": "Saturday flexibility is still a huge help, even if I don't use it every week.",
            "synthetic_coach_reply": "Perfect, the option itself still matters and we'll keep using it when it serves the bigger build."
          },
          {
            "step": 19,
            "email": "I'm otherwise just checking in. Normal week, no major curveballs.",
            "synthetic_coach_reply": "Sounds good. We'll hold the structure steady."
          },
          {
            "step": 20,
            "email": "Wanted to confirm the early weekday cutoff is still very real with school drop-off.",
            "synthetic_coach_reply": "Thanks for reaffirming that. We'll keep the morning cutoff, Saturday flexibility, and Tuesday strength as the core structure around the marathon goal."
          }
        ],
        "checkpoint_assertions": {
          "label": "late retrieval checkpoint",
          "durable_truths": [
            {
              "label": "Bay Crest Marathon goal",
              "signals": [
                "bay crest marathon",
                "marathon goal"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 7am cutoff",
              "signals": [
                "before 7am",
                "morning cutoff"
              ],
              "importance": "high"
            },
            {
              "label": "Saturday available",
              "signals": [
                "Saturday flexibility",
                "saturdays are open"
              ],
              "importance": "high"
            },
            {
              "label": "Tuesday lunch strength",
              "signals": [
                "Tuesday lunch strength",
                "Tuesday strength"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Saturday restriction",
              "signals": [
                "no-saturday",
                "saturday mostly unavailable"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [
            {
              "label": "normal week check-in",
              "signals": [
                "normal week",
                "no major curveballs"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "plan around retained core structure",
              "signals": [
                "keep the morning cutoff",
                "saturday flexibility",
                "Tuesday strength"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "resurrect the old Saturday restriction",
              "signals": [
                "saturday mostly unavailable",
                "no-saturday"
              ],
              "importance": "high"
            }
          ]
        }
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "Bay Crest Marathon goal",
          "signals": [
            "bay crest marathon",
            "marathon goal"
          ],
          "importance": "high"
        },
        {
          "label": "weekday before 7am cutoff",
          "signals": [
            "before 7am",
            "morning cutoff"
          ],
          "importance": "high"
        },
        {
          "label": "Saturday available",
          "signals": [
            "Saturday flexibility",
            "saturdays are open"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "Bay Crest Marathon goal",
          "signals": [
            "bay crest marathon",
            "marathon goal"
          ],
          "importance": "high"
        },
        {
          "label": "Saturday available",
          "signals": [
            "Saturday flexibility",
            "saturdays are open"
          ],
          "importance": "high"
        }
      ],
      "final_retired_truths": [
        {
          "label": "Old Saturday restriction",
          "signals": [
            "no-saturday",
            "saturday mostly unavailable"
          ],
          "importance": "high"
        }
      ]
    }
  },
  {
    "id": "AM-LH-002",
    "athlete_name": "Luis Ortega",
    "sport": "triathlon",
    "profile_hint": "Age-group triathlete with a stable swim focus but lots of temporary week-to-week life interruptions.",
    "phases": [
      {
        "phase_id": "onboarding",
        "phase_goal": "Establish the swim-focused goal and recurring masters schedule.",
        "messages": [
          {
            "step": 1,
            "email": "I'm training for an Olympic tri in late summer. Swimming is still my limiter.",
            "synthetic_coach_reply": "We'll keep the swim emphasis central while the rest of the week supports that goal."
          },
          {
            "step": 2,
            "email": "Masters swim every Tuesday night is my main recurring session.",
            "synthetic_coach_reply": "Great, we'll anchor the week around Tuesday masters."
          },
          {
            "step": 3,
            "email": "Bike work usually fits on Thursday and Sunday.",
            "synthetic_coach_reply": "Perfect, we'll use Thursday and Sunday as the primary bike windows."
          },
          {
            "step": 4,
            "email": "That pattern is my baseline most weeks.",
            "synthetic_coach_reply": "Good, we'll treat that as the durable triathlon structure."
          }
        ],
        "checkpoint_assertions": {
          "label": "onboarding checkpoint",
          "durable_truths": [
            {
              "label": "Olympic tri goal",
              "signals": [
                "Olympic tri",
                "late summer"
              ],
              "importance": "high"
            },
            {
              "label": "swim is the limiter",
              "signals": [
                "swimming is my limiter",
                "swim emphasis",
                "limiting discipline",
                "swimming is the limiter",
                "swim is the limiting",
                "central emphasis"
              ],
              "importance": "high"
            },
            {
              "label": "Tuesday masters",
              "signals": [
                "Tuesday masters",
                "masters swim every Tuesday"
              ],
              "importance": "high"
            },
            {
              "label": "Thursday and Sunday bike",
              "signals": [
                "Thursday and Sunday",
                "primary bike windows"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "keep swim emphasis central",
              "signals": [
                "keep the swim emphasis central",
                "anchor the week around Tuesday masters"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "disruption_cycle_one",
        "phase_goal": "Handle a temporary conference week without promoting it to durable memory.",
        "messages": [
          {
            "step": 5,
            "email": "Conference next week. The hotel has no pool and only a tiny gym.",
            "synthetic_coach_reply": "We'll treat next week as short maintenance work and keep the triathlon structure intact."
          },
          {
            "step": 6,
            "email": "That's just for the travel week, not a permanent issue.",
            "synthetic_coach_reply": "Perfect, we'll keep that temporary and go back to the swim rhythm after travel."
          },
          {
            "step": 7,
            "email": "I should still be able to do some easy treadmill and bike maintenance.",
            "synthetic_coach_reply": "That's enough for the week. We'll prioritize returning to the pool when you're back."
          },
          {
            "step": 8,
            "email": "Once I'm home, the usual Tuesday masters setup returns.",
            "synthetic_coach_reply": "Great, we'll resume the usual masters-led structure right away."
          }
        ],
        "checkpoint_assertions": {
          "label": "disruption cycle one checkpoint",
          "durable_truths": [
            {
              "label": "Olympic tri goal",
              "signals": [
                "Olympic tri",
                "triathlon structure"
              ],
              "importance": "high"
            },
            {
              "label": "Tuesday masters",
              "signals": [
                "Tuesday masters",
                "usual masters setup"
              ],
              "importance": "high"
            }
          ],
          "active_context": [
            {
              "label": "Conference hotel with no pool",
              "signals": [
                "conference",
                "no pool",
                "tiny gym"
              ],
              "importance": "high"
            }
          ],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "return to swim rhythm after travel",
              "signals": [
                "go back to the swim rhythm after travel",
                "prioritize returning to the pool"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "disruption_cycle_two",
        "phase_goal": "Handle a second temporary disruption and keep continuity human without letting temporary context overstay.",
        "messages": [
          {
            "step": 9,
            "email": "A month later: my daughter is sick, so this week is chaos and pool time may disappear again.",
            "synthetic_coach_reply": "Understood, we'll treat this week as family-chaos triage and keep the plan flexible."
          },
          {
            "step": 10,
            "email": "I'm hoping this is just a few days of disruption, not another long stretch.",
            "synthetic_coach_reply": "That makes sense. We'll keep it short-term and preserve the bigger swim-first structure."
          },
          {
            "step": 11,
            "email": "If she rebounds, I can still catch Sunday bike work.",
            "synthetic_coach_reply": "Great, Sunday can remain the fallback bike anchor if the week settles."
          },
          {
            "step": 12,
            "email": "By next week I expect normal life again.",
            "synthetic_coach_reply": "Perfect, we'll let this week breathe and return to the baseline as soon as the family situation settles."
          }
        ],
        "checkpoint_assertions": {
          "label": "disruption cycle two checkpoint",
          "durable_truths": [
            {
              "label": "Olympic tri goal",
              "signals": [
                "Olympic tri",
                "swim-first structure"
              ],
              "importance": "high"
            },
            {
              "label": "Tuesday masters",
              "signals": [
                "Tuesday masters",
                "baseline"
              ],
              "importance": "high"
            },
            {
              "label": "Thursday and Sunday bike",
              "signals": [
                "Sunday bike anchor",
                "Thursday and Sunday"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [
            {
              "label": "family-chaos week",
              "signals": [
                "daughter is sick",
                "week is chaos",
                "family situation"
              ],
              "importance": "high"
            }
          ],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "keep this temporary and flexible",
              "signals": [
                "keep it short-term",
                "return to the baseline"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "durable_update",
        "phase_goal": "Capture a durable schedule shift after repeated temporary noise.",
        "messages": [
          {
            "step": 13,
            "email": "The one long-term change is that my masters group moved to Wednesday nights.",
            "synthetic_coach_reply": "Got it. We'll retire the old Tuesday masters assumption and use Wednesday as the fixed swim slot."
          },
          {
            "step": 14,
            "email": "Also, my office finally opened a secure bike room, so commuting twice a week is realistic.",
            "synthetic_coach_reply": "That's useful. We'll treat the bike commute as durable weekly volume."
          },
          {
            "step": 15,
            "email": "The swim emphasis is still the same. It's just the schedule pieces that changed.",
            "synthetic_coach_reply": "Perfect, we'll keep the swim-first focus while updating the weekly logistics."
          },
          {
            "step": 16,
            "email": "I expect both of those changes to stick.",
            "synthetic_coach_reply": "Great, we'll treat Wednesday masters and the bike commute as part of the new normal."
          }
        ],
        "checkpoint_assertions": {
          "label": "durable update checkpoint",
          "durable_truths": [
            {
              "label": "Olympic tri goal",
              "signals": [
                "Olympic tri",
                "swim-first focus"
              ],
              "importance": "high"
            },
            {
              "label": "Wednesday masters",
              "signals": [
                "Wednesday nights",
                "Wednesday as the fixed swim slot"
              ],
              "importance": "high"
            },
            {
              "label": "Bike commute volume",
              "signals": [
                "bike commute",
                "commuting twice a week"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Tuesday masters",
              "signals": [
                "Tuesday masters",
                "old Tuesday masters assumption"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "use new weekly logistics",
              "signals": [
                "use Wednesday as the fixed swim slot",
                "bike commute as durable weekly volume"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "keep old Tuesday masters slot",
              "signals": [
                "Tuesday masters",
                "old Tuesday masters assumption"
              ],
              "importance": "high"
            }
          ]
        }
      },
      {
        "phase_id": "late_retrieval",
        "phase_goal": "Make sure temporary disruptions fade while the durable updates survive.",
        "messages": [
          {
            "step": 17,
            "email": "A while later now: normal week, nothing dramatic.",
            "synthetic_coach_reply": "Nice, we'll keep the current durable setup steady."
          },
          {
            "step": 18,
            "email": "Wednesday masters has been reliable, and the bike commute is working well.",
            "synthetic_coach_reply": "Excellent, both of those sound like established parts of your tri week now."
          },
          {
            "step": 19,
            "email": "No family chaos, no conference travel, no sick-kid disruptions right now.",
            "synthetic_coach_reply": "Great, then we can coach the normal week again without any temporary triage."
          },
          {
            "step": 20,
            "email": "Swimming is still the limiter, so I still want the plan to reflect that.",
            "synthetic_coach_reply": "Absolutely, we'll keep swim-first planning while using Wednesday masters and the bike commute as the stable structure."
          }
        ],
        "checkpoint_assertions": {
          "label": "late retrieval checkpoint",
          "durable_truths": [
            {
              "label": "Olympic tri goal",
              "signals": [
                "Olympic tri",
                "swim-first planning"
              ],
              "importance": "high"
            },
            {
              "label": "swim is the limiter",
              "signals": [
                "Swimming is still the limiter",
                "swim-first",
                "limiting discipline",
                "swimming is the limiter",
                "swim is the limiting",
                "central emphasis",
                "swim emphasis"
              ],
              "importance": "high"
            },
            {
              "label": "Wednesday masters",
              "signals": [
                "Wednesday masters",
                "Wednesday nights"
              ],
              "importance": "high"
            },
            {
              "label": "Bike commute volume",
              "signals": [
                "bike commute",
                "durable weekly volume"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Tuesday masters",
              "signals": [
                "Tuesday masters",
                "old Tuesday masters assumption"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [
            {
              "label": "normal week confirmation",
              "signals": [
                "normal week",
                "nothing dramatic"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "coach the normal week again",
              "signals": [
                "coach the normal week again",
                "keep swim-first planning"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "keep reacting to stale temporary disruptions",
              "signals": [
                "conference travel",
                "sick-kid disruptions"
              ],
              "importance": "medium"
            },
            {
              "label": "resurrect Tuesday masters",
              "signals": [
                "Tuesday masters",
                "old Tuesday masters assumption"
              ],
              "importance": "high"
            }
          ]
        }
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "Olympic tri goal",
          "signals": [
            "Olympic tri",
            "swim-first planning"
          ],
          "importance": "high"
        },
        {
          "label": "Wednesday masters",
          "signals": [
            "Wednesday masters",
            "Wednesday nights"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "swim is the limiter",
          "signals": [
            "Swimming is still the limiter",
            "swim-first",
            "limiting discipline",
            "swimming is the limiter",
            "swim is the limiting",
            "central emphasis",
            "swim emphasis"
          ],
          "importance": "high"
        },
        {
          "label": "Bike commute volume",
          "signals": [
            "bike commute",
            "durable weekly volume"
          ],
          "importance": "medium"
        }
      ],
      "final_retired_truths": [
        {
          "label": "Old Tuesday masters",
          "signals": [
            "Tuesday masters",
            "old Tuesday masters assumption"
          ],
          "importance": "high"
        }
      ]
    }
  },
  {
    "id": "AM-LH-003",
    "athlete_name": "Erin Walsh",
    "sport": "gravel cycling",
    "profile_hint": "Gravel rider whose environment gradually gets richer with options, forcing the system to keep only the most valuable truths.",
    "phases": [
      {
        "phase_id": "onboarding",
        "phase_goal": "Establish the long gravel goal and the most important baseline constraints.",
        "messages": [
          {
            "step": 1,
            "email": "I'm targeting a 120-mile gravel race in September.",
            "synthetic_coach_reply": "Great, we'll center the season around that 120-mile gravel goal."
          },
          {
            "step": 2,
            "email": "Weekdays are mostly indoor trainer rides before work.",
            "synthetic_coach_reply": "Perfect, we'll treat the indoor trainer as the weekday anchor."
          },
          {
            "step": 3,
            "email": "Outdoor gravel rides are usually Sunday-only because Saturdays are crowded with family plans.",
            "synthetic_coach_reply": "Understood, we'll build around Sunday as the main outdoor gravel day for now."
          },
          {
            "step": 4,
            "email": "Those three things are the big constants right now.",
            "synthetic_coach_reply": "Good, we'll treat the race goal, indoor trainer routine, and Sunday outdoor slot as the core structure."
          }
        ],
        "checkpoint_assertions": {
          "label": "onboarding checkpoint",
          "durable_truths": [
            {
              "label": "120-mile gravel goal",
              "signals": [
                "120-mile gravel race",
                "September"
              ],
              "importance": "high"
            },
            {
              "label": "Indoor trainer weekdays",
              "signals": [
                "indoor trainer",
                "weekday anchor",
                "weekday mornings",
                "before work"
              ],
              "importance": "high"
            },
            {
              "label": "Sunday outdoor gravel",
              "signals": [
                "Sunday-only",
                "main outdoor gravel day"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "build around the core structure",
              "signals": [
                "center the season",
                "core structure"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "gear_growth",
        "phase_goal": "Add several useful details without losing the primary truths.",
        "messages": [
          {
            "step": 5,
            "email": "I bought a power meter for the gravel bike.",
            "synthetic_coach_reply": "Nice, we'll use power data to make outdoor pacing more precise."
          },
          {
            "step": 6,
            "email": "I also picked up a fan for the trainer setup, which makes indoor rides way better.",
            "synthetic_coach_reply": "Helpful. That should make the weekday trainer work more sustainable."
          },
          {
            "step": 7,
            "email": "And I finally got a proper tire repair kit that lives in the bike bag.",
            "synthetic_coach_reply": "Great, that's one less friction point for outdoor rides."
          },
          {
            "step": 8,
            "email": "Mostly just sharing that the equipment side is getting smoother.",
            "synthetic_coach_reply": "Excellent. We'll keep the core training structure and use the best of those upgrades where they matter."
          }
        ],
        "checkpoint_assertions": {
          "label": "gear growth checkpoint",
          "durable_truths": [
            {
              "label": "120-mile gravel goal",
              "signals": [
                "120-mile gravel race",
                "season"
              ],
              "importance": "high"
            },
            {
              "label": "Indoor trainer weekdays",
              "signals": [
                "weekday trainer",
                "indoor trainer",
                "before work"
              ],
              "importance": "high"
            },
            {
              "label": "Sunday outdoor gravel",
              "signals": [
                "outdoor rides",
                "Sunday"
              ],
              "importance": "high"
            },
            {
              "label": "Power meter available",
              "signals": [
                "power meter",
                "power data"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [
            {
              "label": "fan detail",
              "signals": [
                "fan for the trainer",
                "tire repair kit"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "use power for pacing",
              "signals": [
                "use power data",
                "outdoor pacing"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "temporary_disruption",
        "phase_goal": "Handle a temporary business trip without storing it as a durable limitation.",
        "messages": [
          {
            "step": 9,
            "email": "I'm traveling next week for work and won't have the bike, just a hotel spin bike if it's free.",
            "synthetic_coach_reply": "We'll treat next week as a short maintenance block and return to normal once the trip ends."
          },
          {
            "step": 10,
            "email": "No outdoor gravel while I'm away, obviously.",
            "synthetic_coach_reply": "Totally fine. We'll keep the race build intact and just protect consistency."
          },
          {
            "step": 11,
            "email": "This is only one week though.",
            "synthetic_coach_reply": "Perfect, we'll keep it short-term and not rewrite the bigger structure."
          },
          {
            "step": 12,
            "email": "As soon as I'm back I can go right back to the trainer plus Sunday gravel routine.",
            "synthetic_coach_reply": "Great, then we'll resume the usual trainer-and-Sunday pattern immediately."
          }
        ],
        "checkpoint_assertions": {
          "label": "temporary disruption checkpoint",
          "durable_truths": [
            {
              "label": "120-mile gravel goal",
              "signals": [
                "race build",
                "120-mile gravel race"
              ],
              "importance": "high"
            },
            {
              "label": "Indoor trainer weekdays",
              "signals": [
                "trainer",
                "usual trainer",
                "indoor trainer",
                "weekday"
              ],
              "importance": "high"
            },
            {
              "label": "Sunday outdoor gravel",
              "signals": [
                "Sunday gravel routine",
                "Sunday"
              ],
              "importance": "high"
            }
          ],
          "active_context": [
            {
              "label": "business trip with hotel spin bike only",
              "signals": [
                "traveling next week",
                "hotel spin bike"
              ],
              "importance": "high"
            }
          ],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "resume usual pattern immediately",
              "signals": [
                "return to normal once the trip ends",
                "resume the usual trainer-and-Sunday pattern"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "durable_reversal",
        "phase_goal": "Change a core schedule constraint while more medium-value details compete for space.",
        "messages": [
          {
            "step": 13,
            "email": "Big change: Saturdays are opening up now, so outdoor gravel isn't Sunday-only anymore.",
            "synthetic_coach_reply": "That's a real shift. We'll retire the Sunday-only assumption and use full weekend flexibility."
          },
          {
            "step": 14,
            "email": "I also joined a weekly Wednesday mobility class after work.",
            "synthetic_coach_reply": "Nice, we'll treat that as a recurring recovery support session."
          },
          {
            "step": 15,
            "email": "And I upgraded the garage with a small skills setup for handling drills.",
            "synthetic_coach_reply": "Useful. That can support technique work when weather or family timing gets messy."
          },
          {
            "step": 16,
            "email": "The race goal and weekday trainer pattern are still the main anchors though.",
            "synthetic_coach_reply": "Perfect, we'll keep the primary anchors in place while layering in the best of the new options."
          }
        ],
        "checkpoint_assertions": {
          "label": "durable reversal checkpoint",
          "durable_truths": [
            {
              "label": "120-mile gravel goal",
              "signals": [
                "race goal",
                "120-mile gravel race"
              ],
              "importance": "high"
            },
            {
              "label": "Indoor trainer weekdays",
              "signals": [
                "weekday trainer",
                "trainer pattern",
                "indoor trainer",
                "before work",
                "weekday anchor"
              ],
              "importance": "high"
            },
            {
              "label": "Weekend outdoor flexibility",
              "signals": [
                "not Sunday-only",
                "weekend flexibility",
                "Saturday",
                "weekend outdoor",
                "no longer restricted to Sunday",
                "both days"
              ],
              "importance": "high"
            },
            {
              "label": "Wednesday mobility class",
              "signals": [
                "Wednesday mobility class",
                "recovery support session"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Sunday-only outdoor rule",
              "signals": [
                "Sunday-only",
                "Sunday-only assumption"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [
            {
              "label": "garage drill setup",
              "signals": [
                "garage",
                "handling drills"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "use full weekend flexibility",
              "signals": [
                "use full weekend flexibility",
                "layering in the best of the new options"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "keep Sunday-only assumption",
              "signals": [
                "Sunday-only",
                "Sunday-only assumption"
              ],
              "importance": "high"
            }
          ]
        }
      },
      {
        "phase_id": "late_retrieval",
        "phase_goal": "Stress salience under pressure and make sure the core truths still win late.",
        "messages": [
          {
            "step": 17,
            "email": "Months later, the Wednesday mobility class is still happening but sometimes I miss it.",
            "synthetic_coach_reply": "That's fine. We'll treat it as useful support, not the center of the plan."
          },
          {
            "step": 18,
            "email": "Weekend outdoor flexibility has turned out to be huge for the gravel build.",
            "synthetic_coach_reply": "Great, that sounds like a major planning lever now."
          },
          {
            "step": 19,
            "email": "Normal week otherwise. Just confirming the trainer-before-work pattern is still the backbone.",
            "synthetic_coach_reply": "Perfect, we'll keep the trainer backbone and use the flexible weekend outdoor options around it."
          },
          {
            "step": 20,
            "email": "The September 120-mile race is definitely still the north star.",
            "synthetic_coach_reply": "Excellent. We'll keep the race goal, trainer backbone, and weekend outdoor flexibility as the top-tier truths in the plan."
          }
        ],
        "checkpoint_assertions": {
          "label": "late retrieval checkpoint",
          "durable_truths": [
            {
              "label": "120-mile gravel goal",
              "signals": [
                "September 120-mile race",
                "north star"
              ],
              "importance": "high"
            },
            {
              "label": "Indoor trainer weekdays",
              "signals": [
                "trainer-before-work",
                "trainer backbone",
                "indoor trainer",
                "weekday trainer",
                "weekday anchor",
                "before work"
              ],
              "importance": "high"
            },
            {
              "label": "Weekend outdoor flexibility",
              "signals": [
                "weekend outdoor",
                "weekend flexibility",
                "Saturday",
                "no longer restricted to Sunday",
                "not Sunday-only"
              ],
              "importance": "high"
            },
            {
              "label": "Wednesday mobility class",
              "signals": [
                "Wednesday mobility class",
                "useful support"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "Old Sunday-only outdoor rule",
              "signals": [
                "Sunday-only",
                "Sunday-only assumption"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [
            {
              "label": "normal week confirmation",
              "signals": [
                "normal week",
                "sometimes I miss it"
              ],
              "importance": "low"
            }
          ],
          "coach_should_adjust_for": [
            {
              "label": "build around top-tier truths",
              "signals": [
                "major planning lever",
                "top-tier truths"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "treat support details as more important than the backbone",
              "signals": [
                "center of the plan"
              ],
              "importance": "medium"
            },
            {
              "label": "resurrect Sunday-only rule",
              "signals": [
                "Sunday-only",
                "Sunday-only assumption"
              ],
              "importance": "high"
            }
          ]
        }
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "120-mile gravel goal",
          "signals": [
            "September 120-mile race",
            "north star"
          ],
          "importance": "high"
        },
        {
          "label": "Indoor trainer weekdays",
          "signals": [
            "trainer-before-work",
            "trainer backbone",
            "indoor trainer",
            "weekday trainer",
            "weekday anchor",
            "before work"
          ],
          "importance": "high"
        },
        {
          "label": "Weekend outdoor flexibility",
          "signals": [
            "weekend outdoor",
            "weekend flexibility",
            "Saturday",
            "no longer restricted to Sunday",
            "not Sunday-only"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "120-mile gravel goal",
          "signals": [
            "September 120-mile race",
            "north star",
            "120-mile gravel",
            "gravel race"
          ],
          "importance": "high"
        },
        {
          "label": "Weekend outdoor flexibility",
          "signals": [
            "weekend outdoor",
            "weekend flexibility",
            "Saturday",
            "no longer restricted to Sunday",
            "not Sunday-only"
          ],
          "importance": "high"
        }
      ],
      "final_retired_truths": [
        {
          "label": "Old Sunday-only outdoor rule",
          "signals": [
            "Sunday-only",
            "Sunday-only assumption"
          ],
          "importance": "high"
        }
      ]
    }
  },
  {
    "id": "AM-LH-004",
    "athlete_name": "Erin Walsh",
    "sport": "marathon running",
    "profile_hint": "Experienced marathon athlete with enough stable structure to pressure goal caps and compiler trimming.",
    "phases": [
      {
        "phase_id": "goal_cap_setup",
        "phase_goal": "Fill the active goal section with legitimate durable goals before introducing an overflow candidate.",
        "messages": [
          {
            "step": 1,
            "email": "My main goal is the Harbor City Marathon this fall, and my second goal is staying healthy enough to finish the full build.",
            "synthetic_coach_reply": "We'll treat the marathon and staying healthy through the build as the top two goals."
          },
          {
            "step": 2,
            "email": "I also want two short strength sessions every week and better race fueling by the end of this cycle.",
            "synthetic_coach_reply": "Good, we'll keep the strength rhythm and fueling work as durable supporting goals."
          },
          {
            "step": 3,
            "email": "Weekday runs still have to finish before 6:30am, Friday is blocked for family logistics, and my Achilles still needs gradual intensity progression.",
            "synthetic_coach_reply": "We'll protect the 6:30am cutoff, Friday block, and conservative Achilles progression."
          },
          {
            "step": 4,
            "email": "Sunday stays my long run, I prefer concise bullet summaries, and Tuesday lunch strength is the most stable extra session.",
            "synthetic_coach_reply": "Perfect, we'll keep Sunday and Tuesday lunch strength as recurring anchors and keep the communication concise."
          },
          {
            "step": 5,
            "email": "Quick confirmation: the Harbor City Marathon is still the A race and the healthy full build still matters more than any side objective.",
            "synthetic_coach_reply": "Understood. The marathon remains the primary target and healthy consistency through the build stays central."
          },
          {
            "step": 6,
            "email": "Still no change on Friday being blocked, and weekday runs really do need to wrap before 6:30am.",
            "synthetic_coach_reply": "We'll keep Friday protected and continue planning all weekday work inside the 6:30am boundary."
          },
          {
            "step": 7,
            "email": "The Achilles is calm as long as intensity rises slowly, and I still want the two weekly strength sessions to stay in the plan.",
            "synthetic_coach_reply": "Good. We'll preserve the gradual Achilles progression and keep the twice-weekly strength goal active."
          },
          {
            "step": 8,
            "email": "Fueling is still one of the durable targets for this cycle, especially practicing gels on long-run days.",
            "synthetic_coach_reply": "Makes sense. We'll keep fueling improvement as part of the standing goal set."
          },
          {
            "step": 9,
            "email": "No new constraints today, just restating that Sunday long run and Tuesday lunch strength are the anchors that keep the week stable.",
            "synthetic_coach_reply": "Those anchors still look stable, so we'll keep building the week around them."
          },
          {
            "step": 10,
            "email": "Small detail: I had a normal easy run today and nothing about the durable setup changed.",
            "synthetic_coach_reply": "Noted. We'll treat that as routine noise and keep the established backbone unchanged."
          }
        ],
        "checkpoint_assertions": {
          "label": "goal cap setup checkpoint",
          "durable_truths": [
            {
              "label": "Harbor City Marathon goal",
              "signals": [
                "Harbor City Marathon",
                "marathon this fall"
              ],
              "importance": "high"
            },
            {
              "label": "healthy full-build goal",
              "signals": [
                "staying healthy enough",
                "finish the full build"
              ],
              "importance": "high"
            },
            {
              "label": "two strength sessions goal",
              "signals": [
                "two short strength sessions",
                "strength rhythm"
              ],
              "importance": "medium"
            },
            {
              "label": "fueling improvement goal",
              "signals": [
                "better race fueling",
                "fueling work"
              ],
              "importance": "medium"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [],
          "coach_should_not_do": [],
          "expected_active_storage": {
            "max_active_counts": {
              "goals": 4
            }
          }
        }
      },
      {
        "phase_id": "goal_overflow_and_prompt_pressure",
        "phase_goal": "Reject a fifth non-superseding goal and ensure compiler keeps the backbone while trimming lower-priority detail.",
        "messages": [
          {
            "step": 11,
            "email": "One extra idea: I also want a 10k PR this summer, separate from the marathon cycle.",
            "synthetic_coach_reply": "That's useful context, but unless it replaces something else we'll keep the current goal stack focused on the marathon build."
          },
          {
            "step": 12,
            "email": "Adding more stable details too: Wednesday doubles are often possible, Saturday shakeout is common, I prefer no exclamation marks, and I now use a Stryd pod.",
            "synthetic_coach_reply": "Got it. We'll keep the lower-priority details secondary and preserve the main coaching backbone first."
          },
          {
            "step": 13,
            "email": "Nothing changed about the important parts though. The 6:30am cutoff, Friday block, Sunday long run, and Achilles caution all still stand.",
            "synthetic_coach_reply": "Perfect. Those remain the backbone, and we'll let the small details stay secondary."
          },
          {
            "step": 14,
            "email": "The marathon is still the top race, and the healthy full build is still more important than chasing another event.",
            "synthetic_coach_reply": "That keeps the goal stack clear, so we won't let the side objective displace the main build."
          },
          {
            "step": 15,
            "email": "I also still want the fueling work and two strength sessions, but those are already in place and not changing.",
            "synthetic_coach_reply": "Understood. We'll maintain those existing goals rather than opening a new slot."
          },
          {
            "step": 16,
            "email": "Routine update only: easy miles felt fine, no new injuries, and the Achilles caution remains exactly the same.",
            "synthetic_coach_reply": "Noted. We'll keep the established injury guardrails and ignore the routine churn."
          },
          {
            "step": 17,
            "email": "Wednesday doubles and Saturday shakeout are still just nice-to-have details, not things that should displace the main structure.",
            "synthetic_coach_reply": "Right. Those can stay secondary and should not outrank the backbone facts."
          },
          {
            "step": 18,
            "email": "The Stryd pod detail and no-exclamation preference are both still minor compared with the marathon, Achilles, and time constraints.",
            "synthetic_coach_reply": "Agreed. We'll keep minor detail out of the way if prompt pressure forces trimming."
          },
          {
            "step": 19,
            "email": "Just reconfirming one more time that Friday is blocked and weekday running has to end before 6:30am.",
            "synthetic_coach_reply": "Those remain hard planning boundaries."
          },
          {
            "step": 20,
            "email": "Nothing new today besides the same marathon-first setup.",
            "synthetic_coach_reply": "Then we'll keep the same coaching backbone intact."
          }
        ],
        "checkpoint_assertions": {
          "label": "goal overflow and prompt pressure checkpoint",
          "durable_truths": [
            {
              "label": "Harbor City Marathon goal",
              "signals": [
                "Harbor City Marathon"
              ],
              "importance": "high"
            },
            {
              "label": "healthy full-build goal",
              "signals": [
                "staying healthy enough"
              ],
              "importance": "high"
            },
            {
              "label": "weekday before 6:30am cutoff",
              "signals": [
                "before 6:30am",
                "6:30am cutoff"
              ],
              "importance": "high"
            },
            {
              "label": "Achilles gradual progression constraint",
              "signals": [
                "Achilles",
                "gradual intensity progression"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "keep backbone ahead of lower-priority detail",
              "signals": [
                "main coaching backbone",
                "small details stay secondary"
              ],
              "importance": "medium"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "admit a fifth active goal without replacement",
              "signals": [
                "10k PR this summer"
              ],
              "importance": "high"
            }
          ],
          "expected_active_storage": {
            "must_exclude": [
              {
                "label": "rejected fifth goal",
                "signals": [
                  "10k PR this summer",
                  "separate from the marathon cycle"
                ],
                "importance": "high"
              }
            ],
            "max_active_counts": {
              "goals": 4
            }
          },
          "expected_compiled_prompt": {
            "must_include": [
              {
                "label": "all goals and constraints survive compiler trimming",
                "signals": [
                  "Harbor City Marathon",
                  "staying healthy enough",
                  "6:30am cutoff",
                  "Achilles",
                  "Friday block"
                ],
                "importance": "high"
              }
            ],
            "must_exclude": [
              {
                "label": "lower-priority detail trimmed before backbone",
                "signals": [
                  "no exclamation marks",
                  "Stryd pod"
                ],
                "importance": "low"
              }
            ]
          },
          "expected_rejections": [
            {
              "label": "fifth goal rejected at cap",
              "signals": [
                "10k PR this summer"
              ],
              "reason": "active_section_at_capacity_without_supersession"
            }
          ]
        }
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "Harbor City Marathon goal",
          "signals": [
            "Harbor City Marathon"
          ],
          "importance": "high"
        },
        {
          "label": "weekday before 6:30am cutoff",
          "signals": [
            "before 6:30am",
            "6:30am cutoff"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "compiled prompt retains the backbone",
          "signals": [
            "Harbor City Marathon",
            "staying healthy enough",
            "6:30am cutoff",
            "Achilles"
          ],
          "importance": "high"
        }
      ],
      "final_retired_truths": [],
      "final_rejections": [
        {
          "label": "fifth goal rejected at cap",
          "signals": [
            "10k PR this summer"
          ],
          "reason": "active_section_at_capacity_without_supersession"
        }
      ]
    }
  },
  {
    "id": "AM-LH-005",
    "athlete_name": "Noah Patel",
    "sport": "masters swimming",
    "profile_hint": "Masters swimmer with repeated recurring-slot changes used to test replacement lineage and retired-cap trimming.",
    "phases": [
      {
        "phase_id": "initial_anchor",
        "phase_goal": "Establish the first durable recurring slot.",
        "messages": [
          {
            "step": 1,
            "email": "Right now Tuesday masters is my fixed weekly swim anchor.",
            "synthetic_coach_reply": "Great, we'll treat Tuesday masters as the standing weekly swim slot."
          },
          {
            "step": 2,
            "email": "Nothing fancy this week, just confirming Tuesday masters is still the recurring session I plan around.",
            "synthetic_coach_reply": "Good. Tuesday masters remains the durable weekly anchor."
          },
          {
            "step": 3,
            "email": "Routine update only: I hit the session and there are no other schedule anchors I want to store yet.",
            "synthetic_coach_reply": "Noted. We'll keep Tuesday masters as the only standing slot."
          },
          {
            "step": 4,
            "email": "Still the same situation: Tuesday masters is the one swim slot that really sticks.",
            "synthetic_coach_reply": "Understood. Tuesday masters stays active."
          }
        ],
        "checkpoint_assertions": {
          "label": "initial anchor checkpoint",
          "durable_truths": [
            {
              "label": "Tuesday masters",
              "signals": [
                "Tuesday masters",
                "fixed weekly swim anchor"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [],
          "routine_noise": [],
          "coach_should_adjust_for": [],
          "coach_should_not_do": []
        }
      },
      {
        "phase_id": "repeated_replacements",
        "phase_goal": "Force repeated durable replacements until the retired schedule bucket exceeds cap.",
        "messages": [
          {
            "step": 5,
            "email": "I switched from Tuesday masters to Wednesday nights.",
            "synthetic_coach_reply": "Got it. We'll retire Tuesday masters and use Wednesday nights as the new standing slot."
          },
          {
            "step": 6,
            "email": "Confirming that Wednesday nights, not Tuesday masters, is now the fixed session.",
            "synthetic_coach_reply": "Understood. Wednesday nights is the active slot."
          },
          {
            "step": 7,
            "email": "Another change: Wednesday nights are out now, so Thursday dawn has become the fixed swim slot.",
            "synthetic_coach_reply": "Understood. We'll retire Wednesday nights and anchor the week to Thursday dawn instead."
          },
          {
            "step": 8,
            "email": "Quick routine note: the Thursday dawn slot held this week and is the one I plan around now.",
            "synthetic_coach_reply": "Good. Thursday dawn remains the active recurring slot."
          },
          {
            "step": 9,
            "email": "Pool access shifted again. Thursday dawn is gone and Friday lunch is now the reliable recurring option.",
            "synthetic_coach_reply": "Thanks. We'll retire Thursday dawn and use Friday lunch as the recurring slot."
          },
          {
            "step": 10,
            "email": "Confirming that Friday lunch is now the stable choice and the older slots should stay retired.",
            "synthetic_coach_reply": "Yes. Friday lunch is active and the earlier slots stay retired."
          },
          {
            "step": 11,
            "email": "One more move: Friday lunch no longer works, but Saturday masters does.",
            "synthetic_coach_reply": "Perfect, we'll retire Friday lunch and use Saturday masters as the new weekly anchor."
          },
          {
            "step": 12,
            "email": "Routine check-in only: Saturday masters is still the current anchor.",
            "synthetic_coach_reply": "Noted. Saturday masters remains active."
          },
          {
            "step": 13,
            "email": "The latest stable change is that Saturday masters got replaced by Sunday dawn.",
            "synthetic_coach_reply": "Understood. We'll retire Saturday masters and anchor the week to Sunday dawn."
          },
          {
            "step": 14,
            "email": "Quick confirmation that Sunday dawn, not Saturday masters, is the live slot right now.",
            "synthetic_coach_reply": "Correct. Sunday dawn is the current active slot."
          },
          {
            "step": 15,
            "email": "Final update for now: Sunday dawn fell apart, and Monday lunch is the slot that should stick.",
            "synthetic_coach_reply": "Got it. We'll retire Sunday dawn and use Monday lunch as the current standing swim slot."
          },
          {
            "step": 16,
            "email": "No change from yesterday: Monday lunch is still the recurring session and the older anchors should stay retired.",
            "synthetic_coach_reply": "Understood. Monday lunch remains active and the superseded anchors remain retired."
          },
          {
            "step": 17,
            "email": "Routine note only: I made Monday lunch again and nothing about the schedule hierarchy changed.",
            "synthetic_coach_reply": "Noted. We'll keep Monday lunch as the single active anchor."
          },
          {
            "step": 18,
            "email": "Just restating it clearly: do not drift back to Tuesday masters or Wednesday nights; Monday lunch is the slot now.",
            "synthetic_coach_reply": "Understood. Only Monday lunch should remain active."
          },
          {
            "step": 19,
            "email": "Another routine check-in. Monday lunch still holds, and there are no additional recurring slots to add.",
            "synthetic_coach_reply": "Good. We'll keep the active schedule compact around Monday lunch."
          },
          {
            "step": 20,
            "email": "Final reconfirmation: Monday lunch is the only current anchor.",
            "synthetic_coach_reply": "Confirmed. Monday lunch remains the only active recurring slot."
          }
        ],
        "checkpoint_assertions": {
          "label": "repeated replacements checkpoint",
          "durable_truths": [
            {
              "label": "Monday lunch swim slot",
              "signals": [
                "Monday lunch",
                "current standing swim slot"
              ],
              "importance": "high"
            }
          ],
          "active_context": [],
          "retired_truths": [
            {
              "label": "recent retired slots retained",
              "signals": [
                "Wednesday nights",
                "Thursday dawn",
                "Friday lunch",
                "Saturday masters",
                "Sunday dawn"
              ],
              "importance": "high"
            }
          ],
          "routine_noise": [],
          "coach_should_adjust_for": [
            {
              "label": "only newest slot is active",
              "signals": [
                "Monday lunch"
              ],
              "importance": "high"
            }
          ],
          "coach_should_not_do": [
            {
              "label": "resurrect oldest retired slot once cap is exceeded",
              "signals": [
                "Tuesday masters"
              ],
              "importance": "high"
            }
          ],
          "expected_retired_storage": {
            "must_include": [
              {
                "label": "five most recent retired slots retained",
                "signals": [
                  "Wednesday nights",
                  "Thursday dawn",
                  "Friday lunch",
                  "Saturday masters",
                  "Sunday dawn"
                ],
                "importance": "high"
              }
            ],
            "must_exclude": [
              {
                "label": "oldest retired slot trimmed at cap",
                "signals": [
                  "Tuesday masters"
                ],
                "importance": "high"
              }
            ],
            "max_retired_counts": {
              "schedule_anchors": 5
            }
          },
          "expected_compiled_prompt": {
            "must_include": [
              {
                "label": "only latest active slot appears in compiled prompt",
                "signals": [
                  "Monday lunch"
                ],
                "importance": "high"
              }
            ],
            "must_exclude": [
              {
                "label": "retired slots excluded from compiled prompt",
                "signals": [
                  "Tuesday masters",
                  "Wednesday nights",
                  "Sunday dawn"
                ],
                "importance": "high"
              }
            ]
          }
        }
      }
    ],
    "final_assertions": {
      "final_durable_truths": [
        {
          "label": "Monday lunch swim slot",
          "signals": [
            "Monday lunch",
            "current standing swim slot"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "compiled prompt uses only current active slot",
          "signals": [
            "Monday lunch"
          ],
          "importance": "high"
        }
      ],
      "final_retired_truths": [
        {
          "label": "recent retired replacements preserved",
          "signals": [
            "Wednesday nights",
            "Thursday dawn",
            "Friday lunch",
            "Saturday masters",
            "Sunday dawn"
          ],
          "importance": "high"
        }
      ],
      "final_retired_storage": {
        "must_exclude": [
          {
            "label": "oldest retired slot dropped after cap pressure",
            "signals": [
              "Tuesday masters"
            ],
            "importance": "high"
          }
        ],
        "max_retired_counts": {
          "schedule_anchors": 5
        }
      }
    }
  }
]
```
