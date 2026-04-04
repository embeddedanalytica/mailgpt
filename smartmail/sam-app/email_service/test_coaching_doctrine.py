import unittest
from pathlib import Path

from skills.coaching_reasoning.doctrine import (
    CATEGORY_BUDGETS,
    VALID_CATEGORIES,
    VALID_COST_TIERS,
    VALID_SCOPES,
    _CACHE,
    _META_CACHE,
    _apply_category_budgets,
    _parse_frontmatter,
    _resolve_sport,
    _select_optional_candidates,
    _signal_blob,
    build_doctrine_selection_trace,
    build_doctrine_context_for_brief,
    derive_situation_tags,
    derive_turn_purpose,
    get_doctrine_metadata,
    list_loaded_files,
    select_doctrine_files,
)
from skills.coaching_reasoning.doctrine.manifest import (
    CORE_UNIVERSAL_FILES,
    LEGACY_UNIVERSAL_FILES,
    all_registered_doctrine_paths,
)

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


def _planning_brief(**overrides):
    brief = _base_brief(
        delivery_context={"inbound_body": "Can you map the week and tell me what next week should look like?"},
    )
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
        files = select_doctrine_files(_planning_brief())
        self.assertIn("running/methodology.md", files)
        brief = _planning_brief()
        del brief["athlete_context"]["primary_sport"]
        files_no_sport = select_doctrine_files(brief)
        self.assertNotIn("running/methodology.md", files_no_sport)

    def test_neutral_running_brief_omits_methodology_after_phase3(self):
        files = select_doctrine_files(_base_brief())
        self.assertNotIn("running/methodology.md", files)

    def test_milestone_turn_loads_relationship_arc(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "I just finished the race and it feels like a real milestone."},
        )
        self.assertIn("universal/relationship_arc.md", select_doctrine_files(brief))

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
        self.assertNotIn("universal/return_from_setback.md", files)
        self.assertNotIn("running/injury_return_patterns.md", files)
        self.assertNotIn("universal/common_coaching_failures.md", files)

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


class TestTurnPurposeDerivation(unittest.TestCase):

    def test_reply_mode_clarification_overrides(self):
        brief = _base_brief(
            reply_mode="clarification",
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "yellow",
                "today_action": "adjust",
                "clarification_needed": True,
                "risk_recent_history": ["yellow", "green", "green"],
                "weeks_in_coaching": 4,
            },
            delivery_context={"inbound_body": "Pain flared after the run. Should I train tomorrow?"},
        )
        self.assertEqual(derive_turn_purpose(brief), "clarification")

    def test_intake_mode_maps_to_intake(self):
        brief = _base_brief(reply_mode="intake")
        self.assertEqual(derive_turn_purpose(brief), "intake")

    def test_milestone_or_reflection_is_combined_purpose(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "I just ran a PR. What have you learned about me?"},
        )
        self.assertEqual(derive_turn_purpose(brief), "milestone_or_reflection")

    def test_setback_management_requires_no_real_planning_ask(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Travel this week with jet lag and poor sleep."},
        )
        self.assertEqual(derive_turn_purpose(brief), "setback_management")

    def test_planning_beats_setback_when_week_is_being_built(self):
        brief = _base_brief(
            delivery_context={
                "inbound_body": "I'm traveling next week. Can you map the week around that?"
            },
        )
        self.assertEqual(derive_turn_purpose(brief), "planning")

    def test_return_to_load_requires_setback_and_progression(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Shin is quiet again. Can I bring back tempo next week?"},
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "yellow", "green"],
                "weeks_in_coaching": 4,
            },
        )
        self.assertEqual(derive_turn_purpose(brief), "return_to_load")

    def test_plan_mutation_edits_existing_structure(self):
        brief = _base_brief(
            validated_plan={"weekly_skeleton": {"tue": "tempo", "wed": "easy"}},
            delivery_context={"inbound_body": "Can we swap Tuesday and Wednesday this week?"},
        )
        self.assertEqual(derive_turn_purpose(brief), "plan_mutation")

    def test_week_level_rework_biases_to_planning(self):
        brief = _base_brief(
            validated_plan={"weekly_skeleton": {"tue": "tempo", "wed": "easy"}},
            delivery_context={"inbound_body": "Can you rework next week and map the whole week around travel?"},
        )
        self.assertEqual(derive_turn_purpose(brief), "planning")

    def test_direct_question_without_replanning_is_lightweight(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Can I swap my easy run to Friday?"},
            validated_plan={},
        )
        self.assertEqual(derive_turn_purpose(brief), "lightweight_answer")

    def test_default_is_simple_acknowledgment(self):
        self.assertEqual(derive_turn_purpose(_base_brief()), "simple_acknowledgment")


