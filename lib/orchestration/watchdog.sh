#!/usr/bin/env bash
# lib/orchestration/watchdog.sh — Self-healing watchdog for orchestration
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: events.sh (emit_event), state.sh (update_change_field, jq on STATE_FILENAME)
#
# Per-change watchdog state stored in orchestration-state.json:
#   .changes[].watchdog = {
#     last_activity_epoch, action_hash_ring[], consecutive_same_hash, escalation_level
#   }

# ─── Configuration ───────────────────────────────────────────────────

# Per-state timeout defaults (seconds). Overridden by watchdog_timeout directive.
WATCHDOG_TIMEOUT_RUNNING=600
WATCHDOG_TIMEOUT_VERIFYING=300
WATCHDOG_TIMEOUT_DISPATCHED=120

# Loop detection: consecutive identical action hashes before declaring stuck
WATCHDOG_LOOP_THRESHOLD=5
WATCHDOG_HASH_RING_SIZE=5

# Per-change token budget (0 = use complexity-based defaults)
# Overridden by max_tokens_per_change directive.
WATCHDOG_MAX_TOKENS_PER_CHANGE=0

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

    # ── Token budget enforcement (independent of escalation) ──
    _watchdog_check_token_budget "$change_name"
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

# Per-change token budget enforcement.
# Complexity-based defaults: S=2M, M=5M, L=10M, XL=20M.
# Warn at 80%, pause at 100%, fail at 120%.
_watchdog_check_token_budget() {
    local change_name="$1"

    local limit
    limit=$(_watchdog_token_limit_for_change "$change_name")
    [[ "$limit" -le 0 ]] && return 0

    local tokens_used
    tokens_used=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME")

    local pct=0
    [[ "$limit" -gt 0 ]] && pct=$(( (tokens_used * 100) / limit ))

    # Before pausing/failing, check if loop already finished (race: watchdog runs
    # in the same poll cycle as poll_change, Ralph may have written "done" by now)
    if [[ "$pct" -ge 100 ]]; then
        local wt_path
        wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        local loop_state_file="$wt_path/.claude/loop-state.json"
        if [[ -n "$wt_path" && -f "$loop_state_file" ]]; then
            local loop_status
            loop_status=$(jq -r '.status // "unknown"' "$loop_state_file" 2>/dev/null)
            if [[ "$loop_status" == "done" ]]; then
                log_info "Watchdog: $change_name budget at ${pct}% but loop already done — skipping pause"
                return 0
            fi
        fi
    fi

    if [[ "$pct" -ge 120 ]]; then
        _watchdog_salvage_partial_work "$change_name"
        log_error "Watchdog: $change_name token budget exceeded (${tokens_used}/${limit}, ${pct}%) — marking failed"
        emit_event "WATCHDOG_TOKEN_BUDGET" "$change_name" "{\"tokens_used\":$tokens_used,\"limit\":$limit,\"pct\":$pct,\"action\":\"fail\"}"
        update_change_field "$change_name" "status" '"failed"'
        send_notification "wt-orchestrate" "Token budget exceeded for '$change_name' (${pct}%)" "critical"
    elif [[ "$pct" -ge 100 ]]; then
        log_warn "Watchdog: $change_name token budget reached (${tokens_used}/${limit}, ${pct}%) — pausing"
        emit_event "WATCHDOG_TOKEN_BUDGET" "$change_name" "{\"tokens_used\":$tokens_used,\"limit\":$limit,\"pct\":$pct,\"action\":\"pause\"}"
        pause_change "$change_name" || true
    elif [[ "$pct" -ge 80 ]]; then
        # Only warn once per threshold crossing — check if we already warned
        local prev_warned
        prev_warned=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .watchdog.token_budget_warned // false' "$STATE_FILENAME" 2>/dev/null)
        if [[ "$prev_warned" != "true" ]]; then
            log_warn "Watchdog: $change_name token budget warning (${tokens_used}/${limit}, ${pct}%)"
            emit_event "WATCHDOG_TOKEN_BUDGET" "$change_name" "{\"tokens_used\":$tokens_used,\"limit\":$limit,\"pct\":$pct,\"action\":\"warn\"}"
            local tmp
            tmp=$(mktemp)
            jq --arg n "$change_name" \
                '(.changes[] | select(.name == $n) | .watchdog.token_budget_warned) = true' \
                "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
        fi
    fi
}

# Get token limit for a change. Priority: WATCHDOG_MAX_TOKENS_PER_CHANGE > complexity-based default.
_watchdog_token_limit_for_change() {
    local change_name="$1"

    # Explicit directive overrides everything
    if [[ "${WATCHDOG_MAX_TOKENS_PER_CHANGE:-0}" -gt 0 ]]; then
        echo "$WATCHDOG_MAX_TOKENS_PER_CHANGE"
        return
    fi

    # Complexity-based defaults (calibrated from E2E data:
    # S tasks routinely use 1-1.5M, M tasks 2-3M with artifact creation overhead)
    local complexity
    complexity=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .complexity // "M"' "$STATE_FILENAME" 2>/dev/null)
    case "$complexity" in
        S)  echo 2000000 ;;
        M)  echo 5000000 ;;
        L)  echo 10000000 ;;
        XL) echo 20000000 ;;
        *)  echo 5000000 ;;
    esac
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
