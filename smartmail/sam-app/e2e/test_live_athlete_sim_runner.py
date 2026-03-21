"""Live smoke test for the athlete simulator runner."""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[2]
TOOLS_PATH = ROOT / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import live_athlete_sim_runner  # noqa: E402


@unittest.skipUnless(
    os.getenv("RUN_LIVE_ATHLETE_SIM_SMOKE", "false").strip().lower() == "true",
    "RUN_LIVE_ATHLETE_SIM_SMOKE is not true",
)
class TestLiveAthleteSimRunner(unittest.TestCase):
    def test_live_smoke_short_conversation(self) -> None:
        if not os.getenv("OPENAI_API_KEY"):
            raise unittest.SkipTest("OPENAI_API_KEY required for live athlete simulator smoke test")

        fixture_payload = [
            {
                "id": "LAS-SMOKE-001",
                "name": "smoke test athlete",
                "athlete_brief": (
                    "You are a cautious runner trying to rebuild after a choppy month. "
                    "You want concise, observant coaching and you reveal details gradually."
                ),
                "judge_brief": (
                    "Reward attentive, personalized coaching and penalize generic replies or missed continuity."
                ),
                "opening_message": "I want to rebuild some consistency without doing too much too soon.",
                "evaluation_focus": ["memory", "specificity"],
                "min_turns": 2,
                "max_turns": 3,
            }
        ]

        with tempfile.TemporaryDirectory() as td:
            fixture_path = Path(td) / "fixture.md"
            fixture_path.write_text(
                "# fixture\n\n```json\n" + json.dumps(fixture_payload, indent=2) + "\n```\n",
                encoding="utf-8",
            )
            output_dir = Path(td) / "out"
            exit_code = live_athlete_sim_runner.main(
                [
                    "--bench",
                    str(fixture_path),
                    "--output-dir",
                    str(output_dir),
                    "--runs-per-scenario",
                    "1",
                    "--min-turns",
                    "2",
                    "--max-turns",
                    "3",
                ]
            )

            results_path = output_dir / "results.json"
            results = json.loads(results_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(results["total_runs"], 1)
        self.assertEqual(results["ok_runs"], 1)


if __name__ == "__main__":
    unittest.main()
