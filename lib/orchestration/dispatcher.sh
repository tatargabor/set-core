#!/usr/bin/env bash
# lib/orchestration/dispatcher.sh — Change lifecycle: dispatch, resume, pause
# Dependencies: config.sh, utils.sh, state.sh, events.sh, builder.sh
#
# Python implementation: lib/set_orch/dispatcher.py
# This file contains thin wrappers that delegate to set-orch-core dispatch *
# and cmd_start/cmd_pause/cmd_resume which remain in bash for init/signal setup,
# then exec to Python monitor loop (set-orch-core engine monitor).

# ─── Worktree Preparation (delegated to Python) ─────────────────────

sync_worktree_with_main() {
    # Migrated to: wt_orch/dispatcher.py sync_worktree_with_main()
    local wt_path="$1"
    local change_name="$2"
    local result
    result=$(set-orch-core dispatch sync-worktree --wt-path "$wt_path" --change "$change_name" 2>&1)
    local rc=$?
    [[ $rc -eq 0 ]] && log_info "Sync: $change_name $(echo "$result" | python3 -c 'import json,sys; print(json.load(sys.stdin).get("message","ok"))' 2>/dev/null || echo 'ok')"
    [[ $rc -ne 0 ]] && log_warn "Sync failed for $change_name"
    return $rc
}

bootstrap_worktree() {
    # Migrated to: wt_orch/dispatcher.py bootstrap_worktree()
    local project_path="$1"
    local wt_path="$2"
    set-orch-core dispatch bootstrap --project-path "$project_path" --wt-path "$wt_path" 2>/dev/null
}

prune_worktree_context() {
    # Migrated to: wt_orch/dispatcher.py prune_worktree_context()
    local wt_path="$1"
    set-orch-core dispatch prune-context --wt-path "$wt_path" 2>/dev/null
}

# ─── Model Routing (delegated to Python) ─────────────────────────────

resolve_change_model() {
    # Migrated to: wt_orch/dispatcher.py resolve_change_model()
    # default_model defaults to empty so the Python side resolves via
    # model_config.resolve_model("agent") — keep this empty to honor
    # operator overrides from orchestration.yaml::models.agent.
    local change_name="$1"
    local default_model="${2:-}"
    local model_routing="${3:-off}"
    set-orch-core dispatch resolve-model \
        --state "$STATE_FILENAME" \
        --change "$change_name" \
        --default-model "$default_model" \
        --model-routing "$model_routing"
}

# ─── Recovery (delegated to Python) ──────────────────────────────────

recover_orphaned_changes() {
    # Migrated to: wt_orch/dispatcher.py recover_orphaned_changes()
    set-orch-core dispatch recover-orphans --state "$STATE_FILENAME" 2>/dev/null
}

redispatch_change() {
    # Migrated to: wt_orch/dispatcher.py redispatch_change()
    local change_name="$1"
    local failure_pattern="${2:-stuck}"
    set-orch-core dispatch redispatch \
        --state "$STATE_FILENAME" \
        --change "$change_name" \
        --failure-pattern "$failure_pattern" \
        --max-redispatch "${MAX_REDISPATCH:-2}"
}

retry_failed_builds() {
    # Migrated to: wt_orch/dispatcher.py retry_failed_builds()
    local max_retries="${1:-2}"
    set-orch-core dispatch retry-builds \
        --state "$STATE_FILENAME" \
        --max-retries "$max_retries"
}

# ─── Core Dispatch (delegated to Python) ─────────────────────────────

dispatch_change() {
    # Migrated to: wt_orch/dispatcher.py dispatch_change()
    local change_name="$1"
    local args=(
        --state "$STATE_FILENAME"
        --change "$change_name"
        --default-model "${DEFAULT_IMPL_MODEL:-}"
        --model-routing "${MODEL_ROUTING:-off}"
    )
    [[ "${TEAM_MODE:-false}" == "true" ]] && args+=(--team)
    [[ "${CONTEXT_PRUNING:-true}" == "false" ]] && args+=(--no-prune)
    [[ -n "${INPUT_MODE:-}" ]] && args+=(--input-mode "$INPUT_MODE")
    [[ -n "${INPUT_PATH:-}" ]] && args+=(--input-path "$INPUT_PATH")
    [[ -n "${DIGEST_DIR:-}" ]] && args+=(--digest-dir "$DIGEST_DIR")
    set-orch-core dispatch dispatch-change "${args[@]}"
}

