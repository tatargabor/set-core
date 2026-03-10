#!/usr/bin/env bash
# lib/orchestration/monitor.sh — Main orchestration monitoring loop
# Dependencies: state.sh, events.sh, dispatcher.sh, verifier.sh, merger.sh, watchdog.sh

monitor_loop() {
    local directives="$1"
    local max_parallel
    max_parallel=$(echo "$directives" | jq -r '.max_parallel')
    local checkpoint_every
    checkpoint_every=$(echo "$directives" | jq -r '.checkpoint_every')
    local test_command
    test_command=$(echo "$directives" | jq -r '.test_command')
    local merge_policy
    merge_policy=$(echo "$directives" | jq -r '.merge_policy')
    local token_budget
    token_budget=$(echo "$directives" | jq -r '.token_budget')
    local auto_replan
    auto_replan=$(echo "$directives" | jq -r '.auto_replan')
    local test_timeout
    test_timeout=$(echo "$directives" | jq -r '.test_timeout // 300')
    local max_verify_retries
    max_verify_retries=$(echo "$directives" | jq -r '.max_verify_retries // 1')
    local review_before_merge
    review_before_merge=$(echo "$directives" | jq -r '.review_before_merge // false')
    local review_model
    review_model=$(echo "$directives" | jq -r '.review_model // "sonnet"')
    DEFAULT_IMPL_MODEL=$(echo "$directives" | jq -r '.default_model // "opus"')
    local smoke_command
    smoke_command=$(echo "$directives" | jq -r '.smoke_command // ""')
    local smoke_timeout
    smoke_timeout=$(echo "$directives" | jq -r '.smoke_timeout // 120')
    local smoke_blocking
    smoke_blocking=$(echo "$directives" | jq -r '.smoke_blocking // false')
    local smoke_fix_token_budget
    smoke_fix_token_budget=$(echo "$directives" | jq -r ".smoke_fix_token_budget // $DEFAULT_SMOKE_FIX_TOKEN_BUDGET")
    local smoke_fix_max_turns
    smoke_fix_max_turns=$(echo "$directives" | jq -r ".smoke_fix_max_turns // $DEFAULT_SMOKE_FIX_MAX_TURNS")
    local smoke_fix_max_retries
    smoke_fix_max_retries=$(echo "$directives" | jq -r ".smoke_fix_max_retries // $DEFAULT_SMOKE_FIX_MAX_RETRIES")
    local smoke_health_check_url
    smoke_health_check_url=$(echo "$directives" | jq -r '.smoke_health_check_url // ""')
    local smoke_health_check_timeout
    smoke_health_check_timeout=$(echo "$directives" | jq -r ".smoke_health_check_timeout // $DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT")

    local e2e_command
    e2e_command=$(echo "$directives" | jq -r '.e2e_command // ""')
    local e2e_timeout
    e2e_timeout=$(echo "$directives" | jq -r '.e2e_timeout // 120')
    local e2e_mode
    e2e_mode=$(echo "$directives" | jq -r '.e2e_mode // "per_change"')

    local token_hard_limit
    token_hard_limit=$(echo "$directives" | jq -r ".token_hard_limit // $DEFAULT_TOKEN_HARD_LIMIT")

    # Apply events directives to globals
    EVENTS_ENABLED=$(echo "$directives" | jq -r '.events_log // "true"')
    EVENTS_MAX_SIZE=$(echo "$directives" | jq -r ".events_max_size // $EVENTS_MAX_SIZE")

    # Apply watchdog directives to globals
    local wd_timeout wd_loop_thresh
    wd_timeout=$(echo "$directives" | jq -r '.watchdog_timeout // empty')
    wd_loop_thresh=$(echo "$directives" | jq -r '.watchdog_loop_threshold // empty')
    [[ -n "$wd_timeout" ]] && WATCHDOG_TIMEOUT_RUNNING="$wd_timeout" && WATCHDOG_TIMEOUT_VERIFYING="$wd_timeout" && WATCHDOG_TIMEOUT_DISPATCHED="$wd_timeout"
    [[ -n "$wd_loop_thresh" ]] && WATCHDOG_LOOP_THRESHOLD="$wd_loop_thresh"
    # Max redispatch attempts per change (default: 2)
    MAX_REDISPATCH=$(echo "$directives" | jq -r '.max_redispatch // 2')
    # Apply context pruning directive to global
    CONTEXT_PRUNING=$(echo "$directives" | jq -r '.context_pruning // true')

    # Apply model routing directive to global
    MODEL_ROUTING=$(echo "$directives" | jq -r '.model_routing // "off"')

    # Apply checkpoint auto-approve directive to global
    CHECKPOINT_AUTO_APPROVE=$(echo "$directives" | jq -r '.checkpoint_auto_approve // false')

    # Apply hook directives to globals (used by run_hook via indirect variable reference)
    hook_pre_dispatch=$(echo "$directives" | jq -r '.hook_pre_dispatch // empty')
    hook_post_verify=$(echo "$directives" | jq -r '.hook_post_verify // empty')
    hook_pre_merge=$(echo "$directives" | jq -r '.hook_pre_merge // empty')
    hook_post_merge=$(echo "$directives" | jq -r '.hook_post_merge // empty')
    hook_on_fail=$(echo "$directives" | jq -r '.hook_on_fail // empty')

    # Parse time limit (default 5h, --time-limit none to disable)
    local time_limit_secs=0
    local time_limit_input="${CLI_TIME_LIMIT:-$DEFAULT_TIME_LIMIT}"
    if [[ "$time_limit_input" == "none" || "$time_limit_input" == "0" ]]; then
        time_limit_secs=0
        info "Time limit: disabled"
    elif [[ -n "$time_limit_input" ]]; then
        time_limit_secs=$(parse_duration "$time_limit_input")
        if [[ "$time_limit_secs" -le 0 ]]; then
            warn "Invalid time limit '$time_limit_input', using default $DEFAULT_TIME_LIMIT"
            time_limit_secs=$(parse_duration "$DEFAULT_TIME_LIMIT")
        fi
        info "Time limit: $(format_duration "$time_limit_secs")"
    fi

    # Persist timing info in state for cmd_status to read
    update_state_field "started_epoch" "$ORCHESTRATOR_START_EPOCH"
    update_state_field "time_limit_secs" "$time_limit_secs"

    # Active seconds: only counts time when loops are making progress.
    # Restored on resume so the timer is cumulative across restarts.
    local active_seconds
    active_seconds=$(jq -r '.active_seconds // 0' "$STATE_FILENAME" 2>/dev/null)
    local token_wait=false  # true when token budget exceeded, waiting for reset
    local replan_retry_count=0  # consecutive replan failures, reset on success

    info "Monitor loop started (poll every ${POLL_INTERVAL}s, auto_replan=$auto_replan)"
    local post_merge_command
    post_merge_command=$(echo "$directives" | jq -r '.post_merge_command // ""')
    log_info "Directives: test_command=$test_command, review_before_merge=$review_before_merge, review_model=$review_model, test_timeout=$test_timeout, max_verify_retries=$max_verify_retries, smoke_command=$smoke_command, post_merge_command=$post_merge_command"

    local _poll_count=0
    while true; do
        sleep "$POLL_INTERVAL"
        _poll_count=$((_poll_count + 1))

        # Periodic memory stats + audit (every ~10 polls ~ 2.5 min)
        if (( _poll_count % 10 == 0 )); then
            orch_memory_stats
            orch_gate_stats
            orch_memory_audit
        fi

        # Track active time: only count this interval if loops are making progress
        # Skip entirely during token_wait — rate limit pause should not count
        if [[ "$token_wait" != true ]] && any_loop_active; then
            active_seconds=$((active_seconds + POLL_INTERVAL))
            update_state_field "active_seconds" "$active_seconds"
        fi

        # Check time limit against ACTIVE time (not wall clock)
        if [[ "$time_limit_secs" -gt 0 && "$active_seconds" -ge "$time_limit_secs" ]]; then
            local wall_elapsed=$(($(date +%s) - ORCHESTRATOR_START_EPOCH))
            warn "Time limit reached ($(format_duration "$active_seconds") active, $(format_duration "$wall_elapsed") wall clock)"
            log_info "Time limit reached: $(format_duration "$active_seconds") active / $(format_duration "$wall_elapsed") wall"
            update_state_field "status" '"time_limit"'
            send_notification "wt-orchestrate" "Time limit reached ($(format_duration "$active_seconds") active). Run 'wt-orchestrate start' to continue." "normal"
            orch_memory_stats
            orch_gate_stats
            local _cov_summary
            _cov_summary=$(final_coverage_check 2>/dev/null || true)
            send_summary_email "time-limit" "$(basename "$(pwd)")" "$STATE_FILENAME" "$_cov_summary" 2>/dev/null || true
            generate_report 2>/dev/null || true
            break
        fi

        # Check if we've been stopped externally
        local orch_status
        orch_status=$(jq -r '.status' "$STATE_FILENAME" 2>/dev/null || echo "unknown")
        if [[ "$orch_status" == "stopped" || "$orch_status" == "done" ]]; then
            final_coverage_check 2>/dev/null || true
            generate_report 2>/dev/null || true
            break
        fi
        # Skip monitoring if paused or at checkpoint
        if [[ "$orch_status" == "paused" || "$orch_status" == "checkpoint" ]]; then
            continue
        fi

        # Poll each active change (running + verifying — verifying may have been interrupted mid-gate)
        # In phase_end mode, skip per-change E2E (runs on main after all changes merge)
        local _poll_e2e_cmd="$e2e_command"
        [[ "$e2e_mode" == "phase_end" ]] && _poll_e2e_cmd=""

        local active_changes
        active_changes=$(jq -r '.changes[]? | select(.status == "running" or .status == "verifying") | .name' "$STATE_FILENAME" 2>/dev/null || true)
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            poll_change "$name" "$test_command" "$merge_policy" \
                "$test_timeout" "$max_verify_retries" "$review_before_merge" "$review_model" \
                "$smoke_command" "$smoke_timeout" "$smoke_blocking" \
                "$smoke_fix_max_retries" "$smoke_fix_max_turns" \
                "$smoke_health_check_url" "$smoke_health_check_timeout" \
                "$_poll_e2e_cmd" "$e2e_timeout"
            watchdog_check "$name"
        done <<< "$active_changes"

        # Safety net: check paused/waiting changes for completed loop-state.
        # Covers race where watchdog paused a change that finished between poll and watchdog check.
        local suspended_changes
        suspended_changes=$(jq -r '.changes[]? | select(.status == "paused" or .status == "waiting:budget" or .status == "budget_exceeded") | .name' "$STATE_FILENAME" 2>/dev/null || true)
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            local _wt_path
            _wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
            local _loop_state="$_wt_path/.claude/loop-state.json"
            if [[ -n "$_wt_path" && -f "$_loop_state" ]]; then
                local _ls_status
                _ls_status=$(jq -r '.status // "unknown"' "$_loop_state" 2>/dev/null)
                if [[ "$_ls_status" == "done" ]]; then
                    log_info "Monitor: suspended change $name has loop-state=done — processing via poll_change"
                    # Temporarily set to running so poll_change can process the done state
                    update_change_field "$name" "status" '"running"'
                    poll_change "$name" "$test_command" "$merge_policy" \
                        "$test_timeout" "$max_verify_retries" "$review_before_merge" "$review_model" \
                        "$smoke_command" "$smoke_timeout" "$smoke_blocking" \
                        "$smoke_fix_max_retries" "$smoke_fix_max_turns" \
                        "$smoke_health_check_url" "$smoke_health_check_timeout" \
                        "$_poll_e2e_cmd" "$e2e_timeout"
                fi
            fi
        done <<< "$suspended_changes"

        # Check token budget — if exceeded, skip dispatch but keep polling
        # (waiting for rate limit window to reset; running loops will finish naturally)
        if [[ "$token_budget" -gt 0 ]]; then
            local total_tokens
            total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
            if [[ "$total_tokens" -gt "$token_budget" ]]; then
                if [[ "$token_wait" != true ]]; then
                    warn "Token budget exceeded ($total_tokens > $token_budget) — waiting for running loops to finish"
                    log_warn "Token budget exceeded: $total_tokens > $token_budget — entering wait mode"
                    token_wait=true
                fi
                # Don't dispatch new changes, but continue polling running ones
                retry_merge_queue
                continue
            else
                if [[ "$token_wait" == true ]]; then
                    info "Token budget available again — resuming dispatch"
                    log_info "Token wait ended, resuming dispatch"
                    token_wait=false
                fi
            fi
        fi

        # Resume verify-failed changes (orphaned by restart or manual state edit).
        # resume_change() sets status to "running", so this won't re-trigger next poll.
        local vf_changes
        vf_changes=$(jq -r '.changes[]? | select(.status == "verify-failed") | .name' "$STATE_FILENAME" 2>/dev/null || true)
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            local vf_retry_count
            vf_retry_count=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .verify_retry_count // 0' "$STATE_FILENAME")
            if [[ "$vf_retry_count" -lt "$max_verify_retries" ]]; then
                log_info "Recovering verify-failed change $name (retry $vf_retry_count/$max_verify_retries)"
                info "Recovering verify-failed: $name"
                local vf_new_count=$((vf_retry_count + 1))
                update_change_field "$name" "verify_retry_count" "$vf_new_count"
                # Rebuild retry_context from stored build_output if missing
                local existing_ctx
                existing_ctx=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .retry_context // empty' "$STATE_FILENAME")
                if [[ -z "$existing_ctx" || "$existing_ctx" == "null" ]]; then
                    local stored_build_output
                    stored_build_output=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .build_output // empty' "$STATE_FILENAME")
                    local stored_scope
                    stored_scope=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .scope // empty' "$STATE_FILENAME")
                    if [[ -n "$stored_build_output" ]]; then
                        local rebuild_prompt="Build failed after implementation. Fix the build errors.\n\nBuild output (last 2000 chars):\n${stored_build_output: -2000}\n\nOriginal scope: $stored_scope"
                        update_change_field "$name" "retry_context" "$(printf '%s' "$rebuild_prompt" | jq -Rs .)"
                        log_info "Rebuilt retry_context for $name from stored build_output"
                    fi
                fi
                resume_change "$name"
            else
                log_info "Verify-failed change $name exhausted retries ($vf_retry_count/$max_verify_retries) — marking failed"
                update_change_field "$name" "status" '"failed"'
            fi
        done <<< "$vf_changes"

        # Dispatch newly ready changes (skipped during token_wait)
        dispatch_ready_changes "$max_parallel"

        # Retry merge queue + any merge-blocked items not in queue
        retry_merge_queue

        # Resume stalled changes after cooldown (handles rate limit recovery)
        resume_stalled_changes

        # Cascade failure: mark pending changes whose dependencies have failed
        cascade_failed_deps

        # Retry failed builds before declaring all-done (cheaper than replan)
        retry_failed_builds "$max_verify_retries"

        # Check token hard limit — pause for human approval before spending more
        if [[ "$token_hard_limit" -gt 0 ]]; then
            local hl_total_tokens
            hl_total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
            # Include tokens from previous replan cycles
            local hl_prev_tokens
            hl_prev_tokens=$(jq -r '.prev_total_tokens // 0' "$STATE_FILENAME")
            local hl_cumulative=$((hl_total_tokens + hl_prev_tokens))
            if [[ "$hl_cumulative" -gt "$token_hard_limit" ]]; then
                local hl_already_triggered
                hl_already_triggered=$(jq -r '.token_hard_limit_triggered // false' "$STATE_FILENAME")
                if [[ "$hl_already_triggered" != "true" ]]; then
                    update_state_field "token_hard_limit_triggered" "true"
                    local hl_m=$((hl_cumulative / 1000000))
                    warn "Token hard limit reached: ${hl_m}M / $((token_hard_limit / 1000000))M tokens"
                    log_warn "Token hard limit reached: $hl_cumulative > $token_hard_limit"
                    trigger_checkpoint "token_hard_limit"
                    # After approval, reset flag so it can trigger again at next multiple
                    update_state_field "token_hard_limit_triggered" "false"
                    token_hard_limit=$((token_hard_limit + DEFAULT_TOKEN_HARD_LIMIT))
                    log_info "Token hard limit raised to $token_hard_limit for next checkpoint"
                    continue
                fi
            fi
        fi

        # Update HTML report
        generate_report 2>/dev/null || true

        # Watchdog heartbeat (sentinel monitors events.jsonl mtime)
        watchdog_heartbeat

        # Check if checkpoint needed (skip if checkpoint_every is null/empty/0)
        if [[ -n "$checkpoint_every" && "$checkpoint_every" != "null" && "$checkpoint_every" -gt 0 ]] 2>/dev/null; then
            local changes_since
            changes_since=$(jq -r '.changes_since_checkpoint // 0' "$STATE_FILENAME")
            if [[ "$changes_since" -ge "$checkpoint_every" ]]; then
                trigger_checkpoint "periodic"
                continue
            fi
        fi

        # Check if all done — count resolved changes (success + terminal failures)
        local total_changes
        total_changes=$(jq '.changes | length' "$STATE_FILENAME")
        local truly_complete
        truly_complete=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$STATE_FILENAME")
        local failed_count
        failed_count=$(jq '[.changes[] | select(.status == "failed")] | length' "$STATE_FILENAME")
        local merge_blocked_count
        merge_blocked_count=$(jq '[.changes[] | select(.status == "merge-blocked")] | length' "$STATE_FILENAME")
        local active_count
        active_count=$(jq '[.changes[] | select(.status == "running" or .status == "pending" or .status == "verifying" or .status == "stalled")] | length' "$STATE_FILENAME")

        # When no active changes remain but some are merge-blocked/failed,
        # nothing can unblock them — transition to done with partial completion
        if [[ "$active_count" -eq 0 && "$truly_complete" -lt "$total_changes" ]]; then
            local terminal_count=$((truly_complete + failed_count + merge_blocked_count))
            if [[ "$terminal_count" -ge "$total_changes" ]]; then
                log_info "$truly_complete succeeded, $failed_count failed, $merge_blocked_count merge-blocked — all resolved"
                send_notification "wt-orchestrate" "$truly_complete/$total_changes changes complete ($failed_count failed, $merge_blocked_count merge-blocked)" "warning"
                # Fall through to completion handling below
            fi
        fi

        local all_resolved=$(( truly_complete + failed_count + merge_blocked_count ))
        if [[ "$truly_complete" -ge "$total_changes" || ("$active_count" -eq 0 && "$all_resolved" -ge "$total_changes") ]]; then
            log_info "All $total_changes changes complete"
            send_notification "wt-orchestrate" "All $total_changes changes complete!" "normal"

            # ── Phase-end E2E: run Playwright on main after all changes merged ──
            if [[ "$e2e_mode" == "phase_end" && -n "$e2e_command" && "$truly_complete" -gt 0 ]]; then
                run_phase_end_e2e "$e2e_command" "$e2e_timeout"
            fi

            # Auto-replan: generate next plan and continue if new work found
            if [[ "$auto_replan" == "true" ]]; then
                info "All changes done. Auto-replanning..."
                log_info "Auto-replan triggered"

                # Track replan cycle in state — persist BEFORE attempting so retries
                # read the same cycle number and don't re-increment
                local cycle
                cycle=$(jq '.replan_cycle // 0' "$STATE_FILENAME")
                local replan_attempt
                replan_attempt=$(jq '.replan_attempt // 0' "$STATE_FILENAME")

                # Only increment cycle on first attempt (not retries of same cycle)
                if [[ "$replan_attempt" -eq 0 ]]; then
                    cycle=$((cycle + 1))
                    update_state_field "replan_cycle" "$cycle"
                fi

                local replan_rc=0
                auto_replan_cycle "$directives" "$cycle" || replan_rc=$?

                if [[ $replan_rc -eq 0 ]]; then
                    # New plan dispatched, continue monitoring
                    replan_retry_count=0
                    update_state_field "replan_attempt" "0"
                    info "Replan cycle $cycle: new changes dispatched, continuing..."
                    log_info "Replan cycle $cycle started"
                    continue
                elif [[ $replan_rc -eq 1 ]]; then
                    # No new work found — genuinely done
                    update_state_field "replan_attempt" "0"
                    update_state_field "status" '"done"'
                    cleanup_all_worktrees
                    orch_memory_stats
                    orch_gate_stats
                    local _cov_summary
                    _cov_summary=$(final_coverage_check 2>/dev/null || true)
                    send_summary_email "complete" "$(basename "$(pwd)")" "$STATE_FILENAME" "$_cov_summary" 2>/dev/null || true
                    generate_report 2>/dev/null || true
                    success "All work complete! No more phases to implement."
                    log_info "Auto-replan found no new work — orchestration complete"
                    break
                else
                    # Replan failed (rc=2) — retry with limit
                    # Use persistent attempt counter (survives poll loop re-entry)
                    replan_attempt=$((replan_attempt + 1))
                    update_state_field "replan_attempt" "$replan_attempt"
                    replan_retry_count=$replan_attempt

                    if [[ $replan_retry_count -ge $MAX_REPLAN_RETRIES ]]; then
                        warn "Replan failed $replan_retry_count consecutive times — giving up"
                        log_error "Auto-replan exhausted after $replan_retry_count failures (cycle $cycle)"
                        local failed_names
                        failed_names=$(jq -r '[.changes[] | select(.status == "failed") | .name] | join(", ")' "$STATE_FILENAME")
                        [[ -n "$failed_names" ]] && warn "Failed changes: $failed_names"
                        update_state_field "status" '"done"'
                        update_state_field "replan_exhausted" 'true'
                        update_state_field "replan_attempt" "0"
                        local _cov_summary
                        _cov_summary=$(final_coverage_check 2>/dev/null || true)
                        send_summary_email "replan-exhausted" "$(basename "$(pwd)")" "$STATE_FILENAME" "$_cov_summary" 2>/dev/null || true
                        generate_report 2>/dev/null || true
                        break
                    fi
                    warn "Replan failed (cycle $cycle, attempt $replan_retry_count/$MAX_REPLAN_RETRIES) — will retry"
                    log_error "Auto-replan error (cycle $cycle, rc=$replan_rc, attempt $replan_retry_count/$MAX_REPLAN_RETRIES)"
                    sleep 30
                    continue
                fi
            else
                trigger_checkpoint "completion"
                update_state_field "status" '"done"'
                cleanup_all_worktrees
                success "All changes complete!"
                orch_memory_stats
                orch_gate_stats
                local _cov_summary
                _cov_summary=$(final_coverage_check 2>/dev/null || true)
                send_summary_email "complete" "$(basename "$(pwd)")" "$STATE_FILENAME" "$_cov_summary" 2>/dev/null || true
                generate_report 2>/dev/null || true
                log_info "Orchestration complete"
                break
            fi
        fi
    done
}
