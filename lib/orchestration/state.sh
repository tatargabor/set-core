#!/usr/bin/env bash
# lib/orchestration/state.sh — State initialization, queries, notifications, status
# Dependencies: config.sh, utils.sh must be sourced first
# Sourced by bin/wt-orchestrate

init_state() {
    local plan_file="$1"

    local plan_version
    plan_version=$(jq -r '.plan_version' "$plan_file")
    local plan_brief_hash
    plan_brief_hash=$(jq -r '.brief_hash' "$plan_file")
    local plan_phase
    plan_phase=$(jq -r '.plan_phase // "initial"' "$plan_file")
    local plan_method
    plan_method=$(jq -r '.plan_method // "api"' "$plan_file")

    # Build changes array from plan
    local changes
    changes=$(jq '[.changes[] | {
        name: .name,
        scope: .scope,
        complexity: .complexity,
        change_type: (.change_type // "feature"),
        depends_on: .depends_on,
        roadmap_item: .roadmap_item,
        model: (.model // null),
        skip_review: (.skip_review // false),
        skip_test: (.skip_test // false),
        has_manual_tasks: (.has_manual_tasks // false),
        status: "pending",
        worktree_path: null,
        ralph_pid: null,
        started_at: null,
        completed_at: null,
        tokens_used: 0,
        tokens_used_prev: 0,
        input_tokens: 0,
        output_tokens: 0,
        cache_read_tokens: 0,
        cache_create_tokens: 0,
        input_tokens_prev: 0,
        output_tokens_prev: 0,
        cache_read_tokens_prev: 0,
        cache_create_tokens_prev: 0,
        test_result: null,
        smoke_result: null,


        verify_retry_count: 0
    }]' "$plan_file")

    jq -n \
        --argjson plan_version "$plan_version" \
        --arg brief_hash "$plan_brief_hash" \
        --arg created_at "$(date -Iseconds)" \
        --argjson changes "$changes" \
        --arg plan_phase "$plan_phase" \
        --arg plan_method "$plan_method" \
        '{
            plan_version: $plan_version,
            brief_hash: $brief_hash,
            plan_phase: $plan_phase,
            plan_method: $plan_method,
            status: "running",
            created_at: $created_at,
            changes: $changes,
            checkpoints: [],
            merge_queue: [],
            changes_since_checkpoint: 0,
            cycle_started_at: null
        }' > "$STATE_FILENAME"

    local change_count
    change_count=$(echo "$changes" | jq 'length')
    log_info "State initialized with $change_count changes (plan v$plan_version)"
}

# Update a top-level field in state
update_state_field() {
    local field="$1"
    local value="$2"
    local tmp
    tmp=$(mktemp)
    jq ".$field = $value" "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
}

# Update a change's field in state
# Automatically emits STATE_CHANGE event when status field changes
update_change_field() {
    local change_name="$1"
    local field="$2"
    local value="$3"

    # Capture old status before update for event emission
    local old_status=""
    if [[ "$field" == "status" ]]; then
        old_status=$(jq -r --arg name "$change_name" '.changes[] | select(.name == $name) | .status // ""' "$STATE_FILENAME" 2>/dev/null)
    fi

    local tmp
    tmp=$(mktemp)
    jq --arg name "$change_name" --argjson val "$value" \
        '(.changes[] | select(.name == $name)).'$field' = $val' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # Emit STATE_CHANGE event on status transitions
    if [[ "$field" == "status" && -n "$old_status" ]]; then
        local new_status
        new_status=$(echo "$value" | tr -d '"')
        if [[ "$old_status" != "$new_status" ]]; then
            emit_event "STATE_CHANGE" "$change_name" \
                "{\"from\":\"$old_status\",\"to\":\"$new_status\"}"
            # Trigger on_fail hook when a change transitions to failed
            if [[ "$new_status" == "failed" ]]; then
                local wt_path_for_hook
                wt_path_for_hook=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME" 2>/dev/null || true)
                run_hook "on_fail" "$change_name" "failed" "$wt_path_for_hook" || true
            fi
        fi
    fi

    # Emit TOKENS event on significant token updates
    if [[ "$field" == "tokens_used" ]]; then
        local prev_tokens
        prev_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME" 2>/dev/null)
        local delta=$((value - prev_tokens))
        # Only emit on significant deltas (>10K tokens)
        if [[ "$delta" -gt 10000 || "$delta" -lt -10000 ]]; then
            emit_event "TOKENS" "$change_name" \
                "{\"delta\":$delta,\"total\":$value}"
        fi
    fi
}

# Get a change's status
get_change_status() {
    local change_name="$1"
    jq -r --arg name "$change_name" '.changes[] | select(.name == $name) | .status' "$STATE_FILENAME"
}

# Get all changes with a specific status
get_changes_by_status() {
    local status="$1"
    jq -r --arg s "$status" '[.changes[] | select(.status == $s) | .name] | .[]' "$STATE_FILENAME"
}

# Count changes with a specific status
count_changes_by_status() {
    local status="$1"
    jq --arg s "$status" '[.changes[] | select(.status == $s)] | length' "$STATE_FILENAME"
}

# Check if all depends_on for a change are merged
deps_satisfied() {
    local change_name="$1"
    local deps
    deps=$(jq -r --arg name "$change_name" \
        '.changes[] | select(.name == $name) | .depends_on[]?' "$STATE_FILENAME" 2>/dev/null)

    [[ -z "$deps" ]] && return 0  # no dependencies

    while IFS= read -r dep; do
        local dep_status
        dep_status=$(get_change_status "$dep")
        if [[ "$dep_status" != "merged" ]]; then
            return 1
        fi
    done <<< "$deps"

    return 0
}

# ─── Dependency Graph ────────────────────────────────────────────────

# Topological sort of changes (returns names in execution order)
topological_sort() {
    local plan_file="$1"

    _TOPO_FILE="$plan_file" python3 -c "
import json, sys, os

with open(os.environ['_TOPO_FILE']) as f:
    plan = json.load(f)

changes = {c['name']: c.get('depends_on', []) for c in plan['changes']}

# Build adjacency: if B depends on A, then A -> B
adj = {name: [] for name in changes}
in_deg = {name: 0 for name in changes}
for name, deps in changes.items():
    for d in deps:
        if d in adj:
            adj[d].append(name)
            in_deg[name] += 1

queue = [n for n in changes if in_deg[n] == 0]
queue.sort()  # deterministic order
result = []
while queue:
    node = queue.pop(0)
    result.append(node)
    for neighbor in sorted(adj[node]):
        in_deg[neighbor] -= 1
        if in_deg[neighbor] == 0:
            queue.append(neighbor)

if len(result) != len(changes):
    print('ERROR:circular', file=sys.stderr)
    sys.exit(1)

for name in result:
    print(name)
"
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
        state_mtime=$(stat --format='%Y' "$STATE_FILENAME" 2>/dev/null || echo 0)
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

    echo "  Progress: $merged merged, $done_count done, $running running, $pending pending"
    [[ "$verifying" -gt 0 ]] && echo "  Verifying: $verifying"
    [[ "$verify_failed" -gt 0 ]] && echo "  Verify-failed: $verify_failed"
    [[ "$failed" -gt 0 ]] && echo "  Failed:   $failed"
    [[ "$stalled" -gt 0 ]] && echo "  Stalled:  $stalled"

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

    jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used)\t\(.test_result // "-")\t\(.review_result // "-")\t\(.gate_total_ms // 0)\t\(.gate_retry_tokens // 0)\t\(.gate_retry_count // 0)"' "$STATE_FILENAME" | \
    while IFS=$'\t' read -r name change_status tokens test_res review_res g_ms g_rtok g_rcnt; do
        local progress="-"
        # Try to read iteration progress from worktree
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        if [[ -n "$wt_path" && -f "$wt_path/.claude/loop-state.json" ]]; then
            local iter max_iter
            iter=$(jq -r '.current_iteration // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null)
            max_iter=$(jq -r '.max_iterations // "?"' "$wt_path/.claude/loop-state.json" 2>/dev/null)
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
        printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "$name" "$change_status" "$progress" "$test_res" "$review_res" "$tokens" "$gate_col"
    done

    # Manual task hints for waiting:human changes
    if [[ "$waiting_human" -gt 0 ]]; then
        echo ""
        info "⏸ Changes waiting for manual input:"
        jq -r '.changes[] | select(.status == "waiting:human") | .name' "$STATE_FILENAME" | while read -r wh_name; do
            local wh_wt
            wh_wt=$(jq -r --arg n "$wh_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
            local wh_summary=""
            if [[ -n "$wh_wt" && -f "$wh_wt/.claude/loop-state.json" ]]; then
                wh_summary=$(jq -r '.manual_tasks[0]? | "[\(.id)] \(.description)"' "$wh_wt/.claude/loop-state.json" 2>/dev/null)
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
    echo "  Total tokens: $total_tokens (in:$total_in out:$total_out cr:$total_cr cc:$total_cc)"

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
            update_change_field "$change_name" "status" '"done"'
            log_info "Change $change_name unblocked — ready for merge retry"
            success "Change '$change_name' unblocked"
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

    # Mark latest checkpoint as approved
    local tmp
    tmp=$(mktemp)
    jq '(.checkpoints[-1]).approved = true' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
    update_state_field "status" '"running"'

    log_info "Checkpoint approved (merge=$merge_flag)"
    success "Checkpoint approved"

    if $merge_flag; then
        info "Executing merge queue..."
        execute_merge_queue
    fi
}

# ─── Checkpoint & Summary ────────────────────────────────────────────

trigger_checkpoint() {
    local reason="$1"

    log_info "Checkpoint triggered: $reason"
    emit_event "CHECKPOINT" "" "{\"reason\":\"$reason\"}"

    # Generate summary
    generate_summary "$reason"

    # Add checkpoint to state
    local tmp
    tmp=$(mktemp)
    jq --arg at "$(date -Iseconds)" --arg reason "$reason" \
        '.checkpoints += [{at: $at, type: $reason, approved: false}]' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # Reset counter
    update_state_field "changes_since_checkpoint" "0"

    # Send notification
    local total
    total=$(jq '.changes | length' "$STATE_FILENAME")
    local done_count
    done_count=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$STATE_FILENAME")
    local running
    running=$(count_changes_by_status "running")
    send_notification "wt-orchestrate" "Checkpoint ($reason): $done_count/$total done, $running running. Run 'wt-orchestrate approve' to continue."

    # Auto-approve if directive is set (unattended/E2E mode)
    if [[ "${CHECKPOINT_AUTO_APPROVE:-false}" == "true" ]]; then
        log_info "Checkpoint auto-approved (checkpoint_auto_approve=true)"
        local tmp2
        tmp2=$(mktemp)
        jq '.checkpoints[-1].approved = true' "$STATE_FILENAME" > "$tmp2" && mv "$tmp2" "$STATE_FILENAME"
        update_state_field "status" '"running"'
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

# Rebuild orchestration-state.json from orchestration-events.jsonl by replaying
# state transitions. Called by sentinel on startup when state appears inconsistent.
# Returns 0 if reconstruction succeeded, 1 if not possible (no events file).
reconstruct_state_from_events() {
    local events_file="${1:-}"
    local state_file="${2:-$STATE_FILENAME}"

    # Derive events file from state file if not provided
    if [[ -z "$events_file" ]]; then
        events_file="${state_file%.json}-events.jsonl"
    fi

    if [[ ! -f "$events_file" ]]; then
        log_warn "Cannot reconstruct state: no events file at $events_file"
        return 1
    fi

    if [[ ! -f "$state_file" ]]; then
        log_warn "Cannot reconstruct state: no state file at $state_file (need base structure)"
        return 1
    fi

    local event_count
    event_count=$(wc -l < "$events_file" 2>/dev/null || echo 0)
    if [[ "$event_count" -eq 0 ]]; then
        log_warn "Cannot reconstruct state: events file is empty"
        return 1
    fi

    log_info "Reconstructing state from $event_count events in $events_file"

    # Strategy: start from existing state file (has plan structure, change metadata),
    # then replay events to fix status, tokens, timestamps.
    # This preserves fields that events don't track (scope, complexity, depends_on, etc.)

    local tmp_state
    tmp_state=$(mktemp)
    cp "$state_file" "$tmp_state"

    # 1. Replay STATE_CHANGE events to get final per-change status
    #    Each STATE_CHANGE has: {"from":"X","to":"Y"} in data, and change name
    local state_changes
    state_changes=$(jq -c 'select(.type == "STATE_CHANGE" and .change != null and .change != "")' "$events_file" 2>/dev/null || true)

    if [[ -n "$state_changes" ]]; then
        # Get the last status for each change name
        local final_statuses
        final_statuses=$(echo "$state_changes" | jq -c '{change: .change, status: .data.to}' | \
            jq -s 'group_by(.change) | map({key: .[0].change, value: .[-1].status}) | from_entries' 2>/dev/null || echo '{}')

        # Apply final statuses to state
        if [[ "$final_statuses" != "{}" ]]; then
            local change_names
            change_names=$(echo "$final_statuses" | jq -r 'keys[]' 2>/dev/null || true)
            while IFS= read -r cname; do
                [[ -z "$cname" ]] && continue
                local final_status
                final_status=$(echo "$final_statuses" | jq -r --arg n "$cname" '.[$n] // empty')
                [[ -z "$final_status" ]] && continue
                jq --arg n "$cname" --arg s "$final_status" \
                    '(.changes[] | select(.name == $n) | .status) = $s' \
                    "$tmp_state" > "${tmp_state}.2" && mv "${tmp_state}.2" "$tmp_state"
            done <<< "$change_names"
        fi
    fi

    # 2. Replay TOKENS events to get latest token counts
    local token_events
    token_events=$(jq -c 'select(.type == "TOKENS" and .change != null and .change != "")' "$events_file" 2>/dev/null || true)

    if [[ -n "$token_events" ]]; then
        local final_tokens
        final_tokens=$(echo "$token_events" | jq -c '{change: .change, total: .data.total}' | \
            jq -s 'group_by(.change) | map({key: .[0].change, value: .[-1].total}) | from_entries' 2>/dev/null || echo '{}')

        if [[ "$final_tokens" != "{}" ]]; then
            local tnames
            tnames=$(echo "$final_tokens" | jq -r 'keys[]' 2>/dev/null || true)
            while IFS= read -r tname; do
                [[ -z "$tname" ]] && continue
                local tokens
                tokens=$(echo "$final_tokens" | jq -r --arg n "$tname" '.[$n] // 0')
                jq --arg n "$tname" --argjson t "$tokens" \
                    '(.changes[] | select(.name == $n) | .tokens_used) = $t' \
                    "$tmp_state" > "${tmp_state}.2" && mv "${tmp_state}.2" "$tmp_state"
            done <<< "$tnames"
        fi
    fi

    # 3. Derive overall orchestration status from change statuses
    #    If all changes are done/merged/completed/archived → done
    #    If any are running → running (but we clear running since process is dead)
    #    Otherwise → stopped
    local all_done=true any_active=false
    local change_statuses
    change_statuses=$(jq -r '.changes[].status' "$tmp_state" 2>/dev/null || true)
    while IFS= read -r cs; do
        case "$cs" in
            done|merged|completed|archived|skipped) ;;
            running|stalled|stuck)
                all_done=false
                any_active=true
                # Running changes with no live process should be stalled
                jq '(.changes[] | select(.status == "running") | .status) = "stalled"' \
                    "$tmp_state" > "${tmp_state}.2" && mv "${tmp_state}.2" "$tmp_state"
                ;;
            *)
                all_done=false
                ;;
        esac
    done <<< "$change_statuses"

    if $all_done; then
        jq '.status = "done"' "$tmp_state" > "${tmp_state}.2" && mv "${tmp_state}.2" "$tmp_state"
    else
        jq '.status = "stopped"' "$tmp_state" > "${tmp_state}.2" && mv "${tmp_state}.2" "$tmp_state"
    fi

    # 4. Write reconstructed state
    mv "$tmp_state" "$state_file"

    local final_orch_status
    final_orch_status=$(jq -r '.status' "$state_file" 2>/dev/null)
    log_info "State reconstructed: orchestration status=$final_orch_status"

    emit_event "STATE_RECONSTRUCTED" "" \
        "{\"event_count\":$event_count,\"status\":\"$final_orch_status\"}"

    return 0
}
