#!/usr/bin/env python3
"""Run the SmartMail intent benchmark through isolated Codex sessions."""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BENCH_PATH = REPO_ROOT / "intent_classification_test_bench.md"
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "intent-bench"
SKILL_PATH = REPO_ROOT / ".cursor" / "skills" / "intent-debugger" / "SKILL.md"
WRAPPER_PATH = REPO_ROOT / ".cursor" / "skills" / "intent-debugger" / "scripts" / "run_intent_debug.py"
SCHEMA_PATH = REPO_ROOT / "tools" / "intent_bench_agent_output.schema.json"
SESSION_TIMEOUT_SECONDS = 600


@dataclass(frozen=True)
class BenchCase:
    test_id: str
    expected_intent: str
    message: str
    why: str


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the intent classification benchmark via isolated Codex sessions."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Path to the markdown benchmark fixture.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Number of isolated attempts per test case.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=4,
        help="Maximum number of child Codex sessions to run concurrently.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional override for the benchmark artifact directory.",
    )
    return parser


def require_prerequisites(bench_path: Path, codex_bin: str | None) -> str:
    missing = []
    if not bench_path.exists():
        missing.append(f"benchmark fixture not found: {bench_path}")
    if not SKILL_PATH.exists():
        missing.append(f"skill file not found: {SKILL_PATH}")
    if not WRAPPER_PATH.exists():
        missing.append(f"intent debugger wrapper not found: {WRAPPER_PATH}")
    if not SCHEMA_PATH.exists():
        missing.append(f"output schema not found: {SCHEMA_PATH}")
    if not codex_bin:
        missing.append("`codex` executable not found in PATH")
    if missing:
        raise RuntimeError("\n".join(missing))

    if not os.getenv("OPENAI_API_KEY", "").strip():
        raise RuntimeError(
            "OPENAI_API_KEY is required before launching benchmark child sessions."
        )
    return codex_bin


def load_bench_cases(bench_path: Path) -> list[BenchCase]:
    text = bench_path.read_text(encoding="utf-8")
    match = re.search(r"```json\s*(.*?)```", text, flags=re.DOTALL)
    if not match:
        raise ValueError(f"No JSON block found in benchmark fixture: {bench_path}")

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON block in benchmark fixture: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Benchmark JSON block must be a non-empty array.")

    cases: list[BenchCase] = []
    seen_ids: set[str] = set()
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Benchmark case {index} is not an object.")

        test_id = str(item.get("id", "")).strip()
        expected_intent = str(item.get("expected_intent", "")).strip()
        message = str(item.get("message", "")).strip()
        why = str(item.get("why", "")).strip()

        if not all([test_id, expected_intent, message, why]):
            raise ValueError(f"Benchmark case {index} is missing required fields.")
        if test_id in seen_ids:
            raise ValueError(f"Duplicate benchmark test id: {test_id}")
        seen_ids.add(test_id)
        cases.append(
            BenchCase(
                test_id=test_id,
                expected_intent=expected_intent,
                message=message,
                why=why,
            )
        )
    return cases


def make_output_dir(output_dir: str | None) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser().resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = DEFAULT_OUTPUT_ROOT / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def build_child_prompt(case: BenchCase, attempt: int) -> str:
    case_blob = json.dumps(
        {
            "test_id": case.test_id,
            "attempt": attempt,
            "expected_intent": case.expected_intent,
            "why": case.why,
            "message": case.message,
        },
        indent=2,
        ensure_ascii=True,
    )
    return f"""You are running one isolated benchmark case for SmartMail intent classification.

Read and follow this local skill before doing anything else:
- {SKILL_PATH}

Requirements:
- Use the real local intent debugger wrapper at {WRAPPER_PATH}
- Classify exactly one message
- Do not use --repeat
- Do not edit any files
- Do not run unit tests, integration tests, or e2e tests
- Return only a JSON object that matches the provided output schema

Workflow:
1. Read the skill file.
2. Run the wrapper exactly once for the benchmark message.
3. Use the wrapper JSON output as the source of truth.
4. Return a JSON object with these fields:
   - test_id
   - attempt
   - expected_intent
   - detected_intent
   - match
   - complexity_score
   - resolution_source
   - intent_resolution_reason
   - signals (array of notable signal names, or []/null when absent)
   - behavior_summary
   - error (optional, only if something failed)

If the message contains newlines, pipe it over stdin. Otherwise `--message` is fine.
Do not include markdown fences.

Benchmark case:
{case_blob}
"""


