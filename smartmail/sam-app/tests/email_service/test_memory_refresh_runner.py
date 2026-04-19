import unittest

from sectioned_memory_contract import (
    MAX_OPEN_LOOP_CHARS,
    ContinuitySummary,
    SectionedMemoryContractError,
    empty_sectioned_memory,
)
from skills.memory.refresh_helpers import stale_continuity_carryover_detected
from skills.memory.sectioned.runner import _clean_sectioned_validated_output
from skills.memory.sectioned.validator import validate_sectioned_candidate_response


def _validated_with_loop(loop: str) -> dict:
    return {
        "candidates": [],
        "continuity": {
            "summary": "Current coaching context updated.",
            "last_recommendation": "Keep training steady.",
            "open_loops": [loop],
        },
    }


class TestMemoryRefreshRunner(unittest.TestCase):
    def test_answered_open_loop_is_pruned_when_coach_moves_on(self):
        validated = _validated_with_loop("Confirm travel dates for the race week.")
        current_continuity = {
            "summary": "Travel planning still unresolved.",
            "last_recommendation": "Send race-week travel dates.",
            "open_loops": ["Confirm travel dates for the race week."],
        }
        interaction_context = {
            "inbound_email": (
                "Travel dates are now locked: I fly out on Thursday, May 14 and come back on "
                "Monday, May 18."
            ),
            "coach_reply": "Perfect. Keep the week otherwise unchanged and protect sleep.",
        }

        cleaned = _clean_sectioned_validated_output(
            validated=validated,
            sectioned_memory=empty_sectioned_memory(),
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )

        self.assertEqual(cleaned["continuity"]["open_loops"], [])

    def test_open_loop_stays_when_coach_explicitly_reasks_for_same_topic(self):
        validated = _validated_with_loop("Confirm travel dates for the race week.")
        current_continuity = {
            "summary": "Travel planning still unresolved.",
            "last_recommendation": "Send race-week travel dates.",
            "open_loops": ["Confirm travel dates for the race week."],
        }
        interaction_context = {
            "inbound_email": "I should know the travel plan soon, but I do not have dates yet.",
            "coach_reply": "Please confirm the travel dates for race week once they are final.",
        }

        cleaned = _clean_sectioned_validated_output(
            validated=validated,
            sectioned_memory=empty_sectioned_memory(),
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )

        self.assertEqual(
            cleaned["continuity"]["open_loops"],
            ["Confirm travel dates for the race week."],
        )


class TestOpenLoopMaxLength(unittest.TestCase):
    """Verify that oversized open_loop items are rejected or truncated at each layer."""

    def test_contract_rejects_open_loop_exceeding_max_chars(self):
        oversized = "x" * (MAX_OPEN_LOOP_CHARS + 1)
        with self.assertRaises(SectionedMemoryContractError):
            ContinuitySummary.from_dict({
                "summary": "ok",
                "last_recommendation": "ok",
                "open_loops": [oversized],
                "updated_at": 1000,
            })

    def test_contract_accepts_open_loop_at_max_chars(self):
        at_limit = "x" * MAX_OPEN_LOOP_CHARS
        result = ContinuitySummary.from_dict({
            "summary": "ok",
            "last_recommendation": "ok",
            "open_loops": [at_limit],
            "updated_at": 1000,
        })
        self.assertEqual(list(result.open_loops), [at_limit])

    def test_validator_truncates_oversized_open_loop(self):
        oversized = "y" * (MAX_OPEN_LOOP_CHARS + 500)
        payload = {
            "candidates": [],
            "continuity": {
                "summary": "ok",
                "last_recommendation": "ok",
                "open_loops": [oversized],
            },
        }
        validated = validate_sectioned_candidate_response(payload)
        loop = validated["continuity"]["open_loops"][0]
        self.assertEqual(len(loop), MAX_OPEN_LOOP_CHARS)
        self.assertEqual(loop, "y" * MAX_OPEN_LOOP_CHARS)


