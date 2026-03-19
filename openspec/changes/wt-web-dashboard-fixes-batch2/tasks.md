# Tasks: wt-web Dashboard Fixes Batch 2

All tasks already implemented and committed.

## 1. Digest expand index keys
- [x] 1.1 Change OverviewPanel expandedReqs from `Set<string>` to `Set<number>`
- [x] 1.2 Change RequirementsPanel expandedReqs from `Set<string>` to `Set<number>`
- [x] 1.3 Use array index for React key and toggle instead of `r.id`

## 2. Coverage skip_merged fix
- [x] 2.1 Add `update_coverage_status(change_name, "merged")` to merger.py Case 1 (branch deleted)
- [x] 2.2 Add `update_coverage_status(change_name, "merged")` to merger.py Case 2 (ancestor of HEAD)

## 3. Progress bar covered vs merged
- [x] 3.1 Dual-layer bar: grey for covered, blue for merged
- [x] 3.2 Label shows "X/Y merged"

## 4. Claude session path mangling
- [x] 4.1 Create `_claude_mangle()` helper in api.py
- [x] 4.2 Replace all 7 inline mangling sites with helper

## 5. Per-change sessions
- [x] 5.1 Add `change` prop to SessionPanel
- [x] 5.2 Pass `selectedChange` from Dashboard to SessionPanel
- [x] 5.3 Update api.ts `getProjectSessions` and `getProjectSession` to support change param
- [x] 5.4 Reset session state when change switches

## 6. Gate critical handling
- [x] 6.1 Add "critical" to GateBar `statusStyle`
- [x] 6.2 Add "critical" to GateDetail `resultStyle`
- [x] 6.3 Include "critical" in `firstFail` auto-expand check
- [x] 6.4 Add "skip_merged" to GateBar `statusStyle`

## 7. Expand All / Collapse buttons
- [x] 7.1 Replace triangle characters with text buttons in OverviewPanel
- [x] 7.2 Replace triangle characters with text buttons in RequirementsPanel

## Commits

| Commit | Description |
|--------|-------------|
| `b23021ecb` | Digest expand index keys + coverage skip_merged |
| `e6e6d6a46` | Progress bar covered vs merged + planned color |
| `e69b7a8e6` | Session path mangling fix |
| `1b91b90b2` | Per-change sessions in Sessions tab |
| `d45543feb` | GateDetail critical auto-expand |
| `de01cac62` | GateBar critical + skip_merged colors |
