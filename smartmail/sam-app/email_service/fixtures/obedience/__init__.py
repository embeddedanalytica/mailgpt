"""Last-mile obedience regression fixtures.

Each fixture is a dict with:
  - id: unique fixture identifier
  - name: human-readable name
  - failure_type: taxonomy code from the classification set
  - description: what this fixture tests
  - response_brief: a minimal ResponseBrief dict (may omit fields defaulted by the builder)
  - directive_expectations: assertions about the coaching directive output
  - response_expectations: assertions about the final email response
"""

from typing import Any, Dict, List


def _base_athlete_context(**overrides: Any) -> Dict[str, Any]:
    base = {
        "goal_summary": "Rebuild base fitness for fall half marathon",
        "experience_level": "intermediate",
        "structure_preference": "concise",
        "constraints_summary": "Mild Achilles tightness historically; weekday runs finish by 6:45am",
        "primary_sport": "running",
    }
    base.update(overrides)
    return base


def _base_decision_context(**overrides: Any) -> Dict[str, Any]:
    base = {
        "track": "main_base",
        "phase": "base",
        "risk_flag": "green",
        "today_action": "coaching_reply",
        "clarification_needed": False,
        "clarification_questions": [],
        "missing_profile_fields": [],
        "plan_update_status": "no_change",
        "risk_recent_history": [],
        "weeks_in_coaching": 8,
        "intake_completed_this_turn": False,
        "brevity_preference": "normal",
    }
    base.update(overrides)
    return base


def _base_validated_plan(**overrides: Any) -> Dict[str, Any]:
    base = {
        "weekly_skeleton": ["Mon easy 30", "Wed easy 40", "Sat long 60-75", "Sun easy 30"],
        "planner_rationale": "Conservative base rebuild protecting Achilles",
        "plan_summary": "4x/week easy running with progressive long run",
        "session_guidance": ["All sessions easy/conversational pace"],
        "adjustments_or_priorities": ["No intensity this block"],
        "if_then_rules": ["If Achilles stiffness >60min post-run, skip next session"],
        "safety_note": "Monitor Achilles response 24h post-run",
    }
    base.update(overrides)
    return base


def _base_delivery_context(**overrides: Any) -> Dict[str, Any]:
    base = {
        "inbound_subject": "Quick update",
        "inbound_body": "Everything going well this week.",
        "selected_model_name": "claude-sonnet-4-5-20250514",
        "response_channel": "email",
        "connect_strava_link": "",
    }
    base.update(overrides)
    return base


def _base_memory_context(**overrides: Any) -> Dict[str, Any]:
    base = {
        "memory_available": True,
        "priority_facts": ["Goal: fall half marathon", "Constraint: Achilles tightness"],
        "structure_facts": ["Weekday runs 5:15-6:45am"],
        "context_facts": ["Prefers concise, practical emails"],
        "continuity_summary": None,
    }
    base.update(overrides)
    return base