class TestSituationTagDerivation(unittest.TestCase):

    def test_tags_include_strengths(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "I just ran a personal best and want to reflect on the block."},
        )
        self.assertEqual(
            derive_situation_tags(brief),
            {"milestone": "strong", "reflection": "strong"},
        )

    def test_setback_is_weak_on_history_only(self):
        brief = _base_brief(
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "green", "green"],
                "weeks_in_coaching": 4,
            },
        )
        self.assertEqual(derive_situation_tags(brief)["setback"], "weak")

    def test_travel_in_constraints_is_weak(self):
        brief = _base_brief(
            athlete_context={
                "goal_summary": "Half marathon",
                "experience_level": "intermediate",
                "structure_preference": "flexibility",
                "primary_sport": "running",
                "constraints_summary": "Travel to Boston with hotel gym only",
            },
        )
        self.assertEqual(derive_situation_tags(brief)["travel"], "weak")

    def test_prescription_tag_is_strong_for_week_build(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Can you map the week and tell me what next week should look like?"},
        )
        self.assertEqual(derive_situation_tags(brief)["prescription"], "strong")

    def test_clarification_needed_tag_is_strong(self):
        brief = _base_brief(
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": True,
                "risk_recent_history": ["green", "green", "green"],
                "weeks_in_coaching": 4,
            },
        )
        self.assertEqual(derive_situation_tags(brief)["clarification_needed"], "strong")


class TestDoctrineTrace(unittest.TestCase):

    def test_trace_exposes_phase1_classification_without_loading_changes(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Shin is quiet again. Can I bring back tempo next week?"},
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "yellow", "green"],
                "weeks_in_coaching": 4,
            },
        )
        trace = build_doctrine_selection_trace(brief)
        self.assertEqual(trace["turn_purpose"], "return_to_load")
        self.assertEqual(trace["loaded_files"], select_doctrine_files(brief))
        self.assertEqual(trace["posture"], "cautious_progress")
        self.assertEqual(trace["trajectory"], "recovering")
        self.assertEqual(trace["response_shape"], "safety_then_next_step")
        self.assertTrue(trace["purpose_micro_avoid"])
        self.assertIn("loaded_file_reasons", trace)
        self.assertIn("dropped_files", trace)
        self.assertIn("skipped_files", trace)
        self.assertLessEqual(len(trace["skipped_files"]), 3)
        self.assertEqual(
            trace["situation_tags"][0],
            {"tag": "intensity_return", "strength": "strong"},
        )

    def test_trace_skip_reasons_include_purpose_mismatch_candidates(self):
        trace = build_doctrine_selection_trace(_base_brief())
        self.assertTrue(trace["skipped_files"])
        self.assertTrue(
            any("mismatch" in reason or "not explicit" in reason for reason in trace["skipped_files"].values())
        )

    def test_trace_records_budget_drops_on_simple_turns(self):
        brief = _base_brief(
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "green",
                "today_action": "do planned",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "green", "green"],
                "weeks_in_coaching": 4,
            },
        )
        trace = build_doctrine_selection_trace(brief)
        self.assertIn("universal/return_from_setback.md", trace["dropped_files"])


