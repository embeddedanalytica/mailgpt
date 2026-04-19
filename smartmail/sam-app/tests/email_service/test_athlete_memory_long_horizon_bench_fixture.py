import json
import tempfile
import unittest
from pathlib import Path

from athlete_memory_long_horizon_bench_fixture import (
    DEFAULT_LONG_HORIZON_BENCH_PATH,
    load_athlete_memory_long_horizon_bench_scenarios,
)


def _fixture_text(payload) -> str:
    return "# bench\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"


def _fact(label: str, signal: str, importance: str = "medium") -> dict:
    return {
        "label": label,
        "signals": [signal],
        "importance": importance,
    }


def _checkpoint(label: str) -> dict:
    return {
        "label": label,
        "durable_truths": [_fact("goal", "marathon build", "high")],
        "active_context": [],
        "retired_truths": [],
        "routine_noise": [],
        "coach_should_adjust_for": [_fact("protect long run", "long run", "medium")],
        "coach_should_not_do": [],
    }


def _phase(phase_id: str, start_step: int) -> dict:
    return {
        "phase_id": phase_id,
        "phase_goal": f"goal for {phase_id}",
        "messages": [
            {
                "step": step,
                "email": f"email {step}",
                "synthetic_coach_reply": f"reply {step}",
                "event_tags": ["routine_checkin"],
            }
            for step in range(start_step, start_step + 4)
        ],
        "checkpoint_assertions": _checkpoint(f"{phase_id} checkpoint"),
    }


def _scenario(scenario_id: str) -> dict:
    return {
        "id": scenario_id,
        "athlete_name": "Name",
        "sport": "running",
        "profile_hint": "hint",
        "phases": [
            _phase("phase_1", 1),
            _phase("phase_2", 5),
            _phase("phase_3", 9),
            _phase("phase_4", 13),
            _phase("phase_5", 17),
        ],
        "final_assertions": {
            "final_durable_truths": [_fact("goal", "marathon build", "high")],
            "final_retrieval_support": [_fact("goal", "marathon build", "high")],
            "final_retired_truths": [],
        },
    }


class TestAthleteMemoryLongHorizonBenchFixture(unittest.TestCase):
    def test_loads_real_fixture_with_five_scenarios(self):
        scenarios = load_athlete_memory_long_horizon_bench_scenarios(
            DEFAULT_LONG_HORIZON_BENCH_PATH
        )
        self.assertEqual(len(scenarios), 5)
        self.assertTrue(all(20 <= sum(len(phase["messages"]) for phase in item["phases"]) <= 25 for item in scenarios))

    def test_optional_architecture_assertions_are_accepted(self):
        payload = [_scenario("AM-LH-1")]
        payload[0]["phases"][0]["checkpoint_assertions"]["expected_active_storage"] = {
            "must_include": [_fact("goal", "marathon build", "high")],
            "max_active_counts": {"goals": 4},
        }
        payload[0]["final_assertions"]["final_rejections"] = [
            {
                "label": "goal rejected",
                "signals": ["extra goal"],
                "reason": "active_section_at_capacity_without_supersession",
            }
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            scenarios = load_athlete_memory_long_horizon_bench_scenarios(path)
        self.assertIn("expected_active_storage", scenarios[0]["phases"][0]["checkpoint_assertions"])
        self.assertIn("final_rejections", scenarios[0]["final_assertions"])

    def test_duplicate_ids_fail(self):
        payload = [_scenario("AM-LH-1"), _scenario("AM-LH-1")]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_long_horizon_bench_scenarios(path)

    def test_non_monotonic_steps_fail(self):
        payload = [_scenario("AM-LH-1")]
        payload[0]["phases"][1]["messages"][0]["step"] = 99
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_long_horizon_bench_scenarios(path)

    def test_checkpoint_assertions_required(self):
        payload = [_scenario("AM-LH-1")]
        del payload[0]["phases"][0]["checkpoint_assertions"]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_long_horizon_bench_scenarios(path)


if __name__ == "__main__":
    unittest.main()
