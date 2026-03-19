## Architecture

### Module: `lib/set_orch/merger.py`

1:1 function migration from `lib/orchestration/merger.sh` (672 lines). Three logical groups:

**Merge Pipeline** — `merge_change()` orchestrates: pre-merge hook → branch existence check → wt-merge with LLM conflict resolution → post-merge deps install → post-merge build verification → smoke tests (blocking/non-blocking) → agent-assisted rebase on conflict

**Worktree Lifecycle** — `cleanup_worktree`, `cleanup_all_worktrees`, `_archive_worktree_logs`, `archive_change`, `_sync_running_worktrees`

**Merge Queue** — `execute_merge_queue`, `retry_merge_queue`, `_try_merge` with conflict fingerprint dedup, max 5 retries

### Module: `lib/set_orch/milestone.py`

1:1 function migration from `lib/orchestration/milestone.sh` (242 lines). Two logical groups:

**Milestone Checkpoint** — `run_milestone_checkpoint()`: git tag → worktree → deps install → dev server → email → emit event

**Cleanup** — `cleanup_milestone_servers`, `cleanup_milestone_worktrees`, `_enforce_max_milestone_worktrees`

### Module: `lib/set_orch/engine.py`

1:1 function migration from `lib/orchestration/monitor.sh` (586 lines). Single entry point:

**Monitor Loop** — `monitor_loop(directives, state_file)`: directive parsing → poll interval → poll active changes → poll suspended changes → token budget → verify-failed recovery → cascade failed deps → dispatch → phase completion → merge queue retry → resume stalled → retry failed builds → token hard limit → self-watchdog → checkpoint → completion detection → auto-replan

### Function Mapping

| Bash function (merger.sh) | Python function | Notes |
|---|---|---|
| `archive_change` | `archive_change()` | git add+commit via subprocess |
| `_collect_smoke_screenshots` | `_collect_smoke_screenshots()` | shutil.copytree |
| `merge_change` | `merge_change()` | Full pipeline, returns bool |
| `_sync_running_worktrees` | `_sync_running_worktrees()` | Post-merge sync |
| `_archive_worktree_logs` | `_archive_worktree_logs()` | shutil.copy2 |
| `cleanup_worktree` | `cleanup_worktree()` | wt-close → fallback manual |
| `cleanup_all_worktrees` | `cleanup_all_worktrees()` | Iterate terminal changes |
| `execute_merge_queue` | `execute_merge_queue()` | Drain queue |
| `retry_merge_queue` | `retry_merge_queue()` | Retry + merge-blocked |
| `_try_merge` | `_try_merge()` | Single attempt + fingerprint dedup |

| Bash function (milestone.sh) | Python function | Notes |
|---|---|---|
| `run_milestone_checkpoint` | `run_milestone_checkpoint()` | Full pipeline |
| `_send_milestone_email` | `_send_milestone_email()` | HTML email |
| `_enforce_max_milestone_worktrees` | `_enforce_max_milestone_worktrees()` | Kill server + remove wt |
| `cleanup_milestone_servers` | `cleanup_milestone_servers()` | Kill all PIDs |
| `cleanup_milestone_worktrees` | `cleanup_milestone_worktrees()` | Remove all wts |

| Bash function (monitor.sh) | Python function | Notes |
|---|---|---|
| `monitor_loop` | `monitor_loop()` | Full loop with all branches |

### Data Structures

```python
@dataclass
class MergeResult:
    success: bool
    status: str  # "merged", "merge-blocked", "smoke_failed", "merge_timeout"
    smoke_result: str = ""  # "pass", "fail", "fixed", "blocked", "skip_merged"

@dataclass
class Directives:
    """Parsed orchestration directives from JSON input."""
    max_parallel: int
    checkpoint_every: int
    test_command: str
    merge_policy: str
    token_budget: int
    auto_replan: bool
    max_replan_cycles: int
    test_timeout: int
    max_verify_retries: int
    review_before_merge: bool
    review_model: str
    smoke_command: str
    smoke_timeout: int
    smoke_blocking: bool
    # ... (all ~40 fields from monitor.sh directive parsing)
```

### CLI Bridge

New `set-orch-core merge` subcommand group:

```
set-orch-core merge change --change NAME --state PATH
set-orch-core merge archive --change NAME
set-orch-core merge cleanup-worktree --change NAME --wt-path PATH
set-orch-core merge cleanup-all --state PATH
set-orch-core merge execute-queue --state PATH
set-orch-core merge retry-queue --state PATH
```

New `set-orch-core milestone` subcommand group:

```
set-orch-core milestone checkpoint --phase N --base-port PORT --max-worktrees N --state PATH
set-orch-core milestone cleanup-servers --state PATH
set-orch-core milestone cleanup-worktrees
```

New `set-orch-core engine` subcommand group:

```
set-orch-core engine monitor --directives-json PATH --state PATH
```

### Dependencies

- `set_orch.state` — `locked_state`, `update_change_field`, `update_state_field`, `load_state`, `Change`, `OrchestratorState`
- `set_orch.events` — `EventBus.emit()`
- `set_orch.subprocess_utils` — `run_command()`, `run_git()`, `CommandResult`
- `set_orch.process` — `check_pid()`
- `set_orch.notifications` — `send_notification()`
- `set_orch.verifier` — `poll_change()`, `extract_health_check_url()`, `health_check()`, `smoke_fix_scoped()`, `verify_merge_scope()`, `run_phase_end_e2e()`
- `set_orch.dispatcher` — `resume_change()`, `dispatch_ready_changes()`, `cascade_failed_deps()`, `resume_stalled_changes()`, `retry_failed_builds()`, `sync_worktree_with_main()`, `check_base_build()`, `fix_base_build_with_llm()`

### Design Decisions

1. **`monitor_loop` becomes a Python while-loop** — bash's `while true; sleep N; done` maps to `while True: time.sleep(N)`. All jq directive parsing becomes `json.loads` + dict access. Globals become `Directives` dataclass fields.
2. **Merge pipeline stays sequential** — `merge_change` has complex branching (pre-merge hook, branch existence, LLM conflict resolution, post-merge build, smoke pipeline). Each step may short-circuit. Sequential execution with early returns matches bash structure.
3. **`wt-merge` and `wt-close` remain subprocess calls** — these are standalone CLI tools, not library functions. Python calls them via `run_command()`.
4. **Conflict fingerprint dedup** — `git merge-tree` + md5sum piped through subprocess, same as bash. No Python-native alternative needed.
5. **Milestone dev server** — background subprocess with PID tracking, same pattern as bash. `subprocess.Popen` with stdout/stderr redirected.
6. **`flock` serialization for merge** — the bash merger relies on flock held by monitor_loop. Python equivalent: `fcntl.flock()` or delegate to bash wrapper. Decision: bash wrapper holds flock, Python does the work inside.
7. **Engine CLI is fire-and-forget** — `set-orch-core engine monitor` runs as a long-lived process. The bash `monitor_loop()` wrapper starts it and waits.
