"""Regression tests for last-mile obedience fixtures.

- Fixture integrity tests (no LLM required).
- LLM-backed obedience eval tests for known-bad emails (require ENABLE_LIVE_LLM_CALLS=true).
- Assertion helpers for directive and response expectations.
"""

from __future__ import annotations

import os
import re
import unittest
from typing import Any, Dict, List

from fixtures.obedience import (
    OBEDIENCE_FIXTURES,
    get_fixture,
    get_fixtures_by_type,
)
from response_generation_contract import validate_response_brief

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS") == "true"


# ---------------------------------------------------------------------------
# Taxonomy
# ---------------------------------------------------------------------------

VALID_FAILURE_TYPES = {
    "reopened_resolved_topic",
    "ignored_latest_constraint",
    "answered_from_stale_context",
    "exceeded_requested_scope",
    "introduced_unsupported_assumption",
    "missed_exact_instruction",
}


# ---------------------------------------------------------------------------
# Assertion helpers — usable by later phases with real LLM output
# ---------------------------------------------------------------------------

def assert_directive_expectations(
    directive: Dict[str, Any],
    expectations: Dict[str, Any],
    test_case: unittest.TestCase,
) -> None:
    """Check a coaching directive against fixture expectations."""

    if "reply_action" in expectations:
        test_case.assertEqual(
            directive.get("reply_action"),
            expectations["reply_action"],
            "reply_action mismatch",
        )

    if "content_plan_max_items" in expectations:
        content_plan = directive.get("content_plan", [])
        test_case.assertLessEqual(
            len(content_plan),
            expectations["content_plan_max_items"],
            f"content_plan has {len(content_plan)} items, max {expectations['content_plan_max_items']}",
        )

    if "avoid_must_contain_any" in expectations:
        avoid = directive.get("avoid", [])
        avoid_text = " ".join(avoid).lower()
        keywords = expectations["avoid_must_contain_any"]
        test_case.assertTrue(
            any(kw.lower() in avoid_text for kw in keywords),
            f"avoid list must mention one of {keywords}, got: {avoid}",
        )

    if "main_message_must_contain_any" in expectations:
        main_message = directive.get("main_message", "").lower()
        keywords = expectations["main_message_must_contain_any"]
        test_case.assertTrue(
            any(kw.lower() in main_message for kw in keywords),
            f"main_message must mention one of {keywords}",
        )


def assert_response_expectations(
    response_text: str,
    expectations: Dict[str, Any],
    test_case: unittest.TestCase,
) -> None:
    """Check a final email response against fixture expectations."""

    if expectations.get("suppressed"):
        test_case.assertEqual(
            response_text, "",
            "Response should be suppressed (empty)",
        )
        return

    if "max_sentences" in expectations:
        sentences = [s.strip() for s in re.split(r'[.!?]+', response_text) if s.strip()]
        test_case.assertLessEqual(
            len(sentences),
            expectations["max_sentences"],
            f"Response has {len(sentences)} sentences, max {expectations['max_sentences']}",
        )

    if "must_not_contain" in expectations:
        lower_text = response_text.lower()
        for phrase in expectations["must_not_contain"]:
            test_case.assertNotIn(
                phrase.lower(),
                lower_text,
                f"Response must not contain '{phrase}'",
            )

    if "must_contain_any" in expectations:
        lower_text = response_text.lower()
        keywords = expectations["must_contain_any"]
        test_case.assertTrue(
            any(kw.lower() in lower_text for kw in keywords),
            f"Response must contain one of {keywords}",
        )

    if "must_contain_any_2" in expectations:
        lower_text = response_text.lower()
        keywords = expectations["must_contain_any_2"]
        test_case.assertTrue(
            any(kw.lower() in lower_text for kw in keywords),
            f"Response must contain one of {keywords}",
        )

    if "must_not_match_pattern" in expectations:
        pattern = expectations["must_not_match_pattern"]
        test_case.assertIsNone(
            re.search(pattern, response_text),
            f"Response must not match pattern '{pattern}'",
        )


# ---------------------------------------------------------------------------
# Phase 1 tests: fixture integrity + contract compliance (no LLM)
# ---------------------------------------------------------------------------

