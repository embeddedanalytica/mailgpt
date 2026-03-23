# AI Coaching App — Implementation Backlog

**Archived — not a current product backlog.** Do not use this file for prioritization or planning; it is kept for historical context only. Current runtime and scope live in [sam-app/README.md](sam-app/README.md).

Status: historical/foundational backlog.
This file captures the early implementation plan for the project. Large parts are now implemented or superseded by the current runtime described in [sam-app/README.md](sam-app/README.md) and by the completed rule-engine record in [rule-engine-epic.md](rule-engine-epic.md).

---

# EPIC 1 — Core State Foundation

Status: implemented foundation.

These stories establish persistent structured state.  
No intelligence logic included yet.

---

## Story 1.1 — Persist Athlete Profile

### Why
Coaching decisions must align with the athlete’s goals and constraints.

### What
Store a structured athlete profile extracted from onboarding conversation.

### Acceptance Criteria
- Onboarding occurs via conversational flow.
- System extracts and stores:
  - Primary goal
  - Time availability
  - Experience level
  - Constraints (injury, schedule, etc.)
- Profile is persisted independently of conversation threads.
- Profile is automatically retrieved for every new interaction.

---

## Story 1.2 — Persist Active Plan Object

### Why
Coaching continuity must survive new conversation threads.

### What
Store a structured active plan object per athlete.

### Acceptance Criteria
- Only one active plan per athlete.
- Plan contains:
  - Plan version
  - Current phase
  - Current focus
  - Next recommended session
  - Plan status (active / adjusting / recovery)
- Plan updates increment version instead of overwriting history.
- Plan is retrievable across threads.

---

## Story 1.3 — Store Activity Snapshot

### Why
The system must retain structured memory even without external connectors.

### What
Store a structured snapshot of each athlete check-in.

### Acceptance Criteria
Each snapshot includes:
- Activity type
- Duration (if provided)
- Key metric (if provided)
- Subjective feedback (if provided)
- Timestamp
- Source = manual

System maintains:
- Last activity snapshot
- Aggregated progress snapshot

No analytics required at this stage.

---

# EPIC 2 — Conversation Intelligence

Status: implemented foundation.

---

## Story 2.1 — Intent Classification

### Why
System behavior must vary depending on user intent.

### What
Classify each incoming message into a defined intent category.

### Intent Categories
- Check-in
- Question
- Plan change request
- Milestone update
- Off-topic

### Acceptance Criteria
- Intent classification runs before response generation.
- Intent is stored per message.
- Intent is accessible by the logic engine.

---

## Story 2.2 — Complexity Scoring

### Why
Drive model routing and coaching depth control.

### What
Assign a complexity score (1–5) to each message.

### Score Reflects
- Coaching depth required
- Analytical effort
- Plan modification impact

### Acceptance Criteria
- Complexity score stored per message.
- Score available prior to model routing.

---

## Story 2.3 — Model Routing Based on Complexity

### Why
Optimize cost while maintaining quality.

### What
Route response generation to different models based on complexity score.

### Routing Rules
- Score 1–2 → Lightweight model
- Score 3–5 → Advanced model

### Acceptance Criteria
- Routing decision logged.
- Routing thresholds configurable.
- Routing occurs before response generation.

---

# EPIC 3 — MVP Coaching Logic Engine

Status: historical scope; core intent is implemented, but the active coaching system has moved beyond this MVP framing.
Use this section as background only, not as the current source of truth for coaching behavior.

---

## Story 3.1 — “Enough Information” Evaluation

### Why
System must avoid premature or uninformed recommendations.

### What
Determine whether sufficient data exists to generate guidance.

### Evaluation Criteria
- Active plan exists
- Recent activity snapshot exists
- Required fields present for current coaching decision

### Acceptance Criteria
System outputs:
- NEED_MORE_INFO
- READY_FOR_GUIDANCE

Initial implementation is rule-based.

