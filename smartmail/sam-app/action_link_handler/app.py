"""
Action Link Handler Lambda Function

Handles GET /action/{token} endpoint for action links (verification, etc.)
"""

import os
import logging
import time
import json
import uuid
import base64
import boto3 # type: ignore
from botocore.exceptions import ClientError # type: ignore
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))
kms_client = boto3.client("kms", region_name=os.getenv("AWS_REGION", "us-west-2"))


STRAVA_AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
STRAVA_TOKEN_URL = "https://www.strava.com/oauth/token"


def _token_table_name() -> str:
    return os.getenv("ACTION_TOKENS_TABLE_NAME", "")


def _coach_profiles_table_name() -> str:
    return os.getenv("COACH_PROFILES_TABLE_NAME", "")


def _athlete_connections_table_name() -> str:
    return os.getenv("ATHLETE_CONNECTIONS_TABLE_NAME", "")


def _provider_tokens_table_name() -> str:
    return os.getenv("PROVIDER_TOKENS_TABLE_NAME", "")


def _strava_client_id() -> str:
    return os.getenv("STRAVA_CLIENT_ID", "").strip()


def _strava_client_secret() -> str:
    return os.getenv("STRAVA_CLIENT_SECRET", "").strip()


def _strava_redirect_uri() -> str:
    return os.getenv("STRAVA_REDIRECT_URI", "").strip()


def _strava_scopes() -> str:
    return os.getenv("STRAVA_SCOPES", "read,activity:read_all").strip()


def _strava_state_ttl_seconds() -> int:
    try:
        minutes = int(os.getenv("STRAVA_STATE_TTL_MINUTES", "15"))
        if minutes <= 0:
            return 900
        return minutes * 60
    except (ValueError, TypeError):
        return 900


def _kms_key_id() -> str:
    return os.getenv("TOKENS_KMS_KEY_ID", "").strip()


def create_action_token_record(
    email: str,
    action_type: str,
    payload: dict,
    expires_in_seconds: int,
    source: str,
) -> str:
    """Creates a new action token row and returns token_id."""
    table_name = _token_table_name()
    if not table_name:
        raise RuntimeError("ACTION_TOKENS_TABLE_NAME is not set")

    token_id = base64.urlsafe_b64encode(os.urandom(32)).decode("utf-8").rstrip("=")
    now = int(time.time())
    item = {
        "token_id": token_id,
        "email": email.lower(),
        "action_type": action_type,
        "payload": payload,
        "source": source,
        "created_at": now,
        "expires_at": now + int(expires_in_seconds),
    }
    table = dynamodb.Table(table_name)
    table.put_item(Item=item)
    return token_id