class TestFixtureIntegrity(unittest.TestCase):
    """Ensure fixture data is well-formed and internally consistent."""

    def test_all_fixtures_have_required_fields(self):
        required = {"id", "name", "failure_type", "description", "response_brief",
                     "directive_expectations", "response_expectations"}
        for f in OBEDIENCE_FIXTURES:
            with self.subTest(fixture=f["id"]):
                self.assertTrue(
                    required.issubset(set(f.keys())),
                    f"Fixture {f['id']} missing fields: {required - set(f.keys())}",
                )

    def test_all_fixture_ids_unique(self):
        ids = [f["id"] for f in OBEDIENCE_FIXTURES]
        self.assertEqual(len(ids), len(set(ids)), f"Duplicate fixture IDs: {ids}")

    def test_all_failure_types_valid(self):
        for f in OBEDIENCE_FIXTURES:
            with self.subTest(fixture=f["id"]):
                self.assertIn(
                    f["failure_type"],
                    VALID_FAILURE_TYPES,
                    f"Unknown failure_type: {f['failure_type']}",
                )

    def test_taxonomy_coverage(self):
        """At least one fixture per failure type."""
        covered = {f["failure_type"] for f in OBEDIENCE_FIXTURES}
        # We don't require answered_from_stale_context yet — it needs
        # multi-turn context that single-brief fixtures can't represent.
        required_coverage = VALID_FAILURE_TYPES - {"answered_from_stale_context"}
        missing = required_coverage - covered
        self.assertFalse(
            missing,
            f"No fixtures for failure types: {missing}",
        )

    def test_get_fixture_lookup(self):
        f = get_fixture("OB-ES-001")
        self.assertEqual(f["name"], "keep_it_short")

    def test_get_fixture_missing_raises(self):
        with self.assertRaises(KeyError):
            get_fixture("DOES-NOT-EXIST")

    def test_get_fixtures_by_type(self):
        results = get_fixtures_by_type("exceeded_requested_scope")
        self.assertGreater(len(results), 0)
        for f in results:
            self.assertEqual(f["failure_type"], "exceeded_requested_scope")


class TestFixtureBriefsPassContract(unittest.TestCase):
    """Every fixture's response_brief must pass the existing ResponseBrief contract."""

    def test_all_briefs_validate(self):
        for f in OBEDIENCE_FIXTURES:
            with self.subTest(fixture=f["id"]):
                validate_response_brief(f["response_brief"])


# ---------------------------------------------------------------------------
# LLM-backed obedience eval tests for known-bad emails
# ---------------------------------------------------------------------------

