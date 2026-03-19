## Why

OpenSpec artifacts save ~25-30% tokens per change by providing structured context instead of letting agents explore freely. However, the orchestrator does not enforce their existence — agents can be dispatched without complete artifacts, and merged changes are never auto-archived. This means stale changes accumulate in `openspec/changes/` and delta specs are not synced back to main specs, gradually degrading the spec corpus that future plans depend on.

## What Changes

- **Pre-dispatch artifact validation**: Before dispatching an agent, the orchestrator checks whether the change has a `tasks.md`. If not, the first iteration is forced to `/opsx:ff` (artifact creation). If `tasks.md` exists but is outdated relative to code changes, emit a warning.
- **Auto-archive merged changes**: After a successful merge, the orchestrator archives the change directory from `openspec/changes/<name>/` to `openspec/changes/archive/<date>-<name>/`. Delta spec sync is attempted best-effort (non-blocking).
- **Stale change detection**: At orchestration start, warn about changes in `openspec/changes/` that have no matching worktree or running agent (likely leftover from previous runs).

## Capabilities

### New Capabilities
- `openspec-auto-archive`: Automatic archiving of merged changes with best-effort delta spec sync

### Modified Capabilities
- `orchestration-engine`: Pre-dispatch artifact validation and stale change detection at startup

## Impact

- `bin/set-orchestrate`: `dispatch_change()` gains artifact check (~15 lines), `merge_change()` gains auto-archive call (~10 lines), `cmd_start()` gains stale change warning (~15 lines)
- No new dependencies — uses existing `openspec` CLI and filesystem operations
