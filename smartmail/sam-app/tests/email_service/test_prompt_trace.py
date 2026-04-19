"""Trace every LLM prompt in the coaching pipeline for a single inbound message.

Uses the built-in prompt trace in skill_runtime (ENABLE_PROMPT_TRACE=true) to
capture the system_prompt and user_content of every LLM call, then prints each
prompt in execution order.

Run:
    ENABLE_LIVE_LLM_CALLS=true ENABLE_PROMPT_TRACE=true python3 -m unittest -v test_prompt_trace
"""

import json
import os
import unittest

from skills import runtime as skill_runtime

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"
_TRACE = os.getenv("ENABLE_PROMPT_TRACE", "false").strip().lower() == "true"

# The inbound message that triggers the full pipeline
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


def _print_prompt_trace(calls):
    """Pretty-print the captured prompt trace."""
    print("\n" + "=" * 80)
    print(f"PROMPT TRACE — {len(calls)} LLM call(s) captured")
    print("=" * 80)

    for i, call in enumerate(calls, 1):
        print(f"\n{'─' * 80}")
        print(f"  CALL {i}/{len(calls)}:  skill={call['skill']}  model={call['model']}")
        print(f"{'─' * 80}")

        print(f"\n  SYSTEM PROMPT ({len(call['system_prompt'])} chars):")
        print(f"  {'·' * 40}")
        for line in call["system_prompt"].split("\n"):
            print(f"  │ {line}")

        print(f"\n  USER CONTENT ({len(call['user_content'])} chars):")
        print(f"  {'·' * 40}")
        try:
            parsed = json.loads(call["user_content"])
            formatted = json.dumps(parsed, indent=2)
            for line in formatted.split("\n"):
                print(f"  │ {line}")
        except (json.JSONDecodeError, TypeError):
            for line in call["user_content"].split("\n"):
                print(f"  │ {line}")

    print(f"\n{'=' * 80}")
    print("EXECUTION ORDER:")
    print("=" * 80)
    for i, call in enumerate(calls, 1):
        prompt_len = len(call["system_prompt"])
        input_len = len(call["user_content"])
        print(f"  {i}. {call['skill']:.<40s} model={call['model']:<25s} prompt={prompt_len:>5d} chars  input={input_len:>5d} chars")
    print("=" * 80)


@unittest.skipUnless(_LIVE and _TRACE, "requires ENABLE_LIVE_LLM_CALLS=true ENABLE_PROMPT_TRACE=true")
class TestPromptTrace(unittest.TestCase):
    """Sends one message through the strategist + writer and prints every LLM prompt."""

    def setUp(self):
        skill_runtime.prompt_trace.clear()

    def test_trace_all_prompts(self):
        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow
        from skills.response_generation.runner import run_response_generation_workflow

        brief = {
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

        continuity_context = {
            "current_phase": "base",
            "current_block_focus": "main_base",
            "weeks_in_current_block": 4,
        }

        # Stage 1: Strategist
        coaching_result = run_coaching_reasoning_workflow(
            brief,
            model_name=None,
            continuity_context=continuity_context,
        )
        directive = coaching_result["directive"]

        # Stage 2: Writer
        writer_directive = {
            k: v for k, v in directive.items()
            if k not in ("rationale", "reply_action")
        }
        rg_input = {
            "reply_mode": brief["reply_mode"],
            "coaching_directive": writer_directive,
            "plan_data": brief["validated_plan"],
            "delivery_context": brief["delivery_context"],
            "continuity_context": continuity_context,
        }
        run_response_generation_workflow(rg_input, model_name=None)

        _print_prompt_trace(skill_runtime.prompt_trace)
