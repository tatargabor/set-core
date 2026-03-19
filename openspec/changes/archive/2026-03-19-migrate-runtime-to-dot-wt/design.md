# Design: migrate-runtime-to-dot-wt

## Context

Runtime files are scattered across `.claude/`, project root, `wt/orchestration/`, `.wt-tools/`, and `.wt/sentinel/`. The memory system and metrics already use `~/.local/share/wt-tools/<project>/` — this change migrates all shared runtime there and keeps only minimal per-agent ephemeral files in worktrees.

### Current → Target migration table

```
SHARED RUNTIME → ~/.local/share/wt-tools/<project>/
──────────────────────────────────────────────────────────────────────────
Current location                              Target location
──────────────────────────────────────────────────────────────────────────
wt/orchestration/orchestration-state.json     orchestration/state.json
orchestration-events.jsonl (root, legacy)     orchestration/events.jsonl
wt/orchestration/orchestration-state-events.jsonl  orchestration/events.jsonl
wt/orchestration/orchestration.log            logs/orchestration.log
.claude/orchestration.log (legacy)            logs/orchestration.log
wt/orchestration/plans/                       orchestration/plans/
wt/orchestration/runs/                        orchestration/runs/
wt/orchestration/digest/                      orchestration/digest/
wt/orchestration/spec-coverage-report.md      orchestration/spec-coverage-report.md
wt/orchestration/report.html                  orchestration/report.html
wt/orchestration/audit-cycle-*.log            orchestration/audit-cycle-*.log
wt/orchestration/logs/{change}/               logs/changes/{change}/
wt/orchestration/smoke-screenshots/{change}/  screenshots/smoke/{change}/
wt/orchestration/e2e-screenshots/cycle-*/     screenshots/e2e/cycle-*/
.wt/sentinel/events.jsonl                     sentinel/events.jsonl
.wt/sentinel/findings.json                    sentinel/findings.json
.wt/sentinel/status.json                      sentinel/status.json
.wt/sentinel/inbox.jsonl                      sentinel/inbox.jsonl
.wt/sentinel/inbox.cursor                     sentinel/inbox.cursor
.wt/sentinel/archive/                         sentinel/archive/
sentinel.pid (project root)                   sentinel/sentinel.pid
.wt-tools/.saved-codemaps                     cache/codemaps/
.wt-tools/.saved-designs                      cache/designs/
.wt-tools/.last-memory-commit                 cache/last-memory-commit
.wt-tools/agents/*.skill                      cache/skill-invocations/
.wt-tools/jira.json                           cache/credentials/jira.json
.wt-tools/confluence.json                     cache/credentials/confluence.json
design-snapshot.md (project root)             design-snapshot.md
.claude/.wt-version                           version

PER-WORKTREE AGENT EPHEMERAL → <worktree>/.wt/
──────────────────────────────────────────────────────────────────────────
.claude/loop-state.json                       loop-state.json
.claude/activity.json                         activity.json
.claude/ralph-terminal.pid                    ralph-terminal.pid
.claude/scheduled_tasks.lock                  scheduled_tasks.lock
.claude/reflection.md                         reflection.md
.claude/logs/ralph-iter-*.log                 logs/ralph-iter-*.log

STAYS AS-IS (not migrated)
──────────────────────────────────────────────────────────────────────────
wt/orchestration/specs/                       Config, user-provided, git-tracked
wt/orchestration/orchestration.yaml           Config, git-tracked
/tmp/wt-memoryd-<project>.sock                OS convention for daemon IPC
/tmp/wt-memoryd-<project>.pid                 OS convention for daemon PID
~/.local/share/wt-tools/memory/               Already correct
~/.local/share/wt-tools/metrics/              Already correct
~/.local/share/wt-tools/e2e-runs/             Already correct
```

## Goals / Non-Goals

