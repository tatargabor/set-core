#!/usr/bin/env bash
# lib/orchestration/milestone.sh — Milestone checkpoint: tag, worktree, dev server, email
# Sourced by bin/wt-orchestrate after server-detect.sh
# Dependencies: state.sh, events.sh, server-detect.sh, notify-email.sh
# Provides: run_milestone_checkpoint(), cleanup_milestone_servers(), cleanup_milestone_worktrees()

MILESTONE_WORKTREE_DIR=".claude/milestones"

# Run milestone checkpoint for a completed phase.
# Steps: git tag → create worktree → install deps → start server → send email → emit event
# Args: phase_number base_port max_worktrees [milestone_dev_server]
run_milestone_checkpoint() {
    local phase="$1"
    local base_port="${2:-3100}"
    local max_worktrees="${3:-3}"
    local milestone_dev_server="${4:-}"

    log_info "Milestone checkpoint: phase $phase"

    # 1. Git tag
    local tag_name="milestone/phase-$phase"
    git tag -f "$tag_name" HEAD 2>/dev/null || {
        log_warn "Milestone: failed to create tag $tag_name"
    }
    with_state_lock safe_jq_update "$STATE_FILENAME" \
        --arg p "$phase" --arg tag "$tag_name" \
        '.phases[$p].tag = $tag'
    log_info "Milestone: tagged $tag_name"

    # 2. Create worktree (enforce max_worktrees limit)
    _enforce_max_milestone_worktrees "$max_worktrees"
    local wt_path="$MILESTONE_WORKTREE_DIR/phase-$phase"
    if [[ -d "$wt_path" ]]; then
        log_warn "Milestone: worktree $wt_path already exists — removing"
        git worktree remove --force "$wt_path" 2>/dev/null || true
    fi
    mkdir -p "$(dirname "$wt_path")"
    if git worktree add "$wt_path" "$tag_name" 2>/dev/null; then
        log_info "Milestone: worktree created at $wt_path"
    else
        log_warn "Milestone: failed to create worktree at $wt_path"
    fi

    # 3. Install deps + 4. Start dev server
    local server_port=$((base_port + phase))
    local server_pid=""

    local smoke_dev_cmd
    smoke_dev_cmd=$(jq -r '.directives.smoke_dev_server_command // ""' "$STATE_FILENAME" 2>/dev/null || echo "")

    local dev_cmd
    dev_cmd=$(detect_dev_server "$wt_path" "$milestone_dev_server" "$smoke_dev_cmd" 2>/dev/null || true)

    if [[ -n "$dev_cmd" && -d "$wt_path" ]]; then
        # Install dependencies
        install_dependencies "$wt_path" || true

        # Start dev server with PORT env var
        log_info "Milestone: starting dev server on port $server_port: $dev_cmd"
        (cd "$wt_path" && PORT=$server_port exec bash -c "$dev_cmd") >/dev/null 2>&1 &
        server_pid=$!

        # Check if process is alive after 5s
        local smoke_hc_url
        smoke_hc_url=$(jq -r '.directives.smoke_health_check_url // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        if [[ -n "$smoke_hc_url" ]]; then
            # Adapt health check URL to milestone port
            local hc_url
            hc_url=$(echo "$smoke_hc_url" | sed "s/:[0-9]\+/:$server_port/")
            if health_check "$hc_url" 30; then
                log_info "Milestone: dev server healthy on port $server_port (PID $server_pid)"
            else
                log_warn "Milestone: dev server health check failed on port $server_port"
            fi
        else
            sleep 5
            if kill -0 "$server_pid" 2>/dev/null; then
                log_info "Milestone: dev server running on port $server_port (PID $server_pid)"
            else
                log_warn "Milestone: dev server died on port $server_port"
                server_pid=""
            fi
        fi

        # Store PID and port in state
        with_state_lock safe_jq_update "$STATE_FILENAME" \
            --arg p "$phase" --argjson port "$server_port" \
            '.phases[$p].server_port = $port'
        if [[ -n "$server_pid" ]]; then
            with_state_lock safe_jq_update "$STATE_FILENAME" \
                --arg p "$phase" --argjson pid "$server_pid" \
                '.phases[$p].server_pid = $pid'
        fi
    else
        log_info "Milestone: no dev server detected — skipping server start"
    fi

    # 5. Send milestone email
    _send_milestone_email "$phase" "$server_port" "$server_pid"

    # 6. Emit event
    local change_count
    change_count=$(jq --argjson p "$phase" '[.changes[] | select(.phase == $p)] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    emit_event "MILESTONE_COMPLETE" "" \
        "$(jq -cn --argjson phase "$phase" --argjson changes "$change_count" \
            --argjson port "$server_port" --arg tag "$tag_name" \
            '{phase: $phase, changes: $changes, server_port: $port, tag: $tag}')"

    log_info "Milestone checkpoint complete: phase $phase"
}

# Send milestone completion email
_send_milestone_email() {
    local phase="$1"
    local port="$2"
    local pid="$3"

    if ! type send_email &>/dev/null; then
        return 0
    fi

    local project_name
    project_name="$(basename "$(pwd)")"

    # Gather phase stats
    local total_changes merged_changes phase_tokens
    total_changes=$(jq --argjson p "$phase" '[.changes[] | select(.phase == $p)] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    merged_changes=$(jq --argjson p "$phase" '[.changes[] | select(.phase == $p and (.status == "merged" or .status == "done"))] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    phase_tokens=$(jq --argjson p "$phase" '[.changes[] | select(.phase == $p) | .tokens_used // 0] | add // 0' "$STATE_FILENAME" 2>/dev/null || echo 0)

    local subject="[wt-tools] $project_name — Phase $phase complete ($merged_changes/$total_changes changes)"

    local html=""
    html+="<h2>Phase $phase Complete: $project_name</h2>"
    html+="<p><strong>Date:</strong> $(date '+%Y-%m-%d %H:%M:%S')</p>"
    html+="<h3>Phase Summary</h3>"
    html+="<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    html+="<tr><td><strong>Changes</strong></td><td>$merged_changes / $total_changes merged</td></tr>"
    html+="<tr><td><strong>Tokens</strong></td><td>$phase_tokens</td></tr>"

    if [[ -n "$pid" ]]; then
        html+="<tr><td><strong>Dev Server</strong></td><td><a href=\"http://localhost:$port\">http://localhost:$port</a></td></tr>"
    fi
    html+="</table>"

    # List merged changes
    html+="<h3>Changes in Phase $phase</h3>"
    html+="<table border='1' cellpadding='6' cellspacing='0' style='border-collapse:collapse;'>"
    html+="<tr style='background:#f0f0f0;'><th>Change</th><th>Status</th><th>Tokens</th></tr>"
    while IFS=$'\t' read -r name cstatus ctokens; do
        [[ -z "$name" ]] && continue
        local color="#fff"
        case "$cstatus" in
            done|merged) color="#d4edda" ;;
            failed) color="#f8d7da" ;;
        esac
        html+="<tr style='background:$color;'><td>$name</td><td>$cstatus</td><td>$ctokens</td></tr>"
    done < <(jq -r --argjson p "$phase" '.changes[] | select(.phase == $p) | "\(.name)\t\(.status)\t\(.tokens_used // 0)"' "$STATE_FILENAME" 2>/dev/null || true)
    html+="</table>"

    html+="<p style='color:#888;'>Orchestrator continues automatically. Stop with: <code>wt-orchestrate stop</code></p>"

    send_email "$subject" "$html" 2>/dev/null || true
}

# Enforce max milestone worktrees limit — remove oldest if exceeded
_enforce_max_milestone_worktrees() {
    local max="$1"
    [[ ! -d "$MILESTONE_WORKTREE_DIR" ]] && return 0

    local existing
    existing=$(find "$MILESTONE_WORKTREE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | wc -l)

    while [[ "$existing" -ge "$max" ]]; do
        local oldest
        oldest=$(find "$MILESTONE_WORKTREE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null | sort | head -1)
        [[ -z "$oldest" ]] && break

        local oldest_name
        oldest_name=$(basename "$oldest")
        local oldest_phase="${oldest_name#phase-}"

        # Kill server if running
        local old_pid
        old_pid=$(jq -r --arg p "$oldest_phase" '.phases[$p].server_pid // empty' "$STATE_FILENAME" 2>/dev/null)
        if [[ -n "$old_pid" ]]; then
            kill "$old_pid" 2>/dev/null || true
            with_state_lock safe_jq_update "$STATE_FILENAME" \
                --arg p "$oldest_phase" '.phases[$p].server_pid = null'
            log_info "Milestone: killed server for phase $oldest_phase (PID $old_pid)"
        fi

        # Remove worktree
        git worktree remove --force "$oldest" 2>/dev/null || rm -rf "$oldest"
        log_info "Milestone: removed oldest worktree $oldest_name (limit: $max)"
        existing=$((existing - 1))
    done
}

# ─── Cleanup ─────────────────────────────────────────────────────────

# Kill all milestone dev server processes
cleanup_milestone_servers() {
    [[ ! -f "$STATE_FILENAME" ]] && return 0

    local has_phases
    has_phases=$(jq 'has("phases")' "$STATE_FILENAME" 2>/dev/null)
    [[ "$has_phases" != "true" ]] && return 0

    local pids
    pids=$(jq -r '.phases | to_entries[] | .value.server_pid // empty' "$STATE_FILENAME" 2>/dev/null)
    while IFS= read -r pid; do
        [[ -z "$pid" || "$pid" == "null" ]] && continue
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            log_info "Milestone cleanup: killed server PID $pid"
        fi
    done <<< "$pids"

    # Clear all PIDs from state
    with_state_lock safe_jq_update "$STATE_FILENAME" \
        '.phases = (.phases | to_entries | map(.value.server_pid = null) | from_entries)'
}

# Remove all milestone worktrees
cleanup_milestone_worktrees() {
    [[ ! -d "$MILESTONE_WORKTREE_DIR" ]] && return 0

    local cleaned=0
    while IFS= read -r wt_dir; do
        [[ -z "$wt_dir" ]] && continue
        git worktree remove --force "$wt_dir" 2>/dev/null || rm -rf "$wt_dir"
        cleaned=$((cleaned + 1))
    done < <(find "$MILESTONE_WORKTREE_DIR" -mindepth 1 -maxdepth 1 -type d 2>/dev/null)

    if [[ $cleaned -gt 0 ]]; then
        log_info "Milestone cleanup: removed $cleaned worktree(s)"
    fi

    # Remove empty milestone dir
    rmdir "$MILESTONE_WORKTREE_DIR" 2>/dev/null || true
}
