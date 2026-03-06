# Slop Signals

Use this reference to classify code bloat precisely. Favor concrete findings over general complaints.

## Verbosity

Treat these as removable unless they capture non-obvious intent:

- Comments or docstrings that restate the code line by line
- Tutorial-style narration inside production code
- Large section headers that add no information
- Filler TODOs with no owner, trigger, or decision
- Repetitive prose spread across neighboring helpers

Keep comments that explain why, constraints, invariants, business rules, or surprising edge cases.

## Over-Engineering

Treat these as likely slop:

- Wrapper classes with no policy beyond forwarding calls
- Single-use abstractions justified by hypothetical reuse
- Strategy or factory layers with one real implementation
- Config flags with one valid value
- Orchestration layers that only reshuffle inputs and outputs
- Fragmented modules where each file holds trivial glue

Keep complexity that protects domain rules, compatibility, or operational safety.

## Naming

Treat these as likely naming debt:

- Vague names like `manager`, `processor`, `handler`, `util`, `helper`, `data`, `info`
- Placeholder prefixes like `new_`, `final_`, `temp_`
- Overlong names that describe mechanics instead of intent
- Near-synonyms split across files for the same concept
- Names that hide the domain concept behind generic verbs

Prefer names that match the repo's existing domain language and make the object or function's job obvious.

## Structure

Treat these as structural slop:

- Duplicated helper families with tiny variations
- Dead branches or unused fallback paths
- Placeholder extensibility for product directions that do not exist
- Extra files created only to preserve symmetry
- Pass-through helpers that only rename parameters

Prefer collapsing code until each layer has a distinct reason to exist.

## Keep Rules

Do not remove something only because it looks verbose or abstract. Keep it when:

- tests or callers prove the shape is relied on
- the code carries domain-required complexity
- comments preserve business context or incident history
- a public API would break without an explicit migration
- naming is already aligned with the product vocabulary

## No-Touch Defaults

Skip by default:

- vendored and third-party code
- generated files or files with generated headers
- build artifacts and caches
- binary and asset directories

Ask before broad renames, cross-cutting simplification, or cleanup that changes an external contract.
