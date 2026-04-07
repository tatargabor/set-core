# Design: set-recovery skill

## Architecture

```
bin/set-recovery (bash wrapper)
  ↓
lib/set_orch/recovery.py
  RecoveryPlan dataclass
  recover_to_change(project_path, target_change, dry_run, yes)
    ↓
  1. Validate project state (no running orchestrator/sentinel)
  2. Load state, find target change index
  3. Build RecoveryPlan (what to undo)
  4. Show preview
  5. Confirm (unless --yes)
  6. Backup state.json + create git tag
  7. Execute steps (atomic: rollback partial on failure)
  8. Report
```

## RecoveryPlan dataclass

```python
@dataclass
class RecoveryPlan:
    target_change: str           # e.g., "shopping-cart"
    target_commit: str           # archive commit SHA of target
    rollback_changes: list[str]  # changes after target, in order
    branches_to_delete: list[str]
    worktrees_to_remove: list[str]
    archive_dirs_to_restore: list[Path]
    state_changes_to_reset: list[str]
    backup_tag: str              # e.g., "recovery-backup-20260407-130000"
```

## Step-by-step recovery

### Step 1: Validate

```python
def _validate_project(project_path: Path, target_change: str) -> None:
    # Check no running orchestrator
    state = load_state(project_path / "orchestration-state.json")
    if state.orchestrator_pid and is_pid_alive(state.orchestrator_pid):
        raise RecoveryError("Orchestrator running — stop it first")
    
    # Check no running sentinel  
    sentinel_pid_file = project_path / ".set" / "sentinel.pid"
    if sentinel_pid_file.exists():
        pid = int(sentinel_pid_file.read_text())
        if is_pid_alive(pid):
            raise RecoveryError("Sentinel running — stop it first")
    
    # Check target change exists and is merged
    target = next((c for c in state.changes if c.name == target_change), None)
    if not target:
        raise RecoveryError(f"Target change '{target_change}' not found")
    if target.status != "merged":
        raise RecoveryError(f"Target '{target_change}' is {target.status}, not merged — cannot recover to non-merged state")
```

### Step 2: Find target commit

The archive commit is created by `merger.py` after the change is merged + archived:
```bash
git log --grep="archive {target_change}" --format="%H" -1
```

If no archive commit found, fall back to the `merge {target_change}` commit. Worst case, search by `--grep="{target_change}"` and pick the latest.

### Step 3: Build plan

```python
def _build_recovery_plan(state, target_change, target_commit) -> RecoveryPlan:
    # Find changes that come AFTER the target in topological order
    target_idx = next(i for i, c in enumerate(state.changes) if c.name == target_change)
    rollback = [c for c in state.changes[target_idx+1:] if c.status in ("merged", "verifying", "integrating", "running", "done")]
    
    return RecoveryPlan(
        target_change=target_change,
        target_commit=target_commit,
        rollback_changes=[c.name for c in rollback],
        branches_to_delete=[f"change/{c.name}" for c in rollback],
        worktrees_to_remove=[c.worktree_path for c in rollback if c.worktree_path],
        archive_dirs_to_restore=[
            project_path / "openspec" / "changes" / "archive" / d
            for c in rollback
            for d in find_archived_change_dirs(c.name)
        ],
        state_changes_to_reset=[c.name for c in rollback],
        backup_tag=f"recovery-backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
    )
```

### Step 4: Preview

```
Recovery Plan for /path/to/minishop-run1
========================================

Target: shopping-cart (last good)
After rollback, ready to re-run:
  - admin-products
  - checkout-orders

Will undo:
  Git:
    - reset main → f9965a7 (chore: archive shopping-cart)
    - delete branch change/admin-products
    - delete branch change/checkout-orders
    - tag rollback point as recovery-backup-20260407-130000
  
  Worktrees:
    - /path/to/minishop-run1-wt-admin-products
    - /path/to/minishop-run1-wt-checkout-orders
  
  OpenSpec:
    - move archive/2026-04-07-minishop-run1-admin-products → changes/admin-products
    - move archive/2026-04-07-minishop-run1-checkout-orders → changes/checkout-orders
  
  State:
    - admin-products: merged → pending (clear: tokens, gates, retries, worktree)
    - checkout-orders: merged → pending (clear: tokens, gates, retries, worktree)
    - merge_queue: cleared
    - current_phase: 3 → 3 (admin-products' phase)
  
  Backup:
    - orchestration-state.json → orchestration-state.json.bak.20260407-130000
    - git tag recovery-backup-20260407-130000

Type 'yes' to proceed:
```

### Step 5: Execute

