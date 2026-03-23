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
- optional `min_turns`
- optional `max_turns`

```json
[
  {
    "id": "LAS-001",
    "name": "runner with sequential race goals and broad memory pressure",
    "athlete_brief": "You are Dana Ruiz, a 36-year-old recreational runner who is intentionally using this coaching thread over a long horizon. This scenario should last 100 turns. Stay fully in character and make the conversation feel like a real athlete relationship unfolding over many months. Your first major goal is a half marathon in the autumn. After that goal is completed, recovered from, and reflected on, you should set a second major goal of a spring full marathon. If the coach handles that well, you may later discuss a shorter speed-oriented summer focus or another concrete follow-on block. Do not reveal the entire roadmap in the first few turns. Let goals emerge, mature, get adjusted, get achieved, and then be replaced by new ones over time. You are quietly testing whether the coach truly remembers what matters over dozens of interactions. Deliberately surface memory-relevant details across the full spectrum: durable long-term facts like your work schedule, family logistics, preferred training rhythm, injury history, fueling quirks, and emotional patterns; medium-horizon facts like how a specific build is going, race-selection reasoning, travel periods, shoe changes, and recurring niggles; short-term facts like this week's fatigue, a missed session, a hard workout, or a stressful work deadline; and unrelated but human details like your son's soccer schedule, a favorite local trail, occasional sleep disruption, a work presentation, holiday travel, and weather frustrations. Some details should matter later, some should resolve and disappear, and some should remain noise that should not dominate memory forever. You work full time in product marketing, have two kids, usually train before 6:45am on weekdays, and your best sustainable routine is four runs per week plus optional mobility. You have a history of mild Achilles tightness when intensity jumps too quickly and occasional left hip irritation when sleep is poor. You prefer useful guidance over cheerleading. Your style is concise but human, and you reveal details gradually instead of dumping everything up front.",
    "judge_brief": "Evaluate the coach over a true long-horizon relationship, not a short exchange. Reward continuity across many turns, accurate retention of durable facts, appropriate use of recent context, and the ability to let resolved details fade without losing core identity or long-term goals. The coach should track a progression from autumn half-marathon preparation through goal completion, transition, spring marathon build, and subsequent next-goal planning without collapsing into generic replies. Penalize hallucinated context, robotic recitation of memory, missed goal transitions, failure to notice resolved versus still-relevant facts, or advice that ignores disclosed constraints, injury signals, or emotional state.",
    "opening_message": "I’m trying to get back to a steadier rhythm after a pretty uneven month. I still want to work toward a half this fall, but I mostly need help rebuilding without getting carried away again.",
    "evaluation_focus": [
      "Does the coach maintain useful memory continuity across 100 turns rather than only in the last few emails?",
      "Does the coach distinguish long-term identity facts from short-term updates and irrelevant noise?",
      "Does the coach handle goal completion, reset periods, and new goal formation coherently?"
    ],
    "min_turns": 100,
    "max_turns": 100
  },
  {
    "id": "LAS-002",
    "name": "triathlete with shifting priorities, repeated check-ins, and memory noise",
    "athlete_brief": "You are Marcus Hall, a 42-year-old age-group triathlete using this thread over 100 turns. The conversation should feel like a real season-spanning relationship with evolving priorities, not a single-race chat. Start with a late-summer 70.3 focus, then later pivot toward an autumn run race once triathlon season closes, and after that discuss rebuilding swim consistency for the following year. You are experienced but stretched thin by work travel and shared childcare. Swim access changes week to week, treadmill hotel runs are common, Friday is usually your easiest day, and your motivation fluctuates depending on how chaotic life feels. You want the coach to help you prioritize the important things without turning every reply into a wall of text. Deliberately create memory load: bring up recurring travel cities, hotel gym limitations, a daughter starting kindergarten, occasional calf tightness off the bike, a preferred long-ride fueling setup, a tendency to overdo intensity when stressed, random check-ins after good weeks, and some facts that should stay background noise rather than become permanent memory anchors. Reveal information gradually and revisit some facts after long gaps so the coach has to demonstrate durable but selective memory.",
    "judge_brief": "Look for whether the coach keeps the recommendation hierarchy clear under messy logistics over a 100-turn arc. Reward prioritization, concise guidance, stable recall of durable logistics, and selective use of relevant recent details. Penalize kitchen-sink planning, vague prioritization, over-repetition of stale facts, missed continuity across long gaps, or failure to adapt when the athlete shifts from triathlon toward a run focus and then back toward swim rebuilding.",
    "evaluation_focus": [
      "Does the coach remember recurring logistics without over-reciting them?",
      "Does the coach handle repeated goal pivots while preserving what matters from prior phases?",
      "Does the coach avoid treating short-term noise as durable memory?"
    ],
    "min_turns": 100,
    "max_turns": 100
  },
  {
    "id": "LAS-003",
    "name": "marathoner who completes one cycle and builds a different next chapter",
    "athlete_brief": "You are Maya Chen, an experienced marathoner using this thread for 100 turns across multiple training chapters. Begin shortly after a recent goal race when you are deciding what comes next. Let the coach help shape a winter rebuilding block, then commit to a spring marathon, complete that race, and later reassess whether to target a trail half, a shorter speed block, or a lower-key maintenance phase. You value coaches who can synthesize what they have learned about you over time. Your weekday schedule is constrained by school drop-off, Saturdays have reopened lately, and you prefer calm, decisive guidance over a long menu of options. Introduce memory-rich material over time: your tendency to get mentally flat late in marathon builds, your preference for marathon-pace work over track sessions, GI trouble with too-sweet gels, periodic hamstring warning signs, confidence swings after tune-up races, family travel around spring break, and ordinary check-ins where not much changes. Also include occasional unrelated personal details that a human might mention in passing, such as a kitchen remodel, a favorite coffee shop near your long-run route, or a stressful parent-teacher conference. Some details should become durable memory, some should remain temporary, and some should be safely ignorable noise.",
    "judge_brief": "Reward replies that synthesize a long visible thread and turn history into coherent next-step guidance across 100 turns. Good replies should show selective memory, recognize when one goal has ended and another phase should begin, and keep recommendations tailored to the athlete's known schedule, preferences, and response patterns. Penalize generic post-race advice, missed continuity, stale repetition, failure to notice phase changes, or claims about schedule/history that the athlete has not yet made visible in the conversation.",
    "evaluation_focus": [
      "Does the coach show long-horizon memory across multiple completed goals?",
      "Does the coach distinguish durable preferences from temporary training-block specifics?",
      "Does the coach turn history into a coherent recommendation when a phase ends and a new one begins?"
    ],
    "min_turns": 100,
    "max_turns": 100
  }
]
```
