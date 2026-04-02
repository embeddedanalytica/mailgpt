"""Bug #27: Which layer fabricates URLs — strategist or writer?

Sends the LAS-003 T12 athlete message ("please attach the Week 2 ICS/CSV or
provide a download link") through the strategist and then the writer, and
prints the raw output of each layer so we can see where URL fabrication
originates.

Run:
    ENABLE_LIVE_LLM_CALLS=true python3 -m unittest -v test_bug27_url_fabrication
"""

import json
import os
import re
import unittest

from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow
from skills.response_generation.runner import run_response_generation_workflow

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"

# Athlete message from LAS-003 T12 — explicitly asks for file attachment / download link
_INBOUND_BODY = (
    "Hamstring: clear. Please attach the Week 2 ICS/CSV here or paste a one-click "
    "download URL I can use (I will not share portal credentials). If attachment or "
    "link isn't possible, paste the exact portal path and a 2-step download "
    "instruction that does not require me to share login info, and explicitly "
    "confirm the exported events use 05:30 AM for all weekday runs and 07:30 AM "
    "for Saturdays and that the MP safeguards + 12-mile cap are encoded in the "
    "file. Also clarify whether you actually imported Week 2 into my account or "
    "simply released it to the portal. Thanks — Maya"
)


def _las003_t12_brief():
    """ResponseBrief matching LAS-003 T12 state."""
    return {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Complete a winter rebuild and then target a spring marathon",
            "experience_level": "unknown",
            "structure_preference": "structured",
            "primary_sport": "running",
            "constraints_summary": (
                "Left hamstring — needs to be pain-free before progressing. "
                "Weekday runs at 05:30 AM, Saturday long run at 07:30 AM. "
                "12-mile single-session cap."
            ),
        },
        "decision_context": {
            "plan_update_status": "updated",
            "risk_flag": "green",
            "clarification_needed": False,
            "weeks_in_coaching": 12,
        },
        "validated_plan": {
            "plan_summary": (
                "Current plan - Goal: Complete a winter rebuild and then target "
                "a spring marathon. Version: 7. Phase: base. Focus: main_base. "
                "Status: active. Next session: TBD: hard (tempo)"
            ),
            "weekly_skeleton": ["tempo", "easy_aerobic"],
        },
        "memory_context": {
            "memory_available": True,
            "priority_facts": [
                "Spring marathon after winter rebuild (10-week default)",
                "Left hamstring — pain-free gating on progression",
            ],
            "structure_facts": [
                "Weekday runs 05:30 AM (05:00-06:30 window), Saturday long run 07:30 AM",
                "Strength 2x/week, max one hard weekday session",
            ],
            "context_facts": [
                "Prefers MP work over track; long MP segments preferred",
                "GI sensitivity to sweet gels — prefers lower-sugar fueling",
            ],
            "continuity_summary": {
                "summary": (
                    "Athlete requested Week 2 ICS/CSV and confirmed weekday/weekend "
                    "times. Coach confirmed file location and MP safeguards."
                ),
                "last_recommendation": (
                    "Download/import Week 2 ICS/CSV, verify times and safeguards."
                ),
                "open_loops": [],
            },
        },
        "delivery_context": {
            "inbound_subject": "Please attach Week 2 ICS/CSV or provide a direct download link",
            "inbound_body": _INBOUND_BODY,
            "response_channel": "email",
        },
    }


_URL_PATTERN = re.compile(r"https?://\S+", re.IGNORECASE)


def _find_urls(text):
    return _URL_PATTERN.findall(text or "")


@unittest.skipUnless(_LIVE, "requires ENABLE_LIVE_LLM_CALLS=true")
class TestBug27UrlFabricationLayer(unittest.TestCase):
    """Sends LAS-003 T12 through both layers and reports where URLs appear."""

    def test_which_layer_fabricates_urls(self):
        brief = _las003_t12_brief()

        # ---- Stage 1: Strategist ----
        coaching_result = run_coaching_reasoning_workflow(
            brief,
            model_name=None,
        )
        directive = coaching_result["directive"]

        print("\n" + "=" * 70)
        print("STRATEGIST OUTPUT (coaching directive)")
        print("=" * 70)
        print(json.dumps(directive, indent=2))

        # Check every string field in the directive for URLs
        strategist_urls = []
        for key in ("opening", "main_message", "rationale", "tone", "recommend_material"):
            strategist_urls.extend(_find_urls(directive.get(key)))
        for item in directive.get("content_plan", []):
            strategist_urls.extend(_find_urls(item))
        for item in directive.get("avoid", []):
            strategist_urls.extend(_find_urls(item))

        print(f"\nURLs found in strategist output: {strategist_urls or 'NONE'}")

        # ---- Stage 2: Writer ----
        writer_directive = {
            k: v for k, v in directive.items()
            if k not in ("rationale", "reply_action")
        }
        rg_input = {
            "reply_mode": brief["reply_mode"],
            "coaching_directive": writer_directive,
            "plan_data": brief["validated_plan"],
            "delivery_context": brief["delivery_context"],
            "continuity_context": {
                "current_phase": "base",
                "current_block_focus": "main_base",
                "weeks_in_current_block": 4,
            },
        }

        generated = run_response_generation_workflow(
            rg_input,
            model_name=None,
        )
        email_body = generated.get("final_email_body", "")

        print("\n" + "=" * 70)
        print("WRITER OUTPUT (final email body)")
        print("=" * 70)
        print(email_body)

        writer_urls = _find_urls(email_body)
        print(f"\nURLs found in writer output: {writer_urls or 'NONE'}")

        # ---- Verdict ----
        print("\n" + "=" * 70)
        print("VERDICT")
        print("=" * 70)
        if strategist_urls and writer_urls:
            print("BOTH layers fabricated URLs")
        elif strategist_urls:
            print("STRATEGIST fabricated URLs — writer just followed the directive")
        elif writer_urls:
            print("WRITER fabricated URLs — strategist was clean")
        else:
            print("NEITHER layer fabricated URLs (no reproduction)")
        print("=" * 70)

        # We don't assert pass/fail — this is diagnostic.
        # But flag if URLs were fabricated so it shows in test output.
        if strategist_urls or writer_urls:
            print("\nWARNING: URL fabrication reproduced — bug #27 confirmed")
