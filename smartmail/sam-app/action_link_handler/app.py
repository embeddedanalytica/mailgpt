"""
Action Link Handler Lambda Function

Handles GET /action/{token} endpoint for action links (verification, etc.)
"""

import os
import logging
import time
import boto3 # type: ignore
from botocore.exceptions import ClientError # type: ignore

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize DynamoDB client
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))


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
    elif action_type_upper in ["CONNECT_STRAVA", "PAUSE_COACHING"]:
        # These actions are recognized but not yet implemented
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
