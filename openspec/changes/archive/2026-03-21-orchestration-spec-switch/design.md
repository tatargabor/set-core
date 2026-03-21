# Design: Orchestration Spec Switch

## Approach

All changes in the sentinel bash layer (`bin/set-sentinel`), with minor touches to state and dispatcher.

### 1. Spec change detection

**Where**: `bin/set-sentinel`, after `fix_stale_state()` (line ~620), inside flock guard.

```bash
detect_spec_change() {
    local spec_arg="$1"
    local state_file="$PROJECT_DIR/orchestration-state.json"

    [[ ! -f "$state_file" ]] && return 1  # no state = fresh start, not a switch

    local stored_hash
    stored_hash=$(jq -r '.brief_hash // empty' "$state_file" 2>/dev/null)
    [[ -z "$stored_hash" ]] && return 1  # no hash stored = legacy state, treat as fresh

    local current_hash
    current_hash=$(brief_hash "$spec_arg")

    [[ "$stored_hash" == "$current_hash" ]] && return 1  # same spec, resume

    # Different spec detected
    local stored_path
    stored_path=$(jq -r '.input_path // "unknown"' "$state_file" 2>/dev/null)
    sentinel_log "Spec changed: $stored_path → $spec_arg (hash: $stored_hash → $current_hash) — resetting orchestration"
    return 0
}
```

### 2. Reset flow

**Where**: `bin/set-sentinel`, new function `reset_for_spec_switch()`.

```bash
reset_for_spec_switch() {
    sentinel_log "Resetting orchestration for spec switch"

    # 1. Delete orch/* tags (unblock clean_old_worktrees)
    local tags
    tags=$(git tag -l 'orch/*' 2>/dev/null || true)
    if [[ -n "$tags" ]]; then
        echo "$tags" | xargs git tag -d 2>/dev/null || true
        sentinel_log "Removed $(echo "$tags" | wc -l) orch/* tags"
    fi

    # 2. Clean worktrees (now unblocked)
    clean_old_worktrees  # existing function, handles worktree removal

    # 3. Delete merged change/* branches only
    local merged_branches
    merged_branches=$(git branch --merged main 2>/dev/null | grep 'change/' | sed 's/^[ *]*//' || true)
    if [[ -n "$merged_branches" ]]; then
        echo "$merged_branches" | xargs git branch -d 2>/dev/null || true
        sentinel_log "Pruned $(echo "$merged_branches" | wc -l) merged change/* branches"
    fi

    # 4. Remove orchestration state files
    rm -f "$PROJECT_DIR/orchestration-state.json"
    rm -f "$PROJECT_DIR/orchestration-state.json.lock"
    rm -f "$PROJECT_DIR/orchestration-state-events.jsonl"
    rm -f "$PROJECT_DIR/orchestration-events.jsonl"
    rm -f "$PROJECT_DIR/orchestrator.lock"

    # 5. Remove digest (will be regenerated)
    rm -rf "$PROJECT_DIR/wt/orchestration/digest"

    # 6. Remove plan (will be regenerated)
    rm -f "$PROJECT_DIR/wt/orchestration/plan.json"

    sentinel_log "Orchestration reset complete — git history preserved"
}
```

### 3. Integration into sentinel startup

**Where**: `bin/set-sentinel`, after `fix_stale_state` call (~line 620), before orchestrator launch.

```bash
fix_stale_state

# Spec switch detection
if [[ "$FRESH_FLAG" == "true" ]] || detect_spec_change "$SPEC_ARG"; then
    reset_for_spec_switch
fi

# Continue with normal orchestrator launch...
```

### 4. `--fresh` flag parsing

**Where**: `bin/set-sentinel`, argument parsing section.

Add `--fresh` to the getopts/case block. Sets `FRESH_FLAG=true`.

### 5. Change name dedup in dispatcher

**Where**: `lib/set_orch/dispatcher.py`, worktree creation function.

Before creating branch/worktree, check if name exists and append suffix:

```python
def _unique_change_branch(name: str) -> str:
    """Return a unique branch name, appending -N suffix if needed."""
    branch = f"change/{name}"
    result = run_command(["git", "branch", "--list", branch], timeout=10)
    if not result.stdout.strip():
        return branch  # doesn't exist, use as-is

    for i in range(2, 100):
        candidate = f"change/{name}-{i}"
        result = run_command(["git", "branch", "--list", candidate], timeout=10)
        if not result.stdout.strip():
            return candidate

    raise RuntimeError(f"Could not find unique branch name for {name}")
```

Same pattern for worktree path.

## Dependencies

- `brief_hash()` function in `lib/orchestration/utils.sh` (exists)
- `clean_old_worktrees()` in `bin/set-sentinel` (exists)
- `jq` for JSON parsing (already required)
