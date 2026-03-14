#!/usr/bin/env bash
# lib/orchestration/utils.sh — Parsing, duration, hashing, directive resolution, safe state primitives
# Sourced by bin/wt-orchestrate after config.sh

# ─── Safe State Primitives ────────────────────────────────────────────

# Atomically update a JSON file via jq. Validates output before overwriting.
# Usage: safe_jq_update <file> [jq args...]
# Returns 1 if jq fails or produces empty output; original file is untouched.
safe_jq_update() {
    local file="$1"; shift
    local _sjq_tmp _sjq_err
    _sjq_tmp=$(mktemp)
    _sjq_err=$(mktemp)

    if ! jq "$@" "$file" > "$_sjq_tmp" 2>"$_sjq_err"; then
        log_error "safe_jq_update: jq failed on $file — $(cat "$_sjq_err" 2>/dev/null)"
        rm -f "$_sjq_tmp" "$_sjq_err"
        return 1
    fi
    rm -f "$_sjq_err"

    if [[ ! -s "$_sjq_tmp" ]]; then
        log_error "safe_jq_update: jq produced empty output for $file"
        rm -f "$_sjq_tmp"
        return 1
    fi

    mv "$_sjq_tmp" "$file"
}

# Acquire exclusive flock on STATE_FILENAME and execute a command.
# Usage: with_state_lock <command> [args...]
# Returns the exit code of the wrapped command, or 1 on lock timeout.
with_state_lock() {
    local lock_file="${STATE_FILENAME}.lock"
    (
        flock --timeout 10 200 || {
            log_error "with_state_lock: timeout acquiring lock on $STATE_FILENAME"
            return 1
        }
        "$@"
    ) 200>"$lock_file"
}

# Delegated to Python: wt_orch.config.parse_duration()
parse_duration() {
    wt-orch-core config parse-duration "$1"
}

# Update monitor self-watchdog progress timestamp.
# Call this after any meaningful progress: dispatch, merge, gate result, status change.
# The variable last_progress_ts must be declared in the caller (monitor_loop).
update_progress_ts() {
    last_progress_ts=$(date +%s)
    idle_escalation_count=0
}

# Check if any running Ralph loop has made recent progress.
# A loop is "active" if its loop-state.json was modified within the last 5 minutes.
# Returns 0 (true) if at least one loop is active, 1 (false) if all stalled.
any_loop_active() {
    local stale_threshold=300  # 5 minutes
    local now
    now=$(date +%s)

    # Verifying changes count as active — the orchestrator is running tests/builds (finding #17)
    local verifying
    verifying=$(get_changes_by_status "verifying" 2>/dev/null || true)
    [[ -n "$verifying" ]] && return 0

    local running
    running=$(get_changes_by_status "running" 2>/dev/null || true)
    [[ -z "$running" ]] && return 1

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME" 2>/dev/null)
        [[ -z "$wt_path" ]] && continue
        local loop_state="$wt_path/.claude/loop-state.json"
        if [[ -f "$loop_state" ]]; then
            local mtime
            mtime=$(stat -c %Y "$loop_state" 2>/dev/null || stat -f %m "$loop_state" 2>/dev/null || echo 0)
            local age=$((now - mtime))
            if [[ "$age" -lt "$stale_threshold" ]]; then
                return 0  # at least one loop is active
            fi
        fi
    done <<< "$running"
    return 1  # all loops stalled or no loop-state files
}

# Delegated to Python: wt_orch.config.format_duration()
format_duration() {
    wt-orch-core config format-duration "$1"
}

# ─── Brief Parser ────────────────────────────────────────────────────

# Delegated to Python: wt_orch.config (find_brief is internal to find_input)
find_brief() {
    # Legacy compat — callers should use find_input instead
    local openspec_dir
    openspec_dir=$(find_openspec_dir)
    if [[ -n "${BRIEF_OVERRIDE:-}" && -f "$BRIEF_OVERRIDE" ]]; then
        echo "$BRIEF_OVERRIDE"
    elif [[ -f "$openspec_dir/${BRIEF_FILENAME:-project-brief.md}" ]]; then
        echo "$openspec_dir/${BRIEF_FILENAME:-project-brief.md}"
    elif [[ -f "$openspec_dir/${BRIEF_FALLBACK:-project.md}" ]]; then
        echo "$openspec_dir/${BRIEF_FALLBACK:-project.md}"
    else
        echo ""
    fi
}

# Delegated to Python: wt_orch.config.find_input()
# Sets global: INPUT_MODE ("digest" or "brief"), INPUT_PATH
find_input() {
    local args=()
    if [[ -n "${SPEC_OVERRIDE:-}" ]]; then
        args+=(--spec "$SPEC_OVERRIDE")
    elif [[ -n "${BRIEF_OVERRIDE:-}" ]]; then
        args+=(--brief "$BRIEF_OVERRIDE")
    fi
    local result
    result=$(wt-orch-core config find-input "${args[@]}" 2>&1)
    if [[ $? -ne 0 ]]; then
        error "$result"
        return 1
    fi
    INPUT_MODE=$(echo "$result" | jq -r '.mode')
    INPUT_PATH=$(echo "$result" | jq -r '.path')
}

# Delegated to Python: wt_orch.config.find_openspec_dir()
find_openspec_dir() {
    if [[ -d "openspec" ]]; then
        echo "openspec"
    elif [[ -d "../openspec" ]]; then
        echo "../openspec"
    else
        echo "openspec"
    fi
}

# Delegated to Python: wt_orch.config.parse_next_items()
parse_next_items() {
    wt-orch-core config parse-next-items --file "$1"
}

# ─── Directives ──────────────────────────────────────────────────────

# Delegated to Python: wt_orch.config.parse_directives()
parse_directives() {
    wt-orch-core config parse-directives --file "$1"
}

# Delegated to Python: wt_orch.config.brief_hash()
brief_hash() {
    wt-orch-core config brief-hash --file "$1"
}

# ─── Config & Directives ─────────────────────────────────────────────

# Delegated to Python: wt_orch.config.load_config_file()
load_config_file() {
    if [[ -z "${CONFIG_FILE:-}" || ! -f "${CONFIG_FILE:-}" ]]; then
        echo '{}'
        return 0
    fi
    wt-orch-core config load-config --file "$CONFIG_FILE"
}

# Delegated to Python: wt_orch.config.resolve_directives()
resolve_directives() {
    local input_file="$1"
    local args=(--file "$input_file")
    if [[ -n "${CONFIG_FILE:-}" && -f "${CONFIG_FILE:-}" ]]; then
        args+=(--config "$CONFIG_FILE")
    fi
    if [[ -n "${CLI_MAX_PARALLEL:-}" ]]; then
        args+=(--override "max_parallel=$CLI_MAX_PARALLEL")
    fi
    wt-orch-core config resolve-directives "${args[@]}"
}

# ─── State Management ────────────────────────────────────────────────

# Initialize orchestration state
