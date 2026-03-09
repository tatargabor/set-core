#!/usr/bin/env bash
# lib/orchestration/watchdog.sh — Self-healing watchdog for orchestration
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: events.sh (emit_event), state.sh (update_change_field, jq on STATE_FILENAME)
#
# Per-change watchdog state stored in orchestration-state.json:
#   .changes[].watchdog = {
#     last_activity_epoch, action_hash_ring[], consecutive_same_hash,
#     escalation_level, progress_baseline
#   }
#
# Progress detection reads loop-state.json iterations to detect spinning/stuck patterns.
# Global token safety nets (token_budget, token_hard_limit) remain in monitor.sh.

# ─── Configuration ───────────────────────────────────────────────────

# Per-state timeout defaults (seconds). Overridden by watchdog_timeout directive.
WATCHDOG_TIMEOUT_RUNNING=600
WATCHDOG_TIMEOUT_VERIFYING=300
WATCHDOG_TIMEOUT_DISPATCHED=120

# Loop detection: consecutive identical action hashes before declaring stuck
WATCHDOG_LOOP_THRESHOLD=5
WATCHDOG_HASH_RING_SIZE=5

# ─── Watchdog Check ─────────────────────────────────────────────────

# Main watchdog check for a single change. Called after poll_change() in monitor_loop.
# Detects: timeouts (per-state), action hash loops, and escalates accordingly.
watchdog_check() {
    local change_name="$1"

    local status
    status=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .status // ""' "$STATE_FILENAME" 2>/dev/null)

    # Only watch active statuses
    case "$status" in
        running|verifying|dispatched|stalled) ;;
        *) return 0 ;;
    esac

    # Lazy-init watchdog state for this change
    local has_wd
    has_wd=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .watchdog // empty' "$STATE_FILENAME" 2>/dev/null)
    if [[ -z "$has_wd" || "$has_wd" == "null" ]]; then
        _watchdog_init "$change_name"
    fi

    # Read current watchdog state
    local wd_json
    wd_json=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .watchdog' "$STATE_FILENAME" 2>/dev/null)
    local last_activity
    last_activity=$(echo "$wd_json" | jq -r '.last_activity_epoch // 0')
    local escalation_level
    escalation_level=$(echo "$wd_json" | jq -r '.escalation_level // 0')
    local consecutive_same
    consecutive_same=$(echo "$wd_json" | jq -r '.consecutive_same_hash // 0')

    local now
    now=$(date +%s)

    # ── Check for activity (resets escalation) ──
    if _watchdog_has_activity "$change_name" "$last_activity"; then
        if [[ "$escalation_level" -gt 0 ]]; then
            log_info "Watchdog: $change_name recovered — resetting escalation from level $escalation_level"
        fi
        _watchdog_update "$change_name" "$now" "0" "0"
        return 0
    fi

    # ── Artifact creation grace: skip hash detection if loop-state.json absent ──
    # After dispatch, Ralph spends 1-2 min creating artifacts (proposal, design, specs, tasks)
    # before the loop starts and creates loop-state.json. Without this guard, the watchdog
    # sees identical hashes ("0:0:unknown") and escalates L1→L3 in ~30s (false positive kill).
    local wt_path_wd
    wt_path_wd=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    if [[ -n "$wt_path_wd" && ! -f "$wt_path_wd/.claude/loop-state.json" ]]; then
        # No loop-state yet — artifact creation phase. Skip hash detection.
        # Timeout check (below) with PID-alive guard remains active as safety net.
        return 0
    fi

    # ── Action hash loop detection ──
    local current_hash
    current_hash=$(_watchdog_action_hash "$change_name")
    local prev_hash
    prev_hash=$(echo "$wd_json" | jq -r '.action_hash_ring[-1] // ""')

    if [[ "$current_hash" == "$prev_hash" && -n "$current_hash" ]]; then
        consecutive_same=$((consecutive_same + 1))
    else
        consecutive_same=0
    fi

    # Append to ring buffer (keep last N)
    local tmp
    tmp=$(mktemp)
    jq --arg n "$change_name" --arg h "$current_hash" --argjson max "$WATCHDOG_HASH_RING_SIZE" \
        '(.changes[] | select(.name == $n) | .watchdog.action_hash_ring) |= (. + [$h] | .[-$max:])' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
    # Update consecutive count
    tmp=$(mktemp)
    jq --arg n "$change_name" --argjson c "$consecutive_same" \
        '(.changes[] | select(.name == $n) | .watchdog.consecutive_same_hash) = $c' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # ── Timeout check ──
    local timeout_secs
    timeout_secs=$(_watchdog_timeout_for_status "$status")
    local idle_secs=$((now - last_activity))

    local should_escalate=false

    # Loop detection triggers escalation
    if [[ "$consecutive_same" -ge "$WATCHDOG_LOOP_THRESHOLD" ]]; then
        log_warn "Watchdog: $change_name stuck in loop ($consecutive_same identical hashes)"
        should_escalate=true
    fi

    # Timeout triggers escalation (but only if Ralph PID is dead)
    if [[ "$idle_secs" -ge "$timeout_secs" ]]; then
        local ralph_pid
        ralph_pid=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .ralph_pid // 0' "$STATE_FILENAME")
        if [[ "$ralph_pid" -gt 0 ]] && kill -0 "$ralph_pid" 2>/dev/null; then
            # PID alive = long iteration, not stuck
            return 0
        fi
        log_warn "Watchdog: $change_name timeout (${idle_secs}s idle, threshold ${timeout_secs}s, PID $ralph_pid dead)"
        should_escalate=true
    fi

    if [[ "$should_escalate" == "true" ]]; then
        escalation_level=$((escalation_level + 1))
        _watchdog_escalate "$change_name" "$escalation_level"
        _watchdog_update "$change_name" "$now" "$escalation_level" "$consecutive_same"
    fi

    # ── Progress-based trend detection (independent of escalation) ──
    _watchdog_check_progress "$change_name"
}

