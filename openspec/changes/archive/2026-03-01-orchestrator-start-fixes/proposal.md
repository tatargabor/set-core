# Proposal: orchestrator-start-fixes

## Why

The orchestrator has 3 bugs that prevent reliable start with `--spec`:
1. `default_model` directive is not parsed → changes run on opus instead of the requested model (wastes money)
2. Sentinel agent restart command doesn't pass `$ARGUMENTS` → restarts lose `--spec` flag
3. `done` state + stale plan = 0 changes instant exit (already partially fixed by auto-plan, but `default_model` missing from resolve output)

## What Changes

- Add `default_model` to `resolve_directives()` case statement and JSON output in `bin/set-orchestrate`
- Fix sentinel.md restart command to include `$ARGUMENTS`
- Verify auto-plan fix works end-to-end

## Capabilities

- **directive-default-model**: Parse and propagate `default_model` directive
- **sentinel-restart-args**: Preserve CLI arguments across sentinel restarts

## Impact

- `bin/set-orchestrate` — directive parser + JSON output
- `.claude/commands/wt/sentinel.md` — restart command
