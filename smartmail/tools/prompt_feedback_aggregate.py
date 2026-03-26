#!/usr/bin/env python3
"""Aggregate live athlete simulator judge feedback into a deterministic batch artifact."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_NAME = "aggregate.json"
UNTAGGED_ISSUE = "untagged"
SCORE_FIELDS = (
    "understanding",
    "memory_continuity",
    "personalization",
    "coaching_quality",
    "tone_trust",
    "communication_style_fit",
    "safety",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Aggregate live athlete simulator judge feedback artifacts."
    )
    parser.add_argument(
        "--input-dir",
        required=True,
        help="Directory containing live athlete simulator attempt JSONL artifacts.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path override; defaults to <input-dir>/aggregate.json.",
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _average(values: Iterable[float]) -> float:
    sequence = list(values)
    if not sequence:
        return 0.0
    return round(sum(sequence) / len(sequence), 3)


def _sorted_counter(counter: Counter[str]) -> Dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _attempt_sort_key(path: Path) -> Tuple[str, str]:
    return (path.stem.lower(), path.name.lower())


def _parse_attempt_from_name(path: Path) -> int:
    stem = path.stem
    marker = "-attempt"
    if marker not in stem:
        return 0
    remainder = stem.split(marker, 1)[1]
    digits = []
    for char in remainder:
        if char.isdigit():
            digits.append(char)
        else:
            break
    if not digits:
        return 0
    return int("".join(digits))


def _load_attempt_metadata(jsonl_path: Path) -> Dict[str, Any]:
    summary_path = jsonl_path.with_suffix(".summary.json")
    if summary_path.exists():
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        return {
            "scenario_id": str(payload.get("scenario_id") or jsonl_path.stem),
            "scenario_name": str(payload.get("scenario_name") or payload.get("scenario_id") or jsonl_path.stem),
            "attempt": int(payload.get("attempt") or _parse_attempt_from_name(jsonl_path)),
            "run_id": str(payload.get("run_id") or jsonl_path.stem),
        }
    return {
        "scenario_id": jsonl_path.stem.split("-attempt", 1)[0].upper(),
        "scenario_name": jsonl_path.stem.split("-attempt", 1)[0].upper(),
        "attempt": _parse_attempt_from_name(jsonl_path),
        "run_id": jsonl_path.stem,
    }


def _require_dict(value: Any, *, context: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"{context} must be an object.")
    return value


def _require_string_list(value: Any, *, context: str) -> List[str]:
    if not isinstance(value, list):
        raise ValueError(f"{context} must be a list.")
    result: List[str] = []
    for index, item in enumerate(value, start=1):
        if not isinstance(item, str) or not item.strip():
            raise ValueError(f"{context}[{index}] must be a non-empty string.")
        result.append(item.strip())
    return result


def _normalize_scores(value: Any, *, context: str) -> Dict[str, float]:
    scores = _require_dict(value, context=context)
    normalized: Dict[str, float] = {}
    for field in SCORE_FIELDS:
        raw = scores.get(field)
        if not isinstance(raw, (int, float)):
            raise ValueError(f"{context}.{field} must be numeric.")
        normalized[field] = float(raw)
    return normalized


def _iter_judge_events(input_dir: Path) -> Tuple[List[Path], List[Dict[str, Any]]]:
    attempt_files = sorted(
        [
            path
            for path in input_dir.glob("*.jsonl")
            if not path.name.endswith(".summary.json")
        ],
        key=_attempt_sort_key,
    )
    if not attempt_files:
        raise RuntimeError(f"No attempt JSONL files found in {input_dir}")

    judge_events: List[Dict[str, Any]] = []
    for path in attempt_files:
        metadata = _load_attempt_metadata(path)
        with path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                stripped = line.strip()
                if not stripped:
                    continue
                try:
                    payload = json.loads(stripped)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"{path}:{line_number} contains invalid JSON: {exc.msg}") from exc
                if payload.get("phase") != "judge_result":
                    continue
                result = _require_dict(payload.get("result"), context=f"{path}:{line_number}.result")
                judge_events.append(
                    {
                        "scenario_id": metadata["scenario_id"],
                        "scenario_name": metadata["scenario_name"],
                        "attempt": metadata["attempt"],
                        "run_id": metadata["run_id"],
                        "turn": int(payload.get("turn") or 0),
                        "headline": str(result.get("headline") or "").strip(),
                        "athlete_likely_experience": str(result.get("athlete_likely_experience") or "").strip(),
                        "improved_reply_example": str(result.get("improved_reply_example") or "").strip(),
                        "scores": _normalize_scores(result.get("scores"), context=f"{path}:{line_number}.result.scores"),
                        "what_missed": _require_string_list(
                            result.get("what_missed", []),
                            context=f"{path}:{line_number}.result.what_missed",
                        ),
                        "issue_tags": _require_string_list(
                            result.get("issue_tags", []),
                            context=f"{path}:{line_number}.result.issue_tags",
                        ),
                        "strength_tags": _require_string_list(
                            result.get("strength_tags", []),
                            context=f"{path}:{line_number}.result.strength_tags",
                        ),
                    }
                )
    if not judge_events:
        raise RuntimeError(f"No judge_result events found in {input_dir}")
    return attempt_files, judge_events


def aggregate_feedback(input_dir: Path) -> Dict[str, Any]:
    attempt_files, judge_events = _iter_judge_events(input_dir)
    issue_counts: Counter[str] = Counter()
    strength_counts: Counter[str] = Counter()
    scenario_scores: Dict[str, Dict[str, List[float]]] = defaultdict(
        lambda: {field: [] for field in SCORE_FIELDS}
    )
    misses_by_issue_tag: Dict[str, Dict[str, Any]] = {}
    examples: List[Dict[str, Any]] = []
    overall_scores: Dict[str, List[float]] = {field: [] for field in SCORE_FIELDS}
    scenario_meta: Dict[str, str] = {}

    for event in judge_events:
        scenario_id = event["scenario_id"]
        scenario_meta.setdefault(scenario_id, event["scenario_name"])
        for field in SCORE_FIELDS:
            value = event["scores"][field]
            overall_scores[field].append(value)
            scenario_scores[scenario_id][field].append(value)
        issue_tags = event["issue_tags"] or [UNTAGGED_ISSUE]
        issue_counts.update(issue_tags)
        strength_counts.update(event["strength_tags"])
        examples.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": event["scenario_name"],
                "attempt": event["attempt"],
                "turn": event["turn"],
                "headline": event["headline"],
                "athlete_likely_experience": event["athlete_likely_experience"],
                "improved_reply_example": event["improved_reply_example"] or None,
                "issue_tags": list(issue_tags),
                "strength_tags": list(event["strength_tags"]),
                "what_missed": list(event["what_missed"]),
            }
        )
        for issue_tag in issue_tags:
            bucket = misses_by_issue_tag.setdefault(issue_tag, {"count": 0, "items": []})
            for missed in event["what_missed"]:
                bucket["count"] += 1
                bucket["items"].append(
                    {
                        "missed": missed,
                        "scenario_id": scenario_id,
                        "scenario_name": event["scenario_name"],
                        "attempt": event["attempt"],
                        "turn": event["turn"],
                        "headline": event["headline"],
                        "improved_reply_example": event["improved_reply_example"] or None,
                    }
                )

    per_scenario = []
    for scenario_id in sorted(scenario_scores):
        per_scenario.append(
            {
                "scenario_id": scenario_id,
                "scenario_name": scenario_meta.get(scenario_id, scenario_id),
                "judge_result_count": len(scenario_scores[scenario_id][SCORE_FIELDS[0]]),
                "average_scores": {
                    field: _average(scenario_scores[scenario_id][field]) for field in SCORE_FIELDS
                },
            }
        )

    for issue_tag in sorted(misses_by_issue_tag):
        bucket = misses_by_issue_tag[issue_tag]
        bucket["items"] = sorted(
            bucket["items"],
            key=lambda item: (
                item["scenario_id"],
                item["attempt"],
                item["turn"],
                item["missed"],
            ),
        )

    return {
        "generated_at": _utc_now_iso(),
        "run_id": input_dir.name,
        "input_dir": str(input_dir),
        "attempt_files": [str(path) for path in attempt_files],
        "judge_result_count": len(judge_events),
        "average_scores": {field: _average(overall_scores[field]) for field in SCORE_FIELDS},
        "score_by_scenario": per_scenario,
        "issue_tag_counts": _sorted_counter(issue_counts),
        "strength_tag_counts": _sorted_counter(strength_counts),
        "misses_by_issue_tag": {key: misses_by_issue_tag[key] for key in sorted(misses_by_issue_tag)},
        "examples": sorted(
            examples,
            key=lambda item: (item["scenario_id"], item["attempt"], item["turn"]),
        ),
    }


def write_aggregate(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    input_dir = Path(args.input_dir).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_dir / DEFAULT_OUTPUT_NAME
    )
    aggregate = aggregate_feedback(input_dir)
    write_aggregate(output_path, aggregate)
    print(
        f"aggregated judge_results={aggregate['judge_result_count']} "
        f"issues={', '.join(aggregate['issue_tag_counts'].keys()) or 'none'} "
        f"output={output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
