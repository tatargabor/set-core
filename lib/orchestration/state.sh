#!/usr/bin/env bash
# lib/orchestration/state.sh — State initialization, queries, notifications, status
# Dependencies: config.sh, utils.sh must be sourced first
# Sourced by bin/wt-orchestrate

init_state() {
    local plan_file="$1"

    wt-orch-core state init --plan-file "$plan_file" --output "$STATE_FILENAME"

    local change_count plan_version
    change_count=$(jq '.changes | length' "$STATE_FILENAME")
    plan_version=$(jq -r '.plan_version' "$STATE_FILENAME")
    log_info "State initialized with $change_count changes (plan v$plan_version)"

    # Initialize phase tracking from change phase assignments
    _init_phase_state
}

# Apply phase overrides from directives.
# Called after init_state if milestones.phase_overrides is set.
# Migrated to: wt_orch/state.py apply_phase_overrides()
# Kept as jq — phase overrides use JSON arg from bash caller, simpler to keep inline
apply_phase_overrides() {
    local overrides_json="$1"  # JSON object: {"change-name": phase_number, ...}

    [[ -z "$overrides_json" || "$overrides_json" == "null" || "$overrides_json" == "{}" ]] && return 0

    log_info "Applying phase overrides: $overrides_json"

    # Update each change's phase field
    with_state_lock safe_jq_update "$STATE_FILENAME" --argjson ov "$overrides_json" '
        .changes = [.changes[] |
            if $ov[.name] then .phase = $ov[.name] else . end
        ]
    '

    # Recalculate phases object
    _init_phase_state
}

