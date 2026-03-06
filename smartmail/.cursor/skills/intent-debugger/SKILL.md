---
name: intent-debugger
description: Use when the user wants to locally debug, classify, inspect, or validate SmartMail message intent using the real conversation-intelligence pipeline without deploying to AWS or sending email. Apply it for requests to test a pasted message, run the intent classifier, inspect intent-routing behavior, compare repeated runs, or summarize why the classifier produced a specific result.
---

# Intent Debugger

Run the real local intent-classification CLI, then explain the result in plain language.

## Setup

Resolve the project-local skill path from the repo root:

```bash
export REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export INTENT_DEBUGGER_HOME="$REPO_ROOT/.cursor/skills/intent-debugger"
```

Use the bundled wrapper unless the user explicitly asks to call the underlying CLI directly:

```bash
python3 "$INTENT_DEBUGGER_HOME/scripts/run_intent_debug.py" --message "Travel week, only two days available" --pretty
```

## Workflow

1. Read the user prompt and extract the message they want classified.
2. If the user pasted a long or multi-line message, pass it via stdin to the wrapper. Use `--message` only for short inline text.
3. Run the local wrapper so the call goes through `sam-app/email_service/debug_conversation_intelligence.py` and the real `analyze_conversation_intelligence()` path.
4. If the user is checking stability or inconsistency, add `--repeat 3`. Otherwise keep the default single run.
5. Read the JSON output and summarize:
   - final intent
   - complexity score
   - resolution source
   - notable signal flags
   - why the classifier likely landed there
6. If repeated runs were requested, explicitly say whether the outcome was stable or varied.

## Guardrails

- Do not mock the classifier or reimplement intent logic.
- Do not route through AWS, SNS, SES, `business.py`, or the full email flow.
- Fail clearly if `OPENAI_API_KEY` is missing or the local debug CLI cannot be found.
- Keep the summary concise. Lead with the final intent and the reason it seems to have won.
- Include raw JSON only if the user asks for it or it helps explain unstable behavior.

## Output Shape

Default response should cover:

- detected intent
- complexity score
- resolution source (`resolver`, `judge`, or `fallback`)
- notable signals
- short behavior summary
- stability note when repeated runs were used
