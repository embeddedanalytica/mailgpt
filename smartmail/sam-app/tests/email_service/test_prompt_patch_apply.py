import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_patch_apply


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_prompt_pack(root: Path, version: str) -> Path:
    target = root / "coach_reply" / version
    target.mkdir(parents=True, exist_ok=True)
    _write_json(
        target / "manifest.json",
        {
            "version": version,
            "created_at": "2026-03-22T00:00:00Z",
            "parent_version": None,
            "editable_surfaces": list(prompt_patch_apply.SURFACE_FILE_MAP.keys()),
        },
    )
    _write_json(target / "response_generation.json", {"directive_system_prompt_lines": ["base-directive"]})
    _write_json(target / "coaching_reasoning.json", {"base_prompt_lines": ["base-coaching"]})
    return target


class TestPromptPatchApply(unittest.TestCase):
    def test_apply_proposal_creates_new_prompt_pack_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            _write_prompt_pack(root, "v1")
            proposal_path = Path(td) / "proposal.json"
            _write_json(
                proposal_path,
                {
                    "base_version": "v1",
                    "proposed_version": "v1-proposal",
                    "changes": [
                        {
                            "target_surface": "response_generation.directive_system_prompt",
                            "issue_tags": ["too_vague"],
                            "patch_strategy": "Require concrete workout guidance.",
                            "evidence": {"example_refs": [{"improved_reply_example": "Run 4 x 5 minutes."}]},
                        },
                        {
                            "target_surface": "coaching_reasoning.base_prompt",
                            "issue_tags": ["unclear_priority"],
                            "patch_strategy": "State the main next step clearly.",
                            "evidence": {"example_refs": []},
                        },
                    ],
                },
            )

            with mock.patch.object(prompt_patch_apply, "PROMPT_PACKS_ROOT", root):
                target_dir = prompt_patch_apply.apply_proposal(proposal_path=proposal_path)

            response_generation = json.loads((target_dir / "response_generation.json").read_text(encoding="utf-8"))
            coaching_reasoning = json.loads((target_dir / "coaching_reasoning.json").read_text(encoding="utf-8"))
            manifest = json.loads((target_dir / "manifest.json").read_text(encoding="utf-8"))

        self.assertEqual(target_dir.name, "v1-proposal")
        self.assertGreater(len(response_generation["directive_system_prompt_lines"]), 1)
        self.assertGreater(len(coaching_reasoning["base_prompt_lines"]), 1)
        self.assertEqual(manifest["parent_version"], "v1")
        self.assertIn("source_proposal", manifest)

    def test_apply_proposal_rejects_unknown_surface(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            _write_prompt_pack(root, "v1")
            proposal_path = Path(td) / "proposal.json"
            _write_json(
                proposal_path,
                {
                    "base_version": "v1",
                    "proposed_version": "v1-proposal",
                    "changes": [{"target_surface": "unsupported.surface", "patch_strategy": "x", "issue_tags": [], "evidence": {}}],
                },
            )

            with mock.patch.object(prompt_patch_apply, "PROMPT_PACKS_ROOT", root):
                with self.assertRaisesRegex(ValueError, "unsupported proposal target surface"):
                    prompt_patch_apply.apply_proposal(proposal_path=proposal_path)

    def test_main_writes_new_version(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td) / "prompt_packs"
            _write_prompt_pack(root, "v1")
            proposal_path = Path(td) / "proposal.json"
            _write_json(
                proposal_path,
                {
                    "base_version": "v1",
                    "proposed_version": "v1-proposal",
                    "changes": [],
                },
            )

            with mock.patch.object(prompt_patch_apply, "PROMPT_PACKS_ROOT", root):
                exit_code = prompt_patch_apply.main(["--proposal", str(proposal_path)])
                target_exists = (root / "coach_reply" / "v1-proposal").exists()

        self.assertEqual(exit_code, 0)
        self.assertTrue(target_exists)


if __name__ == "__main__":
    unittest.main()