def render_connect_strava_success_html() -> str:
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
      .ok { font-size: 20px; margin: 0 0 8px; }
      .muted { color: #555; }
    </style>
  </head>
  <body>
    <div class="card">
      <p class="ok">Connected to Strava</p>
      <p class="muted">You can close this tab and continue in email.</p>
    </div>
  </body>
</html>"""


def render_connect_strava_failed_html(message: str) -> str:
    safe_message = message.replace("<", "&lt;").replace(">", "&gt;")
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }}
      .card {{ max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }}
      .muted {{ color: #555; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Could not connect Strava</h2>
      <p class="muted">{safe_message}</p>
    </div>
  </body>
</html>"""


def ensure_athlete_id(email: str) -> str:
    """Ensures an athlete_id exists in coach_profiles and returns it."""
    table_name = _coach_profiles_table_name()
    if not table_name:
        raise RuntimeError("COACH_PROFILES_TABLE_NAME is not set")

    table = dynamodb.Table(table_name)
    now = int(time.time())
    response = table.update_item(
        Key={"email": email.lower()},
        UpdateExpression="""
            SET #created_at = if_not_exists(#created_at, :created_at),
                #updated_at = :updated_at,
                #athlete_id = if_not_exists(#athlete_id, :athlete_id)
        """,
        ExpressionAttributeNames={
            "#created_at": "created_at",
            "#updated_at": "updated_at",
            "#athlete_id": "athlete_id",
        },
        ExpressionAttributeValues={
            ":created_at": now,
            ":updated_at": now,
            ":athlete_id": f"ath_{uuid.uuid4().hex}",
        },
        ReturnValues="ALL_NEW",
    )
    athlete_id = (response.get("Attributes") or {}).get("athlete_id")
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise RuntimeError("Could not ensure athlete_id")
    return athlete_id


def upsert_athlete_connection(
    athlete_id: str,
    provider: str,
    provider_athlete_id: str,
    scopes: list[str],
) -> None:
    """Upserts athlete/provider connector metadata."""
    table_name = _athlete_connections_table_name()
    if not table_name:
        raise RuntimeError("ATHLETE_CONNECTIONS_TABLE_NAME is not set")

    provider_norm = provider.strip().lower()
    now = int(time.time())
    table = dynamodb.Table(table_name)
    table.update_item(
        Key={"athlete_id": athlete_id, "provider": provider_norm},
        UpdateExpression="""
            SET #created_at = if_not_exists(#created_at, :created_at),
                #updated_at = :updated_at,
                #status = :status,
                #gsi_provider = :gsi_provider,
                #provider_athlete_id = :provider_athlete_id,
                #gsi_provider_athlete_id = :provider_athlete_id,
                #scopes = :scopes
        """,
        ExpressionAttributeNames={
            "#created_at": "created_at",
            "#updated_at": "updated_at",
            "#status": "status",
            "#gsi_provider": "gsi_provider",
            "#provider_athlete_id": "provider_athlete_id",
            "#gsi_provider_athlete_id": "gsi_provider_athlete_id",
            "#scopes": "scopes",
        },
        ExpressionAttributeValues={
            ":created_at": now,
            ":updated_at": now,
            ":status": "connected",
            ":gsi_provider": provider_norm,
            ":provider_athlete_id": provider_athlete_id,
            ":scopes": scopes,
        },
    )


def encrypt_with_kms(plaintext: str) -> str:
    """KMS encrypts token values and returns base64 ciphertext."""
    key_id = _kms_key_id()
    if not key_id:
        raise RuntimeError("TOKENS_KMS_KEY_ID is not set")

    result = kms_client.encrypt(
        KeyId=key_id,
        Plaintext=plaintext.encode("utf-8"),
    )
    ciphertext_blob = result.get("CiphertextBlob")
    if not ciphertext_blob:
        raise RuntimeError("KMS encrypt returned empty ciphertext")
    return base64.b64encode(ciphertext_blob).decode("utf-8")


def upsert_provider_tokens(
    connection_id: str,
    access_token: str,
    refresh_token: str,
    expires_at: int,
) -> None:
    table_name = _provider_tokens_table_name()
    if not table_name:
        raise RuntimeError("PROVIDER_TOKENS_TABLE_NAME is not set")

    now = int(time.time())
    table = dynamodb.Table(table_name)
    table.update_item(
        Key={"connection_id": connection_id},
        UpdateExpression="""
            SET #created_at = if_not_exists(#created_at, :created_at),
                #updated_at = :updated_at,
                #access_token_enc = :access_token_enc,
                #refresh_token_enc = :refresh_token_enc,
                #expires_at = :expires_at
        """,
        ExpressionAttributeNames={
            "#created_at": "created_at",
            "#updated_at": "updated_at",
            "#access_token_enc": "access_token_enc",
            "#refresh_token_enc": "refresh_token_enc",
            "#expires_at": "expires_at",
        },
        ExpressionAttributeValues={
            ":created_at": now,
            ":updated_at": now,
            ":access_token_enc": encrypt_with_kms(access_token),
            ":refresh_token_enc": encrypt_with_kms(refresh_token) if refresh_token else None,
            ":expires_at": int(expires_at),
        },
    )


def exchange_strava_code_for_tokens(code: str) -> dict:
    client_id = _strava_client_id()
    client_secret = _strava_client_secret()
    if not client_id or not client_secret:
        raise RuntimeError("STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET must be configured")

    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
    }
    request = Request(
        STRAVA_TOKEN_URL,
        data=urlencode(payload).encode("utf-8"),
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response_data = response.read().decode("utf-8")
            return json.loads(response_data)
    except HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8")
        except Exception:
            body = str(e)
        raise RuntimeError(f"Strava token exchange failed: {e.code} {body}") from e
    except URLError as e:
        raise RuntimeError(f"Strava token exchange failed: {e}") from e


def handle_connect_strava_action(token_id: str, token_data: dict) -> dict:
    """Creates one-time OAuth state token and redirects user to Strava authorize."""
    email = (token_data.get("email") or "").strip().lower()
    if not email:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_invalid_token_html(),
            "result": "missing_email_on_connect_strava",
        }

    redirect_uri = _strava_redirect_uri()
    client_id = _strava_client_id()
    if not redirect_uri or not client_id:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth config is not set correctly."),
            "result": "strava_oauth_config_missing",
        }

    try:
        state_token = create_action_token_record(
            email=email,
            action_type="STRAVA_OAUTH_STATE",
            payload={"email": email, "origin_action_token_id": token_id},
            expires_in_seconds=_strava_state_ttl_seconds(),
            source="connect_strava",
        )
    except Exception as e:
        logger.error(f"Failed creating OAuth state token for {email}: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("Could not start Strava authorization."),
            "result": "strava_state_create_failed",
        }

    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": _strava_scopes(),
        "state": state_token,
    }
    authorize_url = f"{STRAVA_AUTHORIZE_URL}?{urlencode(params)}"
    return {
        "statusCode": 302,
        "headers": {"Location": authorize_url},
        "body": "",
        "result": "redirected_to_strava_authorize",
    }


