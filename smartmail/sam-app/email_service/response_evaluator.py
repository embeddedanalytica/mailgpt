"""
LLM layer: evaluation and storage of AI-generated email responses.
Uses OPENAI_REASONING_MODEL; all eval prompts and storage live here.
"""
import logging
import os
import time
import uuid
import boto3  # type: ignore
import openai  # type: ignore

from config import OPENAI_REASONING_MODEL, RESPONSE_EVALUATION_TABLE, AWS_REGION
from skills.response_generation import EVAL_SYSTEM_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


class ResponseEvaluation:
    """Evaluates AI-generated replies and stores results in DynamoDB."""

    EVAL_SYSTEM_PROMPT_TEMPLATE = EVAL_SYSTEM_PROMPT_TEMPLATE

    @staticmethod
    def evaluate_response(original_email: str, ai_response: str) -> str | None:
        """
        Evaluates the AI-generated response and stores the result in DynamoDB.
        Returns the evaluation JSON string, or None on error.
        """
        try:
            client = openai.OpenAI()
            prompt = ResponseEvaluation.EVAL_SYSTEM_PROMPT_TEMPLATE.format(
                original_email=original_email,
                ai_response=ai_response,
            )
            response = client.chat.completions.create(
                model=OPENAI_REASONING_MODEL,
                messages=[{"role": "system", "content": prompt}],
            )
            evaluation_result = response.choices[0].message.content.strip()
            logger.info("Evaluation result: %s", evaluation_result)

            table = dynamodb.Table(RESPONSE_EVALUATION_TABLE)
            table.put_item(
                Item={
                    "evaluation_id": str(uuid.uuid4()),
                    "original_email": original_email,
                    "ai_response": ai_response,
                    "evaluation": evaluation_result,
                    "timestamp": int(time.time()),
                }
            )
            return evaluation_result
        except Exception as e:
            logger.error("Error evaluating AI response: %s", e)
            return None
