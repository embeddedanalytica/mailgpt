import importlib.util
import json
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEBUG_TURN_PATH = _REPO_ROOT / "tools" / "debug_turn.py"
_SPEC = importlib.util.spec_from_file_location("debug_turn_module", _DEBUG_TURN_PATH)
assert _SPEC and _SPEC.loader
debug_turn = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(debug_turn)


class _FakeHarness:
    def __init__(self, *, delay_seconds: float = 0.0, should_fail: bool = False) -> None:
        self.delay_seconds = delay_seconds
        self.should_fail = should_fail
        self.calls = []

    def send_inbound_email(
        self,
        email_addr: str,
        *,
        subject: str,
        body: str,
        date_received: str | None = None,
    ):
        self.calls.append(
            {
                "email_addr": email_addr,
                "subject": subject,
                "body": body,
                "date_received": date_received,
            }
        )
        time.sleep(self.delay_seconds)
        if self.should_fail:
            raise RuntimeError("synthetic failure")
        return SimpleNamespace(
            athlete_id="ath_test_123",
            message_id="msg_test_123",
            lambda_body="ok",
            suppressed=False,
            outbound={"subject": "Re: Check-in", "text": "Coach reply"},
        )


class DebugTurnTraceTests(unittest.TestCase):
    def test_slow_send_writes_started_heartbeats_and_final_record(self) -> None:
        harness = _FakeHarness(delay_seconds=0.05)
        snapshot_calls = []

        def fake_snapshot(_harness, email_l: str) -> dict:
            snapshot_calls.append(email_l)
            return {"snapshot_call": len(snapshot_calls), "email": email_l}

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "debug_trace.jsonl"
            with (
                mock.patch.object(debug_turn, "_SEND_HEARTBEAT_SECONDS", 0.01),
                mock.patch.object(debug_turn, "_safe_snapshot", side_effect=fake_snapshot),
                mock.patch.object(debug_turn, "_reset_prompt_trace"),
                mock.patch.object(
                    debug_turn,
                    "_drain_prompt_trace",
                    return_value=[{"skill": "coaching_directive", "model": "test-model"}],
                ),
            ):
                turn = debug_turn._do_send_turn(
                    harness,
                    email_addr="athlete@example.com",
                    subject="Check-in",
                    body="Slow test body",
                    date_received=None,
                    trace_path=trace_path,
                    turn_num=3,
                )

            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]

        self.assertEqual(rows[0]["kind"], "debug_send_started")
        self.assertGreaterEqual(len([r for r in rows if r["kind"] == "debug_send_heartbeat"]), 1)
        self.assertEqual(rows[-1]["kind"], "debug_send")
        self.assertEqual(rows[-1]["turn_num"], 3)
        self.assertEqual(rows[-1]["start_trace_line"], 1)
        self.assertEqual(rows[-1]["heartbeat_count"], len(rows) - 2)
        self.assertGreater(rows[-1]["elapsed_seconds"], 0)
        self.assertEqual(rows[-1]["skills"][0]["skill"], "coaching_directive")
        self.assertEqual(turn["trace_line"], len(rows))
        self.assertEqual(turn["coach_text"], "Coach reply")

    def test_multiple_runs_append_cleanly(self) -> None:
        harness = _FakeHarness(delay_seconds=0.0)
        snapshot_counter = {"count": 0}

        def fake_snapshot(_harness, email_l: str) -> dict:
            snapshot_counter["count"] += 1
            return {"snapshot_call": snapshot_counter["count"], "email": email_l}

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "debug_trace.jsonl"
            with (
                mock.patch.object(debug_turn, "_SEND_HEARTBEAT_SECONDS", 0.01),
                mock.patch.object(debug_turn, "_safe_snapshot", side_effect=fake_snapshot),
                mock.patch.object(debug_turn, "_reset_prompt_trace"),
                mock.patch.object(debug_turn, "_drain_prompt_trace", return_value=[]),
            ):
                for idx, body in enumerate(
                    [
                        "Run one body",
                        "Run two body",
                        "Run three body",
                    ],
                    start=1,
                ):
                    with self.subTest(turn=idx):
                        turn = debug_turn._do_send_turn(
                            harness,
                            email_addr="athlete@example.com",
                            subject="Check-in",
                            body=body,
                            date_received=None,
                            trace_path=trace_path,
                            turn_num=idx,
                        )
                        self.assertTrue(turn["ok"])

            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]

        self.assertEqual(len(rows), 6)
        self.assertEqual(
            [row["kind"] for row in rows],
            [
                "debug_send_started",
                "debug_send",
                "debug_send_started",
                "debug_send",
                "debug_send_started",
                "debug_send",
            ],
        )
        self.assertEqual([rows[1]["turn_num"], rows[3]["turn_num"], rows[5]["turn_num"]], [1, 2, 3])
        self.assertEqual([rows[1]["start_trace_line"], rows[3]["start_trace_line"], rows[5]["start_trace_line"]], [1, 3, 5])

    def test_failed_send_writes_error_record(self) -> None:
        harness = _FakeHarness(delay_seconds=0.0, should_fail=True)

        with tempfile.TemporaryDirectory() as td:
            trace_path = Path(td) / "debug_trace.jsonl"
            with (
                mock.patch.object(debug_turn, "_SEND_HEARTBEAT_SECONDS", 0.01),
                mock.patch.object(debug_turn, "_safe_snapshot", return_value={}),
                mock.patch.object(debug_turn, "_reset_prompt_trace"),
                mock.patch.object(debug_turn, "_drain_prompt_trace", return_value=[]),
            ):
                turn = debug_turn._do_send_turn(
                    harness,
                    email_addr="athlete@example.com",
                    subject="Check-in",
                    body="Failure body",
                    date_received=None,
                    trace_path=trace_path,
                    turn_num=1,
                )

            rows = [json.loads(line) for line in trace_path.read_text().splitlines()]

        self.assertFalse(turn["ok"])
        self.assertEqual(rows[0]["kind"], "debug_send_started")
        self.assertEqual(rows[-1]["kind"], "debug_send_error")
        self.assertEqual(rows[-1]["error"], "synthetic failure")


if __name__ == "__main__":
    unittest.main()
