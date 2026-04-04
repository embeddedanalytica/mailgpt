"""Focused doctrine inspection script for representative coaching scenarios.

Run locally from `sam-app/email_service`:

    python3 focused_doctrine_scenarios.py

Inspect a custom inbound message without editing this file:

    python3 focused_doctrine_scenarios.py --message "Can I swap my easy run to Friday?"

Optionally enable live strategist output:

    ENABLE_LIVE_LLM_CALLS=true python3 focused_doctrine_scenarios.py
"""

from __future__ import annotations

import argparse
import json
import os
from copy import deepcopy
from typing import Any

from skills.coaching_reasoning.doctrine import build_doctrine_selection_trace
from skills.coaching_reasoning.prompt import build_system_prompt
from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow


def _base_brief() -> dict[str, Any]:
    return {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Half marathon in 10 weeks",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
            "primary_sport": "running",
            "constraints_summary": "",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
            "risk_recent_history": ["green", "green", "green"],
            "weeks_in_coaching": 4,
        },
        "validated_plan": {},
        "memory_context": {},
        "delivery_context": {"inbound_body": "Solid week -- feeling good."},
    }


def _merge(base: dict[str, Any], overrides: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in overrides.items():
        merged[key] = value
    return merged


SCENARIOS: list[dict[str, Any]] = [
    {
        "name": "simple_ack",
        "brief": _merge(
            _base_brief(),
            {"delivery_context": {"inbound_body": "Sounds good. Starting Monday."}},
        ),
    },
    {
        "name": "lightweight_question",
        "brief": _merge(
            _base_brief(),
            {"delivery_context": {"inbound_body": "Can I swap my easy run to Friday?"}},
        ),
    },
    {
        "name": "planning",
        "brief": _merge(
            _base_brief(),
            {
                "delivery_context": {
                    "inbound_body": "Can you map next week and tell me what the week should look like?"
                }
            },
        ),
    },
    {
        "name": "milestone",
        "brief": _merge(
            _base_brief(),
            {
                "delivery_context": {
                    "inbound_body": "I finished the race today and it feels like a real milestone."
                }
            },
        ),
    },
    {
        "name": "return_to_load",
        "brief": _merge(
            _base_brief(),
            {
                "delivery_context": {
                    "inbound_body": "Shin is quiet again. Can I bring back tempo next week?"
                },
                "decision_context": {
                    "track": "main_build",
                    "phase": "build",
                    "risk_flag": "green",
                    "today_action": "do planned",
                    "clarification_needed": False,
                    "risk_recent_history": ["yellow", "yellow", "green"],
                    "weeks_in_coaching": 4,
                },
            },
        ),
    },
    {
        "name": "setback_management",
        "brief": _merge(
            _base_brief(),
            {
                "delivery_context": {
                    "inbound_body": "Pain flared after the long run, so I'm backing off this week."
                },
                "decision_context": {
                    "track": "main_build",
                    "phase": "build",
                    "risk_flag": "yellow",
                    "today_action": "adjust",
                    "clarification_needed": False,
                    "risk_recent_history": ["yellow", "green", "green"],
                    "weeks_in_coaching": 4,
                },
            },
        ),
    },
]


def _print_header(name: str) -> None:
    print()
    print("=" * 80)
    print(name)
    print("=" * 80)


def _print_trace(trace: dict[str, Any]) -> None:
    print("TRACE:")
    print(json.dumps(trace, indent=2, sort_keys=True))


def _print_prompt_preview(prompt: str, max_chars: int = 3500) -> None:
    preview = prompt[:max_chars]
    if len(prompt) > max_chars:
        preview += "\n... [truncated]"
    print("PROMPT PREVIEW:")
    print(preview)


def _build_custom_scenario(
    message: str,
    *,
    name: str | None = None,
    risk_flag: str | None = None,
    clarification_needed: bool = False,
) -> dict[str, Any]:
    brief = _merge(
        _base_brief(),
        {"delivery_context": {"inbound_body": message}},
    )
    if risk_flag is not None:
        brief["decision_context"]["risk_flag"] = risk_flag
    if clarification_needed:
        brief["decision_context"]["clarification_needed"] = True
    return {"name": name or "custom_input", "brief": brief}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect doctrine selection for built-in or custom coaching scenarios."
    )
    parser.add_argument(
        "--message",
        help="Custom inbound athlete message to inspect.",
    )
    parser.add_argument(
        "--name",
        help="Optional label for the custom scenario.",
    )
    parser.add_argument(
        "--risk-flag",
        choices=["green", "yellow", "red"],
        help="Optional decision_context.risk_flag override for a custom scenario.",
    )
    parser.add_argument(
        "--clarification-needed",
        action="store_true",
        help="Set decision_context.clarification_needed for a custom scenario.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    live = os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"
    scenarios = SCENARIOS

    if args.message:
        scenarios = [
            _build_custom_scenario(
                args.message,
                name=args.name,
                risk_flag=args.risk_flag,
                clarification_needed=args.clarification_needed,
            )
        ]

    for scenario in scenarios:
        brief = scenario["brief"]
        trace = build_doctrine_selection_trace(brief)
        prompt = build_system_prompt(brief)

        _print_header(scenario["name"])
        print("INBOUND:")
        print(brief["delivery_context"]["inbound_body"])
        print()
        _print_trace(trace)
        print()
        _print_prompt_preview(prompt)

        if live:
            print()
            print("DIRECTIVE:")
            result = run_coaching_reasoning_workflow(brief)
            print(json.dumps(result["directive"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