**Goals:**
- `~/.local/share/wt-tools/<project>/` for all shared runtime (worktree-independent, branch-independent, merge-conflict-free)
- Minimal `<worktree>/.wt/` for per-agent ephemeral only (loop-state, activity, PID)
- Centralized path resolution (Python class + bash helper)
- Clean separation: `.claude/` = config, `wt/` = config+artifacts, `~/.local/share/` = runtime
- Worktree retention after merge (configurable)
- Simple `.gitignore` (remove many scattered patterns)

**Non-Goals:**
- Changing runtime file formats or behavior
- Supporting old and new paths simultaneously long-term (clean cutover)
- Backward compatibility with projects that haven't been re-initialized
- Changing `wt/orchestration/orchestration.yaml` or `wt/orchestration/specs/` (config, stays tracked)

## Decisions

### 1. Shared runtime goes to `~/.local/share/wt-tools/<project>/`

**Decision:** All runtime that is NOT per-agent-ephemeral goes to the XDG data directory, keyed by project name (git repo name, same as memory system).

**Why not `.wt/` in project root (original plan)?**
- `.wt/` in project root is per-worktree — each worktree clone gets its own copy
- Orchestration state is SHARED across worktrees — makes no sense per-worktree
- Worktree deletion destroys state — unacceptable for audit/debug
- Still needs `.gitignore` management
- Memory and metrics already established the `~/.local/share/` convention

**Project name resolution:** Same as memory system — uses `git rev-parse --show-toplevel` to get repo name, handles worktrees via `git rev-parse --git-common-dir`.

### 2. Per-worktree ephemeral stays in `<worktree>/.wt/`

**Decision:** Only `loop-state.json`, `activity.json`, `ralph-terminal.pid`, `scheduled_tasks.lock`, `reflection.md`, and current iteration logs stay in the worktree.

**Why?**
- Agent (Claude Code) writes these — simplest with relative paths
- Truly ephemeral — only valid during current agent execution
- Per-worktree by nature — each agent has its own state
- With worktree retention=keep, they persist for debugging

### 3. Python WtRuntime class for shared path resolution

**Decision:** Centralized `WtRuntime` class in `lib/wt_orch/paths.py` (renamed from WtDirs — it resolves to `~/.local/share/`, not a project-local dir).

```python
class WtRuntime:
    """Resolves paths to ~/.local/share/wt-tools/<project>/"""
    def __init__(self, project_path: str):
        self.project_name = _resolve_project_name(project_path)
        self.root = os.path.join(
            os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share")),
            "wt-tools", self.project_name
        )

    @property
    def state_file(self): return os.path.join(self.root, "orchestration", "state.json")

    @property
    def events_file(self): return os.path.join(self.root, "orchestration", "events.jsonl")

    @property
    def sentinel_dir(self): return os.path.join(self.root, "sentinel")

    @property
    def logs_dir(self): return os.path.join(self.root, "logs")

    # ... etc for all shared runtime paths

    @staticmethod
    def agent_dir(worktree_path: str) -> str:
        """Resolves per-worktree ephemeral path: <worktree>/.wt/"""
        return os.path.join(worktree_path, ".wt")
```

### 4. Bash helper for shell scripts

**Decision:** `bin/wt-paths` sourceable script exporting `$WT_RUNTIME_DIR`, `$WT_STATE_FILE`, `$WT_EVENTS_FILE`, etc.

```bash
# Resolves project name same way as Python
WT_PROJECT_NAME=$(basename "$(git rev-parse --show-toplevel 2>/dev/null)")
WT_RUNTIME_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/wt-tools/$WT_PROJECT_NAME"
WT_STATE_FILE="$WT_RUNTIME_DIR/orchestration/state.json"
WT_EVENTS_FILE="$WT_RUNTIME_DIR/orchestration/events.jsonl"
WT_SENTINEL_DIR="$WT_RUNTIME_DIR/sentinel"
WT_LOGS_DIR="$WT_RUNTIME_DIR/logs"
# Per-worktree (relative to current directory)
WT_AGENT_DIR=".wt"
```

### 5. Worktree retention — don't delete after merge

**Decision:** Default `worktree_retention: keep`. Worktrees are NOT deleted after merge.