# ─── Heartbeat ───────────────────────────────────────────────────────

# Emit a heartbeat event at the end of each poll cycle.
# Sentinel monitors events.jsonl mtime to detect orchestrator liveness.
watchdog_heartbeat() {
    local active_changes
    active_changes=$(jq '[.changes[] | select(.status == "running" or .status == "verifying" or .status == "dispatched")] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    local active_seconds
    active_seconds=$(jq -r '.active_seconds // 0' "$STATE_FILENAME" 2>/dev/null || echo 0)

    emit_event "WATCHDOG_HEARTBEAT" "" \
        "{\"active_changes\":$active_changes,\"active_seconds\":$active_seconds}"
}

# ─── Internal Helpers ────────────────────────────────────────────────

_watchdog_init() {
    local change_name="$1"
    local now
    now=$(date +%s)
    local tmp
    tmp=$(mktemp)
    jq --arg n "$change_name" --argjson now "$now" \
        '(.changes[] | select(.name == $n) | .watchdog) = {
            last_activity_epoch: $now,
            action_hash_ring: [],
            consecutive_same_hash: 0,
            escalation_level: 0
        }' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
}

_watchdog_update() {
    local change_name="$1"
    local activity_epoch="$2"
    local esc_level="$3"
    local consec="$4"
    local tmp
    tmp=$(mktemp)
    jq --arg n "$change_name" --argjson epoch "$activity_epoch" \
        --argjson esc "$esc_level" --argjson c "$consec" \
        '(.changes[] | select(.name == $n) | .watchdog) |=
            (.last_activity_epoch = $epoch | .escalation_level = $esc | .consecutive_same_hash = $c)' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
}

# Check if there's been activity since last_activity_epoch.
# Activity = tokens_used changed OR status changed (detected via mtime of loop-state.json).
_watchdog_has_activity() {
    local change_name="$1"
    local last_epoch="$2"

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    [[ -z "$wt_path" ]] && return 1

    local loop_state="$wt_path/.claude/loop-state.json"
    if [[ -f "$loop_state" ]]; then
        local mtime
        mtime=$(stat -c %Y "$loop_state" 2>/dev/null || echo 0)
        if [[ "$mtime" -gt "$last_epoch" ]]; then
            return 0
        fi
    fi

    return 1
}