def handle_strava_callback(event: dict, aws_request_id: str = None) -> dict:
    query = event.get("queryStringParameters") or {}
    if not isinstance(query, dict):
        query = {}

    error_value = (query.get("error") or "").strip()
    if error_value:
        logger.info(
            "result=strava_oauth_denied, error=%s%s",
            error_value,
            f", aws_request_id={aws_request_id}" if aws_request_id else "",
        )
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("Authorization was denied in Strava."),
        }

    state_token = (query.get("state") or "").strip()
    code = (query.get("code") or "").strip()
    if not state_token or not code:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("Missing OAuth callback parameters."),
        }

    token_data = get_token_from_db(state_token)
    now = int(time.time())
    if not token_data:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state is invalid or expired."),
        }
    if token_data.get("action_type") != "STRAVA_OAUTH_STATE":
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state is invalid."),
        }
    expires_at = int(token_data.get("expires_at", 0) or 0)
    if expires_at <= now:
        return {
            "statusCode": 410,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state expired. Start again from email."),
        }
    if token_data.get("used_at") is not None:
        return {
            "statusCode": 409,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state already used. Start again from email."),
        }
    if not consume_token_atomically(state_token, now):
        return {
            "statusCode": 409,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state already used. Start again from email."),
        }

    email = (token_data.get("payload") or {}).get("email") or token_data.get("email")
    if not isinstance(email, str) or not email.strip():
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("OAuth state is missing user info."),
        }

    try:
        token_response = exchange_strava_code_for_tokens(code)
        access_token = str(token_response.get("access_token") or "").strip()
        refresh_token = str(token_response.get("refresh_token") or "").strip()
        expires_at = int(token_response.get("expires_at") or 0)
        athlete = token_response.get("athlete") or {}
        provider_athlete_id = str(athlete.get("id") or "").strip()
        if not access_token or not refresh_token or not expires_at or not provider_athlete_id:
            raise RuntimeError("Strava token response is missing required fields")

        callback_scope = (query.get("scope") or "").strip()
        scopes = [s.strip() for s in callback_scope.split(",") if s.strip()] if callback_scope else []
        athlete_id = ensure_athlete_id(email)
        upsert_athlete_connection(
            athlete_id=athlete_id,
            provider="strava",
            provider_athlete_id=provider_athlete_id,
            scopes=scopes,
        )
        connection_id = f"{athlete_id}#strava"
        upsert_provider_tokens(
            connection_id=connection_id,
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
        )
    except Exception as e:
        logger.error(f"Strava callback processing failed: {e}")
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "text/html; charset=utf-8"},
            "body": render_connect_strava_failed_html("Failed to complete Strava connection."),
        }

    log_parts = [f"email={email.lower()}", "provider=strava", "result=strava_connected"]
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))
    return {
        "statusCode": 200,
        "headers": {"Content-Type": "text/html; charset=utf-8"},
        "body": render_connect_strava_success_html(),
    }


