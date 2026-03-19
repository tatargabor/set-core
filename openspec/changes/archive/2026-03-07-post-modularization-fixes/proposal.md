## Why

The modularization effort (completed 2026-03-07) split 7 monolithic scripts into 25+ focused modules. A thorough code review of the extracted modules revealed 51 issues: 7 critical bugs, 27 warnings, and 17 suggestions. Several of these are data-loss or silent-failure bugs that existed in the monoliths but are now clearly visible in the isolated modules. Fixing them now prevents production regressions and improves reliability.

## What Changes

- Fix `_stop_raw_filter` heredoc bug — transcript extraction currently saves zero memories on every session end (data loss)
- Add missing `cmd_repair` function that is dispatched but never defined
- Fix `cmd_seed` duplicate detection (wrong `--query` flag → positional arg)
- Fix orchestration scope bugs: `parse_directives` called without argument, `$PROJECT_PATH` undefined, smoke variables local-scoped but used cross-function
- Fix `allowedTools` permission mode: string-based flag return + unquoted expansion breaks `claude` CLI invocation
- Fix JSON injection in `init_loop_state` (unescaped `label`/`change` fields)
- Remove debug `warn` left in production `check_done`
- Fix `run_with_lock` missing on `cmd_projects` RocksDB access
- Fix bare `python3` usage instead of `$SHODH_PYTHON`
- Add missing dependency declarations in module headers
- Fix `deploy.sh` hidden coupling (calls functions defined in caller `set-project`)
- Fix `_save_project_type` basename lookup vs custom `--name`

## Capabilities

### New Capabilities

(none)

### Modified Capabilities

(none — these are bug fixes in existing modules, no spec-level behavior changes)

## Impact

- **lib/hooks/stop.sh** — transcript extraction fix (most critical, data loss)
- **lib/memory/** — core.sh, maintenance.sh, ui.sh, sync.sh fixes
- **lib/orchestration/** — dispatcher.sh, merger.sh, verifier.sh scope fixes
- **lib/loop/** — engine.sh, state.sh, tasks.sh, prompt.sh fixes
- **lib/editor.sh** — permission flag return convention
- **lib/project/deploy.sh** + **bin/set-project** — coupling and lookup fixes
- **bin/set-memory** — missing cmd_repair dispatch target