dispatch_via_wt_loop() {
    # Migrated to: wt_orch/dispatcher.py dispatch_via_wt_loop()
    # Note: This is called internally by dispatch_change() in Python.
    # Kept for backward compat if called directly from bash.
    local change_name="$1"
    local impl_model="$2"
    local wt_path="$3"
    local scope="$4"

    local task_desc="Implement $change_name: ${scope:0:200}"
    local team_flag=""
    [[ "${TEAM_MODE:-false}" == "true" ]] && team_flag="--team"

    log_info "Dispatch $change_name with model=$impl_model"

    (
        cd "$wt_path" || exit 1
        set-loop start "$task_desc" --max 30 --done openspec --label "$change_name" --model "$impl_model" --change "$change_name" $team_flag
    ) &
    wait $! 2>/dev/null || true

    local loop_state="$wt_path/.set/loop-state.json"
    local retries=0
    while [[ ! -f "$loop_state" && $retries -lt 10 ]]; do
        sleep 1
        retries=$((retries + 1))
    done

    if [[ ! -f "$loop_state" ]]; then
        error "set-loop failed to start for $change_name"
        update_change_field "$change_name" "status" '"failed"'
        return 1
    fi

    local terminal_pid
    terminal_pid=$(jq -r '.terminal_pid // empty' "$loop_state" 2>/dev/null)
    update_change_field "$change_name" "ralph_pid" "${terminal_pid:-0}"
    update_change_field "$change_name" "status" '"running"'
}

dispatch_ready_changes() {
    # Migrated to: wt_orch/dispatcher.py dispatch_ready_changes()
    local max_parallel="$1"
    local args=(
        --state "$STATE_FILENAME"
        --max-parallel "$max_parallel"
        --default-model "${DEFAULT_IMPL_MODEL:-}"
        --model-routing "${MODEL_ROUTING:-off}"
    )
    [[ "${TEAM_MODE:-false}" == "true" ]] && args+=(--team)
    [[ "${CONTEXT_PRUNING:-true}" == "false" ]] && args+=(--no-prune)
    [[ -n "${INPUT_MODE:-}" ]] && args+=(--input-mode "$INPUT_MODE")
    [[ -n "${INPUT_PATH:-}" ]] && args+=(--input-path "$INPUT_PATH")
    [[ -n "${DIGEST_DIR:-}" ]] && args+=(--digest-dir "$DIGEST_DIR")
    set-orch-core dispatch dispatch-ready "${args[@]}"
}

# ─── Lifecycle (delegated to Python) ─────────────────────────────────

pause_change() {
    # Migrated to: wt_orch/dispatcher.py pause_change()
    local change_name="$1"
    set-orch-core dispatch pause \
        --state "$STATE_FILENAME" \
        --change "$change_name"
}

resume_change() {
    # Migrated to: wt_orch/dispatcher.py resume_change()
    local change_name="$1"
    local args=(
        --state "$STATE_FILENAME"
        --change "$change_name"
        --default-model "${DEFAULT_IMPL_MODEL:-}"
        --model-routing "${MODEL_ROUTING:-off}"
    )
    [[ "${TEAM_MODE:-false}" == "true" ]] && args+=(--team)
    set-orch-core dispatch resume "${args[@]}"
}

resume_stopped_changes() {
    # Migrated to: wt_orch/dispatcher.py resume_stopped_changes()
    set-orch-core dispatch resume-stopped --state "$STATE_FILENAME" 2>/dev/null
}

resume_stalled_changes() {
    # Migrated to: wt_orch/dispatcher.py resume_stalled_changes()
    set-orch-core dispatch resume-stalled --state "$STATE_FILENAME" 2>/dev/null
}

# ─── Command Handlers (remain in bash — signal traps, monitor_loop) ──