def is_strava_callback_request(event: dict) -> bool:
    path_candidates = [
        event.get("rawPath"),
        event.get("path"),
        (event.get("requestContext") or {}).get("path"),
        (event.get("requestContext") or {}).get("http", {}).get("path"),
    ]
    for value in path_candidates:
        if isinstance(value, str) and value.endswith("/oauth/strava/callback"):
            return True
    return False


def get_token_from_db(token_id: str) -> dict:
    """
    Looks up a token in the action_tokens DynamoDB table.
    
    Args:
        token_id: The token ID to lookup
    
    Returns:
        Token item dict if found, None otherwise
    """
    try:
        table_name = os.getenv("ACTION_TOKENS_TABLE_NAME")
        if not table_name:
            logger.error("ACTION_TOKENS_TABLE_NAME environment variable not set")
            return None
        
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"token_id": token_id})
        
        if "Item" in response:
            return response["Item"]
        return None
    except ClientError as e:
        logger.error(f"Error looking up token in DynamoDB: {e}")
        return None


def route_action(token_id: str, action_type: str, token_data: dict, now: int, aws_request_id: str = None) -> dict:
    """
    Routes to the appropriate handler based on action_type.
    
    Args:
        token_id: The token ID
        action_type: The action type from token data
        token_data: Full token data from DynamoDB
        now: Current epoch seconds
        aws_request_id: AWS request ID for logging
    
    Returns:
        Dict with statusCode, headers, body, and result (for logging)
    """
    action_type_upper = action_type.upper() if action_type else ""
    route_decision = "unknown_action"
    
    if action_type_upper == "VERIFY_SESSION":
        # Extract email from token record
        email = token_data.get("email")
        if not email:
            route_decision = "unknown_action"
            log_parts = [f"token_id={token_id}", f"action_type={action_type}", f"result={route_decision}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            response = {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_invalid_token_html()
            }
            return response
        
        # Get session TTL from environment with validation
        session_ttl_days = 14  # Default
        try:
            ttl_env = os.getenv("SESSION_TTL_DAYS", "14")
            session_ttl_days = int(ttl_env)
            if session_ttl_days <= 0:
                logger.warning(f"Invalid SESSION_TTL_DAYS value: {session_ttl_days}, using default 14")
                session_ttl_days = 14
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid SESSION_TTL_DAYS: {e}, using default 14")
            session_ttl_days = 14
        
        # Create/update verified session
        session_created = create_or_update_verified_session(email, now, session_ttl_days)
        
        if session_created:
            route_decision = "verified_session_created"
            response = {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_verify_session_html(),
                "result": route_decision
            }
        else:
            # Failed to create session - return error
            route_decision = "session_write_failed"
            response = {
                "statusCode": 500,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_session_write_failed_html(),
                "result": route_decision
            }
    elif action_type_upper == "UNSUBSCRIBE":
        route_decision = "unknown_action"
        response = {
            "statusCode": 200,
            "headers": {
                "Content-Type": "text/html; charset=utf-8"
            },
            "body": render_unsubscribe_html(),
            "result": route_decision
        }
    elif action_type_upper == "CONNECT_STRAVA":
        response = handle_connect_strava_action(token_id, token_data)
        route_decision = response.get("result", "connect_strava_failed")
    elif action_type_upper == "PAUSE_COACHING":
        route_decision = "unknown_action"
        response = {
            "statusCode": 400,
            "headers": {
                "Content-Type": "text/html; charset=utf-8"
            },
            "body": render_unknown_action_html(),
            "result": route_decision
        }
    else:
        # Unknown action type
        route_decision = "unknown_action"
        response = {
            "statusCode": 400,
            "headers": {
                "Content-Type": "text/html; charset=utf-8"
            },
            "body": render_unknown_action_html(),
            "result": route_decision
        }
    
    # Log outcome
    log_parts = [f"token_id={token_id}", f"action_type={action_type}", f"result={route_decision}"]
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))
    
    # Remove result from response before returning
    response.pop("result", None)
    return response


