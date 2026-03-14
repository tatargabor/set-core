#!/usr/bin/env bash
# lib/orchestration/merger.sh — Merge, cleanup, archive operations
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: state.sh (update_change_field, etc.), events.sh (emit_event),
#             dispatcher.sh (resume_change, check_base_build, fix_base_build_with_llm),
#             verifier.sh (verify_merge_scope, extract_health_check_url, health_check, smoke_fix_scoped)

# ─── Archive ─────────────────────────────────────────────────────────

archive_change() {
    local change_name="$1"
    local change_dir="openspec/changes/$change_name"

    # Skip if change directory doesn't exist
    [[ -d "$change_dir" ]] || return 0

    local archive_dir="openspec/changes/archive"
    local dated_name="$(date +%Y-%m-%d)-$change_name"
    local dest="$archive_dir/$dated_name"

    (
        mkdir -p "$archive_dir"
        mv "$change_dir" "$dest"
        git add "$dest" "$change_dir" 2>/dev/null || true
        git commit -m "chore: archive $change_name change" --no-verify 2>/dev/null || true
        log_info "Archived $change_name → $dest"
    ) || {
        log_warn "Failed to archive $change_name (non-blocking)"
    }
}

# ─── Smoke Screenshot Collection ─────────────────────────────────────

# Collect Playwright test-results/ artifacts after a smoke run.
# Uses attempt-N/ subdirectories to preserve screenshots from each attempt.
# Args: change_name
_collect_smoke_screenshots() {
    local change_name="$1"
    local attempt_num
    attempt_num=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .smoke_fix_attempts // 0' "$STATE_FILENAME" 2>/dev/null || echo 0)
    local sc_dir="wt/orchestration/smoke-screenshots/$change_name/attempt-$((attempt_num + 1))"
    mkdir -p "$sc_dir"
    if [[ -d "test-results" ]]; then
        cp -r test-results/* "$sc_dir/" 2>/dev/null || true
    fi
    local sc_count
    sc_count=$(find "wt/orchestration/smoke-screenshots/$change_name" -name "*.png" 2>/dev/null | wc -l)
    update_change_field "$change_name" "smoke_screenshot_dir" "\"wt/orchestration/smoke-screenshots/$change_name\""
    update_change_field "$change_name" "smoke_screenshot_count" "$sc_count"
    log_info "Smoke screenshots: collected $sc_count images for $change_name (attempt $((attempt_num + 1)))"
}

# ─── Merge ───────────────────────────────────────────────────────────

merge_change() {
    local change_name="$1"

    log_info "Merging $change_name..."
    info "Merging: $change_name"

    # Merge timeout: track start time for checkpoint-based elapsed checks
    local _merge_start_ts
    _merge_start_ts=$(date +%s)
    local _merge_timeout
    _merge_timeout=$(jq -r ".directives.merge_timeout // $DEFAULT_MERGE_TIMEOUT" "$STATE_FILENAME" 2>/dev/null || echo "$DEFAULT_MERGE_TIMEOUT")

    # Helper: check if merge has exceeded timeout
    _merge_timed_out() {
        local now
        now=$(date +%s)
        local elapsed=$((now - _merge_start_ts))
        [[ "$elapsed" -ge "$_merge_timeout" ]]
    }

    # Pre-merge hook
    local wt_path_for_hook
    wt_path_for_hook=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    if ! run_hook "pre_merge" "$change_name" "done" "$wt_path_for_hook"; then
        log_warn "pre_merge hook blocked $change_name"
        return 1
    fi

    emit_event "MERGE_ATTEMPT" "$change_name" '{}'

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")

    local source_branch="change/$change_name"
    local branch_exists=false
    git show-ref --verify --quiet "refs/heads/$source_branch" 2>/dev/null && branch_exists=true

    # Case 1: Branch no longer exists — someone already merged and deleted it
    if ! $branch_exists; then
        info "Already handled: $change_name (branch $source_branch no longer exists)"
        log_info "Skipping merge for $change_name — branch deleted (assumed merged)"
        update_change_field "$change_name" "status" '"merged"'
        update_change_field "$change_name" "smoke_result" '"skip_merged"'
        update_change_field "$change_name" "smoke_status" '"skipped"'
        update_coverage_status "$change_name" "merged" 2>/dev/null || true
        cleanup_worktree "$change_name" "$wt_path"
        archive_change "$change_name"
        safe_jq_update "$STATE_FILENAME" --arg n "$change_name" '.merge_queue -= [$n]'
        return 0
    fi

    # Case 2: Branch exists but is already ancestor of HEAD (manual merge, branch not deleted)
    local source_sha
    source_sha=$(git rev-parse "$source_branch" 2>/dev/null || true)
    if [[ -n "$source_sha" ]] && git merge-base --is-ancestor "$source_sha" HEAD 2>/dev/null; then
        info "Already merged: $change_name (branch $source_branch is ancestor of HEAD)"
        log_info "Skipping merge for $change_name — already merged"
        update_change_field "$change_name" "status" '"merged"'
        update_change_field "$change_name" "smoke_result" '"skip_merged"'
        update_change_field "$change_name" "smoke_status" '"skipped"'
        update_coverage_status "$change_name" "merged" 2>/dev/null || true
        cleanup_worktree "$change_name" "$wt_path"
        archive_change "$change_name"
        safe_jq_update "$STATE_FILENAME" --arg n "$change_name" '.merge_queue -= [$n]'
        return 0
    fi

    # Case 3: Normal merge (with LLM conflict resolution)
    if wt-merge "$change_name" --no-push --llm-resolve >>"$LOG_FILE" 2>&1; then
        update_change_field "$change_name" "status" '"merged"'
        update_coverage_status "$change_name" "merged" 2>/dev/null || true
        log_info "Merged $change_name"
        success "Merged: $change_name"

        # Git history protection: tag the merge point for recovery
        git tag -f "orch/$change_name" HEAD 2>/dev/null || true
        local merged_count
        merged_count=$(jq '[.changes[] | select(.status == "merged" or .status == "done")] | length' "$STATE_FILENAME" 2>/dev/null || echo "0")
        merged_count=$((merged_count + 1))  # include this merge (state not yet updated for some paths)
        git tag -f "orch/merged-${merged_count}" HEAD 2>/dev/null || true
        log_info "Tagged: orch/$change_name, orch/merged-${merged_count}"

        # Sync running worktrees with updated main to prevent stale-main gate failures
        _sync_running_worktrees "$change_name"

        # Invalidate base build cache — merge changes main, old result is stale
        BASE_BUILD_STATUS=""
        BASE_BUILD_OUTPUT=""
        BASE_BUILD_FIX_ATTEMPTED=false

        # Post-merge dependency install: if package.json changed, run package manager install
        local pkg_changed=false
        git diff HEAD~1 --name-only 2>/dev/null | grep -q '^package\.json$' && pkg_changed=true
        if $pkg_changed; then
            local install_cmd=""
            if [[ -f "pnpm-lock.yaml" ]]; then
                install_cmd="pnpm install"
            elif [[ -f "yarn.lock" ]]; then
                install_cmd="yarn install"
            elif [[ -f "package-lock.json" ]]; then
                install_cmd="npm install"
            fi
            if [[ -n "$install_cmd" ]]; then
                log_info "Post-merge: package.json changed, running $install_cmd"
                if $install_cmd >> "$LOG_FILE" 2>&1; then
                    log_info "Post-merge: $install_cmd succeeded"
                else
                    log_warn "Post-merge: $install_cmd failed (merge not reverted)"
                fi
            fi
        fi

        # Post-merge custom command (project-specific, e.g. "pnpm db:generate" for Prisma)
        local pmc=""
        pmc=$(jq -r '.directives.post_merge_command // empty' "$STATE_FILENAME" 2>/dev/null || true)
        if [[ -n "$pmc" ]]; then
            log_info "Post-merge: running custom command: $pmc"
            local pmc_rc=0
            timeout 300 bash -c "$pmc" >> "$LOG_FILE" 2>&1 || pmc_rc=$?
            if [[ $pmc_rc -eq 0 ]]; then
                log_info "Post-merge: custom command succeeded"
            else
                log_warn "Post-merge: custom command failed (rc=$pmc_rc)"
            fi
        fi

        # Post-merge scope verification: did implementation files actually land?
        if ! verify_merge_scope "$change_name"; then
            send_notification "wt-orchestrate" "Scope verify FAILED for $change_name — only artifact files merged, no implementation code!" "critical"
            orch_remember "Scope verification failed for $change_name — merged but no implementation files landed" Decision "phase:post-merge,change:$change_name"
        fi

        # Post-merge build verification: ensure main still builds after merge
        if [[ -n "$test_command" || -n "$(jq -r '.directives.test_command // empty' "$STATE_FILENAME" 2>/dev/null)" ]]; then
            local build_command="build"
            local pm="pnpm"
            [[ -f "yarn.lock" ]] && pm="yarn"
            [[ -f "package-lock.json" ]] && pm="npm"
            log_info "Post-merge: verifying build on main after merging $change_name"
            local post_merge_build_output=""
            local post_merge_rc=0
            post_merge_build_output=$(timeout 300 $pm run $build_command 2>&1) || post_merge_rc=$?
            if [[ $post_merge_rc -ne 0 ]]; then
                log_error "Post-merge: build FAILED on main after merging $change_name"
                log_error "Post-merge build output: ${post_merge_build_output: -500}"
                # Store build output for fix_base_build_with_llm
                BASE_BUILD_STATUS="fail"
                BASE_BUILD_OUTPUT="$post_merge_build_output"
                log_info "Post-merge: attempting automatic build fix for $change_name"
                if fix_base_build_with_llm "$PROJECT_PATH"; then
                    log_info "Post-merge: build fix succeeded after merging $change_name"
                else
                    send_notification "wt-orchestrate" "Post-merge build broken after $change_name merge! Auto-fix failed." "critical"
                    orch_remember "Post-merge build failed after merging $change_name — auto-fix attempted but failed" Decision "phase:post-merge,change:$change_name"
                fi
            else
                log_info "Post-merge: build passed on main"
            fi
        fi

        # Merge timeout checkpoint: abort before smoke if already over time
        if _merge_timed_out; then
            local _elapsed=$(( $(date +%s) - _merge_start_ts ))
            log_error "Merge timeout: $change_name exceeded ${_merge_timeout}s (elapsed: ${_elapsed}s) — aborting before smoke"
            update_change_field "$change_name" "status" '"merge_timeout"'
            send_notification "wt-orchestrate" "Merge timeout for $change_name after ${_elapsed}s (limit: ${_merge_timeout}s)" "critical"
            safe_jq_update "$STATE_FILENAME" --arg n "$change_name" '.merge_queue -= [$n]'
            return 0
        fi

        # Post-merge smoke/e2e tests: run on main after merge (not pre-merge — worktree code isn't on localhost)
        # Read smoke config from persisted state (not monitor_loop locals)
        local smoke_command smoke_blocking smoke_timeout smoke_health_check_url smoke_health_check_timeout smoke_fix_max_retries smoke_fix_max_turns
        smoke_command=$(jq -r '.directives.smoke_command // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        smoke_blocking=$(jq -r '.directives.smoke_blocking // "false"' "$STATE_FILENAME" 2>/dev/null || echo "false")
        smoke_timeout=$(jq -r '.directives.smoke_timeout // "120"' "$STATE_FILENAME" 2>/dev/null || echo "120")
        smoke_health_check_url=$(jq -r '.directives.smoke_health_check_url // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        smoke_health_check_timeout=$(jq -r '.directives.smoke_health_check_timeout // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        smoke_fix_max_retries=$(jq -r '.directives.smoke_fix_max_retries // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        smoke_fix_max_turns=$(jq -r '.directives.smoke_fix_max_turns // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
        if [[ -n "${smoke_command:-}" ]]; then
            update_change_field "$change_name" "smoke_status" '"pending"'

            if [[ "${smoke_blocking:-false}" == "true" ]]; then
                # === BLOCKING SMOKE PIPELINE ===
                # flock is already held from merge — extends through smoke+fix
                log_info "Post-merge: blocking smoke pipeline for $change_name"

                # Health check: verify dev server is responding
                local hc_url="${smoke_health_check_url:-}"
                if [[ -z "$hc_url" ]]; then
                    hc_url=$(extract_health_check_url "$smoke_command")
                fi
                update_change_field "$change_name" "smoke_status" '"checking"'
                if [[ -n "$hc_url" ]] && ! health_check "$hc_url" "${smoke_health_check_timeout:-$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT}"; then
                    # Health check failed — try auto-starting dev server if configured
                    local smoke_dev_server_command
                    smoke_dev_server_command=$(jq -r '.directives.smoke_dev_server_command // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
                    if [[ -n "$smoke_dev_server_command" ]]; then
                        log_info "Post-merge: health check failed, auto-starting dev server for $change_name"
                        bash -c "$smoke_dev_server_command" &
                        _ORCH_DEV_SERVER_PID=$!
                        export _ORCH_DEV_SERVER_PID
                        # Wait for server with extended timeout (60s)
                        if health_check "$hc_url" 60; then
                            log_info "Post-merge: dev server auto-started (PID $_ORCH_DEV_SERVER_PID), health check passed"
                        else
                            log_error "Post-merge: dev server auto-start failed for $change_name — killing PID $_ORCH_DEV_SERVER_PID"
                            kill "$_ORCH_DEV_SERVER_PID" 2>/dev/null || true
                            _ORCH_DEV_SERVER_PID=""
                            update_change_field "$change_name" "smoke_result" '"blocked"'
                            update_change_field "$change_name" "smoke_status" '"blocked"'
                            update_change_field "$change_name" "status" '"smoke_blocked"'
                            send_notification "wt-orchestrate" "Smoke blocked for $change_name — dev server auto-start failed at $hc_url" "critical"
                            orch_remember "Smoke blocked for $change_name — dev server auto-start failed at $hc_url" Decision "phase:post-merge,change:$change_name"
                            return 0
                        fi
                    else
                        log_error "Post-merge: health check FAILED for $change_name — no server at $hc_url"
                        update_change_field "$change_name" "smoke_result" '"blocked"'
                        update_change_field "$change_name" "smoke_status" '"blocked"'
                        update_change_field "$change_name" "status" '"smoke_blocked"'
                        send_notification "wt-orchestrate" "Smoke blocked for $change_name — no server at $hc_url" "critical"
                        orch_remember "Smoke blocked for $change_name — dev server not responding at $hc_url" Decision "phase:post-merge,change:$change_name"
                        return 0
                    fi
                fi

                # Recompile buffer
                sleep 5

                # Run smoke
                update_change_field "$change_name" "smoke_status" '"running"'
                log_info "Post-merge: running smoke tests (blocking) for $change_name"
                local pm_smoke_output=""
                local pm_smoke_rc=0
                pm_smoke_output=$(timeout "${smoke_timeout:-120}" bash -c "$smoke_command" 2>&1) || pm_smoke_rc=$?

                # Collect screenshots regardless of pass/fail
                _collect_smoke_screenshots "$change_name"

                if [[ $pm_smoke_rc -eq 0 ]]; then
                    log_info "Post-merge: smoke tests passed for $change_name"
                    update_change_field "$change_name" "smoke_result" '"pass"'
                    update_change_field "$change_name" "smoke_status" '"done"'
                    update_state_field "last_smoke_pass_commit" "\"$(git rev-parse HEAD)\""
                else
                    log_error "Post-merge: smoke tests FAILED for $change_name (exit $pm_smoke_rc)"
                    update_change_field "$change_name" "smoke_result" '"fail"'
                    update_change_field "$change_name" "smoke_fix_attempts" "0"

                    # Merge timeout checkpoint: abort before fix cycle if over time
                    if _merge_timed_out; then
                        local _elapsed=$(( $(date +%s) - _merge_start_ts ))
                        log_error "Merge timeout: $change_name exceeded ${_merge_timeout}s during smoke fix — aborting"
                        update_change_field "$change_name" "status" '"merge_timeout"'
                        update_change_field "$change_name" "smoke_status" '"timeout"'
                        send_notification "wt-orchestrate" "Merge timeout for $change_name after ${_elapsed}s (limit: ${_merge_timeout}s) — smoke fix aborted" "critical"
                        safe_jq_update "$STATE_FILENAME" --arg n "$change_name" '.merge_queue -= [$n]'
                        return 0
                    fi

                    # Scoped fix agent with retries
                    if smoke_fix_scoped "$change_name" "$smoke_command" "${smoke_timeout:-120}" \
                            "${smoke_fix_max_retries:-$DEFAULT_SMOKE_FIX_MAX_RETRIES}" "${smoke_fix_max_turns:-$DEFAULT_SMOKE_FIX_MAX_TURNS}" "$pm_smoke_output"; then
                        update_change_field "$change_name" "smoke_result" '"fixed"'
                        update_change_field "$change_name" "smoke_status" '"done"'
                        update_state_field "last_smoke_pass_commit" "\"$(git rev-parse HEAD)\""
                        orch_remember "Scoped fix resolved post-merge smoke failure for $change_name" Learning "phase:post-merge,change:$change_name"
                    else
                        update_change_field "$change_name" "smoke_status" '"failed"'
                        update_change_field "$change_name" "status" '"smoke_failed"'
                        send_notification "wt-orchestrate" "Post-merge smoke FAILED for $change_name — scoped fix exhausted (${smoke_fix_max_retries:-$DEFAULT_SMOKE_FIX_MAX_RETRIES} retries)" "critical"
                        orch_remember "Post-merge smoke failed for $change_name — scoped fix exhausted" Decision "phase:post-merge,change:$change_name"
                        # Don't proceed to cleanup/archive — leave for sentinel
                        return 0
                    fi
                fi
            else
                # === NON-BLOCKING SMOKE (legacy behavior) ===
                log_info "Post-merge: running smoke/e2e tests on main for $change_name"
                local pm_smoke_output=""
                local pm_smoke_rc=0
                pm_smoke_output=$(timeout "${smoke_timeout:-120}" bash -c "$smoke_command" 2>&1) || pm_smoke_rc=$?
                # Collect screenshots regardless of pass/fail
                _collect_smoke_screenshots "$change_name"

                if [[ $pm_smoke_rc -eq 0 ]]; then
                    log_info "Post-merge: smoke tests passed for $change_name"
                    update_change_field "$change_name" "smoke_result" '"pass"'
                    update_change_field "$change_name" "smoke_status" '"done"'
                    update_state_field "last_smoke_pass_commit" "\"$(git rev-parse HEAD)\""
                else
                    log_error "Post-merge: smoke tests FAILED for $change_name (exit $pm_smoke_rc)"
                    log_error "Post-merge smoke output: ${pm_smoke_output: -500}"
                    update_change_field "$change_name" "smoke_result" '"fail"'
                    update_change_field "$change_name" "smoke_status" '"failed"'
                    # Attempt generic LLM fix (legacy — no change context)
                    log_info "Post-merge: attempting LLM smoke fix on main for $change_name"
                    # Multi-change context for legacy path
                    local _legacy_mc_ctx=""
                    local _legacy_since
                    _legacy_since=$(jq -r '.last_smoke_pass_commit // ""' "$STATE_FILENAME" 2>/dev/null || echo "")
                    if [[ -n "$_legacy_since" ]]; then
                        local _legacy_merged
                        _legacy_merged=$(git log --oneline "$_legacy_since..HEAD" --merges 2>/dev/null || true)
                        if [[ -n "$_legacy_merged" && $(echo "$_legacy_merged" | wc -l) -gt 1 ]]; then
                            _legacy_mc_ctx="
Multiple changes merged since last smoke pass:
$_legacy_merged

The failure may be caused by an interaction between changes, not just the last one.
"
                        fi
                    fi
                    local smoke_fix_prompt
                    smoke_fix_prompt=$(jq -n \
                        --arg change_name "$change_name" \
                        --arg scope "" \
                        --arg output_tail "${pm_smoke_output: -2000}" \
                        --arg smoke_cmd "$smoke_command" \
                        --arg multi_change_context "$_legacy_mc_ctx" \
                        --arg variant "smoke" \
                        '{change_name: $change_name, scope: $scope, output_tail: $output_tail, smoke_cmd: $smoke_cmd, multi_change_context: $multi_change_context, variant: $variant}' \
                    | wt-orch-core template fix --input-file -)
                    local smoke_fix_rc=0
                    echo "$smoke_fix_prompt" | run_claude --model "$(model_id sonnet)" --max-turns 20 >>"$LOG_FILE" 2>&1 || smoke_fix_rc=$?
                    if [[ $smoke_fix_rc -eq 0 ]]; then
                        local recheck_rc=0
                        timeout "${smoke_timeout:-120}" bash -c "$smoke_command" >>"$LOG_FILE" 2>&1 || recheck_rc=$?
                        if [[ $recheck_rc -eq 0 ]]; then
                            log_info "Post-merge: smoke fix SUCCEEDED for $change_name"
                            update_change_field "$change_name" "smoke_result" '"fixed"'
                            update_change_field "$change_name" "smoke_status" '"done"'
                            update_state_field "last_smoke_pass_commit" "\"$(git rev-parse HEAD)\""
                            orch_remember "LLM fixed post-merge smoke failure for $change_name" Learning "phase:post-merge,change:$change_name"
                        else
                            log_error "Post-merge: smoke fix attempt did not resolve failures for $change_name"
                            send_notification "wt-orchestrate" "Post-merge smoke FAILED for $change_name — LLM fix attempted but smoke still failing" "critical"
                            orch_remember "Post-merge smoke failed for $change_name — LLM fix attempt did not resolve" Decision "phase:post-merge,change:$change_name"
                        fi
                    else
                        send_notification "wt-orchestrate" "Post-merge smoke FAILED for $change_name — LLM fix also failed" "critical"
                        orch_remember "Post-merge smoke failed for $change_name — LLM fix failed" Decision "phase:post-merge,change:$change_name"
                    fi
                fi
            fi
        fi

        local iter_count
        iter_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .iterations // 0' "$STATE_FILENAME" 2>/dev/null || echo "?")
        orch_remember "Merged $change_name successfully ($iter_count iterations)" Context "phase:merge,change:$change_name"

        # Post-merge hook
        run_hook "post_merge" "$change_name" "merged" "" || true  # non-blocking

        cleanup_worktree "$change_name" "$wt_path"
        archive_change "$change_name"
        # Remove from merge queue if present
        safe_jq_update "$STATE_FILENAME" --arg n "$change_name" '.merge_queue -= [$n]'
    else
        # Log level: ERROR on first conflict, INFO on subsequent (retry) calls
        local merge_retry_count
        merge_retry_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .merge_retry_count // 0' "$STATE_FILENAME")
        if [[ "$merge_retry_count" -eq 0 ]]; then
            warn "Merge conflict for $change_name"
            log_error "Merge conflict for $change_name"
            orch_remember "Merge conflict for $change_name — consider sequencing this change after its conflicting dependencies in future plans" Decision "phase:merge,change:$change_name"
        else
            log_info "Merge conflict for $change_name (retry $merge_retry_count)"
        fi

        # Pre-validate: confirm conflict actually exists before spawning expensive agent loop
        local main_branch
        main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
        git fetch origin "$main_branch" 2>/dev/null || true
        local merge_base_test
        merge_base_test=$(git merge-base "change/$change_name" "origin/$main_branch" 2>/dev/null || true)
        local conflict_confirmed=false
        if [[ -n "$merge_base_test" ]]; then
            git merge-tree "$merge_base_test" "origin/$main_branch" "change/$change_name" 2>/dev/null | grep -q "^<<<<<<<" && conflict_confirmed=true || true
        fi

        if [[ "$conflict_confirmed" != "true" ]]; then
            log_info "No real conflict markers for $change_name — retrying merge"
            if wt-merge "$change_name" --no-push --llm-resolve >>"$LOG_FILE" 2>&1; then
                update_change_field "$change_name" "status" '"merged"'
                update_coverage_status "$change_name" "merged" 2>/dev/null || true
                return 0
            fi
            log_warn "wt-merge failed for $change_name but no conflict markers — marking merge-blocked"
            update_change_field "$change_name" "status" '"merge-blocked"'
            return 1
        fi

        # Check if this is the first conflict — try agent-assisted rebase
        local agent_rebase_done
        agent_rebase_done=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .agent_rebase_done // false' "$STATE_FILENAME")
        if [[ "$agent_rebase_done" != "true" && -n "$wt_path" && -d "$wt_path" ]]; then
            update_change_field "$change_name" "agent_rebase_done" "true"
            log_info "First merge conflict for $change_name — triggering agent-assisted rebase"
            # main_branch already set by pre-validation block above
            local retry_prompt="Merge conflict: your branch conflicts with $main_branch. Resolve the conflict by merging $main_branch into your branch.\n\nRun: git fetch origin $main_branch && git merge origin/$main_branch\n\nResolve any conflicts, keeping both sides' changes where possible. Prefer your changes (the feature) when they contradict $main_branch. After resolving, commit the merge."
            # Recall memories about recent merges for context
            local _mem_ctx
            _mem_ctx=$(orch_recall "$change_name merge conflict recent merges" 3 "phase:merge")
            if [[ -n "$_mem_ctx" ]]; then
                retry_prompt="$retry_prompt\n\n## Context from Memory\n${_mem_ctx:0:1000}"
            fi
            update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
            update_change_field "$change_name" "merge_rebase_pending" "true"
            resume_change "$change_name"
            # Return 0: agent rebase started, caller should not add to merge queue
            return 0
        else
            update_change_field "$change_name" "status" '"merge-blocked"'
            # No notification here — retry_merge_queue sends one only on final failure
            return 1
        fi
    fi
}

# ─── Post-Merge Sync ─────────────────────────────────────────────────

# Sync all running worktrees with main after a merge to prevent stale-main gate failures.
# Non-blocking: sync failures are logged but do not affect the merge result.
_sync_running_worktrees() {
    local merged_change="$1"

    local running_changes
    running_changes=$(jq -r '.changes[] | select(.status == "running") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    [[ -z "$running_changes" ]] && return 0

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME" 2>/dev/null)
        [[ -z "$wt_path" || ! -d "$wt_path" ]] && continue

        if sync_worktree_with_main "$wt_path" "$name" 2>/dev/null; then
            log_info "Post-merge sync: $name synced with main (after $merged_change merge)"
        else
            log_warn "Post-merge sync: $name sync failed (non-blocking)"
        fi
    done <<< "$running_changes"
}

# ─── Worktree Cleanup ────────────────────────────────────────────────

# Archive worktree agent logs before cleanup
_archive_worktree_logs() {
    local change_name="$1"
    local wt_path="$2"
    local logs_src="$wt_path/.claude/logs"
    [[ -d "$logs_src" ]] || return 0

    local archive_dir="wt/orchestration/logs/$change_name"
    mkdir -p "$archive_dir"
    cp -n "$logs_src"/*.log "$archive_dir/" 2>/dev/null || true
    local count
    count=$(find "$archive_dir" -name "*.log" 2>/dev/null | wc -l)
    log_info "Archived $count log files for $change_name to $archive_dir"
}

# Clean up worktree and branch after successful merge
cleanup_worktree() {
    local change_name="$1"
    local wt_path="$2"

    # Archive agent logs before removing the worktree
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        _archive_worktree_logs "$change_name" "$wt_path"
    fi

    # Try wt-close first (handles both worktree removal and branch deletion)
    if wt-close "$change_name" 2>/dev/null; then
        log_info "Cleaned up worktree for $change_name"
        return 0
    fi

    # Fallback: manual cleanup if wt-close fails
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        git worktree remove "$wt_path" --force 2>/dev/null || true
        log_info "Force-removed worktree $wt_path"
    fi

    local branch="change/$change_name"
    if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null; then
        git branch -D "$branch" 2>/dev/null || true
        log_info "Deleted branch $branch"
    fi
}

cleanup_all_worktrees() {
    log_info "Cleaning up worktrees for merged/done changes..."
    local cleaned=0
    while IFS= read -r line; do
        [[ -z "$line" ]] && continue
        local name wt_path status
        name=$(echo "$line" | jq -r '.name')
        wt_path=$(echo "$line" | jq -r '.worktree_path // empty')
        status=$(echo "$line" | jq -r '.status')
        [[ "$status" != "merged" && "$status" != "done" ]] && continue
        [[ -z "$wt_path" ]] && continue
        [[ ! -d "$wt_path" ]] && continue
        cleanup_worktree "$name" "$wt_path"
        cleaned=$((cleaned + 1))
    done < <(jq -c '.changes[]' "$STATE_FILENAME" 2>/dev/null)
    if [[ $cleaned -gt 0 ]]; then
        log_info "Cleaned up $cleaned worktree(s)"
        info "Cleaned up $cleaned worktree(s)"
    fi
}

# ─── Merge Queue ─────────────────────────────────────────────────────

execute_merge_queue() {
    local queue
    queue=$(jq -r '.merge_queue[]?' "$STATE_FILENAME" 2>/dev/null)

    [[ -z "$queue" ]] && return 0

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        merge_change "$name" || true
    done <<< "$queue"
}

# Retry merge queue items + any merge-blocked changes not in the queue.
# Safe to call from any context (monitor loop, resume, etc.)
# Max 5 retries per change to prevent infinite loops.
MAX_MERGE_RETRIES=5

_try_merge() {
    local name="$1"
    local retry_count
    retry_count=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .merge_retry_count // 0' "$STATE_FILENAME")
    if [[ "$retry_count" -ge "$MAX_MERGE_RETRIES" ]]; then
        return 0  # silently skip — already logged at the limit
    fi
    retry_count=$((retry_count + 1))
    update_change_field "$name" "merge_retry_count" "$retry_count"

    log_info "Merge attempt $retry_count/$MAX_MERGE_RETRIES for $name"

    # Update the change branch to include latest main before retrying merge.
    # This handles the case where main moved (other merges landed) since the branch was created.
    local wt_path
    wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        local main_branch
        main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
        log_info "Updating $name branch with latest $main_branch before merge retry"
        (cd "$wt_path" && git fetch origin "$main_branch" 2>/dev/null && git merge "origin/$main_branch" --no-edit 2>/dev/null) || true
    fi

    if merge_change "$name" 2>/dev/null; then
        return 0
    fi

    # Conflict fingerprint dedup: capture conflicted files and compare with previous attempt
    local conflict_fingerprint=""
    local source_branch="change/$name"
    local main_ref
    main_ref=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
    local merge_base_ref
    merge_base_ref=$(git merge-base "$source_branch" "origin/$main_ref" 2>/dev/null || true)
    if [[ -n "$merge_base_ref" ]]; then
        conflict_fingerprint=$(git merge-tree "$merge_base_ref" "origin/$main_ref" "$source_branch" 2>/dev/null | grep "^+++ b/" | sort | md5sum | cut -d' ' -f1)
    fi
    local prev_fingerprint
    prev_fingerprint=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .last_conflict_fingerprint // empty' "$STATE_FILENAME")
    if [[ -n "$conflict_fingerprint" ]]; then
        update_change_field "$name" "last_conflict_fingerprint" "\"$conflict_fingerprint\""
        if [[ "$conflict_fingerprint" == "$prev_fingerprint" ]]; then
            log_info "Same conflict fingerprint as previous attempt for $name — stopping retries"
            update_change_field "$name" "status" '"merge-blocked"'
            send_notification "wt-orchestrate" "Merge permanently blocked: $name (same conflict repeating)" "critical"
            return 0
        fi
    fi

    if [[ "$retry_count" -ge "$MAX_MERGE_RETRIES" ]]; then
        log_error "Merge failed after $MAX_MERGE_RETRIES attempts for $name — giving up"
        send_notification "wt-orchestrate" "Merge permanently blocked: $name (after $MAX_MERGE_RETRIES attempts)" "critical"
        orch_remember "Merge permanently failed for $name after $MAX_MERGE_RETRIES attempts — this change has unresolvable conflicts" Decision "phase:merge,change:$name"
    fi
}

retry_merge_queue() {
    # Process merge queue items
    local queue_items
    queue_items=$(jq -r '.merge_queue[]?' "$STATE_FILENAME" 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        _try_merge "$name"
    done <<< "$queue_items"

    # Also find merge-blocked items not in the queue (safety net)
    # Note: merge_rebase_pending changes have status "running", not "merge-blocked", so they're naturally skipped
    local blocked
    blocked=$(jq -r '.changes[] | select(.status == "merge-blocked") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        # Check if already in merge_queue (don't double-process)
        if echo "$queue_items" | grep -qx "$name" 2>/dev/null; then
            continue
        fi
        _try_merge "$name"
    done <<< "$blocked"
}