cmd_start() {
    # In automated mode, auto-defer untriaged ambiguities instead of pausing
    export TRIAGE_AUTO_DEFER=true

    # ── Auto-resume: if state file has active changes, skip planning entirely ──
    if [[ -f "$STATE_FILENAME" ]] && [[ "${FORCE_REPLAN:-}" != "true" ]]; then
        local _active_statuses='["running","pending","verifying","stalled","dispatched","verify-failed","done","merge-blocked"]'
        local _active_count
        _active_count=$(jq --argjson s "$_active_statuses" \
            '[.changes[] | select(.status as $st | $s | index($st))] | length' \
            "$STATE_FILENAME" 2>/dev/null || echo 0)
        if [[ "$_active_count" -gt 0 ]]; then
            info "Resuming from existing state ($_active_count active changes)"
            log_info "Auto-resume: $_active_count active changes in state — skipping planning"

            # Detect zombie processes (dead PIDs on running changes)
            local _zombie_pids
            _zombie_pids=$(jq -r '.changes[] | select(.status == "running") | .name + ":" + (.ralph_pid // 0 | tostring)' "$STATE_FILENAME" 2>/dev/null || true)
            while IFS=: read -r _zname _zpid; do
                [[ -z "$_zname" || "$_zpid" == "0" || "$_zpid" == "null" ]] && continue
                if ! kill -0 "$_zpid" 2>/dev/null; then
                    log_info "Zombie detected: $_zname (PID $_zpid dead) — will be handled by monitor stall recovery"
                    warn "Dead process detected for $_zname (PID $_zpid) — monitor will recover"
                fi
            done <<< "$_zombie_pids"

            # Verify directives file exists
            local _directives_file="$(lineage_directives_file "$(pwd)" 2>/dev/null || printf 'directives.json')"
            if [[ ! -f "$_directives_file" ]]; then
                # Try to regenerate from state or input
                if [[ -n "${INPUT_PATH:-}" ]] && [[ -e "${INPUT_PATH:-}" ]]; then
                    local _dir_regen
                    _dir_regen=$(resolve_directives "$INPUT_PATH")
                    echo "$_dir_regen" > "$_directives_file"
                    log_info "Regenerated directives from INPUT_PATH"
                elif [[ -f "$PLAN_FILENAME" ]]; then
                    local _plan_input
                    _plan_input=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
                    if [[ -n "$_plan_input" && -e "$_plan_input" ]]; then
                        local _dir_regen
                        _dir_regen=$(resolve_directives "$_plan_input")
                        echo "$_dir_regen" > "$_directives_file"
                        log_info "Regenerated directives from plan input_path"
                    fi
                fi
                if [[ ! -f "$_directives_file" ]]; then
                    error "Cannot resume: directives.json missing and cannot be regenerated"
                    error "Re-run with --spec to start fresh"
                    return 1
                fi
            fi

            local _dir_content
            _dir_content=$(cat "$_directives_file")
            local _max_parallel
            _max_parallel=$(echo "$_dir_content" | jq -r '.max_parallel // 3')

            # Setup cleanup trap
            local cleanup_done=false
            cleanup_orchestrator() {
                [[ "${cleanup_done:-}" == true ]] && return
                cleanup_done=true
                [[ -n "${_ORCH_DEV_SERVER_PID:-}" ]] && kill "$_ORCH_DEV_SERVER_PID" 2>/dev/null || true
                local current_status=""
                if [[ -f "$STATE_FILENAME" ]]; then
                    current_status=$(jq -r '.status // ""' "$STATE_FILENAME" 2>/dev/null || true)
                fi
                if [[ "$current_status" == "done" ]]; then
                    log_info "Orchestrator exiting normally (status=done)"
                    return
                fi
                warn "Orchestrator interrupted, saving state..."
                if [[ -f "$STATE_FILENAME" ]]; then
                    update_state_field "status" '"stopped"'
                fi
                log_info "Orchestrator stopped (auto-resume path)"
            }
            trap 'cleanup_orchestrator' EXIT
            trap 'exit 0' SIGTERM SIGINT SIGHUP

            # Recover orphaned changes and dispatch pending
            recover_orphaned_changes
            resume_stopped_changes
            dispatch_ready_changes "$_max_parallel"

            # Exec to Python monitor
            log_info "Exec'ing to Python monitor (auto-resume path)"
            log_info "  state_file=$STATE_FILENAME"
            log_info "  directives=$_directives_file"
            log_info "  cwd=$(pwd)"
            log_info "  python=$(which python3 2>/dev/null || echo 'not found')"
            trap - EXIT
            update_state_field "status" '"running"'
            exec set-orch-core engine monitor \
                --directives "$_directives_file" \
                --state "$STATE_FILENAME" \
                --poll-interval "${POLL_INTERVAL:-15}" \
                --default-model "$(echo "$_dir_content" | jq -r '.default_model // ""')" \
                --model-routing "$(echo "$_dir_content" | jq -r '.model_routing // "off"')" \
                ${CHECKPOINT_AUTO_APPROVE:+--checkpoint-auto-approve}
        fi
    fi

    # Auto-plan if no plan exists or CLI --spec/--brief differs from plan's input
    local need_plan=false
    # FORCE_REPLAN=false skips planning entirely (used by 'set-orchestrate resume')
    if [[ "${FORCE_REPLAN:-}" == "false" ]]; then
        need_plan=false
    elif [[ ! -f "$PLAN_FILENAME" ]]; then
        need_plan=true
    elif [[ -n "$SPEC_OVERRIDE" || -n "$BRIEF_OVERRIDE" ]]; then
        # CLI spec/brief provided — check if it matches the existing plan
        local plan_input_path
        plan_input_path=$(jq -r '.input_path // ""' "$PLAN_FILENAME" 2>/dev/null)
        local cli_input=""
        [[ -n "$SPEC_OVERRIDE" ]] && cli_input="$SPEC_OVERRIDE"
        [[ -n "$BRIEF_OVERRIDE" ]] && cli_input="$BRIEF_OVERRIDE"
        # Resolve cli_input to absolute path using the same logic as find_input():
        # short names like "v12" → set/orchestration/specs/v12.md, relative paths → absolute
        local resolved_cli="$cli_input"
        if [[ -n "$SPEC_OVERRIDE" ]]; then
            if [[ -d "$cli_input" ]]; then
                # Directory spec (digest mode)
                resolved_cli="$(cd "$cli_input" && pwd)"
            elif [[ -f "$cli_input" ]]; then
                resolved_cli="$(cd "$(dirname "$cli_input")" && pwd)/$(basename "$cli_input")"
            else
                # Try short-name resolution: set/orchestration/specs/<name>.md
                local wt_spec="set/orchestration/specs/${cli_input}.md"
                local wt_spec_sub="set/orchestration/specs/${cli_input}"
                if [[ -f "$wt_spec" ]]; then
                    resolved_cli="$(cd "$(dirname "$wt_spec")" && pwd)/$(basename "$wt_spec")"
                elif [[ -f "$wt_spec_sub" ]]; then
                    resolved_cli="$(cd "$(dirname "$wt_spec_sub")" && pwd)/$(basename "$wt_spec_sub")"
                fi
            fi
        elif [[ -n "$BRIEF_OVERRIDE" && -f "$cli_input" ]]; then
            resolved_cli="$(cd "$(dirname "$cli_input")" && pwd)/$(basename "$cli_input")"
        fi
        # Normalize paths for comparison (resolve ./ prefix, symlinks, etc.)
        local norm_plan norm_cli
        norm_plan=$(realpath -m "$plan_input_path" 2>/dev/null || echo "$plan_input_path")
        norm_cli=$(realpath -m "$resolved_cli" 2>/dev/null || echo "$resolved_cli")
        if [[ "$norm_plan" != "$norm_cli" ]]; then
            info "CLI input ($cli_input) differs from plan ($plan_input_path) — replanning"
            log_info "Input mismatch detected: CLI=$cli_input (resolved=$resolved_cli) plan=$plan_input_path — auto-replanning"
            need_plan=true
        else
            # Same path — check if content changed since last plan
            local plan_hash current_hash
            plan_hash=$(jq -r '.input_hash // ""' "$PLAN_FILENAME" 2>/dev/null)
            if [[ -d "$resolved_cli" ]]; then
                # Directory spec: use digest freshness check
                local freshness
                freshness=$(check_digest_freshness "$resolved_cli" 2>/dev/null || echo "missing")
                if [[ "$freshness" != "fresh" ]]; then
                    info "Spec directory changed since last digest — replanning"
                    log_info "Digest freshness: $freshness for $resolved_cli"
                    need_plan=true
                fi
            else
                current_hash=$(sha256sum "$resolved_cli" 2>/dev/null | cut -d' ' -f1)
                if [[ -n "$plan_hash" && -n "$current_hash" && "$plan_hash" != "$current_hash" ]]; then
                    info "Spec content changed since last plan — replanning"
                    log_info "Content hash mismatch: plan=$plan_hash current=$current_hash"
                    need_plan=true
                fi
            fi
        fi
    fi

    # History detection: warn if previous run tags exist but state is gone
    if [[ ! -f "$STATE_FILENAME" ]]; then
        local _orch_tags
        _orch_tags=$(git tag -l 'orch/*' 2>/dev/null || true)
        if [[ -n "$_orch_tags" ]]; then
            local _tag_count
            _tag_count=$(echo "$_orch_tags" | wc -l)
            warn "Previous orchestration history detected ($_tag_count orch/* tags) but no state file"
            info "Tags: $(echo "$_orch_tags" | tr '\n' ' ')"
            info "To recover: git log --oneline \$(git tag -l 'orch/*' | tail -1)"
            info "To clean tags: git tag -l 'orch/*' | xargs git tag -d"
            log_info "History detection: $_tag_count orch/* tags found without state file"
        fi
    fi

    if [[ "$need_plan" == true ]]; then
        # Guard: do not replan while changes are actively running
        if [[ -f "$STATE_FILENAME" ]]; then
            local _active_count
            _active_count=$(jq '[.changes[] | select(.status == "running" or .status == "verifying" or .status == "dispatching")] | length' "$STATE_FILENAME" 2>/dev/null || echo "0")
            if [[ "$_active_count" -gt 0 ]]; then
                warn "Spec changed but $_active_count change(s) still active — deferring replan"
                log_info "Replan deferred: $_active_count active changes, spec change detected"
                need_plan=false
            fi
        fi
    fi

    if [[ "$need_plan" == true ]]; then
        # Backup state before clean slate — recover if plan fails
        if [[ -f "$STATE_FILENAME" ]]; then
            cp "$STATE_FILENAME" "${STATE_FILENAME}.bak"
            log_info "State backed up to ${STATE_FILENAME}.bak"
        fi

        # Clean slate: remove plan/state artifacts for fresh planning
        local stale_files=("$PLAN_FILENAME" "$STATE_FILENAME" "$SUMMARY_FILENAME"
                           ".claude/orchestration-last-response.txt")
        for f in "${stale_files[@]}"; do
            if [[ -f "$f" ]]; then
                log_info "Removing stale file: $f"
                rm -f "$f"
            fi
        done
        info "Creating plan..."
        if ! cmd_plan; then
            # Plan failed — restore backed up state so orchestrator can continue
            if [[ -f "${STATE_FILENAME}.bak" ]]; then
                mv "${STATE_FILENAME}.bak" "$STATE_FILENAME"
                warn "Plan failed — restored previous state"
                log_error "cmd_plan failed, state restored from backup"
            fi
            return 1
        fi
        rm -f "${STATE_FILENAME}.bak"

        # Plan approval gate: if directive set, wait for user to approve
        local directives_for_gate
        directives_for_gate=$(parse_directives "$INPUT_PATH")
        local need_approval
        need_approval=$(echo "$directives_for_gate" | jq -r '.plan_approval // false')
        if [[ "$need_approval" == "true" ]]; then
            info "Plan generated. Review with 'set-orchestrate plan --show'"
            info "Approve with 'set-orchestrate approve' to begin dispatch."
            log_info "Plan approval required — entering plan_review state"
            init_state "$PLAN_FILENAME"
            update_state_field "status" '"plan_review"'
            return 0
        fi
    fi

    # Record start time for time-limit tracking
    ORCHESTRATOR_START_EPOCH=$(date +%s)

    if [[ -f "$STATE_FILENAME" ]]; then
        local current_status
        current_status=$(jq -r '.status' "$STATE_FILENAME")
        if [[ "$current_status" == "running" ]]; then
            # Check if any running change has a live Ralph PID
            local has_live_pid=false
            local running_pids
            running_pids=$(jq -r '.changes[] | select(.status == "running" or .status == "verifying") | .ralph_pid // 0' "$STATE_FILENAME" 2>/dev/null || true)
            while IFS= read -r pid; do
                [[ -z "$pid" || "$pid" == "0" || "$pid" == "null" ]] && continue
                if set-orch-core process check-pid --pid "$pid" --expect-cmd "set-loop" >/dev/null 2>&1; then
                    has_live_pid=true
                    break
                fi
            done <<< "$running_pids"
            if [[ "$has_live_pid" == true ]]; then
                warn "Orchestrator is already running. Use 'set-orchestrate status' to check progress."
                return 1
            fi
            # No live PIDs — crashed state, treat as stopped for resume
            log_info "Status=running but no live PIDs found — treating as crashed, entering resume path"
            info "Detected crashed state (no live processes) — resuming"
            current_status="stopped"
            update_state_field "status" '"stopped"'
        fi
        # Previous run completed — start fresh
        if [[ "$current_status" == "done" ]]; then
            log_info "Previous run completed (status=done) — starting fresh"
            rm -f "$STATE_FILENAME"
        fi
        # Plan review: wait for approval
        if [[ "$current_status" == "plan_review" ]]; then
            info "Plan is pending approval. Review with 'set-orchestrate plan --show'"
            info "Approve with 'set-orchestrate approve' to begin dispatch."
            return 0
        fi
        # Resume from time_limit, stopped, or checkpoint: continue where we left off
        if [[ -f "$STATE_FILENAME" ]] && [[ "$current_status" == "time_limit" || "$current_status" == "stopped" || "$current_status" == "checkpoint" ]]; then
            info "Resuming from previous run (status: $current_status)"
            log_info "Resuming orchestration (was: $current_status)"
            update_state_field "status" '"running"'

            # Clear stale audit/E2E results from previous execution
            safe_jq_update "$STATE_FILENAME" '.phase_audit_results = []'
            safe_jq_update "$STATE_FILENAME" '.phase_e2e_results = []'
            log_info "Cleared stale phase_audit_results and phase_e2e_results from previous run"

            # Restore input path from plan
            if [[ -z "${INPUT_PATH:-}" || ! -e "${INPUT_PATH:-}" ]]; then
                INPUT_MODE=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
                INPUT_PATH=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
                if [[ -z "$INPUT_PATH" || ! -e "$INPUT_PATH" ]]; then
                    error "Cannot find input from plan: $INPUT_PATH"
                    return 1
                fi
            fi

            local directives
            directives=$(resolve_directives "$INPUT_PATH")
            local max_parallel
            max_parallel=$(echo "$directives" | jq -r '.max_parallel')
            local pause_on_exit_val
            pause_on_exit_val=$(echo "$directives" | jq -r '.pause_on_exit')

            # Persist directives in state (may have changed since last run)
            update_state_field "directives" "$(echo "$directives" | jq -c .)"

            # Setup cleanup trap
            local cleanup_done=false
            cleanup_orchestrator() {
                [[ "${cleanup_done:-}" == true ]] && return
                cleanup_done=true
                # Kill dev server if auto-started by smoke pipeline
                [[ -n "${_ORCH_DEV_SERVER_PID:-}" ]] && kill "$_ORCH_DEV_SERVER_PID" 2>/dev/null || true
                # Don't overwrite "done" status — only set "stopped" if still running
                local current_status=""
                if [[ -f "$STATE_FILENAME" ]]; then
                    current_status=$(jq -r '.status // ""' "$STATE_FILENAME" 2>/dev/null || true)
                fi
                if [[ "$current_status" == "done" ]]; then
                    log_info "Orchestrator exiting normally (status=done)"
                    exit 0
                fi
                echo ""
                warn "Orchestrator interrupted, saving state..."
                log_info "Orchestrator interrupted by signal"
                if [[ -f "$STATE_FILENAME" ]]; then
                    update_state_field "status" '"stopped"'
                fi
                if [[ "${pause_on_exit_val:-}" == "true" ]]; then
                    local running_changes
                    running_changes=$(get_changes_by_status "running" 2>/dev/null || true)
                    while IFS= read -r name; do
                        [[ -z "$name" ]] && continue
                        pause_change "$name" 2>/dev/null || true
                    done <<< "$running_changes"
                fi
                log_info "Orchestrator stopped"
            }
            trap 'cleanup_orchestrator' EXIT
            trap 'exit 0' SIGTERM SIGINT SIGHUP

            # Apply dispatch-critical globals from directives BEFORE first dispatch
            DEFAULT_IMPL_MODEL=$(echo "$directives" | jq -r '.default_model // ""')
            TEAM_MODE=$(echo "$directives" | jq -r 'if .team_mode == true then "yes" else "" end')
            CONTEXT_PRUNING=$(echo "$directives" | jq -r '.context_pruning // true')
            MODEL_ROUTING=$(echo "$directives" | jq -r '.model_routing // "off"')
            CHECKPOINT_AUTO_APPROVE=$(echo "$directives" | jq -r 'if .checkpoint_auto_approve == true then "yes" else "" end')

            # Recover orphaned changes (running/verifying with no worktree/PID)
            recover_orphaned_changes
            # Note: retry_merge_queue is now handled by Python monitor loop
            # Resume changes that were running when we were interrupted
            resume_stopped_changes
            # Dispatch any remaining pending changes
            dispatch_ready_changes "$max_parallel"

            # Exec to Python monitor loop
            log_info "Exec'ing to Python monitor (resume path)"
            # Clear EXIT trap — exec replaces the process, and the bash EXIT
            # trap would write status=stopped before Python starts
            trap - EXIT
            update_state_field "status" '"running"'
            local _directives_file="$(lineage_directives_file "$(pwd)" 2>/dev/null || printf 'directives.json')"
            echo "$directives" > "$_directives_file"
            log_info "Exec'ing to Python monitor (fresh start)"
            log_info "  state_file=$STATE_FILENAME"
            log_info "  directives=$_directives_file"
            log_info "  cwd=$(pwd)"
            exec set-orch-core engine monitor \
                --directives "$_directives_file" \
                --state "$STATE_FILENAME" \
                --poll-interval "${POLL_INTERVAL:-15}" \
                --default-model "$(echo "$directives" | jq -r '.default_model // ""')" \
                ${TEAM_MODE:+--team-mode} \
                --model-routing "$(echo "$directives" | jq -r '.model_routing // "off"')" \
                ${CHECKPOINT_AUTO_APPROVE:+--checkpoint-auto-approve}
        fi
    fi

    info "Starting orchestration..."
    log_info "Orchestration started"

    # Restore input path from plan (so --spec is not needed again)
    if [[ -z "${INPUT_PATH:-}" || ! -e "${INPUT_PATH:-}" ]]; then
        INPUT_MODE=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
        INPUT_PATH=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
        if [[ -z "$INPUT_PATH" || ! -e "$INPUT_PATH" ]]; then
            error "Cannot find input from plan: $INPUT_PATH"
            error "Re-run with --spec or --brief, or regenerate the plan."
            return 1
        fi
        log_info "Restored input from plan: $INPUT_MODE @ $INPUT_PATH"
    fi

    local directives
    directives=$(resolve_directives "$INPUT_PATH")
    local max_parallel
    max_parallel=$(echo "$directives" | jq -r '.max_parallel')
    local pause_on_exit_val
    pause_on_exit_val=$(echo "$directives" | jq -r '.pause_on_exit')

    # Initialize state from plan
    init_state "$PLAN_FILENAME"

    # Persist directives in state so post-merge steps can read them
    update_state_field "directives" "$(echo "$directives" | jq -c .)"

    # Stale change detection: warn about orphaned openspec change directories
    if [[ -d "openspec/changes" ]]; then
        local plan_names
        plan_names=$(jq -r '.changes[].name' "$PLAN_FILENAME" 2>/dev/null || true)
        for change_dir in openspec/changes/*/; do
            [[ -d "$change_dir" ]] || continue
            local dir_name
            dir_name=$(basename "$change_dir")
            # Skip archive and hidden dirs
            [[ "$dir_name" == "archive" || "$dir_name" == .* ]] && continue
            # Check if this change is in the current plan
            if echo "$plan_names" | grep -qxF "$dir_name"; then
                continue
            fi
            # Check if an active worktree exists for this change
            if find_existing_worktree "$(pwd)" "$dir_name" &>/dev/null; then
                continue
            fi
            log_warn "Orphaned change directory: openspec/changes/$dir_name (not in plan, no active worktree)"
        done
    fi

    # Setup cleanup trap
    local cleanup_done=false
    cleanup_orchestrator() {
        [[ "${cleanup_done:-}" == true ]] && return
        cleanup_done=true

        # Kill dev server if auto-started by smoke pipeline
        [[ -n "${_ORCH_DEV_SERVER_PID:-}" ]] && kill "$_ORCH_DEV_SERVER_PID" 2>/dev/null || true

        # Don't overwrite "done" status — only set "stopped" if still running
        local current_status=""
        if [[ -f "$STATE_FILENAME" ]]; then
            current_status=$(jq -r '.status // ""' "$STATE_FILENAME" 2>/dev/null || true)
        fi
        if [[ "$current_status" == "done" ]]; then
            log_info "Orchestrator exiting normally (status=done)"
            return
        fi

        echo ""
        warn "Orchestrator interrupted, saving state..."
        log_info "Orchestrator interrupted by signal"

        if [[ -f "$STATE_FILENAME" ]]; then
            update_state_field "status" '"stopped"'
        fi

        if [[ "${pause_on_exit_val:-}" == "true" ]]; then
            log_info "Pausing all Ralph loops (pause_on_exit=true)"
            local running_changes
            running_changes=$(get_changes_by_status "running" 2>/dev/null || true)
            while IFS= read -r name; do
                [[ -z "$name" ]] && continue
                pause_change "$name" 2>/dev/null || true
            done <<< "$running_changes"
        fi

        log_info "Orchestrator stopped"
    }
    trap 'cleanup_orchestrator' EXIT
    trap 'exit 0' SIGTERM SIGINT SIGHUP

    # Apply dispatch-critical globals from directives BEFORE first dispatch
    # (monitor_loop sets these too, but dispatch_ready_changes runs first)
    DEFAULT_IMPL_MODEL=$(echo "$directives" | jq -r '.default_model // ""')
    TEAM_MODE=$(echo "$directives" | jq -r 'if .team_mode == true then "yes" else "" end')
    CONTEXT_PRUNING=$(echo "$directives" | jq -r '.context_pruning // true')
    MODEL_ROUTING=$(echo "$directives" | jq -r '.model_routing // "off"')
    CHECKPOINT_AUTO_APPROVE=$(echo "$directives" | jq -r 'if .checkpoint_auto_approve == true then "yes" else "" end')

    # Resume any stopped changes from a previous interrupted run
    resume_stopped_changes
    # Dispatch initial changes
    dispatch_ready_changes "$max_parallel"

    # Exec to Python monitor loop
    log_info "Exec'ing to Python monitor (digest start)"
    log_info "  state_file=$STATE_FILENAME"
    log_info "  cwd=$(pwd)"
    # Clear EXIT trap — exec replaces the process, and the bash EXIT
    # trap would write status=stopped before Python starts
    trap - EXIT
    update_state_field "status" '"running"'
    local _directives_file="$(lineage_directives_file "$(pwd)" 2>/dev/null || printf 'directives.json')"
    echo "$directives" > "$_directives_file"
    exec set-orch-core engine monitor \
        --directives "$_directives_file" \
        --state "$STATE_FILENAME" \
        --poll-interval "${POLL_INTERVAL:-15}" \
        --default-model "$(echo "$directives" | jq -r '.default_model // ""')" \
        ${TEAM_MODE:+--team-mode} \
        --model-routing "$(echo "$directives" | jq -r '.model_routing // "off"')" \
        ${CHECKPOINT_AUTO_APPROVE:+--checkpoint-auto-approve}
}

cmd_pause() {
    local target="${1:-}"

    if [[ "$target" == "--all" ]]; then
        info "Pausing all running changes..."
        local running_changes
        running_changes=$(get_changes_by_status "running")
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            pause_change "$name"
        done <<< "$running_changes"
        update_state_field "status" '"paused"'
        log_info "All changes paused"
        success "All changes paused"
    elif [[ -n "$target" ]]; then
        pause_change "$target"
    else
        error "Usage: set-orchestrate pause <change-name> | --all"
        return 1
    fi
}

cmd_resume() {
    local target="${1:-}"

    if [[ ! -f "$STATE_FILENAME" ]]; then
        error "No orchestration state found."
        return 1
    fi

    # Restore input from plan if not provided via flags
    if [[ -z "${INPUT_PATH:-}" ]] && [[ -f "$PLAN_FILENAME" ]]; then
        INPUT_MODE=$(jq -r '.input_mode // empty' "$PLAN_FILENAME" 2>/dev/null)
        INPUT_PATH=$(jq -r '.input_path // empty' "$PLAN_FILENAME" 2>/dev/null)
    fi
    find_input 2>/dev/null || true  # best-effort for directives
    local max_parallel="$DEFAULT_MAX_PARALLEL"
    if [[ -n "${INPUT_PATH:-}" ]]; then
        max_parallel=$(resolve_directives "$INPUT_PATH" | jq -r '.max_parallel')
    fi

    if [[ "$target" == "--all" ]]; then
        info "Resuming all paused changes..."
        local paused_changes
        paused_changes=$(get_changes_by_status "paused")
        local count=0
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            local running
            running=$(count_changes_by_status "running")
            if [[ "$running" -ge "$max_parallel" ]]; then
                info "Max parallel ($max_parallel) reached, $name stays paused"
                continue
            fi
            resume_change "$name"
            count=$((count + 1))
        done <<< "$paused_changes"
        update_state_field "status" '"running"'
        log_info "Resumed $count changes"
        success "Resumed $count changes"
    elif [[ -n "$target" ]]; then
        resume_change "$target"
        update_state_field "status" '"running"'
    else
        # No target: resume the orchestration itself (skip planning, use existing state)
        if [[ ! -f "$STATE_FILENAME" ]]; then
            error "No orchestration state found. Use 'set-orchestrate start --spec <path>' to begin."
            return 1
        fi
        info "Resuming orchestration from existing state..."
        FORCE_REPLAN=false cmd_start "$@"
        return $?
    fi
}

# ─── Monitor Loop ────────────────────────────────────────────────────
