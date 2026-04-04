"""Runner for the candidate-operation memory refresh workflow (AM2)."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from athlete_memory_contract import normalize_fact_key
from athlete_memory_contract import format_unix_timestamp_for_prompt
from config import PROFILE_EXTRACTION_MODEL
from skills.memory.unified.errors import MemoryRefreshError, MemoryRefreshPromptError
from skills.memory.unified.prompt import SYSTEM_PROMPT
from skills.memory.unified.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.unified.validator import validate_candidate_memory_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)
_TEXT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "with",
}

# Reversal-cue patterns for the backstop check
_REVERSAL_CUE_PATTERNS = [
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\bused to\b", re.IGNORECASE),
    re.compile(r"\bswitched\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\bmoved\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\bchanged\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\breplaced\b.{0,60}\bwith\b", re.IGNORECASE),
    re.compile(r"\bnow\b.{0,30}\binstead\b", re.IGNORECASE),
    re.compile(r"\bopened up\b", re.IGNORECASE),
    re.compile(r"\bnot anymore\b", re.IGNORECASE),
    re.compile(r"\bswitched\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bchanged\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bmoved\b.{0,20}\bto\b", re.IGNORECASE),
]
_REQUEST_CUE_PATTERNS = [
    re.compile(r"\?", re.IGNORECASE),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bplease\b", re.IGNORECASE),
    re.compile(r"\bwhat\b", re.IGNORECASE),
    re.compile(r"\bwhich\b", re.IGNORECASE),
    re.compile(r"\bwhen\b", re.IGNORECASE),
    re.compile(r"\bwhere\b", re.IGNORECASE),
    re.compile(r"\bconfirm\b", re.IGNORECASE),
    re.compile(r"\bsend\b", re.IGNORECASE),
    re.compile(r"\bshare\b", re.IGNORECASE),
    re.compile(r"\btell me\b", re.IGNORECASE),
    re.compile(r"\blet me know\b", re.IGNORECASE),
    re.compile(r"\breply with\b", re.IGNORECASE),
]


def _has_reversal_cues(text: str) -> bool:
    """Returns True if the text contains explicit reversal language."""
    return any(p.search(text) for p in _REVERSAL_CUE_PATTERNS)


def _normalize_text_tokens(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in _TEXT_STOPWORDS
    }


def _fact_reference_tokens(fact: Dict[str, Any]) -> set[str]:
    tokens = _normalize_text_tokens(fact.get("summary"))
    tokens.update(_normalize_text_tokens(str(fact.get("fact_key", "")).replace(":", " ")))
    return tokens


def _materially_references_fact(text: str, fact: Dict[str, Any]) -> bool:
    candidate_tokens = _normalize_text_tokens(text)
    fact_tokens = _fact_reference_tokens(fact)
    if not candidate_tokens or not fact_tokens:
        return False
    overlap = candidate_tokens & fact_tokens
    if len(overlap) >= 3:
        return True
    smaller = min(len(candidate_tokens), len(fact_tokens))
    negation_markers = {"no", "not", "old", "prior", "retire", "retired", "replace", "replaced", "former"}
    if len(overlap) >= 2 and candidate_tokens & negation_markers:
        return True
    if smaller >= 2 and len(overlap) == smaller:
        return True
    return False


def _find_fact_by_target_id(existing_facts: List[Dict[str, Any]], target_id: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(target_id, str) or not target_id.strip():
        return None
    for fact in existing_facts:
        if fact.get("memory_note_id") == target_id:
            return fact
    return None


def _collect_superseded_facts(
    candidates: List[Dict[str, Any]],
    existing_facts: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    superseded: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    facts_by_key = {
        fact.get("fact_key"): fact
        for fact in existing_facts
        if isinstance(fact, dict) and isinstance(fact.get("fact_key"), str)
    }

    def _append_fact(fact: Optional[Dict[str, Any]]) -> None:
        if not isinstance(fact, dict):
            return
        memory_note_id = fact.get("memory_note_id")
        if isinstance(memory_note_id, str) and memory_note_id in seen_ids:
            return
        if isinstance(memory_note_id, str):
            seen_ids.add(memory_note_id)
        superseded.append(fact)

    for candidate in candidates:
        if candidate.get("action") == "retire":
            _append_fact(_find_fact_by_target_id(existing_facts, candidate.get("target_id")))
        elif candidate.get("action") == "upsert" and not candidate.get("target_id"):
            fact_type = candidate.get("fact_type")
            if fact_type not in {"schedule", "constraint"}:
                continue
            for raw_key in candidate.get("supersedes_fact_keys") or []:
                if not isinstance(raw_key, str) or not raw_key.strip():
                    continue
                canonical = normalize_fact_key(fact_type, raw_key.removeprefix(f"{fact_type}:"))
                _append_fact(facts_by_key.get(canonical))

    return superseded


def _continuity_segments(continuity: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(continuity, dict):
        return []
    segments: List[str] = []
    for field in ("summary", "last_recommendation"):
        value = continuity.get(field)
        if isinstance(value, str) and value.strip():
            segments.append(value.strip())
    for item in continuity.get("open_loops") or []:
        if isinstance(item, str) and item.strip():
            segments.append(item.strip())
    return segments


def _contains_request_cues(text: str) -> bool:
    return any(pattern.search(text) for pattern in _REQUEST_CUE_PATTERNS)


def _loop_answered_by_athlete(loop: str, inbound_email: str) -> bool:
    loop_tokens = _normalize_text_tokens(loop)
    inbound_tokens = _normalize_text_tokens(inbound_email)
    overlap = loop_tokens & inbound_tokens
    if len(overlap) >= 3:
        return True
    if len(overlap) >= 2 and any(token in loop_tokens for token in {"date", "dates", "day", "days", "time", "times", "travel"}):
        return True
    return False


def _prune_resolved_open_loops(
    *,
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
    next_open_loops: List[str],
) -> List[str]:
    if not isinstance(current_continuity, dict):
        return next_open_loops

    inbound_email = interaction_context.get("inbound_email")
    coach_reply = interaction_context.get("coach_reply")
    if not isinstance(inbound_email, str) or not inbound_email.strip():
        return next_open_loops

    coach_reasked = False
    resolved_prior_loops: List[str] = []
    for prior_loop in current_continuity.get("open_loops") or []:
        if not isinstance(prior_loop, str) or not prior_loop.strip():
            continue
        if not _loop_answered_by_athlete(prior_loop, inbound_email):
            continue

        coach_reasked = (
            isinstance(coach_reply, str)
            and _materially_references_fact(coach_reply, {"summary": prior_loop, "fact_key": ""})
            and _contains_request_cues(coach_reply)
        )
        if not coach_reasked:
            resolved_prior_loops.append(prior_loop)

    if not resolved_prior_loops:
        return next_open_loops

    return [
        loop
        for loop in next_open_loops
        if not any(
            _materially_references_fact(loop, {"summary": prior_loop, "fact_key": ""})
            for prior_loop in resolved_prior_loops
        )
    ]


def _stale_continuity_carryover_detected(
    *,
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
    validated: Dict[str, Any],
) -> bool:
    prior_segments = _continuity_segments(current_continuity)
    if not prior_segments:
        return False

    latest_context_tokens = _normalize_text_tokens(interaction_context.get("inbound_email"))
    latest_context_tokens.update(_normalize_text_tokens(interaction_context.get("coach_reply")))

    for segment in prior_segments:
        segment_tokens = _normalize_text_tokens(segment)
        if not segment_tokens:
            continue
        if latest_context_tokens & segment_tokens:
            continue

        for next_segment in _continuity_segments(validated.get("continuity")):
            overlap = _normalize_text_tokens(next_segment) & segment_tokens
            if len(overlap) >= 3:
                return True
    return False


def _drop_segments_referencing_facts(text: str, facts: List[Dict[str, Any]]) -> str:
    if not isinstance(text, str) or not text.strip() or not facts:
        return text
    segments = [segment.strip(" ,;") for segment in re.split(r"[;()]", text) if segment.strip(" ,;")]
    kept_segments = [
        segment
        for segment in segments
        if not any(_materially_references_fact(segment, fact) for fact in facts)
    ]
    if not kept_segments:
        return ""
    return "; ".join(kept_segments)


def _clean_validated_output(
    *,
    validated: Dict[str, Any],
    existing_facts: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    superseded_facts = _collect_superseded_facts(validated["candidates"], existing_facts)
    if superseded_facts:
        for candidate in validated["candidates"]:
            if candidate.get("action") == "upsert" and not candidate.get("target_id"):
                summary = candidate.get("summary")
                if isinstance(summary, str):
                    cleaned_summary = _drop_segments_referencing_facts(summary, superseded_facts)
                    if cleaned_summary:
                        candidate["summary"] = cleaned_summary

        continuity = validated["continuity"]
        continuity["summary"] = (
            _drop_segments_referencing_facts(continuity["summary"], superseded_facts)
            or "Current coaching context updated."
        )
        continuity["open_loops"] = [
            cleaned_loop
            for loop in continuity["open_loops"]
            if (cleaned_loop := _drop_segments_referencing_facts(loop, superseded_facts)).strip()
        ]
        coach_reply = interaction_context.get("coach_reply")
        if isinstance(coach_reply, str) and coach_reply.strip():
            continuity["last_recommendation"] = coach_reply.strip()

    continuity = validated["continuity"]
    continuity["open_loops"] = _prune_resolved_open_loops(
        current_continuity=current_continuity,
        interaction_context=interaction_context,
        next_open_loops=list(continuity["open_loops"]),
    )

    if _stale_continuity_carryover_detected(
        current_continuity=current_continuity,
        interaction_context=interaction_context,
        validated=validated,
    ):
        continuity = validated["continuity"]
        continuity["summary"] = "Current coaching context updated."
        continuity["last_recommendation"] = "Use the updated current schedule and constraints going forward."
        continuity["open_loops"] = [
            loop
            for loop in continuity["open_loops"]
            if _normalize_text_tokens(loop) & (
                _normalize_text_tokens(interaction_context.get("inbound_email"))
                | _normalize_text_tokens(interaction_context.get("coach_reply"))
            )
        ]

    return validated


def _candidates_address_reversal(
    candidates: List[Dict[str, Any]],
    existing_facts: List[Dict[str, Any]],
) -> bool:
    """Returns True if reversal cues are adequately addressed by the candidates.

    A reversal is considered addressed when:
    - At least one retire candidate exists, OR
    - A targeted upsert (update-in-place) exists, OR
    - There are NO existing schedule/constraint facts that could conflict
      with a newly upserted schedule/constraint fact.

    Returns False (triggering a retry) when a new schedule/constraint fact is
    created but an existing fact of the same type is not retired or updated —
    this is the stale-retirement gap.
    """
    has_retire = False
    has_targeted_upsert = False
    new_schedule_constraint_types: set[str] = set()

    for c in candidates:
        action = c.get("action")
        if action == "retire":
            has_retire = True
        elif action == "upsert" and c.get("target_id"):
            has_targeted_upsert = True
        elif action == "upsert" and not c.get("target_id"):
            ft = c.get("fact_type", "")
            if ft in ("schedule", "constraint"):
                new_schedule_constraint_types.add(ft)

    # If there's an explicit retire or in-place update, the LLM engaged with the change
    if has_retire or has_targeted_upsert:
        return True

    # If no new schedule/constraint facts were created, nothing to conflict
    if not new_schedule_constraint_types:
        return False

    # Check if existing facts of the same type exist — if so, the LLM likely
    # created a replacement without retiring the old one
    for fact in existing_facts:
        ft = fact.get("fact_type", "")
        if ft in new_schedule_constraint_types:
            return False  # conflict detected — retry

    # New fact type with no existing conflict
    return True


def _format_memory_notes_for_prompt(memory_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Formats active durable facts for the LLM prompt."""
    formatted: List[Dict[str, Any]] = []
    for note in memory_notes:
        if not isinstance(note, dict):
            continue
        entry: Dict[str, Any] = {
            "memory_note_id": str(note.get("memory_note_id", "")),
            "fact_type": str(note.get("fact_type", "")),
            "fact_key": str(note.get("fact_key", "")),
            "summary": str(note.get("summary", "")),
        }
        last_confirmed = note.get("last_confirmed_at")
        if last_confirmed is not None:
            try:
                entry["last_confirmed_readable"] = format_unix_timestamp_for_prompt(last_confirmed)
            except Exception:
                pass
        if entry["memory_note_id"] and entry["summary"]:
            formatted.append(entry)
    return formatted


