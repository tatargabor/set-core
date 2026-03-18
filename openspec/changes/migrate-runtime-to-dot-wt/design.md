# Design: migrate-runtime-to-dot-wt

## Context

The `sentinel-tab` change introduces `.wt/sentinel/` as the first user of the `.wt/` runtime directory convention. This change completes the migration by moving all other runtime files into `.wt/`.

### Current file locations
```
.claude/loop-state.json              → .wt/agent/loop-state.json
.claude/activity.json                → .wt/agent/activity.json
.claude/ralph-terminal.pid           → .wt/agent/ralph-terminal.pid
.claude/sentinel.pid                 → .wt/agent/sentinel.pid
.claude/scheduled_tasks.lock         → .wt/agent/scheduled_tasks.lock
.claude/reflection.md                → .wt/agent/reflection.md
.claude/orchestration.log            → .wt/logs/orchestration.log
.claude/logs/ralph-iter-*.log        → .wt/logs/ralph-iter-*.log
orchestration-events.jsonl           → .wt/orchestration/events.jsonl
wt/orchestration/orchestration-state.json → .wt/orchestration/state.json
wt/orchestration/plans/              → .wt/orchestration/plans/
wt/orchestration/runs/               → .wt/orchestration/runs/
wt/orchestration/spec-coverage-report.md → .wt/orchestration/spec-coverage-report.md
.wt-tools/.saved-codemaps            → .wt/cache/codemaps/
.wt-tools/.saved-designs             → .wt/cache/designs/
.wt-tools/.last-memory-commit        → .wt/cache/last-memory-commit
.wt-tools/agents/*.skill             → .wt/cache/skill-invocations/
design-snapshot.md                   → .wt/design-snapshot.md
.claude/.wt-version                  → .wt/version
```

## Goals / Non-Goals

**Goals:**
- Single `.wt/` directory for all runtime data
- Centralized path resolution (no hardcoded paths scattered across codebase)
- Simple `.gitignore` (one line: `/.wt/`)
- Clean separation: `.claude/` = config, `wt/` = config+artifacts, `.wt/` = runtime

**Non-Goals:**
- Changing runtime file formats or behavior
- Supporting old and new paths simultaneously long-term (clean cutover, not dual-write)
- Backward compatibility with projects that haven't been re-initialized

## Decisions

### 1. Python WtDirs class for path resolution

**Decision:** Centralized `WtDirs` class in `lib/wt_orch/paths.py`.

```python
class WtDirs:
    def __init__(self, project_path: str):
        self.root = os.path.join(project_path, ".wt")

    @property
    def state_file(self): return os.path.join(self.root, "orchestration", "state.json")

    @property
    def events_file(self): return os.path.join(self.root, "orchestration", "events.jsonl")

    # ... etc for all runtime paths
```

**Why a class not constants?** Paths are project-relative. Different callers have different project roots (main repo vs worktree). A class parameterized by project_path handles this cleanly.

### 2. Bash helper for shell scripts

**Decision:** `bin/wt-paths` sourceable script exporting `$WT_STATE_FILE`, `$WT_EVENTS_FILE`, etc.

```bash
source "$(dirname "$0")/wt-paths"
# Now $WT_STATE_FILE etc. are available
```

**Why not just hardcode `.wt/...`?** Single source of truth. If the convention ever changes, one file update fixes all bash scripts.

### 3. Clean cutover, no dual-write

**Decision:** After migration, old paths are not supported. `wt-project init` creates the new structure. Projects must re-run `wt-project init`.

**Why not a transition period?** Dual-write doubles the complexity and bug surface. The sentinel-tab change already establishes `.wt/` — by the time this change ships, `.wt/` is a known convention. A clean `wt-project init` is the standard deploy mechanism.

### 4. Auto-migration in wt-project init

**Decision:** `wt-project init` detects old-style paths and moves files to `.wt/` automatically.

```bash
# If old state file exists and new doesn't, migrate
if [ -f "wt/orchestration/orchestration-state.json" ] && [ ! -f ".wt/orchestration/state.json" ]; then
    mkdir -p .wt/orchestration
    mv wt/orchestration/orchestration-state.json .wt/orchestration/state.json
fi
```

This ensures existing projects are migrated smoothly on the next `wt-project init`.

## Risks / Trade-offs

- **[Risk] Many files reference old paths** → Mitigation: systematic grep + replace. The WtDirs class prevents future drift.
- **[Risk] Running orchestration during migration** → Mitigation: migration happens during `wt-project init` which requires no running processes.
- **[Risk] Worktrees with old paths** → Mitigation: `bootstrap_worktree()` creates `.wt/` structure. `sync_worktrees` step in deploy copies new files.
- **[Risk] MCP server hardcoded paths** → Mitigation: MCP server imports WtDirs and resolves paths dynamically.

## Migration checklist (files to update)

### Python (import WtDirs, replace hardcoded paths):
- `lib/wt_orch/engine.py` — state.json, events.jsonl, plans/
- `lib/wt_orch/dispatcher.py` — state.json, worktree bootstrap
- `lib/wt_orch/verifier.py` — spec-coverage-report.md
- `lib/wt_orch/merger.py` — state.json
- `lib/wt_orch/planner.py` — plans/, state.json
- `lib/wt_orch/api.py` — all state reads
- `lib/wt_orch/websocket.py` — state.json watch
- `lib/wt_orch/chat.py` — project path resolution
- `mcp-server/wt_mcp_server.py` — state reads, activity reads

### Bash (source wt-paths):
- `bin/wt-sentinel` — state.json, events.jsonl, sentinel.pid
- `bin/wt-loop` — loop-state.json, activity.json, reflection.md
- `bin/wt-new` — bootstrap worktree
- `bin/wt-merge` — state.json, generated file patterns
- `lib/orchestration/*.sh` — various state references

### Skills/prompts (update path references):
- `.claude/commands/wt/sentinel.md`
- `.claude/skills/wt/*/SKILL.md` — any that reference .claude/ runtime files
- `.claude/hooks/*.sh` — any that read runtime state

### Deploy:
- `lib/project/deploy.sh` — create .wt/ structure, auto-migrate old paths
- `lib/wt_orch/dispatcher.py::bootstrap_worktree()` — create .wt/ in worktrees
