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

## Decision: Default enabled (always on)

Prototype testing on MiniShop Run #6 showed 92% spec coverage detection with sonnet in ~80s at ~66K tokens. Cost is negligible compared to the value — catching missing E2E tests and screenshots that the planner omitted. Default is `post_phase_audit: true` (always runs). Users can explicitly disable with `post_phase_audit: false` in orchestration.yaml.

Previous design said "auto" (true only with auto_replan). Changed because the audit is equally valuable in terminal state — the completion report should show what was missed even without replan.

## Decision: Audit results stored as array in state

State stores `phase_audit_results` as an array (one entry per phase/cycle) rather than a single `phase_audit_result`. This supports multi-phase orchestrations where each cycle has its own audit.

```json
{
  "phase_audit_results": [
    {
      "cycle": 1,
      "timestamp": "2026-03-13T05:35:00+01:00",
      "audit_result": "gaps_found",
      "model": "sonnet",
      "duration_ms": 82000,
      "input_tokens": 21000,
      "gaps": [...],
      "summary": "4 critical gaps, 1 minor"
    }
  ]
}
```

## Approach: Audit logging

Three levels of audit logging:

1. **Events (events.jsonl)**: `AUDIT_START` (with cycle, mode), `AUDIT_GAPS` or `AUDIT_CLEAN` (with gap count, severity breakdown, duration_ms)
2. **Orchestration log**: One-line summary per audit — "Post-phase audit cycle 1: 4 gaps (3 critical, 1 minor) in 82s"
3. **Debug log**: Full audit prompt and raw LLM response written to `wt/orchestration/audit-cycle-N.log` for post-mortem analysis

## Approach: HTML report integration

New `render_audit_section()` in `reporter.sh`, called from `generate_report()` between execution and coverage sections. Structure:

```html
<h2>Post-Phase Audit</h2>
<!-- Per cycle -->
<h3>Phase 1 Audit</h3>
<p>Result: gaps_found | Model: sonnet | Duration: 82s</p>
<table>
  <tr><th>ID</th><th>Severity</th><th>Description</th><th>Spec Reference</th><th>Suggested Scope</th></tr>
  <tr class="gap-critical"><td>GAP-1</td>...</tr>
</table>
```

CSS classes: `.gap-critical { background: #4e2a2a; }`, `.gap-minor { background: #3a3a2a; }`, `.audit-clean { color: #4caf50; }`

## Approach: Web dashboard AuditPanel

New `web/src/components/AuditPanel.tsx` component. Reads `phase_audit_results[]` from state.json (already polled by Dashboard). Shows:

1. **Summary bar**: "Phase 1: 4 gaps (3 critical)" with color-coded badge
2. **Gap table**: Sortable by severity, with spec reference, suggested scope
3. **Clean state**: Green "All spec sections covered" message
4. **Multiple phases**: Accordion/tabs if >1 audit result

Integrates into Dashboard.tsx after ChangeTable, before LogPanel. Only renders if `phase_audit_results` exists and is non-empty.

## Approach: Prompt template via set-orch-core

The audit prompt is built via `set-orch-core template audit --input-file -` (same pattern as review/plan/fix prompts). New `render_audit_prompt()` function in `lib/set_orch/templates.py` + CLI registration in `lib/set_orch/cli.py` (same pattern as `render_planning_prompt` → `cmd_template` dispatch). Template receives JSON with:
- `spec_text` or `requirements` (depending on mode)
- `changes[]` with name, scope, status, file_list
- `coverage` (if digest mode)

This keeps the prompt externalized and consistent with other orchestrator templates. No Jinja2 — pure Python f-strings like all existing templates.