# Initialize phase state from change phase fields.
# Computes unique phases, creates the phases object, sets current_phase.
# Migrated to: wt_orch/state.py init_phase_state()
# Kept as jq — called during init_state which already uses Python for the main init
_init_phase_state() {
    local phases_json
    phases_json=$(jq -c '
        [.changes[].phase // 1] | unique | sort | . as $phases |
        if ($phases | length) <= 1 then null
        else
            {
                current_phase: $phases[0],
                phases: (reduce $phases[] as $p ({};
                    .[$p | tostring] = {
                        status: (if $p == $phases[0] then "running" else "pending" end),
                        tag: null,
                        server_port: null,
                        server_pid: null,
                        completed_at: null
                    }
                ))
            }
        end
    ' "$STATE_FILENAME")

    if [[ "$phases_json" != "null" && -n "$phases_json" ]]; then
        local phase_count
        phase_count=$(echo "$phases_json" | jq '.phases | length')
        with_state_lock safe_jq_update "$STATE_FILENAME" --argjson pd "$phases_json" \
            '.current_phase = $pd.current_phase | .phases = $pd.phases'
        log_info "Phase state initialized: $phase_count phases, starting at phase $(echo "$phases_json" | jq '.current_phase')"
    fi
}

# Update a top-level field in state (locked + validated)
# Migrated to: wt_orch/state.py update_state_field()
update_state_field() {
    local field="$1"
    local value="$2"
    wt-orch-core state update-field --file "$STATE_FILENAME" --field "$field" --value "$value"
}

# Update a change's field in state (locked + validated)
# Automatically emits STATE_CHANGE event when status field changes
# Migrated to: wt_orch/state.py update_change_field()
update_change_field() {
    local change_name="$1"
    local field="$2"
    local value="$3"
    wt-orch-core state update-change --file "$STATE_FILENAME" --name "$change_name" --field "$field" --value "$value"
}

# Get a change's status
# Migrated to: wt_orch/state.py get_change_status()
get_change_status() {
    local change_name="$1"
    wt-orch-core state get-status --file "$STATE_FILENAME" --name "$change_name"
}

# Get all changes with a specific status
# Migrated to: wt_orch/state.py get_changes_by_status()
get_changes_by_status() {
    local status="$1"
    wt-orch-core state changes-by-status --file "$STATE_FILENAME" --status "$status"
}

# Count changes with a specific status
# Migrated to: wt_orch/state.py count_changes_by_status()
count_changes_by_status() {
    local status="$1"
    wt-orch-core state count-by-status --file "$STATE_FILENAME" --status "$status"
}

# Check if all depends_on for a change are merged
# Migrated to: wt_orch/state.py deps_satisfied()
deps_satisfied() {
    local change_name="$1"
    wt-orch-core state deps-satisfied --file "$STATE_FILENAME" --name "$change_name"
}

# Check if any depends_on for a change has failed (terminal state)
# Returns 0 if a dependency is truly failed, 1 otherwise
# Note: merge-blocked is NOT a failure — the work is done, only merge is stuck.
# Migrated to: wt_orch/state.py deps_failed()
# Kept as jq — no CLI bridge needed (rarely called, only by cascade_failed_deps)
deps_failed() {
    local change_name="$1"
    local deps
    deps=$(jq -r --arg name "$change_name" \
        '.changes[] | select(.name == $name) | .depends_on[]?' "$STATE_FILENAME" 2>/dev/null)

    [[ -z "$deps" ]] && return 1  # no dependencies → not failed

    while IFS= read -r dep; do
        local dep_status
        dep_status=$(get_change_status "$dep")
        if [[ "$dep_status" == "failed" ]]; then
            return 0
        fi
    done <<< "$deps"

    return 1
}

# Cascade failure: mark pending changes as failed if their dependencies have failed.
# Migrated to: wt_orch/state.py cascade_failed_deps()
cascade_failed_deps() {
    local cascaded
    cascaded=$(wt-orch-core state cascade-failed --file "$STATE_FILENAME")
    [[ "$cascaded" -gt 0 ]] && log_info "Cascade: $cascaded changes marked failed due to dependency failures"
    return 0
}

# ─── Phase Management ────────────────────────────────────────────────
# Migrated to: wt_orch/state.py init_phase_state(), apply_phase_overrides(),
# all_phase_changes_terminal(), advance_phase()

# Check if all changes in the current phase are terminal (merged/failed/skipped).
all_phase_changes_terminal() {
    local phase="$1"
    local non_terminal
    non_terminal=$(jq --argjson p "$phase" '
        [.changes[] | select(.phase == $p) |
            select(.status != "merged" and .status != "failed" and .status != "skipped" and .status != "done")]
        | length
    ' "$STATE_FILENAME" 2>/dev/null)
    [[ "${non_terminal:-1}" -eq 0 ]]
}

# Advance to the next phase. Returns 0 if advanced, 1 if no more phases.
# Migrated to: wt_orch/state.py advance_phase()
advance_phase() {
    wt-orch-core state advance-phase --file "$STATE_FILENAME"
}

# ─── Dependency Graph ────────────────────────────────────────────────

# Topological sort of changes (returns names in execution order)
# Migrated to: wt_orch/state.py topological_sort()
topological_sort() {
    local plan_file="$1"
    wt-orch-core state topo-sort --plan-file "$plan_file"
}

# ─── Quality Gate Hooks ──────────────────────────────────────────────

# Run a lifecycle hook if configured.
# Args: hook_name, change_name, status, worktree_path
# Returns: 0 if hook passes or not configured, 1 if hook blocks the transition.
run_hook() {
    local hook_name="$1"
    local change_name="$2"
    local status="${3:-}"
    local wt_path="${4:-}"

    # Look up hook script path from directives (stored as global by monitor_loop)
    local hook_key="hook_${hook_name}"
    local hook_script="${!hook_key:-}"  # Indirect variable reference
    [[ -z "$hook_script" ]] && return 0
    [[ ! -x "$hook_script" ]] && {
        log_warn "Hook $hook_name: script not executable: $hook_script"
        return 0
    }

    log_info "Running hook $hook_name for $change_name: $hook_script"
    local hook_stderr
    hook_stderr=$(mktemp)
    if "$hook_script" "$change_name" "$status" "$wt_path" 2>"$hook_stderr"; then
        log_info "Hook $hook_name passed for $change_name"
        rm -f "$hook_stderr"
        return 0
    else
        local reason
        reason=$(cat "$hook_stderr" 2>/dev/null || echo "unknown")
        rm -f "$hook_stderr"
        log_error "Hook $hook_name blocked $change_name: $reason"
        emit_event "HOOK_BLOCKED" "$change_name" "{\"hook\":\"$hook_name\",\"reason\":$(printf '%s' "$reason" | jq -Rs .)}"
        return 1
    fi
}

# ─── Notifications ───────────────────────────────────────────────────

send_notification() {
    local title="$1"
    local body="$2"
    local urgency="${3:-normal}"  # normal or critical

    local notification_type="$DEFAULT_NOTIFICATION"
    # Only resolve from INPUT_PATH if already set — do NOT call find_input here
    # as it mutates global INPUT_MODE/INPUT_PATH mid-run
    if [[ -n "${INPUT_PATH:-}" && -f "$INPUT_PATH" ]]; then
        notification_type=$(resolve_directives "$INPUT_PATH" | jq -r '.notification')
    fi

    if [[ "$notification_type" == "none" ]]; then
        log_info "Notification [$urgency]: $title — $body"
        return 0
    fi

    # Desktop channel: notify-send
    if [[ "$notification_type" == *"desktop"* ]] && command -v notify-send &>/dev/null; then
        notify-send -u "$urgency" "$title" "$body" 2>/dev/null || true
    fi

    # Email channel: send via Resend API (requires .env with RESEND_* vars)
    if [[ "$notification_type" == *"email"* ]] && type send_email &>/dev/null; then
        local project_name
        project_name="$(basename "$(pwd)")"
        local email_prefix="[info]"
        [[ "$urgency" == "critical" ]] && email_prefix="[CRITICAL]"
        send_email "$email_prefix $title — $project_name" \
            "<h3>$title</h3><p>$body</p><p style='color:#888;font-size:12px;'>$(date '+%Y-%m-%d %H:%M:%S') | $project_name | $urgency</p>" \
            2>/dev/null || true
    fi

    log_info "Notification [$urgency]: $title — $body"
}

# ─── Memory Helpers ──────────────────────────────────────────────────

# Cumulative memory operation stats (reset per orchestration run)
_MEM_OPS_COUNT=0
_MEM_OPS_TOTAL_MS=0
_MEM_RECALL_COUNT=0
_MEM_RECALL_TOTAL_MS=0

cmd_status() {
    if [[ ! -f "$STATE_FILENAME" ]]; then
        if [[ -f "$PLAN_FILENAME" ]]; then
            info "Plan exists but orchestrator hasn't started. Run 'wt-orchestrate start'."
            cmd_plan --show
        else
            info "No orchestration state. Run 'wt-orchestrate plan' to create a plan."
        fi
        return 0
    fi

    local status
    status=$(jq -r '.status' "$STATE_FILENAME")
    local plan_version
    plan_version=$(jq -r '.plan_version' "$STATE_FILENAME")
    local total
    total=$(jq '.changes | length' "$STATE_FILENAME")
    local merged
    merged=$(count_changes_by_status "merged")
    local done_count
    done_count=$(count_changes_by_status "done")
    local running
    running=$(count_changes_by_status "running")
    local pending
    pending=$(count_changes_by_status "pending")
    local failed
    failed=$(count_changes_by_status "failed")
    local stalled
    stalled=$(count_changes_by_status "stalled")

    # Detect stale "running" status (process crashed without cleanup)
    if [[ "$status" == "running" ]]; then
        local state_mtime now_epoch staleness
        state_mtime=$(stat -c %Y "$STATE_FILENAME" 2>/dev/null || stat -f %m "$STATE_FILENAME" 2>/dev/null || echo 0)
        now_epoch=$(date +%s)
        staleness=$((now_epoch - state_mtime))
        if [[ "$staleness" -gt 120 ]]; then
            status="stopped (stale — process crashed ~$(format_duration "$staleness") ago)"
            update_state_field "status" '"stopped"'
        fi
    fi

    echo ""
    info "═══ Orchestrator Status ═══"
    echo ""
    local plan_phase plan_method
    plan_phase=$(jq -r '.plan_phase // "initial"' "$STATE_FILENAME")
    plan_method=$(jq -r '.plan_method // "api"' "$STATE_FILENAME")
    echo "  Status:   $status (plan v$plan_version, $plan_phase/$plan_method)"
    local verifying
    verifying=$(count_changes_by_status "verifying")
    local verify_failed
    verify_failed=$(count_changes_by_status "verify-failed")

    local skipped
    skipped=$(count_changes_by_status "skipped")

    echo "  Progress: $merged merged, $done_count done, $running running, $pending pending"
    [[ "$skipped" -gt 0 ]] && echo "  Skipped:  $skipped"
    [[ "$verifying" -gt 0 ]] && echo "  Verifying: $verifying"
    [[ "$verify_failed" -gt 0 ]] && echo "  Verify-failed: $verify_failed"
    [[ "$failed" -gt 0 ]] && echo "  Failed:   $failed"
    [[ "$stalled" -gt 0 ]] && echo "  Stalled:  $stalled"

    # Milestone phase display
    local has_phases
    has_phases=$(jq 'has("phases")' "$STATE_FILENAME" 2>/dev/null)
    if [[ "$has_phases" == "true" ]]; then
        local current_phase total_phases
        current_phase=$(jq -r '.current_phase // 1' "$STATE_FILENAME")
        total_phases=$(jq '.phases | length' "$STATE_FILENAME")
        echo "  Milestones: Phase $current_phase/$total_phases"

        # Compact per-phase summary
        while IFS=$'\t' read -r pnum pstatus pport ppid; do
            [[ -z "$pnum" ]] && continue
            local phase_info="    Phase $pnum: $pstatus"
            if [[ -n "$ppid" && "$ppid" != "null" ]] && kill -0 "$ppid" 2>/dev/null; then
                phase_info+=" (http://localhost:$pport)"
            fi
            echo "$phase_info"
        done < <(jq -r '.phases | to_entries | sort_by(.key | tonumber) | .[] | "\(.key)\t\(.value.status // "pending")\t\(.value.server_port // "null")\t\(.value.server_pid // "null")"' "$STATE_FILENAME" 2>/dev/null || true)
    fi

    local waiting_budget
    waiting_budget=$(count_changes_by_status "waiting:budget")
    local budget_exceeded
    budget_exceeded=$(count_changes_by_status "budget_exceeded")
    local total_budget=$((waiting_budget + budget_exceeded))
    [[ "$total_budget" -gt 0 ]] && echo "  ⏸ Budget: $total_budget waiting for budget approval"

    local waiting_human
    waiting_human=$(count_changes_by_status "waiting:human")
    [[ "$waiting_human" -gt 0 ]] && echo "  ⏸ Human:  $waiting_human waiting for manual input"

    local replan_cycle
    replan_cycle=$(jq '.replan_cycle // 0' "$STATE_FILENAME" 2>/dev/null)
    [[ "$replan_cycle" -gt 0 ]] && echo "  Replan:   cycle $replan_cycle"

    # Show elapsed time (wall clock + active) and remaining limit
    local started_epoch
    started_epoch=$(jq -r '.started_epoch // 0' "$STATE_FILENAME" 2>/dev/null)
    local limit_secs
    limit_secs=$(jq -r '.time_limit_secs // 0' "$STATE_FILENAME" 2>/dev/null)
    local active_secs
    active_secs=$(jq -r '.active_seconds // 0' "$STATE_FILENAME" 2>/dev/null)
    if [[ "$started_epoch" -gt 0 ]]; then
        local now wall_elapsed
        now=$(date +%s)
        wall_elapsed=$((now - started_epoch))
        local time_info="  Active:   $(format_duration "$active_secs")"
        if [[ "$limit_secs" -gt 0 ]]; then
            local remaining=$((limit_secs - active_secs))
            if [[ "$remaining" -gt 0 ]]; then
                time_info="$time_info / $(format_duration "$limit_secs") limit ($(format_duration "$remaining") remaining)"
            else
                time_info="$time_info / $(format_duration "$limit_secs") limit (exceeded)"
            fi
        fi
        echo "$time_info"
        # Show wall clock if different from active (indicates wait time)
        if [[ "$wall_elapsed" -gt $((active_secs + 120)) ]]; then
            local wait_time=$((wall_elapsed - active_secs))
            echo "  Wall:     $(format_duration "$wall_elapsed") ($(format_duration "$wait_time") idle/waiting)"
        fi
    fi

    if [[ "$status" == "time_limit" ]]; then
        echo "  Note:     Stopped by time limit. Run 'wt-orchestrate start' to continue."
    fi

    # Input staleness check
    local stored_path
    stored_path=$(jq -r '.input_path // empty' "$STATE_FILENAME" 2>/dev/null)
    [[ -z "$stored_path" ]] && stored_path=$(jq -r '.input_path // empty' "$PLAN_FILENAME" 2>/dev/null)
    if [[ -z "$stored_path" ]]; then
        # Legacy: try find_brief for old state files
        stored_path=$(find_brief 2>/dev/null)
    fi
    if [[ -n "$stored_path" && -f "$stored_path" ]]; then
        local current_hash
        current_hash=$(brief_hash "$stored_path")
        local stored_hash
        stored_hash=$(jq -r '.brief_hash' "$STATE_FILENAME")
        if [[ "$current_hash" != "$stored_hash" ]]; then
            warn "  Input has changed since plan was created. Consider: wt-orchestrate replan"
        fi
    fi

    echo ""
    # Per-change table
    printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "Change" "Status" "Progress" "Tests" "Review" "Tokens" "Gate Cost"
    printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "─────────────────────────" "──────────────" "───────────────" "────────" "────────" "──────────" "──────────────"

    jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used)\t\(.test_result // "-")\t\(.review_result // "-")\t\(.gate_total_ms // 0)\t\(.gate_retry_tokens // 0)\t\(.gate_retry_count // 0)\t\(.redispatch_count // 0)"' "$STATE_FILENAME" | \
    while IFS=$'\t' read -r name change_status tokens test_res review_res g_ms g_rtok g_rcnt redisp_cnt; do
        # Append redispatch indicator to status
        local display_status="$change_status"
        if [[ "${redisp_cnt:-0}" -gt 0 ]]; then
            display_status="${change_status} (R${redisp_cnt}/${MAX_REDISPATCH:-2})"
        fi
        local progress="-"
        # Try to read iteration progress from worktree
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        if [[ -n "$wt_path" && -f "$wt_path/.wt/loop-state.json" ]]; then
            local iter max_iter
            iter=$(jq -r '.current_iteration // 0' "$wt_path/.wt/loop-state.json" 2>/dev/null)
            max_iter=$(jq -r '.max_iterations // "?"' "$wt_path/.wt/loop-state.json" 2>/dev/null)
            progress="iter $iter/$max_iter"
        fi
        # Format gate cost column
        local gate_col="-"
        if [[ "$g_ms" -gt 0 ]]; then
            local g_secs=$(( g_ms / 1000 ))
            local g_frac=$(( (g_ms % 1000) / 100 ))
            gate_col="${g_secs}.${g_frac}s"
            if [[ "$g_rcnt" -gt 0 ]]; then
                local rtok_k=$(( g_rtok / 1000 ))
                gate_col="${gate_col} +${rtok_k}k"
            fi
        fi
        printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "$name" "$display_status" "$progress" "$test_res" "$review_res" "$tokens" "$gate_col"
    done

    # Manual task hints for waiting:human changes
    if [[ "$waiting_human" -gt 0 ]]; then
        echo ""
        info "⏸ Changes waiting for manual input:"
        jq -r '.changes[] | select(.status == "waiting:human") | .name' "$STATE_FILENAME" | while read -r wh_name; do
            local wh_wt
            wh_wt=$(jq -r --arg n "$wh_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
            local wh_summary=""
            if [[ -n "$wh_wt" && -f "$wh_wt/.wt/loop-state.json" ]]; then
                wh_summary=$(jq -r '.manual_tasks[0]? | "[\(.id)] \(.description)"' "$wh_wt/.wt/loop-state.json" 2>/dev/null)
            fi
            echo "  $wh_name: ${wh_summary:-details unavailable}"
            echo "    → wt-manual show $wh_name"
        done
    fi

    # Merge queue
    local queue_size
    queue_size=$(jq '.merge_queue | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$queue_size" -gt 0 ]]; then
        echo ""
        info "Merge queue ($queue_size):"
        jq -r '.merge_queue[]' "$STATE_FILENAME" | while read -r name; do
            echo "  - $name"
        done
    fi

    # Total tokens (with per-type breakdown)
    local total_tokens total_in total_out total_cr total_cc
    total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
    total_in=$(jq '[.changes[].input_tokens // 0] | add // 0' "$STATE_FILENAME")
    total_out=$(jq '[.changes[].output_tokens // 0] | add // 0' "$STATE_FILENAME")
    total_cr=$(jq '[.changes[].cache_read_tokens // 0] | add // 0' "$STATE_FILENAME")
    total_cc=$(jq '[.changes[].cache_create_tokens // 0] | add // 0' "$STATE_FILENAME")
    echo ""
    # Per-phase token breakdown when milestones exist and >1 phase
    local phase_token_breakdown=""
    if [[ "$has_phases" == "true" ]]; then
        local pt_parts=()
        while IFS=$'\t' read -r pt_num pt_tok; do
            [[ -z "$pt_num" ]] && continue
            pt_parts+=("P${pt_num}: ${pt_tok}")
        done < <(jq -r '[.changes | group_by(.phase // 1)[] | {phase: .[0].phase // 1, tokens: ([.[].tokens_used // 0] | add // 0)}] | sort_by(.phase) | .[] | "\(.phase)\t\(.tokens)"' "$STATE_FILENAME" 2>/dev/null || true)
        if [[ ${#pt_parts[@]} -gt 1 ]]; then
            phase_token_breakdown=" ($(IFS=', '; echo "${pt_parts[*]}"))"
        fi
    fi
    echo "  Total tokens: ${total_tokens}${phase_token_breakdown} (in:$total_in out:$total_out cr:$total_cr cc:$total_cc)"

    # Aggregate gate costs
    local agg_gate_ms agg_retry_tok agg_retry_cnt agg_gated
    agg_gate_ms=$(jq '[.changes[].gate_total_ms // 0] | add // 0' "$STATE_FILENAME")
    agg_retry_tok=$(jq '[.changes[].gate_retry_tokens // 0] | add // 0' "$STATE_FILENAME")
    agg_retry_cnt=$(jq '[.changes[].gate_retry_count // 0] | add // 0' "$STATE_FILENAME")
    agg_gated=$(jq '[.changes[] | select((.gate_total_ms // 0) > 0)] | length' "$STATE_FILENAME")
    if [[ "$agg_gated" -gt 0 ]]; then
        local agg_secs=$((agg_gate_ms / 1000))
        local agg_frac=$(( (agg_gate_ms % 1000) / 100 ))
        local rtok_k=$((agg_retry_tok / 1000))
        local gate_pct=0
        [[ "$active_secs" -gt 0 ]] && gate_pct=$((agg_gate_ms * 100 / (active_secs * 1000)))
        echo "  Gate cost:  ${agg_secs}.${agg_frac}s across $agg_gated changes (${gate_pct}% of active), ${agg_retry_cnt} retries (+${rtok_k}k tokens)"
    fi
    echo ""
}

# Internal: approve checkpoint under state lock
_approve_checkpoint_locked() {
    safe_jq_update "$STATE_FILENAME" '(.checkpoints[-1]).approved = true'
    safe_jq_update "$STATE_FILENAME" '.status = "running"'
}

cmd_approve() {
    local merge_flag=false
    local change_name=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --merge) merge_flag=true; shift ;;
            -*) error "Unknown option: $1"; return 1 ;;
            *) change_name="$1"; shift ;;
        esac
    done

    if [[ ! -f "$STATE_FILENAME" ]]; then
        error "No orchestration state found."
        return 1
    fi

    # Per-change approval (e.g., unblocking a merge-blocked change)
    if [[ -n "$change_name" ]]; then
        local cs
        cs=$(get_change_status "$change_name" 2>/dev/null || true)
        if [[ "$cs" == "merge-blocked" ]]; then
            update_change_field "$change_name" "status" '"merge-blocked"'
            update_change_field "$change_name" "merge_retry_count" "0"
            update_change_field "$change_name" "last_conflict_fingerprint" '""'
            log_info "Change $change_name unblocked — merge retry count reset"
            success "Change '$change_name' unblocked — will retry merge on next poll cycle"
            return 0
        elif [[ -z "$cs" ]]; then
            error "Change '$change_name' not found"
            return 1
        else
            warn "Change '$change_name' is not merge-blocked (status: $cs)"
            return 1
        fi
    fi

    local status
    status=$(jq -r '.status' "$STATE_FILENAME")
    if [[ "$status" == "plan_review" ]]; then
        update_state_field "status" '"running"'
        log_info "Plan approved — ready for dispatch"
        success "Plan approved — run 'wt-orchestrate start' to begin dispatch"
        return 0
    fi
    if [[ "$status" != "checkpoint" ]]; then
        warn "Orchestrator is not waiting for approval (status: $status)"
        return 1
    fi

    # Mark latest checkpoint as approved + resume (under single lock)
    with_state_lock _approve_checkpoint_locked

    log_info "Checkpoint approved (merge=$merge_flag)"
    success "Checkpoint approved"

    if $merge_flag; then
        info "Executing merge queue..."
        execute_merge_queue
    fi
}

# ─── Checkpoint & Summary ────────────────────────────────────────────

# Internal: add checkpoint + reset counter under state lock
_trigger_checkpoint_locked() {
    local reason="$1"
    safe_jq_update "$STATE_FILENAME" --arg at "$(date -Iseconds)" --arg reason "$reason" \
        '.checkpoints += [{at: $at, type: $reason, approved: false}]'
    safe_jq_update "$STATE_FILENAME" '.changes_since_checkpoint = 0'
}

trigger_checkpoint() {
    local reason="$1"

    log_info "Checkpoint triggered: $reason"
    emit_event "CHECKPOINT" "" "{\"reason\":\"$reason\"}"

    # Generate summary (non-fatal — don't let summary crash kill the orchestrator)
    generate_summary "$reason" || log_warn "Summary generation failed (non-fatal)"

    # Add checkpoint to state + reset counter (single lock)
    with_state_lock _trigger_checkpoint_locked "$reason"

    # Send notification (reads are non-critical, outside lock)
    local total
    total=$(jq '.changes | length' "$STATE_FILENAME" 2>/dev/null || echo 0)  # expected: state may be mid-write
    local done_count
    done_count=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    local running
    running=$(count_changes_by_status "running")
    send_notification "wt-orchestrate" "Checkpoint ($reason): $done_count/$total done, $running running. Run 'wt-orchestrate approve' to continue."

    # Auto-approve if directive is set (unattended/E2E mode)
    # Exception: mcp_auth checkpoints require human action (browser OAuth) and cannot be auto-approved
    if [[ "${CHECKPOINT_AUTO_APPROVE:-false}" == "true" ]] && [[ "$reason" == "mcp_auth" ]]; then
        log_info "Checkpoint mcp_auth cannot be auto-approved (requires browser authentication)"
    elif [[ "${CHECKPOINT_AUTO_APPROVE:-false}" == "true" ]]; then
        log_info "Checkpoint auto-approved (checkpoint_auto_approve=true)"
        with_state_lock _approve_checkpoint_locked
        return
    fi

    # Set status and wait for approval
    update_state_field "status" '"checkpoint"'
    info "Checkpoint: $reason. Waiting for approval..."
    info "Run 'wt-orchestrate approve' (or 'approve --merge') to continue."

    # Wait for approval
    while true; do
        sleep "$APPROVAL_POLL"
        local approved
        approved=$(jq -r '.checkpoints[-1].approved' "$STATE_FILENAME" 2>/dev/null)
        local orch_status
        orch_status=$(jq -r '.status' "$STATE_FILENAME" 2>/dev/null)
        if [[ "$approved" == "true" ]] || [[ "$orch_status" == "running" ]]; then
            log_info "Checkpoint approved"
            break
        fi
        if [[ "$orch_status" == "stopped" ]]; then
            log_info "Orchestrator stopped during checkpoint"
            return
        fi
    done
}

generate_summary() {
    local reason="$1"
    local timestamp
    timestamp=$(date -Iseconds)

    {
        echo "# Orchestration Summary"
        echo ""
        echo "**Generated:** $timestamp"
        echo "**Reason:** $reason"
        echo ""
        echo "## Changes"
        echo ""
        printf "| %-25s | %-12s | %-10s | %-8s |\n" "Change" "Status" "Tokens" "Tests"
        printf "| %-25s | %-12s | %-10s | %-8s |\n" "-------------------------" "------------" "----------" "--------"
        jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used)\t\(.test_result // "-")"' "$STATE_FILENAME" | \
        while IFS=$'\t' read -r name status tokens tests; do
            printf "| %-25s | %-12s | %-10s | %-8s |\n" "$name" "$status" "$tokens" "$tests"
        done
        echo ""

        local queue_size
        queue_size=$(jq '.merge_queue | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
        if [[ "$queue_size" -gt 0 ]]; then
            echo "## Merge Queue"
            echo ""
            jq -r '.merge_queue[]' "$STATE_FILENAME" | while read -r name; do
                echo "- $name"
            done
            echo ""
        fi

        local total_tokens
        total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
        echo "## Totals"
        echo ""
        echo "- **Total tokens:** $total_tokens"
        echo ""

        # Event-based timeline (if events log exists)
        if [[ -n "${EVENTS_LOG_FILE:-}" && -f "${EVENTS_LOG_FILE:-}" ]]; then
            local event_count
            event_count=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)
            if [[ "$event_count" -gt 0 ]]; then
                echo "## Event Timeline"
                echo ""
                echo "- **Total events:** $event_count"
                # Count by type
                local type_counts
                type_counts=$(jq -r '.type' "$EVENTS_LOG_FILE" 2>/dev/null | sort | uniq -c | sort -rn | head -10)
                if [[ -n "$type_counts" ]]; then
                    echo "- **By type:**"
                    echo "$type_counts" | while read -r cnt typ; do
                        echo "  - $typ: $cnt"
                    done
                fi
                # Show errors
                local error_count
                error_count=$(jq -r 'select(.type == "ERROR") | .change' "$EVENTS_LOG_FILE" 2>/dev/null | wc -l)
                if [[ "$error_count" -gt 0 ]]; then
                    echo "- **Errors:** $error_count"
                fi
                echo ""
            fi
        fi
    } > "$SUMMARY_FILENAME"

    log_info "Summary written to $SUMMARY_FILENAME"
}

# ─── Crash-Safe State Recovery ──────────────────────────────────────
# Migrated to: wt_orch/state.py reconstruct_state_from_events()

# Rebuild orchestration-state.json from orchestration-events.jsonl by replaying
# state transitions. Called by sentinel on startup when state appears inconsistent.
# Returns 0 if reconstruction succeeded, 1 if not possible (no events file).
reconstruct_state_from_events() {
    local events_file="${1:-}"
    local state_file="${2:-$STATE_FILENAME}"

    local args=(--file "$state_file")
    [[ -n "$events_file" ]] && args+=(--events "$events_file")

    wt-orch-core state reconstruct "${args[@]}"
}
