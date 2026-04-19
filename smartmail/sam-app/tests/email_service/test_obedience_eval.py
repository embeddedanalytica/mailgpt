"""E2E tests for the LLM-based obedience evaluation skill.

Runs in isolation — calls run_obedience_eval() directly with known-bad emails
and verifies that violations are detected and corrections are applied.

Requires: ENABLE_LIVE_LLM_CALLS=true
"""

import os
import re
import unittest

from skills.obedience_eval import run_obedience_eval
from skills.obedience_eval.validator import validate_obedience_eval

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS") == "true"


def _directive(**overrides):
    base = {
        "opening": "Test",
        "main_message": "Brief ack.",
        "content_plan": ["acknowledge"],
        "avoid": [],
        "tone": "calm",
        "recommend_material": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# Validator unit tests (no LLM required)
# ---------------------------------------------------------------------------

class TestObedienceEvalValidator(unittest.TestCase):
    """Unit tests for validate_obedience_eval — no LLM calls."""

    def test_valid_passed_result(self):
        result = validate_obedience_eval({
            "passed": True,
            "violations": [],
            "corrected_email_body": None,
            "reasoning": "Email is compliant.",
        })
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])
        self.assertIsNone(result["corrected_email_body"])

    def test_valid_failed_result(self):
        result = validate_obedience_eval({
            "passed": False,
            "violations": [{
                "violation_type": "reopened_resolved_topic",
                "detail": "Email mentions Achilles despite avoid list.",
            }],
            "corrected_email_body": "Here's your schedule for this week.",
            "reasoning": "Avoid list violation found.",
        })
        self.assertFalse(result["passed"])
        self.assertEqual(len(result["violations"]), 1)
        self.assertEqual(result["violations"][0]["violation_type"], "reopened_resolved_topic")
        self.assertIsNotNone(result["corrected_email_body"])

    def test_passed_true_with_violations_raises(self):
        with self.assertRaises(Exception):
            validate_obedience_eval({
                "passed": True,
                "violations": [{"violation_type": "reopened_resolved_topic", "detail": "x"}],
                "corrected_email_body": None,
                "reasoning": "Inconsistent.",
            })

    def test_passed_false_without_violations_raises(self):
        with self.assertRaises(Exception):
            validate_obedience_eval({
                "passed": False,
                "violations": [],
                "corrected_email_body": "fixed",
                "reasoning": "Inconsistent.",
            })

    def test_passed_false_without_correction_raises(self):
        with self.assertRaises(Exception):
            validate_obedience_eval({
                "passed": False,
                "violations": [{"violation_type": "reopened_resolved_topic", "detail": "x"}],
                "corrected_email_body": None,
                "reasoning": "Missing correction.",
            })

    def test_invalid_violation_type_raises(self):
        with self.assertRaises(Exception):
            validate_obedience_eval({
                "passed": False,
                "violations": [{"violation_type": "made_up_type", "detail": "x"}],
                "corrected_email_body": "fixed",
                "reasoning": "Bad type.",
            })

    def test_missing_reasoning_raises(self):
        with self.assertRaises(Exception):
            validate_obedience_eval({
                "passed": True,
                "violations": [],
                "corrected_email_body": None,
                "reasoning": "",
            })

    def test_all_violation_types_accepted(self):
        for vtype in [
            "reopened_resolved_topic",
            "ignored_latest_constraint",
            "answered_from_stale_context",
            "exceeded_requested_scope",
            "introduced_unsupported_assumption",
            "missed_exact_instruction",
            "physical_presence_implied",
            "metadata_leak",
        ]:
            result = validate_obedience_eval({
                "passed": False,
                "violations": [{"violation_type": vtype, "detail": "test"}],
                "corrected_email_body": "corrected",
                "reasoning": "test",
            })
            self.assertEqual(result["violations"][0]["violation_type"], vtype)


# ---------------------------------------------------------------------------
# LLM-backed e2e tests
# ---------------------------------------------------------------------------

