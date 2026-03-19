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
- **Audit logging**: Full audit prompt, raw LLM response, and parsed gap report written to orchestration log. AUDIT_START, AUDIT_GAPS/AUDIT_CLEAN events emitted to events.jsonl.
- **HTML report integration**: New `render_audit_section()` in reporter.sh showing gap table per phase with severity badges, coverage summary, and spec reference links.
- **Web dashboard integration**: New AuditPanel component in wt-web showing audit results per phase — gap table with severity color coding, coverage %, and drill-down to spec references. Reads from state.json `phase_audit_results[]` array.
- **Default enabled**: `post_phase_audit: true` (always on). Directive `post_phase_audit: false` to explicitly disable.

## Capabilities

### New Capabilities
- `post-phase-audit`: LLM-driven spec-vs-implementation audit at phase boundaries with gap detection, follow-up change generation, logging, HTML reporting, and web dashboard visualization

### Modified Capabilities
- `orchestration-engine`: Integration point in monitor loop for audit trigger
- `orchestration-report`: New audit section in HTML report
- `web-dashboard`: New AuditPanel component for gap visualization

## Impact

- New `lib/orchestration/auditor.sh` — audit logic, gap report generation, follow-up change creation
- `lib/orchestration/monitor.sh` — trigger audit before replan or terminal state
- `lib/orchestration/planner.sh` — receive gap report in replan prompt
- `lib/orchestration/reporter.sh` — new `render_audit_section()` for HTML report
- `lib/orchestration/utils.sh` — new directive `post_phase_audit`
- `bin/set-orchestrate` — new default constant, source auditor.sh
- `web/src/components/AuditPanel.tsx` — new React component for gap visualization
- `web/src/pages/Dashboard.tsx` — integrate AuditPanel
