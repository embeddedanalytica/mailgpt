"""Lightweight shared runtime helpers for skill execution."""

import json
import logging
import os
from typing import Any, Callable, Dict, List, Optional, Tuple, TypeVar

try:
    import openai  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via tests with stubs
    openai = None  # type: ignore


if openai is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")


# Prompt trace — when ENABLE_PROMPT_TRACE=true, every LLM call is recorded here.
# Consumers read prompt_trace after a pipeline run to inspect what was sent.
prompt_trace: List[Dict[str, Any]] = []


def _prompt_trace_enabled() -> bool:
    return os.getenv("ENABLE_PROMPT_TRACE", "false").strip().lower() == "true"


class SkillExecutionError(Exception):
    """Raised when a shared skill execution helper fails."""

    def __init__(self, message: str, *, code: str, raw_response: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.raw_response = str(raw_response or "")


def live_llm_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"


def require_openai_client(*, require_live_llm: bool, disabled_message: str):
    if require_live_llm and not live_llm_enabled():
        raise RuntimeError(disabled_message)
    if openai is None:
        raise RuntimeError("openai package is not installed")
    return openai.OpenAI()


def preview_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "")
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}..."


def execute_json_schema(
    *,
    logger: logging.Logger,
    model_name: str,
    system_prompt: str,
    user_content: str,
    schema_name: str,
    schema: Dict[str, Any],
    disabled_message: str,
    warning_log_name: str,
    retries: int = 0,
    require_live_llm: bool = True,
) -> Tuple[Dict[str, Any], str]:
    client = require_openai_client(
        require_live_llm=require_live_llm,
        disabled_message=disabled_message,
    )
    if _prompt_trace_enabled():
        prompt_trace.append({
            "skill": schema_name,
            "model": model_name,
            "system_prompt": system_prompt,
            "user_content": user_content,
        })

    attempts = max(1, int(retries) + 1)
    raw_content = ""

    for attempt in range(attempts):
        response = client.responses.create(
            model=model_name,
            input=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": schema_name,
                    "strict": True,
                    "schema": schema,
                }
            },
        )
        raw_content = str(getattr(response, "output_text", "") or "")
        try:
            payload = json.loads(raw_content)
            if isinstance(payload, dict):
                return payload, raw_content
        except Exception:
            pass

        logger.warning("%s invalid_json attempt=%s", warning_log_name, attempt + 1)

    raise SkillExecutionError(
        "invalid_json_response",
        code="invalid_json_response",
        raw_response=raw_content,
    )


TValidated = TypeVar("TValidated")


def run_validated_json_schema_workflow(
    *,
    logger: logging.Logger,
    model_name: str,
    system_prompt: str,
    user_content: str,
    schema_name: str,
    schema: Dict[str, Any],
    disabled_message: str,
    warning_log_name: str,
    validate_payload: Callable[[Dict[str, Any]], TValidated],
    workflow_label: str,
    proposal_error_factory: Callable[[str], Exception],
    retries: int = 0,
    require_live_llm: bool = True,
    on_raw_llm_response: Optional[Callable[[str], None]] = None,
) -> TValidated:
    raw_content = ""
    try:
        payload, raw_content = execute_json_schema(
            logger=logger,
            model_name=model_name,
            system_prompt=system_prompt,
            user_content=user_content,
            schema_name=schema_name,
            schema=schema,
            disabled_message=disabled_message,
            warning_log_name=warning_log_name,
            retries=retries,
            require_live_llm=require_live_llm,
        )
        if on_raw_llm_response is not None:
            on_raw_llm_response(raw_content)
        return validate_payload(payload)
    except SkillExecutionError as exc:
        logger.error(
            "%s failed: %s (raw_response_preview=%s)",
            workflow_label,
            exc,
            preview_text(exc.raw_response or raw_content),
        )
        raise proposal_error_factory(f"{workflow_label}_failed") from exc
    except Exception as exc:
        logger.error(
            "%s failed: %s (raw_response_preview=%s)",
            workflow_label,
            exc,
            preview_text(raw_content),
        )
        raise proposal_error_factory(f"{workflow_label}_failed") from exc
