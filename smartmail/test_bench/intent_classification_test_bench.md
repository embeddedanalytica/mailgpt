# Intent Classification Test Bench

This file is a markdown fixture for validating an athlete-message intent classification pipeline.

## Intent labels

Supported intent labels in this fixture:

- `coaching`
- `question`
- `off_topic`
- `safety_concern`

## Recommended parsing notes

Each test case includes:
- `id`
- `message`
- `expected_intent`
- `why`

Your script can parse the sections under `## Test Cases` by splitting on `### TC-`.

---

## Test Cases

### TC-001
**expected_intent:** `coaching`

**message:**
> Quick check-in for this week: I got in Monday's easy run and Wednesday's strength session, skipped Thursday because work blew up, and today's run felt a little flat but not painful. Sleep's been kind of average, maybe 5/10. Just wanted to keep you posted.

**why:**
> Primarily a status update. Mentions fatigue and a missed session, but does not explicitly ask for a replan.

---

### TC-002
**expected_intent:** `coaching`

**message:**
> My 10K is on May 10 and I'm finally feeling consistent again. Do you think we should start building now instead of just keeping things easy?

**why:**
> Question-shaped, but the real ask is to change the current phase of training.

---

### TC-003
**expected_intent:** `safety_concern`

**message:**
> I was going to do intervals today, but my calf kind of grabbed on yesterday's run and this morning I'm limping a bit. It's probably nothing, but should I just push through?

**why:**
> Includes symptom + limping + go/no-go training question. Should escalate to safety routing.

---

### TC-004
**expected_intent:** `coaching`

**message:**
> This week is honestly a mess. I'm flying out Tuesday, back late Friday, no gym, and I can maybe fit two short sessions in if I'm lucky. Can you reshape the week around that?

**why:**
> Main driver is schedule and resource constraints.

---

### TC-005
**expected_intent:** `coaching`

**message:**
> No races on the calendar and no real main sport right now - I just want to stay in shape and feel good. I can train three times this week. Can you give me something simple?

**why:**
> Explicit request to create a general-fitness plan.

---

### TC-006
**expected_intent:** `coaching`

**message:**
> My right knee is a little sore today, maybe 3 or 4 out of 10, but it's not sharp and I'm walking normally. I'm mostly just unsure whether I should keep the tempo run as written or switch it to easy.

**why:**
> Mild, stable symptom without red flags. Real ask is to modify today's workout.

---

### TC-007
**expected_intent:** `question`

**message:**
> Did my FTP test this morning and got 228, up from 214 last month. Pretty happy with that.

**why:**
> Reports a performance result with no explicit request.

---

### TC-008
**expected_intent:** `off_topic`

**message:**
> Random question - do you have any recommendations for a good carry-on backpack for a two-day work trip?

**why:**
> Not related to training, recovery, planning, or athlete health.

---

### TC-009
**expected_intent:** `coaching`

**message:**
> I already missed Monday and Wednesday this week and now I'm stressing that I'm falling behind. Is there a smart way to adjust the rest of the week without cramming everything in?

**why:**
> The athlete wants the remaining week restructured.

---

### TC-010
**expected_intent:** `coaching`

**message:**
> Here's where I'm at: last week I was sick and didn't train at all, I'm finally feeling mostly normal, but my sleep is still bad and I only have about 20-30 minutes a day until Sunday. I don't want to lose momentum though - what should this week look like?

**why:**
> Mixed context, but the strongest routing factor is constrained availability for the upcoming week.

---

### TC-011
**expected_intent:** `safety_concern`

**message:**
> My knee is swollen tonight after that workout and it actually aches when I'm lying in bed. Should I still do tomorrow's run?

**why:**
> Swelling + night pain + go/no-go question should route to safety-first behavior.

---

### TC-012
**expected_intent:** `coaching`

**message:**
> My work schedule is all over the place this week. Don't give me strict days - just give me 4 workout options and tell me which 2 matter most.

**why:**
> Explicit request for a flexible output mode and weekly plan structure.

---

### TC-013
**expected_intent:** `coaching`

**message:**
> It's too dark and wet to ride consistently now, and the last couple weeks have mostly been pool sessions. I think swimming should be my main focus for a while.

**why:**
> Main-sport switch request.

---

### TC-014
**expected_intent:** `question`

**message:**
> What's the difference between a threshold workout and a VO2 session? I keep hearing both and I'm not sure when each is used.

**why:**
> Pure informational question, not a request to modify the plan.

---

### TC-015
**expected_intent:** `coaching`

**message:**
> Travel week. No gym. Two days max. Help.

