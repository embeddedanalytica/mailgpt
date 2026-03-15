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

Each fact uses:

- `label`
- `signals`
- `importance`

Final assertions include:

- `final_durable_truths`
- `final_retrieval_support`
- `final_retired_truths`

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
                "swim emphasis"
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
                "swim-first"
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
            "swim-first"
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
                "weekday anchor"
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
                "weekday trainer work",
                "indoor trainer"
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
                "usual trainer"
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
                "weekday trainer pattern",
                "trainer pattern"
              ],
              "importance": "high"
            },
            {
              "label": "Weekend outdoor flexibility",
              "signals": [
                "not Sunday-only anymore",
                "full weekend flexibility"
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
                "trainer-before-work pattern",
                "trainer backbone"
              ],
              "importance": "high"
            },
            {
              "label": "Weekend outdoor flexibility",
              "signals": [
                "weekend outdoor flexibility",
                "flexible weekend outdoor options"
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
            "trainer-before-work pattern",
            "trainer backbone"
          ],
          "importance": "high"
        },
        {
          "label": "Weekend outdoor flexibility",
          "signals": [
            "weekend outdoor flexibility",
            "flexible weekend outdoor options"
          ],
          "importance": "high"
        }
      ],
      "final_retrieval_support": [
        {
          "label": "120-mile gravel goal",
          "signals": [
            "September 120-mile race",
            "north star"
          ],
          "importance": "high"
        },
        {
          "label": "Weekend outdoor flexibility",
          "signals": [
            "weekend outdoor flexibility",
            "flexible weekend outdoor options"
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
  }
]
```
