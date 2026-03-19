## Context

The modularization (Phase 1-6) split 7 monolithic bash scripts into 25+ focused lib/ modules. A post-extraction code review found 51 issues across all modules — 7 critical, 27 warnings, 17 suggestions. These are pure bug fixes; no architectural changes.

## Goals / Non-Goals

**Goals:**
- Fix all 7 critical bugs (data loss, undefined functions, broken CLI flags)
- Fix high-priority warnings (scope bugs, JSON injection, missing locks)
- Add missing dependency comments to module headers
- Remove debug artifacts left from extraction

**Non-Goals:**
- Refactoring or further modularization
- New features or behavior changes
- Performance optimization
- Fixing pre-existing design issues that aren't bugs (e.g., the string-based metric append argument ordering is confusing but functionally correct)

## Decisions

### D1: stop.sh heredoc fix — use environment variable

The `_stop_raw_filter` passes transcript path via heredoc but Python reads `sys.argv[1]` (never set). Fix: pass path via environment variable inside the heredoc, matching patterns already used elsewhere in the codebase (`_SHODH_STORAGE`, `_SHODH_TOPIC`).

### D2: allowedTools flag — use eval for now

The `get_claude_permission_flags` returns a string like `--allowedTools "Edit,Write,..."`. Callers expand it unquoted. Full array-based fix would require changing the interface across 3+ callers. Pragmatic fix: use `eval` at the call site (the value is fully controlled, not user input), and add a TODO for array migration.

### D3: orchestration scope bugs — read from STATE_FILENAME

Variables like `smoke_command`, `directives`, `PROJECT_PATH` are local to `monitor_loop` but used in cross-function calls. Fix: read from the persisted `STATE_FILENAME` JSON at point of use, matching the pattern already used for `post_merge_command`. This eliminates the scope problem entirely.

### D4: deploy.sh coupling — move functions into deploy.sh

`_register_mcp_server` and `_cleanup_deprecated_memory_refs` are called from `deploy.sh` but defined in `set-project`. Move them into `deploy.sh` to make it self-contained. `set-project` can still call them (they'll be sourced from deploy.sh).

### D5: Task grouping — fix by module, not by severity

Group tasks by module (memory, hooks, orchestration, loop, project) rather than by severity. Each module's fixes can be tested independently, and this matches the source tree structure.

## Risks / Trade-offs

- [Risk] `eval` for allowedTools flag → Mitigation: value is hardcoded in `editor.sh`, never from user input. Add comment explaining safety.
- [Risk] Moving functions into deploy.sh may break existing sourcing → Mitigation: functions are only called from deploy.sh and set-project; after move, set-project sources deploy.sh first, so all callers still see the functions.
- [Risk] Reading from STATE_FILENAME in orchestration adds jq calls → Mitigation: these are infrequent paths (merge, smoke fix), not hot loops. Negligible performance impact.
