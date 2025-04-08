import openai
import logging
import os

logger = logging.getLogger()
logger.setLevel(logging.INFO)

OPENAI_GENERIC_MODEL = "gpt-4o-mini-2024-07-18"
NO_RESPONSE_MODEL = "gpt-4o-mini-2024-07-18"

openai.api_key = os.getenv("OPENAI_API_KEY")

class OpenAIResponder:
    SYSTEM_PROMPT = (
        "You are an AI assistant that writes natural, friendly, and conversational replies to user emails..."
    )

    NOT_REGISTERED_SYSTEM_PROMPT = (
        "You must inform the user that they are not registered and cannot receive a response. "
        "Be polite and invite them to register at https://geniml.com."
    )

    SYSTEM_PROMPT_FOR_INTENTION_CHECK = (
        "You are an intelligent email assistant analyzing the latest email in a thread..."
    )

    @staticmethod
    def generate_response(subject, body):
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_GENERIC_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}\n{body}"},
                ],
            )
            ai_reply = response.choices[0].message.content.strip()
            signature = "\n\nTruly yours,\nGeniML\nhttps://geniml.com"
            disclaimer = "\n\n###\nDisclaimer: This response is AI-generated and may contain errors..."
            return ai_reply + signature + disclaimer
        except Exception as e:
            logger.error(f"Error generating response: {e}")
            return None

    @staticmethod
    def generate_invite_response(subject, body):
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=NO_RESPONSE_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.NOT_REGISTERED_SYSTEM_PROMPT},
                    {"role": "user", "content": subject},
                ],
            )
            return response.choices[0].message.content.strip() + "\n\nTruly yours,\nGeniML\nhttps://geniml.com"
        except Exception as e:
            logger.error(f"Error generating invite: {e}")
            return None

    @staticmethod
    def should_ai_respond(email_body, recipient, to_recipients, cc_recipients):
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_GENERIC_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT_FOR_INTENTION_CHECK},
                    {"role": "user", "content": email_body}
                ],
                temperature=0
            )
            decision = response.choices[0].message.content.strip().lower()
            return decision == "true"
        except Exception as e:
            logger.error(f"Error in intention check: {e}")
            return False