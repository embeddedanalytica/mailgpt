import json
import tempfile
import unittest
from pathlib import Path

import sys


TOOLS_PATH = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_feedback_aggregate


def _judge_result_event(turn: int, *, issue_tags=None, strength_tags=None, missed=None, scores=None, improved_reply_example=None):
    return {
        "phase": "judge_result",
        "turn": turn,
        "result": {
            "headline": f"headline {turn}",
            "scores": scores
            or {
                "understanding": 4,
                "memory_continuity": 5,
                "personalization": 3,
                "coaching_quality": 4,
                "tone_trust": 5,
                "communication_style_fit": 4,
                "safety": 5,
            },
            "what_landed": ["landed"],
            "what_missed": missed or [f"missed detail {turn}"],
            **(
                {"improved_reply_example": improved_reply_example}
                if improved_reply_example is not None
                else {}
            ),
            "hallucinations_or_unwarranted_assumptions": [],
            "athlete_likely_experience": f"experience {turn}",
            "issue_tags": issue_tags if issue_tags is not None else ["missed_fact"],
            "strength_tags": strength_tags if strength_tags is not None else ["specific_guidance"],
        },
    }


def _write_attempt(root: Path, stem: str, *, scenario_id: str, scenario_name: str, attempt: int, events):
    jsonl_path = root / f"{stem}.jsonl"
    summary_path = root / f"{stem}.summary.json"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for event in events:
            handle.write(json.dumps(event) + "\n")
    summary_path.write_text(
        json.dumps(
            {
                "scenario_id": scenario_id,
                "scenario_name": scenario_name,
                "attempt": attempt,
                "run_id": stem,
            }
        ),
        encoding="utf-8",
    )
    return jsonl_path


class TestPromptFeedbackAggregate(unittest.TestCase):
    def test_aggregate_feedback_collects_multiple_attempt_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_attempt(
                root,
                "las-001-attempt1-abc",
                scenario_id="LAS-001",
                scenario_name="Scenario One",
                attempt=1,
                events=[
                    {"phase": "athlete_turn", "turn": 1, "body": "hello"},
                    _judge_result_event(1, issue_tags=["missed_fact"], strength_tags=["specific_guidance"]),
                    _judge_result_event(2, issue_tags=["too_vague"], strength_tags=["good_attunement"]),
                ],
            )
            _write_attempt(
                root,
                "las-002-attempt2-def",
                scenario_id="LAS-002",
                scenario_name="Scenario Two",
                attempt=2,
                events=[
                    _judge_result_event(
                        1,
                        issue_tags=["missed_fact", "too_vague"],
                        strength_tags=["specific_guidance"],
                        improved_reply_example="Use the athlete's protected Friday as the reset day.",
                        scores={
                            "understanding": 2,
                            "memory_continuity": 3,
                            "personalization": 2,
                            "coaching_quality": 2,
                            "tone_trust": 3,
                            "communication_style_fit": 3,
                            "safety": 5,
                        },
                    ),
                ],
            )

            aggregate = prompt_feedback_aggregate.aggregate_feedback(root)

        self.assertEqual(aggregate["run_id"], root.name)
        self.assertEqual(aggregate["judge_result_count"], 3)
        self.assertEqual(
            aggregate["issue_tag_counts"],
            {"missed_fact": 2, "too_vague": 2},
        )
        self.assertEqual(
            aggregate["strength_tag_counts"],
            {"good_attunement": 1, "specific_guidance": 2},
        )
        self.assertEqual(
            aggregate["average_scores"],
            {
                "understanding": 3.333,
                "memory_continuity": 4.333,
                "personalization": 2.667,
                "coaching_quality": 3.333,
                "tone_trust": 4.333,
                "communication_style_fit": 3.667,
                "safety": 5.0,
            },
        )
        self.assertEqual(len(aggregate["score_by_scenario"]), 2)
        self.assertEqual(aggregate["score_by_scenario"][0]["scenario_id"], "LAS-001")
        self.assertEqual(
            aggregate["misses_by_issue_tag"]["missed_fact"]["items"][0]["scenario_id"],
            "LAS-001",
        )
        self.assertEqual(
            aggregate["misses_by_issue_tag"]["too_vague"]["items"][-1]["scenario_id"],
            "LAS-002",
        )
        self.assertEqual(
            aggregate["examples"][-1]["improved_reply_example"],
            "Use the athlete's protected Friday as the reset day.",
        )
        self.assertEqual(
            aggregate["misses_by_issue_tag"]["too_vague"]["items"][-1]["improved_reply_example"],
            "Use the athlete's protected Friday as the reset day.",
        )

    def test_aggregate_feedback_groups_untagged_misses(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_attempt(
                root,
                "las-003-attempt1-ghi",
                scenario_id="LAS-003",
                scenario_name="Scenario Three",
                attempt=1,
                events=[_judge_result_event(1, issue_tags=[], missed=["generic and vague"])],
            )

            aggregate = prompt_feedback_aggregate.aggregate_feedback(root)

        self.assertEqual(aggregate["issue_tag_counts"], {"untagged": 1})
        self.assertIn("untagged", aggregate["misses_by_issue_tag"])
        self.assertEqual(
            aggregate["misses_by_issue_tag"]["untagged"]["items"][0]["missed"],
            "generic and vague",
        )

    def test_aggregate_feedback_raises_for_empty_directory(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaisesRegex(RuntimeError, "No attempt JSONL files found"):
                prompt_feedback_aggregate.aggregate_feedback(root)

    def test_aggregate_feedback_raises_on_malformed_json_line(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "las-001-attempt1-bad.jsonl"
            path.write_text("{not json}\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid JSON"):
                prompt_feedback_aggregate.aggregate_feedback(root)

    def test_main_writes_default_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_attempt(
                root,
                "las-001-attempt1-abc",
                scenario_id="LAS-001",
                scenario_name="Scenario One",
                attempt=1,
                events=[_judge_result_event(1)],
            )

            exit_code = prompt_feedback_aggregate.main(["--input-dir", str(root)])

            output_path = root / "aggregate.json"
            payload = json.loads(output_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["judge_result_count"], 1)


if __name__ == "__main__":
    unittest.main()
