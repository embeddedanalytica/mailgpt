"""Live end-to-end coaching workflow checks for SmartMail.

This test intentionally exercises the real local email-service orchestration,
real deployed registration/action-link routes, real DynamoDB persistence, and
live LLM-backed coaching components. Only the final outbound coaching SES send
is intercepted so the rendered reply can be asserted without emailing anyone.
"""

from __future__ import annotations

import email
import json
import os
import re
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Set, Tuple
from unittest import mock

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.exceptions import BotoCoreError, ClientError

BASE_URL = "https://geniml.com"
AWS_REGION = "us-west-2"
ACTION_TOKENS_TABLE = "action_tokens"
VERIFIED_SESSIONS_TABLE = "verified_sessions"
USERS_TABLE = "users"
RATE_LIMITS_TABLE = "rate_limits"
ATHLETE_IDENTITIES_TABLE = "athlete_identities"
COACH_PROFILES_TABLE = "coach_profiles"
PROGRESS_SNAPSHOTS_TABLE = "progress_snapshots"
RULE_STATE_TABLE = "rule_state"
CONVERSATION_INTELLIGENCE_TABLE = "conversation_intelligence"
MANUAL_ACTIVITY_SNAPSHOTS_TABLE = "manual_activity_snapshots"
PLAN_HISTORY_TABLE = "plan_history"
PLAN_UPDATE_REQUESTS_TABLE = "plan_update_requests"

ROOT = Path(__file__).resolve().parents[2]
EMAIL_SERVICE_DIR = ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_DIR))

import app as email_service_app  # type: ignore
import business as email_business  # type: ignore
import coaching as email_coaching  # type: ignore
import email_reply_sender  # type: ignore
import dynamodb_models  # type: ignore
from skills.response_generation import run_response_generation_workflow as live_run_response_generation_workflow  # type: ignore


REQUIRED_INTENTS = {
    "coaching",
    "question",
}
SYNTHETIC_START_DATETIME = datetime(2026, 1, 1, 15, 0, 0, tzinfo=timezone.utc)
SYNTHETIC_DAYS_PER_TURN = 5


