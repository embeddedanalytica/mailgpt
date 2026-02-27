# SmartMail - AI-Powered Email Coaching Service

This project is a serverless email-only coaching product that uses OpenAI to provide conversational coaching responses. The application features email verification to prevent abuse, rate limiting to control costs, and ensures personal data is never leaked to spoofers.

## Architecture

The application consists of three main Lambda functions:

1. **EmailServiceFunction** (Python) - Processes incoming emails with verification gate and anti-abuse protection
   - Triggered by SNS notifications from SES
   - Parses email content from SNS messages
   - **Verification Gate**: Checks if sender has verified session before processing
   - **Unverified Users**: Creates verification token and sends verification email (no LLM calls)
   - **Cooldown Protection**: Enforces 30-minute cooldown between verification emails (prevents spam/abuse)
   - **Verified Users**: Generates AI responses using OpenAI (when implemented)
   - Sends replies via SES
   - Evaluates response quality and stores evaluations
   - Manages coach profiles, action tokens, verified sessions, and rate limits

2. **mailgptregistration** (Node.js) - Handles user registration via API Gateway
   - Exposes REST API endpoint: `POST /register`
   - Stores user emails in DynamoDB
   - Sends welcome emails via SES

3. **ActionLinkHandlerFunction** (Python) - Handles action links for email verification
   - Exposes REST API endpoint: `GET /action/{token}`
   - Processes single-use action tokens (verification, unsubscribe, etc.)
   - Validates token expiry and single-use enforcement
   - Creates/updates verified sessions for email verification
   - Returns HTML responses for user-facing pages

### Data Flow

```
Incoming Email → AWS SES → SNS Topic → EmailServiceFunction
                                      ↓
                              Check verified_sessions
                                      ↓
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            Not Verified                          Verified
                    │                                   │
        Check cooldown (rate_limits)          Generate AI Response
                    │                                   │
        ┌───────────┴───────────┐                      │
        │                       │                      │
  Cooldown Active        Cooldown Expired              │
        │                       │                      │
  Drop Silently    Create token + Send verify email    │
        │              (action_tokens)                 │
        │                       │                      │
        └───────────────────────┘                      │
                                                        ↓
                                              OpenAI API → SES Reply

User Registration → API Gateway → mailgptregistration → DynamoDB + SES Welcome Email

Action Link Click → API Gateway → ActionLinkHandlerFunction
                                      ↓
                              Validate token (action_tokens)
                                      ↓
                    ┌─────────────────┴─────────────────┐
                    │                                   │
            Invalid/Expired/Used                  Valid Token
                    │                                   │
            Return Error HTML              Atomically consume token
                    │                                   │
                    │                          Create verified_sessions
                    │                                   │
                    │                          Return Success HTML
```

## Prerequisites

To use the SAM CLI, you need the following tools:

