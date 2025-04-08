import logging
import openai
import boto3
import time
import uuid
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

openai.api_key = os.getenv("OPENAI_API_KEY")
dynamodb = boto3.resource("dynamodb")
RESPONSE_EVALUAION_TABLE = "response_evaluations"
OPENAI_REASONING_MODEL = "gpt-4o-mini-2024-07-18"

class ResponseEvaluation:

    @staticmethod
    def evaluate_response(original_email, ai_response):
        try:
            client = openai.OpenAI()
            prompt = (
                "You are a strict evaluator of email replies. Read in reverse order.\n\n"
                + original_email + "\n\n"
                "Here is the reply:\n\n"
                + ai_response + "\n\n"
                "Score 1–5 for Accuracy, Relevance, Clarity, Helpfulness, Tone. Justify each.\n\n"
                "Respond in JSON:\n"
                "{\n"
                "  \"accuracy_score\": X,\n"
                "  ...\n"
                "}"
            )
            response = client.chat.completions.create(
                model=OPENAI_REASONING_MODEL,
                messages=[{"role": "system", "content": prompt}]
            )
            result = response.choices[0].message.content.strip()

            table = dynamodb.Table(RESPONSE_EVALUAION_TABLE)
            evaluation_id = str(uuid.uuid4())
            table.put_item(Item={
                "evaluation_id": evaluation_id,
                "original_email": original_email,
                "ai_response": ai_response,
                "evaluation": result,
                "timestamp": int(time.time())
            })
            return result
        except Exception as e:
            logger.error(f"Eval failed: {e}")
            return None