def consume_token_atomically(token_id: str, now: int) -> bool:
    """
    Atomically consumes a token by setting used_at.
    Uses conditional update to ensure single-use (race-safe).
    
    Args:
        token_id: The token ID to consume
        now: Current epoch seconds
    
    Returns:
        True if token was successfully consumed (first use), False if already used
    """
    try:
        table_name = os.getenv("ACTION_TOKENS_TABLE_NAME")
        if not table_name:
            logger.error("ACTION_TOKENS_TABLE_NAME environment variable not set")
            return False
        
        table = dynamodb.Table(table_name)
        
        # Atomic conditional update: only succeeds if used_at doesn't exist
        table.update_item(
            Key={"token_id": token_id},
            UpdateExpression="SET used_at = :used_at",
            ConditionExpression="attribute_not_exists(used_at)",
            ExpressionAttributeValues={":used_at": now}
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            # Token was already used (race condition or second request)
            logger.info(f"Token {token_id} already used (conditional update failed)")
            return False
        else:
            logger.error(f"Error consuming token {token_id}: {e}")
            return False


def create_or_update_verified_session(email: str, now: int, session_ttl_days: int) -> bool:
    """
    Creates or updates a verified session in the verified_sessions table.
    
    Args:
        email: Email address
        now: Current epoch seconds
        session_ttl_days: Number of days the session should last
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table_name = os.getenv("VERIFIED_SESSIONS_TABLE_NAME")
        if not table_name:
            logger.error("VERIFIED_SESSIONS_TABLE_NAME environment variable not set")
            return False
        
        table = dynamodb.Table(table_name)
        session_expires_at = now + (session_ttl_days * 86400)
        
        # Upsert verified session using UpdateItem (idempotent)
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET last_verified_at = :last_verified_at,
                    last_seen_at = :last_seen_at,
                    session_expires_at = :session_expires_at,
                    verification_count = if_not_exists(verification_count, :zero) + :one
            """,
            ExpressionAttributeValues={
                ":last_verified_at": now,
                ":last_seen_at": now,
                ":session_expires_at": session_expires_at,
                ":zero": 0,
                ":one": 1
            }
        )
        return True
    except ClientError as e:
        logger.error(f"Error creating/updating verified session for {email}: {e}")
        return False


def render_verify_session_html() -> str:
    """
    Renders HTML page for successfully verified session.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
      .ok { font-size: 20px; margin: 0 0 8px; }
      .muted { color: #555; }
    </style>
  </head>
  <body>
    <div class="card">
      <p class="ok">✅ Verified</p>
      <p class="muted">You can close this tab and reply to the email to continue.</p>
    </div>
  </body>
</html>"""


def render_unsubscribe_html() -> str:
    """
    Renders HTML page for UNSUBSCRIBE action.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Unsubscribe link accepted</h2>
      <p>Unsubscribe will be implemented next.</p>
    </div>
  </body>
</html>"""


def render_invalid_token_html() -> str:
    """
    Renders HTML page for invalid token (missing email).
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Invalid token</h2>
      <p>This link is not valid.</p>
    </div>
  </body>
</html>"""


def render_unknown_action_html() -> str:
    """
    Renders HTML page for unknown action.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Unknown action</h2>
      <p>This link is not recognized.</p>
    </div>
  </body>
</html>"""


def render_token_expired_html() -> str:
    """
    Renders HTML page for expired token.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Link expired</h2>
      <p>This link has expired. Please request a new one.</p>
    </div>
  </body>
</html>"""


def render_token_already_used_html() -> str:
    """
    Renders HTML page for already used token.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Link already used</h2>
      <p>This link has already been used. Please request a new one.</p>
    </div>
  </body>
</html>"""


def render_token_not_found_html() -> str:
    """
    Renders HTML page for missing/invalid token.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Link invalid or expired</h2>
      <p>This link may have expired or already been used. Please request a new one.</p>
    </div>
  </body>
</html>"""


def render_invalid_link_html() -> str:
    """
    Renders HTML page for invalid link (missing or empty token param).
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Invalid link</h2>
      <p>This link is not valid.</p>
    </div>
  </body>
</html>"""


