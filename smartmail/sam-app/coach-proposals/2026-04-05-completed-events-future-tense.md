---
proposal_id: 2026-04-05-completed-events-future-tense
created_at: 2026-04-05T22:30:00Z
status: applied
applied_at: 2026-04-05T23:50:00Z
applied_summary: Added coaching_reasoning decision rule for past-tense completed sessions — debrief only, avoid redundant future-planning for the same event.
issue_tags: [missed_continuity, reopened_resolved_topic]
affected_files:
  - sam-app/email_service/skills/response_generation/prompt.py
  - sam-app/email_service/prompt_packs/coach_reply/v1/operational_rules.json
  - sam-app/email_service/skills/coaching_reasoning/
confidence: 3
estimated_cx_impact: 3
---

## Source
Sim: sim-2026-04-05-combined · Persona: Marcus — Anxious Beginner · Turn: 14

## Issue
The athlete had **already completed** the social run and reported how it went; the coach reply still framed a **weekend / social run plan as if it were upcoming**, reopening a resolved topic and eroding trust (“did you even read my email?”).

Athlete sent: “Social run went okay … used your script … 35 minutes … shins tired after but fine next morning … is tired different from bad?”

Coach replied: (paraphrased) Explained tired vs bad shins helpfully, but also included **weekend plan / social run with friend** language as if the athlete still needed permission or scheduling for that outing—**after** the athlete said it already happened.

## Diagnosis
The **latest inbound body is present** in `build_llm_reply_body` (`coaching_reply_rendering.py`), so the failure is not missing raw text—it is **reasoning/writing behavior**:
- **Coaching reasoning** may have produced a `content_plan` that still included “social run guidance” from an **earlier turn** or a **generic beginner template**, without a step that says **“if the athlete already reported the event, switch to debrief-only.”**
- **Response generation** may **merge** generic weekend advice with the answer to the shin question without **cross-checking tense** (past vs future) against the first paragraphs of the athlete message.

There is no **hard constraint** in the writer prompt pack that says: **Do not instruct or schedule events the athlete has already completed in this message.**

## Proposed change
1. **Response generation (surface text layer)**  
   In `operational_rules.json` / directive system prompt for coach reply: add a **short, high-priority rule**:  
   - **“If the athlete’s message describes a training session or event as already completed, do not reintroduce it as future or upcoming; respond in past/debrief form only.”**

2. **Coaching reasoning (strategy layer)**  
   When classifying beginner “social / group run” topics, add instruction: **scan the inbound for past tense / completed markers** (“we did”, “went okay”, “yesterday”) and set directive **`avoid`** entries for redundant future-planning about that same event.

3. **Optional lightweight signal**  
   If the pipeline already has **intent classification** or **extracted check-in** fields, pass a boolean `athlete_reports_completed_session: true` into the response brief so the writer can’t miss it—only if cheap to derive without brittle regex.

## Why this fixes it
Stops **duplicate planning** for events the athlete **already executed**, which is a specific, high-salience **continuity** failure mode for anxious, detail-reading users.

## Risks
- **Prompt size:** adding one tight operational rule is **small** (neutral to slightly additive); avoid duplicating long examples.
- **False positives:** don’t suppress *future* group runs if the athlete mentions both a past and future event—rule should say **match the specific event** described as completed.

## Verification
Suggested re-run: `/athlete-sim persona=Marcus turns=5` with a turn that only debriefs a **completed** group run and asks a narrow follow-up; expect **no** “next time you can join your friend” boilerplate unless the athlete asked about a **future** outing.
