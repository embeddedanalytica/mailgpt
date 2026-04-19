"""Unit tests for coaching (profile-gated reply). DynamoDB/merge mocked."""
from datetime import date
import sys
import unittest
from unittest import mock

# Allow running without boto: stub dynamodb_models before coaching imports it
from _test_sectioned_memory_fixtures import sectioned_from_flat_memory_notes
from sectioned_memory_contract import empty_sectioned_memory

try:
    import coaching
except ModuleNotFoundError as e:
    if "boto" in str(e).lower() or "botocore" in str(e).lower():
        coaching = None  # type: ignore
    else:
        raise


def _final_email_response(body: str = "This week: keep the quality controlled") -> dict:
    return {"final_email_body": body}


def _stub_coaching_reasoning_result() -> dict:
    """Minimal valid coaching reasoning result for test mocking."""
    return {
        "directive": {
            "reply_action": "send",
            "opening": "Test opening",
            "main_message": "Test message",
            "content_plan": ["present the plan"],
            "avoid": [],
            "tone": "calm and direct",
            "recommend_material": None,
        },
        "doctrine_files_loaded": [],
        "continuity_recommendation": {
            "recommended_goal_horizon_type": "general_fitness",
            "recommended_phase": "base",
            "recommended_block_focus": "controlled_load_progression",
            "recommended_transition_action": "keep",
            "recommended_transition_reason": "stable training",
            "recommended_goal_event_date": None,
        },
    }


