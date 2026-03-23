import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_pack_loader
import prompt_pack_promote


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


class TestPromptPackPromote(unittest.TestCase):
    def test_promote_copies_version_and_writes_lineage_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            base_dir = root / "coach_reply" / "v1"
            base_dir.mkdir(parents=True)
            _write_json(
                base_dir / "manifest.json",
                {
                    "version": "v1",
                    "created_at": "2026-03-22T00:00:00Z",
                    "parent_version": None,
                    "editable_surfaces": ["response_generation.system_prompt"],
                },
            )
            _write_json(base_dir / "response_generation.json", {"system_prompt_lines": ["x"], "directive_system_prompt_lines": ["y"]})
            _write_json(base_dir / "coaching_reasoning.json", {"base_prompt_lines": ["z"]})

            proposal_path = Path(td) / "proposal.json"
            regression_path = Path(td) / "regression_report.json"
            _write_json(proposal_path, {"base_version": "v1", "proposed_version": "v1-proposal"})
            _write_json(
                regression_path,
                {
                    "decision": "promote",
                    "base_version": "v1",
                    "proposed_version": "v1-proposal",
                    "base_metrics": {"overall_average_score": 4.0},
                    "proposed_metrics": {"overall_average_score": 4.5},
                    "score_deltas": {"overall_average_score": 0.5},
                },
            )

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                target_dir = prompt_pack_promote.promote_prompt_pack(
                    base_version="v1",
                    source_version=None,
                    new_version="v2",
                    proposal_path=proposal_path,
                    regression_report_path=regression_path,
                    activate=False,
                )

            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["version"], "v2")
        self.assertEqual(manifest["parent_version"], "v1")
        self.assertEqual(manifest["source_version"], "v1")
        self.assertEqual(manifest["metrics_summary"]["proposed_metrics"]["overall_average_score"], 4.5)
        self.assertEqual(manifest["metrics_summary"]["score_deltas"]["overall_average_score"], 0.5)
        self.assertIn("source_proposal", manifest)
        self.assertIn("source_regression_report", manifest)
        self.assertIn("Proposal proposed_version=v1-proposal", manifest["promotion_notes"])

    def test_promote_requires_passing_regression_decision(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            base_dir = root / "coach_reply" / "v1"
            base_dir.mkdir(parents=True)
            _write_json(base_dir / "manifest.json", {"version": "v1"})
            _write_json(base_dir / "response_generation.json", {"system_prompt_lines": ["x"], "directive_system_prompt_lines": ["y"]})
            _write_json(base_dir / "coaching_reasoning.json", {"base_prompt_lines": ["z"]})

            proposal_path = Path(td) / "proposal.json"
            regression_path = Path(td) / "regression_report.json"
            _write_json(proposal_path, {"base_version": "v1"})
            _write_json(regression_path, {"decision": "reject"})

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                with self.assertRaisesRegex(ValueError, "decision must be 'promote'"):
                    prompt_pack_promote.promote_prompt_pack(
                        base_version="v1",
                        source_version=None,
                        new_version="v2",
                        proposal_path=proposal_path,
                        regression_report_path=regression_path,
                        activate=False,
                    )

    def test_promote_rejects_mismatched_base_version_metadata(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            base_dir = root / "coach_reply" / "v1"
            base_dir.mkdir(parents=True)
            _write_json(base_dir / "manifest.json", {"version": "v1"})
            _write_json(base_dir / "response_generation.json", {"system_prompt_lines": ["x"], "directive_system_prompt_lines": ["y"]})
            _write_json(base_dir / "coaching_reasoning.json", {"base_prompt_lines": ["z"]})

            proposal_path = Path(td) / "proposal.json"
            regression_path = Path(td) / "regression_report.json"
            _write_json(proposal_path, {"base_version": "wrong"})
            _write_json(regression_path, {"decision": "promote", "base_version": "v1"})

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                with self.assertRaisesRegex(ValueError, "proposal base_version must match"):
                    prompt_pack_promote.promote_prompt_pack(
                        base_version="v1",
                        source_version=None,
                        new_version="v2",
                        proposal_path=proposal_path,
                        regression_report_path=regression_path,
                        activate=False,
                    )

    def test_promote_can_copy_from_distinct_source_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            coach_reply_root = root / "coach_reply"
            base_dir = coach_reply_root / "v1"
            source_dir = coach_reply_root / "v1-proposal"
            base_dir.mkdir(parents=True)
            source_dir.mkdir(parents=True)
            _write_json(base_dir / "manifest.json", {"version": "v1"})
            _write_json(base_dir / "response_generation.json", {"system_prompt_lines": ["base"], "directive_system_prompt_lines": ["base-d"]})
            _write_json(base_dir / "coaching_reasoning.json", {"base_prompt_lines": ["base-c"]})
            _write_json(source_dir / "manifest.json", {"version": "v1-proposal"})
            _write_json(source_dir / "response_generation.json", {"system_prompt_lines": ["proposal"], "directive_system_prompt_lines": ["proposal-d"]})
            _write_json(source_dir / "coaching_reasoning.json", {"base_prompt_lines": ["proposal-c"]})

            proposal_path = Path(td) / "proposal.json"
            regression_path = Path(td) / "regression_report.json"
            _write_json(proposal_path, {"base_version": "v1", "proposed_version": "v1-proposal"})
            _write_json(regression_path, {"decision": "promote", "base_version": "v1", "proposed_version": "v1-proposal"})

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                target_dir = prompt_pack_promote.promote_prompt_pack(
                    base_version="v1",
                    source_version="v1-proposal",
                    new_version="v2",
                    proposal_path=proposal_path,
                    regression_report_path=regression_path,
                    activate=False,
                )

            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))
            response_generation = json.loads((target_dir / "response_generation.json").read_text(encoding="utf-8"))

        self.assertEqual(manifest["parent_version"], "v1")
        self.assertEqual(manifest["source_version"], "v1-proposal")
        self.assertEqual(response_generation["system_prompt_lines"], ["proposal"])

    def test_promote_can_activate_new_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            base_dir = root / "coach_reply" / "v1"
            base_dir.mkdir(parents=True)
            _write_json(base_dir / "manifest.json", {"version": "v1"})
            _write_json(base_dir / "response_generation.json", {"system_prompt_lines": ["x"], "directive_system_prompt_lines": ["y"]})
            _write_json(base_dir / "coaching_reasoning.json", {"base_prompt_lines": ["z"]})

            proposal_path = Path(td) / "proposal.json"
            regression_path = Path(td) / "regression_report.json"
            _write_json(proposal_path, {"base_version": "v1"})
            _write_json(regression_path, {"decision": "promote", "proposed_metrics": {}})

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                prompt_pack_promote.promote_prompt_pack(
                    base_version="v1",
                    source_version=None,
                    new_version="v2",
                    proposal_path=proposal_path,
                    regression_report_path=regression_path,
                    activate=True,
                )

            active_path = root / "coach_reply" / prompt_pack_loader.ACTIVE_VERSION_FILE_NAME
            self.assertEqual(active_path.read_text(encoding="utf-8").strip(), "v2")

    def test_set_active_prompt_pack_version_can_switch_back_to_prior_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            coach_reply_root = root / "coach_reply"
            (coach_reply_root / "v1").mkdir(parents=True)
            (coach_reply_root / "v2").mkdir(parents=True)

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                prompt_pack_promote.set_active_prompt_pack_version("v2")
                prompt_pack_promote.set_active_prompt_pack_version("v1")

            active_path = coach_reply_root / prompt_pack_loader.ACTIVE_VERSION_FILE_NAME
            self.assertEqual(active_path.read_text(encoding="utf-8").strip(), "v1")

    def test_main_supports_activate_version_mode(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            coach_reply_root = root / "coach_reply"
            (coach_reply_root / "v1").mkdir(parents=True)
            (coach_reply_root / "v2").mkdir(parents=True)

            with mock.patch.object(prompt_pack_promote, "PROMPT_PACKS_ROOT", root):
                exit_code = prompt_pack_promote.main(["--activate-version", "v2"])

            active_path = coach_reply_root / prompt_pack_loader.ACTIVE_VERSION_FILE_NAME
            self.assertEqual(exit_code, 0)
            self.assertEqual(active_path.read_text(encoding="utf-8").strip(), "v2")

    def test_loader_uses_active_version_file_when_env_missing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            coach_reply_root = root / "coach_reply"
            v1_dir = coach_reply_root / "v1"
            v2_dir = coach_reply_root / "v2"
            v1_dir.mkdir(parents=True)
            v2_dir.mkdir(parents=True)
            _write_json(v1_dir / "manifest.json", {"version": "v1"})
            _write_json(v1_dir / "response_generation.json", {"system_prompt_lines": ["one"], "directive_system_prompt_lines": ["one-d"]})
            _write_json(v1_dir / "coaching_reasoning.json", {"base_prompt_lines": ["one-c"]})
            _write_json(v2_dir / "manifest.json", {"version": "v2"})
            _write_json(v2_dir / "response_generation.json", {"system_prompt_lines": ["two"], "directive_system_prompt_lines": ["two-d"]})
            _write_json(v2_dir / "coaching_reasoning.json", {"base_prompt_lines": ["two-c"]})
            (coach_reply_root / prompt_pack_loader.ACTIVE_VERSION_FILE_NAME).write_text("v2\n", encoding="utf-8")

            with mock.patch.object(prompt_pack_loader, "PROMPT_PACKS_ROOT", root):
                prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
                with mock.patch.dict("os.environ", {}, clear=False):
                    version = prompt_pack_loader.get_active_coach_reply_prompt_pack_version()
                    payload = prompt_pack_loader.load_coach_reply_prompt_pack()
                prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

        self.assertEqual(version, "v2")
        self.assertEqual(payload["version"], "v2")


if __name__ == "__main__":
    unittest.main()
