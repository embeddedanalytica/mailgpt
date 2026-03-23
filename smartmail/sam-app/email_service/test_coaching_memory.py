"""Unit tests for coaching_memory (AM2 candidate-operation orchestration)."""

import unittest
from unittest.mock import MagicMock, patch

from coaching_memory import (
    build_memory_refresh_context,
    maybe_post_reply_memory_refresh,
    should_attempt_memory_refresh,
)


class TestShouldAttemptMemoryRefresh(unittest.TestCase):

    def test_coaching_reply_allowed(self):
        self.assertTrue(
            should_attempt_memory_refresh(reply_kind="coaching", parsed_updates={})
        )

    def test_safety_concern_blocked(self):
        self.assertFalse(
            should_attempt_memory_refresh(reply_kind="safety_concern", parsed_updates={})
        )

    def test_off_topic_blocked(self):
        self.assertFalse(
            should_attempt_memory_refresh(reply_kind="off_topic", parsed_updates={})
        )

    def test_clarification_blocked(self):
        self.assertFalse(
            should_attempt_memory_refresh(reply_kind="clarification_needed", parsed_updates={})
        )

    def test_profile_incomplete_with_updates_allowed(self):
        self.assertTrue(
            should_attempt_memory_refresh(
                reply_kind="profile_incomplete",
                parsed_updates={"name": "Alice"},
            )
        )

    def test_profile_incomplete_without_updates_blocked(self):
        self.assertFalse(
            should_attempt_memory_refresh(
                reply_kind="profile_incomplete",
                parsed_updates={},
            )
        )


class TestBuildMemoryRefreshContext(unittest.TestCase):

    def test_basic_context(self):
        ctx = build_memory_refresh_context(
            inbound_body="I ran 5k today",
            inbound_subject="Training update",
            parsed_updates={"name": "Alice"},
            manual_snapshot=None,
            selected_model_name="gpt-4o",
            rule_engine_decision={"track": "base_build"},
        )
        self.assertEqual(ctx["inbound_email"], "I ran 5k today")
        self.assertEqual(ctx["inbound_subject"], "Training update")
        self.assertEqual(ctx["profile_updates_applied"], ["name"])
        self.assertFalse(ctx["manual_activity_detected"])
        self.assertEqual(ctx["selected_model_name"], "gpt-4o")
        self.assertEqual(ctx["rule_engine_decision"], {"track": "base_build"})
        self.assertNotIn("coach_reply", ctx)

    def test_context_with_reply(self):
        ctx = build_memory_refresh_context(
            inbound_body="hello",
            inbound_subject=None,
            parsed_updates={},
            manual_snapshot=None,
            selected_model_name=None,
            rule_engine_decision=None,
            reply_text="Great job!",
        )
        self.assertEqual(ctx["coach_reply"], "Great job!")


