## Why

The OpenSpec skill-based workflow (archive, continue, ff, apply, new) currently does not build developer memory. Every decision, error, and pattern discovered during a change is lost after archiving. Shodh-Memory is a local, offline Rust binary that provides cognitive memory via REST API — integrating it lets the LLM automatically remember and recall past experience as part of the normal workflow, with zero manual effort.

## What Changes

- New `set-memory` bash CLI helper that wraps the Shodh-Memory REST API with graceful degradation (silent no-op when shodh-memory is not running)
- All 5 core OpenSpec skills gain automatic memory steps:
  - **new**: recalls related past work before starting
  - **continue**: recalls relevant experience before creating artifacts
  - **ff**: recalls past experience before artifact creation loop
  - **apply**: recalls patterns/errors before implementing; remembers errors, patterns, and completion events after
  - **archive**: remembers decisions, learnings, and completion events
- `install.sh` updated to include `set-memory` in the installed scripts

## Capabilities

### New Capabilities
- `memory-cli`: Bash CLI helper (`set-memory`) for Shodh-Memory REST API — health check, remember, recall, status commands with graceful degradation
- `skill-memory-hooks`: Automatic memory recall/remember steps woven into the 5 core OpenSpec SKILL.md files

### Modified Capabilities

## Impact

- **Files added**: `bin/set-memory`
- **Files modified**: 5 SKILL.md files (archive, continue, ff, apply, new), `install.sh`
- **Dependencies**: `curl`, `jq` (already prerequisites); `shodh-memory` is optional (graceful degradation)
- **No breaking changes**: All memory steps are conditional on `set-memory health` — existing workflows are unaffected when shodh-memory is not installed