class TestDoctrineRoutingTable(unittest.TestCase):

    def test_selector_routing_examples(self):
        cases = [
            {
                "name": "simple_ack_stays_cheap",
                "brief": _base_brief(
                    delivery_context={"inbound_body": "Sounds good. Starting Monday."},
                ),
                "purpose": "simple_acknowledgment",
                "must_load": {
                    "universal/core.md",
                    "universal/authority_and_override_rules.md",
                },
                "must_not_load": {
                    "running/methodology.md",
                    "universal/relationship_arc.md",
                    "universal/common_coaching_failures.md",
                },
            },
            {
                "name": "week_planning_loads_methodology",
                "brief": _planning_brief(),
                "purpose": "planning",
                "must_load": {
                    "running/methodology.md",
                    "running/common_prescription_errors.md",
                },
                "must_not_load": {
                    "universal/relationship_arc.md",
                },
            },
            {
                "name": "milestone_loads_relationship_arc",
                "brief": _base_brief(
                    delivery_context={
                        "inbound_body": "I finished the race today and it feels like a real milestone."
                    },
                ),
                "purpose": "milestone_or_reflection",
                "must_load": {
                    "universal/relationship_arc.md",
                },
                "must_not_load": {
                    "running/methodology.md",
                },
            },
            {
                "name": "return_to_load_loads_comeback_doctrine",
                "brief": _base_brief(
                    delivery_context={"inbound_body": "Shin is quiet again. Can I bring back tempo next week?"},
                    decision_context={
                        "track": "main_build",
                        "phase": "build",
                        "risk_flag": "green",
                        "today_action": "do planned",
                        "clarification_needed": False,
                        "risk_recent_history": ["yellow", "yellow", "green"],
                        "weeks_in_coaching": 4,
                    },
                ),
                "purpose": "return_to_load",
                "must_load": {
                    "universal/return_from_setback.md",
                    "universal/intensity_reintroduction.md",
                    "running/injury_return_patterns.md",
                    "universal/common_coaching_failures.md",
                },
                "must_not_load": {
                    "universal/relationship_arc.md",
                },
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                trace = build_doctrine_selection_trace(case["brief"])
                loaded = set(trace["loaded_files"])

                self.assertEqual(trace["turn_purpose"], case["purpose"])
                for path in case["must_load"]:
                    self.assertIn(path, loaded)
                for path in case["must_not_load"]:
                    self.assertNotIn(path, loaded)

    def test_selector_trace_examples(self):
        cases = [
            {
                "name": "simple_turn_records_budget_drop",
                "brief": _base_brief(
                    decision_context={
                        "track": "main_build",
                        "phase": "build",
                        "risk_flag": "green",
                        "today_action": "do planned",
                        "clarification_needed": False,
                        "risk_recent_history": ["yellow", "green", "green"],
                        "weeks_in_coaching": 4,
                    },
                    delivery_context={"inbound_body": "Sounds good. Starting Monday."},
                ),
                "purpose": "simple_acknowledgment",
                "required_tags": {("setback", "weak")},
                "required_loaded_reasons": {
                    "universal/core.md": "always_on",
                    "universal/authority_and_override_rules.md": "always_on",
                },
                "required_dropped_files": {"universal/return_from_setback.md"},
            },
            {
                "name": "planning_trace_explains_methodology_load",
                "brief": _planning_brief(),
                "purpose": "planning",
                "required_tags": {("prescription", "strong")},
                "required_loaded_reasons": {
                    "running/methodology.md": "purpose=planning",
                    "running/common_prescription_errors.md": "purpose=planning",
                },
                "required_dropped_files": set(),
            },
            {
                "name": "return_to_load_trace_explains_backstop",
                "brief": _base_brief(
                    delivery_context={"inbound_body": "Shin is quiet again. Can I bring back tempo next week?"},
                    decision_context={
                        "track": "main_build",
                        "phase": "build",
                        "risk_flag": "green",
                        "today_action": "do planned",
                        "clarification_needed": False,
                        "risk_recent_history": ["yellow", "yellow", "green"],
                        "weeks_in_coaching": 4,
                    },
                ),
                "purpose": "return_to_load",
                "required_tags": {
                    ("setback", "strong"),
                    ("intensity_return", "strong"),
                    ("prescription", "strong"),
                },
                "required_loaded_reasons": {
                    "universal/return_from_setback.md": "purpose=return_to_load",
                    "universal/intensity_reintroduction.md": "purpose=return_to_load",
                    "running/injury_return_patterns.md": "purpose=return_to_load",
                    "universal/common_coaching_failures.md": "multiple_active_situations",
                },
                "required_dropped_files": set(),
            },
        ]

        for case in cases:
            with self.subTest(case["name"]):
                trace = build_doctrine_selection_trace(case["brief"])
                tags = {(item["tag"], item["strength"]) for item in trace["situation_tags"]}

                self.assertEqual(trace["turn_purpose"], case["purpose"])
                self.assertTrue(case["required_tags"].issubset(tags))

                for path, reason in case["required_loaded_reasons"].items():
                    self.assertEqual(trace["loaded_file_reasons"].get(path), reason)

                for path in case["required_dropped_files"]:
                    self.assertIn(path, trace["dropped_files"])


class TestBuildDoctrineContextForBrief(unittest.TestCase):

    def test_running_core_and_methodology(self):
        ctx = build_doctrine_context_for_brief(_planning_brief())
        self.assertIn("periodization", ctx.lower())
        self.assertIn("Daniels", ctx)

    def test_neutral_excludes_setback_heading(self):
        ctx = build_doctrine_context_for_brief(_base_brief())
        self.assertNotIn("Return From Setback", ctx)
        self.assertNotIn("Daniels", ctx)

    def test_setback_includes_heading(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Pain flared after hills — backing off."},
        )
        ctx = build_doctrine_context_for_brief(brief)
        self.assertIn("Return From Setback", ctx)

    def test_non_running_excludes_running_copy(self):
        brief = _planning_brief()
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
        _META_CACHE.clear()

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

    def test_metadata_cached_alongside_content(self):
        brief = _base_brief()
        build_doctrine_context_for_brief(brief)
        for f in select_doctrine_files(brief):
            self.assertIn(f, _META_CACHE)


class TestParseFrontmatter(unittest.TestCase):

    def test_parses_priority_and_category(self):
        text = "---\npriority: 90\ncategory: safety_protocol\n---\n# Title\nBody"
        meta, body = _parse_frontmatter(text)
        self.assertEqual(meta["priority"], 90)
        self.assertEqual(meta["category"], "safety_protocol")
        self.assertIn("# Title", body)

    def test_parses_new_metadata_fields(self):
        text = (
            "---\n"
            "priority: 70\n"
            "category: guidance\n"
            "scope: purpose\n"
            "purposes: [planning, plan_mutation]\n"
            "sports: [running]\n"
            "situations: [prescription]\n"
            "cost_tier: medium\n"
            "---\n"
            "Body"
        )
        meta, _ = _parse_frontmatter(text)
        self.assertEqual(meta["scope"], "purpose")
        self.assertEqual(meta["purposes"], ["planning", "plan_mutation"])
        self.assertEqual(meta["sports"], ["running"])
        self.assertEqual(meta["situations"], ["prescription"])
        self.assertEqual(meta["cost_tier"], "medium")

    def test_defaults_when_no_frontmatter(self):
        text = "# Title\nBody"
        meta, body = _parse_frontmatter(text)
        self.assertEqual(meta["priority"], 50)
        self.assertEqual(meta["category"], "guidance")
        self.assertEqual(meta["scope"], "purpose")
        self.assertEqual(meta["purposes"], [])
        self.assertEqual(meta["sports"], [])
        self.assertEqual(meta["situations"], [])
        self.assertEqual(meta["cost_tier"], "medium")
        self.assertEqual(body, text)

    def test_invalid_category_keeps_default(self):
        text = "---\npriority: 70\ncategory: bogus\n---\nBody"
        meta, _ = _parse_frontmatter(text)
        self.assertEqual(meta["category"], "guidance")

    def test_invalid_priority_keeps_default(self):
        text = "---\npriority: abc\ncategory: anti_pattern\n---\nBody"
        meta, _ = _parse_frontmatter(text)
        self.assertEqual(meta["priority"], 50)
        self.assertEqual(meta["category"], "anti_pattern")


class TestDoctrineFrontmatterIntegrity(unittest.TestCase):
    """Verify every active doctrine file has valid frontmatter."""

    _LEGACY = set(LEGACY_UNIVERSAL_FILES)

    def test_every_active_file_has_valid_frontmatter(self):
        for rel_path in all_registered_doctrine_paths():
            if rel_path in self._LEGACY:
                continue
            full = _DOCTRINE_DIR / rel_path
            raw = full.read_text().strip()
            meta, _ = _parse_frontmatter(raw)
            self.assertIn(
                meta["category"], VALID_CATEGORIES,
                f"{rel_path}: invalid category {meta['category']!r}",
            )
            self.assertIn(
                meta["scope"], VALID_SCOPES,
                f"{rel_path}: invalid scope {meta['scope']!r}",
            )
            self.assertIn(
                meta["cost_tier"], VALID_COST_TIERS,
                f"{rel_path}: invalid cost_tier {meta['cost_tier']!r}",
            )
            self.assertIsInstance(meta["purposes"], list, f"{rel_path}: purposes must be a list")
            self.assertIsInstance(meta["sports"], list, f"{rel_path}: sports must be a list")
            self.assertIsInstance(meta["situations"], list, f"{rel_path}: situations must be a list")
            self.assertGreaterEqual(
                meta["priority"], 0,
                f"{rel_path}: priority must be >= 0",
            )
            self.assertLessEqual(
                meta["priority"], 100,
                f"{rel_path}: priority must be <= 100",
            )

    def test_get_doctrine_metadata_works(self):
        _CACHE.clear()
        _META_CACHE.clear()
        meta = get_doctrine_metadata("universal/core.md")
        self.assertIn("priority", meta)
        self.assertIn("category", meta)
        self.assertIn("scope", meta)
        self.assertIn("purposes", meta)
        self.assertIn("sports", meta)
        self.assertIn("situations", meta)
        self.assertIn("cost_tier", meta)


class TestCategoryBudgets(unittest.TestCase):
    """Verify category-aware selection respects budgets."""

    def _multi_signal_brief(self, **overrides):
        """Brief that triggers setback + illness + travel + intensity + prescription signals."""
        brief = _base_brief(
            delivery_context={
                "inbound_body": (
                    "Pain flared again, I'm also sick with a cold and low energy. "
                    "I was travelling with jet lag and poor sleep. "
                    "When can I bring back threshold and tempo? "
                    "Can you plan the week with some strides?"
                ),
            },
            decision_context={
                "track": "main_build",
                "phase": "build",
                "risk_flag": "yellow",
                "today_action": "adjust",
                "clarification_needed": False,
                "risk_recent_history": ["yellow", "red", "yellow", "green"],
                "weeks_in_coaching": 8,
            },
        )
        brief.update(overrides)
        return brief

    def test_all_safety_protocols_load_when_triggered(self):
        brief = self._multi_signal_brief()
        files = select_doctrine_files(brief)
        safety_files = [
            "universal/return_from_setback.md",
            "universal/illness_and_low_energy.md",
            "universal/intensity_reintroduction.md",
        ]
        for f in safety_files:
            self.assertIn(f, files, f"Safety protocol {f} should load when triggered")

    def test_both_anti_patterns_load_when_triggered(self):
        brief = self._multi_signal_brief()
        files = select_doctrine_files(brief)
        # common_coaching_failures triggers from setback+intensity backstop
        self.assertIn("universal/common_coaching_failures.md", files)
        # common_prescription_errors triggers from prescription signals + running
        self.assertIn("running/common_prescription_errors.md", files)

    def test_resource_capped_to_one(self):
        """If both recommendation files trigger, only 1 should load."""
        # This test is theoretical since running/recommendations requires
        # "recommend" + reading phrases and general/recommendations isn't
        # in the selection logic. But it tests the budget mechanism.
        brief = self._multi_signal_brief()
        blob = _signal_blob(brief)
        candidates = [
            "running/recommendations.md",
            "general/recommendations.md",
        ]
        budgeted = _apply_category_budgets(candidates, brief, blob)
        self.assertEqual(len(budgeted), 1)

    def test_under_budget_loads_all(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "Pain flared after the long run."},
        )
        files = select_doctrine_files(brief)
        # Setback triggers: return_from_setback (safety) + common_failures (anti_pattern)
        # + injury_return_patterns (safety, running)
        # All within budget
        self.assertIn("universal/return_from_setback.md", files)
        self.assertIn("universal/common_coaching_failures.md", files)
        self.assertIn("running/injury_return_patterns.md", files)

    def test_core_files_always_present_under_heavy_load(self):
        brief = self._multi_signal_brief()
        files = select_doctrine_files(brief)
        for f in CORE_UNIVERSAL_FILES:
            self.assertIn(f, files)

    def test_selection_is_deterministic(self):
        brief = self._multi_signal_brief()
        first = select_doctrine_files(brief)
        second = select_doctrine_files(brief)
        self.assertEqual(first, second)

    def test_travel_loads_as_safety_protocol(self):
        brief = _base_brief(
            delivery_context={"inbound_body": "On a work trip with jet lag and poor sleep."},
        )
        files = select_doctrine_files(brief)
        self.assertIn("universal/travel_and_disruption.md", files)


class TestCriticalConceptsPresent(unittest.TestCase):
    """Verify domain substance survived restructuring."""

    REQUIRED_CONCEPTS = {
        "universal/core.md": ["periodization", "progressive overload", "recovery", "specificity"],
        "universal/authority_and_override_rules.md": ["current athlete report", "safety"],
        "universal/relationship_arc.md": ["weeks 1-4", "weeks 5-12", "weeks 12+", "milestone"],
        "universal/return_from_setback.md": ["clearance", "7-10 stable days", "fragile"],
        "universal/illness_and_low_energy.md": ["systemic illness", "24-48h", "7 days"],
        "universal/travel_and_disruption.md": ["frequency", "minimum viable week"],
        "universal/intensity_reintroduction.md": ["gate 1", "gate 2", "gate 3", "controlled"],
        "universal/common_coaching_failures.md": ["session cost", "catch-up", "caution"],
        "running/methodology.md": ["daniels", "threshold", "taper", "80/20"],
        "running/injury_return_patterns.md": ["green", "yellow", "red", "frequency"],
        "running/common_prescription_errors.md": ["session cost", "tolerance"],
        "running/recommendations.md": ["daniels", "pfitzinger", "80/20"],
    }

    def test_each_file_contains_required_concepts(self):
        for rel_path, concepts in self.REQUIRED_CONCEPTS.items():
            full = _DOCTRINE_DIR / rel_path
            content = full.read_text().lower()
            for concept in concepts:
                self.assertIn(
                    concept.lower(), content,
                    f"{rel_path}: missing required concept {concept!r}",
                )


if __name__ == "__main__":
    unittest.main()