def _build_brief(
    *,
    reply_mode: str = "normal_coaching",
    athlete_context: Dict[str, Any] | None = None,
    decision_context: Dict[str, Any] | None = None,
    validated_plan: Dict[str, Any] | None = None,
    delivery_context: Dict[str, Any] | None = None,
    memory_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "reply_mode": reply_mode,
        "athlete_context": athlete_context or _base_athlete_context(),
        "decision_context": decision_context or _base_decision_context(),
        "validated_plan": validated_plan or _base_validated_plan(),
        "delivery_context": delivery_context or _base_delivery_context(),
        "memory_context": memory_context or _base_memory_context(),
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

OBEDIENCE_FIXTURES: List[Dict[str, Any]] = [
    # -----------------------------------------------------------------------
    # exceeded_requested_scope
    # -----------------------------------------------------------------------
    {
        "id": "OB-ES-001",
        "name": "keep_it_short",
        "failure_type": "exceeded_requested_scope",
        "description": (
            "Athlete explicitly asks for a short reply. "
            "The directive and response must respect brevity."
        ),
        "response_brief": _build_brief(
            decision_context=_base_decision_context(brevity_preference="brief"),
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Quick update: ran Tue and Thu as planned, Achilles quiet. "
                    "Keep it short — just confirm I'm good to go this weekend."
                ),
            ),
        ),
        "directive_expectations": {
            "content_plan_max_items": 3,
            "avoid_must_contain_any": ["expand", "elaborate", "lengthy", "extra"],
        },
        "response_expectations": {
            "max_sentences": 5,
            "must_not_contain": ["let me also", "additionally", "one more thing"],
        },
    },
    # -----------------------------------------------------------------------
    # reopened_resolved_topic
    # -----------------------------------------------------------------------
    {
        "id": "OB-RT-001",
        "name": "do_not_revisit_topic",
        "failure_type": "reopened_resolved_topic",
        "description": (
            "Athlete says 'do not revisit X'. "
            "The directive must include X in avoid. "
            "The response must not mention X."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Achilles is fine — please stop bringing it up every message. "
                    "Do not revisit the Achilles unless I raise it. "
                    "Just tell me what's on the schedule this week."
                ),
            ),
            memory_context=_base_memory_context(
                priority_facts=[
                    "Goal: fall half marathon",
                    "Constraint: historical Achilles tightness (currently resolved)",
                ],
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["Achilles", "achilles", "tendon"],
        },
        "response_expectations": {
            "must_not_contain": ["Achilles", "achilles", "tendon", "heel"],
        },
    },
    # -----------------------------------------------------------------------
    # exceeded_requested_scope
    # -----------------------------------------------------------------------
    {
        "id": "OB-ES-002",
        "name": "just_this_week",
        "failure_type": "exceeded_requested_scope",
        "description": (
            "Athlete asks 'just tell me this week'. "
            "Response must not discuss future weeks or long-term plans."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Just tell me this week — what are my sessions? "
                    "I don't need the big picture right now."
                ),
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["future", "long-term", "next week", "beyond this week"],
        },
        "response_expectations": {
            "must_not_contain": ["next week", "in the coming weeks", "long-term", "eventually"],
        },
    },
    # -----------------------------------------------------------------------
    # ignored_latest_constraint
    # -----------------------------------------------------------------------
    {
        "id": "OB-IC-001",
        "name": "locked_anchors",
        "failure_type": "ignored_latest_constraint",
        "description": (
            "Athlete locks specific session anchors (Sat long run, Sun recovery). "
            "Coach must not move or replace them."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Locking these for the week: Saturday long run and Sunday easy recovery. "
                    "Do not move or replace these sessions. "
                    "Fill in the rest of the week around them."
                ),
            ),
            validated_plan=_base_validated_plan(
                weekly_skeleton=[
                    "Mon easy 30",
                    "Wed easy 40",
                    "Sat long 75",
                    "Sun easy recovery 30",
                ],
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["move", "replace", "swap", "Saturday", "Sunday"],
        },
        "response_expectations": {
            "must_contain_any": ["Saturday", "Sat"],
            "must_contain_any_2": ["Sunday", "Sun"],
            "must_not_suggest_moving_anchors": True,
        },
    },
    # -----------------------------------------------------------------------
    # ignored_latest_constraint
    # -----------------------------------------------------------------------
    {
        "id": "OB-IC-002",
        "name": "latest_constraint_overrides_prior",
        "failure_type": "ignored_latest_constraint",
        "description": (
            "Athlete updates a constraint that contradicts an earlier one. "
            "The latest constraint must take priority."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Update: I can now run 5 days a week instead of 4. "
                    "My schedule opened up — add a Friday easy run. "
                    "Everything else stays the same."
                ),
            ),
            memory_context=_base_memory_context(
                structure_facts=["Weekday runs 5:15-6:45am", "Available 4 days/week"],
            ),
        ),
        "directive_expectations": {
            "main_message_must_contain_any": ["5 days", "five days", "Friday"],
        },
        "response_expectations": {
            "must_contain_any": ["Friday", "Fri", "five", "5 days"],
            "must_not_contain": ["4 days a week", "four days"],
        },
    },
    # -----------------------------------------------------------------------
    # ignored_latest_constraint — reply-when-told-not-to
    # -----------------------------------------------------------------------
    {
        "id": "OB-IC-003",
        "name": "no_reply_unless_concern",
        "failure_type": "ignored_latest_constraint",
        "description": (
            "Athlete says 'only reply if there is a concern'. "
            "If there is nothing to flag, the directive should suppress the reply."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Ran easy 30 min, felt fine. Achilles quiet. "
                    "No issues. Please only reply if there's a concern."
                ),
            ),
        ),
        "directive_expectations": {
            "reply_action": "suppress",
        },
        "response_expectations": {
            "suppressed": True,
        },
    },
    # -----------------------------------------------------------------------
    # introduced_unsupported_assumption
    # -----------------------------------------------------------------------
    {
        "id": "OB-UA-001",
        "name": "no_unsupported_week_labels",
        "failure_type": "introduced_unsupported_assumption",
        "description": (
            "Coach must not assert a specific week number unless it can be "
            "computed from an explicit anchor. Must not invent block labels."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "How's my plan looking? Just give me the sessions for this week."
                ),
            ),
        ),
        "directive_expectations": {},
        "response_expectations": {
            "must_not_contain_unanchored_week_numbers": True,
        },
    },
    # -----------------------------------------------------------------------
    # answered_from_stale_context
    # -----------------------------------------------------------------------
    {
        "id": "OB-SC-001",
        "name": "constraint_updated_by_athlete",
        "failure_type": "answered_from_stale_context",
        "description": (
            "Athlete says schedule changed from 4 to 5 days. "
            "Memory still says 4 days. Contradicted facts must be marked. "
            "Directive must reflect the new constraint, not the old one."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Update: I can now do 5 days a week instead of 4. "
                    "My schedule opened up — add a Friday easy run. "
                    "Everything else stays the same."
                ),
            ),
            memory_context=_base_memory_context(
                structure_facts=["Weekday runs 5:15-6:45am", "Available 4 days/week"],
                contradicted_facts=[
                    'Prior fact "Available 4 days/week" may be superseded — '
                    'athlete now says 5 days'
                ],
            ),
        ),
        "directive_expectations": {
            "main_message_must_contain_any": ["5 days", "five days", "Friday"],
        },
        "response_expectations": {
            "must_contain_any": ["Friday", "Fri", "five", "5 days"],
            "must_not_contain": ["4 days a week", "four days a week"],
        },
    },
    {
        "id": "OB-SC-002",
        "name": "injury_resolved_still_referenced",
        "failure_type": "answered_from_stale_context",
        "description": (
            "Athlete says the knee issue is resolved. Memory still lists it. "
            "Coach must not reference the knee as an active concern."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Knee is totally fine now, it cleared up two weeks ago. "
                    "Stop treating it as a constraint. What's the plan this week?"
                ),
            ),
            memory_context=_base_memory_context(
                priority_facts=[
                    "Goal: fall half marathon",
                    "Constraint: recurring knee pain after long runs",
                ],
                contradicted_facts=[
                    'Prior fact "Constraint: recurring knee pain after long runs" '
                    'may be superseded — athlete says knee is resolved'
                ],
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["knee"],
        },
        "response_expectations": {
            "must_not_contain": ["knee pain", "knee issue", "protect your knee"],
        },
    },
    # -----------------------------------------------------------------------
    # reopened_resolved_topic — confirmed detail re-asked
    # -----------------------------------------------------------------------
    {
        "id": "OB-RT-002",
        "name": "confirmed_detail_reopened",
        "failure_type": "reopened_resolved_topic",
        "description": (
            "Athlete already confirmed Tuesday as their preferred day. "
            "Coach should not re-ask about scheduling preference."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Yes, Tuesday works. I confirmed this last message. "
                    "Please just send the plan."
                ),
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["Tuesday", "tuesday", "scheduling", "day preference"],
        },
        "response_expectations": {
            "must_not_contain": [
                "which day works", "would Tuesday", "does Tuesday",
                "let me know what day", "preferred day",
            ],
        },
    },
    # -----------------------------------------------------------------------
    # exceeded_requested_scope — only answer the question
    # -----------------------------------------------------------------------
    {
        "id": "OB-ES-003",
        "name": "answer_question_only",
        "failure_type": "exceeded_requested_scope",
        "description": (
            "Athlete asks a direct question ('Is my long run too long?'). "
            "Coach should answer the question, not rewrite the plan."
        ),
        "response_brief": _build_brief(
            reply_mode="lightweight_non_planning",
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Quick question: is 75 minutes too long for my weekend long run "
                    "at this point? That's all I need to know."
                ),
            ),
        ),
        "directive_expectations": {
            "content_plan_max_items": 2,
            "avoid_must_contain_any": ["rewrite", "plan", "extra", "beyond"],
        },
        "response_expectations": {
            "max_sentences": 4,
            "must_not_contain": ["here is your updated plan", "let me adjust"],
        },
    },
    # -----------------------------------------------------------------------
    # missed_exact_instruction — start from specific week
    # -----------------------------------------------------------------------
    {
        "id": "OB-MI-002",
        "name": "start_from_week_2",
        "failure_type": "missed_exact_instruction",
        "description": (
            "Athlete says 'start from Week 2'. "
            "Coach must use Week 2 exactly, not Week 1 or Week 3."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Start from Week 2, not Week 1. "
                    "I already did the intro week on my own."
                ),
                athlete_instructions={
                    "latest_overrides": ["Start from Week 2, not Week 1"],
                },
            ),
        ),
        "directive_expectations": {
            "main_message_must_contain_any": ["Week 2", "week 2"],
        },
        "response_expectations": {
            "must_contain_any": ["Week 2", "week 2"],
            "must_not_contain": ["Week 1", "week 1"],
        },
    },
    # -----------------------------------------------------------------------
    # missed_exact_instruction — stop using week labels
    # -----------------------------------------------------------------------
    {
        "id": "OB-MI-001",
        "name": "stop_using_week_labels",
        "failure_type": "missed_exact_instruction",
        "description": (
            "Athlete explicitly asks to stop labeling weeks. "
            "Response must not contain 'Week N' or block-phase labels."
        ),
        "response_brief": _build_brief(
            delivery_context=_base_delivery_context(
                inbound_body=(
                    "Stop labeling weeks — no 'Week 5' or 'initial_assessment'. "
                    "Just reference the locked 8-week build to Sep 24. "
                    "Confirm Sat ride and Sun run are locked."
                ),
            ),
        ),
        "directive_expectations": {
            "avoid_must_contain_any": ["week label", "Week ", "initial_assessment", "week number"],
        },
        "response_expectations": {
            "must_not_match_pattern": r"Week \d+",
            "must_not_contain": ["initial_assessment", "assessment block"],
        },
    },
]


def get_fixture(fixture_id: str) -> Dict[str, Any]:
    for f in OBEDIENCE_FIXTURES:
        if f["id"] == fixture_id:
            return f
    raise KeyError(f"No fixture with id={fixture_id!r}")


def get_fixtures_by_type(failure_type: str) -> List[Dict[str, Any]]:
    return [f for f in OBEDIENCE_FIXTURES if f["failure_type"] == failure_type]
