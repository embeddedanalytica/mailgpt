"""Reusable helper for driving the live local coaching workflow."""

from __future__ import annotations

import email
import json
import re
import secrets
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime
from email.message import EmailMessage
from html import unescape
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Tuple
from unittest import mock

import boto3
from boto3.dynamodb.conditions import Attr, Key


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

ROOT = Path(__file__).resolve().parents[3]
EMAIL_SERVICE_DIR = ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_DIR) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_DIR))

import app as email_service_app  # type: ignore
import business as email_business  # type: ignore
import dynamodb_models  # type: ignore
import email_reply_sender  # type: ignore


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

        with open(body_file.name, "r", encoding="utf-8", errors="ignore") as handle:
            body = handle.read()

        headers: Dict[str, str] = {}
        with open(header_file.name, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                if ":" not in line:
                    continue
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        return status, body, headers


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


def _build_sns_event(
    *,
    sender: str,
    subject: str,
    body: str,
    message_id: str,
    date_received: str,
) -> Dict[str, Any]:
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
        raise RuntimeError(f"Timed out waiting for VERIFY_SESSION token for {email_address}")

    def cleanup_for_email(self, email_address: str, athlete_id: Optional[str] = None) -> None:
        email_address = email_address.lower()
        if not athlete_id:
            athlete_identity = self.get_item(ATHLETE_IDENTITIES_TABLE, {"email": email_address})
            athlete_id = athlete_identity.get("athlete_id") if athlete_identity else None

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


@dataclass
class LiveCoachingTurnResult:
    athlete_id: str
    message_id: str
    date_received: str
    lambda_response: Dict[str, Any]
    lambda_body: str
    outbound: Dict[str, Any]
    suppressed: bool = False


class LiveCoachingHarness:
    """Drive the local coaching lambda against a verified athlete identity."""

    def __init__(self) -> None:
        self.ddb = _DynamoState()

    def prepare_verified_athlete(self, email_address: str) -> None:
        normalized = email_address.lower()
        self.ddb.cleanup_for_email(normalized)
        register_status, register_body, _headers = _http_request(
            "POST",
            f"{BASE_URL}/register",
            json_body={"email": normalized},
        )
        if register_status != 200 or "Successfully registered" not in register_body:
            raise RuntimeError(f"registration failed for {normalized}: status={register_status} body={register_body}")
        token_item = self.ddb.wait_for_token(normalized)
        token_id = str(token_item["token_id"])
        verify_status, verify_body, _ = _http_request("GET", f"{BASE_URL}/action/{token_id}")
        if verify_status != 200 or "Verified" not in verify_body:
            raise RuntimeError(f"verification failed for {normalized}: status={verify_status} body={verify_body}")

    def send_inbound_email(
        self,
        email_address: str,
        *,
        subject: str,
        body: str,
        message_id: Optional[str] = None,
        date_received: Optional[str] = None,
    ) -> LiveCoachingTurnResult:
        normalized = email_address.lower()
        self.ddb.delete_item(RATE_LIMITS_TABLE, {"email": normalized})
        capture = _RawEmailCapture()
        resolved_message_id = message_id or f"<live-athlete-sim-{secrets.token_hex(8)}@example.com>"
        if date_received is None:
            now_struct = time.gmtime(time.time())
            resolved_date_received = time.strftime("%a, %d %b %Y %H:%M:%S +0000", now_struct)
        else:
            resolved_date_received = date_received
        effective_today = datetime.strptime(
            resolved_date_received,
            "%a, %d %b %Y %H:%M:%S +0000",
        ).date()

        event = _build_sns_event(
            sender=normalized,
            subject=subject,
            body=body,
            message_id=resolved_message_id,
            date_received=resolved_date_received,
        )
        with mock.patch.object(email_reply_sender.ses_client, "send_raw_email", side_effect=capture.send_raw_email):
            with mock.patch.object(
                email_service_app,
                "get_reply_for_inbound",
                side_effect=lambda athlete_id, from_email, email_data, **kwargs: email_business.get_reply_for_inbound(
                    athlete_id,
                    from_email,
                    email_data,
                    effective_today=effective_today,
                    **kwargs,
                ),
            ):
                response = email_service_app.lambda_handler(
                    event,
                    SimpleNamespace(aws_request_id=f"req-live-athlete-sim-{secrets.token_hex(6)}"),
                )

        status_code = int(response.get("statusCode", 0) or 0)
        response_body = str(response.get("body", ""))
        if status_code != 200:
            raise RuntimeError(f"coaching lambda returned non-200: {response}")

        athlete_id = dynamodb_models.get_athlete_id_for_email(normalized)
        if not athlete_id:
            raise RuntimeError(f"athlete_id missing after inbound email for {normalized}")

        # Coach suppressed the reply (strategist or response-gen failure) — valid outcome
        if not capture.messages:
            return LiveCoachingTurnResult(
                athlete_id=str(athlete_id),
                message_id=resolved_message_id,
                date_received=resolved_date_received,
                lambda_response=response,
                lambda_body=response_body,
                outbound={},
                suppressed=True,
            )

        return LiveCoachingTurnResult(
            athlete_id=str(athlete_id),
            message_id=resolved_message_id,
            date_received=resolved_date_received,
            lambda_response=response,
            lambda_body=response_body,
            outbound=capture.messages[-1],
        )

    def fetch_state_snapshot(self, athlete_id: str) -> Dict[str, Any]:
        profile = dynamodb_models.get_coach_profile(athlete_id) or {}
        current_plan = dynamodb_models.get_current_plan(athlete_id)
        plan_summary = dynamodb_models.fetch_current_plan_summary(athlete_id)
        progress = dynamodb_models.get_progress_snapshot(athlete_id)
        memory_context = dynamodb_models.get_memory_context_for_response_generation(athlete_id)
        plan_history = dynamodb_models.get_plan_history(athlete_id)["items"]
        conversation_records = self.ddb.query_all(CONVERSATION_INTELLIGENCE_TABLE, Key("athlete_id").eq(athlete_id))
        latest_intelligence = None
        if conversation_records:
            latest_intelligence = sorted(conversation_records, key=lambda item: int(item.get("created_at", 0)))[-1]
        return {
            "athlete_id": athlete_id,
            "profile": profile,
            "current_plan": current_plan,
            "plan_summary": plan_summary,
            "progress": progress,
            "memory_context": memory_context,
            "plan_history_count": len(plan_history),
            "conversation_intelligence_count": len(conversation_records),
            "latest_conversation_intelligence": latest_intelligence,
        }

    def cleanup(self, email_address: str, athlete_id: Optional[str] = None) -> None:
        self.ddb.cleanup_for_email(email_address.lower(), athlete_id=athlete_id)