# Compute action hash: MD5 of (loop-state mtime, tokens_used, ralph_status)
_watchdog_action_hash() {
    local change_name="$1"

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    local loop_state="${wt_path:-.}/.claude/loop-state.json"

    local mtime="0"
    [[ -f "$loop_state" ]] && mtime=$(stat -c %Y "$loop_state" 2>/dev/null || echo 0)

    local tokens
    tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME")

    local ralph_status="unknown"
    [[ -f "$loop_state" ]] && ralph_status=$(jq -r '.status // "unknown"' "$loop_state" 2>/dev/null)

    echo -n "${mtime}:${tokens}:${ralph_status}" | md5sum | cut -d' ' -f1
}

# Get timeout threshold for a given change status
_watchdog_timeout_for_status() {
    local status="$1"
    case "$status" in
        running)    echo "$WATCHDOG_TIMEOUT_RUNNING" ;;
        verifying)  echo "$WATCHDOG_TIMEOUT_VERIFYING" ;;
        dispatched) echo "$WATCHDOG_TIMEOUT_DISPATCHED" ;;
        *)          echo "$WATCHDOG_TIMEOUT_RUNNING" ;;
    esac
}

# Progress-based trend detection.
# Reads completed iterations from loop-state.json to detect:
#   - Spinning: 3+ consecutive no_op iterations with no commits → fail
#   - Stuck: 3+ consecutive iterations without commits (but not all no_op) → pause
# Replaces the old complexity-based token budget enforcement.
_watchdog_check_progress() {
    local change_name="$1"

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    local loop_state_file="$wt_path/.claude/loop-state.json"

    # Guard: loop-state must exist and be readable
    if [[ -z "$wt_path" || ! -f "$loop_state_file" ]]; then
        return 0
    fi

    # Guard: re-read change status — skip if already failed/paused/waiting by escalation
    local current_status
    current_status=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .status // ""' "$STATE_FILENAME" 2>/dev/null)
    case "$current_status" in
        failed|paused|waiting:budget) return 0 ;;
    esac

    # Guard: skip if loop already done or waiting for API recovery
    local loop_status
    loop_status=$(jq -r '.status // "unknown"' "$loop_state_file" 2>/dev/null)
    if [[ "$loop_status" == "done" || "$loop_status" == "waiting:api" ]]; then
        return 0
    fi

    # Read completed iterations array
    local iterations_json
    iterations_json=$(jq -c '.iterations // []' "$loop_state_file" 2>/dev/null) || return 0
    local total_iterations
    total_iterations=$(echo "$iterations_json" | jq 'length')

    # Guard: need at least 2 completed iterations
    if [[ "$total_iterations" -lt 2 ]]; then
        return 0
    fi

    # Guard: progress baseline — only examine iterations after resume baseline
    local baseline
    baseline=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .watchdog.progress_baseline // 0' "$STATE_FILENAME" 2>/dev/null)
    [[ -z "$baseline" || "$baseline" == "null" ]] && baseline=0

    # Filter to iterations after baseline and get tail 3
    local tail_json
    tail_json=$(echo "$iterations_json" | jq --argjson b "$baseline" \
        '[.[] | select(.n > $b)] | .[-3:]')
    local tail_count
    tail_count=$(echo "$tail_json" | jq 'length')

    # Need at least 3 post-baseline iterations to detect patterns
    if [[ "$tail_count" -lt 3 ]]; then
        return 0
    fi

    # Check if all tail iterations have empty commits
    local all_no_commits
    all_no_commits=$(echo "$tail_json" | jq 'all(.commits == [] or .commits == null)')
    if [[ "$all_no_commits" != "true" ]]; then
        # Progress detected — recent commits exist
        return 0
    fi

    # All tail iterations have no commits — determine pattern
    local all_no_op
    all_no_op=$(echo "$tail_json" | jq 'all(.no_op == true)')

    # TOCTOU guard: re-read loop-state status before taking action
    local recheck_status
    recheck_status=$(jq -r '.status // "unknown"' "$loop_state_file" 2>/dev/null)
    if [[ "$recheck_status" == "done" ]]; then
        return 0
    fi

    if [[ "$all_no_op" == "true" ]]; then
        # Spinning: all no_op=true AND no commits → fail
        log_error "Watchdog: $change_name spinning — $tail_count consecutive no-op iterations, failing"
        emit_event "WATCHDOG_NO_PROGRESS" "$change_name" \
            "{\"pattern\":\"spinning\",\"action\":\"fail\",\"iterations\":$tail_count}"
        _watchdog_salvage_partial_work "$change_name"
        update_change_field "$change_name" "status" '"failed"'
        send_notification "wt-orchestrate" "Watchdog: '$change_name' spinning — $tail_count consecutive no-op iterations, failing" "critical"
    else
        # Stuck: no commits but some iterations had no_op=false → pause
        log_warn "Watchdog: $change_name stuck — $tail_count iterations without commits, pausing"
        emit_event "WATCHDOG_NO_PROGRESS" "$change_name" \
            "{\"pattern\":\"stuck\",\"action\":\"pause\",\"iterations\":$tail_count}"
        pause_change "$change_name" || true
        send_notification "wt-orchestrate" "Watchdog: '$change_name' stuck — $tail_count iterations without commits, pausing" "normal"
    fi
}

