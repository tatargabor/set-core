# Proposal: set-web Dashboard Fixes Batch 2

## Problem

Multiple set-web dashboard issues discovered during craftbrew E2E runs:

1. **Digest expand broken on duplicate req IDs** — clicking one row toggles all rows with the same ID because state keyed by `r.id` not array index
2. **Coverage not updated on skip_merged** — merger.py Case 1 & 2 (branch already merged) skip `update_coverage_status()`, leaving reqs stuck at "planned"
3. **Progress bar misleading** — shows done/total but doesn't distinguish covered vs merged
4. **Session path mangling wrong** — Claude CLI replaces `.` with `-` in project dirs, our code was replacing `/` only
5. **Sessions tab project-only** — no way to see per-change agent sessions
6. **GateBar/GateDetail ignore "critical"** — review gate returns "critical" but UI only knows pass/fail/skip
7. **SC badge shows but detail empty** — spec_coverage_result=timeout shown as badge but no output to display

## Solution

All fixes are already implemented and committed (session work). This change documents them retroactively.

## Scope

- `web/src/components/DigestView.tsx` — index-based expand, progress bar
- `web/src/components/GateBar.tsx` — critical + skip_merged styles
- `web/src/components/GateDetail.tsx` — critical auto-expand
- `web/src/components/SessionPanel.tsx` — per-change sessions
- `web/src/pages/Dashboard.tsx` — pass selectedChange to SessionPanel
- `web/src/lib/api.ts` — change-aware session API wrappers, mangling fix
- `lib/set_orch/api.py` — `_claude_mangle()` helper
- `lib/set_orch/merger.py` — coverage update in skip_merged paths
