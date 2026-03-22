"""
Centralized configuration for the email service.
All environment variables and feature flags in one place.
"""
import os

# AWS
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# DynamoDB table names
USERS_TABLE = os.getenv("USERS_TABLE", "users")
RESPONSE_EVALUATION_TABLE = os.getenv("RESPONSE_EVALUATION_TABLE", "response_evaluations")
RATE_LIMITS_TABLE_NAME = os.getenv("RATE_LIMITS_TABLE_NAME")

# Verified user quotas (spam/abuse protection)
VERIFIED_HOURLY_QUOTA = int(os.getenv("VERIFIED_HOURLY_QUOTA", "2"))
VERIFIED_DAILY_QUOTA = int(os.getenv("VERIFIED_DAILY_QUOTA", "10"))

# Rate-limit notice (throttled “you’re over limit” emails)
SEND_RATE_LIMIT_NOTICE = os.getenv("SEND_RATE_LIMIT_NOTICE", "false").lower() == "true"
RATE_LIMIT_NOTICE_COOLDOWN_MINUTES = int(
    os.getenv("RATE_LIMIT_NOTICE_COOLDOWN_MINUTES", "60")
)

# Verification email cooldown (avoid spamming unverified users)
VERIFY_EMAIL_COOLDOWN_MINUTES = int(os.getenv("VERIFY_EMAIL_COOLDOWN_MINUTES", "30"))
VERIFY_TOKEN_TTL_MINUTES = int(os.getenv("VERIFY_TOKEN_TTL_MINUTES", "30"))

# Action link (verification link base URL)
ACTION_BASE_URL = os.getenv("ACTION_BASE_URL", "")

# OpenAI (model names only; API key stays in openai client init)
LIGHTWEIGHT_RESPONSE_MODEL = os.getenv("LIGHTWEIGHT_RESPONSE_MODEL", "gpt-5-nano")
OPENAI_CLASSIFICATION_MODEL = os.getenv("OPENAI_CLASSIFICATION_MODEL", "gpt-5-mini")
OPENAI_GENERIC_MODEL = os.getenv("OPENAI_GENERIC_MODEL", OPENAI_CLASSIFICATION_MODEL)
OPENAI_REASONING_MODEL = os.getenv("OPENAI_REASONING_MODEL", OPENAI_CLASSIFICATION_MODEL)
NO_RESPONSE_MODEL = os.getenv("NO_RESPONSE_MODEL", LIGHTWEIGHT_RESPONSE_MODEL)

ADVANCED_RESPONSE_MODEL = os.getenv("ADVANCED_RESPONSE_MODEL", OPENAI_GENERIC_MODEL)
MODEL_ROUTING_LIGHTWEIGHT_MAX_COMPLEXITY = int(
    os.getenv("MODEL_ROUTING_LIGHTWEIGHT_MAX_COMPLEXITY", "2")
)

# Profile extraction (missing-profile detail collection)
PROFILE_EXTRACTION_MODEL = os.getenv("PROFILE_EXTRACTION_MODEL", OPENAI_CLASSIFICATION_MODEL)
ENABLE_SESSION_CHECKIN_EXTRACTION = (
    os.getenv("ENABLE_SESSION_CHECKIN_EXTRACTION", "false").lower() == "true"
)

# RE4 planning/rendering models
PLANNING_LLM_MODEL = os.getenv("PLANNING_LLM_MODEL", OPENAI_GENERIC_MODEL)
LANGUAGE_RENDER_MODEL = os.getenv("LANGUAGE_RENDER_MODEL", OPENAI_GENERIC_MODEL)

# Coaching reasoning (two-stage pipeline)
ENABLE_COACHING_REASONING = (
    os.getenv("ENABLE_COACHING_REASONING", "").strip().lower() == "true"
)