```python
def _execute_plan(project_path, plan, state):
    # Backup
    state_backup = project_path / f"orchestration-state.json.bak.{plan.backup_tag.split('-', 1)[1]}"
    shutil.copy(project_path / "orchestration-state.json", state_backup)
    run_git("tag", plan.backup_tag, cwd=project_path)
    
    try:
        # 1. Stop any zombie agent processes
        for change in plan.state_changes_to_reset:
            ch = next(c for c in state.changes if c.name == change)
            if ch.ralph_pid:
                try: os.kill(ch.ralph_pid, signal.SIGTERM)
                except: pass
        
        # 2. Remove worktrees
        for wt_path in plan.worktrees_to_remove:
            if os.path.isdir(wt_path):
                run_git("worktree", "remove", "--force", wt_path, cwd=project_path)
        
        # 3. Delete branches
        for branch in plan.branches_to_delete:
            run_git("branch", "-D", branch, cwd=project_path)
        
        # 4. Reset main
        run_git("reset", "--hard", plan.target_commit, cwd=project_path)
        
        # 5. Restore archived changes
        for archive_dir in plan.archive_dirs_to_restore:
            change_name = archive_dir.name.split("-", 3)[-1]  # strip date prefix
            dest = project_path / "openspec" / "changes" / change_name
            shutil.move(str(archive_dir), str(dest))
        
        # 6. Reset state
        with locked_state(project_path / "orchestration-state.json") as s:
            for ch in s.changes:
                if ch.name in plan.state_changes_to_reset:
                    ch.status = "pending"
                    ch.ralph_pid = None
                    ch.worktree_path = None
                    ch.completed_at = None
                    ch.tokens_used = 0
                    ch.input_tokens = 0
                    ch.output_tokens = 0
                    ch.cache_read_tokens = 0
                    ch.cache_create_tokens = 0
                    ch.build_result = None
                    ch.test_result = None
                    ch.e2e_result = None
                    ch.review_result = None
                    ch.test_coverage = None
                    ch.extras.pop("merge_retry_count", None)
                    ch.extras.pop("integration_retry_count", None)
                    ch.extras.pop("integration_e2e_retry_count", None)
                    ch.extras.pop("retry_context", None)
            s.merge_queue = []
            s.status = "stopped"  # require explicit restart
            # Reset phase to first rolled-back change's phase
            if plan.state_changes_to_reset:
                first_phase = next(c.phase for c in s.changes if c.name == plan.state_changes_to_reset[0])
                s.extras["current_phase"] = first_phase
        
    except Exception as e:
        # Atomic rollback: restore state.json from backup
        shutil.copy(state_backup, project_path / "orchestration-state.json")
        # Note: git reset can be undone via the backup tag
        raise RecoveryError(f"Recovery failed mid-way: {e}. State restored. Git can be recovered via tag {plan.backup_tag}")
```

### Step 6: Report

```
Recovery complete.

Project: minishop-run1
Rolled back to: shopping-cart (commit f9965a7)

To resume orchestration with the rolled-back changes:
  1. Verify state: cat orchestration-state.json | jq '.changes[] | {name, status}'
  2. Restart sentinel: curl -X POST http://localhost:7400/api/minishop-run1/sentinel/start \
       -d '{"spec": "docs/v1-minishop.md"}'

To undo this recovery:
  cd /path/to/project
  git reset --hard recovery-backup-20260407-130000
  cp orchestration-state.json.bak.20260407-130000 orchestration-state.json
```

## Edge cases

1. **Target is the only change**: Refuse — nothing to roll back
2. **Target is the last change**: Refuse — nothing came after
3. **Some rollback changes have non-merged status** (e.g., `running`): kill agent process, then continue
4. **Archive dir naming mismatch**: Search by suffix
5. **Git tag already exists** (re-running recovery): Append a counter
6. **State.json corrupt**: Refuse, ask user to fix manually first
7. **Worktree dir already deleted**: Skip git worktree remove, log warning

## CLI argument design

```
Usage: set-recovery <project-name> <target-change> [options]

Arguments:
  <project-name>   Registered project name (from set-project list)
  <target-change>  Name of the change to recover to (must be merged)

Options:
  --dry-run        Show plan without executing
  --yes            Skip confirmation prompt
  --json           Output plan as JSON (for scripts)
  --keep-archive   Don't move archived changes back (advanced)

Exit codes:
  0   Success
  1   Validation failed (running orch, target not merged, etc.)
  2   User cancelled
  3   Execution error (state restored)
```

## Skill structure

```
.claude/skills/set-recovery/
  SKILL.md          # Skill documentation
```

`.claude/commands/set/recovery.md` — slash command that invokes the skill.

## Why not split into smaller pieces

The recovery is inherently atomic — partial rollback leaves a worse state than before. Better to have one tool that does everything correctly than separate scripts the user must orchestrate.

## Future extensions

- `--undo` to apply the latest backup tag
- `set-recovery list` to show available backup tags
- Web UI button "Rollback to this change" in the dashboard Changes tab
