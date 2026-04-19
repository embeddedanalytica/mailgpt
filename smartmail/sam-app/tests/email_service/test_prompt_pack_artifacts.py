import json
import os
import unittest
from pathlib import Path

import prompt_pack_loader


PROMPT_PACK_ROOT = (
    Path(__file__).resolve().parents[2]
    / "email_service"
    / "prompt_packs"
    / "coach_reply"
    / "v1"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class TestPromptPackArtifacts(unittest.TestCase):
    def test_manifest_exists_and_declares_expected_surfaces(self):
        manifest = _load_json(PROMPT_PACK_ROOT / "manifest.json")
        self.assertEqual(manifest["version"], "v1")
        self.assertEqual(
            manifest["editable_surfaces"],
            [
                "response_generation.directive_system_prompt",
                "coaching_reasoning.base_prompt",
            ],
        )

    def test_loader_defaults_to_v1(self):
        self.assertEqual(
            prompt_pack_loader.get_active_coach_reply_prompt_pack_version(),
            "v1",
        )

    def test_loader_reads_prompt_pack_payload(self):
        payload = prompt_pack_loader.load_coach_reply_prompt_pack(version="v1")
        self.assertEqual(payload["version"], "v1")
        self.assertIn("response_generation", payload)
        self.assertIn("coaching_reasoning", payload)

    def test_loader_uses_env_override(self):
        original = os.environ.get("COACH_REPLY_PROMPT_PACK_VERSION")
        try:
            os.environ["COACH_REPLY_PROMPT_PACK_VERSION"] = "v1"
            prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
            payload = prompt_pack_loader.load_coach_reply_prompt_pack()
        finally:
            if original is None:
                os.environ.pop("COACH_REPLY_PROMPT_PACK_VERSION", None)
            else:
                os.environ["COACH_REPLY_PROMPT_PACK_VERSION"] = original
            prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
        self.assertEqual(payload["version"], "v1")

    def test_loader_missing_version_fails_clearly(self):
        with self.assertRaisesRegex(prompt_pack_loader.PromptPackError, "prompt-pack artifact missing"):
            prompt_pack_loader.load_coach_reply_prompt_pack(version="missing-version")


if __name__ == "__main__":
    unittest.main()
