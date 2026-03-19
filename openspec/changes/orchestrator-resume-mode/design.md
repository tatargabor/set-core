# Design: Orchestrator Resume Mode

## Current flow (problem)

```
wt-orchestrate start --spec docs/
  → cmd_start()
  → need_plan? (plan file missing → YES)
  → cmd_plan() → digest → decompose → 5-10 min wasted
  → init_state() → overwrites existing state
  → dispatch → monitor
```

## New flow (resume)

```
wt-orchestrate start --spec docs/
  → cmd_start()
  → state file exists with active changes? → AUTO-RESUME
  → skip digest, planning, state init
  → detect zombies (dead PIDs → stalled)
  → exec monitor loop directly
```

## Component Changes

### 1. dispatcher.sh — Auto-resume detection in cmd_start()

Before the `need_plan` check, add resume detection:

```bash
# Auto-resume: if state file has active changes, skip planning
if [[ -f "$STATE_FILENAME" ]] && ! ${FORCE_REPLAN:-false}; then
    local active_count
    active_count=$(jq '[.changes[] | select(.status == "running" or .status == "pending" or .status == "verifying" or .status == "stalled" or .status == "dispatched")] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$active_count" -gt 0 ]]; then
        info "Resuming from existing state ($active_count active changes)"
        log_info "Auto-resume: $active_count active changes in state"

        # Detect zombie processes
        _detect_zombies

        # Restore directives
        local directives
        directives=$(cat "wt/orchestration/directives.json" 2>/dev/null || echo '{}')

        # Dispatch pending changes that have no worktree yet
        dispatch_ready_changes "$max_parallel"

        # Go directly to monitor
        trap - EXIT
        update_state_field "status" '"running"'
        local _directives_file="wt/orchestration/directives.json"
        exec wt-orch-core engine monitor \
            --directives "$_directives_file" \
            --state "$STATE_FILENAME" \
            --poll-interval "${POLL_INTERVAL:-15}" \
            --default-model "$(jq -r '.default_model // "opus"' "$_directives_file")" \
            ${CHECKPOINT_AUTO_APPROVE:+--checkpoint-auto-approve}
    fi
fi
```

### 2. dispatcher.sh — Zombie detection helper

```bash
_detect_zombies() {
    # Mark running changes with dead PIDs as stalled
    local changes
    changes=$(jq -r '.changes[] | select(.status == "running") | .name + ":" + (.ralph_pid // 0 | tostring)' "$STATE_FILENAME" 2>/dev/null)
    while IFS=: read -r name pid; do
        [[ -z "$name" || "$pid" == "0" ]] && continue
        if ! kill -0 "$pid" 2>/dev/null; then
            log_info "Zombie detected: $name (PID $pid dead) — will be handled by monitor"
        fi
    done <<< "$changes"
}
```

### 3. sentinel — Backup instead of delete

In the sentinel's "fresh start" logic, replace state deletion with backup:

```bash
# BEFORE (destructive):
rm -f "$STATE_FILENAME" "$EVENTS_FILE"

# AFTER (safe):
if [[ -f "$STATE_FILENAME" ]]; then
    cp "$STATE_FILENAME" "${STATE_FILENAME}.bak"
    log "Backed up state to ${STATE_FILENAME}.bak"
fi
```

### 4. wt-orchestrate — Resume subcommand alias

```bash
case "$command" in
    resume)     FORCE_REPLAN=false cmd_start "$@" ;;
```

## Decision Log

- **Auto-detect vs explicit flag**: auto-detect is better UX (no flag needed), but `--resume` kept as explicit override
- **Zombie detection in bash vs Python**: bash detects, Python monitor handles recovery (consistent with existing stall detection)
- **Sentinel backup**: `.bak` file preserved for manual recovery, not auto-restored
