import { DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";
import { SESClient, SendEmailCommand } from "@aws-sdk/client-ses";

const dynamoDBClient = new DynamoDBClient({ region: "us-west-2" });
const sesClient = new SESClient({ region: "us-west-2" });

export const handler = async (event) => {
  console.log("Event: ", event);

  // Handle OPTIONS Preflight Request
  if (event.requestContext.http.method === "OPTIONS") {
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
  if (event.requestContext.http.method === "POST") {
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

      // Send follow-up email using SES
      const emailParams = {
        Destination: {
          ToAddresses: [email],
        },
        Message: {
          Body: {
            Text: {
              Data: `Thank you for registering with GeniML! You can now interact with our AI-powered service by sending an email to your preferred AI agent at @geniml.com. For example, if you need pet advice, email vet@geniml.com. Welcome aboard!`,
            },
          },
          Subject: {
            Data: "Welcome to GeniML!",
          },
        },
        Source: "no-reply@geniml.com", // Ensure this email is verified in SES
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
        body: JSON.stringify({ message: "Successfully registered and email sent!" }),
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