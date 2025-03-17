import { DynamoDBClient, PutItemCommand } from "@aws-sdk/client-dynamodb";

const client = new DynamoDBClient({ region: "us-west-2" });

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
      await client.send(
        new PutItemCommand({
          TableName: "users",
          Item: { email_address: { S: email } },
        })
      );

      return {
        statusCode: 200,
        headers: {
          "Content-Type": "application/json",
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "OPTIONS, POST",
          "Access-Control-Allow-Headers": "Content-Type",
        },
        body: JSON.stringify({ message: "Successfully registered!" }),
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