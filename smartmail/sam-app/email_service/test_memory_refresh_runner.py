import unittest

from skills.memory.unified.runner import _clean_validated_output


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

        cleaned = _clean_validated_output(
            validated=validated,
            existing_facts=[],
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

        cleaned = _clean_validated_output(
            validated=validated,
            existing_facts=[],
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )

        self.assertEqual(
            cleaned["continuity"]["open_loops"],
            ["Confirm travel dates for the race week."],
        )


if __name__ == "__main__":
    unittest.main()