**Config in `orchestration.yaml`:**
```yaml
worktree_retention: keep              # keep | auto-clean-after-7d | delete-on-merge
```

**Implementation:**
- `merger.py::cleanup_worktree()` — skip worktree deletion when retention=keep, only archive logs
- `merger.py::cleanup_all_worktrees()` — same skip
- New: `wt-cleanup --older-than Nd` command for manual/cron GC
- `wt-close` remains for explicit manual deletion

**Why keep?**
- Git history on the branch is valuable for debugging merge issues
- Logs and intermediate state help diagnose verify gate failures
- Disk space is cheap; re-running a failed orchestration is expensive
- User explicitly requested this based on production experience

### 6. Clean cutover, no dual-write

**Decision:** After migration, old paths are not supported. `wt-project init` creates the new structure. Projects must re-run `wt-project init`.

### 7. Auto-migration in wt-project init

**Decision:** `wt-project init` detects old-style paths and moves files to `~/.local/share/wt-tools/<project>/` automatically. Also migrates `.wt/sentinel/` to the new shared location.

### 8. Sentinel migration from `.wt/sentinel/` to `~/.local/share/`

**Decision:** The sentinel-tab change put sentinel files in `.wt/sentinel/` (project-local). This change migrates them to `~/.local/share/wt-tools/<project>/sentinel/` because sentinel is project-level, not worktree-level.

The `.wt/sentinel/` code in `lib/wt_orch/sentinel/wt_dir.py` will be updated to resolve to the shared location via `WtRuntime`.

### 9. Git untrack currently tracked runtime files

**Decision:** `wt/orchestration/orchestration-state.json` and `wt/orchestration/spec-coverage-report.md` are force-tracked despite `/wt/` gitignore. These must be `git rm --cached` during migration.

## Full directory structure (target)

```
~/.local/share/wt-tools/<project>/
├── memory/                        # EXISTING (RocksDB)
├── metrics/                       # EXISTING (SQLite) — global, not per-project
├── e2e-runs/                      # EXISTING
├── orchestration/
│   ├── state.json
│   ├── events.jsonl
│   ├── plans/
│   ├── runs/
│   ├── digest/
│   ├── spec-coverage-report.md
│   ├── report.html
│   └── audit-cycle-*.log
├── sentinel/
│   ├── events.jsonl
│   ├── findings.json
│   ├── status.json
│   ├── inbox.jsonl
│   ├── inbox.cursor
│   ├── sentinel.pid
│   └── archive/
├── logs/
│   ├── orchestration.log
│   └── changes/{change-name}/     # Archived from worktree on merge
│       └── ralph-iter-*.log
├── screenshots/
│   ├── smoke/{change-name}/attempt-*/
│   └── e2e/cycle-*/
├── cache/
│   ├── codemaps/
│   ├── designs/
│   ├── skill-invocations/
│   ├── last-memory-commit
│   └── credentials/
│       ├── jira.json
│       └── confluence.json
├── design-snapshot.md
└── version

<worktree>/.wt/                    # Per-agent ephemeral (minimal)
├── loop-state.json
├── activity.json
├── ralph-terminal.pid
├── scheduled_tasks.lock
├── reflection.md
└── logs/
    └── ralph-iter-*.log           # Current run only; archived on merge

/tmp/                              # OS ephemeral (stays)
├── wt-memoryd-<project>.sock
└── wt-memoryd-<project>.pid
```

## Risks / Trade-offs

- **[Risk] Sentinel code already uses `.wt/sentinel/`** → Mitigation: update `wt_dir.py` to use `WtRuntime.sentinel_dir`. Auto-migration moves existing `.wt/sentinel/` data.
- **[Risk] Many files reference old paths (~30+ files)** → Mitigation: systematic `WtRuntime` adoption. Python linter/grep to catch stragglers.
- **[Risk] Worktree retention fills disk** → Mitigation: `wt-cleanup --older-than Nd` for explicit GC. Config option for auto-clean.
- **[Risk] `~/.local/share/` path resolution in agents** → Mitigation: agents in worktrees need project name. Bootstrap injects `WT_PROJECT_NAME` env var or agents resolve via git.
- **[Risk] Running orchestration during migration** → Mitigation: migration happens during `wt-project init` which requires no running processes.
- **[Risk] Git-tracked state files** → Mitigation: `git rm --cached` for `wt/orchestration/orchestration-state.json` and `spec-coverage-report.md`.

