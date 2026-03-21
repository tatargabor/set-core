# Proposal: Runtime Directory Cleanup

## Why

The shared data directory (`~/.local/share/set-core/`) mixes runtime directories (logs, screenshots, cache, sentinel) with non-runtime directories (e2e-runs, memory, metrics). Runtime dirs are named after projects (`craftbrew-run7/`, `set-core/`) and sit alongside `e2e-runs/`, `memory/`, etc. — making it impossible to tell what's a runtime dir and what's a meta dir. This also pollutes the top level as more projects are added.

## What Changes

Move all per-project runtime directories under a `runtime/` subdirectory:

```
BEFORE:                              AFTER:
~/.local/share/set-core/             ~/.local/share/set-core/
├── craftbrew-run7/   (runtime)      ├── runtime/
├── set-core/         (runtime)      │   ├── craftbrew-run7/
├── _global/          (runtime)      │   ├── set-core/
├── e2e-runs/         (projects)     │   └── _global/
├── memory/                          ├── e2e-runs/
└── metrics/                         ├── memory/
                                     └── metrics/
```

Two critical changes drive everything:
1. `paths.py:92` — `SetRuntime.root` adds `runtime/` between base and project name
2. `bin/set-paths:39` — `WT_RUNTIME_DIR` bash equivalent gets same change

All Python code using `SetRuntime` properties updates automatically. Shell scripts using `set-paths` variables update automatically. Only hardcoded path references need manual fixes.

## Capabilities

### Modified Capabilities
- `runtime-directory-convention`: Runtime root gains `runtime/` subdirectory
- `deploy-flow`: Migration of existing runtime dirs on first run

## Risk

**Low-Medium**. The `SetRuntime` class centralizes all runtime paths — changing its root cascades to 14+ Python files automatically. Manual fixes needed only in shell scripts with hardcoded paths and the watcher. Backward compat fallback reads from old location if new doesn't exist.

## Scope

### In Scope
- `SetRuntime.root` path change (paths.py)
- `WT_RUNTIME_DIR` path change (set-paths)
- Watcher hardcoded path fix (use SetRuntime)
- Shell script hardcoded path fixes (set-sentinel, set-orchestrate, set-cleanup)
- Auto-migration on first access (move old → new)
- Test updates (test_paths.py)
- Backward compat fallback

### Out of Scope
- Memory directory restructuring (stays at `~/.local/share/set-core/memory/`)
- E2E runs directory changes (stays at `e2e-runs/`)
- Metrics directory changes
- projects.json format changes
