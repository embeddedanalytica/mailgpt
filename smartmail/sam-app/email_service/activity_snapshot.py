"""
Manual activity snapshot parsing from inbound email text.
"""
from __future__ import annotations

import re
from typing import Any, Dict, Optional


_ACTIVITY_KEYWORDS = {
    "run": "running",
    "ran": "running",
    "running": "running",
    "jog": "running",
    "ride": "cycling",
    "rode": "cycling",
    "bike": "cycling",
    "cycling": "cycling",
    "swim": "swimming",
    "swam": "swimming",
    "swimming": "swimming",
    "lift": "strength",
    "lifted": "strength",
    "strength": "strength",
    "gym": "strength",
    "hike": "hiking",
    "hiked": "hiking",
    "walk": "walking",
    "walked": "walking",
    "rest": "rest",
    "rested": "rest",
}


def _detect_activity_type(text: str) -> Optional[str]:
    lowered = text.lower()
    for keyword, activity_type in _ACTIVITY_KEYWORDS.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            return activity_type
    if re.search(r"\bcheck[ -]?in\b", lowered):
        return "check-in"
    return None


def _extract_duration(text: str) -> Optional[str]:
    match = re.search(
        r"\b(?:(\d{1,2})\s*h(?:ours?)?\s*)?(?:(\d{1,3})\s*m(?:in(?:utes?)?)?)\b",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    hours = match.group(1)
    minutes = match.group(2)
    if hours and minutes:
        return f"{int(hours)}h {int(minutes)}m"
    if hours:
        return f"{int(hours)}h"
    if minutes:
        return f"{int(minutes)}m"
    return None


def _extract_key_metric(text: str) -> Optional[str]:
    distance = re.search(r"\b(\d+(?:\.\d+)?)\s*(km|k|mi|miles?)\b", text, re.IGNORECASE)
    if distance:
        return f"distance:{distance.group(1)}{distance.group(2).lower()}"
    pace = re.search(r"\bpace\s*[:=]?\s*([0-9]{1,2}:[0-9]{2})\b", text, re.IGNORECASE)
    if pace:
        return f"pace:{pace.group(1)}"
    hr = re.search(r"\b(?:hr|heart rate|avg hr)\s*[:=]?\s*(\d{2,3})\b", text, re.IGNORECASE)
    if hr:
        return f"heart_rate:{hr.group(1)}"
    return None


def _extract_subjective_feedback(text: str) -> Optional[str]:
    match = re.search(
        r"((?:felt|feeling|energy|soreness|sleep)\b[^.!?\n]{0,120})",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return match.group(1).strip(" .")


def _parse_subjective_state(text: str) -> Dict[str, str]:
    lowered = text.lower()
    energy = "unknown"
    soreness = "unknown"
    sleep = "unknown"

    if re.search(r"\b(high energy|great energy|energetic)\b", lowered):
        energy = "high"
    elif re.search(r"\b(low energy|drained|exhausted|tired)\b", lowered):
        energy = "low"
    elif re.search(r"\b(energy ok|energy good|normal energy)\b", lowered):
        energy = "ok"

    if re.search(r"\b(very sore|high soreness)\b", lowered):
        soreness = "high"
    elif re.search(r"\b(little sore|low soreness|not sore)\b", lowered):
        soreness = "low"
    elif re.search(r"\b(sore|soreness)\b", lowered):
        soreness = "medium"

    if re.search(r"\b(good sleep|slept well)\b", lowered):
        sleep = "good"
    elif re.search(r"\b(poor sleep|bad sleep|slept poorly)\b", lowered):
        sleep = "poor"
    elif re.search(r"\b(ok sleep|sleep ok|normal sleep)\b", lowered):
        sleep = "ok"

    return {"energy": energy, "soreness": soreness, "sleep": sleep}


def parse_manual_activity_snapshot_from_email(body: str, now_epoch: int) -> Optional[Dict[str, Any]]:
    """
    Returns manual activity snapshot dict or None when no check-in signal is detected.
    """
    activity_type = _detect_activity_type(body)
    if not activity_type:
        return None

    snapshot: Dict[str, Any] = {
        "activity_type": activity_type,
        "timestamp": int(now_epoch),
        "source": "manual",
    }
    duration = _extract_duration(body)
    if duration:
        snapshot["duration"] = duration
    key_metric = _extract_key_metric(body)
    if key_metric:
        snapshot["key_metric"] = key_metric
    subjective_feedback = _extract_subjective_feedback(body)
    if subjective_feedback:
        snapshot["subjective_feedback"] = subjective_feedback
    snapshot["subjective_state"] = _parse_subjective_state(body)
    return snapshot