---

## Story 3.2 — Targeted Follow-Up Question Generator

### Why
Vague check-ins must be expanded before coaching decisions.

### What
Generate targeted clarification questions when information is insufficient.

### Rules
- Maximum 2 follow-up questions per interaction.
- Questions must address specific missing fields.
- Avoid generic prompts.

### Acceptance Criteria
Triggered only when evaluator returns NEED_MORE_INFO.

---

## Story 3.3 — Generate Next Recommended Action

### Why
Deliver visible coaching intelligence.

### What
Generate next recommended action when sufficient information exists.

### Inputs
- Last activity snapshot
- Plan phase
- Subjective feedback (if available)
- Progress snapshot

### Output Types
- Rest day recommendation
- Easy session
- Hard effort
- Recovery suggestion

### Acceptance Criteria
- Recommendation references recent activity.
- Recommendation aligns with current plan phase.
- Plan object is not modified in this story.

---

# EPIC 4 — Progress Awareness

Status: partially implemented / partly superseded by current persistence and rule-engine behavior.

---

## Story 4.1 — Update Progress Snapshot

### Why
Future guidance must reflect trends and goal alignment.

### What
Update aggregated progress snapshot after each check-in.

### Snapshot Includes
- Consistency indicator
- Goal alignment status
- Trend direction (improving / plateau / declining)

### Acceptance Criteria
- Snapshot updated after activity storage.
- Snapshot retrievable independently of raw activity history.

---

## Story 4.2 — Milestone Detection

### Why
Reinforce motivation and showcase value.

### What
Detect milestone events and trigger celebration messaging.

### Example Milestones
- Activity streak
- Personal best
- Goal progress markers

### Acceptance Criteria
- Milestone detection runs after progress update.
- Celebration message is contextual.
- Celebration does NOT count toward tier response limits.

---

# EPIC 5 — Tier Governance

Status: partially implemented.
Response-frequency enforcement exists in the current system; this section remains useful only for backlog items not already reflected in README/current code.

---

## Story 5.1 — Response Frequency Enforcement

### Why
Enforce subscription-based usage limits.

### What
Limit response frequency based on athlete tier.

### Acceptance Criteria
Before sending response:
- Check responses sent within defined time window.
- Compare against tier allowance.

If exceeded:
- Send deferment message.
- Do not generate coaching response.

Milestone messages bypass this restriction.

---

## Story 5.2 — Coaching Depth Enforcement

### Why
Different tiers receive different coaching intensity.

### What
Restrict coaching depth based on subscription tier.

### Controls May Include
- Limit use of advanced model
- Limit clarification loops
- Limit plan modification frequency

### Acceptance Criteria
- Tier rules configurable.
- Enforcement occurs before model routing or logic execution.

---

# EPIC 6 — Adaptive Plan (Phase 2)

Status: largely superseded by the implemented rule engine and plan-update flow.
Treat this section as historical framing unless a future item is still not covered elsewhere.

---

## Story 6.1 — Off-Track Detection

### Why
Coaching must adapt to performance trends.

### What
Detect when athlete deviates from expected trajectory.

### Triggers
- Missed sessions
- Declining trend
- Negative fatigue pattern

### Acceptance Criteria
- Plan status set to "Adjusting".
- Adjustment flag stored in plan object.

---

## Story 6.2 — Plan Adjustment Generator

### Why
Close the adaptive coaching loop.

### What
Modify structured plan when adjustment is required.

### Possible Adjustments
- Reduce intensity
- Insert recovery
- Change phase
- Increment plan version

### Acceptance Criteria
- Plan version increments.
- Adjustment logged.
- Updated plan retrievable in next interaction.

---

# Connector Integrations

Status: still relevant future work, but not the current source of truth for connector behavior.

Connector ingestion (e.g., Strava, Garmin) is handled in a separate epic and enriches activity snapshots but is not required for core functionality.