class TestStaleContinuityFallbackExemption(unittest.TestCase):
    """Verify that generic fallback strings don't trigger the staleness detector."""

    def _generic_continuity(self):
        return {
            "summary": "Current coaching context updated.",
            "last_recommendation": "Use the updated current schedule and constraints going forward.",
            "open_loops": [],
        }

    def test_generic_fallback_does_not_trigger_staleness(self):
        """The core bug: generic fallback as prior continuity should never be
        detected as stale carryover, even when the LLM echoes it back."""
        result = stale_continuity_carryover_detected(
            current_continuity=self._generic_continuity(),
            interaction_context={
                "inbound_email": "Sunday check-in: slept 7h, resting HR 58, easy run 40 min.",
                "coach_reply": "Solid check-in. Keep the plan unchanged this week.",
            },
            validated={
                "candidates": [],
                "continuity": self._generic_continuity(),
            },
        )
        self.assertFalse(
            result,
            "Generic fallback continuity must not trigger staleness detection — "
            "this causes a self-perpetuating trap where continuity never recovers.",
        )

    def test_generic_fallback_allows_llm_to_write_fresh_summary(self):
        """When prior continuity is generic, the LLM's fresh summary should survive."""
        fresh_continuity = {
            "summary": "Athlete completed Sunday check-in with solid metrics.",
            "last_recommendation": "Keep plan unchanged, monitor Achilles.",
            "open_loops": ["Report Wednesday PM with resting HR and RPE."],
        }
        result = stale_continuity_carryover_detected(
            current_continuity=self._generic_continuity(),
            interaction_context={
                "inbound_email": "Sunday check-in: slept 7h, resting HR 58, easy run 40 min.",
                "coach_reply": "Solid check-in. Keep the plan unchanged this week.",
            },
            validated={
                "candidates": [],
                "continuity": fresh_continuity,
            },
        )
        self.assertFalse(
            result,
            "Fresh LLM continuity must not be nuked when prior was generic fallback.",
        )

    def test_real_stale_carryover_still_detected(self):
        """Non-generic prior continuity that is echoed without grounding should still fire."""
        old_continuity = {
            "summary": "Athlete is planning a spring triathlon in June.",
            "last_recommendation": "Finalize the swim-bike-run split by Friday.",
            "open_loops": [],
        }
        result = stale_continuity_carryover_detected(
            current_continuity=old_continuity,
            interaction_context={
                # Conversation has moved on - no mention of triathlon or swim-bike-run
                "inbound_email": "Quick question about my Tuesday tempo run pacing.",
                "coach_reply": "For Tuesday tempo, target 8:30/mi for the main set.",
            },
            validated={
                "candidates": [],
                "continuity": {
                    # LLM echoed old content that has nothing to do with current conversation
                    "summary": "Athlete is planning a spring triathlon in June.",
                    "last_recommendation": "Finalize the swim-bike-run split by Friday.",
                    "open_loops": [],
                },
            },
        )
        self.assertTrue(
            result,
            "Real stale carryover (non-generic, ungrounded echo) must still be detected.",
        )

    def test_clean_output_preserves_fresh_continuity_after_generic_fallback(self):
        """End-to-end: _clean_sectioned_validated_output should not nuke fresh
        continuity when the prior state was a generic fallback."""
        fresh_validated = {
            "candidates": [],
            "continuity": {
                "summary": "Athlete reported solid Sunday check-in metrics.",
                "last_recommendation": "Continue plan as-is.",
                "open_loops": ["Await Wednesday PM report with HR and RPE."],
            },
        }
        cleaned = _clean_sectioned_validated_output(
            validated=fresh_validated,
            sectioned_memory=empty_sectioned_memory(),
            current_continuity=self._generic_continuity(),
            interaction_context={
                "inbound_email": "Sunday check-in: slept 7h, resting HR 58, easy run 40 min.",
                "coach_reply": "Solid check-in. Keep the plan unchanged this week.",
            },
        )
        self.assertEqual(
            cleaned["continuity"]["summary"],
            "Athlete reported solid Sunday check-in metrics.",
            "Fresh summary must survive when prior was generic fallback.",
        )
        self.assertEqual(
            cleaned["continuity"]["open_loops"],
            ["Await Wednesday PM report with HR and RPE."],
            "Fresh open loops must survive when prior was generic fallback.",
        )


if __name__ == "__main__":
    unittest.main()
