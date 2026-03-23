import unittest
from pathlib import Path

from skills.coaching_reasoning.doctrine import (
    _CACHE,
    _resolve_sport,
    build_doctrine_context_for_brief,
    list_loaded_files,
    select_doctrine_files,
)
from skills.coaching_reasoning.doctrine.manifest import CORE_UNIVERSAL_FILES, all_registered_doctrine_paths

_DOCTRINE_DIR = Path(__file__).parent / "skills" / "coaching_reasoning" / "doctrine"


def _base_brief(**overrides):
    brief = {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Half marathon",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
            "primary_sport": "running",
            "constraints_summary": "",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
            "risk_recent_history": ["green", "green", "green"],
            "weeks_in_coaching": 4,
        },
        "validated_plan": {},
        "memory_context": {},
        "delivery_context": {"inbound_body": "Solid week — feeling good."},
    }
    brief.update(overrides)
    return brief


class TestManifestIntegrity(unittest.TestCase):
    """Every file referenced in the manifest must exist and be non-empty."""

    def test_all_registered_files_exist(self):
        for rel_path in all_registered_doctrine_paths():
            full = _DOCTRINE_DIR / rel_path
            self.assertTrue(full.exists(), f"Missing doctrine file: {rel_path}")

    def test_all_registered_files_non_empty(self):
        for rel_path in all_registered_doctrine_paths():
            full = _DOCTRINE_DIR / rel_path
            content = full.read_text().strip()
            self.assertTrue(len(content) > 0, f"Empty doctrine file: {rel_path}")


class TestResolveSport(unittest.TestCase):

    def test_exact_match(self):
        self.assertEqual(_resolve_sport("running"), "running")

    def test_alias_marathon(self):
        self.assertEqual(_resolve_sport("marathon"), "running")

    def test_alias_half_marathon(self):
        self.assertEqual(_resolve_sport("half marathon"), "running")

    def test_alias_case_insensitive(self):
        self.assertEqual(_resolve_sport("Marathon"), "running")
        self.assertEqual(_resolve_sport("TRAIL RUNNING"), "running")

    def test_none_returns_none(self):
        self.assertIsNone(_resolve_sport(None))

    def test_empty_returns_none(self):
        self.assertIsNone(_resolve_sport(""))
        self.assertIsNone(_resolve_sport("   "))

    def test_unknown_sport_returns_none(self):
        self.assertIsNone(_resolve_sport("cricket"))


