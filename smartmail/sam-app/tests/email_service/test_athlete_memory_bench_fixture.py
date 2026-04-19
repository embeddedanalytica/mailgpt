import json
import tempfile
import unittest
from pathlib import Path

from athlete_memory_bench_fixture import (
    DEFAULT_BENCH_PATH,
    load_athlete_memory_bench_scenarios,
)


def _fixture_text(payload) -> str:
    return "# bench\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n"


def _fact(label: str, *signals: str) -> dict:
    return {
        "label": label,
        "signals": list(signals or [label]),
        "aliases": [],
        "semantic_signals": [],
        "importance": "medium",
    }


def _message(step: int) -> dict:
    return {
        "step": step,
        "email": f"email {step}",
        "synthetic_coach_reply": f"reply {step}",
        "durable_truths": [_fact("durable", "durable signal")],
        "active_context": [_fact("active", "active signal")],
        "active_context_mode": "acceptable",
        "retired_truths": [],
        "routine_noise": [_fact("noise", "noise signal")],
        "coach_should_adjust_for": [_fact("adjust", "adjust signal")],
        "coach_should_not_do": [],
        "message_intent": "general",
    }


def _scenario(scenario_id: str) -> dict:
    return {
        "id": scenario_id,
        "athlete_name": "Name",
        "sport": "sport",
        "profile_hint": "hint",
        "messages": [_message(step) for step in range(1, 6)],
        "final_assertions": {
            "final_durable_truths": [_fact("durable", "durable signal")],
            "final_retrieval_support": [_fact("retrieval", "retrieval signal")],
            "final_retired_truths": [],
        },
    }


class TestAthleteMemoryBenchFixture(unittest.TestCase):
    def test_loads_real_fixture_with_15_scenarios(self):
        scenarios = load_athlete_memory_bench_scenarios(DEFAULT_BENCH_PATH)
        self.assertEqual(len(scenarios), 15)
        self.assertTrue(all(len(item["messages"]) == 5 for item in scenarios))

    def test_duplicate_ids_fail(self):
        payload = [_scenario("AM-X"), _scenario("AM-X")]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_bench_scenarios(path)

    def test_missing_fields_fail(self):
        payload = [_scenario("AM-X")]
        del payload[0]["profile_hint"]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_bench_scenarios(path)

    def test_non_five_step_sequence_fails(self):
        payload = [_scenario("AM-X")]
        payload[0]["messages"] = [_message(step) for step in range(1, 5)]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_bench_scenarios(path)

    def test_invalid_fact_signal_fails(self):
        payload = [_scenario("AM-X")]
        payload[0]["messages"][0]["durable_truths"][0]["signals"] = []
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_bench_scenarios(path)

    def test_invalid_active_context_mode_fails(self):
        payload = [_scenario("AM-X")]
        payload[0]["messages"][0]["active_context_mode"] = "sticky"
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "bench.md"
            path.write_text(_fixture_text(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_athlete_memory_bench_scenarios(path)


if __name__ == "__main__":
    unittest.main()