@unittest.skipIf(coaching is None, "boto3/botocore not installed; skip coaching tests")
class TestBuildProfileGatedReply(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(
            coaching, "run_coaching_reasoning_workflow",
            return_value=_stub_coaching_reasoning_result(),
        )
        self._mock_coaching_reasoning = patcher.start()
        self.addCleanup(patcher.stop)

    @staticmethod
    def _continuity_state_dict() -> dict:
        return {
            "goal_horizon_type": "event",
            "current_phase": "base",
            "current_block_focus": "controlled_load_progression",
            "block_started_at": "2026-01-01",
            "goal_event_date": "2026-02-12",
            "last_transition_reason": "stable_training",
            "last_transition_date": "2026-01-01",
        }

    def test_returns_ready_message_when_profile_complete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "Weekday mornings only"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
            self.assertEqual(brief["plan_data"]["plan_summary"], "Current plan - Goal: 10k.")
            self.assertEqual(
                brief["delivery_context"]["connect_strava_link"],
                "https://geniml.com/action/tok_123",
            )
            ensure_plan.assert_called_once_with("ath_1", fallback_goal="10k")

    def test_continuity_context_uses_effective_today_when_injected(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "Weekday mornings only"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "get_continuity_state", return_value=self._continuity_state_dict()), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token", return_value=None):
            run_response_generation_workflow.return_value = _final_email_response("Reply")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
                effective_today=date(2026, 1, 15),
            )

            continuity_context = run_response_generation_workflow.call_args.args[0]["continuity_context"]
            self.assertEqual(continuity_context["weeks_in_current_block"], 3)
            self.assertEqual(continuity_context["weeks_until_event"], 4)

    def test_continuity_context_uses_date_today_by_default(self):
        class _FakeDate:
            @classmethod
            def today(cls):
                return date(2026, 1, 22)

        with mock.patch.object(coaching, "get_coach_profile", return_value={
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "Weekday mornings only"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "get_continuity_state", return_value=self._continuity_state_dict()), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "date", _FakeDate):
            run_response_generation_workflow.return_value = _final_email_response("Reply")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            continuity_context = run_response_generation_workflow.call_args.args[0]["continuity_context"]
            self.assertEqual(continuity_context["weeks_in_current_block"], 4)
            self.assertEqual(continuity_context["weeks_until_event"], 3)

    def test_returns_collection_prompt_when_profile_incomplete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
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
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            writer_brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "intake")
            self.assertEqual(
                sorted(response_brief["decision_context"]["missing_profile_fields"]),
                ["experience_level", "injury_status", "primary_goal", "time_availability"],
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.side_effect = [
                {},
                {
                    "primary_goal": "",
                    "time_availability": {"sessions_per_week": "4 days/week"},
                    "experience_level": "intermediate",
                    "injury_status": {"has_injuries": False},
                },
            ]
            parse_updates.return_value = {
                "time_availability": {"sessions_per_week": "4 days/week"},
                "experience_level": "intermediate",
                "injury_status": {"has_injuries": False},
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
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            writer_brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "intake")
            self.assertEqual(
                response_brief["decision_context"]["missing_profile_fields"],
                ["primary_goal"],
            )

    def test_profile_incomplete_reply_skips_memory_refresh_even_when_updates_exist(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(
                 coaching,
                 "parse_profile_updates_from_email",
                 return_value={"time_availability": {"availability_notes": "Before 7am on weekdays"}},
             ), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "run_obedience_eval") as run_obedience_eval:
            run_response_generation_workflow.return_value = _final_email_response("Clarification reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I can only train before 7am on weekdays and I want to get back to running.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "Clarification reply")
            maybe_post_refresh.assert_not_called()
            run_obedience_eval.assert_not_called()

    def test_profile_incomplete_reply_skips_memory_refresh_when_no_updates_applied(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "run_obedience_eval") as run_obedience_eval:
            run_response_generation_workflow.return_value = _final_email_response("Clarification reply")
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "Clarification reply")
            maybe_post_refresh.assert_not_called()
            run_obedience_eval.assert_not_called()

    def test_profile_gate_does_not_run_duplicate_checkin_extraction(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Clarification reply")), \
             mock.patch.object(coaching, "run_session_checkin_extraction_workflow") as run_checkin_extraction:
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I want to rebuild fitness.",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "read_only"},
                log_outcome=None,
            )

            self.assertEqual(reply, "Clarification reply")
            run_checkin_extraction.assert_not_called()

    def test_rule_engine_mutation_reuses_router_checkin_extraction(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "Weekday mornings only"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "run_session_checkin_extraction_workflow") as run_checkin_extraction, \
             mock.patch.object(coaching, "run_rule_engine_for_week") as run_rule_engine, \
             mock.patch.object(coaching, "apply_rule_engine_plan_update", return_value={"status": "applied"}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Ready reply")):
            run_rule_engine.return_value = mock.Mock(
                to_dict=lambda: {"plan_update_status": "updated"},
                plan_update_status="updated",
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Move my long ride to Saturday.",
                inbound_message_id="msg-1",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "intent": "coaching",
                    "mode": "mutate",
                    "clarification_needed": False,
                    "extracted_checkin": {"days_available": 4},
                },
                log_outcome=None,
            )

            self.assertEqual(reply, "Ready reply")
            run_checkin_extraction.assert_not_called()
            self.assertEqual(run_rule_engine.call_args.kwargs["checkin"], {"days_available": 4})

    def test_applies_updates_from_email_and_then_checks_profile(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.side_effect = [
                {},
                {
                    "primary_goal": "marathon",
                    "time_availability": {"sessions_per_week": "4 days/week"},
                    "experience_level": "unknown",
                    "injury_status": {"has_injuries": False},
                },
            ]
            parse_updates.return_value = {
                "primary_goal": "marathon",
                "time_availability": {"sessions_per_week": "4 days/week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
            # Profile just became complete: LLM generates first plan with transition flag
            self.assertEqual(reply, "Composed ready reply")
            run_response_generation_workflow.assert_called_once()
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertTrue(response_brief["decision_context"].get("intake_completed_this_turn"))
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Logged reply")), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 1 hour per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation") as get_memory_context, \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            get_memory_context.return_value = {
                "sectioned_memory": sectioned_from_flat_memory_notes(
                    [
                        {
                            "memory_note_id": "note-1",
                            "fact_type": "schedule",
                            "fact_key": "schedule:early-training",
                            "summary": "Prefers early weekday training",
                        },
                    ]
                ),
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
            writer_brief = args[0]
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertEqual(writer_brief["delivery_context"]["inbound_subject"], "Plan help")
            self.assertEqual(writer_brief["delivery_context"]["selected_model_name"], "gpt-5-nano")
            self.assertEqual(writer_brief["plan_data"]["plan_summary"], "Current plan - Goal: 10k.")
            self.assertEqual(
                response_brief["memory_context"]["continuity_summary"]["summary"],
                "Rebuilding after travel.",
            )
            self.assertEqual(
                response_brief["memory_context"]["continuity_focus"],
                "Rebuilding after travel.",
            )
            self.assertIn(
                "Prefers early weekday training",
                response_brief["memory_context"]["structure_facts"],
            )

    def test_post_reply_memory_refresh_failure_does_not_affect_reply(self):
        """Post-reply unified refresh failure should not affect the reply already generated."""
        old_memory_context = {
            "sectioned_memory": sectioned_from_flat_memory_notes(
                [
                    {
                        "memory_note_id": "note-1",
                        "fact_type": "schedule",
                        "fact_key": "schedule:old-note",
                        "summary": "Old persisted schedule note",
                    },
                ]
            ),
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value=old_memory_context), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
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
            maybe_post_refresh.assert_called_once()
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertIn(
                "Old persisted schedule note",
                response_brief["memory_context"]["structure_facts"],
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation") as get_memory_context, \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "Half marathon",
                "time_availability": {"availability_notes": "About 5 hours per week"},
                "experience_level": "intermediate",
                "injury_status": {"has_injuries": False},
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: Half marathon."
            get_memory_context.return_value = {
                "sectioned_memory": sectioned_from_flat_memory_notes(
                    [
                        {
                            "memory_note_id": "note-1",
                            "fact_type": "constraint",
                            "fact_key": "constraint:calf-tightness",
                            "summary": "Watch for calf tightness when adding speed",
                        },
                        {
                            "memory_note_id": "note-2",
                            "fact_type": "schedule",
                            "fact_key": "schedule:early-cutoff",
                            "summary": "Weekday sessions need to finish before 7am",
                        },
                        {
                            "memory_note_id": "note-3",
                            "fact_type": "preference",
                            "fact_key": "preference:reply-format",
                            "summary": "Prefers concise bullets and explicit priorities",
                        },
                    ]
                ),
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

            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertEqual(
                response_brief["memory_context"]["continuity_summary"]["open_loops"],
                [
                    "Confirm whether travel is done this week",
                    "Check calf response after first moderate workout",
                ],
            )
            self.assertEqual(
                response_brief["memory_context"]["continuity_focus"],
                "Athlete is rebuilding after two inconsistent weeks caused by work travel.",
            )
            # constraint → priority_facts; schedule → structure_facts; preference → preference_facts
            self.assertIn(
                "Watch for calf tightness when adding speed",
                response_brief["memory_context"]["priority_facts"],
            )
            self.assertIn(
                "Weekday sessions need to finish before 7am",
                response_brief["memory_context"]["structure_facts"],
            )
            self.assertIn(
                "Prefers concise bullets and explicit priorities",
                response_brief["memory_context"]["preference_facts"],
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
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "Half marathon",
                "time_availability": {"availability_notes": "About 5 hours per week"},
                "experience_level": "intermediate",
                "injury_status": {"has_injuries": False},
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: Half marathon."
            run_response_generation_workflow.return_value = _final_email_response(
                "This week: keep the quality controlled\n\n"
                "You can still move the week forward, but this is a control-first week."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_2",
                "user@example.com",
                "Can you map out my next few days?",
                inbound_subject="Next few days",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            maybe_post_refresh.assert_called_once()

    def test_profile_complete_reply_skips_persist_when_memory_refresh_payload_invalid(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value=_final_email_response("Generated reply")):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, can you adjust this week?",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            maybe_post_refresh.assert_called_once()

    def test_profile_incomplete_selected_model_uses_clarification_mode_brief(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={}), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
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
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            writer_brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "intake")
            self.assertTrue(response_brief["decision_context"]["clarification_needed"])
            self.assertEqual(response_brief["validated_plan"], {})

    def test_clarification_needed_reply_uses_clarification_mode_brief(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
                },
                log_outcome=None,
            )

            self.assertIn("event date", reply)
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            writer_brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "clarification")
            self.assertTrue(response_brief["decision_context"]["clarification_needed"])
            self.assertEqual(response_brief["validated_plan"], {})

    def test_llm_reply_does_not_include_old_rule_engine_context(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
                    "intent": "coaching",
                    "clarification_needed": False,
                },
                log_outcome=None,
            )

            self.assertIn("This week: keep the quality controlled", reply)
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertNotIn("track", response_brief["decision_context"])
            self.assertNotIn("phase", response_brief["decision_context"])
            self.assertNotIn("risk_flag", response_brief["decision_context"])
            self.assertNotIn("today_action", response_brief["decision_context"])
            self.assertNotIn("reply_strategy", response_brief["decision_context"])

    def test_clarification_needed_reply_skips_memory_refresh(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
                },
                log_outcome=None,
            )

            self.assertIn("pain score", reply)
            maybe_post_refresh.assert_called_once()

    def test_coaching_reply_uses_llm_generation_without_guided_rule_engine_payload(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            run_response_generation_workflow.return_value = _final_email_response("LLM guided reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertEqual(reply, "LLM guided reply")
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "normal_coaching")
            self.assertEqual(brief["plan_data"], {"plan_summary": "Current plan - Goal: 10k."})
            maybe_post_refresh.assert_called_once()

    def test_mutate_mode_runs_rule_engine_and_persists_plan_before_reply(self):
        call_order = []
        engine_output = mock.Mock()
        engine_output.plan_update_status = "updated"
        engine_output.to_dict.return_value = {
            "plan_update_status": "updated",
            "weekly_skeleton": ["easy_aerobic", "tempo", "long_run"],
        }

        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "get_sectioned_memory", return_value=empty_sectioned_memory()), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_session_checkin_extraction_workflow", return_value={"event_date": "2026-05-17", "days_available": 4, "pain_score": 2, "has_upcoming_event": True}) as extract_checkin, \
             mock.patch.object(coaching, "run_rule_engine_for_week", side_effect=lambda **kwargs: call_order.append("run_rule_engine_for_week") or engine_output) as run_engine, \
             mock.patch.object(coaching, "apply_rule_engine_plan_update", side_effect=lambda **kwargs: call_order.append("apply_rule_engine_plan_update") or {"status": "applied", "plan_version": 2, "error_code": None}) as apply_update, \
             mock.patch.object(coaching, "fetch_current_plan_summary", side_effect=lambda athlete_id, **kwargs: call_order.append("fetch_current_plan_summary") or "Current plan - Goal: 10k. Version 2"), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
            run_response_generation_workflow.return_value = _final_email_response("LLM guided reply")

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Availability update for this week. Event date: 2026-05-17. Days available: 4. Pain score: 2 out of 10.",
                inbound_message_id="msg-1",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
                effective_today=date(2026, 3, 25),
            )

            self.assertEqual(reply, "LLM guided reply")
            extract_checkin.assert_called_once()
            run_engine.assert_called_once()
            apply_update.assert_called_once()
            self.assertEqual(
                call_order,
                ["run_rule_engine_for_week", "apply_rule_engine_plan_update", "fetch_current_plan_summary"],
            )
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["plan_data"], {"plan_summary": "Current plan - Goal: 10k. Version 2"})

    def test_safety_reply_strategy_bypasses_llm_generation(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
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
                rule_engine_decision={"intent": "safety_concern"},
                log_outcome=None,
            )

            self.assertIn("Pause training", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "safety_risk_managed")
            # Unified refresh is always called; the gate logic inside decides to skip
            maybe_post_refresh.assert_called_once()

    def test_off_topic_reply_strategy_skips_memory_refresh(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_refresh, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"availability_notes": "About 2 hours per week"},
                "experience_level": "unknown",
                "injury_status": {"has_injuries": False},
            }
            run_response_generation_workflow.return_value = _final_email_response(
                "I can help with training, recovery, and plan adjustments. Share your latest workout update or coaching question."
            )

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "What's your favorite running shoe?",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "off_topic"},
                log_outcome=None,
            )

            self.assertIn("training, recovery, and plan adjustments", reply)
            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "off_topic_redirect")
            # Unified refresh is always called; the gate logic inside decides to skip
            maybe_post_refresh.assert_called_once()

    def test_question_intent_uses_lightweight_non_planning_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
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

            writer_brief = run_response_generation_workflow.call_args.args[0]
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "lightweight_non_planning")
            self.assertEqual(response_brief["validated_plan"], {})

    def test_question_intent_with_only_missing_injury_stays_lightweight(self):
        # Profile has everything except injury_status — question intent should stay lightweight
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response(
                "Keep easy runs easy for now."
            )

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Should I add strides after an easy run?",
                inbound_subject="Question",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "question", "mode": "read_only"},
                log_outcome=None,
            )

            writer_brief = run_response_generation_workflow.call_args.args[0]
            response_brief = self._mock_coaching_reasoning.call_args.args[0]
            self.assertEqual(writer_brief["reply_mode"], "lightweight_non_planning")
            self.assertNotIn("missing_profile_fields", response_brief["decision_context"])
            self.assertNotIn("clarification_needed", response_brief["decision_context"])
            self.assertEqual(
                response_brief["decision_context"]["clarification_questions"],
                [
                    "- Any current injuries, pains, or physical limitations (perfectly fine if there are none — just let me know either way)"
                ],
            )

    def test_milestone_update_intent_uses_lightweight_non_planning_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Nice work on the PR. Let the next recovery day stay easy.")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I ran a PR this weekend.",
                inbound_subject="Race result",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "question", "mode": "read_only"},
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "lightweight_non_planning")

    def test_mutate_intent_without_special_handling_uses_normal_coaching_mode(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh"), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow:
            run_response_generation_workflow.return_value = _final_email_response("Keep one quality session and protect recovery.")

            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can we shift my quality day to Thursday?",
                inbound_subject="Plan change",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
            )

            brief = run_response_generation_workflow.call_args.args[0]
            self.assertEqual(brief["reply_mode"], "normal_coaching")

    def test_response_generation_failure_returns_fallback_and_logs_bounded_context(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_reply_memory_refresh, \
             mock.patch.object(coaching, "update_continuity_state", return_value=True) as update_continuity_state, \
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
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertEqual(reply, coaching.EmailCopy.FALLBACK_AI_ERROR_REPLY)
            self.assertTrue(logger_error.called)
            logged = logger_error.call_args.args
            self.assertIn("response_generation_send_suppressed", logged[0])
            self.assertIn('"reply_mode":"normal_coaching"', logged[-1])
            self.assertIn('"plan_summary":"Current plan - Goal: 10k."', logged[-1])
            maybe_post_reply_memory_refresh.assert_not_called()
            update_continuity_state.assert_not_called()

    def test_whitespace_only_generated_reply_returns_fallback(self):
        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_reply_memory_refresh, \
             mock.patch.object(coaching, "update_continuity_state", return_value=True) as update_continuity_state, \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "run_response_generation_workflow", return_value={"final_email_body": "   "}):
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_message_id="msg-1",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertEqual(reply, coaching.EmailCopy.FALLBACK_AI_ERROR_REPLY)
            maybe_post_reply_memory_refresh.assert_not_called()
            update_continuity_state.assert_not_called()

    def test_suppressed_reply_skips_writer_and_returns_sentinel(self):
        suppressed = _stub_coaching_reasoning_result()
        suppressed["directive"]["reply_action"] = "suppress"
        suppressed["directive"]["opening"] = "No reply needed."
        suppressed["directive"]["main_message"] = "Suppress outbound reply."
        suppressed["directive"]["content_plan"] = ["suppress reply"]

        with mock.patch.object(coaching, "get_coach_profile", return_value={
            "primary_goal": "10k",
            "time_availability": {"availability_notes": "About 2 hours per week"},
            "experience_level": "unknown",
            "injury_status": {"has_injuries": False},
        }), \
             mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}), \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True), \
             mock.patch.object(coaching, "ensure_current_plan", return_value=True), \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "get_memory_context_for_response_generation", return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None}), \
             mock.patch.object(coaching, "run_coaching_reasoning_workflow", return_value=suppressed), \
             mock.patch.object(coaching, "run_response_generation_workflow") as run_response_generation_workflow, \
             mock.patch.object(coaching, "maybe_post_reply_memory_refresh") as maybe_post_reply_memory_refresh, \
             mock.patch.object(coaching, "update_continuity_state", return_value=True), \
             mock.patch.object(coaching, "create_action_token", return_value=None):
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "No need to reply unless you want to change anything.",
                inbound_message_id="msg-1",
                inbound_subject="Status only",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"intent": "coaching", "mode": "mutate"},
                log_outcome=None,
            )

            self.assertIs(reply, coaching.SUPPRESSED_REPLY)
            run_response_generation_workflow.assert_not_called()
            maybe_post_reply_memory_refresh.assert_not_called()


if __name__ == "__main__":
    unittest.main()