class TestSelectDoctrineFiles(unittest.TestCase):

    def test_always_includes_core(self):
        files = select_doctrine_files(_base_brief())
        for f in CORE_UNIVERSAL_FILES:
            self.assertIn(f, files)

    def test_running_includes_methodology_only_when_sport_running(self):
        files = select_doctrine_files(_base_brief())
        self.assertIn("running/methodology.md", files)
        brief = _base_brief()
        del brief["athlete_context"]["primary_sport"]
        files_no_sport = select_doctrine_files(brief)
        self.assertNotIn("running/methodology.md", files_no_sport)

    def test_neutral_brief_omits_situational_universal(self):
        files = select_doctrine_files(_base_brief())
        self.assertNotIn("universal/return_from_setback.md", files)
        self.assertNotIn("universal/illness_and_low_energy.md", files)
        self.assertNotIn("universal/travel_and_disruption.md", files)
        self.assertNotIn("universal/intensity_reintroduction.md", files)

    def test_yellow_history_triggers_setback_doctrine(self):
        brief = _base_brief(
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "green"],
                "weeks_in_coaching": 4,
            },
        )
        files = select_doctrine_files(brief)
        self.assertIn("universal/return_from_setback.md", files)
        self.assertIn("running/injury_return_patterns.md", files)

    def test_pain_in_inbound_triggers_setback(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Mild pain came back after the long run."},
        )
        files = select_doctrine_files(brief)
        self.assertIn("universal/return_from_setback.md", files)

    def test_illness_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Caught a cold — low energy all week."},
        )
        self.assertIn("universal/illness_and_low_energy.md", select_doctrine_files(brief))

    def test_illness_synonym_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "I'm a bit under the weather and pretty drained."},
        )
        self.assertIn("universal/illness_and_low_energy.md", select_doctrine_files(brief))

    def test_travel_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "On a work trip — hotel gym only and poor sleep."},
        )
        self.assertIn("universal/travel_and_disruption.md", select_doctrine_files(brief))

    def test_disruption_synonym_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "This was a crazy week and the schedule blew up."},
        )
        self.assertIn("universal/travel_and_disruption.md", select_doctrine_files(brief))

    def test_intensity_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Ready to add threshold work again next week."},
        )
        self.assertIn("universal/intensity_reintroduction.md", select_doctrine_files(brief))

    def test_intensity_synonym_signals(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Can we bring back some faster work or a progression run?"}
        )
        self.assertIn("universal/intensity_reintroduction.md", select_doctrine_files(brief))

    def test_yellow_risk_flag_triggers_common_failures(self):
        brief = _base_brief(
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "yellow",
                "today_action": "adjust",
                "clarification_needed": False,
                "risk_recent_history": ["green", "green"],
                "weeks_in_coaching": 4,
            },
        )
        self.assertIn("universal/common_coaching_failures.md", select_doctrine_files(brief))

    def test_setback_triggers_common_failures_backstop(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Pain flared again after the long run."},
        )
        self.assertIn("universal/common_coaching_failures.md", select_doctrine_files(brief))

    def test_prescription_signals_running_only(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Can we bump weekly volume and add a tempo?"},
        )
        self.assertIn("running/common_prescription_errors.md", select_doctrine_files(brief))
        brief_no_sport = _base_brief(
            delivery_context={"inbound_body": "Can we bump weekly volume and add a tempo?"},
        )
        del brief_no_sport["athlete_context"]["primary_sport"]
        self.assertNotIn(
            "running/common_prescription_errors.md",
            select_doctrine_files(brief_no_sport),
        )

    def test_plan_the_week_triggers_running_prescription_errors(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Can you map the week and tell me what next week should look like?"},
        )
        self.assertIn("running/common_prescription_errors.md", select_doctrine_files(brief))

    def test_running_recommendations_only_when_justified(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Any book you'd recommend for pacing?"},
        )
        self.assertIn("running/recommendations.md", select_doctrine_files(brief))
        neutral = _base_brief()
        self.assertNotIn("running/recommendations.md", select_doctrine_files(neutral))


class TestBuildDoctrineContextForBrief(unittest.TestCase):

    def test_running_core_and_methodology(self):
        ctx = build_doctrine_context_for_brief(_base_brief())
        self.assertIn("Periodization", ctx)
        self.assertIn("Daniels", ctx)

    def test_neutral_excludes_setback_heading(self):
        ctx = build_doctrine_context_for_brief(_base_brief())
        self.assertNotIn("Return From Setback", ctx)

    def test_setback_includes_heading(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Pain flared after hills — backing off."},
        )
        ctx = build_doctrine_context_for_brief(brief)
        self.assertIn("Return From Setback", ctx)

    def test_non_running_excludes_running_copy(self):
        brief = _base_brief()
        brief["athlete_context"]["primary_sport"] = "cricket"
        ctx = build_doctrine_context_for_brief(brief)
        self.assertNotIn("Daniels", ctx)


class TestListLoadedFiles(unittest.TestCase):

    def test_matches_select(self):
        brief = _base_brief()
        self.assertEqual(list_loaded_files(brief), select_doctrine_files(brief))

    def test_alias_resolves_like_running(self):
        half = _base_brief()
        half["athlete_context"]["primary_sport"] = "half marathon"
        direct = _base_brief()
        direct["athlete_context"]["primary_sport"] = "running"
        self.assertEqual(select_doctrine_files(half), select_doctrine_files(direct))


class TestCaching(unittest.TestCase):

    def setUp(self):
        _CACHE.clear()

    def test_files_cached_after_first_load(self):
        brief = _base_brief()
        build_doctrine_context_for_brief(brief)
        for f in select_doctrine_files(brief):
            self.assertIn(f, _CACHE)

    def test_second_load_uses_cache(self):
        brief = _base_brief()
        first = build_doctrine_context_for_brief(brief)
        keys_after = set(_CACHE.keys())
        second = build_doctrine_context_for_brief(brief)
        self.assertEqual(first, second)
        self.assertEqual(keys_after, set(_CACHE.keys()))


if __name__ == "__main__":
    unittest.main()
