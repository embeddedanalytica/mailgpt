import json
import tempfile
import unittest
from pathlib import Path

import sys


TOOLS_PATH = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_patch_proposer


def _aggregate_payload() -> dict:
    return {
        "run_id": "20260322T061624Z",
        "input_dir": "/tmp/example-run",
        "issue_tag_counts": {
            "missed_continuity": 4,
            "too_vague": 3,
            "untagged": 2,
            "unclear_priority": 1,
        },
        "examples": [
            {
                "scenario_id": "LAS-001",
                "scenario_name": "Scenario One",
                "attempt": 1,
                "turn": 2,
                "headline": "Continuity miss",
                "athlete_likely_experience": "Partly understood",
                "issue_tags": ["missed_continuity"],
                "strength_tags": ["good_attunement"],
                "what_missed": ["Did not carry forward the prior Friday constraint."],
                "improved_reply_example": "Keep Friday light again and protect the quality session earlier in the week.",
            },
            {
                "scenario_id": "LAS-002",
                "scenario_name": "Scenario Two",
                "attempt": 1,
                "turn": 1,
                "headline": "Too vague",
                "athlete_likely_experience": "Generic",
                "issue_tags": ["too_vague"],
                "strength_tags": [],
                "what_missed": ["Guidance lacked concrete session details."],
                "improved_reply_example": None,
            },
            {
                "scenario_id": "LAS-003",
                "scenario_name": "Scenario Three",
                "attempt": 2,
                "turn": 3,
                "headline": "Priority unclear",
                "athlete_likely_experience": "Unsure what matters most",
                "issue_tags": ["unclear_priority"],
                "strength_tags": [],
                "what_missed": ["The main next step was not obvious."],
                "improved_reply_example": None,
            },
        ],
    }


class TestPromptPatchProposer(unittest.TestCase):
    def test_build_proposal_references_supported_issue_tags_only(self):
        proposal = prompt_patch_proposer.build_proposal(_aggregate_payload(), base_version="v1")

        self.assertEqual(proposal["base_version"], "v1")
        self.assertEqual(proposal["proposed_version"], "v1-proposal")
        self.assertEqual(
            proposal["target_surfaces"],
            [
                "coaching_reasoning.base_prompt",
                "response_generation.directive_system_prompt",
            ],
        )
        self.assertEqual(len(proposal["changes"]), 3)
        self.assertEqual(proposal["changes"][0]["issue_tags"], ["missed_continuity"])

    def test_build_proposal_limits_targets_to_allowed_surfaces(self):
        proposal = prompt_patch_proposer.build_proposal(_aggregate_payload(), base_version="v1")
        for change in proposal["changes"]:
            self.assertIn(change["target_surface"], prompt_patch_proposer.ALLOWED_SURFACES)

    def test_build_proposal_preserves_example_references(self):
        proposal = prompt_patch_proposer.build_proposal(_aggregate_payload(), base_version="v1")
        continuity_change = next(
            change for change in proposal["changes"] if change["issue_tags"] == ["missed_continuity"]
        )
        self.assertEqual(
            continuity_change["evidence"]["example_refs"][0]["scenario_id"],
            "LAS-001",
        )
        self.assertEqual(
            continuity_change["evidence"]["example_refs"][0]["improved_reply_example"],
            "Keep Friday light again and protect the quality session earlier in the week.",
        )

    def test_main_writes_default_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            aggregate_path = root / "aggregate.json"
            aggregate_path.write_text(json.dumps(_aggregate_payload()), encoding="utf-8")

            exit_code = prompt_patch_proposer.main(
                ["--aggregate", str(aggregate_path), "--base-version", "v1"]
            )

            proposal_path = root / "proposal.json"
            proposal = json.loads(proposal_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(proposal["base_version"], "v1")
        self.assertEqual(len(proposal["changes"]), 3)

    def test_main_fails_on_invalid_aggregate_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            aggregate_path = root / "aggregate.json"
            aggregate_path.write_text(json.dumps({"run_id": "x"}), encoding="utf-8")

            exit_code = prompt_patch_proposer.main(
                ["--aggregate", str(aggregate_path), "--base-version", "v1"]
            )

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