def _format_continuity_for_prompt(continuity: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Formats continuity summary for the LLM prompt."""
    if continuity is None or not isinstance(continuity, dict):
        return None
    formatted: Dict[str, Any] = {}
    for field in ("summary", "last_recommendation"):
        value = continuity.get(field)
        if isinstance(value, str) and value.strip():
            formatted[field] = value.strip()
    open_loops = continuity.get("open_loops")
    if isinstance(open_loops, list):
        formatted["open_loops"] = [
            str(item).strip() for item in open_loops if isinstance(item, str) and str(item).strip()
        ]
    updated_at = continuity.get("updated_at")
    if updated_at is not None:
        try:
            formatted["updated_at_readable"] = format_unix_timestamp_for_prompt(updated_at)
        except Exception:
            pass
    return formatted if formatted else None


def build_memory_refresh_user_payload(
    *,
    current_memory_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> str:
    """Builds the JSON user-message payload for the candidate memory refresh LLM call."""
    if not isinstance(interaction_context, dict):
        raise MemoryRefreshPromptError("interaction_context must be a dict")

    payload = {
        "current_active_facts": _format_memory_notes_for_prompt(current_memory_notes),
        "current_continuity": _format_continuity_for_prompt(current_continuity),
        "interaction_context": interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _run_single_attempt(
    *,
    user_payload: str,
) -> Dict[str, Any]:
    """Runs a single LLM call and validates the response."""
    data, raw_content = execute_json_schema(
        logger=logger,
        model_name=PROFILE_EXTRACTION_MODEL,
        system_prompt=SYSTEM_PROMPT,
        user_content=user_payload,
        schema_name=JSON_SCHEMA_NAME,
        schema=JSON_SCHEMA,
        disabled_message="live candidate memory refresh LLM calls are disabled",
        warning_log_name="memory_refresh_candidates",
    )
    return validate_candidate_memory_response(data)


def run_candidate_memory_refresh(
    *,
    current_memory_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Runs the candidate-operation memory refresh skill.

    Returns a validated dict with keys: candidates, continuity.
    Raises MemoryRefreshError on failure.
    """
    raw_content = ""
    try:
        user_payload = build_memory_refresh_user_payload(
            current_memory_notes=current_memory_notes,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )
        logger.info(
            "Candidate memory refresh starting payload_chars=%s",
            len(user_payload),
        )

        validated = _run_single_attempt(user_payload=user_payload)

        # --- Reversal backstop ---
        inbound_email = interaction_context.get("inbound_email", "")
        if (
            isinstance(inbound_email, str)
            and _has_reversal_cues(inbound_email)
            and not _candidates_address_reversal(
                validated["candidates"], current_memory_notes
            )
        ):
            logger.warning(
                "reversal_backstop: reversal cues detected but no retire/update on "
                "schedule or constraint — retrying once"
            )
            validated = _run_single_attempt(user_payload=user_payload)

        validated = _clean_validated_output(
            validated=validated,
            existing_facts=current_memory_notes,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )

        logger.info(
            "Candidate memory refresh completed candidate_count=%s open_loops=%s",
            len(validated["candidates"]),
            len(validated["continuity"]["open_loops"]),
        )
        return validated

    except MemoryRefreshError:
        raise
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Candidate memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise MemoryRefreshError(
            "LLM candidate memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
