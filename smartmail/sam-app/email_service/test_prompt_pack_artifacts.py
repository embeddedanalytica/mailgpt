import json
import os
import unittest
from pathlib import Path

import prompt_pack_loader
from skills.coaching_reasoning import prompt as coaching_reasoning_prompt
from skills.response_generation import prompt as response_generation_prompt


PROMPT_PACK_ROOT = (
    Path(__file__).resolve().parent / "prompt_packs" / "coach_reply" / "v1"
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

    def test_response_generation_prompt_pack_matches_current_inline_prompts(self):
        payload = _load_json(PROMPT_PACK_ROOT / "response_generation.json")
        self.assertEqual(
            "\n".join(payload["directive_system_prompt_lines"]),
            response_generation_prompt.DIRECTIVE_SYSTEM_PROMPT,
        )

    def test_coaching_reasoning_prompt_pack_matches_current_base_prompt(self):
        payload = _load_json(PROMPT_PACK_ROOT / "coaching_reasoning.json")
        self.assertEqual(
            "\n".join(payload["base_prompt_lines"]),
            coaching_reasoning_prompt._BASE_PROMPT,  # type: ignore[attr-defined]
        )

    def test_loader_defaults_to_v1(self):
        self.assertEqual(
            prompt_pack_loader.get_active_coach_reply_prompt_pack_version(),
            "v1",
        )

    def test_loader_reads_prompt_pack_payload(self):
        payload = prompt_pack_loader.load_coach_reply_prompt_pack(version="v1")
        self.assertEqual(payload["version"], "v1")
        self.assertEqual(
            payload["response_generation"]["directive_system_prompt"],
            response_generation_prompt.DIRECTIVE_SYSTEM_PROMPT,
        )

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
