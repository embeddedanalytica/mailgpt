"""Unit tests for coaching (profile-gated reply). DynamoDB/merge mocked."""
import sys
import unittest
from unittest import mock

# Allow running without boto: stub dynamodb_models before coaching imports it
try:
    import coaching
except ModuleNotFoundError as e:
    if "boto" in str(e).lower() or "botocore" in str(e).lower():
        coaching = None  # type: ignore
    else:
        raise


def _memory_note(
    note_id: int,
    *,
    fact_type: str,
    fact_key: str,
    summary: str,
    importance: str = "high",
    status: str = "active",
    created_at: int = 1773273600,
    updated_at: int = 1773273600,
    last_confirmed_at: int = 1773273600,
) -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


def _final_email_response(body: str = "This week: keep the quality controlled") -> dict:
    return {"final_email_body": body}


@unittest.skipIf(coaching is None, "boto3/botocore not installed; skip coaching tests")
class TestBuildProfileGatedReply(unittest.TestCase):
    def test_returns_ready_message_when_profile_complete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", return_value={"route": "neither", "reason_resolution": "single_prompt"}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            run_response_generation_workflow.return_value = _final_email_response("Composed ready reply")
            create_token.return_value = "tok_123"
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )
            self.assertEqual(reply, "Composed ready reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["validated_plan"]["plan_summary"], "Current plan - Goal: 10k.")
            self.assertEqual(
                brief["delivery_context"]["connect_strava_link"],
                "https://geniml.com/action/tok_123",
            )
            ensure_plan.assert_called_once_with("ath_1", fallback_goal="10k")

    def test_returns_collection_prompt_when_profile_incomplete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {}
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_response_generation_workflow.return_value = _final_email_response("Composed clarification reply")
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )
            self.assertEqual(reply, "Composed clarification reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "clarification")
            self.assertEqual(
                brief["decision_context"]["clarification_questions"],
                [
                    "- Your primary goal (e.g., first marathon, improve 10k time)",
                    "- Your time availability (sessions/week and/or hours/week)",
                    "- Your experience level (beginner, intermediate, advanced, or unknown)",
                    "- Any constraints (injury, schedule, equipment, medical, preference). Empty is okay.",
                ],
            )
            ensure_plan.assert_called_once_with("ath_1", fallback_goal=None)

    def test_clarification_omits_time_availability_when_four_days_schedule_was_extracted(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.side_effect = [
                {},
                {
                    "primary_goal": "",
                    "time_availability": {"sessions_per_week": 4},
                    "experience_level": "intermediate",
                    "constraints": [],
                },
            ]
            parse_updates.return_value = {
                "time_availability": {"sessions_per_week": 4},
                "experience_level": "intermediate",
                "constraints": [],
            }
            merge.return_value = True
            ensure_plan.return_value = True
            run_response_generation_workflow.return_value = _final_email_response("Composed clarification reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I can train four days a week most weeks.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "Composed clarification reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "clarification")
            self.assertEqual(
                brief["decision_context"]["clarification_questions"],
                ["- Your primary goal (e.g., first marathon, improve 10k time)"],
            )

    def test_profile_incomplete_reply_still_runs_memory_refresh_when_eligible(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(
                 coaching,
                 "parse_profile_updates_from_email",
                 return_value={"time_availability": {"hours_per_week": 4.0}},
             ), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "long_term", "reason_resolution": "single_prompt"},
                 {"route": "long_term", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes", return_value=True) as replace_memory_notes, \
             mock.patch.object(coaching, "replace_continuity_summary", return_value=True) as replace_continuity_summary, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_memory_refresh.return_value = {
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="constraint:weekday_before_7am_cutoff",
                        summary="Can usually train only before 7am on weekdays",
                        importance="medium",
                    )
                ],
                "continuity_summary": {
                    "summary": "Athlete is still filling in profile details.",
                    "last_recommendation": "Collect baseline context before changing training.",
                    "open_loops": ["Confirm weekly availability and current goal"],
                    "updated_at": 1773273600,
                },
            }
            run_response_generation_workflow.return_value = _final_email_response("Clarification reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I can only train before 7am on weekdays and I want to get back to running.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "Clarification reply")
            self.assertEqual(run_memory_refresh.call_count, 1)
            replace_memory_notes.assert_called_once()
            replace_continuity_summary.assert_not_called()

    def test_profile_incomplete_reply_skips_memory_refresh_when_no_updates_applied(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "run_memory_router") as run_memory_router, \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes") as replace_memory_notes, \
             mock.patch.object(coaching, "replace_continuity_summary") as replace_continuity_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Clarification reply")
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "Clarification reply")
            run_memory_router.assert_not_called()
            run_memory_refresh.assert_not_called()
            replace_memory_notes.assert_not_called()
            replace_continuity_summary.assert_not_called()

    def test_applies_updates_from_email_and_then_checks_profile(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", return_value={"route": "neither", "reason_resolution": "single_prompt"}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.side_effect = [
                {},
                {
                    "primary_goal": "marathon",
                    "time_availability": {"sessions_per_week": 4},
                    "experience_level": "unknown",
                    "constraints": [],
                },
            ]
            parse_updates.return_value = {
                "primary_goal": "marathon",
                "time_availability": {"sessions_per_week": 4},
                "experience_level": "unknown",
                "constraints": [],
            }
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            run_response_generation_workflow.return_value = _final_email_response("Composed ready reply")
            create_token.return_value = "tok_456"
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Goal: marathon. I have 3 hours per week. Sports: running.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )
            self.assertEqual(reply, "Composed ready reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["delivery_context"]["connect_strava_link"], "https://geniml.com/action/tok_456")
            merge.assert_called_once()
            ensure_plan.assert_called_once_with("ath_1", fallback_goal="marathon")

    def test_calls_log_outcome_when_provided(self):
        log_calls = []
        def capture(**kwargs):
            log_calls.append(kwargs)
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", return_value={"route": "neither", "reason_resolution": "single_prompt"}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Logged reply")), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 1.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = "tok_789"
            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                selected_model_name="gpt-5-nano",
                log_outcome=capture,
            )
            self.assertGreater(len(log_calls), 0)
            self.assertTrue(any("result" in c for c in log_calls))

    def test_ready_message_skips_strava_link_when_token_creation_fails(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", return_value={"route": "neither", "reason_resolution": "single_prompt"}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            run_response_generation_workflow.return_value = _final_email_response("Composed ready reply")
            create_token.return_value = None
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )
            self.assertEqual(reply, "Composed ready reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertNotIn("connect_strava_link", brief["delivery_context"])

    def test_profile_complete_uses_selected_model_for_llm_reply(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation") as get_memory_context, \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            get_memory_context.return_value = {
                "memory_notes": [
                    _memory_note(
                        2,
                        fact_type="schedule",
                        fact_key="schedule:weekday_before_7am_cutoff",
                        summary="Prefers early weekday training",
                    )
                ],
                "continuity_summary": {
                    "summary": "Rebuilding after travel.",
                    "last_recommendation": "Keep intensity low.",
                    "open_loops": ["Check energy next week"],
                    "updated_at": 1773273600,
                },
            }
            create_token.return_value = "tok_123"
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            run_response_generation_workflow.assert_called_once()
            args, kwargs = run_response_generation_workflow.call_args
            self.assertEqual(kwargs["model_name"], "gpt-5-nano")
            brief = args[0]
            self.assertEqual(brief["delivery_context"]["inbound_subject"], "Plan help")
            self.assertEqual(brief["delivery_context"]["selected_model_name"], "gpt-5-nano")
            self.assertEqual(brief["validated_plan"]["plan_summary"], "Current plan - Goal: 10k.")
            self.assertEqual(
                brief["memory_context"]["continuity_summary"]["summary"],
                "Rebuilding after travel.",
            )
            self.assertEqual(
                brief["memory_context"]["memory_notes"][0]["summary"],
                "Prefers early weekday training",
            )
            self.assertEqual(
                brief["memory_context"]["continuity_focus"],
                "Rebuilding after travel.",
            )
            self.assertEqual(
                [note["summary"] for note in brief["memory_context"]["priority_memory_notes"]],
                ["Prefers early weekday training"],
            )
            self.assertEqual(brief["memory_context"]["supporting_memory_notes"], [])

    def test_pre_reply_memory_refresh_updates_llm_context_before_generation(self):
        call_order = []
        refreshed_context = {
            "memory_notes": [
                _memory_note(
                    3,
                    fact_type="constraint",
                    fact_key="constraint:weekday_before_6am_cutoff",
                    summary="Updated from inbound email before reply generation",
                )
            ],
            "continuity_summary": {
                "summary": "Fresh continuity before reply.",
                "last_recommendation": "Keep it steady.",
                "open_loops": [],
                "updated_at": 1773273600,
            },
        }
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation") as get_memory_context, \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "long_term", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes", return_value=True), \
             mock.patch.object(coaching, "replace_continuity_summary", return_value=True), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            get_memory_context.return_value = {"memory_notes": [], "continuity_summary": None}

            def refresh_side_effect(**kwargs):
                call_order.append("pre_refresh")
                get_memory_context.return_value = refreshed_context
                return {
                    "memory_notes": [
                        _memory_note(
                            3,
                            fact_type="constraint",
                            fact_key="constraint:weekday_before_6am_cutoff",
                            summary="Updated from inbound email before reply generation",
                        )
                    ],
                    "continuity_summary": {
                        "summary": "Fresh continuity before reply.",
                        "last_recommendation": "Keep it steady.",
                        "open_loops": [],
                        "updated_at": 1773273600,
                    },
                }

            run_memory_refresh.side_effect = refresh_side_effect

            def generate_side_effect(*args, **kwargs):
                call_order.append("generate_reply")
                brief = args[0]
                self.assertEqual(
                    brief["memory_context"]["memory_notes"][0]["summary"],
                    "Updated from inbound email before reply generation",
                )
                self.assertEqual(
                    [note["summary"] for note in brief["memory_context"]["priority_memory_notes"]],
                    ["Updated from inbound email before reply generation"],
                )
                return _final_email_response(
                    "This week: keep the quality controlled\n\n"
                    "You can still move the week forward, but this is a control-first week."
                )

            run_response_generation_workflow.side_effect = generate_side_effect

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I can only train before 6am now.",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            self.assertEqual(call_order, ["pre_refresh", "generate_reply"])

    def test_pre_reply_memory_refresh_failure_falls_back_to_old_memory(self):
        old_memory_context = {
            "memory_notes": [
                _memory_note(
                    1,
                    fact_type="schedule",
                    fact_key="schedule:old_persisted_note",
                    summary="Old persisted memory note",
                    created_at=1773187200,
                    last_confirmed_at=1773187200,
                    updated_at=1773187200,
                )
            ],
            "continuity_summary": None,
        }
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value=old_memory_context), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "long_term", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes") as replace_memory_notes, \
             mock.patch.object(coaching, "replace_continuity_summary") as replace_continuity_summary, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            run_memory_refresh.side_effect = coaching.MemoryRefreshError("bad payload")
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I can only train before 6am now.",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            replace_memory_notes.assert_not_called()
            replace_continuity_summary.assert_not_called()
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertIn("Old persisted memory note", brief["memory_context"]["memory_notes"][0]["summary"])
            self.assertEqual(
                [note["summary"] for note in brief["memory_context"]["priority_memory_notes"]],
                ["Old persisted memory note"],
            )

    def test_profile_complete_llm_reply_renders_multiple_memory_notes_and_open_loops(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation") as get_memory_context, \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "Half marathon",
                "time_availability": {"hours_per_week": 5.0},
                "experience_level": "intermediate",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: Half marathon."
            get_memory_context.return_value = {
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="constraint:calf_tightness_watch",
                        summary="Watch for calf tightness when adding speed",
                    ),
                    _memory_note(
                        2,
                        fact_type="constraint",
                        fact_key="constraint:weekday_before_7am_cutoff",
                        summary="Weekday sessions need to finish before 7am",
                    ),
                    _memory_note(
                        4,
                        fact_type="preference",
                        fact_key="preference:reply_format",
                        summary="Prefers concise bullets and explicit priorities",
                        importance="low",
                    ),
                ],
                "continuity_summary": {
                    "summary": "Athlete is rebuilding after two inconsistent weeks caused by work travel.",
                    "last_recommendation": "Rebuild consistency first, then reintroduce quality gradually.",
                    "open_loops": [
                        "Confirm whether travel is done this week",
                        "Check calf response after first moderate workout",
                    ],
                    "updated_at": 1773273600,
                },
            }
            create_token.return_value = None
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )

            coaching.build_profile_gated_reply(
                "ath_2",
                "user@example.com",
                "Can you map out my next few days?",
                inbound_subject="Next few days",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(
                brief["memory_context"]["continuity_summary"]["open_loops"],
                [
                    "Confirm whether travel is done this week",
                    "Check calf response after first moderate workout",
                ],
            )
            self.assertEqual(
                [note["summary"] for note in brief["memory_context"]["memory_notes"]],
                [
                    "Watch for calf tightness when adding speed",
                    "Weekday sessions need to finish before 7am",
                    "Prefers concise bullets and explicit priorities",
                ],
            )
            self.assertEqual(
                brief["memory_context"]["continuity_focus"],
                "Athlete is rebuilding after two inconsistent weeks caused by work travel.",
            )
            self.assertEqual(
                [note["summary"] for note in brief["memory_context"]["priority_memory_notes"]],
                [
                    "Watch for calf tightness when adding speed",
                    "Weekday sessions need to finish before 7am",
                ],
            )
            self.assertEqual(
                [note["summary"] for note in brief["memory_context"]["supporting_memory_notes"]],
                ["Prefers concise bullets and explicit priorities"],
            )

    def test_profile_complete_reply_triggers_memory_refresh_and_persists_full_payload(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "short_term", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes", return_value=True) as replace_memory_notes, \
             mock.patch.object(coaching, "replace_continuity_summary", return_value=True) as replace_continuity_summary, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "Half marathon",
                "time_availability": {"hours_per_week": 5.0},
                "experience_level": "intermediate",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: Half marathon."
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )
            run_memory_refresh.return_value = {
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="constraint:weekday_before_7am_cutoff",
                        summary="Weekday sessions need to finish before 7am",
                    )
                ],
                "continuity_summary": {
                    "summary": "Athlete is rebuilding after travel.",
                    "last_recommendation": "Keep one moderate session this week.",
                    "open_loops": ["Check calf response after Thursday workout"],
                    "updated_at": 1773273600,
                },
            }

            reply = coaching.build_profile_gated_reply(
                "ath_2",
                "user@example.com",
                "Can you map out my next few days?",
                inbound_subject="Next few days",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            run_memory_refresh.assert_called_once()
            replace_memory_notes.assert_not_called()
            replace_continuity_summary.assert_called_once()

    def test_profile_complete_reply_skips_persist_when_memory_refresh_payload_invalid(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "short_term", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes") as replace_memory_notes, \
             mock.patch.object(coaching, "replace_continuity_summary") as replace_continuity_summary, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Generated reply")):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_memory_refresh.side_effect = coaching.MemoryRefreshError("bad payload")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, can you adjust this week?",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            replace_memory_notes.assert_not_called()
            replace_continuity_summary.assert_not_called()

    def test_profile_incomplete_selected_model_uses_clarification_mode_brief(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response(
                "Please reply with your primary goal, time availability, experience level, and constraints."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("primary goal", reply.lower())
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "clarification")
            self.assertTrue(brief["decision_context"]["clarification_needed"])
            self.assertEqual(brief["validated_plan"], {})

    def test_clarification_needed_reply_uses_clarification_mode_brief(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_response_generation_workflow.return_value = _final_email_response(
                "Before I change your plan, I need your event date, available days, and pain score."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "clarification_needed": True,
                    "engine_output": {
                        "track": "main_build",
                        "risk_flag": "yellow",
                        "plan_update_status": "unchanged_clarification_needed",
                    },
                },
                log_outcome=None,
            )

            self.assertIn("event date", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "clarification")
            self.assertTrue(brief["decision_context"]["clarification_needed"])
            self.assertEqual(brief["validated_plan"], {})

    def test_llm_reply_uses_brief_derived_decision_context_not_raw_rule_engine_dump(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "reply_strategy": "standard",
                    "clarification_needed": False,
                    "engine_output": {
                        "classification_label": "deterministic_re3_transition",
                        "track": "return_or_risk_managed",
                        "phase": "build",
                        "risk_flag": "yellow",
                        "weekly_skeleton": ["easy_aerobic", "strength"],
                        "today_action": "prioritize_big_2_anchors",
                        "plan_update_status": "updated",
                        "adjustments": ["prioritize_big_2_anchors"],
                        "next_email_payload": {
                            "subject_hint": "This week: stay safe and keep it steady",
                            "summary": "This is a risk-managed week.",
                            "sessions": ["Priority: long easy aerobic session"],
                            "plan_focus_line": "Use safety and consistency as the primary filter.",
                            "technique_cue": "Keep cadence light and posture tall.",
                            "recovery_target": "Prioritize recovery basics before adding any load.",
                            "if_then_rules": ["If symptoms rise, remove intensity immediately."],
                            "disclaimer_short": "",
                            "safety_note": "No hard sessions when risk is red-tier.",
                        },
                    },
                },
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["decision_context"]["track"], "return_or_risk_managed")
            self.assertEqual(brief["decision_context"]["phase"], "build")
            self.assertEqual(brief["decision_context"]["risk_flag"], "yellow")
            self.assertEqual(brief["decision_context"]["today_action"], "prioritize_big_2_anchors")
            self.assertNotIn("reply_strategy", brief["decision_context"])

    def test_clarification_needed_reply_skips_memory_refresh(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router") as run_memory_router, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            run_response_generation_workflow.return_value = _final_email_response(
                "Please send your event date, available days, and pain score."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "clarification_needed": True,
                    "engine_output": {
                        "track": "main_build",
                        "risk_flag": "yellow",
                        "plan_update_status": "unchanged_clarification_needed",
                    },
                },
                log_outcome=None,
            )

            self.assertIn("pain score", reply)
            run_memory_router.assert_not_called()

    def test_rule_engine_guided_reply_uses_llm_generation_with_guided_payload(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "short_term", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "get_memory_notes", return_value=[]), \
             mock.patch.object(coaching, "get_continuity_summary", return_value=None), \
             mock.patch.object(coaching, "run_memory_refresh") as run_memory_refresh, \
             mock.patch.object(coaching, "replace_memory_notes", return_value=True), \
             mock.patch.object(coaching, "replace_continuity_summary", return_value=True), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_memory_refresh.return_value = {
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="constraint:injury_watch",
                        summary="note",
                    )
                ],
                "continuity_summary": {
                    "summary": "continuity",
                    "last_recommendation": "recommendation",
                    "open_loops": [],
                    "updated_at": 1773273600,
                },
            }
            run_response_generation_workflow.return_value = _final_email_response("LLM guided reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "reply_strategy": "rule_engine_guided",
                    "engine_output": {
                        "classification_label": "deterministic_re3_transition",
                        "track": "return_or_risk_managed",
                        "phase": "build",
                        "risk_flag": "yellow",
                        "weekly_skeleton": ["easy_aerobic", "strength"],
                        "today_action": "prioritize_big_2_anchors",
                        "plan_update_status": "updated",
                        "adjustments": ["prioritize_big_2_anchors"],
                        "next_email_payload": {
                            "subject_hint": "This week: stay safe and keep it steady",
                            "summary": "This is a risk-managed week.",
                            "sessions": ["Priority: long easy aerobic session", "Priority: strength session"],
                            "plan_focus_line": "Use safety and consistency as the primary filter.",
                            "technique_cue": "Keep cadence light and posture tall.",
                            "recovery_target": "Prioritize recovery basics before adding any load.",
                            "if_then_rules": ["If symptoms rise, remove intensity immediately."],
                            "disclaimer_short": "",
                            "safety_note": "No hard sessions when risk is red-tier.",
                        },
                    },
                },
                log_outcome=None,
            )

            self.assertEqual(reply, "LLM guided reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(
                brief["validated_plan"]["session_guidance"],
                ["Priority: long easy aerobic session", "Priority: strength session"],
            )
            self.assertEqual(
                brief["validated_plan"]["adjustments_or_priorities"],
                [
                    "This is a risk-managed week.",
                    "Use safety and consistency as the primary filter.",
                    "Keep cadence light and posture tall.",
                    "Prioritize recovery basics before adding any load.",
                ],
            )
            run_memory_refresh.assert_called_once()

    def test_safety_reply_strategy_bypasses_llm_generation(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router") as run_memory_router, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_response_generation_workflow.return_value = _final_email_response(
                "Pause training for now and get medical guidance before doing another hard session."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I have sharp knee pain, should I run?",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"reply_strategy": "safety_concern"},
                log_outcome=None,
            )

            self.assertIn("Pause training", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "safety_risk_managed")
            run_memory_router.assert_not_called()

    def test_off_topic_reply_strategy_skips_memory_refresh(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router") as run_memory_router, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            run_response_generation_workflow.return_value = _final_email_response(
                "I can help with training, recovery, and plan adjustments. Share your latest workout update or coaching question."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "What's your favorite running shoe?",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"reply_strategy": "off_topic"},
                log_outcome=None,
            )

            self.assertIn("training, recovery, and plan adjustments", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "off_topic_redirect")
            run_memory_router.assert_not_called()

    def test_question_intent_uses_lightweight_non_planning_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"hours_per_week": 2.0},
            "experience_level": "unknown",
            "constraints": [],
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Keep the effort conversational on easy days.")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "How easy should easy runs feel?",
                inbound_subject="Question",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "question", "mode": "read_only"},
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "lightweight_non_planning")
            self.assertEqual(brief["validated_plan"], {})

    def test_milestone_update_intent_uses_lightweight_non_planning_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"hours_per_week": 2.0},
            "experience_level": "unknown",
            "constraints": [],
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Nice work on the PR. Let the next recovery day stay easy.")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I ran a PR this weekend.",
                inbound_subject="Race result",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "milestone_update", "mode": "read_only"},
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "lightweight_non_planning")

    def test_mutate_intent_without_special_handling_uses_normal_coaching_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"hours_per_week": 2.0},
            "experience_level": "unknown",
            "constraints": [],
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Keep one quality session and protect recovery.")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can we shift my quality day to Thursday?",
                inbound_subject="Plan change",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "plan_change_request", "mode": "mutate"},
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "normal_coaching")

    def test_response_generation_failure_returns_none_and_logs_bounded_context(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"hours_per_week": 2.0},
            "experience_level": "unknown",
            "constraints": [],
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", side_effect=coaching.ResponseGenerationProposalError("invalid_json_response")), \
             mock.patch.object(coaching.logger, "error") as logger_error:
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_message_id="msg-1",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "plan_change_request", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertIsNone(reply)
            self.assertTrue(logger_error.called)
            logged = logger_error.call_args.args
            self.assertIn("response_generation_send_suppressed", logged[0])
            self.assertIn('"reply_mode":"normal_coaching"', logged[-1])
            self.assertIn('"plan_summary":"Current plan - Goal: 10k."', logged[-1])

    def test_whitespace_only_generated_reply_returns_none(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"hours_per_week": 2.0},
            "experience_level": "unknown",
            "constraints": [],
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"memory_notes": [], "continuity_summary": None}), \
             mock.patch.object(coaching, "run_memory_router", side_effect=[
                 {"route": "neither", "reason_resolution": "single_prompt"},
             ]), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value={"final_email_body": "   "}):
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_message_id="msg-1",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "plan_change_request", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertIsNone(reply)


if __name__ == "__main__":
    unittest.main()