## Migration checklist (files to update)

### Python — import WtRuntime, replace hardcoded paths:
- `lib/wt_orch/engine.py` — state.json, events.jsonl, plans/, loop-state queries
- `lib/wt_orch/dispatcher.py` — state.json, worktree bootstrap, ralph-terminal.pid
- `lib/wt_orch/verifier.py` — spec-coverage-report.md, screenshots
- `lib/wt_orch/merger.py` — state.json, log archival, cleanup_worktree retention
- `lib/wt_orch/planner.py` — plans/, state.json
- `lib/wt_orch/api.py` — all state reads, sentinel.pid, sentinel endpoints
- `lib/wt_orch/websocket.py` — state.json file watch path
- `lib/wt_orch/chat.py` — project path resolution
- `lib/wt_orch/events.py` — events file resolution
- `lib/wt_orch/state.py` — state file hardcoded name
- `lib/wt_orch/logging_config.py` — log file paths
- `lib/wt_orch/watchdog.py` — loop-state monitoring
- `lib/wt_orch/loop_state.py` — loop state, PID, activity, log getters
- `lib/wt_orch/loop_tasks.py` — state file references
- `lib/wt_orch/auditor.py` — audit-cycle log paths
- `lib/wt_orch/reporter.py` — report.html output path
- `lib/wt_orch/digest.py` — digest directory
- `lib/wt_orch/milestone.py` — milestone worktree cleanup (retention-aware)
- `lib/wt_orch/sentinel/wt_dir.py` — migrate from `.wt/sentinel/` to WtRuntime
- `lib/wt_orch/sentinel/events.py` — use WtRuntime.sentinel_dir
- `lib/wt_orch/sentinel/findings.py` — use WtRuntime.sentinel_dir
- `lib/wt_orch/sentinel/status.py` — use WtRuntime.sentinel_dir
- `lib/wt_orch/sentinel/inbox.py` — use WtRuntime.sentinel_dir
- `lib/wt_orch/sentinel/rotation.py` — use WtRuntime.sentinel_dir
- `mcp-server/wt_mcp_server.py` — state reads, activity reads
- `gui/control_center/mixins/handlers.py` — loop-state I/O
- `gui/control_center/mixins/table.py` — loop-state reads

### Bash — source wt-paths:
- `bin/wt-sentinel` — state.json, events.jsonl, sentinel.pid
- `bin/wt-loop` — loop-state.json, activity.json, reflection.md
- `bin/wt-new` — bootstrap worktree
- `bin/wt-merge` — state.json, generated file patterns
- `bin/wt-close` — remains for manual deletion
- `lib/orchestration/state.sh` — loop-state queries
- `lib/orchestration/events.sh` — events log path
- `lib/orchestration/utils.sh` — loop-state detection
- `lib/orchestration/dispatcher.sh` — loop-state queries
- `lib/loop/state.sh` — path helpers
- `lib/design/bridge.sh` — design-snapshot path
- `mcp-server/statusline.sh` — loop-state reads
- `.claude/hooks/activity-track.sh` — activity.json writes

### Skills/prompts:
- `.claude/commands/wt/sentinel.md` — sentinel file references
- `.claude/rules/design-bridge.md` — design-snapshot.md path
- `.claude/skills/wt/*/SKILL.md` — any referencing .claude/ runtime files

### Deploy:
- `lib/project/deploy.sh` — create `~/.local/share/wt-tools/<project>/` structure, auto-migrate old paths, update .gitignore
- `dispatcher.py::bootstrap_worktree()` — create `.wt/` in worktrees for per-agent ephemeral
