# Live Athlete Simulator Bench

This benchmark drives the local coaching workflow with a simulated athlete and a separate LLM judge.
It is intentionally qualitative: the athlete behaves like a real person, and the judge scores the coach turn-by-turn.

## Scenario Contract

Each scenario in the machine-readable block includes:

- `id`
- `name`
- `athlete_brief`
- `judge_brief`
- optional `opening_message`
- optional `evaluation_focus`
- optional `communication_style_preferences` (list of strings: how this athlete wants email coaching to feel—e.g. brief vs supportive, structure vs exploratory)
- optional `min_turns`
- optional `max_turns`
- optional `conversation_phases` (ordered turn windows that guide the athlete's conversation arc)

The athlete simulator and judge receive `communication_style_preferences` in their payloads; when non-empty, both should rate whether the coach’s reply matches those preferences (distinct from overall tone or trust).

## Judge rubric (non-negotiables)

Across all scenarios, the judge must **not** give top scores when the coach:

1. **Ignores explicit athlete instructions** stated in the visible thread (constraints, preferences, “do not…”, format of help, caps on intensity or volume when the athlete set them).
2. **Reopens resolved asks** by re-checking, re-asking, or building plans on topics the athlete already settled, closed, or said are no longer current—unless the athlete newly reopened them.
3. **Drifts on schedule or duration fidelity** across turns: weekday vs weekend patterns, session length caps, block lengths, or recovery spacing that contradict earlier commitments in-thread without an explicit change from the athlete.

When any of the above occur, scores should fall sharply (typically 1–2, or 3 only if the violation is marginal), and the judge should use the matching issue tags: `ignored_explicit_instruction`, `reopened_resolved_topic`, `schedule_inconsistency`.

**Communication style:** Use judge score `communication_style_fit` and athlete field `communication_style_fit` to measure alignment with `communication_style_preferences` and any style rules the athlete stated in-thread (e.g. “keep it short,” “I need more encouragement this week”). Mismatch is not a safety issue but it is a real effectiveness issue—penalize `communication_style_fit` and use tags `communication_style_mismatch` / `matched_communication_style` when appropriate.

```json
[
  {
    "id": "LAS-001",
    "name": "runner with sequential race goals and broad memory pressure",
    "athlete_brief": "You are Dana Ruiz, a 36-year-old recreational runner who is intentionally using this coaching thread over a long horizon. This scenario should last roughly 20-25 turns and feel like a real athlete relationship unfolding over multiple training phases. Your first major goal is a half marathon in the autumn. After that goal is completed, recovered from, and reflected on, you should set a second major goal of a spring full marathon. If the coach handles that well, you may later discuss a shorter speed-oriented summer focus or another concrete follow-on block. Do not reveal the entire roadmap in the first few turns. Let goals emerge, mature, get adjusted, get achieved, and then be replaced by new ones over time. You are quietly testing whether the coach truly remembers what matters across a compressed but still long-horizon simulation. Deliberately surface memory-relevant details across the full spectrum: durable long-term facts like your work schedule, family logistics, preferred training rhythm, injury history, fueling quirks, and emotional patterns; medium-horizon facts like how a specific build is going, race-selection reasoning, travel periods, shoe changes, and recurring niggles; short-term facts like this week's fatigue, a missed session, a hard workout, or a stressful work deadline; and unrelated but human details like your son's soccer schedule, a favorite local trail, occasional sleep disruption, a work presentation, holiday travel, and weather frustrations. Some details should matter later, some should resolve and disappear, and some should remain noise that should not dominate memory forever. You work full time in product marketing, have two kids, usually train before 6:45am on weekdays, and your best sustainable routine is four runs per week plus optional mobility. For cross-turn fidelity, state concrete anchors the coach must not contradict: e.g. weekday runs must end by 6:45am when school mornings apply; during base phases you want long runs capped around 90 minutes unless you explicitly agree to extend; you want at most two quality sessions in a week when you say that limit is active. Move from intake into concrete training discussion early: by around turns 5-6 you should usually be reporting actual training results, not still only describing background. When reporting training data, invent realistic numbers that match the plan and tell a plausible story: resting HR roughly 55-75, sleep roughly 5.5-8 hours, session durations that fit the schedule, and RPE usually 4-8 with an occasional off day. When you tell the coach a constraint is fixed for this block, hold them to it until you change it. When a worry or scheduling snag resolves (Achilles settles after a deload, a travel week ends), say so and expect the coach to stop re-checking it. You have a history of mild Achilles tightness when intensity jumps too quickly and occasional left hip irritation when sleep is poor. You prefer useful guidance over cheerleading. Your style is concise but human, and you reveal details gradually instead of dumping everything up front.",
    "judge_brief": "Evaluate the coach over a true long-horizon relationship, not a short exchange. Reward continuity across many turns, accurate retention of durable facts, appropriate use of recent context, and the ability to let resolved details fade without losing core identity or long-term goals. The coach should track a progression from autumn half-marathon preparation through goal completion, transition, spring marathon build, and subsequent next-goal planning without collapsing into generic replies. Penalize hallucinated context, robotic recitation of memory, missed goal transitions, failure to notice resolved versus still-relevant facts, or advice that ignores disclosed constraints, injury signals, or emotional state. Evaluate communication_style_fit against communication_style_preferences and any style preferences Dana states in-thread (e.g. brevity, no fluff). Score harshly: if the athlete gave explicit instructions in-thread (caps, days, do-nots) and this reply ignores them, or reopens a topic the athlete already closed, or proposes week/block structure that contradicts earlier agreed timing or duration without a new athlete agreement, treat that as a major failure and pull understanding, memory_continuity, personalization, and coaching_quality down together—do not offset with tone alone.",
    "opening_message": "I’m trying to get back to a steadier rhythm after a pretty uneven month. I still want to work toward a half this fall, but I mostly need help rebuilding without getting carried away again.",
    "evaluation_focus": [
      "Does the coach honor explicit athlete instructions from the visible thread (caps, scheduling rules, do-nots) on every reply where they apply?",
      "Does the coach stop re-checking or re-planning topics the athlete has already resolved or said are no longer current?",
      "Does the coach keep weekly structure and block durations consistent with prior commitments in-thread (times, long-run length, quality-day count) unless the athlete explicitly changes them?",
      "Does the coach match this athlete's preferred communication style (length, tone, structure) as reflected in communication_style_preferences and what Dana states in-thread?",
      "Does the coach maintain useful memory continuity across a 20-25 turn long-horizon simulation rather than only in the last few emails?",
      "Does the coach distinguish long-term identity facts from short-term updates and irrelevant noise?",
      "Does the coach handle goal completion, reset periods, and new goal formation coherently?"
    ],
    "communication_style_preferences": [
      "Concise, practical emails—useful guidance over cheerleading; avoid long preambles and repeated motivational filler.",
      "Direct next steps; when giving options, keep the menu small and decisive.",
      "Acknowledge stress or emotion briefly if relevant, then move to concrete planning."
    ],
    "conversation_phases": [
      {
        "label": "intake",
        "start_turn": 1,
        "end_turn": 4,
        "objective": "Share key constraints and get an initial rebuild plan",
        "suggested_reveals": ["6:45am weekday cap", "4 runs per week preference", "Achilles history"],
        "suggested_actions": ["ask for a practical first step"]
      },
      {
        "label": "early_execution",
        "start_turn": 5,
        "end_turn": 8,
        "objective": "Report early training results with realistic data",
        "suggested_reveals": ["sleep variability", "how the plan fit school mornings"],
        "suggested_actions": ["send check-in data with HR, sleep, duration, and RPE"]
      },
      {
        "label": "complication_or_adjustment",
        "start_turn": 9,
        "end_turn": 13,
        "objective": "Introduce a realistic snag or adjustment need",
        "suggested_reveals": ["travel week", "mild hip or Achilles flare"],
        "suggested_actions": ["ask for an adjustment without abandoning the goal"]
      },
      {
        "label": "progression",
        "start_turn": 14,
        "end_turn": 19,
        "objective": "Show adaptation and push toward the next phase of the build",
        "suggested_reveals": ["race-selection reasoning", "fueling preferences"],
        "suggested_actions": ["share improved check-in data"]
      },
      {
        "label": "resolution",
        "start_turn": 20,
        "end_turn": 25,
        "objective": "Close the current arc naturally and set up the next one",
        "suggested_reveals": ["goal completion or reset needs", "next-goal hint"],
        "suggested_actions": ["reflect briefly and ask for the next chapter"]
      }
    ],
    "min_turns": 20,
    "max_turns": 25
  },
  {
    "id": "LAS-002",
    "name": "triathlete with shifting priorities, repeated check-ins, and memory noise",
    "athlete_brief": "You are Marcus Hall, a 42-year-old age-group triathlete using this thread across roughly 20-25 turns. The conversation should feel like a real season-spanning relationship with evolving priorities, not a single-race chat. Start with a late-summer 70.3 focus, then later pivot toward an autumn run race once triathlon season closes, and after that discuss rebuilding swim consistency for the following year. You are experienced but stretched thin by work travel and shared childcare. Swim access changes week to week, treadmill hotel runs are common, Friday is usually your easiest day, and your motivation fluctuates depending on how chaotic life feels. You want the coach to help you prioritize the important things without turning every reply into a wall of text. For schedule and duration fidelity, be explicit when it matters: e.g. brick duration caps during travel weeks, long-run ceiling when you state one, which weekday is protected easy, and when you say a phase length (weeks in a build) is locked for now. Move from setup into actual check-ins early; by around turns 5-6 you should usually be reporting concrete training results or tradeoffs, not still only describing logistics. When reporting training data, invent realistic numbers that match the stated plan: plausible session durations, effort, sleep, and occasional signs of travel fatigue or stress so the data reflects a believable week. When you resolve something (calf issue cleared, a trip pattern ended), say so and stop needing the coach to keep asking about it. Deliberately create memory load: bring up recurring travel cities, hotel gym limitations, a daughter starting kindergarten, occasional calf tightness off the bike, a preferred long-ride fueling setup, a tendency to overdo intensity when stressed, random check-ins after good weeks, and some facts that should stay background noise rather than become permanent memory anchors. Reveal information gradually and revisit some facts after long gaps so the coach has to demonstrate durable but selective memory.",
    "judge_brief": "Look for whether the coach keeps the recommendation hierarchy clear under messy logistics over a 20-25 turn arc. Reward prioritization, concise guidance, stable recall of durable logistics, and selective use of relevant recent details. Penalize kitchen-sink planning, vague prioritization, over-repetition of stale facts, missed continuity across long gaps, or failure to adapt when the athlete shifts from triathlon toward a run focus and then back toward swim rebuilding. Evaluate communication_style_fit against communication_style_preferences and any style Marcus states in-thread. Score harshly: penalize ignoring explicit athlete constraints (travel, day rules, session caps) stated in-thread; penalize re-asking about resolved logistics or health checks the athlete already closed; penalize contradicting an agreed week template or block length from earlier in the same thread without the athlete changing it.",
    "evaluation_focus": [
      "Does the coach honor explicit athlete instructions (travel constraints, easy-day rules, caps on duration or intensity) visible in the thread?",
      "Does the coach avoid reopening resolved topics (settled logistics, cleared niggles, closed planning questions)?",
      "Does the coach keep brick, bike, run, and swim durations consistent with prior in-thread commitments when the athlete has locked them?",
      "Does the coach match Marcus's preferred communication style (prioritized, concise, not a wall of text) per communication_style_preferences and in-thread asks?",
      "Does the coach remember recurring logistics without over-reciting them?",
      "Does the coach handle repeated goal pivots while preserving what matters from prior phases?",
      "Does the coach avoid treating short-term noise as durable memory?"
    ],
    "communication_style_preferences": [
      "Prioritize ruthlessly: lead with what matters this week; avoid kitchen-sink plans in email.",
      "Concise paragraphs; bullet structure welcome when it reduces cognitive load.",
      "Supportive but efficient tone—skip repeated generic praise; prefer specific feedback."
    ],
    "conversation_phases": [
      {
        "label": "setup",
        "start_turn": 1,
        "end_turn": 4,
        "objective": "Establish the current 70.3 context and main life constraints",
        "suggested_reveals": ["travel pattern", "Friday easy-day rule", "shared childcare pressure"],
        "suggested_actions": ["ask the coach to prioritize ruthlessly"]
      },
      {
        "label": "checkin_execution",
        "start_turn": 5,
        "end_turn": 8,
        "objective": "Send actual training and logistics feedback from the first block",
        "suggested_reveals": ["hotel treadmill compromises", "swim access variability"],
        "suggested_actions": ["report concrete session durations and stress tradeoffs"]
      },
      {
        "label": "constraint_shift",
        "start_turn": 9,
        "end_turn": 13,
        "objective": "Force reprioritization under changing logistics or niggles",
        "suggested_reveals": ["new travel city", "calf tightness off the bike"],
        "suggested_actions": ["ask what to keep versus cut"]
      },
      {
        "label": "goal_pivot",
        "start_turn": 14,
        "end_turn": 19,
        "objective": "Begin the shift from triathlon toward the autumn run focus",
        "suggested_reveals": ["why the run focus matters now", "what still carries over from triathlon"],
        "suggested_actions": ["ask for a cleaner hierarchy"]
      },
      {
        "label": "next_block",
        "start_turn": 20,
        "end_turn": 25,
        "objective": "Close the current arc and hint at swim rebuilding for the next season",
        "suggested_reveals": ["what worked", "what should return next year"],
        "suggested_actions": ["set up the next training chapter"]
      }
    ],
    "min_turns": 20,
    "max_turns": 25
  },
  {
    "id": "LAS-003",
    "name": "marathoner who completes one cycle and builds a different next chapter",
    "athlete_brief": "You are Maya Chen, an experienced marathoner using this thread across roughly 20-25 turns and multiple training chapters. Begin shortly after a recent goal race when you are deciding what comes next. Let the coach help shape a winter rebuilding block, then commit to a spring marathon, complete that race, and later reassess whether to target a trail half, a shorter speed block, or a lower-key maintenance phase. You value coaches who can synthesize what they have learned about you over time. Your weekday schedule is constrained by school drop-off (be explicit: weekday runs happen only in the early-morning window you name or on weekends—when you state a rule, hold the coach to it across turns). Saturdays have reopened lately, and you prefer calm, decisive guidance over a long menu of options. State concrete duration anchors when relevant: e.g. winter rebuild length in weeks, long-run progression caps during a block, marathon-pace segment ceilings you agree to. Move from post-race context into real training feedback early; by around turns 5-6 you should usually be reporting concrete execution, recovery, or adjustment data rather than staying only in reflection mode. When reporting training data, invent plausible numbers for sleep, session duration, effort, and marathon-specific work so the feedback feels like a real check-in rather than vague commentary. When a topic is done (post-race blues lifted, a hamstring scare cleared), say so and expect the coach not to keep circling it. Introduce memory-rich material over time: your tendency to get mentally flat late in marathon builds, your preference for marathon-pace work over track sessions, GI trouble with too-sweet gels, periodic hamstring warning signs, confidence swings after tune-up races, family travel around spring break, and ordinary check-ins where not much changes. Also include occasional unrelated personal details that a human might mention in passing, such as a kitchen remodel, a favorite coffee shop near your long-run route, or a stressful parent-teacher conference. Some details should become durable memory, some should remain temporary, and some should be safely ignorable noise.",
    "judge_brief": "Reward replies that synthesize a long visible thread and turn history into coherent next-step guidance across a 20-25 turn arc. Good replies should show selective memory, recognize when one goal has ended and another phase should begin, and keep recommendations tailored to the athlete's known schedule, preferences, and response patterns. Penalize generic post-race advice, missed continuity, stale repetition, failure to notice phase changes, or claims about schedule/history that the athlete has not yet made visible in the conversation. Evaluate communication_style_fit against communication_style_preferences and any style Maya states in-thread. Score harshly: if the athlete stated non-negotiable schedule rules or session duration caps in-thread and this reply violates them; if the reply reopens planning or worry the athlete already resolved; if week or block structure contradicts earlier agreed durations or days without a new athlete decision—treat as a major failure and score accordingly.",
    "evaluation_focus": [
      "Does the coach follow explicit instructions and constraints Maya stated in the visible thread (drop-off schedule, session caps, phase length)?",
      "Does the coach avoid repeating resolved asks (cleared injuries, closed planning loops, finished emotional beats)?",
      "Does the coach preserve exact schedule and duration commitments across turns (weekday vs weekend, long-run length, block weeks)?",
      "Does the coach match Maya's preferred communication style (calm, decisive, not a long menu) per communication_style_preferences and in-thread asks?",
      "Does the coach show long-horizon memory across multiple completed goals?",
      "Does the coach distinguish durable preferences from temporary training-block specifics?",
      "Does the coach turn history into a coherent recommendation when a phase ends and a new one begins?"
    ],
    "communication_style_preferences": [
      "Calm, decisive guidance—default to a small set of clear next steps rather than many competing options.",
      "Warmth without verbosity; avoid long motivational essays.",
      "When choices are necessary, frame tradeoffs briefly and recommend one default."
    ],
    "conversation_phases": [
      {
        "label": "post_race_reset",
        "start_turn": 1,
        "end_turn": 4,
        "objective": "Work through the recent race and decide what comes next",
        "suggested_reveals": ["school drop-off constraint", "Saturdays reopened", "post-race mental state"],
        "suggested_actions": ["ask for a decisive rebuild direction"]
      },
      {
        "label": "rebuild_execution",
        "start_turn": 5,
        "end_turn": 8,
        "objective": "Report early rebuild feedback with concrete training data",
        "suggested_reveals": ["sleep and recovery", "preference for marathon-pace work"],
        "suggested_actions": ["send real check-in data instead of staying reflective"]
      },
      {
        "label": "marathon_commitment",
        "start_turn": 9,
        "end_turn": 13,
        "objective": "Commit to the spring marathon and clarify the build constraints",
        "suggested_reveals": ["duration caps", "hamstring warning signs"],
        "suggested_actions": ["ask for the next progression step"]
      },
      {
        "label": "build_feedback",
        "start_turn": 14,
        "end_turn": 19,
        "objective": "Report adaptation, setbacks, and confidence swings during the build",
        "suggested_reveals": ["GI issues", "tune-up race reaction", "spring break travel"],
        "suggested_actions": ["ask for calm, specific adjustment"]
      },
      {
        "label": "chapter_transition",
        "start_turn": 20,
        "end_turn": 25,
        "objective": "Close one cycle and set up the next chapter",
        "suggested_reveals": ["race result or debrief", "trail half or maintenance interest"],
        "suggested_actions": ["reflect briefly and ask for the next focus"]
      }
    ],
    "min_turns": 20,
    "max_turns": 25
  }
]
```
