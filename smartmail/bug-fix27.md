# Bug #27 Fix: Writer fabricates URLs and portal infrastructure

## Root cause

Neither the strategist nor the writer knows what ground truth is available to them. When the athlete asks for something not in the input (files, links, portal paths), the strategist generates a directive that goes along with the premise, and the writer fills in fabricated details. The strategist is the primary source — it invents delivery mechanisms (portals, exports, download paths) and the writer faithfully executes.

Confirmed via targeted test (`test_bug27_url_fabrication.py`): the strategist's `content_plan` and `main_message` contain fabricated infrastructure before the writer ever runs.

## Approach

Add a grounding rule to both prompt packs: only reference information present in your input — if the athlete asks for something you don't have, say you cannot provide it.

This is a general anti-hallucination principle, not a list of specific prohibitions. It covers URLs, portals, files, article titles, and anything else the LLM might invent to be helpful. No schema changes, no new fields, no contract changes.

## Changes

### 1. `prompt_packs/coach_reply/v1/coaching_reasoning.json` — strategist prompt

Added to COACH IDENTITY block:

> "Only reference information present in your input context. If the athlete asks for something you don't have — a file, a link, a resource, a specific fact — say you cannot provide it rather than inventing an answer."

### 2. `prompt_packs/coach_reply/v1/response_generation.json` — writer prompt

Added to COACH IDENTITY block:

> "Only reference information present in your input. If a file, link, or resource is not in the writer_brief, do not invent one — say you cannot provide it."

## Verification

`test_bug27_url_fabrication.py` sends the LAS-003 T12 athlete message ("attach the Week 2 ICS/CSV or provide a download link") through both layers and checks for URL fabrication. 6 consecutive runs post-fix produced zero fabricated URLs, zero invented filenames, and zero fake portal paths. The strategist consistently redirected to honest alternatives (offer to paste plan as text, ask the athlete to describe what they see).

## Touch points

2 prompt files, 1 line each.