class TestMaybePostReplyMemoryRefresh(unittest.TestCase):

    def _make_kwargs(self, **overrides):
        defaults = dict(
            athlete_id="ath_123",
            inbound_body="I ran 5k today",
            inbound_subject="Update",
            reply_text="Great work!",
            reply_kind="coaching",
            parsed_updates={},
            manual_snapshot=None,
            selected_model_name="gpt-4o",
            rule_engine_decision=None,
            log=MagicMock(),
            get_memory_notes_fn=MagicMock(return_value=[]),
            get_continuity_summary_fn=MagicMock(return_value=None),
            replace_memory_fn=MagicMock(return_value=True),
        )
        defaults.update(overrides)
        return defaults

    def test_skips_when_gate_rejects(self):
        kwargs = self._make_kwargs(reply_kind="off_topic")
        maybe_post_reply_memory_refresh(**kwargs)
        kwargs["log"].assert_called_once()
        self.assertEqual(kwargs["log"].call_args[1]["result"], "memory_refresh_skipped_by_gate")
        kwargs["get_memory_notes_fn"].assert_not_called()

    @patch("coaching_memory.run_candidate_memory_refresh")
    @patch("coaching_memory.apply_candidate_refresh")
    def test_calls_candidate_refresh_and_persists(self, mock_reducer, mock_refresh):
        mock_refresh.return_value = {
            "candidates": [],
            "continuity": {
                "summary": "Training started",
                "last_recommendation": "Easy runs this week",
                "open_loops": [],
            },
        }
        mock_reducer.return_value = {
            "memory_notes": [],
            "continuity_summary": {
                "summary": "Training started",
                "last_recommendation": "Easy runs this week",
                "open_loops": [],
                "updated_at": 1710700000,
            },
        }
        kwargs = self._make_kwargs()
        maybe_post_reply_memory_refresh(**kwargs)

        mock_refresh.assert_called_once()
        kwargs["replace_memory_fn"].assert_called_once()
        call_args = kwargs["replace_memory_fn"].call_args
        self.assertEqual(call_args[0][0], "ath_123")
        kwargs["log"].assert_called_once()
        self.assertEqual(kwargs["log"].call_args[1]["result"], "memory_refresh_persisted")

    @patch("coaching_memory.run_candidate_memory_refresh")
    def test_fails_closed_on_refresh_error(self, mock_refresh):
        from skills.memory.unified.errors import MemoryRefreshError
        mock_refresh.side_effect = MemoryRefreshError("LLM failed")
        kwargs = self._make_kwargs()
        maybe_post_reply_memory_refresh(**kwargs)
        kwargs["log"].assert_called_once()
        self.assertEqual(kwargs["log"].call_args[1]["result"], "memory_refresh_failed")
        kwargs["replace_memory_fn"].assert_not_called()

    @patch("coaching_memory.apply_candidate_refresh")
    @patch("coaching_memory.run_candidate_memory_refresh")
    def test_fails_closed_on_persistence_failure(self, mock_refresh, mock_reducer):
        mock_refresh.return_value = {
            "candidates": [],
            "continuity": {
                "summary": "s",
                "last_recommendation": "r",
                "open_loops": [],
            },
        }
        mock_reducer.return_value = {
            "memory_notes": [],
            "continuity_summary": {
                "summary": "s",
                "last_recommendation": "r",
                "open_loops": [],
                "updated_at": 1710700000,
            },
        }
        kwargs = self._make_kwargs()
        kwargs["replace_memory_fn"].return_value = False
        maybe_post_reply_memory_refresh(**kwargs)
        kwargs["log"].assert_called_once()
        self.assertEqual(kwargs["log"].call_args[1]["result"], "memory_refresh_failed")

    @patch("coaching_memory.apply_candidate_refresh")
    @patch("coaching_memory.run_candidate_memory_refresh")
    def test_reads_current_memory_state(self, mock_refresh, mock_reducer):
        mock_refresh.return_value = {
            "candidates": [],
            "continuity": {
                "summary": "s",
                "last_recommendation": "r",
                "open_loops": [],
            },
        }
        mock_reducer.return_value = {
            "memory_notes": [],
            "continuity_summary": {
                "summary": "s",
                "last_recommendation": "r",
                "open_loops": [],
                "updated_at": 1710700000,
            },
        }
        memory_notes = [{"memory_note_id": "f1", "summary": "Marathon goal"}]
        continuity = {"summary": "Last session was good"}
        kwargs = self._make_kwargs(
            get_memory_notes_fn=MagicMock(return_value=memory_notes),
            get_continuity_summary_fn=MagicMock(return_value=continuity),
        )
        maybe_post_reply_memory_refresh(**kwargs)

        kwargs["get_memory_notes_fn"].assert_called_once_with("ath_123")
        kwargs["get_continuity_summary_fn"].assert_called_once_with("ath_123")

        call_kwargs = mock_refresh.call_args[1]
        self.assertEqual(call_kwargs["current_memory_notes"], memory_notes)
        self.assertEqual(call_kwargs["current_continuity"], continuity)


if __name__ == "__main__":
    unittest.main()
