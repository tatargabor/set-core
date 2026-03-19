## Context

The `set-memory` CLI wrapper and shodh-memory Python library are already installed and working. The CLI currently uses a single global storage directory. The 5 core OpenSpec SKILL.md files lack memory hooks, so remember/recall never fires automatically. The Control Center GUI has no visibility into memory. The project header currently ignores right-clicks (returns early at `menus.py:143`).

shodh-memory is a Python library (not a server) — `Memory(storage_path=...)` creates an embedded database, operations are synchronous file I/O, no daemon or background process needed.

## Goals / Non-Goals

**Goals:**
- Per-project memory isolation via auto-detected storage paths
- Memory indicator [M] button in project header, following existing [team filter] [chat] pattern
- Project header context menu (new) with Memory submenu
- Browse and remember dialogs accessible from GUI
- SKILL.md hook detection warning in GUI
- Complete the SKILL.md modifications from the original change (5 files)

**Non-Goals:**
- Memory management (delete/edit individual memories) — future work
- Cross-project recall UI — future work
- Auto-migration of legacy global storage — coexists as `_legacy`
- Real-time memory change notifications — on-demand queries only

## Decisions

### Decision 1: Per-project storage via git root basename
**Choice**: Use `basename $(git rev-parse --show-toplevel)` to determine project name, creating `~/.local/share/set-core/memory/<project>/` directories.

**Rationale**: Tested that shodh-memory `Memory(storage_path=...)` creates fully isolated instances — no cross-talk between paths. Git root detection works identically from any worktree of the same repo (worktrees share the same git root name). Zero configuration needed.

**Alternative considered**: Global storage with tag-based filtering — rejected because semantic search would return cross-project noise (e.g., PySide6 memories from project A polluting project B recalls).

### Decision 2: [M] button in project header row (not worktree rows)
**Choice**: Place the memory indicator at project level in the header widget, not per-row in the Extra column.

**Rationale**: Memory is project-scoped (all worktrees of the same repo share one memory store). Placing it per-row would be redundant and misleading. The project header already has the [team filter] and [chat] button pattern, so [M] fits naturally. More horizontal space available in the header.

### Decision 3: New project header context menu
**Choice**: Add a `show_project_header_context_menu` method that triggers when right-clicking on header rows (currently silently returns at `menus.py:143`).

**Rationale**: The header row is wasted interactive surface. Team Chat and Team Settings are currently only accessible via row-level context menu (confusing — they're project-level concepts). The new menu groups project-level actions properly.

### Decision 4: On-demand memory queries (no background worker)
**Choice**: Memory status is checked during table refresh (synchronous Python subprocess), not via a dedicated background worker.

**Rationale**: shodh-memory operations are fast (embedded DB, local files). A `get_stats()` call takes <50ms. No need for a separate worker thread — can query inline during `_create_project_header`. If it becomes slow with thousands of memories, we can add caching later.

**Alternative considered**: MemoryWorker polling on timer — rejected as over-engineering for a <50ms operation.

### Decision 5: SKILL.md hooks call CLI directly, no separate health check
**Choice**: SKILL.md memory steps call `set-memory recall/remember` directly without a preceding `set-memory health` gate. The CLI itself already performs a health check inside every command and degrades gracefully.

**Rationale**: The original spec called for `set-memory health && set-memory recall ...` which causes two Python subprocess invocations (double health check). Since every CLI command already health-checks internally and returns `[]` or exits 0 on failure, the SKILL.md only needs the direct call. Simpler instructions, less latency.

**Reuse note**: The `skill-memory-hooks` spec from the original `shodh-memory-integration` change is correct for what-to-save (decisions, errors, patterns, events). The how (health gating) is simplified per this decision.

## Risks / Trade-offs

- **[Python subprocess overhead]** Each `get_stats()` check spawns a Python subprocess during table refresh. Mitigation: one call per project (not per worktree), <50ms each. Cache result for the refresh cycle.
- **[SKILL.md fragility]** Memory hooks in SKILL.md are soft instructions — the LLM might skip them under context pressure. Mitigation: place recall early and remember late in each skill flow, keep instructions concise.
- **[Legacy storage confusion]** Users with existing global memories won't see them automatically in per-project view. Mitigation: `set-memory status` shows both legacy and project storage; `_legacy` project name accessible via `--project _legacy`.
