#!/usr/bin/env bash
# lib/orchestration/verifier.sh — Change verification, testing, review, smoke tests
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: state.sh (update_change_field, etc.), events.sh (emit_event),
#             dispatcher.sh (resume_change, check_base_build, fix_base_build_with_llm, sync_worktree_with_main)

# ─── Test Runner ─────────────────────────────────────────────────────

# Run tests in a worktree with timeout. Captures exit code + truncated output.
# Returns 0 on pass, 1 on fail. Sets TEST_OUTPUT variable.
run_tests_in_worktree() {
    local wt_path="$1"
    local test_command="$2"
    local test_timeout="${3:-$DEFAULT_TEST_TIMEOUT}"

    TEST_OUTPUT=""
    local raw_output rc=0
    raw_output=$(cd "$wt_path" && timeout "$test_timeout" bash -c "$test_command" 2>&1) || rc=$?

    # Truncate output to 2000 chars
    if [[ ${#raw_output} -gt 2000 ]]; then
        TEST_OUTPUT="...truncated...
${raw_output: -2000}"
    else
        TEST_OUTPUT="$raw_output"
    fi

    return $rc
}

# ─── Code Review ─────────────────────────────────────────────────────

# LLM code review of a change branch. Returns 0 if no CRITICAL issues, 1 if CRITICAL found.
# Sets REVIEW_OUTPUT variable.
review_change() {
    local change_name="$1"
    local wt_path="$2"
    local scope="$3"
    local rev_model="${4:-$DEFAULT_REVIEW_MODEL}"

    REVIEW_OUTPUT=""

    # Generate diff of change branch vs main
    local source_branch="change/$change_name"
    local diff_output
    diff_output=$(cd "$wt_path" && git diff "$(git merge-base HEAD origin/HEAD 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo HEAD~5)..HEAD" 2>/dev/null) || {
        log_warn "Could not generate diff for $change_name review"
        return 0  # skip review on diff failure
    }

    # Truncate large diffs
    if [[ ${#diff_output} -gt 30000 ]]; then
        diff_output="${diff_output:0:30000}
...diff truncated at 30000 chars..."
    fi

    local review_prompt
    review_prompt=$(cat <<REVIEW_EOF
You are a senior code reviewer. Review this diff for critical issues.

## Change Scope
$scope

## Diff
\`\`\`diff
$diff_output
\`\`\`

## Review Criteria
Check for:
1. Security vulnerabilities: SQL injection, XSS, command injection, path traversal
2. Authentication/authorization gaps: missing auth checks, broken access control
3. Tenant isolation: can one user/org access another's data?
4. Data integrity: missing validation, race conditions, data loss risks
5. Error handling: unhandled exceptions that crash the app

For each issue found, classify severity as: CRITICAL, HIGH, MEDIUM, LOW.

Output format:
- If no issues: "REVIEW PASS — no critical issues found"
- If issues found:
  ISSUE: [severity] description
  FILE: path/to/file
  LINE: approximate line number

Only flag real problems — not style preferences.
REVIEW_EOF
)

    REVIEW_OUTPUT=$(echo "$review_prompt" | run_claude --model "$(model_id "$rev_model")") || {
        if [[ "$rev_model" != "opus" ]]; then
            log_warn "Code review failed with $rev_model for $change_name, escalating to opus"
            REVIEW_OUTPUT=$(echo "$review_prompt" | run_claude --model "$(model_id opus)") || {
                log_warn "Code review failed with opus for $change_name — skipping"
                return 0
            }
        else
            log_warn "Code review failed for $change_name — skipping"
            return 0
        fi
    }

    log_info "Code review complete for $change_name (${#REVIEW_OUTPUT} chars)"

    # Check for CRITICAL severity
    if echo "$REVIEW_OUTPUT" | grep -qi '\[CRITICAL\]\|severity.*critical\|CRITICAL:'; then
        return 1
    fi
    return 0
}

# ─── Merge Scope Verification ───────────────────────────────────────

# Verify that a merge actually brought implementation files, not just openspec artifacts.
# Returns 0 on pass or skip, 1 on failure (only artifacts merged).
# Non-blocking: caller logs/notifies but does NOT revert.
verify_merge_scope() {
    local change_name="$1"

    # Get files changed in the merge commit
    local diff_files=""
    diff_files=$(git diff --name-only HEAD~1 2>/dev/null || true)
    if [[ -z "$diff_files" ]]; then
        log_warn "Post-merge scope: no diff files found for $change_name (skip)"
        return 0
    fi

    # Check if ANY file is outside openspec/changes/ and .claude/
    local has_impl=false
    while IFS= read -r f; do
        [[ -z "$f" ]] && continue
        # Skip openspec artifacts and .claude config files
        if [[ "$f" == openspec/changes/* ]] || [[ "$f" == .claude/* ]]; then
            continue
        fi
        has_impl=true
        break
    done <<< "$diff_files"

    if $has_impl; then
        log_info "Post-merge: scope verification passed for $change_name"
        return 0
    else
        log_error "Post-merge: scope verification FAILED — only artifact files merged for $change_name, no implementation"
        return 1
    fi
}

# ─── Health Check ────────────────────────────────────────────────────

# Extract health check URL from smoke command
# Looks for localhost:PORT pattern
extract_health_check_url() {
    local smoke_cmd="$1"
    local port
    port=$(echo "$smoke_cmd" | grep -oP 'localhost:\K[0-9]+' | head -1)
    if [[ -n "$port" ]]; then
        echo "http://localhost:$port"
    fi
}

# Health check: verify dev server is responding
# Returns 0 on success, 1 on timeout
health_check() {
    local url="$1"
    local timeout_secs="${2:-30}"

    if [[ -z "$url" ]]; then
        return 0  # No URL to check — skip
    fi

    log_info "Health check: waiting for $url (timeout: ${timeout_secs}s)"
    local elapsed=0
    while [[ $elapsed -lt $timeout_secs ]]; do
        local http_code
        http_code=$(curl -s -o /dev/null -w '%{http_code}' "$url" 2>/dev/null || echo "000")
        if [[ "$http_code" =~ ^[23] ]]; then
            log_info "Health check: server responding ($http_code)"
            return 0
        fi
        sleep 1
        elapsed=$((elapsed + 1))
    done
    log_error "Health check: server not responding after ${timeout_secs}s"
    return 1
}

# ─── Scoped Smoke Fix ────────────────────────────────────────────────

# Scoped smoke fix agent: uses change context for higher fix rate
# Returns 0 if smoke eventually passes, 1 if all retries exhausted
smoke_fix_scoped() {
    local change_name="$1"
    local smoke_cmd="$2"
    local smoke_tout="$3"
    local max_retries="${4:-3}"
    local max_turns="${5:-15}"
    local smoke_output="$6"

    # Get modified files from the merge commit
    local modified_files
    modified_files=$(git diff HEAD~1 --name-only 2>/dev/null || echo "")

    # Get change scope from state
    local change_scope
    change_scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME" 2>/dev/null || echo "")

    local attempt=0
    while [[ $attempt -lt $max_retries ]]; do
        attempt=$((attempt + 1))
        update_change_field "$change_name" "smoke_fix_attempts" "$attempt"
        update_change_field "$change_name" "smoke_status" '"fixing"'
        log_info "Smoke fix attempt $attempt/$max_retries for $change_name"

        local fix_prompt
        fix_prompt=$(cat <<SCOPED_FIX_EOF
Post-merge smoke/e2e tests failed on main after merging "$change_name".

## Change scope
$change_scope

## Files modified by this change
$modified_files

## Smoke command
$smoke_cmd

## Smoke output
$smoke_output

## Constraints
- MAY ONLY modify files that were part of this change (listed above)
- MUST NOT delete or weaken existing test assertions
- MUST NOT modify files outside the change scope
- Fix the root cause — either implementation code or test expectations

## Steps
1. Analyze the smoke test failures
2. Fix the root cause in the modified files
3. Commit with message: "fix: repair smoke after $change_name merge"
SCOPED_FIX_EOF
)
        local fix_rc=0
        echo "$fix_prompt" | run_claude --model "$(model_id sonnet)" --max-turns "$max_turns" >>"$LOG_FILE" 2>&1 || fix_rc=$?

        if [[ $fix_rc -ne 0 ]]; then
            log_error "Smoke fix agent failed (exit $fix_rc) for $change_name attempt $attempt"
            continue
        fi

        # Verify fix didn't break unit tests or build
        local test_cmd
        test_cmd=$(echo "$directives" | jq -r '.test_command // ""' 2>/dev/null || echo "")
        if [[ -n "$test_cmd" ]]; then
            local test_rc=0
            timeout 300 bash -c "$test_cmd" >>"$LOG_FILE" 2>&1 || test_rc=$?
            if [[ $test_rc -ne 0 ]]; then
                log_error "Smoke fix broke unit tests — reverting (attempt $attempt)"
                git revert HEAD --no-edit >>"$LOG_FILE" 2>&1 || true
                continue
            fi
        fi

        # Re-run smoke to verify the fix
        local recheck_rc=0
        local recheck_output
        recheck_output=$(timeout "$smoke_tout" bash -c "$smoke_cmd" 2>&1) || recheck_rc=$?
        if [[ $recheck_rc -eq 0 ]]; then
            log_info "Smoke fix SUCCEEDED for $change_name (attempt $attempt)"
            return 0
        else
            log_error "Smoke still failing after fix attempt $attempt"
            smoke_output="$recheck_output"  # Update for next attempt
        fi
    done

    log_error "Smoke fix exhausted all $max_retries retries for $change_name"
    return 1
}

# ─── Poll Change ─────────────────────────────────────────────────────

poll_change() {
    local change_name="$1"
    local test_command="$2"
    local merge_policy="$3"
    local test_timeout="${4:-$DEFAULT_TEST_TIMEOUT}"
    local max_verify_retries="${5:-$DEFAULT_MAX_VERIFY_RETRIES}"
    local review_before_merge="${6:-false}"
    local review_model="${7:-$DEFAULT_REVIEW_MODEL}"
    local smoke_command="${8:-}"
    local smoke_timeout="${9:-$DEFAULT_SMOKE_TIMEOUT}"
    local smoke_blocking="${10:-false}"
    local smoke_fix_max_retries="${11:-$DEFAULT_SMOKE_FIX_MAX_RETRIES}"
    local smoke_fix_max_turns="${12:-$DEFAULT_SMOKE_FIX_MAX_TURNS}"
    local smoke_health_check_url="${13:-}"
    local smoke_health_check_timeout="${14:-$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT}"

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")

    [[ -z "$wt_path" ]] && return

    local loop_state="$wt_path/.claude/loop-state.json"
    if [[ ! -f "$loop_state" ]]; then
        # No loop-state yet — check if terminal process is alive via state file
        local ralph_pid
        ralph_pid=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .ralph_pid // empty' "$STATE_FILENAME")
        if [[ -n "$ralph_pid" && "$ralph_pid" != "0" ]] && ! kill -0 "$ralph_pid" 2>/dev/null; then
            log_error "Terminal process $ralph_pid for $change_name is dead, no loop-state found"
            update_change_field "$change_name" "status" '"failed"'
            orch_remember "Change $change_name failed — terminal process died without producing loop-state" Learning "phase:monitor,change:$change_name"
        fi
        return
    fi

    local ralph_status
    ralph_status=$(jq -r '.status // "unknown"' "$loop_state" 2>/dev/null)
    local tokens
    tokens=$(jq -r '.total_tokens // 0' "$loop_state" 2>/dev/null)
    # Add accumulated tokens from previous loop(s) so retries don't reset the counter
    local tokens_prev
    tokens_prev=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used_prev // 0' "$STATE_FILENAME")
    update_change_field "$change_name" "tokens_used" "$((tokens_prev + tokens))"

    case "$ralph_status" in
        done)
            handle_change_done "$change_name" "$wt_path" "$test_command" "$merge_policy" \
                "$test_timeout" "$max_verify_retries" "$review_before_merge" "$review_model" \
                "$smoke_command" "$smoke_timeout" "$smoke_blocking" \
                "$smoke_fix_max_retries" "$smoke_fix_max_turns" \
                "$smoke_health_check_url" "$smoke_health_check_timeout"
            ;;
        running)
            # Check if the loop process is actually alive
            local loop_mtime
            loop_mtime=$(stat -c %Y "$loop_state" 2>/dev/null || echo 0)
            local now_epoch
            now_epoch=$(date +%s)
            local stale_secs=$(( now_epoch - loop_mtime ))

            # If loop-state is fresh, the agent is alive — reset stall counter
            if [[ "$stale_secs" -le 300 ]]; then
                local cur_stall
                cur_stall=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .stall_count // 0' "$STATE_FILENAME")
                if [[ "$cur_stall" -gt 0 ]]; then
                    update_change_field "$change_name" "stall_count" "0"
                    log_info "Change $change_name recovered — stall_count reset to 0"
                fi
            fi

            # If loop-state hasn't been updated in 5+ minutes, check if process is actually dead
            if [[ "$stale_secs" -gt 300 ]]; then
                # Check terminal PID — if still alive, the agent is in a long iteration (not stale)
                local terminal_pid
                terminal_pid=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .ralph_pid // 0' "$STATE_FILENAME")
                if [[ "$terminal_pid" -gt 0 ]] && kill -0 "$terminal_pid" 2>/dev/null; then
                    # PID alive = long iteration, not stale. Don't log every poll cycle (noise).
                    return
                fi

                log_warn "Change $change_name loop-state is stale (${stale_secs}s old, PID $terminal_pid dead) — treating as stopped"
                # Fall through to stall handling
                local stall_count
                stall_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .stall_count // 0' "$STATE_FILENAME")
                stall_count=$((stall_count + 1))
                update_change_field "$change_name" "stall_count" "$stall_count"

                if [[ "$stall_count" -le 3 ]]; then
                    log_info "Resuming stale $change_name (attempt $stall_count/3)"
                    info "$change_name stale (attempt $stall_count/3), resuming..."
                    update_change_field "$change_name" "status" '"stalled"'
                    resume_change "$change_name"
                else
                    log_error "Change $change_name stale after 3 resume attempts — giving up"
                    update_change_field "$change_name" "status" '"failed"'
                    send_notification "wt-orchestrate" "Change '$change_name' failed — process died 3 times" "critical"
                fi
            fi
            ;;
        "waiting:human")
            # Human action required — do NOT auto-resume or increment stall count
            local cur_status
            cur_status=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .status // ""' "$STATE_FILENAME")

            # Check if wt-manual has resolved manual tasks and set status to "dispatched"
            if [[ "$cur_status" == "dispatched" ]]; then
                log_info "Change $change_name manual tasks resolved — resuming"
                info "$change_name — manual tasks resolved, resuming..."
                resume_change "$change_name"
                return
            fi

            if [[ "$cur_status" != "waiting:human" ]]; then
                update_change_field "$change_name" "status" '"waiting:human"'
                # Log manual task summary
                local manual_summary
                manual_summary=$(jq -r '.manual_tasks[]? | "[\(.id)] \(.description) (\(.type))"' "$loop_state" 2>/dev/null | head -5)
                log_info "Change $change_name waiting for human input:"
                while IFS= read -r line; do
                    [[ -n "$line" ]] && log_info "  $line"
                done <<< "$manual_summary"
                info "$change_name — waiting for human input. Run: wt-manual show $change_name"
                send_notification "wt-orchestrate" "Change '$change_name' needs human action. Run: wt-manual show $change_name" "warning"
            fi
            ;;
        budget_exceeded|waiting:budget)
            # Both old budget_exceeded and new waiting:budget — do NOT auto-restart, treat like waiting:human
            local cur_budget_status
            cur_budget_status=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .status // ""' "$STATE_FILENAME")
            if [[ "$cur_budget_status" != "waiting:budget" && "$cur_budget_status" != "budget_exceeded" ]]; then
                update_change_field "$change_name" "status" '"waiting:budget"'
                local budget_tokens
                budget_tokens=$(jq -r '.total_tokens // 0' "$loop_state" 2>/dev/null)
                local budget_limit
                budget_limit=$(jq -r '.token_budget // 0' "$loop_state" 2>/dev/null)
                log_warn "Change $change_name budget checkpoint: $((budget_tokens / 1000))K / $((budget_limit / 1000))K — waiting for human"
                info "$change_name — budget checkpoint ($((budget_tokens / 1000))K / $((budget_limit / 1000))K). Run: wt-loop resume"
                send_notification "wt-orchestrate" "Change '$change_name' budget checkpoint — run 'wt-loop resume' to continue" "warning"
            fi
            ;;
        stopped|stalled|stuck)
            local stall_count
            stall_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .stall_count // 0' "$STATE_FILENAME")
            stall_count=$((stall_count + 1))
            update_change_field "$change_name" "stall_count" "$stall_count"

            if [[ "$stall_count" -le 3 ]]; then
                log_warn "Change $change_name $ralph_status (attempt $stall_count/3) — will auto-resume"
                info "$change_name $ralph_status (attempt $stall_count/3), resuming..."
                update_change_field "$change_name" "status" '"stalled"'
                update_change_field "$change_name" "stalled_at" "$(date +%s)"
            else
                log_error "Change $change_name $ralph_status after 3 resume attempts — giving up"
                update_change_field "$change_name" "status" '"failed"'
                send_notification "wt-orchestrate" "Change '$change_name' failed after 3 resume attempts" "critical"
                orch_remember "Change $change_name $ralph_status after 3 resume attempts — agent could not complete this task" Learning "phase:monitor,change:$change_name"
                trigger_checkpoint "failure"
            fi
            ;;
    esac
}

# ─── Handle Change Done ─────────────────────────────────────────────

handle_change_done() {
    local change_name="$1"
    local wt_path="$2"
    local test_command="$3"
    local merge_policy="$4"
    local test_timeout="${5:-$DEFAULT_TEST_TIMEOUT}"
    local max_verify_retries="${6:-$DEFAULT_MAX_VERIFY_RETRIES}"
    local review_before_merge="${7:-false}"
    local review_model="${8:-$DEFAULT_REVIEW_MODEL}"
    local smoke_command="${9:-}"
    local smoke_timeout="${10:-$DEFAULT_SMOKE_TIMEOUT}"
    local smoke_blocking="${11:-false}"
    local smoke_fix_max_retries="${12:-$DEFAULT_SMOKE_FIX_MAX_RETRIES}"
    local smoke_fix_max_turns="${13:-$DEFAULT_SMOKE_FIX_MAX_TURNS}"
    local smoke_health_check_url="${14:-}"
    local smoke_health_check_timeout="${15:-$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT}"

    log_info "Change $change_name completed, running checks... (review_before_merge=$review_before_merge, test_command=$test_command, test_timeout=$test_timeout)"

    # Get current verify retry count
    local verify_retry_count
    verify_retry_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .verify_retry_count // 0' "$STATE_FILENAME")

    # ── Retry token tracking: compute diff if returning from a retry ──
    local retry_tokens_start
    retry_tokens_start=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .retry_tokens_start // 0' "$STATE_FILENAME")
    if [[ "$retry_tokens_start" -gt 0 ]]; then
        local current_tokens
        current_tokens=$(jq -r '.total_tokens // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null || echo "0")
        local retry_diff=$((current_tokens - retry_tokens_start))
        [[ "$retry_diff" -lt 0 ]] && retry_diff=0
        local prev_retry_tokens
        prev_retry_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .gate_retry_tokens // 0' "$STATE_FILENAME")
        local prev_retry_count
        prev_retry_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .gate_retry_count // 0' "$STATE_FILENAME")
        update_change_field "$change_name" "gate_retry_tokens" "$((prev_retry_tokens + retry_diff))"
        update_change_field "$change_name" "gate_retry_count" "$((prev_retry_count + 1))"
        update_change_field "$change_name" "retry_tokens_start" "0"
        log_info "Verify gate: retry cost for $change_name: +${retry_diff} tokens (total retries: $((prev_retry_count + 1)))"
    fi

    # ── Merge-rebase fast path: skip verify gate, go straight to merge ──
    local merge_rebase_pending
    merge_rebase_pending=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .merge_rebase_pending // false' "$STATE_FILENAME")
    if [[ "$merge_rebase_pending" == "true" ]]; then
        update_change_field "$change_name" "merge_rebase_pending" "false"
        log_info "Change $change_name returning from agent-assisted rebase — testing merge cleanness"
        info "Agent rebase complete for $change_name, testing merge..."

        # Dry-run: test if branch merges cleanly before calling full wt-merge
        local source_branch="change/$change_name"
        local main_branch
        main_branch=$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")
        git fetch origin "$main_branch" 2>/dev/null || true
        local merge_base
        merge_base=$(git merge-base "$source_branch" "origin/$main_branch" 2>/dev/null || true)
        local test_merge_rc=0
        if [[ -n "$merge_base" ]]; then
            git merge-tree "$merge_base" "origin/$main_branch" "$source_branch" 2>/dev/null | grep -q "^<<<<<<<" && test_merge_rc=1 || true
        fi

        if [[ $test_merge_rc -eq 0 ]]; then
            # Branch merges cleanly — proceed with full merge
            if merge_change "$change_name" 2>/dev/null; then
                log_info "Merge succeeded after agent rebase for $change_name"
                return 0
            fi
        fi

        # Agent rebase didn't fully resolve — enter retry queue
        log_warn "Merge still has conflicts after agent rebase for $change_name — entering retry queue"
        local merge_retry_count
        merge_retry_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .merge_retry_count // 0' "$STATE_FILENAME")
        update_change_field "$change_name" "merge_retry_count" "$((merge_retry_count + 1))"
        update_change_field "$change_name" "status" '"merge-blocked"'
        return 0
    fi

    # Gate timing accumulators
    local gate_test_ms=0
    local gate_review_ms=0
    local gate_verify_ms=0

    # ── Read per-change gate skip flags ──
    local skip_test skip_review
    skip_test=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .skip_test // false' "$STATE_FILENAME")
    skip_review=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .skip_review // false' "$STATE_FILENAME")

    # ── Step 1: Run tests if configured (VG-1) ──
    local test_result="skip"
    local test_output=""
    if [[ "$skip_test" == "true" ]]; then
        test_result="skipped"
        log_info "Verify gate: tests skipped for $change_name (skip_test=true)"
    elif [[ -n "$test_command" ]]; then
        update_change_field "$change_name" "status" '"verifying"'
        info "Running tests for $change_name..."
        log_info "Verify gate: test start for $change_name"

        local _t_start=$(($(date +%s%N) / 1000000))
        if run_tests_in_worktree "$wt_path" "$test_command" "$test_timeout"; then
            test_result="pass"
            test_output="$TEST_OUTPUT"
            log_info "Verify gate: tests passed for $change_name"
            orch_remember "Tests passed for $change_name" Context "phase:test,change:$change_name"
        else
            test_result="fail"
            test_output="$TEST_OUTPUT"
            log_error "Verify gate: tests failed for $change_name"
            orch_remember "Tests failed for $change_name: ${test_output:0:500}" Learning "phase:test,change:$change_name"
        fi
        gate_test_ms=$(( $(date +%s%N) / 1000000 - _t_start ))
        update_change_field "$change_name" "gate_test_ms" "$gate_test_ms"
        log_info "Verify gate: test took ${gate_test_ms}ms for $change_name"
    fi

    # Store test results in state (VG-5)
    update_change_field "$change_name" "test_result" "\"$test_result\""
    # Store truncated test output (escape for JSON)
    local escaped_output
    escaped_output=$(printf '%s' "$test_output" | head -c 2000 | jq -Rs .)
    update_change_field "$change_name" "test_output" "$escaped_output"

    if [[ "$test_result" == "fail" ]]; then
        # Retry with test failure context (VG-2)
        if [[ "$verify_retry_count" -lt "$max_verify_retries" ]]; then
            verify_retry_count=$((verify_retry_count + 1))
            info "Tests failed for $change_name — retrying ($verify_retry_count/$max_verify_retries)..."
            log_info "Verify gate: test fail retry $verify_retry_count/$max_verify_retries for $change_name"
            update_change_field "$change_name" "verify_retry_count" "$verify_retry_count"
            update_change_field "$change_name" "status" '"verify-failed"'

            # Resume Ralph with test failure context
            local scope
            scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")
            local retry_prompt="Tests failed after implementation. Fix the failing tests.\n\nTest command: $test_command\nTest output:\n$test_output\n\nOriginal scope: $scope"
            # Recall relevant memories for retry context
            local _mem_ctx
            _mem_ctx=$(orch_recall "$scope" 3 "")
            if [[ -n "$_mem_ctx" ]]; then
                retry_prompt="$retry_prompt\n\n## Context from Memory\n${_mem_ctx:0:1000}"
            fi
            update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
            # Snapshot tokens before retry for cost tracking
            local _snap_tokens
            _snap_tokens=$(jq -r '.total_tokens // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null || echo "0")
            update_change_field "$change_name" "retry_tokens_start" "$_snap_tokens"
            update_change_field "$change_name" "gate_test_ms" "$gate_test_ms"
            resume_change "$change_name"
            return
        fi
        update_change_field "$change_name" "status" '"failed"'
        send_notification "wt-orchestrate" "Change '$change_name' failed tests after $max_verify_retries retries" "critical"
        log_error "Verify gate: $change_name failed tests permanently"
        trigger_checkpoint "failure"
        return
    fi

    # ── Step 2: Build verification — cheap, no LLM cost (VG-BUILD) ──
    # Run build BEFORE expensive LLM review/verify to catch failures early and save tokens
    local gate_build_ms=0
    local build_command=""
    if [[ -f "$wt_path/package.json" ]]; then
        build_command=$(cd "$wt_path" && node -e "
            const p = require('./package.json');
            const s = p.scripts || {};
            if (s['build:ci']) console.log('build:ci');
            else if (s['build']) console.log('build');
        " 2>/dev/null || true)
    fi

    if [[ -n "$build_command" ]]; then
        # Detect package manager
        local pm="npm"
        [[ -f "$wt_path/pnpm-lock.yaml" ]] && pm="pnpm"
        [[ -f "$wt_path/yarn.lock" ]] && pm="yarn"
        [[ -f "$wt_path/bun.lockb" || -f "$wt_path/bun.lock" ]] && pm="bun"

        info "Running build for $change_name ($pm run $build_command)..."
        log_info "Verify gate: build start for $change_name"
        local _b_start=$(($(date +%s%N) / 1000000))

        local build_output=""
        local build_rc=0
        build_output=$(cd "$wt_path" && timeout 300 "$pm" run "$build_command" 2>&1) || build_rc=$?
        gate_build_ms=$(( $(date +%s%N) / 1000000 - _b_start ))
        update_change_field "$change_name" "gate_build_ms" "$gate_build_ms"

        if [[ $build_rc -ne 0 ]]; then
            log_error "Verify gate: build failed for $change_name (exit $build_rc)"
            update_change_field "$change_name" "build_result" '"fail"'
            local escaped_build
            escaped_build=$(printf '%s' "$build_output" | tail -c 2000 | jq -Rs .)
            update_change_field "$change_name" "build_output" "$escaped_build"

            # ── Check if main branch is also broken (don't blame the agent) ──
            local project_path
            project_path=$(git -C "$wt_path" rev-parse --show-toplevel 2>/dev/null || pwd)
            # The main worktree is the project path without worktree suffix
            local main_path="${project_path%%-wt-*}"
            [[ ! -d "$main_path" ]] && main_path="$project_path"

            if ! check_base_build "$main_path"; then
                log_warn "Verify gate: main branch also fails build — attempting LLM fix on main"
                info "Main branch is broken — fixing main before retrying $change_name..."
                if fix_base_build_with_llm "$main_path"; then
                    # Main fixed — sync worktree and re-run build without consuming a retry
                    sync_worktree_with_main "$wt_path" "$change_name" || true
                    log_info "Verify gate: re-running build for $change_name after main fix"
                    local rerun_rc=0
                    build_output=$(cd "$wt_path" && timeout 300 "$pm" run "$build_command" 2>&1) || rerun_rc=$?
                    if [[ $rerun_rc -eq 0 ]]; then
                        log_info "Verify gate: build passed for $change_name after main fix"
                        update_change_field "$change_name" "build_result" '"pass"'
                        # fall through to review/verify
                    else
                        log_error "Verify gate: build still failed for $change_name after main fix"
                        # Fall through to normal retry logic below
                        build_rc=$rerun_rc
                    fi
                else
                    log_error "Verify gate: could not fix main — marking $change_name as build-blocked"
                    update_change_field "$change_name" "status" '"build-blocked"'
                    send_notification "wt-orchestrate" "Change '$change_name' blocked: main branch build is broken" "critical"
                    return
                fi
                # If build now passes, skip the retry logic
                [[ "$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .build_result // ""' "$STATE_FILENAME")" == "pass" ]] && { log_info "Verify gate: build gate resolved via main fix for $change_name"; }
            else
                # ── Main builds OK but worktree doesn't — try syncing main fixes ──
                log_info "Verify gate: main builds OK, syncing $change_name with main before retry"
                if sync_worktree_with_main "$wt_path" "$change_name"; then
                    # Worktree synced — rebuild to see if the inherited issue is gone
                    log_info "Verify gate: re-running build for $change_name after sync"
                    local sync_rerun_rc=0
                    build_output=$(cd "$wt_path" && timeout 300 "$pm" run "$build_command" 2>&1) || sync_rerun_rc=$?
                    if [[ $sync_rerun_rc -eq 0 ]]; then
                        log_info "Verify gate: build passed for $change_name after sync with main"
                        update_change_field "$change_name" "build_result" '"pass"'
                        build_rc=0  # Clear the failure
                    else
                        log_info "Verify gate: build still failed for $change_name after sync (agent code issue)"
                        build_rc=$sync_rerun_rc
                    fi
                fi
            fi

            # Only retry agent if build still failing and it's not a main-side issue
            if [[ "$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .build_result // ""' "$STATE_FILENAME")" != "pass" ]]; then
                if [[ "$verify_retry_count" -lt "$max_verify_retries" ]]; then
                    verify_retry_count=$((verify_retry_count + 1))
                    info "Build failed for $change_name — retrying ($verify_retry_count/$max_verify_retries)..."
                    update_change_field "$change_name" "verify_retry_count" "$verify_retry_count"
                    update_change_field "$change_name" "status" '"verify-failed"'
                    local scope
                    scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")
                    local retry_prompt="Build failed after implementation. Fix the build errors.\n\nBuild command: $pm run $build_command\nBuild output (last 2000 chars):\n${build_output: -2000}\n\nOriginal scope: $scope"
                    update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
                    local _snap_tokens
                    _snap_tokens=$(jq -r '.total_tokens // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null || echo "0")
                    update_change_field "$change_name" "retry_tokens_start" "$_snap_tokens"
                    resume_change "$change_name"
                    return
                fi
                update_change_field "$change_name" "status" '"failed"'
                send_notification "wt-orchestrate" "Change '$change_name' failed build after $max_verify_retries retries" "critical"
                return
            fi
        fi

        log_info "Verify gate: build passed for $change_name (${gate_build_ms}ms)"
        update_change_field "$change_name" "build_result" '"pass"'
    fi

    # ── Step 2b: Check for test file existence (warning only) ──
    local test_files_count=0
    test_files_count=$(cd "$wt_path" && git diff --name-only "$(git merge-base HEAD origin/HEAD 2>/dev/null || git merge-base HEAD main 2>/dev/null || echo HEAD~5)..HEAD" 2>/dev/null | grep -cE '\.(test|spec)\.' || true)
    if [[ "$test_files_count" -eq 0 ]]; then
        log_warn "Verify gate: $change_name has NO test files in the diff — consider adding tests"
        update_change_field "$change_name" "has_tests" "false"
        send_notification "wt-orchestrate" "Change '$change_name' has no test files" "warning"
    else
        log_info "Verify gate: $change_name has $test_files_count test file(s)"
        update_change_field "$change_name" "has_tests" "true"
    fi

    # ── Step 3: LLM Code Review (VG-4) ──
    if [[ "$skip_review" == "true" ]]; then
        update_change_field "$change_name" "review_result" '"skipped"'
        log_info "Verify gate: review skipped for $change_name (skip_review=true)"
    elif [[ "$review_before_merge" == "true" ]]; then
        info "Running code review for $change_name..."
        log_info "Verify gate: review start for $change_name"

        local scope
        scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")

        local _r_start=$(($(date +%s%N) / 1000000))
        if ! review_change "$change_name" "$wt_path" "$scope" "$review_model"; then
            gate_review_ms=$(( $(date +%s%N) / 1000000 - _r_start ))
            update_change_field "$change_name" "gate_review_ms" "$gate_review_ms"
            log_info "Verify gate: review took ${gate_review_ms}ms for $change_name (CRITICAL)"
            log_error "Verify gate: review found CRITICAL issues in $change_name"
            update_change_field "$change_name" "review_result" '"critical"'
            update_change_field "$change_name" "review_output" "$(printf '%s' "$REVIEW_OUTPUT" | head -c 2000 | jq -Rs .)"
            orch_remember "Code review found CRITICAL issues in $change_name: ${REVIEW_OUTPUT:0:500}" Learning "phase:review,change:$change_name"

            # Retry with review feedback
            if [[ "$verify_retry_count" -lt "$max_verify_retries" ]]; then
                verify_retry_count=$((verify_retry_count + 1))
                info "Review found critical issues in $change_name — retrying ($verify_retry_count/$max_verify_retries)..."
                log_info "Verify gate: review critical retry $verify_retry_count/$max_verify_retries for $change_name"
                update_change_field "$change_name" "verify_retry_count" "$verify_retry_count"
                update_change_field "$change_name" "status" '"verify-failed"'
                # Build retry context with review feedback
                local retry_prompt="Code review found CRITICAL issues. Fix these issues.\n\nReview feedback:\n${REVIEW_OUTPUT:0:500}\n\nOriginal scope: $scope"
                # Recall relevant memories for retry context
                local _mem_ctx
                _mem_ctx=$(orch_recall "$scope" 3 "")
                if [[ -n "$_mem_ctx" ]]; then
                    retry_prompt="$retry_prompt\n\n## Context from Memory\n${_mem_ctx:0:1000}"
                fi
                update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
                # Snapshot tokens before retry for cost tracking
                local _snap_tokens
                _snap_tokens=$(jq -r '.total_tokens // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null || echo "0")
                update_change_field "$change_name" "retry_tokens_start" "$_snap_tokens"
                resume_change "$change_name"
                return
            fi
            update_change_field "$change_name" "status" '"failed"'
            send_notification "wt-orchestrate" "Change '$change_name' has critical review issues after retries" "critical"
            return
        fi
        gate_review_ms=$(( $(date +%s%N) / 1000000 - _r_start ))
        update_change_field "$change_name" "gate_review_ms" "$gate_review_ms"
        log_info "Verify gate: review took ${gate_review_ms}ms for $change_name (pass)"
        update_change_field "$change_name" "review_result" '"pass"'
        log_info "Verify gate: review passed for $change_name"
        orch_remember "Code review passed for $change_name — no critical issues" Context "phase:review,change:$change_name"
    fi

    # ── Step 4: Run verify step (existing) ──
    info "Running verify for $change_name..."
    local _v_start=$(($(date +%s%N) / 1000000))
    local verify_ok=true
    local verify_output=""
    if command -v claude &>/dev/null; then
        verify_output=$( (cd "$wt_path" && echo "Run /opsx:verify $change_name" | run_claude --max-turns 5) 2>&1) || verify_ok=false
    fi
    gate_verify_ms=$(( $(date +%s%N) / 1000000 - _v_start ))
    update_change_field "$change_name" "gate_verify_ms" "$gate_verify_ms"
    log_info "Verify gate: verify took ${gate_verify_ms}ms for $change_name"

    if [[ "$verify_ok" != "true" ]]; then
        if [[ "$verify_retry_count" -lt "$max_verify_retries" ]]; then
            verify_retry_count=$((verify_retry_count + 1))
            info "Verify failed, retrying $change_name ($verify_retry_count/$max_verify_retries)..."
            update_change_field "$change_name" "verify_retry_count" "$verify_retry_count"
            update_change_field "$change_name" "status" '"verify-failed"'
            # Store verify output as retry context so agent knows what to fix
            local scope
            scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")
            local retry_prompt="Verify failed after implementation. Fix the issues found by verify.\n\nVerify output:\n${verify_output:0:2000}\n\nOriginal scope: $scope"
            update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
            resume_change "$change_name"
            return
        fi
        update_change_field "$change_name" "status" '"failed"'
        send_notification "wt-orchestrate" "Change '$change_name' failed verify after retries" "critical"
        return
    fi

    # ── Store gate total ──
    local gate_total_ms=$((gate_test_ms + gate_review_ms + gate_verify_ms + gate_build_ms))
    update_change_field "$change_name" "gate_total_ms" "$gate_total_ms"
    local gate_retry_tokens
    gate_retry_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .gate_retry_tokens // 0' "$STATE_FILENAME")
    local gate_retry_count
    gate_retry_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .gate_retry_count // 0' "$STATE_FILENAME")
    log_info "Verify gate: $change_name total ${gate_total_ms}ms (test=${gate_test_ms}ms, build=${gate_build_ms}ms, review=${gate_review_ms}ms, verify=${gate_verify_ms}ms, retries=${gate_retry_count}, retry_tokens=${gate_retry_tokens})"

    # ── Step 5: Mark done and handle merge ──
    update_change_field "$change_name" "status" '"done"'
    update_change_field "$change_name" "completed_at" "\"$(date -Iseconds)\""
    log_info "Change $change_name done (tests: $test_result, review: $([[ "$review_before_merge" == "true" ]] && echo "pass" || echo "skipped"), verify: ok)"

    # Increment changes since checkpoint
    local count
    count=$(jq -r '.changes_since_checkpoint // 0' "$STATE_FILENAME")
    update_state_field "changes_since_checkpoint" "$((count + 1))"

    # All policies queue the merge — the monitor loop drains the queue sequentially.
    # This ensures merge + post-merge pipeline (build, smoke, fix) is atomic per change.
    # eager: queue is drained every poll cycle
    # checkpoint: queue is drained at checkpoint boundaries
    # manual: queue is not drained automatically (user runs 'approve --merge')
    case "$merge_policy" in
        eager|checkpoint)
            local tmp
            tmp=$(mktemp)
            jq --arg n "$change_name" '.merge_queue += [$n]' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
            log_info "$change_name added to merge queue (policy: $merge_policy)"
            info "$change_name queued for merge"
            ;;
        manual)
            info "$change_name ready for manual merge"
            ;;
    esac
}
