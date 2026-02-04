# SmartMail - AI-Powered Email Response Service

This project is a serverless email automation service that uses OpenAI to automatically respond to incoming emails. The application receives emails via AWS SES, processes them through SNS, generates AI-powered responses, and sends replies back via SES.

## Architecture

The application consists of two main Lambda functions:

1. **EmailServiceFunction** (Python) - Processes incoming emails and generates AI responses
   - Triggered by SNS notifications from SES
   - Parses email content from SNS messages
   - Checks user registration in DynamoDB
   - Generates AI responses using OpenAI
   - Sends replies via SES
   - Evaluates response quality and stores evaluations

2. **mailgptregistration** (Node.js) - Handles user registration via API Gateway
   - Exposes REST API endpoint: `POST /register`
   - Stores user emails in DynamoDB
   - Sends welcome emails via SES

### Data Flow

```
Incoming Email → AWS SES → SNS Topic → EmailServiceFunction → OpenAI API → SES Reply
                                                              ↓
                                                         DynamoDB (user check, evaluations)
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

2. **DynamoDB Tables**:
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
│   ├── requirements.txt    # Python dependencies
│   └── vendor/             # Bundled dependencies (OpenAI, etc.)
├── email_registration/     # Node.js Lambda function for user registration
│   └── app.mjs             # Registration API handler
├── template.yaml           # SAM/CloudFormation template
└── samconfig.toml          # SAM deployment configuration
```

## Deployment

### First Time Deployment

1. **Configure your OpenAI API key** in `template.yaml` (line 25):
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

The `EmailServiceFunction` requires:
- `OPENAI_API_KEY`: Your OpenAI API key (set in `template.yaml`)

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

### Run API Gateway Locally

```bash
sam local start-api
```

The API will be available at `http://localhost:3000/register`

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

### Filter Logs

```bash
# Filter for errors only
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "ERROR"

# Filter for specific email
sam logs -n EmailServiceFunction --stack-name "sam-app" --filter "user@example.com"
```

## How It Works

### Email Processing Flow

1. **Email Received**: SES receives an email and stores it in S3
2. **SNS Notification**: SES publishes a notification to SNS topic
3. **Lambda Triggered**: `EmailServiceFunction` is invoked by SNS
4. **Email Parsing**: Function extracts email content from SNS message
5. **User Check**: Verifies sender is registered in DynamoDB `users` table
6. **AI Response Generation**: 
   - Determines if AI should respond (checks if AI is mentioned or direct recipient)
   - Generates response using OpenAI GPT models
   - Evaluates response quality
7. **Reply Sent**: Sends reply via SES with proper threading headers

### Registration Flow

1. **API Request**: User sends POST request to `/register` endpoint
2. **Email Storage**: Email address stored in DynamoDB `users` table
3. **Welcome Email**: Confirmation email sent via SES

## Key Features

- **Intelligent Response Detection**: Only responds when appropriate (AI mentioned, direct recipient, etc.)
- **Email Threading**: Maintains proper email threading with `In-Reply-To` and `References` headers
- **Response Evaluation**: Automatically evaluates AI-generated responses for quality
- **User Registration**: Simple API-based user registration system
- **Multi-recipient Support**: Handles TO and CC recipients correctly

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

- Ensure `users` table exists with `email_address` as partition key
- Verify IAM permissions allow DynamoDB access
- Check table region matches Lambda region

## Cleanup

To delete the entire application stack:

```bash
sam delete --stack-name "sam-app"
```

**Note**: This will delete all Lambda functions, but will NOT delete:
- DynamoDB tables (must be deleted manually)
- S3 bucket (must be deleted manually)
- SNS topics (must be deleted manually)
- SES configuration (must be removed manually)

## Resources

- [AWS SAM Developer Guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/what-is-sam.html)
- [AWS SES Documentation](https://docs.aws.amazon.com/ses/)
- [OpenAI API Documentation](https://platform.openai.com/docs)
- [SAM CLI Documentation](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/serverless-sam-cli-install.html)
