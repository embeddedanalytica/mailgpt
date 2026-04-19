"""
Live end-to-end checks for SmartMail public routes.

These tests hit deployed infrastructure and require:
- AWS CLI configured with access to DynamoDB in the target account
- network access to the public domain
"""

import json
import secrets
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from typing import Dict, Optional, Tuple


BASE_URL = "https://geniml.com"
AWS_REGION = "us-west-2"
ACTION_TOKENS_TABLE = "action_tokens"
VERIFIED_SESSIONS_TABLE = "verified_sessions"

THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from test_live_coaching_workflow import TestLiveCoachingWorkflow  # noqa: E402,F401


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


def _run_aws_cli(args: list[str]) -> str:
    cmd = ["aws", *args, "--region", AWS_REGION]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)
    return proc.stdout


def _put_action_token(token_id: str, email: str, action_type: str = "VERIFY_SESSION") -> None:
    now = int(time.time())
    expires_at = now + 900
    item = {
        "token_id": {"S": token_id},
        "email": {"S": email.lower()},
        "action_type": {"S": action_type},
        "created_at": {"N": str(now)},
        "expires_at": {"N": str(expires_at)},
        "source": {"S": "e2e_test"},
    }
    _run_aws_cli(
        [
            "dynamodb",
            "put-item",
            "--table-name",
            ACTION_TOKENS_TABLE,
            "--item",
            json.dumps(item),
        ]
    )


def _delete_action_token(token_id: str) -> None:
    key = {"token_id": {"S": token_id}}
    _run_aws_cli(
        [
            "dynamodb",
            "delete-item",
            "--table-name",
            ACTION_TOKENS_TABLE,
            "--key",
            json.dumps(key),
        ]
    )


def _delete_verified_session(email: str) -> None:
    key = {"email": {"S": email.lower()}}
    _run_aws_cli(
        [
            "dynamodb",
            "delete-item",
            "--table-name",
            VERIFIED_SESSIONS_TABLE,
            "--key",
            json.dumps(key),
        ]
    )


class TestLiveEndpoints(unittest.TestCase):
    def test_register_route_is_api_not_static_fallback(self) -> None:
        status, body, headers = _http_request("GET", f"{BASE_URL}/register")
        # GET is intentionally blocked by the lambda, but route must reach API.
        self.assertEqual(status, 405)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertIn("Method Not Allowed", body)

    def test_register_post_missing_email_returns_validation_error(self) -> None:
        status, body, headers = _http_request("POST", f"{BASE_URL}/register", json_body={})
        self.assertEqual(status, 400)
        self.assertIn("application/json", headers.get("content-type", ""))
        self.assertIn("Email is required", body)

    def test_action_route_handles_missing_token_without_502(self) -> None:
        status, body, _headers = _http_request("GET", f"{BASE_URL}/action/not-a-real-token")
        self.assertEqual(status, 404)
        self.assertIn("Link invalid or expired", body)

    def test_action_verify_session_token_is_single_use(self) -> None:
        token_id = secrets.token_urlsafe(32).rstrip("=")
        email = f"e2e-{int(time.time())}@example.com"
        _put_action_token(token_id=token_id, email=email, action_type="VERIFY_SESSION")

        try:
            first_status, first_body, _ = _http_request("GET", f"{BASE_URL}/action/{token_id}")
            second_status, second_body, _ = _http_request("GET", f"{BASE_URL}/action/{token_id}")
        finally:
            _delete_action_token(token_id)
            _delete_verified_session(email)

        self.assertEqual(first_status, 200)
        self.assertIn("Verified", first_body)
        self.assertEqual(second_status, 409)
        self.assertIn("already used", second_body)


if __name__ == "__main__":
    unittest.main()
