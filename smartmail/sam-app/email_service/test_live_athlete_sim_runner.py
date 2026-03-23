import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import sys

TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import live_athlete_sim_runner


def _scenario(**overrides):
    scenario = {
        "id": "LAS-TEST-001",
        "name": "sample scenario",
        "athlete_brief": "brief",
        "judge_brief": "judge",
        "opening_message": "I need help getting back on track.",
        "evaluation_focus": ["memory", "tone"],
        "min_turns": 2,
        "max_turns": 3,
    }
    scenario.update(overrides)
    return scenario


class _HarnessStub:
    instances = []

    def __init__(self):
        self.prepared = []
        self.sent = []
        self.cleaned = []
        self.fetch_calls = []
        self.athlete_id = "athlete-123"
        type(self).instances.append(self)

    def prepare_verified_athlete(self, email_address: str) -> None:
        self.prepared.append(email_address)

    def send_inbound_email(self, email_address: str, *, subject: str, body: str):
        self.sent.append((email_address, subject, body))
        turn = len(self.sent)
        return SimpleNamespace(
            athlete_id=self.athlete_id,
            message_id=f"msg-{turn}",
            date_received="Fri, 20 Mar 2026 10:00:00 +0000",
            lambda_response={"statusCode": 200, "body": "Reply sent! Message ID: captured-1"},
            lambda_body="Reply sent! Message ID: captured-1",
            outbound={
                "subject": f"Re: {subject}",
                "text": f"Coach reply {turn}",
                "html": f"<p>Coach reply {turn}</p>",
            },
        )

    def fetch_state_snapshot(self, athlete_id: str):
        self.fetch_calls.append(athlete_id)
        return {
            "athlete_id": athlete_id,
            "profile": {"primary_goal": "goal"},
            "plan_summary": "steady plan",
            "progress": {"last_7d_activity_count": len(self.sent)},
            "memory_context": {"context_notes": [{"label": "note"}]},
        }

    def cleanup(self, email_address: str, athlete_id=None) -> None:
        self.cleaned.append((email_address, athlete_id))


class _AthleteClientStub:
    def __init__(self, reactions):
        self.reactions = list(reactions)
        self.opening_calls = 0
        self.reaction_calls = 0

    def generate_opening_message(self, **_kwargs):
        self.opening_calls += 1
        return {
            "subject": "Opening",
            "body": "Opening body",
            "private_intent": "learn if coach listens",
        }

    def react_to_coach_reply(self, **_kwargs):
        self.reaction_calls += 1
        return dict(self.reactions.pop(0))


class _JudgeClientStub:
    def __init__(self, *, error_on_call: int | None = None):
        self.calls = 0
        self.error_on_call = error_on_call

    def evaluate_reply(self, **_kwargs):
        self.calls += 1
        if self.error_on_call == self.calls:
            raise RuntimeError("judge boom")
        return {
            "headline": "Solid reply",
            "scores": {
                "understanding": 4,
                "memory_continuity": 4,
                "personalization": 4,
                "coaching_quality": 4,
                "tone_trust": 4,
                "safety": 5,
            },
            "what_landed": ["useful guidance"],
            "what_missed": ["missed one detail"],
            "hallucinations_or_unwarranted_assumptions": ["None."],
            "athlete_likely_experience": "Mostly understood",
            "issue_tags": ["missed_fact"],
            "strength_tags": ["specific_guidance"],
        }


