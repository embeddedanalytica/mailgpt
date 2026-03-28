"""JSON schema for obedience evaluation output (OpenAI strict mode)."""

from typing import Any, Dict

JSON_SCHEMA_NAME = "obedience_evaluation"

JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["passed", "violations", "corrected_email_body", "reasoning"],
    "properties": {
        "passed": {
            "type": "boolean",
            "description": "true if the email is fully compliant with the directive, false if any violation was found.",
        },
        "violations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["violation_type", "detail"],
                "properties": {
                    "violation_type": {
                        "type": "string",
                        "enum": [
                            "reopened_resolved_topic",
                            "ignored_latest_constraint",
                            "answered_from_stale_context",
                            "exceeded_requested_scope",
                            "introduced_unsupported_assumption",
                            "missed_exact_instruction",
                            "physical_presence_implied",
                            "metadata_leak",
                        ],
                        "description": "Failure type from the obedience taxonomy.",
                    },
                    "detail": {
                        "type": "string",
                        "minLength": 1,
                        "description": "What specifically is wrong — quote the offending text.",
                    },
                },
            },
            "description": "Empty array when passed=true. One entry per violation when passed=false.",
        },
        "corrected_email_body": {
            "type": ["string", "null"],
            "description": "Corrected email text when passed=false. null when passed=true.",
        },
        "reasoning": {
            "type": "string",
            "minLength": 1,
            "description": "Brief explanation of the evaluation decision. For logging only.",
        },
    },
}