def render_session_write_failed_html() -> str:
    """
    Renders HTML page for session write failure.
    
    Returns:
        HTML string
    """
    return """<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body { font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }
      .card { max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Something went wrong</h2>
      <p>Please request a new link and try again.</p>
    </div>
  </body>
</html>"""


def lambda_handler(event, context):
    """
    AWS Lambda function handler for action link endpoint.
    
    Looks up token in DynamoDB and returns appropriate HTML response.
    """
    # Get AWS request ID for logging
    aws_request_id = None
    if context and hasattr(context, "aws_request_id"):
        aws_request_id = context.aws_request_id
    
    try:
        if is_strava_callback_request(event):
            return handle_strava_callback(event, aws_request_id)

        # Extract token from path parameters
        path_parameters = event.get("pathParameters") or {}
        token_id = path_parameters.get("token", "")
        
        # Validate token path param (A2: non-empty)
        if not token_id or not isinstance(token_id, str) or len(token_id.strip()) == 0:
            result = "invalid_token_param"
            log_parts = [f'token_id="(missing)"', f"result={result}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            return {
                "statusCode": 400,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_invalid_link_html()
            }
        
        # Lookup token in DynamoDB
        token_data = get_token_from_db(token_id)
        now = int(time.time())
        
        if not token_data:
            # Token not found
            result = "missing_token"
            log_parts = [f"token_id={token_id}", f"result={result}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_not_found_html()
            }
        
        # Token found - check expiry
        expires_at = token_data.get("expires_at")
        action_type = token_data.get("action_type", "")
        
        # Defensive handling: if expires_at is missing or not parseable, treat as expired
        is_expired = True
        try:
            if expires_at is not None:
                # Handle int, str, Decimal, and float types from DynamoDB
                # boto3 DynamoDB resource returns Number types as Decimal
                from decimal import Decimal
                if isinstance(expires_at, Decimal):
                    expires_at_int = int(expires_at)
                elif isinstance(expires_at, (int, float)):
                    expires_at_int = int(expires_at)
                elif isinstance(expires_at, str):
                    expires_at_int = int(expires_at)
                else:
                    logger.warning(f"Unexpected expires_at type for token {token_id}: {type(expires_at)}")
                    expires_at_int = None
                
                if expires_at_int is not None:
                    is_expired = expires_at_int <= now
        except (ValueError, TypeError) as e:
            logger.warning(f"Could not parse expires_at for token {token_id}: {e}, treating as expired")
            is_expired = True
        
        # Check if token is already used (before expiry check)
        used_at = token_data.get("used_at")
        is_already_used = used_at is not None
        
        if is_expired:
            # Token found but expired - don't consume, just return expired
            result = "expired_token"
            log_parts = [f"token_id={token_id}", f"action_type={action_type}", f"result={result}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            return {
                "statusCode": 410,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_expired_html()
            }
        
        # Token is valid (not expired) - check if already used
        if is_already_used:
            # Token was already used
            result = "used_token"
            log_parts = [f"token_id={token_id}", f"action_type={action_type}", f"result={result}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            return {
                "statusCode": 409,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_already_used_html()
            }
        
        # Token is valid and not used - try to consume atomically
        consumed = consume_token_atomically(token_id, now)
        
        if consumed:
            # Successfully consumed (first use) - now route by action_type
            response = route_action(token_id, action_type, token_data, now, aws_request_id)
            # route_action already logs the outcome
            return response
        else:
            # Failed to consume (race condition - another request consumed it first)
            result = "used_token"
            log_parts = [f"token_id={token_id}", f"action_type={action_type}", f"result={result}"]
            if aws_request_id:
                log_parts.append(f"aws_request_id={aws_request_id}")
            logger.info(", ".join(log_parts))
            return {
                "statusCode": 409,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_already_used_html()
            }
        
    except Exception as e:
        logger.error(f"Error processing action link: {str(e)}")
        return {
            "statusCode": 500,
            "headers": {
                "Content-Type": "text/html; charset=utf-8"
            },
            "body": "<html><body><h1>Error</h1><p>An error occurred processing the action link.</p></body></html>"
        }
