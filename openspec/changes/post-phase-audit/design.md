## Decision: LLM audit with structured output, not code analysis

The audit compares the input spec text against a summary of what was merged — NOT by reading all source code (too expensive). Instead:

1. Collect the list of merged changes with their scopes and file lists
2. Collect the input spec (or digest requirements)
3. Ask an LLM: "Given this spec and these completed changes, what features are missing or incomplete?"

This is a planning-level check, not a code review. It catches decomposition gaps and completely missing features, not implementation quality issues (that's the verify gate's job).

## Decision: Structured gap report format

The audit outputs JSON for machine consumption:

```json
{
  "audit_result": "gaps_found|clean",
  "gaps": [
    {
      "id": "GAP-1",
      "description": "Subscription management page — no route or component exists",
      "spec_reference": "Section 4.2: User subscription management",
      "severity": "critical|minor",
      "suggested_scope": "Add /[locale]/elofizetes route with subscription list, cancel, and upgrade functionality"
    }
  ],
  "summary": "3 critical gaps, 1 minor gap found out of 14 spec sections"
}
```

## Decision: Audit placement in the pipeline

```
All changes merged/failed
        │
        ▼
┌─────────────────────────────┐
│  Phase-end E2E (if config'd)│
└──────────┬──────────────────┘
           │
           ▼
┌─────────────────────────────┐
│  POST-PHASE AUDIT (new)     │  ← runs BEFORE replan
│  - Collect merged scopes    │
│  - Compare vs input spec    │
│  - Generate gap report      │
└──────────┬──────────────────┘
           │
           ▼
   ┌───────┴───────┐
   │               │
   ▼               ▼
 Replan          Terminal
 (gaps in       (gaps in
  prompt)        report)
```

The audit runs after phase-end E2E (if configured) but before auto_replan_cycle(). This means the replan prompt can include the gap report.

## Decision: Gap-to-change injection in replan

Instead of auto-creating OpenSpec changes, inject the gap descriptions into the replan prompt via `_REPLAN_AUDIT_GAPS` env var. The LLM planner then decides whether to create dedicated changes for each gap or fold them into larger changes. This respects the planner's decomposition logic rather than bypassing it.

## Approach: Audit function in auditor.sh

New file `lib/orchestration/auditor.sh` with:

- `run_post_phase_audit()` — main entry point, collects context, calls LLM, parses output
- `build_audit_prompt()` — constructs the prompt with spec + merged changes + file lists
- `parse_audit_result()` — extracts JSON from LLM output (same pattern as plan parser)

The LLM call uses `run_claude` with the review model (sonnet by default, configurable).

## Approach: Two modes based on input type

- **Digest mode**: Use `requirements.json` — audit against individual REQ-IDs, cross-reference with `coverage.json`. More precise, outputs which REQ-IDs have no implementation evidence.
- **Spec/brief mode**: Use raw spec text — audit against spec sections. Less precise but still catches major gaps.

## Risk: Token cost

The audit adds one LLM call per phase (~10-30K input tokens for spec + change list). For a typical 3-phase orchestration, that's 3 extra calls. Acceptable given the value — catching missing features early prevents expensive replan cycles that implement the same gaps again.

## Risk: LLM hallucinating gaps

The LLM might report features as "missing" when they're implemented under a different name or approach. Mitigation: include file lists per change so the LLM can see what was actually touched. Also, the gap report feeds into the replan prompt — the planner (another LLM call) acts as a second opinion before committing to new changes.
