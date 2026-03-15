# Response Generation Implementation Epic

Status: planned design, not current production behavior.
This file describes the target design for athlete-facing response generation. Current runtime behavior is documented in [sam-app/README.md](/Users/levonsh/Projects/smartmail/sam-app/README.md).

## Context and Scope Boundaries
- The goal is coherent, athlete-facing coaching communication, not just formatting a payload into text.
- The response layer is distinct from planning and state logic. The rule engine remains the authority on state, safety, validated plans, and fallback constraints.
- The current response-generation implementation is treated as replaceable MVP scaffolding, not an architectural constraint.
- Backward compatibility is not a design goal for this epic. If a cleaner design requires replacing current response shapes or composition flow, prefer the cleaner design.
- YAGNI still applies: prefer the smallest clean response model that supports strong coaching replies, safe guardrails, and clear system boundaries.

---

## Epic RG1 — Athlete Response Generation and Reply Composition

### Goal
Enable the system to generate athlete-facing emails that feel like a coach explaining the week, not a flattened data payload.

Responses should be engaging, concise, safe, context-aware, and grounded in validated coaching decisions.
Planning and communication should be separate concerns: the rule engine decides what the athlete should do, and the response layer decides how to explain that clearly and effectively.

### Response Model
- `response_brief`: a bounded input artifact assembled from validated coaching state plus relevant response context.
- `response_payload`: a structured athlete-facing communication artifact produced from the `response_brief`.
- `final_email_body`: the deterministic final rendering of the `response_payload` into outbound email text.

The response system owns communication structure, framing, prioritization, and presentation.
The rule engine owns state, safety, plan authority, and validation boundaries.

Example `response_brief`:

~~~json
{
  "reply_mode": "normal_coaching",
  "athlete_context": {
    "goal_summary": "10k race in 8 weeks",
    "experience_level": "intermediate",
    "structure_preference": "flexibility"
  },
  "decision_context": {
    "track": "main_build",
    "phase": "build",
    "risk_flag": "yellow",
    "today_action": "do planned but conservative"
  },
  "validated_plan": {
    "weekly_skeleton": [
      "easy_aerobic",
      "strength",
      "tempo",
      "easy_aerobic"
    ],
    "planner_rationale": "Keep one quality session but lower the overall ambition of the week."
  },
  "delivery_context": {
    "plan_summary": "Current plan: rebuild consistency while protecting recovery.",
    "athlete_memory_available": false
  }
}
~~~

Example `response_payload`:

~~~json
{
  "subject_hint": "This week: keep the quality controlled",
  "opening": "You can still move the week forward, but this is a control-first week rather than a push week.",
  "coach_take": "Your energy and recovery signals matter more than forcing progression right now.",
  "weekly_focus": "Protect consistency, keep one purposeful session, and avoid stacking stress.",
  "session_guidance": [
    "Priority 1: one controlled quality session only if you feel steady",
    "Priority 2: easy aerobic work around it",
    "Priority 3: one short strength session"
  ],
  "adjustments_or_priorities": [
    "Do not make up missed intensity",
    "Reduce ambition before reducing consistency"
  ],
  "if_then_rules": [
    "If your legs feel flat, swap the quality session for easy aerobic work"
  ],
  "reply_prompt": "Reply with how the quality session felt and whether your energy improved.",
  "safety_note": "Back off immediately if symptoms worsen.",
  "disclaimer_short": ""
}
~~~

Example `final_email_body`:

~~~text
This week: keep the quality controlled

You can still move the week forward, but this is a control-first week rather than a push week.

Your energy and recovery signals matter more than forcing progression right now. The goal this week is to protect consistency, keep one purposeful session, and avoid stacking stress.

Priorities:
- one controlled quality session only if you feel steady
- easy aerobic work around it
- one short strength session

If your legs feel flat, swap the quality session for easy aerobic work.

Reply with how the quality session felt and whether your energy improved.
~~~

The examples above are illustrative. They define the intended shape of the system, not a locked final schema.

### Stories

#### Story RG1.1 — Canonical Response Brief Contract
As a response system, I need a clear `response_brief` contract so language generation receives bounded and relevant coaching context.

Story DoD:
- [ ] A canonical `response_brief` shape is defined with only the fields needed for athlete-facing response generation.
- [ ] The contract separates validated coaching decisions from communication-only context.
- [ ] The contract includes an explicit `reply_mode` so different response flows do not rely on ad hoc branching.
- [ ] Validation rejects malformed or incomplete response briefs before response generation begins.
- [ ] Contract tests cover valid/invalid response-brief payloads and required reply modes.

#### Story RG1.2 — Canonical Response Payload Contract
As a messaging layer, I need a structured `response_payload` contract so communication quality is deliberate and testable.

Story DoD:
- [ ] A canonical `response_payload` shape is defined for athlete-facing communication sections such as opening, coach take, weekly focus, priorities, and follow-up prompt.
- [ ] The contract is distinct from rule-engine output and plan artifacts.
- [ ] Required vs optional sections are explicit.
- [ ] Validation rejects malformed payloads and unknown required structure.
- [ ] Contract tests cover valid/invalid payloads and required safety-related fields.

#### Story RG1.3 — Response Brief Assembly from Coaching Context
As a response system, I need a bounded response brief assembled from coaching artifacts so communication is grounded in validated decisions.

