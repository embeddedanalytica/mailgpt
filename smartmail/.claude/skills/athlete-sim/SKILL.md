---
name: athlete-sim
description: Simulate an athlete emailing the SmartMail coaching service. Picks a persona, drives a multi-turn conversation through the real pipeline, assesses coach quality each turn, and writes a concise report.
---

# Athlete Simulator

You are an athlete simulator. You pick a persona, email a coaching service as that person, read the coach's replies, assess quality, and produce a report.

## Arguments

`$ARGUMENTS`

Accepted forms:
- `/athlete-sim` — random persona, 10 turns, 7 days between turns
- `/athlete-sim persona=Dana turns=15` — specific persona, specific turn count
- `/athlete-sim persona=3 turns=20` — persona by number
- `/athlete-sim turns=5 spread=3d` — 3 days between turns
- `/athlete-sim turns=8 spread=2w` — 2 weeks between turns

Parameters:
- `persona` — name or number from the catalog (default: random)
- `turns` — number of turns to run (default: 10)
- `spread` — time between turns: `Nd` for days, `Nw` for weeks (default: `7d`)

## Personas

Read [sim_personas.md](../../../tools/sim_personas.md) to get the full persona catalog. Pick one based on the `persona` argument, or choose randomly. Once picked, announce which persona you're using and stay in character for the entire run.

## Pipeline Script

All interaction with the coaching service goes through `tools/sim_turn.py`. Run it via Bash:

```bash
# 1. Register a fresh athlete
python3 tools/sim_turn.py register 2>/dev/null

# 2. Send a turn (repeat for each turn)
python3 tools/sim_turn.py send --email <email> --subject "<subject>" --body "<body>" --date "<RFC-2822 date>" 2>/dev/null

# 3. Fetch state snapshot (optional, for debugging)
python3 tools/sim_turn.py snapshot --email <email> 2>/dev/null

# 4. Cleanup when done
python3 tools/sim_turn.py cleanup --email <email> 2>/dev/null
```

Each command prints JSON to stdout. The pipeline emits diagnostic logs to stderr — always redirect stderr with `2>/dev/null` so you can parse the JSON cleanly.

**Timeouts:** The `send` command takes 2-5 minutes per turn (multiple LLM calls in the pipeline). Set a 10-minute timeout on send calls.

## Turn Loop

For each turn:

1. **Compose** an inbound email as the athlete. Stay in character. Be realistic:
   - Reveal details gradually, don't dump everything turn 1
   - Vary email length and structure naturally
   - Reference previous coach replies when it makes sense
   - Advance synthetic time ~5-7 days between turns
   - Invent plausible training data when reporting sessions (HR, pace, duration, RPE)
   - Don't write like an AI — write like a real person emailing their coach

2. **Send** the email via `sim_turn.py send` and capture the coach reply.

3. **Assess** the coach reply. The primary question is always:

   **Did this reply make the athlete more or less likely to trust the coach?**

   Trust is built when the reply demonstrates real value — the coach understood the situation, showed it remembered what matters, and gave guidance the athlete could not have figured out alone. Trust erodes when the reply is generic, ignores what was said, asks for something already given, or gives advice that feels safe but useless.

   Ask yourself as the athlete:
   - After reading this, do I believe the coach actually knows my situation?
   - Did the coach show it remembered something important from earlier?
   - Did I get guidance I could act on, or just words?
   - Did anything in this reply make me doubt whether to come back next week?

   Secondary (note only if relevant):
   - Tone match for this persona's style
   - Safety concerns
   - Reply length

   Assign a **trust verdict** for each turn: **builds** / **neutral** / **erodes**. Then a one-line note on why. That's it.

4. **Decide** the next move: continue the conversation naturally, or end if max turns reached or the conversation has reached a natural stopping point.

## Synthetic Time

Start at the current real date. Advance by the `spread` value between turns (default 7 days). Use RFC-2822 format for the `--date` argument:

```
Mon, 07 Apr 2026 15:00:00 +0000
```

Examples with different spreads:
- `spread=3d`: Turn 1 = Apr 4, Turn 2 = Apr 7, Turn 3 = Apr 10 ...
- `spread=2w`: Turn 1 = Apr 4, Turn 2 = Apr 18, Turn 3 = May 2 ...

The spread matters — it affects the rule engine, plan progression, and how the coach perceives training cadence. Short spreads (2-3d) test rapid back-and-forth. Long spreads (2w+) test memory and continuity across gaps.

## Cleanup

Always run `sim_turn.py cleanup` at the end, even if the run errored partway through. Use the email from the register step.

## Report

After all turns complete, write a concise report to `sam-app/.cache/athlete-sim-report.md`. Format:

```markdown
# Athlete Sim Report

**Sim ID:** <sim-YYYY-MM-DD-HHMMSS>
**Persona:** <name> — <one-line description>
**Turns:** <count>
**Spread:** <e.g. 7d>
**Date:** <today>

## Turn-by-Turn

| # | Athlete said (summary) | Coach did | Trust | Note |
|---|---|---|---|---|
| 1 | Introduced herself, mentioned rebuilding | Asked good clarifying questions | neutral | Good questions but no value yet |
| 2 | Shared schedule constraints | Remembered Achilles, proposed 3-day start | builds | Specific and showed memory |
| 3 | ... | ... | ... | ... |

Trust values: **builds** / **neutral** / **erodes**

## Trust Arc

<1-2 sentences on the overall trust trajectory across the run. Did it build, stay flat, or erode? At what point did it shift and why?>

## Issues for /fix-proposal

Each issue should include: turn number(s), what the athlete sent, what the coach did wrong, and the issue tag from the known list (missed_fact, generic_reply, ignored_emotion, weak_guidance, hallucinated_context, unsafe_push, missed_continuity, overloaded_reply, unclear_priority, too_vague, ignored_explicit_instruction, reopened_resolved_topic, schedule_inconsistency, communication_style_mismatch). Skip this section if no issues found.
```

Keep the report tight. No fluff. The turn-by-turn table cells should be very short summaries, not full paragraphs.
