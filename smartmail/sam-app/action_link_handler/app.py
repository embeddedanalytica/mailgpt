"""
Action Link Handler Lambda Function

Handles GET /action/{token} endpoint for action links (verification, etc.)
"""

import os
import logging
import time
import boto3
from botocore.exceptions import ClientError

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


def render_token_found_html(token_id: str, token_data: dict) -> str:
    """
    Renders HTML page for found token.
    
    Args:
        token_id: The token ID from URL
        token_data: Token data from DynamoDB
    
    Returns:
        HTML string
    """
    action_type = token_data.get("action_type", "N/A")
    email = token_data.get("email", "N/A")
    expires_at = token_data.get("expires_at", "N/A")
    
    return f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SmartMail Coach</title>
    <style>
      body {{ font-family: -apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif; padding: 24px; line-height: 1.4; }}
      .card {{ max-width: 640px; margin: 0 auto; border: 1px solid #ddd; border-radius: 12px; padding: 18px 20px; }}
      code {{ background: #f5f5f5; padding: 2px 6px; border-radius: 6px; }}
      .field {{ margin: 12px 0; }}
      .label {{ font-weight: 600; }}
    </style>
  </head>
  <body>
    <div class="card">
      <h2>Token found ✅</h2>
      <div class="field">
        <span class="label">Token ID:</span> <code>{token_id}</code>
      </div>
      <div class="field">
        <span class="label">Action Type:</span> {action_type}
      </div>
      <div class="field">
        <span class="label">Email:</span> {email}
      </div>
      <div class="field">
        <span class="label">Expires At:</span> {expires_at}
      </div>
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


def lambda_handler(event, context):
    """
    AWS Lambda function handler for action link endpoint.
    
    Looks up token in DynamoDB and returns appropriate HTML response.
    """
    try:
        # Extract token from path parameters
        path_parameters = event.get("pathParameters") or {}
        token_id = path_parameters.get("token", "")
        
        if not token_id:
            logger.warning("No token provided in path parameters")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_not_found_html()
            }
        
        # Log the token lookup attempt
        logger.info(f"Looking up token: {token_id}")
        
        # Lookup token in DynamoDB
        token_data = get_token_from_db(token_id)
        
        if token_data:
            logger.info(f"Token found: {token_id}, action_type={token_data.get('action_type')}, email={token_data.get('email')}")
            return {
                "statusCode": 200,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_found_html(token_id, token_data)
            }
        else:
            logger.info(f"Token not found: {token_id}")
            return {
                "statusCode": 404,
                "headers": {
                    "Content-Type": "text/html; charset=utf-8"
                },
                "body": render_token_not_found_html()
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