class TestLiveAthleteSimRunner(unittest.TestCase):
    def setUp(self) -> None:
        _HarnessStub.instances = []

    def test_scenario_filtering(self):
        scenarios = [_scenario(), _scenario(id="LAS-TEST-002", name="other")]
        selected = live_athlete_sim_runner.select_scenarios(scenarios, ["las-test-002"])
        self.assertEqual([item["id"] for item in selected], ["LAS-TEST-002"])

    def test_build_parser_defaults_to_long_horizon_turn_counts(self):
        args = live_athlete_sim_runner.build_parser().parse_args([])
        self.assertEqual(args.min_turns, 100)
        self.assertEqual(args.max_turns, 100)

    def test_run_single_attempt_enforces_min_turns_before_stop(self):
        athlete_client = _AthleteClientStub(
            reactions=[
                {
                    "reaction_summary": "not enough yet",
                    "felt_understood_score": 3,
                    "trust_delta": "flat",
                    "what_helped": ["usable"],
                    "what_bothered": ["generic"],
                    "continue_conversation": False,
                    "stop_reason": "done early",
                    "next_subject": "More detail",
                    "next_body": "I also only have four training days.",
                },
                {
                    "reaction_summary": "good enough",
                    "felt_understood_score": 4,
                    "trust_delta": "up",
                    "what_helped": ["specific"],
                    "what_bothered": ["none"],
                    "continue_conversation": False,
                    "stop_reason": "got what I needed",
                    "next_subject": "",
                    "next_body": "",
                },
            ]
        )
        judge_client = _JudgeClientStub()
        with tempfile.TemporaryDirectory() as td:
            result = live_athlete_sim_runner.run_single_attempt(
                scenario=_scenario(),
                attempt=1,
                athlete_model="gpt-5-mini",
                judge_model="gpt-5-mini",
                output_dir=Path(td),
                default_min_turns=2,
                default_max_turns=3,
                harness_factory=_HarnessStub,
                athlete_client=athlete_client,
                judge_client=judge_client,
            )

            transcript_files = list(Path(td).glob("*.jsonl"))
            summary_files = list(Path(td).glob("*.summary.json"))

        self.assertEqual(result["status"], live_athlete_sim_runner.OK)
        self.assertEqual(result["turn_count"], 2)
        self.assertEqual(result["stop_reason"], "got what I needed")
        self.assertEqual(len(transcript_files), 1)
        self.assertEqual(len(summary_files), 1)
        harness = _HarnessStub.instances[0]
        self.assertEqual(len(harness.sent), 2)
        self.assertEqual(len(harness.cleaned), 1)

    def test_run_single_attempt_stops_at_max_turns(self):
        athlete_client = _AthleteClientStub(
            reactions=[
                {
                    "reaction_summary": "keep going",
                    "felt_understood_score": 3,
                    "trust_delta": "flat",
                    "what_helped": ["okay"],
                    "what_bothered": ["still vague"],
                    "continue_conversation": True,
                    "stop_reason": "",
                    "next_subject": "Follow-up one",
                    "next_body": "Can you be more specific?",
                },
                {
                    "reaction_summary": "still going",
                    "felt_understood_score": 3,
                    "trust_delta": "flat",
                    "what_helped": ["okay"],
                    "what_bothered": ["still vague"],
                    "continue_conversation": True,
                    "stop_reason": "",
                    "next_subject": "Follow-up two",
                    "next_body": "How should I structure the week?",
                },
                {
                    "reaction_summary": "maxed out",
                    "felt_understood_score": 3,
                    "trust_delta": "flat",
                    "what_helped": ["okay"],
                    "what_bothered": ["still vague"],
                    "continue_conversation": True,
                    "stop_reason": "",
                    "next_subject": "Unused",
                    "next_body": "Unused",
                },
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            result = live_athlete_sim_runner.run_single_attempt(
                scenario=_scenario(min_turns=1, max_turns=3),
                attempt=1,
                athlete_model=None,
                judge_model=None,
                output_dir=Path(td),
                default_min_turns=1,
                default_max_turns=3,
                harness_factory=_HarnessStub,
                athlete_client=athlete_client,
                judge_client=_JudgeClientStub(),
            )
        self.assertEqual(result["status"], live_athlete_sim_runner.OK)
        self.assertEqual(result["turn_count"], 3)
        self.assertEqual(result["stop_reason"], "max_turns_reached")

    def test_run_single_attempt_cleans_up_on_error(self):
        athlete_client = _AthleteClientStub(
            reactions=[
                {
                    "reaction_summary": "unused",
                    "felt_understood_score": 3,
                    "trust_delta": "flat",
                    "what_helped": ["okay"],
                    "what_bothered": ["none"],
                    "continue_conversation": False,
                    "stop_reason": "done",
                    "next_subject": "",
                    "next_body": "",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            result = live_athlete_sim_runner.run_single_attempt(
                scenario=_scenario(min_turns=1, max_turns=2),
                attempt=1,
                athlete_model=None,
                judge_model=None,
                output_dir=Path(td),
                default_min_turns=1,
                default_max_turns=2,
                harness_factory=_HarnessStub,
                athlete_client=athlete_client,
                judge_client=_JudgeClientStub(error_on_call=1),
            )
            summary_path = Path(result["summary_path"])
            summary_payload = json.loads(summary_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], live_athlete_sim_runner.ERROR)
        self.assertIn("judge boom", result["error"])
        self.assertEqual(summary_payload["status"], live_athlete_sim_runner.ERROR)
        harness = _HarnessStub.instances[0]
        self.assertEqual(len(harness.cleaned), 1)

    def test_run_single_attempt_serializes_decimal_snapshots(self):
        class _DecimalHarnessStub(_HarnessStub):
            def fetch_state_snapshot(self, athlete_id: str):
                snapshot = super().fetch_state_snapshot(athlete_id)
                snapshot["progress"] = {
                    "last_7d_activity_count": Decimal("2"),
                    "last_7d_distance_km": Decimal("18.5"),
                }
                snapshot["profile"] = {
                    "time_availability": {"hours_per_week": Decimal("4.5")},
                }
                return snapshot

        athlete_client = _AthleteClientStub(
            reactions=[
                {
                    "reaction_summary": "good enough",
                    "felt_understood_score": 4,
                    "trust_delta": "up",
                    "what_helped": ["specific"],
                    "what_bothered": ["none"],
                    "continue_conversation": False,
                    "stop_reason": "got what I needed",
                    "next_subject": "",
                    "next_body": "",
                }
            ]
        )
        with tempfile.TemporaryDirectory() as td:
            result = live_athlete_sim_runner.run_single_attempt(
                scenario=_scenario(min_turns=1, max_turns=1),
                attempt=1,
                athlete_model=None,
                judge_model=None,
                output_dir=Path(td),
                default_min_turns=1,
                default_max_turns=1,
                harness_factory=_DecimalHarnessStub,
                athlete_client=athlete_client,
                judge_client=_JudgeClientStub(),
            )
            transcript_path = Path(result["transcript_path"])
            transcript_lines = [
                json.loads(line)
                for line in transcript_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]

        self.assertEqual(result["status"], live_athlete_sim_runner.OK)
        snapshot_record = next(item for item in transcript_lines if item["phase"] == "state_snapshot")
        self.assertEqual(snapshot_record["snapshot"]["progress"]["last_7d_activity_count"], 2)
        self.assertEqual(snapshot_record["snapshot"]["progress"]["last_7d_distance_km"], 18.5)
        self.assertEqual(
            snapshot_record["snapshot"]["profile"]["time_availability"]["hours_per_week"],
            4.5,
        )


if __name__ == "__main__":
    unittest.main()
