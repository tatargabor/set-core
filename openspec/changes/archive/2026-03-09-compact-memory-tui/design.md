## Context

The current `set-memory tui` is a single-column 66-character ANSI dashboard that shows globally aggregated metrics across all projects. With 81 projects and 514 sessions in the DB, the global view is noisy and unhelpful. Users work in one project at a time and need project-scoped metrics.

The terminal width is typically 160+ columns but the current layout only uses 66. The vertical space is ~30 lines, well within 80 rows.

### Current flow
```
cmd_tui() → inline Python → query_report(since_days) → format single column → print
```
No project filtering exists in `query_report()`. The `sessions` table has a `project` column with an index.

## Goals / Non-Goals

**Goals:**
- Per-project filtering in `query_report()` using prefix match (project + worktrees)
- 3-column ANSI layout fitting 160×80 terminals
- Auto-detect project from CWD when no `--project` flag
- Recent sessions panel with per-session drill-down
- Backward compatible — no `--project` flag = current global behavior (for `metrics` command)

**Non-Goals:**
- Textual/rich TUI framework migration — stays pure ANSI
- Interactive session selection or drill-down navigation
- Cross-project comparison view
- Memory content browsing (that's `set-memory list/recall`)

## Decisions

### D1: Prefix match for project filtering
**Decision**: Use SQL `LIKE 'project%'` to match both the main project and its worktree sessions.
**Rationale**: Worktree projects are named `<project>-wt-<change>`. A prefix match on the base project name captures all related sessions. Exact match would miss worktree data which is the majority of orchestration activity.
**Alternative considered**: Regex or explicit worktree list — over-engineering for this use case.

### D2: 3-column layout with fixed proportions
**Decision**: Left (DB+usage, ~50 chars), Center (hook overhead+layers+trend, ~50 chars), Right (sessions list, ~56 chars). Total ~160 including separators.
**Rationale**: These three logical groups are independent and scan naturally left-to-right: "what's in the DB" → "how are hooks performing" → "what happened recently".
**Alternative considered**: 2-column — doesn't fit sessions list comfortably.

### D3: Session list shows worktree suffix, not full project name
**Decision**: Strip the base project prefix from session project names. `sales-raketa-wt-smoke-tests` → `wt-smoke-tests`. Main repo sessions show as `(main)`.
**Rationale**: In project-scoped view, the common prefix is redundant. The worktree change name is the differentiator.

### D4: Auto-detect project in tui, explicit in metrics
**Decision**: `set-memory tui` auto-detects project from CWD (git root basename). `set-memory metrics` keeps current global behavior unless `--project` is passed.
**Rationale**: TUI is always used interactively from a project dir. Metrics may be used for cross-project analysis.

### D5: Terminal width detection
**Decision**: Use `os.get_terminal_size()` with fallback to 160. If terminal < 120, fall back to current single-column layout.
**Rationale**: Graceful degradation for narrow terminals without breaking existing behavior.

## Risks / Trade-offs

- [Prefix match false positives] Projects like `foo` would match `foobar`. → Mitigated by convention: project names are unique enough (e.g., `sales-raketa` won't prefix-collide).
- [Inline Python complexity] The 3-column layout is more complex inline Python in bash. → Acceptable — the current TUI is already 180 lines of inline Python. Could extract to a file later if needed.
- [Session list truncation] Long worktree names need truncation. → Use `..` suffix, keep to 22 chars max.