def _format_rfc2822_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _http_request(
    method: str,
    url: str,
    *,
    json_body: Optional[Dict[str, object]] = None,
) -> Tuple[int, str, Dict[str, str]]:
    with tempfile.NamedTemporaryFile() as header_file, tempfile.NamedTemporaryFile() as body_file:
        cmd = [
            "curl",
            "-sS",
            "-X",
            method,
            url,
            "-D",
            header_file.name,
            "-o",
            body_file.name,
            "--max-time",
            "30",
            "-w",
            "%{http_code}",
        ]
        if json_body is not None:
            cmd.extend(["-H", "Content-Type: application/json", "--data", json.dumps(json_body)])

        proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
        status = int(proc.stdout.strip() or "0")

        with open(body_file.name, "r", encoding="utf-8", errors="ignore") as f:
            body = f.read()

        headers: Dict[str, str] = {}
        with open(header_file.name, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                if ":" not in line:
                    continue
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()

        return status, body, headers


@dataclass(frozen=True)
class TurnSpec:
    number: int
    subject: str
    body: str
    style: str
    expect_reply_mode_behavior: str
    expected_intent: Optional[str] = None
    acceptable_intents: Optional[Set[str]] = None
    expected_requested_action: Optional[str] = None
    acceptable_requested_actions: Optional[Set[str]] = None
    expect_manual_snapshot: bool = False
    expect_plan_growth: bool = False
    expect_memory: bool = False
    expect_progress_non_default: bool = False
    expect_clarification_semantics: bool = False
    allow_clarification_instead_of_inference: bool = False
    expect_durable_schedule_reuse: bool = False
    inference_candidate: bool = False


class _RawEmailCapture:
    def __init__(self) -> None:
        self.messages: List[Dict[str, Any]] = []

    def send_raw_email(self, *, Source: str, Destinations: List[str], RawMessage: Dict[str, str]) -> Dict[str, str]:
        raw_data = str(RawMessage["Data"])
        parsed = email.message_from_string(raw_data)
        html_body = ""
        text_body = ""
        if parsed.is_multipart():
            for part in parsed.walk():
                content_type = part.get_content_type()
                payload = part.get_payload(decode=True) or b""
                decoded = payload.decode(part.get_content_charset() or "utf-8", errors="ignore")
                if content_type == "text/html" and not html_body:
                    html_body = decoded
                if content_type == "text/plain" and not text_body:
                    text_body = decoded
        else:
            payload = parsed.get_payload(decode=True) or b""
            decoded = payload.decode(parsed.get_content_charset() or "utf-8", errors="ignore")
            if parsed.get_content_type() == "text/html":
                html_body = decoded
            else:
                text_body = decoded

        if html_body and not text_body:
            text_body = _html_to_text(html_body)

        self.messages.append(
            {
                "source": Source,
                "destinations": list(Destinations),
                "raw": raw_data,
                "subject": str(parsed.get("Subject", "")),
                "html": html_body,
                "text": text_body,
                "in_reply_to": str(parsed.get("In-Reply-To", "")),
                "references": str(parsed.get("References", "")),
            }
        )
        return {"MessageId": f"captured-{len(self.messages)}"}


def _html_to_text(html: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", html, flags=re.IGNORECASE)
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"\r", "", text)
    text = re.sub(r"\n\s+", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _build_sns_event(*, sender: str, subject: str, body: str, message_id: str, date_received: str) -> Dict[str, Any]:
    raw_email = _build_raw_email(
        sender=sender,
        recipient="coach@geniml.com",
        subject=subject,
        body=body,
        message_id=message_id,
        date_received=date_received,
    )
    sns_message = {
        "mail": {
            "source": sender,
            "destination": ["coach@geniml.com"],
            "messageId": message_id,
            "commonHeaders": {
                "subject": subject,
                "date": date_received,
                "to": ["coach@geniml.com"],
                "cc": [],
            },
        },
        "content": raw_email,
    }
    return {"Records": [{"Sns": {"Message": json.dumps(sns_message)}}]}


def _build_raw_email(
    *,
    sender: str,
    recipient: str,
    subject: str,
    body: str,
    message_id: str,
    date_received: str,
) -> str:
    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message["Date"] = date_received
    message["Message-ID"] = message_id
    message.set_content(body)
    return message.as_string()


class _DynamoState:
    def __init__(self) -> None:
        self.resource = boto3.resource("dynamodb", region_name=AWS_REGION)

    def table(self, name: str):
        return self.resource.Table(name)

    def get_item(self, table_name: str, key: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        response = self.table(table_name).get_item(Key=key)
        return response.get("Item")

    def delete_item(self, table_name: str, key: Dict[str, Any]) -> None:
        self.table(table_name).delete_item(Key=key)

    def query_all(self, table_name: str, key_condition, *, scan_forward: bool = True) -> List[Dict[str, Any]]:
        table = self.table(table_name)
        items: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {
            "KeyConditionExpression": key_condition,
            "ScanIndexForward": scan_forward,
        }
        while True:
            response = table.query(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
        return items

    def scan_all(self, table_name: str, *, filter_expression=None) -> List[Dict[str, Any]]:
        table = self.table(table_name)
        items: List[Dict[str, Any]] = []
        kwargs: Dict[str, Any] = {}
        if filter_expression is not None:
            kwargs["FilterExpression"] = filter_expression
        while True:
            response = table.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
        return items

    def wait_for_token(self, email_address: str, *, timeout_seconds: int = 30) -> Dict[str, Any]:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            tokens = self.scan_all(
                ACTION_TOKENS_TABLE,
                filter_expression=Attr("email").eq(email_address.lower()) & Attr("action_type").eq("VERIFY_SESSION"),
            )
            if tokens:
                tokens.sort(key=lambda item: int(item.get("created_at", 0)), reverse=True)
                return tokens[0]
            time.sleep(1)
        raise AssertionError(f"Timed out waiting for VERIFY_SESSION token for {email_address}")

    def cleanup_for_email(self, email_address: str, athlete_id: Optional[str] = None) -> None:
        email_address = email_address.lower()
        for token in self.scan_all(ACTION_TOKENS_TABLE, filter_expression=Attr("email").eq(email_address)):
            self.delete_item(ACTION_TOKENS_TABLE, {"token_id": token["token_id"]})

        for table_name, key in (
            (USERS_TABLE, {"email_address": email_address}),
            (VERIFIED_SESSIONS_TABLE, {"email": email_address}),
            (RATE_LIMITS_TABLE, {"email": email_address}),
            (ATHLETE_IDENTITIES_TABLE, {"email": email_address}),
        ):
            self.delete_item(table_name, key)

        if not athlete_id:
            athlete_identity = self.get_item(ATHLETE_IDENTITIES_TABLE, {"email": email_address})
            athlete_id = athlete_identity.get("athlete_id") if athlete_identity else None
        if not athlete_id:
            return

        for table_name in (COACH_PROFILES_TABLE, PROGRESS_SNAPSHOTS_TABLE, RULE_STATE_TABLE):
            self.delete_item(table_name, {"athlete_id": athlete_id})

        for item in self.query_all(CONVERSATION_INTELLIGENCE_TABLE, Key("athlete_id").eq(athlete_id)):
            self.delete_item(CONVERSATION_INTELLIGENCE_TABLE, {"athlete_id": athlete_id, "message_id": item["message_id"]})
        for item in self.query_all(MANUAL_ACTIVITY_SNAPSHOTS_TABLE, Key("athlete_id").eq(athlete_id)):
            self.delete_item(MANUAL_ACTIVITY_SNAPSHOTS_TABLE, {"athlete_id": athlete_id, "snapshot_key": item["snapshot_key"]})
        for item in self.query_all(PLAN_HISTORY_TABLE, Key("athlete_id").eq(athlete_id)):
            self.delete_item(PLAN_HISTORY_TABLE, {"athlete_id": athlete_id, "plan_version": item["plan_version"]})
        for item in self.query_all(PLAN_UPDATE_REQUESTS_TABLE, Key("athlete_id").eq(athlete_id)):
            self.delete_item(PLAN_UPDATE_REQUESTS_TABLE, {"athlete_id": athlete_id, "logical_request_id": item["logical_request_id"]})


TURNS: List[TurnSpec] = [
    TurnSpec(1, "Starting over after a layoff", "Hi coach, I want to get back to running after a messy few months. My big goal is to get healthy enough to race a half marathon again this spring. Right now I mostly need help rebuilding without doing something stupid.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"plan_update", "clarify_only"}, expect_clarification_semantics=True),
    TurnSpec(2, "A little more context", "A bit more context: I used to run consistently before the layoff and I'd call myself intermediate. I can train four days a week most weeks if we keep it realistic. The thing that nags me is mild Achilles tightness when I get greedy. I also do better when the plan feels structured.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"clarify_only", "plan_update"}, expect_memory=True),
    TurnSpec(3, "Profile details and target race", "Here is the missing context more directly. Primary goal: run a half marathon on 2026-05-17 and finish feeling strong. Time availability: 4 sessions per week and about 4 to 5 hours total. Experience level: intermediate. Constraints: mild Achilles tightness, busy work mornings on Tuesdays, and I prefer structured guidance.", "semi_structured", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"clarify_only", "plan_update"}),
    TurnSpec(4, "Availability update for this week", "Availability update for this week. Event date: 2026-05-17. Days available: 4. Pain score: 2 out of 10. Risk candidate feels green. I can run Monday, Wednesday, Friday, and Sunday. Week is not chaotic. Schedule variability is medium because work may move one session by a few hours.", "structured", "should_mutate", expected_intent="coaching", expected_requested_action="plan_update", expect_plan_growth=True),
    TurnSpec(5, "First check-in after an easy run", "Training check-in. Event date: 2026-05-17. Days available: 4. Pain score: 2 out of 10. Risk candidate is green. I did a run for 45m and 6 km yesterday. Felt good, energy ok, little sore, slept well. Missed sessions count: 0. I want to keep building carefully.", "structured", "should_mutate", expected_intent="coaching", acceptable_requested_actions={"checkin_ack", "plan_update"}, expect_manual_snapshot=True, expect_plan_growth=True, expect_progress_non_default=True),
    TurnSpec(6, "Long run felt fine", "Long run update: I got through 75 minutes this morning and honestly I feel ok after the long run. The Achilles is there in the background but not angry, and I slept well last night. I'd like to keep the same four-day rhythm this week if that still makes sense.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"checkin_ack", "plan_update"}, expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True, allow_clarification_instead_of_inference=True, inference_candidate=True, expect_durable_schedule_reuse=True),
    TurnSpec(7, "How easy should easy feel?", "Quick question: on these comeback runs, how easy should easy actually feel? I'm trying not to chase pace, but I also don't want to jog so slowly that the mechanics get weird.", "freeform", "should_read_only", expected_intent="question", expected_requested_action="answer_question"),
    TurnSpec(8, "Work got messy", "Can we adjust the week? Work is crazy and I probably only have Wednesday, Friday, and Sunday for training. I missed one session already and my stress is definitely up.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, expected_requested_action="plan_update", expect_memory=True, expect_clarification_semantics=True),
    TurnSpec(9, "Here are the details you probably need", "More detail for the adjustment: event date is 2026-05-17, days available this week are 3, pain score is still 2 out of 10, risk candidate feels yellow because work stress is high, week is chaotic true, stress score 8, sleep score 5.", "structured", "should_mutate", expected_intent="coaching", acceptable_requested_actions={"plan_update", "clarify_only"}, expect_plan_growth=True),
    TurnSpec(10, "Tune-up effort felt controlled", "Small milestone: I did a tune-up 5k effort in 24:50 and it felt controlled. I added a 20m cool-down jog after. No big pain spike, just normal post-workout heaviness, and sleep was good.", "semi_structured", "clarification_or_inference_ok", expected_intent="question", acceptable_requested_actions={"checkin_ack", "answer_question"}, expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True, allow_clarification_instead_of_inference=True, inference_candidate=True),
    TurnSpec(11, "Still on the same four-day pattern", "Just to confirm, I'm still doing four days per week most weeks. The same general Monday Wednesday Friday Sunday pattern still works, although Friday has become the easiest day for me to protect.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"clarify_only", "checkin_ack", "plan_update"}, expect_memory=True, expect_durable_schedule_reuse=True),
    TurnSpec(12, "Travel week coming up", "Travel week heads-up: next week is rough. I only have Tuesday, Thursday, and Saturday open, and hotel treadmill plus a tiny gym are all I'll have. I'd love the simplest travel-friendly version of the plan.", "freeform", "clarification_or_inference_ok", expected_intent="coaching", expected_requested_action="plan_update", expect_memory=True, expect_clarification_semantics=True),
    TurnSpec(13, "Travel details", "Event date: 2026-05-17. Days available: 3. Pain score: 2 out of 10. Risk candidate is yellow because I am traveling for work. Week is chaotic true. Equipment access is treadmill and gym, no track. I can do 40m treadmill runs and one short strength session.", "structured", "should_mutate", expected_intent="coaching", expected_requested_action="plan_update", expect_plan_growth=True),
    TurnSpec(14, "Hotel treadmill check-in", "Travel check-in: I did a run for 40m on the hotel treadmill, about 4.5 miles, avg hr 146, and roughly 520 calories. Felt decent, slept ok, and nothing got worse. Mostly just mentally flat from travel.", "semi_structured", "clarification_or_inference_ok", expected_intent="coaching", acceptable_requested_actions={"checkin_ack", "plan_update"}, expect_manual_snapshot=True, expect_progress_non_default=True, allow_clarification_instead_of_inference=True, inference_candidate=True),
    TurnSpec(15, "Back home and Saturday is open", "Good news: for the next month Saturday is open again, so I have more flexibility for the long run. Week to week I still want to stay at four days, but now the long run doesn't have to be Sunday every time.", "freeform", "clarification_or_inference_ok", expected_intent="coaching", acceptable_requested_actions={"plan_update", "clarify_only"}, expect_memory=True, expect_durable_schedule_reuse=True),
    TurnSpec(16, "Family chaos week", "This week got blown up by family stuff. I only got in one 30m run and I'm feeling low energy today. Can we just simplify everything for a few days and keep the important things important?", "freeform", "clarification_or_inference_ok", expected_intent="coaching", expected_requested_action="plan_update", expect_memory=True, expect_clarification_semantics=True),
    TurnSpec(17, "Details for the family-chaos week", "Event date: 2026-05-17. Days available: 2. Pain score: 3 out of 10. Risk candidate is yellow. Family stuff blew up this week. I only got in a 30m run. Felt low energy, sore, poor sleep. Stress score is 9. I am worried about losing momentum.", "structured", "should_mutate", expected_intent="coaching", expected_requested_action="plan_update", expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True),
    TurnSpec(18, "Back on track", "Better week. I ran three times: 35m easy, 50m steady, and 80m today for about 9 miles. Felt good, slept well, and the Achilles feels quiet again. Same four-day rhythm still seems like the sweet spot.", "semi_structured", "clarification_or_inference_ok", expected_intent="coaching", acceptable_requested_actions={"checkin_ack", "plan_update"}, expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True, allow_clarification_instead_of_inference=True, inference_candidate=True, expect_durable_schedule_reuse=True),
    TurnSpec(19, "Should I add strides?", "Question for you: since things are stable again, should I add strides after one easy run, or keep everything fully aerobic for now?", "freeform", "should_read_only", expected_intent="question", expected_requested_action="answer_question"),
    TurnSpec(20, "Harder session left me cooked", "Yesterday I did a harder session: total run 55m with 6 x 3 minutes moderate-hard. Today I'm pretty cooked, sleep was poor, and soreness is definitely up. I don't think anything is injured, but it feels like I pushed the edge.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"checkin_ack", "plan_update"}, expect_manual_snapshot=True, expect_memory=True, expect_clarification_semantics=True),
    TurnSpec(21, "Numbers from the hard session", "Event date: 2026-05-17. Days available: 4. Pain score: 5 out of 10. Risk candidate feels yellow. Intervals yesterday: run 55m total with 6 x 3 minutes moderate-hard. Felt exhausted after, soreness high, sleep poor. Pain affects form false. Pain worsening false. No swelling.", "structured", "should_mutate", expected_intent="coaching", acceptable_requested_actions={"plan_update", "checkin_ack"}, expect_manual_snapshot=True, expect_plan_growth=True, expect_progress_non_default=True),
    TurnSpec(22, "Only three days next week", "Next week I only have three training days because of work travel again. I'd like the week simplified and I want to protect the most important session, but keep the overall direction the same.", "freeform", "clarification_or_inference_ok", expected_intent="coaching", expected_requested_action="plan_update", expect_clarification_semantics=True),
    TurnSpec(23, "Three-day week details", "Event date: 2026-05-17. Days available: 3. Pain score: 3 out of 10. Risk candidate is yellow. Next week I only have three training days. Week is chaotic false, but volume has to come down. Please simplify the week and protect the key session.", "structured", "should_mutate", expected_intent="coaching", expected_requested_action="plan_update", expect_plan_growth=True),
    TurnSpec(24, "Race confidence check", "With the race getting closer, do you think the current plan still fits where I am? I'm curious what the biggest focus should be over the next two weeks, especially since I've settled into that four-day pattern pretty well.", "freeform", "should_read_only", expected_intent="question", expected_requested_action="answer_question", expect_memory=True, expect_durable_schedule_reuse=True),
    TurnSpec(25, "Mild cold and weather", "I have a mild cold and the weather is awful this week. Energy is not great. I don't want to do anything dumb, but I also don't want to lose the thread completely. How conservative should I be?", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question", "safety_concern"}, acceptable_requested_actions={"answer_question", "plan_update"}, expect_clarification_semantics=True),
    TurnSpec(26, "Illness details", "Event date: 2026-05-17. Pain score: 2 out of 10. Risk candidate is yellow. Recent illness is mild. Energy score is 4. Sleep score is 5. I want to know how conservative I should be this week.", "structured", "should_mutate", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"plan_update", "answer_question"}, expect_plan_growth=True, expect_memory=True),
    TurnSpec(27, "Half marathon done", "Race update: I ran the half marathon today in 1:55. I jogged 15m after, I feel tired but happy, and nothing feels scary. This whole build really confirmed that four days per week is a good groove for me.", "semi_structured", "clarification_or_inference_ok", expected_intent="question", expected_requested_action="checkin_ack", expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True, expect_durable_schedule_reuse=True),
    TurnSpec(28, "Next-goal question", "Now that the race is done, what should the next two weeks look like and how should I think about the next goal? I'm open to another half or maybe building toward something longer later in the year.", "freeform", "should_read_only", expected_intent="question", expected_requested_action="answer_question", expect_memory=True),
    TurnSpec(29, "One more durable schedule note", "One thing I learned from this block: four days is sustainable for me, and Saturday is probably the best long-run anchor going forward. Fridays still need to stay pretty light because of work.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"clarify_only", "checkin_ack", "plan_update"}, expect_memory=True, expect_durable_schedule_reuse=True),
    TurnSpec(30, "Freeform final check-in", "Quick final check-in before I go quiet for a few days: easy 35m jog today, about 4 miles, avg hr 138, felt good, slept well, and I'm mostly just happily tired. Curious if your advice changes much given everything you've seen from me over this stretch.", "freeform", "clarification_or_inference_ok", acceptable_intents={"coaching", "question"}, acceptable_requested_actions={"checkin_ack", "answer_question"}, expect_manual_snapshot=True, expect_memory=True, expect_progress_non_default=True, allow_clarification_instead_of_inference=True, inference_candidate=True, expect_durable_schedule_reuse=True),
]


@unittest.skipUnless(
    os.getenv("RUN_LIVE_COACHING_E2E", "false").strip().lower() == "true",
    "RUN_LIVE_COACHING_E2E is not true",
)
class TestLiveCoachingWorkflow(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        missing = []
        if not os.getenv("OPENAI_API_KEY"):
            missing.append("OPENAI_API_KEY")
        if os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() != "true":
            missing.append("ENABLE_LIVE_LLM_CALLS=true")
        if os.getenv("ENABLE_SESSION_CHECKIN_EXTRACTION", "false").strip().lower() != "true":
            missing.append("ENABLE_SESSION_CHECKIN_EXTRACTION=true")
        if missing:
            raise unittest.SkipTest(", ".join(missing) + " required for live coaching e2e")
        try:
            boto3.client("sts", region_name=AWS_REGION).get_caller_identity()
        except (ClientError, BotoCoreError) as exc:
            raise unittest.SkipTest(f"AWS credentials unavailable: {exc}") from exc

    def setUp(self) -> None:
        self.ddb = _DynamoState()
        self.email_address = f"coach-e2e-{int(time.time())}-{secrets.token_hex(4)}@example.com"
        self.capture = _RawEmailCapture()
        self.athlete_id: Optional[str] = None
        self.turn_results: List[Dict[str, Any]] = []
        artifact_dir = Path(
            os.getenv(
                "LIVE_E2E_ARTIFACT_DIR",
                str(Path(__file__).resolve().parent / "artifacts"),
            )
        )
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_run_id = f"{int(time.time())}-{secrets.token_hex(4)}"
        self.turn_artifact_path = artifact_dir / f"live_coaching_turns_{artifact_run_id}.jsonl"
        self._append_turn_artifact(
            {
                "phase": "run_start",
                "run_id": artifact_run_id,
                "email_address": self.email_address,
                "synthetic_start_date": SYNTHETIC_START_DATETIME.isoformat(),
                "synthetic_days_per_turn": SYNTHETIC_DAYS_PER_TURN,
            }
        )
        self.ddb.cleanup_for_email(self.email_address)

    def tearDown(self) -> None:
        self.ddb.cleanup_for_email(self.email_address, athlete_id=self.athlete_id)

    def _check_requested_action(self, turn: TurnSpec, observed_action: Optional[str]) -> Optional[str]:
        """Soft-check requested_action. Returns a warning string if unexpected, None if ok."""
        if observed_action is None:
            return f"turn {turn.number} requested_action missing from metadata"
        if turn.expected_requested_action is not None:
            if observed_action != turn.expected_requested_action:
                return (
                    f"turn {turn.number} requested_action mismatch: "
                    f"expected={turn.expected_requested_action!r} observed={observed_action!r}"
                )
            return None
        if turn.acceptable_requested_actions is not None:
            if observed_action not in turn.acceptable_requested_actions:
                return (
                    f"turn {turn.number} requested_action {observed_action!r} "
                    f"not in acceptable set {sorted(turn.acceptable_requested_actions)!r}"
                )
            return None
        return None  # no assertion specified

    def _assert_intent_acceptable(self, turn: TurnSpec, observed_intent: str) -> None:
        # Realistic freeform emails are intentionally ambiguous. For those turns,
        # the human-facing reply quality matters more than exact classifier labels.
        if turn.style != "structured":
            if turn.acceptable_intents is not None:
                self.assertIn(
                    observed_intent,
                    turn.acceptable_intents,
                    f"turn {turn.number} intent {observed_intent!r} not in acceptable set {sorted(turn.acceptable_intents)!r}",
                )
            elif turn.expected_intent is not None:
                self.assertIn(
                    observed_intent,
                    REQUIRED_INTENTS,
                    f"turn {turn.number} produced unexpected non-coaching intent {observed_intent!r}",
                )
            return
        if turn.expected_intent is not None:
            self.assertEqual(observed_intent, turn.expected_intent, f"turn {turn.number} intent mismatch")
            return
        if turn.acceptable_intents is not None:
            self.assertIn(observed_intent, turn.acceptable_intents, f"turn {turn.number} intent {observed_intent!r} not in acceptable set {sorted(turn.acceptable_intents)!r}")

    def _log_turn(self, turn: TurnSpec, **fields: Any) -> None:
        parts = [
            f"turn={turn.number}",
            f"style={turn.style}",
            f"mode={turn.expect_reply_mode_behavior}",
            f"subject={turn.subject!r}",
        ]
        for key, value in fields.items():
            parts.append(f"{key}={value!r}")
        print("LIVE_E2E " + " ".join(parts), flush=True)

    def _wrap_live_call(self, turn: TurnSpec, label: str, fn):
        def _wrapped(*args: Any, **kwargs: Any):
            started_at = time.time()
            self._log_turn(turn, phase="call_start", call=label)
            try:
                result = fn(*args, **kwargs)
            except Exception as exc:
                self._log_turn(
                    turn,
                    phase="call_error",
                    call=label,
                    duration_seconds=round(time.time() - started_at, 2),
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                raise
            self._log_turn(
                turn,
                phase="call_end",
                call=label,
                duration_seconds=round(time.time() - started_at, 2),
            )
            return result
        return _wrapped

    def _append_turn_artifact(self, payload: Dict[str, Any]) -> None:
        with self.turn_artifact_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def test_live_thirty_turn_coaching_workflow(self) -> None:
        self._log_turn(
            TURNS[0],
            phase="artifact_path",
            artifact_path=str(self.turn_artifact_path),
        )
        register_status, register_body, register_headers = _http_request(
            "POST",
            f"{BASE_URL}/register",
            json_body={"email": self.email_address},
        )
        self.assertEqual(register_status, 200, register_body)
        self.assertIn("application/json", register_headers.get("content-type", ""))
        self.assertIn("Successfully registered", register_body)
        self.assertIsNotNone(self.ddb.get_item(USERS_TABLE, {"email_address": self.email_address.lower()}))

        token_item = self.ddb.wait_for_token(self.email_address)
        token_id = str(token_item["token_id"])
        verify_status, verify_body, _ = _http_request("GET", f"{BASE_URL}/action/{token_id}")
        self.assertEqual(verify_status, 200, verify_body)
        self.assertIn("Verified", verify_body)
        self.assertIsNotNone(self.ddb.get_item(VERIFIED_SESSIONS_TABLE, {"email": self.email_address.lower()}))

        observed_intents: List[str] = []
        plan_versions: List[int] = []
        manual_snapshot_count = 0
        durable_schedule_seen = False
        with mock.patch.object(email_reply_sender.ses_client, "send_raw_email", side_effect=self.capture.send_raw_email):
            for turn in TURNS:
                turn_started_at = time.time()
                self.ddb.delete_item(RATE_LIMITS_TABLE, {"email": self.email_address.lower()})
                before_capture_count = len(self.capture.messages)
                turn_offset_days = SYNTHETIC_DAYS_PER_TURN * (turn.number - 1)
                synthetic_datetime = SYNTHETIC_START_DATETIME + timedelta(days=turn_offset_days)
                date_received = _format_rfc2822_utc(synthetic_datetime)
                message_id = f"<live-e2e-{turn.number}-{secrets.token_hex(6)}@example.com>"
                self._log_turn(
                    turn,
                    phase="start",
                    message_id=message_id,
                    synthetic_date=synthetic_datetime.isoformat(),
                )
                effective_today = synthetic_datetime.date()
                event = _build_sns_event(
                    sender=self.email_address,
                    subject=turn.subject,
                    body=turn.body,
                    message_id=message_id,
                    date_received=date_received,
                )
                with mock.patch.object(
                    email_service_app.EmailProcessor,
                    "parse_sns_event",
                    side_effect=self._wrap_live_call(turn, "parse_sns_event", email_service_app.EmailProcessor.parse_sns_event),
                ), mock.patch.object(
                    email_service_app,
                    "get_reply_for_inbound",
                    side_effect=self._wrap_live_call(
                        turn,
                        "get_reply_for_inbound",
                        lambda athlete_id, from_email, email_data, **kwargs: email_business.get_reply_for_inbound(
                            athlete_id,
                            from_email,
                            email_data,
                            effective_today=effective_today,
                            **kwargs,
                        ),
                    ),
                ), mock.patch.object(
                    email_business,
                    "analyze_conversation_intelligence",
                    side_effect=self._wrap_live_call(turn, "analyze_conversation_intelligence", email_business.analyze_conversation_intelligence),
                ), mock.patch.object(
                    email_business,
                    "route_inbound_with_rule_engine",
                    side_effect=self._wrap_live_call(turn, "route_inbound_with_rule_engine", email_business.route_inbound_with_rule_engine),
                ), mock.patch.object(
                    email_business,
                    "build_profile_gated_reply",
                    side_effect=self._wrap_live_call(turn, "build_profile_gated_reply", email_business.build_profile_gated_reply),
                ), mock.patch.object(
                    email_coaching,
                    "run_response_generation_workflow",
                    side_effect=self._wrap_live_call(turn, "run_response_generation_workflow", live_run_response_generation_workflow),
                ), mock.patch.object(
                    email_reply_sender.EmailReplySender,
                    "send_reply",
                    side_effect=self._wrap_live_call(turn, "send_reply", email_reply_sender.EmailReplySender.send_reply),
                ):
                    try:
                        response = email_service_app.lambda_handler(
                            event,
                            SimpleNamespace(aws_request_id=f"req-live-e2e-{turn.number}"),
                        )
                    except Exception:
                        self._log_turn(turn, phase="lambda_exception", turn_results=self.turn_results)
                        raise
                self.assertEqual(response.get("statusCode"), 200, f"turn {turn.number} returned non-200 response: {response}")

                response_body = str(response.get("body", ""))

                self.athlete_id = dynamodb_models.get_athlete_id_for_email(self.email_address)
                self.assertTrue(self.athlete_id, f"athlete_id missing after turn {turn.number}")
                assert self.athlete_id is not None

                if turn.number == 1:
                    self.assertIsNotNone(self.ddb.get_item(ATHLETE_IDENTITIES_TABLE, {"email": self.email_address.lower()}))
                    self.assertIsNotNone(self.ddb.get_item(COACH_PROFILES_TABLE, {"athlete_id": self.athlete_id}))
                    self.assertIsNotNone(self.ddb.get_item(PROGRESS_SNAPSHOTS_TABLE, {"athlete_id": self.athlete_id}))

                conversation_records = self.ddb.query_all(CONVERSATION_INTELLIGENCE_TABLE, Key("athlete_id").eq(self.athlete_id))
                self.assertEqual(len(conversation_records), turn.number, f"turn {turn.number} should have {turn.number} conversation-intelligence rows, got {len(conversation_records)}")
                latest_intelligence = sorted(conversation_records, key=lambda item: int(item.get("created_at", 0)))[-1]
                observed_intent = str(latest_intelligence.get("intent", ""))
                observed_intents.append(observed_intent)
                self._assert_intent_acceptable(turn, observed_intent)

                # Extract requested_action and brevity_preference from metadata
                ci_metadata = latest_intelligence.get("metadata") or {}
                if isinstance(ci_metadata, str):
                    try:
                        ci_metadata = json.loads(ci_metadata)
                    except (json.JSONDecodeError, TypeError):
                        ci_metadata = {}
                observed_requested_action = ci_metadata.get("requested_action") if isinstance(ci_metadata, dict) else None
                observed_brevity = ci_metadata.get("brevity_preference") if isinstance(ci_metadata, dict) else None
                action_warning = self._check_requested_action(turn, observed_requested_action)
                if action_warning:
                    print(f"LIVE_E2E WARN {action_warning}", flush=True)
                else:
                    self._log_turn(turn, phase="requested_action_ok", requested_action=observed_requested_action)

                self.turn_results.append({
                    "turn": turn.number,
                    "subject": turn.subject,
                    "style": turn.style,
                    "expected_intent": turn.expected_intent,
                    "acceptable_intents": sorted(turn.acceptable_intents) if turn.acceptable_intents else None,
                    "expected_requested_action": turn.expected_requested_action,
                    "acceptable_requested_actions": sorted(turn.acceptable_requested_actions) if turn.acceptable_requested_actions else None,
                    "observed_requested_action": observed_requested_action,
                    "observed_brevity_preference": observed_brevity,
                    "requested_action_warning": action_warning,
                    "lambda_body": response_body,
                })

                if "No reply sent due to response-generation failure." in response_body:
                    self.fail(f"turn {turn.number} response generation suppressed send: subject={turn.subject!r} body={response_body!r} results={self.turn_results!r}")

                self.assertIn("Reply sent! Message ID:", response_body, f"turn {turn.number} did not send a reply: {response_body}")
                self.assertEqual(len(self.capture.messages), before_capture_count + 1, f"turn {turn.number} should capture exactly one outbound email")
                captured = self.capture.messages[-1]
                self.assertTrue(captured["html"].strip(), f"turn {turn.number} html body empty")
                self.assertTrue(captured["text"].strip(), f"turn {turn.number} text body empty")
                self.assertIn("Re:", captured["subject"], f"turn {turn.number} missing reply subject")
                self.assertIn(self.email_address.lower(), [d.lower() for d in captured["destinations"]])
                self._append_turn_artifact(
                    {
                        "phase": "turn_response",
                        "turn": turn.number,
                        "style": turn.style,
                        "expected_mode": turn.expect_reply_mode_behavior,
                        "conversation_intelligence": {
                            "intent": observed_intent,
                            "requested_action": observed_requested_action,
                            "brevity_preference": observed_brevity,
                            "requested_action_warning": action_warning,
                        },
                        "inbound": {
                            "sender": self.email_address,
                            "message_id": message_id,
                            "date_received": date_received,
                            "synthetic_date": synthetic_datetime.isoformat(),
                            "subject": turn.subject,
                            "body": turn.body,
                        },
                        "outbound": {
                            "lambda_body": response_body,
                            "subject": captured["subject"],
                            "destinations": captured["destinations"],
                            "text": captured["text"],
                            "html": captured["html"],
                            "raw": captured["raw"],
                        },
                    }
                )

                profile = dynamodb_models.get_coach_profile(self.athlete_id) or {}
                current_plan = dynamodb_models.get_current_plan(self.athlete_id)
                plan_summary = dynamodb_models.fetch_current_plan_summary(self.athlete_id)
                progress = dynamodb_models.get_progress_snapshot(self.athlete_id)
                memory_context = dynamodb_models.get_memory_context_for_response_generation(self.athlete_id)
                plan_history = dynamodb_models.get_plan_history(self.athlete_id)["items"]
                plan_versions.append(int(current_plan.get("plan_version", 0)) if current_plan else 0)
                turn_duration = round(time.time() - turn_started_at, 2)
                self.turn_results[-1].update({
                    "observed_intent": observed_intent,
                    "plan_version": int(current_plan.get("plan_version", 0)) if current_plan else 0,
                    "plan_history_count": len(plan_history),
                    "memory_notes_count": len(memory_context.get("context_notes", []) or []),
                    "has_continuity_summary": bool(memory_context.get("continuity_summary")),
                    "last_7d_activity_count": (progress or {}).get("last_7d_activity_count"),
                    "reply_preview": captured["text"][:240],
                    "duration_seconds": turn_duration,
                })
                self._log_turn(
                    turn,
                    phase="end",
                    duration_seconds=turn_duration,
                    observed_intent=observed_intent,
                    requested_action=observed_requested_action,
                    brevity_preference=observed_brevity,
                    action_warning=action_warning,
                    lambda_body=response_body,
                    plan_version=int(current_plan.get("plan_version", 0)) if current_plan else 0,
                    plan_history_count=len(plan_history),
                    memory_notes_count=len(memory_context.get("context_notes", []) or []),
                    has_continuity_summary=bool(memory_context.get("continuity_summary")),
                    last_7d_activity_count=(progress or {}).get("last_7d_activity_count"),
                )

                if turn.number >= 3:
                    self.assertTrue(profile.get("primary_goal"), f"turn {turn.number} missing primary_goal")
                    self.assertTrue(profile.get("time_availability"), f"turn {turn.number} missing time_availability")
                    self.assertIn(profile.get("experience_level"), {"beginner", "intermediate", "advanced", "unknown"})
                    self.assertIsInstance(profile.get("constraints"), list)
                    self.assertIsNotNone(current_plan, f"turn {turn.number} current_plan missing")
                    self.assertTrue(plan_summary, f"turn {turn.number} plan summary missing")

                if turn.expect_manual_snapshot:
                    snapshots = self.ddb.query_all(MANUAL_ACTIVITY_SNAPSHOTS_TABLE, Key("athlete_id").eq(self.athlete_id), scan_forward=True)
                    self.assertGreaterEqual(len(snapshots), manual_snapshot_count + 1, f"turn {turn.number} expected new manual snapshot")
                    manual_snapshot_count = len(snapshots)

                if turn.expect_progress_non_default:
                    self.assertIsNotNone(progress, f"turn {turn.number} progress snapshot missing")
                    assert progress is not None
                    self.assertGreaterEqual(progress.get("last_7d_activity_count", 0), 1)
                    self.assertIn(progress.get("data_quality"), {"medium", "high"})
                    self.assertIn(progress.get("last_reported_energy"), {"low", "ok", "high", "unknown"})
                    self.assertIn(progress.get("last_reported_sleep"), {"poor", "ok", "good", "unknown"})

                if turn.expect_plan_growth:
                    self.assertGreaterEqual(len(plan_history), 2, f"turn {turn.number} expected plan history beyond initial version")

                if turn.expect_memory:
                    has_memory = bool(
                        memory_context.get("context_notes")
                        or memory_context.get("continuity_summary")
                        or any(
                            isinstance(v, dict) and v.get("summary")
                            for v in memory_context.get("backbone", {}).values()
                        )
                    )
                    self.assertTrue(has_memory, f"turn {turn.number} expected memory artifacts to exist")

                if turn.expect_durable_schedule_reuse:
                    time_availability = profile.get("time_availability", {})
                    sessions_per_week = time_availability.get("sessions_per_week") if isinstance(time_availability, dict) else None
                    if sessions_per_week == 4:
                        durable_schedule_seen = True

                if turn.number in {1, 2, 3}:
                    self.assertTrue(captured["text"].strip(), f"turn {turn.number} onboarding reply should not be empty")

        self.assertGreaterEqual(len(self.turn_results), 30)
        observed_intent_set = {intent for intent in observed_intents if intent}
        for required_intent in REQUIRED_INTENTS:
            self.assertIn(required_intent, observed_intent_set, f"required intent {required_intent!r} not observed across run: {observed_intents!r}")

        # Requested-action summary (soft — warn, don't fail)
        action_warnings = [
            r for r in self.turn_results
            if r.get("requested_action_warning")
        ]
        action_present = sum(
            1 for r in self.turn_results
            if r.get("observed_requested_action")
        )
        print(
            f"\nLIVE_E2E requested_action coverage: "
            f"{action_present}/{len(self.turn_results)} turns had requested_action, "
            f"{len(action_warnings)} warnings",
            flush=True,
        )
        if action_warnings:
            print("LIVE_E2E requested_action warnings:", flush=True)
            for r in action_warnings:
                print(
                    f"  turn {r['turn']} ({r['subject']}): {r['requested_action_warning']}",
                    flush=True,
                )
        self._append_turn_artifact({
            "phase": "requested_action_summary",
            "turns_with_action": action_present,
            "total_turns": len(self.turn_results),
            "warnings": [
                {
                    "turn": r["turn"],
                    "subject": r["subject"],
                    "warning": r["requested_action_warning"],
                    "observed": r.get("observed_requested_action"),
                    "expected": r.get("expected_requested_action"),
                    "acceptable": r.get("acceptable_requested_actions"),
                }
                for r in action_warnings
            ],
        })

        assert self.athlete_id is not None
        final_profile = dynamodb_models.get_coach_profile(self.athlete_id)
        final_plan = dynamodb_models.get_current_plan(self.athlete_id)
        final_progress = dynamodb_models.get_progress_snapshot(self.athlete_id)
        final_memory_context = dynamodb_models.get_memory_context_for_response_generation(self.athlete_id)
        final_plan_history = dynamodb_models.get_plan_history(self.athlete_id)["items"]
        self.assertIsNotNone(final_profile, "final profile unreadable")
        self.assertIsNotNone(final_plan, "final current_plan unreadable")
        self.assertIsNotNone(final_progress, "final progress snapshot unreadable")
        self.assertGreaterEqual(len(final_plan_history), 2, "final plan history did not grow")
        self.assertTrue(
            final_memory_context.get("context_notes")
            or final_memory_context.get("continuity_summary")
            or any(
                isinstance(v, dict) and v.get("summary")
                for v in final_memory_context.get("backbone", {}).values()
            ),
            "final memory context remained empty",
        )
        self.assertGreater(max(plan_versions), 1, f"plan version never increased: {plan_versions!r}")
        self.assertTrue(durable_schedule_seen, "expected durable schedule context like four days per week to persist or be reused later")
