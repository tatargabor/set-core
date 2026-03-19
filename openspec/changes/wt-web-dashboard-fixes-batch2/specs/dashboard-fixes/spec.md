# Spec: wt-web Dashboard Fixes Batch 2

## Requirements

### REQ-1: Digest expand handles duplicate IDs
Expand/collapse state uses array index instead of requirement ID. Multiple rows with the same ID can be independently toggled.

### REQ-2: Coverage updated on skip_merged merges
`update_coverage_status()` is called in all merge paths (Case 1: branch deleted, Case 2: ancestor, Case 3: normal merge).

### REQ-3: Progress bar shows covered vs merged
Dual-layer bar: grey for covered count, blue overlay for merged. Label shows "X/Y merged".

### REQ-4: Claude session path mangling correct
`_claude_mangle()` replaces both `/` → `-` and `.` → `-`, matching Claude CLI behavior. All 7 mangling sites use the helper.

### REQ-5: Sessions tab shows per-change sessions
When a change is selected, Sessions tab shows that change's agent sessions. Resets on change switch.

### REQ-6: Gate UI handles "critical" result
GateBar shows red badge for "critical". GateDetail auto-expands critical gates and shows review output.

### REQ-7: Expand All / Collapse buttons visible
Buttons have text labels, background color, and hover state instead of barely-visible triangle characters.
