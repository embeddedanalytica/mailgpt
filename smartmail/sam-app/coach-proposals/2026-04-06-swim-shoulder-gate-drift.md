---
proposal_id: 2026-04-06-swim-shoulder-gate-drift
created_at: 2026-04-06T00:00:00Z
status: discarded
discarded_reason: Broader lower-confidence continuity/state redesign than the silent no-reply failure, so it was not the best single highest-priority fix for this run.
issue_tags: [missed_continuity, schedule_inconsistency, hallucinated_context]
affected_files:
  - sam-app/email_service/skills/coaching_reasoning/
  - sam-app/email_service/sectioned_memory_*.py
  - sam-app/email_service/memory_compiler.py
confidence: 3
estimated_cx_impact: 5
---

## Source
Sim: athlete-sim-1775449607-2e638241@example.com · Persona: Keiko (Olympic tri build, shoulder constraint) · Turns: multiple across trace (notably mid-trace fueling turn and late-trace “710 day” / “2025 minute” lines)

## Issue
The coach repeatedly referenced a **May 6 proof swim** and a **7–10 day symptom-free window** while the athlete had already progressed to **structured swim work, open-water pickups, and race-simulation bricks**. Replies sometimes **contradicted** the athlete’s reported reality (e.g. still “technique-only” after they reported 8×50 cruise or 2×(8×100) steady). Some outputs contained **absurd numerics** (“20925 minute technique swim”, “7910 consecutive symptom-free days”, “move feed by 1590 minutes”, “710 day” windows), which reads as broken software, not conservative coaching.

## Diagnosis
**Coaching reasoning** is not **statefully reconciling** the shoulder-return protocol against **latest inbound facts** and **compiled memory** (dates, what was cleared, current week). The model **re-anchors** to an old gate (May 6) every turn without a **single source of truth** for “swim intensity clearance level.” Under load, it also **hallucinates** numeric magnitudes (already related to `prescription-numeric-integrity` proposal) but here the pattern is **merged digits and wrong units** tied to **protocol vocabulary**. `memory_compiler` / **sectioned memory** may not be persisting a compact **shoulder_protocol_state** (e.g. `cleared_for: structured_swim | ows | intervals`) so the strategist improvises inconsistently.

## Proposed change
(1) Add a **small structured state** in memory or rule-engine output (not schema migration — use existing JSON blobs if allowed) for **injury/return protocols**: last proof date, current gate, next allowed action. **Coaching_reasoning** must read that blob and **forbid** contradicting it unless inbound says symptoms returned. (2) Tighten **operational rules** for swim-return: one paragraph max on gates; **no restating** full history unless athlete asks. (3) Extend **numeric sanity** (see `2026-04-05-prescription-numeric-integrity.md`) to reject **impossible minute/day counts** in protocol text before send. (4) Prompt size: mostly **tightening** redundant gate prose → **slight reduction** if done well.

## Why this fixes it
One consistent machine-readable state stops the coach from arguing with the athlete’s own log and stops absurd numbers from appearing in protocol language.

## Risks
Over-structuring could fight nuanced LLM judgment—keep state minimal (enum + dates).

## Verification
Re-run long Keiko-style shoulder arc; assert no reply says “technique-only only” after athlete reports cleared structured set without a new flare.
