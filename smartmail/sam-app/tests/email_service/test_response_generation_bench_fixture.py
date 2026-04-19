import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import response_generation_bench_fixture


def _valid_scenario(scenario_id: str = "RG-001") -> dict:
    return {
        "id": scenario_id,
        "name": "sample",
        "response_brief": {
            "reply_mode": "normal_coaching",
            "coaching_directive": {
                "opening": "Test opening",
                "main_message": "Keep one controlled quality session this week.",
                "content_plan": ["present the plan"],
                "avoid": [],
                "tone": "calm and direct",
                "recommend_material": None,
            },
            "plan_data": {
                "weekly_skeleton": ["easy_aerobic", "strength", "tempo"],
                "plan_summary": "Current plan: rebuild consistency while protecting recovery.",
            },
            "delivery_context": {
                "inbound_subject": "Weekly check-in",
                "selected_model_name": "gpt-5-mini",
            },
        },
    }


class TestResponseGenerationBenchFixture(unittest.TestCase):
    def _write_fixture(self, payload: list[dict]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(
            "# fixture\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n",
            encoding="utf-8",
        )
        return path

    def test_loads_real_fixture_with_twenty_scenarios(self):
        scenarios = response_generation_bench_fixture.load_response_generation_bench_scenarios(
            response_generation_bench_fixture.DEFAULT_BENCH_PATH
        )
        self.assertEqual(len(scenarios), 20)

    def test_duplicate_ids_fail(self):
        fixture = self._write_fixture([_valid_scenario("RG-001"), _valid_scenario("RG-001")])
        with self.assertRaisesRegex(ValueError, "Duplicate scenario id"):
            response_generation_bench_fixture.load_response_generation_bench_scenarios(fixture)

    def test_invalid_response_brief_shape_fails(self):
        scenario = _valid_scenario("RG-003")
        del scenario["response_brief"]["reply_mode"]
        fixture = self._write_fixture([scenario])
        with self.assertRaisesRegex(ValueError, "response_brief invalid"):
            response_generation_bench_fixture.load_response_generation_bench_scenarios(fixture)

    def test_missing_json_block_fails(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(textwrap.dedent("# fixture\n\nno json block\n"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No JSON block"):
            response_generation_bench_fixture.load_response_generation_bench_scenarios(path)

    def test_malformed_json_fails(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(
            textwrap.dedent(
                """
                # fixture
                ```json
                [{"id":"RG-001","name":"bad","response_brief":{}}
                ```
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Invalid JSON block"):
            response_generation_bench_fixture.load_response_generation_bench_scenarios(path)


if __name__ == "__main__":
    unittest.main()
