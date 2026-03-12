## Why

When all changes in a phase are merged, the orchestrator either replans (auto_replan=true) or terminates (auto_replan=false). In both cases, there is no verification that the merged code on main actually covers the input spec. The existing `final_coverage_check()` only counts requirement statuses from digest metadata — it never looks at the actual code. This means:

1. Changes that merged with partial implementation (scope check passed but 50% of tasks were wrong) go undetected
2. Requirements that the decomposition plan missed entirely are never caught
3. The replan cycle has no structured gap data to feed into the next plan — it only knows which changes completed, not what's still missing

In CraftBrew E2E Run #3, 8 of 14 changes merged with zero implementation code. Even with the verify gate fix, a phase-level audit would have caught this as a systemic pattern and generated targeted follow-up changes.

## What Changes

- **Post-phase LLM audit**: After all changes are merged (before replan or termination), run an LLM audit that compares the input spec against the actual codebase on main. Outputs a structured gap report.
- **Gap-to-change generation**: For each gap found, auto-create follow-up change entries in the next replan cycle with specific scope and retry context.
- **Audit integration into replan**: The replan prompt receives the gap report, so the LLM planner prioritizes unimplemented features over new decomposition.
- **Audit integration into terminal state**: When auto_replan=false, the audit report is included in the completion report and email notification.
- **Configurable via directive**: `post_phase_audit: true|false` (default: true when auto_replan is enabled)

## Capabilities

### New Capabilities
- `post-phase-audit`: LLM-driven spec-vs-implementation audit at phase boundaries with gap detection and follow-up change generation

### Modified Capabilities
- `orchestration-engine`: Integration point in monitor loop for audit trigger

## Impact

- New `lib/orchestration/auditor.sh` — audit logic, gap report generation, follow-up change creation
- `lib/orchestration/monitor.sh` — trigger audit before replan or terminal state
- `lib/orchestration/planner.sh` — receive gap report in replan prompt
- `lib/orchestration/utils.sh` — new directive `post_phase_audit`
- `bin/wt-orchestrate` — new default constant
