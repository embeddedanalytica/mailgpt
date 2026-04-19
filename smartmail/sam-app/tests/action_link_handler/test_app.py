import sys
import types
import unittest
from unittest import mock


if "botocore.exceptions" not in sys.modules:
    botocore_module = types.ModuleType("botocore")
    botocore_exceptions_module = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        def __init__(self, error_response, operation_name):
            super().__init__(operation_name)
            self.response = error_response

    botocore_exceptions_module.ClientError = ClientError
    botocore_module.exceptions = botocore_exceptions_module
    sys.modules["botocore"] = botocore_module
    sys.modules["botocore.exceptions"] = botocore_exceptions_module


if "boto3" not in sys.modules:
    boto3_module = types.ModuleType("boto3")

    class _Boto3StubTable:
        def get_item(self, *args, **kwargs):
            return {}

        def update_item(self, *args, **kwargs):
            return {}

        def put_item(self, *args, **kwargs):
            return {}

    class _Boto3StubResource:
        def Table(self, _name):  # noqa: N802
            return _Boto3StubTable()

    class _Boto3StubClient:
        def encrypt(self, **kwargs):
            return {"CiphertextBlob": b"cipher"}

    def _resource(*args, **kwargs):
        return _Boto3StubResource()

    def _client(*args, **kwargs):
        return _Boto3StubClient()

    boto3_module.resource = _resource
    boto3_module.client = _client
    sys.modules["boto3"] = boto3_module


import app


class TestStravaOAuth(unittest.TestCase):
    def test_detects_strava_callback_path(self):
        event = {"path": "/oauth/strava/callback"}
        self.assertTrue(app.is_strava_callback_request(event))

    def test_connect_strava_missing_config_returns_500(self):
        token_data = {"email": "athlete@example.com"}
        with mock.patch.object(app, "_strava_redirect_uri", return_value=""), mock.patch.object(
            app, "_strava_client_id", return_value=""
        ):
            response = app.handle_connect_strava_action("tok_1", token_data)

        self.assertEqual(response["statusCode"], 500)

    def test_connect_strava_redirects_to_authorize(self):
        token_data = {"email": "athlete@example.com"}
        with (
            mock.patch.object(app, "_strava_redirect_uri", return_value="https://geniml.com/oauth/strava/callback"),
            mock.patch.object(app, "_strava_client_id", return_value="12345"),
            mock.patch.object(app, "_strava_scopes", return_value="read,activity:read_all"),
            mock.patch.object(app, "create_action_token_record", return_value="state_abc"),
        ):
            response = app.handle_connect_strava_action("tok_1", token_data)

        self.assertEqual(response["statusCode"], 302)
        self.assertIn("www.strava.com/oauth/authorize", response["headers"]["Location"])
        self.assertIn("state=state_abc", response["headers"]["Location"])

    def test_strava_callback_missing_params_returns_400(self):
        event = {"queryStringParameters": {}}
        response = app.handle_strava_callback(event)
        self.assertEqual(response["statusCode"], 400)

    def test_strava_callback_success(self):
        event = {
            "queryStringParameters": {
                "state": "state_abc",
                "code": "code_123",
                "scope": "read,activity:read_all",
            }
        }
        token_data = {
            "action_type": "STRAVA_OAUTH_STATE",
            "email": "athlete@example.com",
            "expires_at": int(10**10),
            "payload": {"email": "athlete@example.com"},
        }
        token_response = {
            "access_token": "access_1",
            "refresh_token": "refresh_1",
            "expires_at": int(10**10),
            "athlete": {"id": 999},
        }

        with (
            mock.patch.object(app, "get_token_from_db", return_value=token_data),
            mock.patch.object(app, "consume_token_atomically", return_value=True),
            mock.patch.object(app, "exchange_strava_code_for_tokens", return_value=token_response),
            mock.patch.object(app, "ensure_athlete_id", return_value="ath_1"),
            mock.patch.object(app, "upsert_athlete_connection"),
            mock.patch.object(app, "upsert_provider_tokens"),
        ):
            response = app.handle_strava_callback(event)

        self.assertEqual(response["statusCode"], 200)


class TestVerificationWelcomeEmail(unittest.TestCase):
    def test_send_post_verification_welcome_email_sends_ses_message(self):
        ses_client = mock.Mock()
        with mock.patch.object(app.boto3, "client", return_value=ses_client):
            sent = app.send_post_verification_welcome_email("user@example.com")

        self.assertTrue(sent)
        ses_client.send_email.assert_called_once()

    def test_route_action_verify_session_sends_welcome(self):
        with (
            mock.patch.object(app, "create_or_update_verified_session", return_value=True),
            mock.patch.object(app, "send_post_verification_welcome_email", return_value=True) as mock_send_welcome,
        ):
            response = app.route_action(
                token_id="tok_1",
                action_type="VERIFY_SESSION",
                token_data={"email": "user@example.com"},
                now=123456,
            )

        self.assertEqual(response["statusCode"], 200)
        mock_send_welcome.assert_called_once_with("user@example.com")

    def test_route_action_verify_session_welcome_failure_still_succeeds(self):
        with (
            mock.patch.object(app, "create_or_update_verified_session", return_value=True),
            mock.patch.object(app, "send_post_verification_welcome_email", return_value=False),
        ):
            response = app.route_action(
                token_id="tok_1",
                action_type="VERIFY_SESSION",
                token_data={"email": "user@example.com"},
                now=123456,
            )

        self.assertEqual(response["statusCode"], 200)


if __name__ == "__main__":
    unittest.main()