# Escalation chain: level 1=warn, 2=resume, 3=kill+resume, 4=fail
_watchdog_escalate() {
    local change_name="$1"
    local level="$2"

    case "$level" in
        1)
            log_warn "Watchdog: $change_name escalation level 1 — warning"
            emit_event "WATCHDOG_WARN" "$change_name" "{\"level\":1}"
            ;;
        2)
            log_warn "Watchdog: $change_name escalation level 2 — resuming"
            emit_event "WATCHDOG_RESUME" "$change_name" "{\"level\":2}"
            resume_change "$change_name" || true
            ;;
        3)
            log_error "Watchdog: $change_name escalation level 3 — killing and resuming"
            emit_event "WATCHDOG_KILL" "$change_name" "{\"level\":3}"
            # Kill Ralph PID
            local ralph_pid
            ralph_pid=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .ralph_pid // 0' "$STATE_FILENAME")
            if [[ "$ralph_pid" -gt 0 ]] && kill -0 "$ralph_pid" 2>/dev/null; then
                kill -TERM "$ralph_pid" 2>/dev/null || true
                sleep 2
                kill -0 "$ralph_pid" 2>/dev/null && kill -KILL "$ralph_pid" 2>/dev/null || true
                log_info "Watchdog: killed Ralph PID $ralph_pid for $change_name"
            fi
            resume_change "$change_name" || true
            ;;
        *)
            # Level 4+: give up — salvage partial work first
            _watchdog_salvage_partial_work "$change_name"
            log_error "Watchdog: $change_name escalation level $level — marking failed"
            emit_event "WATCHDOG_FAILED" "$change_name" "{\"level\":$level}"
            update_change_field "$change_name" "status" '"failed"'
            send_notification "wt-orchestrate" "Watchdog: change '$change_name' failed after escalation level $level" "critical"
            ;;
    esac
}

# Capture partial work from a failing change's worktree before marking failed.
# Saves git diff as partial-diff.patch and records modified files list in state.
_watchdog_salvage_partial_work() {
    local change_name="$1"

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    [[ -z "$wt_path" || ! -d "$wt_path" ]] && return 0

    # Capture diff (staged + unstaged) relative to HEAD
    local diff_output
    diff_output=$(cd "$wt_path" && git diff HEAD 2>/dev/null || true)
    if [[ -z "$diff_output" ]]; then
        log_info "Watchdog: no partial work to salvage for $change_name"
        return 0
    fi

    # Save patch file in worktree
    local patch_file="$wt_path/partial-diff.patch"
    echo "$diff_output" > "$patch_file"

    # Record modified files list in state
    local modified_files
    modified_files=$(cd "$wt_path" && git diff HEAD --name-only 2>/dev/null | jq -R -s 'split("\n") | map(select(length > 0))' || echo '[]')
    local tmp
    tmp=$(mktemp)
    jq --arg n "$change_name" --argjson files "$modified_files" --arg patch "$patch_file" \
        '(.changes[] | select(.name == $n)) |= (
            .partial_diff_patch = $patch |
            .partial_diff_files = $files
        )' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    local file_count
    file_count=$(echo "$modified_files" | jq 'length')
    log_info "Watchdog: salvaged partial work for $change_name ($file_count files, patch at $patch_file)"
    emit_event "WATCHDOG_SALVAGE" "$change_name" "{\"files\":$file_count,\"patch\":\"$patch_file\"}"
}
