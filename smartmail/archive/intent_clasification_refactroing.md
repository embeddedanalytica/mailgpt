# Intent Classification Refactoring Plan

## Goal

Fix the design flaw where `requested_action` is being used for two different jobs:

- coarse routing
- fine-grained coaching behavior

The refactor should keep `requested_action` only for routing and remove it from the downstream behavior contract used by coaching reasoning and response generation.

## Problem Summary

Today the pipeline spreads behavioral interpretation across too many layers:

1. conversation intelligence classifies the inbound message
2. router uses that classification to choose mutate vs read-only behavior
3. coaching reasoning interprets the classification again
4. response generation interprets the classification again

This creates ambiguity and inconsistent replies. The clearest example is `clarify_only`:

- sometimes it means the athlete supplied information but more is still needed
- sometimes it means the athlete supplied enough information and the coach should proceed

Because both meanings are collapsed into one label, downstream layers guess wrong and reopen resolved topics.

## Core Design Change

Do not introduce a new downstream behavior taxonomy.

Instead:

- keep `requested_action` for routing only
- stop forwarding `requested_action` into the response brief as a behavioral signal
- let coaching reasoning decide from first principles what the coach should do next
- let the writer render that directive without inventing behavior

This is a narrower and safer refactor than adding new strategist schema fields.

## Phase 1: Keep Conversation Intelligence Narrow

Conversation intelligence remains responsible for coarse routing metadata only.

### Files

- [conversation_intelligence_prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/planner/conversation_intelligence_prompt.py)
- [conversation_intelligence_schema.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/planner/conversation_intelligence_schema.py)
- [conversation_intelligence_validator.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/planner/conversation_intelligence_validator.py)

### Changes

- keep:
  - `intent`
  - `complexity_score`
  - `requested_action`
  - `brevity_preference`
- but formally treat `requested_action` as routing metadata only
- do not rely on it as the main downstream coaching-behavior contract

### Outcome

Conversation intelligence stays useful for routing without owning nuanced coaching meaning.

## Phase 2: Decouple Routing from Coaching Behavior

Router may continue using `requested_action`, but downstream prompts should stop treating it as authoritative coaching policy.

### Files

- [inbound_rule_router.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/inbound_rule_router.py)
- [response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_assembly.py)
- [response_generation_contract.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/response_generation_contract.py)

### Changes

In the router:

- keep `_ACTION_MODE_MAP` for coarse execution path only
- allow `requested_action` to continue informing `mutate`, `read_only`, or `skip`

In response brief assembly:

- stop copying `requested_action` into `decision_context`
- remove the lines that forward it into the strategist/writer brief
- keep `brevity_preference` flowing through — it is a legitimate presentation signal, not a behavioral override

In response generation contract:

- remove `requested_action` from `_DECISION_CONTEXT_FIELDS`
- remove the `requested_action` validation block in `_validate_decision_context`

### Why

Routing and coaching behavior are different questions:

- routing needs a coarse signal
- coaching behavior needs full-context reasoning

### Outcome

`requested_action` still helps determine whether the system should run the plan mutation path, but it no longer overrides downstream behavior.

## Phase 3: Make Coaching Reasoning Decide Behavior from First Principles

Coaching reasoning already has enough information to decide whether the athlete answered enough, whether the coach should proceed, and whether anything still needs to be asked.

### Files

- [coaching_reasoning.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/coaching_reasoning.json)
- [skills/coaching_reasoning/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/coaching_reasoning/prompt.py)

Note: `v1-proposal/coaching_reasoning.json` already lacks the "Athlete directive signals" section. No change needed there.

### Changes

Remove the current section that tells coaching reasoning to "respect requested_action strictly."

Replace it with instructions like:

- read the athlete's current message and determine what was answered versus what remains unresolved
- if the athlete has adequately answered the coach's previous open loop, move forward rather than re-asking
- use the existing directive fields to encode that decision:
  - `main_message`
  - `content_plan`
  - `avoid`
- if a topic has been answered or resolved, include it in `avoid` so the writer does not reopen it

Also add brevity calibration:

- match directive length to turn complexity — a confirmation or check-in acknowledgment needs a 1-2 sentence main_message and a short content_plan, not a multi-paragraph coaching essay
- when the athlete's message is brief or low-content (simple confirmation, short check-in), keep the directive minimal — do not pad it with coaching rationale the athlete did not ask for
- reserve longer directives for turns where the athlete introduced new information, asked a real question, or the plan is genuinely changing

### Important constraint

Do not add a new large behavior schema here. Use the strategist fields that already exist.

### Outcome

Coaching reasoning becomes the single owner of "what should the coach do next?" without adding a heavy new enum contract. Low-content turns produce proportionally brief directives.

## Phase 4: Tighten the Writer to Follow the Directive

The writer should not infer behavior from routing metadata. It should faithfully render the strategist's directive.

### Files

- [response_generation.json](/Users/levonsh/Projects/smartmail/sam-app/email_service/prompt_packs/coach_reply/v1/response_generation.json)
- [skills/response_generation/prompt.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/skills/response_generation/prompt.py)

### Changes

Strengthen directive-following instructions:

- when `content_plan` does not include a follow-up question, do not invent one
- when the `avoid` list includes a resolved topic, do not reopen it
- do not turn a confirmation message into another confirmation checklist
- if the strategist indicates the next step is to proceed, acknowledge and move forward briefly

Add output-length calibration:

- match email length to directive weight — a short directive should produce a short email
- when the coaching_directive.content_plan has 1-2 items and main_message is a brief acknowledgment, the email should be a few sentences, not multiple paragraphs
- do not pad short directives with filler coaching advice, motivational prose, or unsolicited plan summaries
- a good confirmation reply can be 2-4 sentences total

### Why

The writer already works in directive mode. The problem is not that it needs a new behavior taxonomy. The problem is that it has been allowed to improvise too much when the strategist input is ambiguous, and to inflate short directives into long emails.

### Outcome

Writer becomes closer to presentation-only without requiring a large schema redesign. Low-content turns produce proportionally brief emails.

## Phase 5: Add Focused Regression Tests

Test that the strategist and writer stop reopening resolved topics.

### Files

- [test_coaching_reasoning_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching_reasoning_skill.py)
- [test_response_generation_skill.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_skill.py)
- [test_response_generation_assembly.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_response_generation_assembly.py)
- [test_coaching.py](/Users/levonsh/Projects/smartmail/sam-app/email_service/test_coaching.py)

### Add cases

- athlete confirms requested details and coach should proceed without re-asking
- athlete partially answers and coach should ask only the remaining missing piece
- athlete confirms and adds a real plan-affecting change, so re-planning remains appropriate
- writer does not invent new follow-up questions when strategist did not ask for them
- writer respects `avoid` when resolved topics are named there

### Outcome

The fix is enforced at the two layers that matter most:

- strategist decision
- final email rendering

## Recommended Rollout

1. Stop forwarding `requested_action` into the response brief.
2. Remove strict `requested_action` behavior rules from coaching reasoning prompt.
3. Improve coaching reasoning prompt so it decides from first principles what was answered and what remains unresolved.
4. Tighten writer prompt so it does not invent follow-up questions or reopen resolved items.
5. Add regression tests around resolved-clarification behavior.

## Expected Result

After this refactor:

- conversation intelligence still helps with routing
- router still chooses mutate vs read-only vs skip
- coaching reasoning becomes the single owner of reply behavior
- writer stops acting like a second strategist
- resolved confirmation turns stop producing pointless re-confirmation emails

## Design Principle

Routing metadata should choose the path.  
Coaching reasoning should choose the behavior.  
The writer should render the decision, not make one.