@unittest.skipUnless(_LIVE, "requires ENABLE_LIVE_LLM_CALLS=true")
class TestObedienceEvalCatchesKnownBadEmails(unittest.TestCase):
    """Verify the LLM-based obedience eval detects and corrects known-bad patterns."""

    @classmethod
    def setUpClass(cls):
        from skills.obedience_eval import run_obedience_eval
        cls._run = staticmethod(run_obedience_eval)

    def test_forbidden_topic_leaked_detected(self):
        """OB-RT-001: email mentions Achilles when avoid says don't."""
        result = self._run(
            email_body=(
                "Your Achilles has been quiet this week, which is great. "
                "Here's your schedule: Mon easy 30, Wed easy 40, Sat long 75."
            ),
            directive={
                "avoid": ["Do not mention the Achilles"],
                "content_plan": ["present schedule"],
                "main_message": "Here's the schedule.",
            },
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("reopened_resolved_topic", vtypes)
        self.assertNotIn("achilles", result["corrected_email_body"].lower())

    def test_scope_exceeded_detected(self):
        """OB-ES-001: narrow ask gets a long email."""
        bad_email = "\n".join([
            "You're cleared for the weekend.",
            "Here's a recap of your week:",
            "- Monday: easy 30",
            "- Tuesday: off",
            "- Wednesday: easy 40",
            "- Thursday: off",
            "- Friday: easy 30",
            "- Saturday: long 75",
            "- Sunday: easy 30",
            "Looking ahead to next week, let's think about adding a tempo session.",
            "Also, your Achilles monitoring is going well.",
            "Keep up the good work!",
        ])
        result = self._run(
            email_body=bad_email,
            directive={
                "avoid": [],
                "content_plan": ["confirm weekend"],
                "main_message": "Cleared for weekend.",
            },
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("exceeded_requested_scope", vtypes)
        corrected_lines = [l for l in result["corrected_email_body"].strip().split("\n") if l.strip()]
        original_lines = [l for l in bad_email.strip().split("\n") if l.strip()]
        self.assertLess(len(corrected_lines), len(original_lines))

    def test_unsupported_week_label_detected(self):
        """OB-UA-001: email says 'Week 3' with no continuity context."""
        result = self._run(
            email_body="This is Week 3 of your build phase. Keep sessions easy.",
            directive={
                "avoid": [],
                "content_plan": ["present schedule"],
                "main_message": "Here's the schedule.",
            },
            continuity_context=None,
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("introduced_unsupported_assumption", vtypes)

    def test_format_constraint_violated_detected(self):
        """OB-MI-001 pattern: email exceeds line limit."""
        result = self._run(
            email_body="Line 1\nLine 2\nLine 3\nLine 4\nLine 5",
            directive={
                "avoid": ["Do not exceed 3 lines max"],
                "content_plan": ["sessions", "caps", "calf rule"],
                "main_message": "Three items.",
            },
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("ignored_latest_constraint", vtypes)
        corrected_lines = [l for l in result["corrected_email_body"].strip().split("\n") if l.strip()]
        self.assertLessEqual(len(corrected_lines), 3)

    def test_clean_email_passes_all_checks(self):
        """A well-behaved email should pass."""
        result = self._run(
            email_body="You're cleared for Saturday. No changes needed.",
            directive={
                "avoid": ["Do not mention the Achilles"],
                "content_plan": ["confirm weekend"],
                "main_message": "Cleared.",
            },
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])
        self.assertIsNone(result["corrected_email_body"])


@unittest.skipUnless(_LIVE, "requires ENABLE_LIVE_LLM_CALLS=true")
class TestObedienceEvalWithFixtureDirectives(unittest.TestCase):
    """Cross-check: known-good and known-bad emails against fixture directives."""

    @classmethod
    def setUpClass(cls):
        from skills.obedience_eval import run_obedience_eval
        cls._run = staticmethod(run_obedience_eval)

    def test_fixture_rt001_good_email_passes(self):
        """If the writer follows the avoid list, the eval should pass."""
        result = self._run(
            email_body="Here's your week: Mon easy 30, Wed easy 40, Sat long 75.",
            directive={
                "avoid": ["Do not mention the Achilles", "Do not re-ask about the Achilles"],
                "content_plan": ["present this week's schedule"],
                "main_message": "Schedule for this week.",
            },
        )
        self.assertTrue(result["passed"])

    def test_fixture_sc001_stale_email_caught(self):
        """Email references 4 days when athlete updated to 5."""
        result = self._run(
            email_body=(
                "Sticking with your 4 days per week schedule. "
                "Here's the plan: Mon, Wed, Sat, Sun."
            ),
            directive={
                "avoid": ["Do not mention 4 days per week"],
                "content_plan": ["present updated 5-day schedule"],
                "main_message": "Updated to 5 days with Friday added.",
            },
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("reopened_resolved_topic", vtypes)

    def test_fixture_rt002_reopened_question_caught(self):
        """Coach re-asks about Tuesday when it was already confirmed."""
        result = self._run(
            email_body="Would Tuesday still work for your quality session?",
            directive={
                "avoid": ["Do not re-ask about Tuesday"],
                "content_plan": ["present the plan"],
                "main_message": "Here's the plan with Tuesday quality session.",
            },
        )
        self.assertFalse(result["passed"])
        vtypes = {v["violation_type"] for v in result["violations"]}
        self.assertIn("reopened_resolved_topic", vtypes)


class TestNewFixtureIntegrity(unittest.TestCase):
    """Verify new Phase 7 fixtures are well-formed."""

    def test_answered_from_stale_context_fixtures_exist(self):
        fixtures = get_fixtures_by_type("answered_from_stale_context")
        self.assertGreaterEqual(len(fixtures), 2, "Expected at least 2 stale-context fixtures")

    def test_new_fixture_ids_are_valid(self):
        new_ids = {"OB-SC-001", "OB-SC-002", "OB-RT-002", "OB-ES-003", "OB-MI-002"}
        all_ids = {f["id"] for f in OBEDIENCE_FIXTURES}
        for fid in new_ids:
            self.assertIn(fid, all_ids, f"Missing new fixture: {fid}")

    def test_all_new_briefs_validate(self):
        new_ids = {"OB-SC-001", "OB-SC-002", "OB-RT-002", "OB-ES-003", "OB-MI-002"}
        for fid in new_ids:
            with self.subTest(fixture=fid):
                f = get_fixture(fid)
                validate_response_brief(f["response_brief"])

    def test_full_taxonomy_coverage(self):
        """All 6 failure types now have at least one fixture."""
        covered = {f["failure_type"] for f in OBEDIENCE_FIXTURES}
        self.assertEqual(
            covered,
            VALID_FAILURE_TYPES,
            f"Missing coverage: {VALID_FAILURE_TYPES - covered}",
        )


if __name__ == "__main__":
    unittest.main()
