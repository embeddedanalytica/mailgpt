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

logger = logging.getLogger(__name__)
openai.api_key = os.getenv("OPENAI_API_KEY")
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


class ResponseEvaluation:
    """Evaluates AI-generated replies and stores results in DynamoDB."""

    EVAL_SYSTEM_PROMPT_TEMPLATE = (
        "You are a strict evaluator of email replies. Here is the email thread. "
        "Read it in reverse chronological order to understand the entire thread:\n\n{original_email}\n\n"
        "Here is the suggested reply from the agent:\n\n{ai_response}\n\n"
        "Please do the following:\n"
        "1. Assign a score from 1-5 for each of the following categories: Accuracy, Relevance, Clarity, Helpfulness, and Tone.\n"
        "2. For each category, provide one or two sentences explaining why you gave that score.\n\n"
        "Respond in JSON only, with the following structure:\n"
        "{{\n"
        '  "accuracy_score": X,\n'
        '  "accuracy_justification": "...",\n'
        '  "relevance_score": X,\n'
        '  "relevance_justification": "...",\n'
        '  "clarity_score": X,\n'
        '  "clarity_justification": "...",\n'
        '  "helpfulness_score": X,\n'
        '  "helpfulness_justification": "...",\n'
        '  "tone_score": X,\n'
        '  "tone_justification": "..."\n'
        "}}"
    )

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
