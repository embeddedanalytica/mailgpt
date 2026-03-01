import crypto from "crypto";
import { DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";
import { SESClient, SendEmailCommand } from "@aws-sdk/client-ses";
import { EMAIL_COPY } from "./email_copy.mjs";

const dynamoDBClient = new DynamoDBClient({ region: "us-west-2" });
const sesClient = new SESClient({ region: "us-west-2" });
const ACTION_TOKENS_TABLE_NAME = process.env.ACTION_TOKENS_TABLE_NAME || "action_tokens";
const ACTION_BASE_URL = process.env.ACTION_BASE_URL || "https://geniml.com/action/";
const VERIFY_TOKEN_TTL_MINUTES = parseInt(process.env.VERIFY_TOKEN_TTL_MINUTES || "30", 10);

export const handler = async (event) => {
  console.log("Event: ", event);
  const method =
    event?.requestContext?.http?.method ||
    event?.httpMethod ||
    event?.requestContext?.httpMethod ||
    "";

  // Handle OPTIONS Preflight Request
  if (method === "OPTIONS") {
    return {
      statusCode: 200,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "OPTIONS, POST",
        "Access-Control-Allow-Headers": "Content-Type",
      },
      body: "OK",
    };
  }

  // Handle POST Request
  if (method === "POST") {
    try {
      console.log("Body: ", event.body);
      const requestBody = JSON.parse(event.body);
      const email = requestBody.email;

      if (!email) {
        return {
          statusCode: 400,
          body: JSON.stringify({ message: "Email is required" }),
        };
      }

      // Store in DynamoDB
      await dynamoDBClient.send(
        new PutItemCommand({
          TableName: "users",
          Item: { email_address: { S: email } },
        })
      );

      // Create verification token (single-use in action_tokens)
      const token = crypto.randomBytes(32).toString("base64url");
      const now = Math.floor(Date.now() / 1000);
      const expiresAt = now + VERIFY_TOKEN_TTL_MINUTES * 60;
      await dynamoDBClient.send(
        new PutItemCommand({
          TableName: ACTION_TOKENS_TABLE_NAME,
          Item: {
            token_id: { S: token },
            email: { S: email.toLowerCase() },
            action_type: { S: "VERIFY_SESSION" },
            created_at: { N: String(now) },
            expires_at: { N: String(expiresAt) },
            source: { S: "registration_api" },
          },
        })
      );

      const verificationLink = `${ACTION_BASE_URL}${token}`;
      const verificationText = EMAIL_COPY.verify.text({
        verificationLink,
        tokenTtlMinutes: VERIFY_TOKEN_TTL_MINUTES,
      });

      // Send follow-up email using SES
      const emailParams = {
        Destination: {
          ToAddresses: [email],
        },
        Message: {
          Body: {
            Text: {
              Data: verificationText,
            },
          },
          Subject: {
            Data: EMAIL_COPY.verify.subject,
          },
        },
        Source: EMAIL_COPY.verify.source, // Ensure this email is verified in SES
      };

      await sesClient.send(new SendEmailCommand(emailParams));

      return {
        statusCode: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "OPTIONS, POST",
          "Access-Control-Allow-Headers": "Content-Type",
        },
        body: JSON.stringify({ message: "Successfully registered. Verification email sent." }),
      };
    } catch (error) {
      console.error(error);
      return {
        statusCode: 500,
        body: JSON.stringify({ message: "Internal Server Error" }),
      };
    }
  }

  // Method Not Allowed (fallback)
  return {
    statusCode: 405,
    headers: {
      "Access-Control-Allow-Origin": "*",
      "Access-Control-Allow-Methods": "OPTIONS, POST",
      "Access-Control-Allow-Headers": "Content-Type",
    },
    body: JSON.stringify({ message: "Method Not Allowed" }),
  };
};
