"""CoachingDirective JSON schema for the coaching-reasoning workflow."""

from typing import Any, Dict

JSON_SCHEMA_NAME = "coaching_directive"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reply_action",
        "opening",
        "main_message",
        "content_plan",
        "avoid",
        "tone",
        "recommend_material",
        "rationale",
        "continuity_recommendation",
    ],
    "properties": {
        "reply_action": {
            "type": "string",
            "enum": ["send", "suppress"],
            "description": "Whether to send a coach reply this turn or suppress it.",
        },
        "opening": {
            "type": "string",
            "minLength": 1,
            "description": "How to open the email — specific to this athlete's situation.",
        },
        "main_message": {
            "type": "string",
            "minLength": 1,
            "description": "Core coaching message for this turn.",
        },
        "content_plan": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "description": "Ordered list of content items to include in the email.",
        },
        "avoid": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Things the writer should NOT say or do.",
        },
        "tone": {
            "type": "string",
            "minLength": 1,
            "description": "Tone guidance for the writer.",
        },
        "recommend_material": {
            "type": ["string", "null"],
            "description": "Book or video recommendation if contextually relevant, otherwise null.",
        },
        "rationale": {
            "type": "string",
            "minLength": 1,
            "description": "Internal reasoning — for eval/logging only, NOT forwarded to the writer.",
        },
        "continuity_recommendation": {
            "type": "object",
            "additionalProperties": False,
            "description": (
                "Continuity state recommendation. Emit on every coaching turn. "
                "Use 'keep' as default when no change is needed."
            ),
            "required": [
                "recommended_goal_horizon_type",
                "recommended_phase",
                "recommended_block_focus",
                "recommended_transition_action",
                "recommended_transition_reason",
                "recommended_goal_event_date",
            ],
            "properties": {
                "recommended_goal_horizon_type": {
                    "type": "string",
                    "enum": ["event", "general_fitness", "performance_block", "return_to_training"],
                    "description": "Goal horizon type for the athlete.",
                },
                "recommended_phase": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Canonical training phase label.",
                },
                "recommended_block_focus": {
                    "type": "string",
                    "enum": [
                        "initial_assessment",
                        "rebuild_consistency",
                        "controlled_load_progression",
                        "maintain_fitness",
                        "maintain_through_constraints",
                        "event_specific_build",
                        "peak_for_event",
                        "taper_for_event",
                        "return_safely",
                        "recovery_deload",
                    ],
                    "description": "Current block focus intent.",
                },
                "recommended_transition_action": {
                    "type": "string",
                    "enum": ["keep", "focus_shift", "phase_shift", "reset_block"],
                    "description": (
                        "What to do: keep=no change, focus_shift=change block focus, "
                        "phase_shift=change training phase, reset_block=full block reset."
                    ),
                },
                "recommended_transition_reason": {
                    "type": "string",
                    "minLength": 1,
                    "description": "Short explanation of why this action is recommended.",
                },
                "recommended_goal_event_date": {
                    "type": ["string", "null"],
                    "description": "ISO date (YYYY-MM-DD) of the goal event, or null if not applicable.",
                },
            },
        },
    },
}