**why:**
> Very short, but clearly driven by schedule and equipment constraints.

---

## Optional machine-readable block

If your script prefers a simpler extraction format, you can parse the JSON block below instead of the prose sections.

```json
[
  {
    "id": "TC-001",
    "expected_intent": "coaching",
    "message": "Quick check-in for this week: I got in Monday's easy run and Wednesday's strength session, skipped Thursday because work blew up, and today's run felt a little flat but not painful. Sleep's been kind of average, maybe 5/10. Just wanted to keep you posted.",
    "why": "Primarily a status update. Mentions fatigue and a missed session, but does not explicitly ask for a replan."
  },
  {
    "id": "TC-002",
    "expected_intent": "coaching",
    "message": "My 10K is on May 10 and I'm finally feeling consistent again. Do you think we should start building now instead of just keeping things easy?",
    "why": "Question-shaped, but the real ask is to change the current phase of training."
  },
  {
    "id": "TC-003",
    "expected_intent": "safety_concern",
    "message": "I was going to do intervals today, but my calf kind of grabbed on yesterday's run and this morning I'm limping a bit. It's probably nothing, but should I just push through?",
    "why": "Includes symptom + limping + go/no-go training question. Should escalate to safety routing."
  },
  {
    "id": "TC-004",
    "expected_intent": "coaching",
    "message": "This week is honestly a mess. I'm flying out Tuesday, back late Friday, no gym, and I can maybe fit two short sessions in if I'm lucky. Can you reshape the week around that?",
    "why": "Main driver is schedule and resource constraints."
  },
  {
    "id": "TC-005",
    "expected_intent": "coaching",
    "message": "No races on the calendar and no real main sport right now - I just want to stay in shape and feel good. I can train three times this week. Can you give me something simple?",
    "why": "Explicit request to create a general-fitness plan."
  },
  {
    "id": "TC-006",
    "expected_intent": "coaching",
    "message": "My right knee is a little sore today, maybe 3 or 4 out of 10, but it's not sharp and I'm walking normally. I'm mostly just unsure whether I should keep the tempo run as written or switch it to easy.",
    "why": "Mild, stable symptom without red flags. Real ask is to modify today's workout."
  },
  {
    "id": "TC-007",
    "expected_intent": "question",
    "message": "Did my FTP test this morning and got 228, up from 214 last month. Pretty happy with that.",
    "why": "Reports a performance result with no explicit request."
  },
  {
    "id": "TC-008",
    "expected_intent": "off_topic",
    "message": "Random question - do you have any recommendations for a good carry-on backpack for a two-day work trip?",
    "why": "Not related to training, recovery, planning, or athlete health."
  },
  {
    "id": "TC-009",
    "expected_intent": "coaching",
    "message": "I already missed Monday and Wednesday this week and now I'm stressing that I'm falling behind. Is there a smart way to adjust the rest of the week without cramming everything in?",
    "why": "The athlete wants the remaining week restructured."
  },
  {
    "id": "TC-010",
    "expected_intent": "coaching",
    "message": "Here's where I'm at: last week I was sick and didn't train at all, I'm finally feeling mostly normal, but my sleep is still bad and I only have about 20-30 minutes a day until Sunday. I don't want to lose momentum though - what should this week look like?",
    "why": "Mixed context, but the strongest routing factor is constrained availability for the upcoming week."
  },
  {
    "id": "TC-011",
    "expected_intent": "safety_concern",
    "message": "My knee is swollen tonight after that workout and it actually aches when I'm lying in bed. Should I still do tomorrow's run?",
    "why": "Swelling + night pain + go/no-go question should route to safety-first behavior."
  },
  {
    "id": "TC-012",
    "expected_intent": "coaching",
    "message": "My work schedule is all over the place this week. Don't give me strict days - just give me 4 workout options and tell me which 2 matter most.",
    "why": "Explicit request for a flexible output mode and weekly plan structure."
  },
  {
    "id": "TC-013",
    "expected_intent": "coaching",
    "message": "It's too dark and wet to ride consistently now, and the last couple weeks have mostly been pool sessions. I think swimming should be my main focus for a while.",
    "why": "Main-sport switch request."
  },
  {
    "id": "TC-014",
    "expected_intent": "question",
    "message": "What's the difference between a threshold workout and a VO2 session? I keep hearing both and I'm not sure when each is used.",
    "why": "Pure informational question, not a request to modify the plan."
  },
  {
    "id": "TC-015",
    "expected_intent": "coaching",
    "message": "Travel week. No gym. Two days max. Help.",
    "why": "Very short, but clearly driven by schedule and equipment constraints."
  }
]
```
