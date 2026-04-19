---
name: deslop
description: Use when Codex needs to identify and remove AI-style code slop in Python, JavaScript, TypeScript, JSX, TSX, or HTML codebases. Apply it when the user asks to simplify code, trim verbose comments or docstrings, reduce over-engineering, tighten vague naming, remove duplicated helpers or pass-through layers, or clean up templated boilerplate while preserving behavior.
---

# Deslop

Trim bloated, generic, or overbuilt code without turning the task into a style sweep. Start with an audit, name the concrete slop signals, then make the smallest edits that materially improve clarity and structure.

## Setup

Resolve the project-local skill path from the repo root:

```bash
export REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
export DESLOP_HOME="$REPO_ROOT/.cursor/skills/deslop"
```

Run the bundled target collector from the repo root unless the user already named exact files:

```bash
python3 "$DESLOP_HOME/scripts/collect_targets.py"
python3 "$DESLOP_HOME/scripts/collect_targets.py" sam-app/email_service
```

## Workflow

1. Read repo instructions first: [`CLAUDE.md`](../../../CLAUDE.md), [`AGENTS.md`](../../../AGENTS.md) (merge bar), then skill/module `CLAUDE.md` if touching that area.
2. Select targets.
   - If the user named files or directories, inspect only those paths.
   - Otherwise run `scripts/collect_targets.py` and start with changed files in the current git repo.
3. Audit before editing. Report findings under concrete buckets such as `verbose comments`, `over-engineering`, `bad naming`, `duplication`, and `dead scaffolding`.
4. Patch only confirmed issues. Make behavior-preserving edits with the narrowest useful scope.
5. Run the narrowest relevant tests after cleanup. If the repo has an explicit done gate, run it before declaring the task finished.

## What To Remove

Treat these as first-class slop signals:

- Comments or docstrings that restate obvious code, narrate each line, or read like a tutorial.
- Wrapper functions, classes, or modules that add no policy and only pass values through.
- Generic names that hide intent, especially `manager`, `processor`, `handler`, `util`, `helper`, `data`, `info`, `new_*`, and `final_*`.
- Redundant abstraction layers created for hypothetical future reuse.
- Boilerplate families with one real callsite or duplicated logic split across many tiny files.
- Dead branches, unused fallback paths, placeholder extension points, and low-value configuration knobs.

Open `references/slop-signals.md` when you need the detailed heuristics or need to distinguish justified complexity from fluff.

## Editing Rules

- Prefer deleting or merging redundant layers over cosmetic rewriting.
- Rename only when the new name is clearly more precise and the rename is local enough to do safely.
- Trim comments aggressively when they restate the code.
- Keep comments that explain business rules, constraints, non-obvious intent, or why a choice exists.
- Preserve stable public APIs unless the user asked for a broader refactor.
- Avoid provenance claims. Do not say code is AI-generated; describe the structural or stylistic problem directly.

## No-Touch Defaults

Skip these unless the user explicitly asks:

- Vendored, generated, or third-party code
- Files with generated headers
- Build outputs and caches
- Asset and binary folders

`scripts/collect_targets.py` already excludes common paths such as `vendor/`, `node_modules/`, `.aws-sam/`, `__pycache__/`, `dist/`, `build/`, `.cursor/`, and `.playwright-cli/`.

## Decision Boundaries

Stop and ask before:

- Collapsing architecture across many files
- Renaming broad public interfaces
- Deleting code whose behavior or ownership is unclear
- Touching excluded or generated code

## Output Shape

Lead with findings. For each issue, state:

- the file or symbol
- the slop category
- why it adds cost without enough value
- the minimal cleanup that would improve it

After the audit, implement the confirmed cleanups and summarize the behavior-preserving changes plus the tests you ran.
