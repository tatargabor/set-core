## Why

The orchestrator's `--spec` flag requires an explicit file path every time (`wt-orchestrate --spec docs/v8.md plan`). There's no standard location for spec documents, no way to list or manage them, and completed specs stay mixed with active ones. The new `wt/orchestration/specs/` directory (from wt-directory-convention) provides a home, but the orchestrator doesn't yet know about it.

## What Changes

- `find_input()` gains spec resolution: `--spec v12` resolves to `wt/orchestration/specs/v12.md` if the literal path doesn't exist
- New `wt-orchestrate specs` subcommand: list, show, archive spec documents from `wt/orchestration/specs/`
- `wt-project migrate` gains spec migration: moves `docs/v*.md` to `wt/orchestration/specs/archive/`
- Plan and run log metadata links back to source spec for traceability

## Capabilities

### New Capabilities
- `spec-resolution`: Short-name spec resolution in `--spec` flag — checks `wt/orchestration/specs/` before failing, enabling `--spec v12` instead of `--spec wt/orchestration/specs/v12.md`
- `spec-management`: `wt-orchestrate specs` subcommand for listing specs (name, status, location), showing spec content, and archiving completed specs to `archive/`

### Modified Capabilities
- `orchestration-config`: `find_input()` gains wt/ spec lookup as a resolution step between explicit path and brief auto-detect

## Impact

- **bin/wt-orchestrate**: New `specs` subcommand in case dispatch
- **lib/orchestration/state.sh**: `find_input()` gains wt/ spec resolution step
- **bin/wt-project**: `cmd_migrate()` gains `docs/v*.md` → `wt/orchestration/specs/archive/` migration
- **Consumer projects**: Spec documents can be organized in `wt/orchestration/specs/` with short-name access