def run_single_attempt(
    *,
    case: BenchCase,
    attempt: int,
    output_dir: Path,
    codex_bin: str,
) -> dict[str, Any]:
    session_dir = output_dir / "sessions" / case.test_id / f"attempt_{attempt}"
    session_dir.mkdir(parents=True, exist_ok=True)

    prompt_text = build_child_prompt(case, attempt)
    prompt_path = session_dir / "prompt.txt"
    prompt_path.write_text(prompt_text, encoding="utf-8")

    final_message_path = session_dir / "final_message.json"
    command = [
        codex_bin,
        "exec",
        "--ephemeral",
        "--color",
        "never",
        "-C",
        str(REPO_ROOT),
        "-s",
        "read-only",
        "--output-schema",
        str(SCHEMA_PATH),
        "-o",
        str(final_message_path),
        prompt_text,
    ]
    (session_dir / "command.txt").write_text(
        shlex.join(command), encoding="utf-8"
    )

    base_result: dict[str, Any] = {
        "test_id": case.test_id,
        "attempt": attempt,
        "expected_intent": case.expected_intent,
        "message": case.message,
        "why": case.why,
        "status": "failed",
        "match": False,
        "session_dir": str(session_dir),
    }

    try:
        completed = subprocess.run(
            command,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=SESSION_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout or ""
        stderr = exc.stderr or ""
        (session_dir / "stdout.log").write_text(stdout, encoding="utf-8")
        (session_dir / "stderr.log").write_text(stderr, encoding="utf-8")
        base_result.update(
            {
                "status": "timeout",
                "error": f"Timed out after {SESSION_TIMEOUT_SECONDS} seconds.",
                "exit_code": None,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session timed out.",
            }
        )
        return base_result

    (session_dir / "stdout.log").write_text(completed.stdout, encoding="utf-8")
    (session_dir / "stderr.log").write_text(completed.stderr, encoding="utf-8")

    if completed.returncode != 0:
        base_result.update(
            {
                "status": "codex_error",
                "error": (
                    f"codex exec exited with status {completed.returncode}. "
                    "See stdout.log and stderr.log."
                ),
                "exit_code": completed.returncode,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session failed before returning valid output.",
            }
        )
        return base_result

    if not final_message_path.exists():
        base_result.update(
            {
                "status": "missing_output",
                "error": "codex exec completed without writing a final message file.",
                "exit_code": completed.returncode,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session produced no structured result.",
            }
        )
        return base_result

    raw_final_message = final_message_path.read_text(encoding="utf-8").strip()
    if not raw_final_message:
        base_result.update(
            {
                "status": "empty_output",
                "error": "codex exec wrote an empty final message file.",
                "exit_code": completed.returncode,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session returned empty structured output.",
            }
        )
        return base_result

    try:
        payload = json.loads(raw_final_message)
    except json.JSONDecodeError as exc:
        base_result.update(
            {
                "status": "invalid_json",
                "error": f"Child final message is not valid JSON: {exc}",
                "exit_code": completed.returncode,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session returned malformed JSON.",
            }
        )
        return base_result

    try:
        normalized = normalize_child_payload(case=case, attempt=attempt, payload=payload)
    except ValueError as exc:
        base_result.update(
            {
                "status": "invalid_payload",
                "error": str(exc),
                "exit_code": completed.returncode,
                "detected_intent": None,
                "complexity_score": None,
                "resolution_source": None,
                "intent_resolution_reason": None,
                "signals": None,
                "behavior_summary": "Child Codex session returned a schema-incompatible payload.",
            }
        )
        return base_result

    normalized.update(
        {
            "status": "ok",
            "exit_code": completed.returncode,
            "session_dir": str(session_dir),
        }
    )
    return normalized


def normalize_child_payload(
    *,
    case: BenchCase,
    attempt: int,
    payload: Any,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("Child payload must be a JSON object.")

    required_fields = [
        "test_id",
        "attempt",
        "expected_intent",
        "detected_intent",
        "match",
        "complexity_score",
        "resolution_source",
        "intent_resolution_reason",
        "signals",
        "behavior_summary",
    ]
    missing = [field for field in required_fields if field not in payload]
    if missing:
        raise ValueError(f"Child payload is missing required fields: {', '.join(missing)}")

    if str(payload["test_id"]).strip() != case.test_id:
        raise ValueError("Child payload returned the wrong test_id.")
    if not isinstance(payload["attempt"], int) or payload["attempt"] != attempt:
        raise ValueError("Child payload returned the wrong attempt number.")
    if str(payload["expected_intent"]).strip() != case.expected_intent:
        raise ValueError("Child payload returned the wrong expected_intent.")
    if not isinstance(payload["match"], bool):
        raise ValueError("Child payload returned a non-boolean match field.")

    detected_intent = payload["detected_intent"]
    if detected_intent is not None:
        detected_intent = str(detected_intent).strip()
        if not detected_intent:
            detected_intent = None

    complexity_score = payload["complexity_score"]
    if complexity_score is not None:
        if not isinstance(complexity_score, int):
            raise ValueError("Child payload returned a non-integer complexity_score.")
        if complexity_score < 1 or complexity_score > 5:
            raise ValueError("Child payload returned complexity_score outside 1..5.")

    resolution_source = payload["resolution_source"]
    if resolution_source is not None:
        resolution_source = str(resolution_source).strip() or None

    intent_resolution_reason = payload["intent_resolution_reason"]
    if intent_resolution_reason is not None:
        intent_resolution_reason = str(intent_resolution_reason).strip() or None

    signals = payload["signals"]
    if signals is not None:
        if not isinstance(signals, list):
            raise ValueError("Child payload returned non-array signals.")
        if any(not isinstance(item, str) for item in signals):
            raise ValueError("Child payload returned non-string signal entries.")

    behavior_summary = str(payload["behavior_summary"]).strip()
    if not behavior_summary:
        raise ValueError("Child payload returned an empty behavior_summary.")

    return {
        "test_id": case.test_id,
        "attempt": attempt,
        "expected_intent": case.expected_intent,
        "detected_intent": detected_intent,
        "match": detected_intent == case.expected_intent,
        "complexity_score": complexity_score,
        "resolution_source": resolution_source,
        "intent_resolution_reason": intent_resolution_reason,
        "signals": signals,
        "behavior_summary": behavior_summary,
        "error": payload.get("error"),
        "message": case.message,
        "why": case.why,
    }


def aggregate_results(
    *,
    cases: list[BenchCase],
    results: list[dict[str, Any]],
    attempts: int,
    max_parallel: int,
    bench_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    by_test: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in results:
        by_test[result["test_id"]].append(result)

    per_test: list[dict[str, Any]] = []
    confusion_counter: Counter[tuple[str, str]] = Counter()
    failure_results = [result for result in results if result["status"] != "ok"]
    matched_runs = sum(1 for result in results if result.get("match"))

    for case in cases:
        test_results = sorted(by_test.get(case.test_id, []), key=lambda item: item["attempt"])
        successful = [item for item in test_results if item["status"] == "ok"]
        detected_counter = Counter(
            item["detected_intent"] for item in successful if item["detected_intent"]
        )
        for item in successful:
            if item["detected_intent"]:
                confusion_counter[(case.expected_intent, item["detected_intent"])] += 1

        majority_intent: str | None = None
        majority_count = 0
        if detected_counter:
            majority_intent, majority_count = detected_counter.most_common(1)[0]

        stable = len(detected_counter) <= 1 and not any(
            item["status"] != "ok" for item in test_results
        )
        per_test.append(
            {
                "test_id": case.test_id,
                "expected_intent": case.expected_intent,
                "attempts": attempts,
                "successful_runs": len(successful),
                "pass_count": sum(1 for item in test_results if item.get("match")),
                "failed_runs": sum(1 for item in test_results if item["status"] != "ok"),
                "majority_intent": majority_intent,
                "majority_count": majority_count,
                "stable": stable,
                "attempt_results": test_results,
            }
        )

    confusion = [
        {"expected_intent": expected, "detected_intent": detected, "count": count}
        for (expected, detected), count in sorted(confusion_counter.items())
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "attempts": attempts,
        "max_parallel": max_parallel,
        "total_cases": len(cases),
        "total_runs": len(results),
        "matched_runs": matched_runs,
        "match_rate": round((matched_runs / len(results)) if results else 0.0, 4),
        "successful_runs": len(results) - len(failure_results),
        "failed_runs": len(failure_results),
        "per_test": per_test,
        "confusion": confusion,
        "runs": sorted(results, key=lambda item: (item["test_id"], item["attempt"])),
    }


def write_summary(summary: dict[str, Any], summary_path: Path) -> None:
    unstable_tests = [
        item
        for item in summary["per_test"]
        if not item["stable"] and item["successful_runs"] > 0
    ]
    failed_runs = [item for item in summary["runs"] if item["status"] != "ok"]

    lines = [
        "# Intent Benchmark Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Benchmark fixture: `{summary['benchmark_path']}`",
        f"- Output directory: `{summary['output_dir']}`",
        f"- Total cases: `{summary['total_cases']}`",
        f"- Total runs: `{summary['total_runs']}`",
        f"- Exact matches: `{summary['matched_runs']}`",
        f"- Exact match rate: `{summary['match_rate']:.2%}`",
        f"- Successful runs: `{summary['successful_runs']}`",
        f"- Failed runs: `{summary['failed_runs']}`",
        "",
        "## Per-Test Results",
        "",
        "| Test | Expected | Passes | Majority | Stable | Failed Runs |",
        "| --- | --- | ---: | --- | --- | ---: |",
    ]
    for item in summary["per_test"]:
        majority = item["majority_intent"] or "n/a"
        stable = "yes" if item["stable"] else "no"
        lines.append(
            f"| {item['test_id']} | {item['expected_intent']} | "
            f"{item['pass_count']}/{item['attempts']} | {majority} | {stable} | "
            f"{item['failed_runs']} |"
        )

    lines.extend(["", "## Unstable Tests", ""])
    if unstable_tests:
        for item in unstable_tests:
            detected = [
                run["detected_intent"] or run["status"]
                for run in item["attempt_results"]
            ]
            lines.append(f"- `{item['test_id']}`: {', '.join(detected)}")
    else:
        lines.append("- None")

    lines.extend(["", "## Session Failures", ""])
    if failed_runs:
        for item in failed_runs:
            lines.append(
                f"- `{item['test_id']}` attempt `{item['attempt']}`: "
                f"{item['status']} - {item.get('error', 'unknown error')}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Confusion Summary", ""])
    if summary["confusion"]:
        lines.append("| Expected | Detected | Count |")
        lines.append("| --- | --- | ---: |")
        for item in summary["confusion"]:
            lines.append(
                f"| {item['expected_intent']} | {item['detected_intent']} | {item['count']} |"
            )
    else:
        lines.append("- None")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark(
    *,
    cases: list[BenchCase],
    attempts: int,
    max_parallel: int,
    output_dir: Path,
    codex_bin: str,
    bench_path: Path,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = [
            executor.submit(
                run_single_attempt,
                case=case,
                attempt=attempt,
                output_dir=output_dir,
                codex_bin=codex_bin,
            )
            for case in cases
            for attempt in range(1, attempts + 1)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    summary = aggregate_results(
        cases=cases,
        results=results,
        attempts=attempts,
        max_parallel=max_parallel,
        bench_path=bench_path,
        output_dir=output_dir,
    )
    runs_path = output_dir / "runs.json"
    summary_path = output_dir / "summary.md"
    runs_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_summary(summary, summary_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.attempts < 1:
        print("--attempts must be >= 1.", file=sys.stderr)
        return 2
    if args.max_parallel < 1:
        print("--max-parallel must be >= 1.", file=sys.stderr)
        return 2

    bench_path = Path(args.bench).expanduser().resolve()
    codex_bin = shutil.which("codex")

    try:
        codex_bin = require_prerequisites(bench_path, codex_bin)
        cases = load_bench_cases(bench_path)
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    output_dir = make_output_dir(args.output_dir)
    summary = run_benchmark(
        cases=cases,
        attempts=args.attempts,
        max_parallel=args.max_parallel,
        output_dir=output_dir,
        codex_bin=codex_bin,
        bench_path=bench_path,
    )

    print(f"Benchmark completed. Artifacts written to {output_dir}")
    print(f"Exact match rate: {summary['match_rate']:.2%}")
    print(f"Failed runs: {summary['failed_runs']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