Story DoD:
- [ ] Response-brief assembly consumes validated plan data, decision context, and other communication inputs without taking state authority.
- [ ] Response-brief assembly can include current plan summary and other relevant context when available.
- [ ] Missing optional context degrades gracefully without blocking reply generation.
- [ ] Assembly logic avoids leaking raw internal structures that are not needed for communication quality.

#### Story RG1.4 — Language-LLM Response Generation Within Guardrails
As a messaging layer, I need the LanguageLLM to generate structured athlete-facing replies while remaining bounded by deterministic safety and plan constraints.

Story DoD:
- [ ] The LanguageLLM consumes only the `response_brief`, not raw mutable system state.
- [ ] The LanguageLLM returns a structured `response_payload`, not free-form email text.
- [ ] Prompting instructs the model to explain the week clearly, stay concise, and avoid contradicting risk or safety posture.
- [ ] Generated output is validated before it can be rendered into the final email body.
- [ ] Tests verify that the language layer cannot override safety notes, plan authority, or reply mode.

#### Story RG1.5 — Deterministic Final Email Composition
As a delivery layer, I need one deterministic way to render `response_payload` into the outbound email body so final formatting stays clean and maintainable.

Story DoD:
- [ ] Final email composition consumes a validated `response_payload` and produces one readable outbound email body.
- [ ] Composition logic is centralized instead of duplicated across reply paths.
- [ ] Formatting rules for sections, ordering, and empty-field handling are explicit and deterministic.
- [ ] Tests verify that different payload shapes render clearly and consistently.

#### Story RG1.6 — Personalization from Memory and Continuity
As a coaching system, I need the response layer to use memory and continuity context safely so replies feel personalized without becoming speculative.

Story DoD:
- [ ] Response generation can accept athlete memory and continuity context once that capability exists.
- [ ] Personalization inputs are bounded and clearly separated from rule-engine authority.
- [ ] Prompting discourages invented history, overfamiliarity, and speculative claims.
- [ ] Missing memory artifacts degrade gracefully to non-personalized but still coherent replies.

#### Story RG1.7 — Specialized Reply Modes
As a product system, I need explicit reply modes so different athlete situations produce appropriately different response structures.

Supported reply modes for this epic are:
- `normal_coaching`
- `clarification`
- `safety_risk_managed`
- `lightweight_non_planning`
- `off_topic_redirect`

Story DoD:
- [ ] Reply modes are explicit product-level behavior, not scattered handler branches.
- [ ] Each reply mode has a distinct response-brief path and communication objective.
- [ ] Safety and clarification modes prioritize control and clarity over engagement or elaboration.
- [ ] Tests verify that reply modes produce meaningfully different outputs and do not collapse into one generic template.

#### Story RG1.8 — Fallback, Validation, and Failure Behavior
As a platform maintainer, I need predictable fallback behavior so the system still sends safe, usable replies when language generation fails.

Story DoD:
- [ ] Invalid or failed language-generation output triggers a deterministic fallback response path.
- [ ] Fallback replies remain aligned with reply mode, safety posture, and validated coaching decisions.
- [ ] Validation happens before final rendering and again before send if needed.
- [ ] Tests cover language-generation failure, malformed payloads, and fallback rendering behavior.

#### Story RG1.9 — Prompting and Behavioral Guidance
As a system designer, I need explicit prompting guidance so the response layer consistently produces useful coaching communication.

Story DoD:
- [ ] Prompting distinguishes planning authority from communication authority.
- [ ] Prompting emphasizes concise explanation, realistic coaching tone, and useful prioritization.
- [ ] Prompting suppresses contradictory, overly generic, or overly verbose responses.
- [ ] Prompting guidance covers normal, clarification, safety, and lightweight non-planning reply modes.
- [ ] Tests or fixtures cover representative output patterns across reply modes.

### Epic RG1 DoD
- [ ] Athlete-facing replies are generated from a dedicated response-generation layer, not from ad hoc string assembly.
- [ ] Response generation consumes bounded, validated coaching inputs rather than raw mutable system state.
- [ ] Planning authority and communication authority remain separate concerns.
- [ ] The system supports distinct reply modes for normal coaching, clarification, safety, lightweight non-planning replies, and off-topic redirects.
- [ ] The LanguageLLM cannot override safety posture, risk framing, or validated plan authority.
- [ ] Deterministic fallback replies remain usable and safe when language generation fails.
- [ ] Personalization can incorporate memory and continuity safely once those capabilities exist.
- [ ] Backward compatibility with the current MVP response payload is not required.
- [ ] Duplicated formatting logic is replaced by one cleaner response model and composition path.

---

## Non-Goals
- Preserving the current response payload shape for its own sake.
- Treating current response-generation code as a long-term architectural boundary.
- Giving the response layer authority over rule-engine state, safety classification, or plan validation.
- Rich frontend presentation concerns beyond outbound email composition.
- A generalized conversational agent beyond the coaching reply use case.

---

## Expected Result
After Epic RG1 is implemented, the system should be able to:
- generate athlete-facing coaching emails from a clean response model,
- explain validated plans in a way that feels like coaching rather than field formatting,
- support specialized reply modes with clearer communication intent,
- personalize safely when memory and continuity inputs are available, and
- fall back cleanly when language generation fails without depending on legacy MVP response code.
