# Design: wt-web Dashboard Fixes Batch 2

## Approach

All fixes are surgical — minimal changes to existing components, no new abstractions.

### 1. Index-based expand state
Replace `Set<string>` (keyed by `r.id`) with `Set<number>` (keyed by array index) in both OverviewPanel and RequirementsPanel. Handles duplicate req IDs correctly.

### 2. Coverage update on skip_merged
Add `update_coverage_status(change_name, "merged")` to merger.py Case 1 (branch deleted) and Case 2 (ancestor of HEAD). Previously only Case 3 (normal merge) updated coverage.

### 3. Dual-layer progress bar
Show grey bar for covered count, blue overlay for merged count. Label says "X/Y merged".

### 4. Claude path mangling
Extract `_claude_mangle()` helper: `path.lstrip("/").replace("/", "-").replace(".", "-")`. Replace all 7 inline mangling sites.

### 5. Per-change sessions
SessionPanel accepts optional `change` prop. When set, fetches from `/changes/{name}/sessions` and `/changes/{name}/session` endpoints instead of project-level.

### 6. Critical gate handling
Add "critical" to `statusStyle` (GateBar) and `resultStyle` (GateDetail). Include in `firstFail` detection for auto-expand.

## Risks
None — all changes are backward-compatible. Unknown gate results fall back to neutral styling.
