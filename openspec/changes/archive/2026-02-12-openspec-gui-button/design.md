## Context

The Control Center GUI renders a project header row per project with buttons for memory [M], team filter, and chat. Currently `get_memory_status()` runs `set-memory status --json` as a synchronous subprocess on the UI thread during every table rebuild (every 2 seconds). Adding an OpenSpec [O] button with similar detection would compound this to ~870ms+ of UI blocking per project per cycle.

Existing worker pattern: `StatusWorker`, `UsageWorker`, `TeamWorker`, `ChatWorker` — all `QThread` subclasses in `gui/workers/`, emitting signals when new data is available.

## Goals / Non-Goals

**Goals:**
- [O] button in project header for OpenSpec visibility
- `wt-openspec` CLI for init, update, and fast JSON status
- FeatureWorker to move all per-project feature detection off the UI thread
- Existing [M] button reads from same cache (performance fix)

**Non-Goals:**
- OpenSpec dashboard/browse dialog (future change)
- Memory hook patching after update (separate change: `shodh-openspec-hooks`)
- Changing the StatusWorker or its 2-second refresh interval

## Decisions

### Decision 1: Filesystem-based OpenSpec detection (not CLI)

`wt-openspec status --json` SHALL check `openspec/config.yaml` existence and count `openspec/changes/*/` directories directly via filesystem, not by calling `openspec list --json` (~800ms). This keeps status under 10ms.

**Alternative**: Call `openspec list --json` — rejected due to ~800ms latency per project.

### Decision 2: Single FeatureWorker for all per-project features

One `FeatureWorker` polls both memory status AND openspec status per project, emitting a combined dict. This avoids spawning separate workers per feature.

**Alternative**: Separate MemoryWorker + OpenSpecWorker — rejected, unnecessary thread overhead for two lightweight checks.

### Decision 3: FeatureWorker receives project list from StatusWorker data

The FeatureWorker needs to know which projects exist and their main repo paths. Rather than discovering this independently, it receives the project list from the latest `status_updated` data (which already contains project names and worktree paths). The main window passes this when wiring signals.

**Alternative**: FeatureWorker reads `projects.json` directly — rejected, would duplicate project discovery logic.

### Decision 4: wt-openspec CLI as thin bash wrapper

Same pattern as `set-memory`: a bash script in `bin/` that wraps the `openspec` npm CLI. The `status` subcommand uses pure bash/filesystem checks for speed; `init` and `update` delegate to `openspec` CLI.

### Decision 5: [O] button placement — after [M], before team filter

Button order: `[project name] ... [M] [O] [team] [chat]`. OpenSpec is a project-level dev tool, logically grouped near memory.

## Risks / Trade-offs

- **[Risk] FeatureWorker 15s interval means stale data for up to 15s** → Acceptable. Feature status rarely changes. Manual refresh after init/update covers the action case.
- **[Risk] `openspec` CLI not installed** → `wt-openspec init` will fail gracefully with "openspec CLI not found" message. `wt-openspec status` filesystem checks don't need the CLI.
- **[Risk] Refactoring get_memory_status to use cache may break tests** → Update test_29_memory.py to mock `_feature_cache` instead of `get_memory_status`.
