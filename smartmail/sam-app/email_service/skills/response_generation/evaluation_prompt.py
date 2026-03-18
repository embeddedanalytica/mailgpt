"""Prompt template for response-evaluation workflow."""

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