* **SAM CLI** - [Install the SAM CLI](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
* **Python 3.13** - [Install Python 3.13](https://www.python.org/downloads/)
* **Node.js 22.x** - [Install Node.js](https://nodejs.org/)
* **Docker** - [Install Docker](https://hub.docker.com/search/?type=edition&offering=community) (required for `sam build --use-container`)
* **AWS CLI** - [Install AWS CLI](https://aws.amazon.com/cli/)
* **OpenAI API Key** - Get your API key from [OpenAI Platform](https://platform.openai.com/)

## AWS Resources Required

Before deploying, ensure you have:

1. **AWS SES Configuration**:
   - Verified email addresses/domains in SES
   - SES Receipt Rule configured to:
     - Store emails in S3 bucket (`smart-gpt-email`)
     - Publish notifications to SNS topic (`smart_mail_sns`)
   - SNS topic subscribed to `EmailServiceFunction`

2. **DynamoDB Tables** (created automatically by SAM template):
   - `coach_profiles` - Coaching preferences storage (partition key: `email`)
   - `action_tokens` - Single-use expiring action links (partition key: `token_id`, TTL: `expires_at`)
   - `verified_sessions` - Verified inbox possession state (partition key: `email`, TTL: `session_expires_at`)
   - `rate_limits` - Anti-abuse counters and cooldowns (partition key: `email`)
   
   **Note:** (Tech Dept!!) The following tables must be created manually (not in SAM template):
   - `users` table with partition key: `email_address` (String)
   - `response_evaluations` table with partition key: `evaluation_id` (String)

3. **S3 Bucket** (optional, for email storage):
   - Bucket: `smart-gpt-email`
   - Configured in SES Receipt Rule

## Project Structure

```
sam-app/
├── email_service/          # Python Lambda function for email processing
│   ├── app.py              # Main Lambda handler
│   ├── email_processor.py  # Email parsing from SNS
│   ├── email_reply_sender.py # SES email sending
│   ├── openai_responder.py # OpenAI API integration
│   ├── response_evaluator.py # Response quality evaluation
│   ├── dynamodb_models.py  # DynamoDB data access layer
│   ├── utils.py            # Utility functions
│   ├── requirements.txt    # Python dependencies
│   └── vendor/             # Bundled dependencies (OpenAI, etc.)
├── email_registration/     # Node.js Lambda function for user registration
│   └── app.mjs             # Registration API handler
├── action_link_handler/    # Python Lambda function for action links
│   └── app.py              # Action link handler (token validation, verification)
├── template.yaml           # SAM/CloudFormation template
└── samconfig.toml          # SAM deployment configuration
```

## Deployment

### First Time Deployment

1. **Configure your OpenAI API key** in `template.yaml` (line ~85):
   ```yaml
   Environment:
     Variables:
       OPENAI_API_KEY: your-api-key-here
   ```

2. **Build the application**:
   ```bash
   cd sam-app
   sam build --use-container
   ```

3. **Deploy with guided prompts**:
   ```bash
   sam deploy --guided
   ```

   The guided deployment will prompt you for:
   - **Stack Name**: `sam-app` (or your preferred name)
   - **AWS Region**: `us-west-2` (or your preferred region)
   - **Confirm changes before deploy**: Yes/No
   - **Allow SAM CLI IAM role creation**: Yes (required)
   - **Save arguments to samconfig.toml**: Yes (recommended)

### Subsequent Deployments

After the first deployment, your configuration is saved in `samconfig.toml`. Simply run:

```bash
sam build --use-container
sam deploy
```

### Deploy Specific Function Only

```bash
sam build EmailServiceFunction
sam deploy
```

## API Endpoints

The application exposes the following API Gateway endpoints:

### 1. User Registration
- **Endpoint**: `POST /register`
- **Handler**: `mailgptregistration` (Node.js)
- **Request Body**:
  ```json
  {
    "email": "user@example.com"
  }
  ```
- **Response**: 200 OK with confirmation message
- **Functionality**: 
  - Stores email in DynamoDB `users` table
  - Sends welcome email via SES

### 2. Action Link Handler
- **Endpoint**: `GET /action/{token}`
- **Handler**: `ActionLinkHandlerFunction` (Python)
- **Path Parameter**: `token` - Single-use action token
- **Response Codes**:
  - `200 OK` - Token consumed successfully, action completed
  - `400 Bad Request` - Invalid token format or missing parameter
  - `404 Not Found` - Token doesn't exist
  - `409 Conflict` - Token already used
  - `410 Gone` - Token expired
  - `500 Internal Server Error` - Session write failure (token consumed but session creation failed)
- **Functionality**:
  - Validates token existence, expiry, and single-use status
  - Atomically consumes token (race-safe)
  - Creates/updates verified session for `VERIFY_SESSION` action type
  - Returns HTML page with appropriate message

## Configuration

### SNS Topic Subscription

After deployment, ensure your SNS topic is subscribed to the Lambda function:

```bash
# Get the function ARN
FUNCTION_ARN=$(aws cloudformation describe-stack-resources \
  --stack-name sam-app \
  --query 'StackResources[?LogicalResourceId==`EmailServiceFunction`].PhysicalResourceId' \
  --output text)

# Add permission for SNS
aws lambda add-permission \
  --function-name $FUNCTION_ARN \
  --statement-id sns-invoke \
  --action lambda:InvokeFunction \
  --principal sns.amazonaws.com \
  --source-arn arn:aws:sns:us-west-2:YOUR_ACCOUNT_ID:smart_mail_sns

# Subscribe to SNS topic
aws sns subscribe \
  --topic-arn arn:aws:sns:us-west-2:YOUR_ACCOUNT_ID:smart_mail_sns \
  --protocol lambda \
  --notification-endpoint $FUNCTION_ARN
```

### Environment Variables

**EmailServiceFunction** requires (automatically set by SAM):
- `OPENAI_API_KEY`: Your OpenAI API key (set in `template.yaml`)
- `ACTION_BASE_URL`: Base URL for action links (e.g., `https://api.example.com/action/`)
- `ACTION_TOKENS_TABLE_NAME`: Name of the action_tokens DynamoDB table
- `VERIFIED_SESSIONS_TABLE_NAME`: Name of the verified_sessions DynamoDB table
- `RATE_LIMITS_TABLE_NAME`: Name of the rate_limits DynamoDB table
- `VERIFY_TOKEN_TTL_MINUTES`: Token expiration time in minutes (default: "30")
- `VERIFY_EMAIL_COOLDOWN_MINUTES`: Cooldown period between verification emails in minutes (default: "30")

**ActionLinkHandlerFunction** requires (automatically set by SAM):
- `ACTION_TOKENS_TABLE_NAME`: Name of the action_tokens DynamoDB table
- `VERIFIED_SESSIONS_TABLE_NAME`: Name of the verified_sessions DynamoDB table
- `COACH_PROFILES_TABLE_NAME`: Name of the coach_profiles DynamoDB table
- `ATHLETE_CONNECTIONS_TABLE_NAME`: Name of the athlete_connections DynamoDB table
- `PROVIDER_TOKENS_TABLE_NAME`: Name of the provider_tokens DynamoDB table
- `SESSION_TTL_DAYS`: Number of days for verified session TTL (default: "14")
- `STRAVA_CLIENT_ID`: Strava application client ID
- `STRAVA_CLIENT_SECRET`: Strava application client secret
- `STRAVA_REDIRECT_URI`: OAuth callback URL (e.g., `https://geniml.com/oauth/strava/callback`)
- `STRAVA_SCOPES`: Requested Strava scopes (default: `read,activity:read_all`)
- `STRAVA_STATE_TTL_MINUTES`: OAuth state token TTL in minutes (default: "15")
- `TOKENS_KMS_KEY_ID`: KMS key ID/ARN used to encrypt provider tokens before storage

## Local Development and Testing

### Build Locally

```bash
sam build --use-container
```

### Test Email Service Function Locally

Create a test event file `events/sns-email-event.json` with an SNS message structure, then:

```bash
sam local invoke EmailServiceFunction --event events/sns-email-event.json
```

### Test Registration API Locally

```bash
sam local start-api
```

Then test the registration endpoint:

```bash
curl -X POST http://localhost:3000/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com"}'
```

### Test Action Link Handler Locally

```bash
sam local start-api
```

Then test the action link endpoint:

```bash
# Test with a valid token (replace {token} with actual token from action_tokens table)
curl http://localhost:3000/action/{token}

# Test with missing token (should return 404)
curl http://localhost:3000/action/nonexistent-token
```

### Run API Gateway Locally

```bash
sam local start-api
```

The API will be available at:
- `http://localhost:3000/register` (POST) - User registration
- `http://localhost:3000/action/{token}` (GET) - Action link handler

## Monitoring and Logs

### View Logs for EmailServiceFunction

```bash
sam logs -n EmailServiceFunction --stack-name "sam-app" --tail
```

Or using AWS CLI:

```bash
aws logs tail "/aws/lambda/sam-app-EmailServiceFunction-<SUFFIX>" \
  --region us-west-2 --follow
```

### View Logs for Registration Function

```bash
sam logs -n mailgptregistration --stack-name "sam-app" --tail
```

### View Logs for Action Link Handler

```bash
sam logs -n ActionLinkHandlerFunction --stack-name "sam-app" --tail
```

Or using AWS CLI:

```bash
aws logs tail "/aws/lambda/sam-app-ActionLinkHandlerFunction-<SUFFIX>" \
  --region us-west-2 --follow
```

### Filter Logs

```bash
# Filter for errors only
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "ERROR"

# Filter for specific email
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "user@example.com"

# Filter for verification email sends
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "result=verification_email_sent"

# Filter for cooldown drops
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "result=unverified_dropped_cooldown"

# Filter action link handler by result code
sam logs -n ActionLinkHandlerFunction --stack-name "sam-app" --filter "result=verified_session_created"
```

## How It Works

### Email Processing Flow

1. **Email Received**: SES receives an email and stores it in S3
2. **SNS Notification**: SES publishes a notification to SNS topic
3. **Lambda Triggered**: `EmailServiceFunction` is invoked by SNS
4. **Email Parsing**: Function extracts email content from SNS message
5. **Verification Check**: 
   - Checks `verified_sessions` table for sender's email
   - If verified and session not expired → proceed to response generation
   - If not verified → go to verification flow
6. **Verification Flow** (unverified users):
   - Check `rate_limits` table for cooldown status
   - If cooldown active → drop silently (no email, no LLM call)
   - If cooldown expired → atomically set cooldown (race-safe)
   - Create verification token in `action_tokens` table (30-minute TTL)
   - Send verification email with action link
   - Return (no LLM call, no response sent)
7. **Response Generation** (verified users only):
   - Determines if AI should respond (checks if AI is mentioned or direct recipient)
   - Generates response using OpenAI GPT models (when implemented)
   - Evaluates response quality
   - Sends reply via SES with proper threading headers

### Registration Flow

1. **API Request**: User sends POST request to `/register` endpoint
2. **Email Storage**: Email address stored in DynamoDB `users` table
3. **Welcome Email**: Confirmation email sent via SES

### Action Link Flow (Email Verification)

1. **Token Generation**: EmailServiceFunction creates action token in `action_tokens` table when unverified user sends email
   - Token ID: Secure random base64url (32+ bytes)
   - Action Type: `VERIFY_SESSION`
   - Expires: 30 minutes from creation
   - Source: `email_inbound`
2. **Verification Email Sent**: Email sent to user with action link (e.g., `https://api.example.com/action/{token}`)
   - Subject: "Verify to access your coaching insights"
   - Includes privacy explanation and expiration notice
   - No personal data included
3. **User Clicks Link**: GET request to `/action/{token}` endpoint
4. **Token Validation**: ActionLinkHandlerFunction validates:
   - Token exists in `action_tokens` table (404 if missing)
   - Token not expired (`expires_at` > current time, 410 if expired)
   - Token not already used (`used_at` is null, 409 if used)
5. **Token Consumption**: Atomically marks token as used (race-safe conditional update)
   - Uses `attribute_not_exists(used_at)` condition
   - Prevents double-use in concurrent requests
6. **Action Routing**: Routes based on `action_type`:
   - `VERIFY_SESSION`: Creates/updates verified session in `verified_sessions` table
   - `UNSUBSCRIBE`: Stub implementation (returns confirmation page)
   - Unknown actions: Returns 400 error
7. **Session Creation** (for VERIFY_SESSION):
   - Sets `last_verified_at`, `last_seen_at` to current time
   - Sets `session_expires_at` to current time + 14 days (TTL)
   - Increments `verification_count`
8. **Response**: Returns HTML page confirming verification (✅ Verified)

**Action Types Supported:**
- `VERIFY_SESSION` - Email verification (creates verified session, 14-day TTL)
- `UNSUBSCRIBE` - Unsubscribe from emails (stub implementation, returns confirmation page)
- `CONNECT_STRAVA` - Redirects user to Strava OAuth and stores encrypted tokens on callback
- `PAUSE_COACHING` - Pause coaching (not yet implemented, returns 400)

**Rate Limiting & Cooldowns:**
- Verification email cooldown: 30 minutes (configurable via `VERIFY_EMAIL_COOLDOWN_MINUTES`)
- Token expiration: 30 minutes (configurable via `VERIFY_TOKEN_TTL_MINUTES`)
- Session TTL: 14 days (configurable via `SESSION_TTL_DAYS`)
- All cooldown operations are race-safe using atomic conditional updates

## Key Features

### Security & Anti-Abuse
- **Email Verification Gate**: Unverified users receive verification emails instead of LLM responses
- **Cooldown Protection**: 30-minute cooldown between verification emails prevents spam/abuse
- **Race-Safe Operations**: Atomic conditional updates prevent duplicate verification emails in concurrent requests
- **No Data Leakage**: Personal data never sent to unverified/spoofed addresses
- **Cost Protection**: No LLM calls for unverified requests

### Email Processing
- **Intelligent Response Detection**: Only responds when appropriate (AI mentioned, direct recipient, etc.)
- **Email Threading**: Maintains proper email threading with `In-Reply-To` and `References` headers
- **Response Evaluation**: Automatically evaluates AI-generated responses for quality
- **Multi-recipient Support**: Handles TO and CC recipients correctly

### User Management
- **User Registration**: Simple API-based user registration system
- **Email Verification**: Secure email verification system with verified sessions
- **Session Management**: Verified sessions with configurable TTL (default: 14 days)

### Action Links
- **Single-Use Tokens**: Time-limited, single-use action links for email verification and other actions
- **Token Management**: Atomic token consumption with race-safe single-use enforcement
- **Expiry Validation**: Tokens expire after 30 minutes (configurable)
- **Action Routing**: Supports multiple action types (VERIFY_SESSION, UNSUBSCRIBE, etc.)

## Troubleshooting

### Function Not Receiving Emails

1. Check SNS topic subscription:
   ```bash
   aws sns list-subscriptions-by-topic \
     --topic-arn arn:aws:sns:us-west-2:YOUR_ACCOUNT_ID:smart_mail_sns
   ```

2. Verify SES Receipt Rule is configured correctly
3. Check Lambda function permissions for SNS

### OpenAI API Errors

- Check API key is correct in `template.yaml`
- Verify OpenAI account has sufficient quota
- Check logs for specific error messages (429 = quota exceeded)

### DynamoDB Errors

- Ensure `users` table exists with `email_address` as partition key (created manually)
- Verify IAM permissions allow DynamoDB access
- Check table region matches Lambda region
- For ActionLinkHandlerFunction: Ensure `action_tokens` and `verified_sessions` tables exist (created by SAM template)

### Action Link Handler Errors

- **404 Not Found**: Token doesn't exist in `action_tokens` table
- **410 Gone**: Token has expired (check `expires_at` field)
- **409 Conflict**: Token has already been used (check `used_at` field)
- **400 Bad Request**: Invalid token format, missing token parameter, or unknown action type
- **500 Internal Server Error**: Session write failure (token already consumed, but session creation failed)

Check logs for detailed error information:
```bash
sam logs -n ActionLinkHandlerFunction --stack-name "sam-app" --tail
```

### Verification Email Issues

- **No verification email received**: 
  - Check if user is already verified (check `verified_sessions` table)
  - Check if cooldown is active (check `rate_limits.verify_email_cooldown_until`)
  - Check logs for `result=verification_email_sent` or `result=unverified_dropped_cooldown`
  - Verify `ACTION_BASE_URL` environment variable is set correctly

- **Multiple verification emails sent**:
  - Should not happen due to atomic cooldown protection
  - Check logs for `result=cooldown_race_lost` to see if race condition occurred
  - Verify `rate_limits` table has correct cooldown values

- **Verification link doesn't work**:
  - Check token exists in `action_tokens` table
  - Verify token hasn't expired (30-minute TTL)
  - Check if token was already used (`used_at` field)
  - Review ActionLinkHandlerFunction logs for specific error codes

## Cleanup

To delete the entire application stack:

```bash
sam delete --stack-name "sam-app"
```

**Note**: This will delete all Lambda functions and API Gateway endpoints, but will NOT delete:
- DynamoDB tables created by SAM template (`coach_profiles`, `action_tokens`, `verified_sessions`, `rate_limits`) - must be deleted manually
- DynamoDB tables created manually (`users`, `response_evaluations`) - must be deleted manually
- S3 bucket (must be deleted manually)
- SNS topics (must be deleted manually)
- SES configuration (must be removed manually)

## Resources

- [AWS SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
- [AWS SES Documentation](https://docs.aws.amazon.com/ses/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [SAM CLI Documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