@unittest.skipUnless(_LIVE, "requires ENABLE_LIVE_LLM_CALLS=true")
class TestObedienceEvalE2E(unittest.TestCase):
    """E2E tests that call the real LLM. Run with ENABLE_LIVE_LLM_CALLS=true."""

    def test_forbidden_topic_corrected(self):
        """Email mentions Achilles when avoid says don't — should be caught and fixed."""
        result = run_obedience_eval(
            email_body=(
                "Your Achilles has been quiet this week, which is great. "
                "Here's your schedule: Mon easy 30, Wed easy 40, Sat long 75."
            ),
            directive=_directive(
                avoid=["Do not mention the Achilles"],
                content_plan=["present this week's schedule"],
                main_message="Here's the schedule for this week.",
            ),
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("reopened_resolved_topic", violation_types)
        self.assertNotIn("achilles", result["corrected_email_body"].lower())

    def test_physical_presence_corrected(self):
        """Coach implies physical presence — critical violation, must be removed."""
        result = run_obedience_eval(
            email_body=(
                "Great progress this week. I'll text you the meeting point tonight. "
                "See you Tuesday morning! Here's the plan: easy 30 min jog."
            ),
            directive=_directive(
                content_plan=["present session plan"],
                main_message="Here's the session plan.",
            ),
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("physical_presence_implied", violation_types)
        corrected_lower = result["corrected_email_body"].lower()
        self.assertNotIn("i'll text you", corrected_lower)
        self.assertNotIn("see you", corrected_lower)
        self.assertNotIn("meeting point", corrected_lower)

    def test_scope_exceeded_corrected(self):
        """Narrow directive but bloated email — should be trimmed."""
        long_email = "\n".join([
            "You're cleared for Saturday. No changes needed.",
            "Here's a recap of your week:",
            "- Monday: easy 30",
            "- Tuesday: off",
            "- Wednesday: easy 40",
            "- Thursday: off",
            "- Friday: easy 30",
            "- Saturday: long 75",
            "- Sunday: easy 30",
            "Looking ahead to next week, let's think about adding a tempo session.",
            "Also, your recovery has been going well.",
            "Keep up the good work!",
        ])
        result = run_obedience_eval(
            email_body=long_email,
            directive=_directive(
                content_plan=["confirm Saturday clearance"],
                main_message="Cleared for Saturday.",
            ),
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("exceeded_requested_scope", violation_types)
        # Corrected email should be shorter
        original_lines = [l for l in long_email.strip().split("\n") if l.strip()]
        corrected_lines = [
            l for l in result["corrected_email_body"].strip().split("\n") if l.strip()
        ]
        self.assertLess(len(corrected_lines), len(original_lines))

    def test_unsupported_week_label_corrected(self):
        """Email says 'Week 3' with no continuity context — should be removed."""
        result = run_obedience_eval(
            email_body="This is Week 3 of your build phase. Keep sessions easy this week.",
            directive=_directive(
                content_plan=["present schedule"],
                main_message="Here's the schedule.",
            ),
            continuity_context=None,
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("introduced_unsupported_assumption", violation_types)
        self.assertIsNone(
            re.search(r"\bweek\s+\d+\b", result["corrected_email_body"], re.IGNORECASE),
            "Corrected email should not contain 'Week N' labels",
        )

    def test_clean_email_passes(self):
        """A fully compliant email should pass with no violations."""
        result = run_obedience_eval(
            email_body="Got it. No changes this week.",
            directive=_directive(),
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])
        self.assertIsNone(result["corrected_email_body"])

    def test_multiple_violations_all_corrected(self):
        """Email with multiple violations — all should be detected and fixed."""
        result = run_obedience_eval(
            email_body=(
                "Your Achilles is healing nicely. "
                "This is Week 3 of your build phase. "
                "I'll book the pool lane for Thursday. "
                "Here's a full weekly breakdown plus some bonus recovery tips."
            ),
            directive=_directive(
                avoid=["Do not mention the Achilles"],
                content_plan=["acknowledge check-in"],
                main_message="Brief acknowledgment.",
            ),
            continuity_context=None,
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        # Should catch at least: forbidden topic, unsupported week label, physical presence
        self.assertTrue(
            len(violation_types) >= 2,
            f"Expected at least 2 violation types, got {violation_types}",
        )
        corrected_lower = result["corrected_email_body"].lower()
        self.assertNotIn("achilles", corrected_lower)
        self.assertNotIn("i'll book", corrected_lower)

    def test_metadata_leak_corrected(self):
        """Email contains raw forwarded email headers — should be stripped."""
        result = run_obedience_eval(
            email_body=(
                "No change to the plan this week.\n"
                "---\n"
                "From: athlete@example.com\n"
                "Sent: Sat, 15 Aug 2026 08:15:52 +0000\n"
                "To: coach@geniml.com\n"
                "Subject: Re: Sunday check-in\n"
                "Will follow the plan this week."
            ),
            directive=_directive(
                content_plan=["acknowledge check-in"],
                main_message="No changes.",
            ),
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("metadata_leak", violation_types)
        self.assertNotIn("From:", result["corrected_email_body"])
        self.assertNotIn("Sent:", result["corrected_email_body"])

    def test_standing_rules_restatement_flagged(self):
        """Check-in reply restates unchanged standing rules not in the content_plan."""
        result = run_obedience_eval(
            email_body=(
                "Thanks for the check-in. No change to the plan.\n"
                "Gating rule reminder: if stiffness appears on three consecutive mornings, "
                "drop the long run to 45 minutes.\n"
                "Stop and report immediately for any sharp or worsening pain.\n"
                "Send the usual short bullet check-in at week's end with: "
                "1) sessions completed, 2) symptoms, and 3) sleep/stress."
            ),
            directive=_directive(
                content_plan=["acknowledge check-in, no plan change"],
                main_message="No changes needed.",
            ),
        )
        self.assertFalse(result["passed"])
        violation_types = {v["violation_type"] for v in result["violations"]}
        self.assertIn("exceeded_requested_scope", violation_types)
        # Corrected email should be shorter — standing rules trimmed
        corrected = result["corrected_email_body"]
        self.assertLess(len(corrected), 300)


if __name__ == "__main__":
    unittest.main()
