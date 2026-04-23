#!/usr/bin/env bash
# set-loop engine: cmd_run — the main iteration loop
# Dependencies: lib/loop/state.sh, lib/loop/tasks.sh, lib/loop/prompt.sh must be sourced first
# Also requires: TIMEOUT_CMD, STDBUF_PREFIX, set-common.sh (get_claude_permission_flags, etc.)

# ─── API Error Detection ────────────────────────────────────────────────────
# Backoff constants
API_BACKOFF_BASE=30
API_BACKOFF_MAX=240
API_BACKOFF_MAX_ATTEMPTS=10

# Classify whether a claude CLI failure is an API error by scanning the log.
# Returns 0 if API error detected, 1 otherwise.
# Usage: classify_api_error "$iter_log_file" "$claude_exit_code"
classify_api_error() {
    local log_file="$1"
    local exit_code="$2"

    # Only check non-zero exits
    [[ "$exit_code" -eq 0 ]] && return 1
    [[ ! -f "$log_file" ]] && return 1

    # Grep the last 50 lines of the log for API error patterns
    local tail_content
    tail_content=$(tail -50 "$log_file" 2>/dev/null) || return 1

    # Rate limit errors
    if echo "$tail_content" | grep -qiE '429|rate.?limit|overloaded|too many requests'; then
        return 0
    fi

    # Server errors
    if echo "$tail_content" | grep -qiE '50[0-3]|internal server error|bad gateway|service unavailable'; then
        return 0
    fi

    # Connection errors
    if echo "$tail_content" | grep -qiE 'ECONNRESET|connection reset|ETIMEDOUT|socket hang up|ECONNREFUSED'; then
        return 0
    fi

    return 1
}

# Run the actual loop (called in the spawned terminal)
cmd_run() {
    # Derive worktree from CWD
    local wt_path
    wt_path=$(get_worktree_path_from_cwd)
    local worktree_name
    worktree_name=$(basename "$wt_path")

    local state_file
    state_file=$(get_loop_state_file "$wt_path")

    if [[ ! -f "$state_file" ]]; then
        error "No loop state found. Use 'set-loop start' first."
        exit 1
    fi

    # Read settings from state
    local max_iter done_criteria task capacity_limit stall_threshold iteration_timeout_min label permission_mode
    max_iter=$(jq -r '.max_iterations' "$state_file")
    done_criteria=$(jq -r '.done_criteria' "$state_file")
    task=$(jq -r '.task' "$state_file")
    capacity_limit=$(jq -r '.capacity_limit_pct' "$state_file")
    stall_threshold=$(jq -r '.stall_threshold // 2' "$state_file")
    local max_idle_iters
    max_idle_iters=$(jq -r '.max_idle_iterations // 3' "$state_file")
    iteration_timeout_min=$(jq -r '.iteration_timeout_min // 90' "$state_file")
    label=$(jq -r '.label // empty' "$state_file")
    permission_mode=$(jq -r '.permission_mode // "default"' "$state_file")
    local claude_model
    claude_model=$(jq -r '.model // empty' "$state_file")
    local change_name
    change_name=$(jq -r '.change // empty' "$state_file")
    local team_mode
    team_mode=$(jq -r '.team_mode // false' "$state_file")

    # Signal trap variables for cleanup
    local current_iter_started=""
    local current_iter_num=0
    local cleanup_done=false
    local SHUTDOWN_REQUESTED=0

    cleanup_on_exit() {
        # Guard against double-trap (EXIT + SIGTERM)
        if [[ "${cleanup_done:-false}" == true ]]; then
            return
        fi
        cleanup_done=true

        echo ""
        echo "⚠️  Loop interrupted, recording state..."

        # Kill child processes (claude, tee, dev servers, etc.) with grace period
        pkill -TERM -P $$ 2>/dev/null || true
        # Wait up to 10s for children to exit, then force kill
        local _grace=0
        while [[ $_grace -lt 10 ]]; do
            if ! pgrep -P $$ &>/dev/null; then
                break
            fi
            sleep 1
            _grace=$((_grace + 1))
        done
        if pgrep -P $$ &>/dev/null; then
            echo "⚠️  Force-killing remaining child processes after 10s grace period"
            pkill -9 -P $$ 2>/dev/null || true
        fi

        # Commit any uncommitted work (graceful shutdown WIP preservation).
        # Skip the commit entirely when the working tree contains deleted
        # files — a shutdown interrupting mid-refactor, or a spurious
        # test-results/ wipe, can leave committed source files marked
        # deleted on disk. `git add -A` would stage those deletions and
        # the resulting wip commit would silently destroy real work
        # (observed: 1368 lines of cart implementation deleted by a
        # graceful-shutdown commit during the craftbrew-run-20260415-0146
        # E2E). When deletions are present, leave the worktree dirty —
        # the orphan-cleanup archive (rename-with-timestamp) preserves
        # full state for post-mortem instead.
        if [[ -d "$wt_path" ]]; then
            local porcelain deletion_count modified_count
            porcelain=$(git -C "$wt_path" status --porcelain 2>/dev/null)
            deletion_count=$(printf '%s\n' "$porcelain" | grep -c '^.D' || true)
            modified_count=$(printf '%s\n' "$porcelain" | grep -c '^..[^[:space:]]' || true)
            if [[ -n "$porcelain" ]]; then
                if [[ "$deletion_count" -gt 0 ]]; then
                    echo "⚠️  Shutdown: $deletion_count deleted file(s) in worktree — skipping wip commit to avoid data loss. Worktree state preserved on disk."
                elif [[ "$modified_count" -gt 0 ]]; then
                    echo "📦 Committing work-in-progress before exit..."
                    git -C "$wt_path" add -A 2>/dev/null || true
                    git -C "$wt_path" commit -m "wip: graceful shutdown — incomplete task" --no-verify 2>/dev/null || true
                fi
            fi
            # Write last_commit to loop-state
            local head_commit
            head_commit=$(git -C "$wt_path" rev-parse HEAD 2>/dev/null || echo "")
            if [[ -n "$head_commit" && -n "${state_file:-}" && -f "$state_file" ]]; then
                update_loop_state "$state_file" "last_commit" "\"$head_commit\""
            fi
        fi

        if [[ -n "$current_iter_started" && -f "$state_file" ]]; then
            local ended
            ended=$(date -Iseconds)
            local commits
            commits=$(get_new_commits "$wt_path" "$current_iter_started" 2>/dev/null || echo "[]")
            add_iteration "$state_file" "$current_iter_num" "$current_iter_started" "$ended" "false" "$commits" "0" "false"
        fi

        if [[ -n "${state_file:-}" && -f "$state_file" ]]; then
            update_loop_state "$state_file" "status" '"stopped"'
        fi
    }

    trap 'SHUTDOWN_REQUESTED=1; cleanup_on_exit' SIGTERM SIGHUP
    trap 'cleanup_on_exit' EXIT SIGINT

    # Update status
    update_loop_state "$state_file" "status" '"running"'
    update_loop_state "$state_file" "terminal_pid" "$$"

    # Save terminal PID
    echo "$$" > "$(get_terminal_pid_file "$wt_path")"

    cd "$wt_path" || exit 1

    # Ensure per-iteration log directory exists
    local log_dir
    log_dir=$(get_loop_log_dir "$wt_path")
    mkdir -p "$log_dir"

    # Gather context for banner
    local git_branch
    git_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null || echo "unknown")
    local memory_status="inactive"
    if command -v set-memory &>/dev/null && set-memory health &>/dev/null; then
        memory_status="active"
    fi
    local title_suffix=""
    if [[ -n "$label" ]]; then
        title_suffix=" ($label)"
    fi

    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  Ralph Loop: $worktree_name"
    if [[ -n "$label" ]]; then
    echo "║  Label: $label"
    fi
    echo "║  Path: $wt_path"
    echo "║  Branch: $git_branch"
    echo "║  Task: $task"
    echo "║  ──────────────────────────────────────────────────────────────"
    local token_budget
    token_budget=$(jq -r '.token_budget // 0' "$state_file")
    local budget_display="unlimited"
    if [[ "$token_budget" -gt 0 ]] 2>/dev/null; then
        budget_display="$((token_budget / 1000))K"
    fi
    echo "║  Mode: $permission_mode | Model: ${claude_model:-default} | Max: $max_iter | Stall: $stall_threshold | Idle: $max_idle_iters | Timeout: ${iteration_timeout_min}m"
    local team_display="off"
    if [[ "$team_mode" == "true" ]]; then team_display="enabled"; fi
    echo "║  Memory: $memory_status | Budget: $budget_display | Team: $team_display"
    echo "║  Started: $(date '+%Y-%m-%d %H:%M:%S')"
    echo "╚════════════════════════════════════════════════════════════════╝"
    echo ""

    if [[ -n "$claude_model" ]]; then
        echo "🤖 Claude model: $claude_model"
    else
        echo "🤖 Claude model: (router default)"
    fi
    echo ""

    local iteration=0
    local stall_count=0
    local repeated_msg_count=0
    local last_commit_msg=""
    local idle_count=0
    local last_output_hash=""
    local ff_attempts=0
    local api_backoff_count=0
    local api_backoff_delay=$API_BACKOFF_BASE
    local ff_max_retries
    ff_max_retries=$(jq -r '.ff_max_retries // 2' "$state_file")
    local start_time
    start_time=$(date -Iseconds)

    while [[ $iteration -lt $max_iter ]]; do
        # Check shutdown flag before starting new iteration
        if [[ $SHUTDOWN_REQUESTED -eq 1 ]]; then
            echo ""
            echo "╔════════════════════════════════════════════════════════════════╗"
            echo "║  🛑 SHUTDOWN: Graceful stop requested, exiting after iteration ║"
            echo "╚════════════════════════════════════════════════════════════════╝"
            update_loop_state "$state_file" "status" '"shutdown"'
            update_terminal_title "Ralph: ${worktree_name}${title_suffix} [shutdown]"
            trap - EXIT SIGTERM SIGINT
            cleanup_on_exit
            exit 0
        fi

        iteration=$((iteration + 1))

        # Update terminal title with progress
        update_terminal_title "Ralph: ${worktree_name}${title_suffix} [${iteration}/${max_iter}]"

        echo ""
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo "  ITERATION $iteration / $max_iter"
        echo "  $(date '+%H:%M:%S')"
        echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        echo ""

        # Update state
        update_loop_state "$state_file" "current_iteration" "$iteration"

        local iter_start
        iter_start=$(date -Iseconds)
        current_iter_started="$iter_start"
        current_iter_num="$iteration"

        # Record tokens before iteration for tracking (JSON with per-type breakdown)
        local tokens_before_json tokens_before in_before out_before cr_before cc_before
        tokens_before_json=$(get_current_tokens "$start_time")
        tokens_before=$(extract_token_field "$tokens_before_json" "total_tokens")
        in_before=$(extract_token_field "$tokens_before_json" "input_tokens")
        out_before=$(extract_token_field "$tokens_before_json" "output_tokens")
        cr_before=$(extract_token_field "$tokens_before_json" "cache_read_tokens")
        cc_before=$(extract_token_field "$tokens_before_json" "cache_create_tokens")

        # Capture pre-iteration action for ff→apply chaining detection
        local pre_action=""
        if [[ "$done_criteria" == "openspec" && -n "$change_name" ]]; then
            pre_action=$(detect_next_change_action "$wt_path" "$change_name")
        fi

        # Build prompt
        local prompt
        prompt=$(build_prompt "$task" "$iteration" "$max_iter" "$wt_path" "$done_criteria" "$change_name")

        # Measure prompt size for context breakdown (chars/4 ≈ tokens)
        local prompt_tokens_est=0
        if [[ -n "$prompt" ]]; then
            prompt_tokens_est=$(( ${#prompt} / 4 ))
        fi

        # Per-iteration log file
        local iter_log_file
        iter_log_file=$(get_iter_log_file "$wt_path" "$iteration")

        # Run Claude with retry logic and per-iteration timeout
        local timeout_seconds=$((iteration_timeout_min * 60))
        echo "Starting Claude Code... (timeout: ${iteration_timeout_min}m, log: $iter_log_file)"
        echo ""

        local claude_exit_code=0
        local retry_count=0
        local max_retries=2
        local iter_timed_out=false

        # Build Claude permission flags from state or config
        local perm_mode
        perm_mode=$(jq -r '.permission_mode // "auto-accept"' "$state_file" 2>/dev/null)
        local perm_flags
        perm_flags=$(get_claude_permission_flags "$perm_mode")

        # Build model flag from state (resolve short names to full IDs)
        local model_flag=""
        local state_model
        state_model=$(jq -r '.model // empty' "$state_file" 2>/dev/null)
        if [[ -n "$state_model" ]]; then
            state_model=$(resolve_model_id "$state_model")
            model_flag="--model $state_model"
        fi

        # Session continuation flags
        local session_flags=""
        local is_resumed=false
        local session_id
        session_id=$(jq -r '.session_id // empty' "$state_file" 2>/dev/null)
        local resume_failures
        resume_failures=$(jq -r '.resume_failures // 0' "$state_file" 2>/dev/null)

        # Decide between new session and --resume. We use --resume whenever a
        # valid session_id is present (preserved by init_loop_state across
        # dispatcher-level restarts) and resume_failures are below the threshold.
        # This keeps Claude's prompt cache warm across gate retries and avoids
        # re-reading files + rebuilding context on every fix iteration.
        #
        # Threshold was 3 but that let two cycles of poisoned-context resume
        # burn through ~20M tokens before dropping to fresh (observed in
        # craftbrew-run-20260423). Lowered to 2: one failed resume already
        # means the preserved context cost us a cycle, a second one doubles
        # the waste without adding diagnostic value.
        if [[ -z "$session_id" ]] || [[ "$resume_failures" -ge 2 ]]; then
            # No session or too many resume failures: new session
            session_id=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null)
            session_flags="--session-id $session_id"
            update_loop_state "$state_file" "session_id" "\"$session_id\""
            if [[ "$resume_failures" -ge 2 ]]; then
                echo "⚠️  Too many resume failures ($resume_failures), using fresh session"
                update_loop_state "$state_file" "resume_failures" "0"
            fi
        else
            # Resume existing session — either mid-iteration continuation or
            # cross-dispatch retry with a preserved session_id.
            session_flags="--resume $session_id"
            is_resumed=true
            if [[ $iteration -eq 1 ]]; then
                echo "♻️  Resuming preserved session ${session_id:0:8} for iteration 1 (retry/redispatch)"
            fi
        fi

        # Build effective prompt: use full prompt always (even on resume)
        # Previously, resumed sessions got a generic "continue" prompt which caused
        # agents to repeat their prior conclusion instead of reading the new action.
        # The full prompt includes critical instructions like /opsx:apply that the
        # agent needs to see even when resuming a session.
        local effective_prompt="$prompt"

        while [[ $retry_count -lt $max_retries ]]; do
            # Pipe prompt via stdin to run in interactive mode (not -p print mode).
            # Interactive mode enables skills (/opsx:ff, /opsx:apply) and hooks.
            # - env -u CLAUDECODE: allow claude when invoked from a Claude session
            # - --foreground: keep child in foreground process group (prevents Tl stops)
            # - Output tee'd to per-iteration log file
            local iter_start_epoch_resume
            iter_start_epoch_resume=$(date +%s)

            # Note: eval is safe here — perm_flags/model_flag/session_flags are
            # fully controlled strings from get_claude_permission_flags() and jq,
            # never from user input. eval is needed because --allowedTools "X,Y"
            # requires proper word splitting of the quoted argument.
            #
            # Output path:
            #   USE_PTY_WRAP=1 (preferred): script -E never -efqc CMD /dev/null
            #     allocates a PTY so Claude's stdout is line-buffered (fixes the
            #     "chain.log empty for minutes" bug). `script -e` returns the
            #     child's exit code via PIPESTATUS[1]. tr strips PTY \r\n.
            #   USE_PTY_WRAP=0 (fallback): stdbuf + tee — unreliable on node.
            if [[ "${USE_PTY_WRAP:-0}" == "1" ]]; then
                if [[ -n "$TIMEOUT_CMD" ]]; then
                    eval "echo \"\$effective_prompt\" | env -u CLAUDECODE script -E never -efqc \"$TIMEOUT_CMD --foreground --signal=TERM $timeout_seconds claude $perm_flags $model_flag $session_flags --verbose\" /dev/null 2>&1 | tr -d '\r' | tee -a \"\$iter_log_file\""
                else
                    eval "echo \"\$effective_prompt\" | env -u CLAUDECODE script -E never -efqc \"claude $perm_flags $model_flag $session_flags --verbose\" /dev/null 2>&1 | tr -d '\r' | tee -a \"\$iter_log_file\""
                fi
                # PIPESTATUS: [0]=echo  [1]=script(-e→child exit)  [2]=tr  [3]=tee
                claude_exit_code=${PIPESTATUS[1]:-$?}
            else
                if [[ -n "$TIMEOUT_CMD" ]]; then
                    eval "echo \"\$effective_prompt\" | env -u CLAUDECODE $STDBUF_PREFIX $TIMEOUT_CMD --foreground --signal=TERM \"$timeout_seconds\" \
                        claude $perm_flags $model_flag $session_flags \
                           --verbose 2>&1 | $STDBUF_PREFIX tee -a \"\$iter_log_file\""
                else
                    eval "echo \"\$effective_prompt\" | env -u CLAUDECODE $STDBUF_PREFIX claude $perm_flags $model_flag $session_flags \
                       --verbose 2>&1 | $STDBUF_PREFIX tee -a \"\$iter_log_file\""
                fi
                claude_exit_code=${PIPESTATUS[0]:-$?}
            fi

            if [[ $claude_exit_code -eq 124 ]]; then
                # Timeout exit code
                iter_timed_out=true
                echo ""
                echo "⏱️  Iteration timed out after ${iteration_timeout_min} minutes"
                echo "⏱️  Timeout: iteration $iteration exceeded ${iteration_timeout_min}m" >&2
                break  # Don't retry on timeout
            fi

            if [[ $claude_exit_code -eq 0 ]]; then
                # Reset API backoff on success
                api_backoff_count=0
                api_backoff_delay=$API_BACKOFF_BASE
                break  # Success
            fi

            # API error detection — check before generic retry
            if classify_api_error "$iter_log_file" "$claude_exit_code"; then
                api_backoff_count=$((api_backoff_count + 1))
                if [[ $api_backoff_count -ge $API_BACKOFF_MAX_ATTEMPTS ]]; then
                    echo ""
                    echo "⚠️  API unavailable after $API_BACKOFF_MAX_ATTEMPTS backoff attempts. Marking as stalled."
                    update_loop_state "$state_file" "status" '"stalled"'
                    update_loop_state "$state_file" "stall_reason" '"api_unavailable"'
                    break 2  # Break out of both retry and iteration loops
                fi
                echo ""
                echo "⏳ API error detected (attempt $api_backoff_count/$API_BACKOFF_MAX_ATTEMPTS). Backing off ${api_backoff_delay}s..."
                update_loop_state "$state_file" "status" '"waiting:api"'
                sleep "$api_backoff_delay"
                # Exponential backoff: double delay, cap at max
                api_backoff_delay=$((api_backoff_delay * 2))
                if [[ $api_backoff_delay -gt $API_BACKOFF_MAX ]]; then
                    api_backoff_delay=$API_BACKOFF_MAX
                fi
                update_loop_state "$state_file" "status" '"running"'
                continue  # Retry same iteration
            fi

            # Resume failure detection: if resumed session failed quickly, fallback
            if $is_resumed; then
                local elapsed=$(( $(date +%s) - iter_start_epoch_resume ))
                if [[ $elapsed -lt 5 ]]; then
                    echo "⚠️  Session resume failed (exit $claude_exit_code in ${elapsed}s), falling back to fresh session"
                    resume_failures=$((resume_failures + 1))
                    update_loop_state "$state_file" "resume_failures" "$resume_failures"
                    # Generate new session ID and retry with fresh session
                    session_id=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null)
                    session_flags="--session-id $session_id"
                    update_loop_state "$state_file" "session_id" "\"$session_id\""
                    is_resumed=false
                    effective_prompt="$prompt"
                    retry_count=$((retry_count + 1))
                    continue
                fi
            fi

            retry_count=$((retry_count + 1))
            if [[ $retry_count -lt $max_retries ]]; then
                echo ""
                echo "⚠️  Claude error (exit code: $claude_exit_code). Retrying in 30 seconds... (attempt $((retry_count + 1))/$max_retries)"
                sleep 30
            else
                echo ""
                echo "⚠️  Claude failed after $max_retries attempts. Continuing to next iteration..."
            fi
        done

        local iter_end
        iter_end=$(date -Iseconds)

        # Get new commits
        local new_commits
        new_commits=$(get_new_commits "$wt_path" "$iter_start")

        # Process reflection file (agent writes learnings here).
        # Canonical path is .set/reflection.md; fall back to legacy
        # .claude/reflection.md for pre-migration worktrees.
        local reflection_file="$wt_path/.set/reflection.md"
        if [[ ! -f "$reflection_file" && -f "$wt_path/.claude/reflection.md" ]]; then
            reflection_file="$wt_path/.claude/reflection.md"
        fi
        if [[ -f "$reflection_file" ]]; then
            local reflection_content
            reflection_content=$(cat "$reflection_file" 2>/dev/null)

            # Filter out noise: empty, too short, or generic/completion messages
            local should_save=true
            if [[ -z "$reflection_content" ]]; then
                should_save=false
            elif [[ "$reflection_content" == "No notable issues." ]]; then
                should_save=false
            elif echo "$reflection_content" | grep -qiE "^(all changes complete|no notable|no errors encountered|nothing to report)"; then
                should_save=false
            elif echo "$reflection_content" | grep -qiE "already (fully |)implemented|already existed|already had a proposal|already committed|confirm tests pass"; then
                should_save=false
            elif [[ ${#reflection_content} -lt 50 ]]; then
                should_save=false
            fi

            if $should_save; then
                if command -v set-memory &>/dev/null && set-memory health &>/dev/null 2>&1; then
                    # Extract change name from last commit for tagging
                    local change_tag=""
                    local last_msg
                    last_msg=$(cd "$wt_path" && git log -1 --format='%s' 2>/dev/null || echo "")
                    if [[ "$last_msg" == *:* ]]; then
                        local commit_change_name="${last_msg%%:*}"
                        # Validate: change name should be kebab-case, not too long
                        if [[ "$commit_change_name" =~ ^[a-z][a-z0-9-]+$ && ${#commit_change_name} -lt 40 ]]; then
                            change_tag="change:$commit_change_name,"
                        fi
                    fi

                    # Content dedup: check if similar memory already exists
                    local prefix="${reflection_content:0:80}"
                    local is_dupe=false
                    local existing
                    existing=$(set-memory recall "$prefix" --limit 1 --mode semantic 2>/dev/null | \
                        python3 -c "
import sys, json
try:
    memories = json.load(sys.stdin)
    if memories and len(memories) > 0:
        existing = memories[0].get('content', '')[:80]
        new = sys.argv[1][:80]
        # Check if first 80 chars are >70% similar (simple overlap check)
        overlap = sum(1 for a, b in zip(existing, new) if a == b)
        threshold = int(min(len(existing), len(new)) * 0.7)
        print('dupe' if overlap > threshold and threshold > 30 else 'ok')
    else:
        print('ok')
except:
    print('ok')
" "$prefix" 2>/dev/null)
                    [[ "$existing" == "dupe" ]] && is_dupe=true

                    if ! $is_dupe; then
                        echo "$reflection_content" | set-memory remember \
                            --type Learning \
                            --tags "${change_tag}source:agent,reflection" \
                            2>/dev/null && echo "💭 Reflection saved to memory" || true
                    else
                        echo "💭 Reflection skipped (duplicate)"
                    fi
                fi
            fi
            rm -f "$reflection_file"
        fi

        # Calculate tokens used this iteration (per-type breakdown)
        local tokens_after_json tokens_after tokens_used tokens_estimated=false
        local in_after out_after cr_after cc_after
        local in_used=0 out_used=0 cr_used=0 cc_used=0
        tokens_after_json=$(get_current_tokens "$start_time")
        tokens_after=$(extract_token_field "$tokens_after_json" "total_tokens")
        in_after=$(extract_token_field "$tokens_after_json" "input_tokens")
        out_after=$(extract_token_field "$tokens_after_json" "output_tokens")
        cr_after=$(extract_token_field "$tokens_after_json" "cache_read_tokens")
        cc_after=$(extract_token_field "$tokens_after_json" "cache_create_tokens")

        tokens_used=$((tokens_after - tokens_before))
        [[ $tokens_used -lt 0 ]] && tokens_used=0
        in_used=$((in_after - in_before)); [[ $in_used -lt 0 ]] && in_used=0
        out_used=$((out_after - out_before)); [[ $out_used -lt 0 ]] && out_used=0
        cr_used=$((cr_after - cr_before)); [[ $cr_used -lt 0 ]] && cr_used=0
        cc_used=$((cc_after - cc_before)); [[ $cc_used -lt 0 ]] && cc_used=0

        # Fallback: if tokens is 0 after claude ran, estimate from session file sizes
        if [[ $tokens_used -eq 0 && $claude_exit_code -ne 1 ]]; then
            echo "⚠️  Token tracking returned 0 after claude invocation" >&2
            local iter_start_epoch
            iter_start_epoch=$(parse_date_to_epoch "$iter_start")
            if [[ "$iter_start_epoch" -gt 0 ]]; then
                tokens_used=$(estimate_tokens_from_files "$wt_path" "$iter_start_epoch")
                if [[ $tokens_used -gt 0 ]]; then
                    tokens_estimated=true
                    tokens_after=$((tokens_before + tokens_used))
                    # Per-type unknown for estimation — leave at 0
                    in_used=0; out_used=0; cr_used=0; cc_used=0
                    echo "📊 Iteration tokens: ~$tokens_used (estimated from file sizes)"
                else
                    echo "📊 Iteration tokens: 0"
                fi
            else
                echo "📊 Iteration tokens: 0"
            fi
        else
            echo ""
            echo "📊 Iteration tokens: $tokens_used (in:$in_used out:$out_used cr:$cr_used cc:$cc_used)"
        fi

        # Extract team metrics from iteration log
        local iter_team_spawned=false
        local iter_teammates_count=0
        local iter_team_tasks_parallel=0
        if [[ "$team_mode" == "true" ]] && [[ -s "$iter_log_file" ]]; then
            local team_create_count
            team_create_count=$(grep -c 'TeamCreate' "$iter_log_file" 2>/dev/null || echo 0)
            if [[ "$team_create_count" -gt 0 ]]; then
                iter_team_spawned=true
                # Count Agent tool invocations with team_name (teammate spawns)
                iter_teammates_count=$(grep -c 'team_name' "$iter_log_file" 2>/dev/null || echo 0)
                # Count TaskCreate calls as proxy for parallel tasks
                iter_team_tasks_parallel=$(grep -c 'TaskCreate' "$iter_log_file" 2>/dev/null || echo 0)
                echo "👥 Team metrics: spawned=$iter_team_spawned teammates=$iter_teammates_count parallel_tasks=$iter_team_tasks_parallel"
            fi
        fi

        # Post-iteration log summary
        if [[ -s "$iter_log_file" ]]; then
            local log_reads log_writes log_skills log_errors
            log_reads=$(grep -c 'Read(' "$iter_log_file" 2>/dev/null || echo 0)
            log_writes=$(grep -c -E 'Write\(|Edit\(' "$iter_log_file" 2>/dev/null || echo 0)
            log_skills=$(grep -c -E '/opsx:|/wt:' "$iter_log_file" 2>/dev/null || echo 0)
            log_errors=$(grep -c -iE 'error|Error:' "$iter_log_file" 2>/dev/null || echo 0)
            echo "📋 Log summary: ${log_reads} reads, ${log_writes} writes, ${log_skills} skills, ${log_errors} errors"
        elif [[ -f "$iter_log_file" ]]; then
            echo "📋 No log output captured"
        fi

        # ─── Context breakdown estimation ────────────────────────────────────
        # base_context: iteration 1 cache_create = fixed context (system prompt + CLAUDE.md + rules)
        # memory_injection: sum of <system-reminder> block sizes in iter log (chars/4)
        # prompt_overhead: measured from build_prompt() output size (chars/4)
        # tool_output: residual (input_tokens - base - memory - prompt), clamped to 0
        local ctx_base=0 ctx_memory=0 ctx_prompt=0 ctx_tools=0

        # Base context: use cc_used for iteration 1, carry forward for subsequent
        if [[ $iteration -eq 1 ]]; then
            ctx_base=$cc_used
            if [[ $ctx_base -gt 0 ]]; then
                update_loop_state "$state_file" "base_context_tokens" "$ctx_base"
            fi
        else
            ctx_base=$(jq -r '.base_context_tokens // 0' "$state_file" 2>/dev/null)
        fi

        # Memory injection: scan iter log for <system-reminder> blocks
        if [[ -s "$iter_log_file" ]]; then
            local reminder_chars=0
            reminder_chars=$( { grep -oP '<system-reminder>.*?</system-reminder>' "$iter_log_file" 2>/dev/null || true; } | wc -c)
            reminder_chars=${reminder_chars:-0}
            if [[ $reminder_chars -eq 0 ]]; then
                # Try multiline extraction for multi-line reminders
                reminder_chars=$( { sed -n '/<system-reminder>/,/<\/system-reminder>/p' "$iter_log_file" 2>/dev/null || true; } | wc -c)
                reminder_chars=${reminder_chars:-0}
            fi
            ctx_memory=$(( reminder_chars / 4 ))
        fi

        # Prompt overhead: from measured prompt size
        ctx_prompt=$prompt_tokens_est

        # Tool output: residual
        ctx_tools=$(( in_used - ctx_base - ctx_memory - ctx_prompt ))
        [[ $ctx_tools -lt 0 ]] && ctx_tools=0

        echo "📐 Context breakdown: base=$ctx_base mem=$ctx_memory prompt=$ctx_prompt tools=$ctx_tools"

        # Output-level idle detection: stop if same output repeats N times
        if [[ -s "$iter_log_file" ]]; then
            local current_hash
            current_hash=$(tail -200 "$iter_log_file" | shasum -a 256 | cut -d' ' -f1)
            if [[ -n "$last_output_hash" && "$current_hash" == "$last_output_hash" ]]; then
                idle_count=$((idle_count + 1))
                echo "⚠️  Identical output detected ($idle_count/$max_idle_iters)"
                if [[ $idle_count -ge $max_idle_iters ]]; then
                    echo ""
                    echo "╔════════════════════════════════════════════════════════════════╗"
                    echo "║  🛑 IDLE: Identical output for $idle_count consecutive iterations  ║"
                    echo "║  The agent is repeating the same response without progress.       ║"
                    echo "╚════════════════════════════════════════════════════════════════╝"
                    update_loop_state "$state_file" "status" '"idle"'
                    update_loop_state "$state_file" "idle_count" "$idle_count"
                    update_terminal_title "Ralph: ${worktree_name}${title_suffix} [idle]"
                    trap - EXIT SIGTERM SIGINT
                    notify-send "Ralph Loop Idle" "$worktree_name: identical output $idle_count times" 2>/dev/null || true
                    # Record this iteration before exiting
                    local idle_iter_end
                    idle_iter_end=$(date -Iseconds)
                    add_iteration "$state_file" "$iteration" "$iter_start" "$idle_iter_end" "false" "$new_commits" "$tokens_used" "$iter_timed_out" "$tokens_estimated" "true" "false" "$iter_log_file" "$is_resumed" "false" "$in_used" "$out_used" "$cr_used" "$cc_used" "$iter_team_spawned" "$iter_teammates_count" "$iter_team_tasks_parallel" "$ctx_base" "$ctx_memory" "$ctx_prompt" "$ctx_tools"
                    exit 0
                fi
            else
                idle_count=0
            fi
            last_output_hash="$current_hash"
            update_loop_state "$state_file" "idle_count" "$idle_count"
            update_loop_state "$state_file" "last_output_hash" "\"$current_hash\""
        fi

        # Early done check BEFORE stall detection — never stall a completed change (STALL-001)
        local early_done=false
        if check_done "$wt_path" "$done_criteria" "$change_name"; then
            early_done=true
            stall_count=0  # Reset stall counter (STALL-002)
        fi
        # Fallback: if primary done criteria says not done, check tasks.md
        # Pass $change_name so we only find THIS change's tasks.md, not a sibling's
        if ! $early_done && [[ "$done_criteria" != "tasks" && "$done_criteria" != "test" && "$done_criteria" != "build" && "$done_criteria" != "merge" ]]; then
            if find_tasks_file "$wt_path" "$change_name" &>/dev/null && check_tasks_done "$wt_path" "$change_name" 2>/dev/null; then
                early_done=true
                stall_count=0
                warn "Early done by tasks.md fallback (primary criteria '$done_criteria' said not done)"
            fi
        fi

        # Stall detection: no commits = no progress
        # Exception: ff iterations create artifacts without committing — check for new/modified files
        local has_artifact_progress=false
        if [[ "$new_commits" == "[]" ]] || [[ -z "$new_commits" ]]; then
            local dirty_count
            dirty_count=$(git status --porcelain 2>/dev/null | wc -l)
            if [[ "$dirty_count" -gt 0 ]]; then
                has_artifact_progress=true
            fi
        fi

        if { [[ "$new_commits" == "[]" ]] || [[ -z "$new_commits" ]]; } && ! $has_artifact_progress && ! $early_done; then
            stall_count=$((stall_count + 1))
            echo "⚠️  No commits or new files this iteration (stall count: $stall_count/$stall_threshold)"

            # Check for stall condition
            if [[ $stall_count -ge $stall_threshold ]]; then
                # Before declaring stall, check if this is actually a waiting:human situation
                # Auto-tasks done + manual tasks remain = waiting for human, not stalled
                local manual_count
                manual_count=$(count_manual_tasks "$wt_path")
                if check_tasks_done "$wt_path" "$change_name" && [[ "$manual_count" -gt 0 ]]; then
                    local manual_tasks_json
                    manual_tasks_json=$(parse_manual_tasks "$wt_path")
                    echo ""
                    echo "╔════════════════════════════════════════════════════════════════╗"
                    echo "║  ⏸  WAITING FOR HUMAN: $manual_count manual task(s) pending      ║"
                    echo "║  All automated tasks complete. Human action required.            ║"
                    echo "║  Run: set-manual show $(basename "$wt_path")                      ║"
                    echo "╚════════════════════════════════════════════════════════════════╝"
                    update_loop_state "$state_file" "status" '"waiting:human"'
                    # Write manual task details to loop-state
                    local tmp_state
                    tmp_state=$(jq --argjson mt "$manual_tasks_json" \
                        --arg ws "$(date -Iseconds)" \
                        '.manual_tasks = $mt | .waiting_since = $ws' "$state_file")
                    echo "$tmp_state" > "$state_file"
                    update_terminal_title "Ralph: ${worktree_name}${title_suffix} [waiting:human]"
                    notify-send "Ralph Loop — Human Action Required" \
                        "$worktree_name has $manual_count manual task(s) pending" 2>/dev/null || true
                    trap - EXIT SIGTERM SIGINT
                    exit 0
                fi

                # Before declaring stall, check if work is actually done
                if check_done "$wt_path" "$done_criteria" "$change_name"; then
                    echo "⚠️  No commits but work is done — skipping stall"
                    stall_count=0
                else
                    echo ""
                    echo "╔════════════════════════════════════════════════════════════════╗"
                    echo "║  🛑 STALLED: No commits in $stall_count iteration(s)            ║"
                    echo "║  The loop appears to have nothing left to do.                   ║"
                    echo "╚════════════════════════════════════════════════════════════════╝"
                    update_loop_state "$state_file" "status" '"stalled"'
                    update_terminal_title "Ralph: ${worktree_name}${title_suffix} [stalled]"
                    trap - EXIT SIGTERM SIGINT
                    exit 0
                fi
            fi
        elif $has_artifact_progress; then
            stall_count=0  # Artifact creation counts as progress (ff iterations)
            echo "📝 No commits but new artifact files detected (ff iteration)"
            # Even with artifact progress, check if work is done — the agent may
            # have completed all tasks but artifact files trigger false progress
            if check_done "$wt_path" "$done_criteria" "$change_name"; then
                echo "✅ Work is done despite artifact-only progress — will exit on done check"
            fi
        else
            stall_count=0  # Reset on progress
            echo "✅ Commits this iteration: $(echo "$new_commits" | jq -r 'length') new"

            # Repeated commit message detection: same message N times = stall
            # Normalize: strip trailing iteration/attempt numbers for comparison
            local current_commit_msg
            current_commit_msg=$(git log -1 --format='%s' 2>/dev/null | sed -E 's/ (on |)iteration [0-9]+//; s/ \(attempt [0-9]+\)//' || echo "")
            if [[ -n "$current_commit_msg" && "$current_commit_msg" == "$last_commit_msg" ]]; then
                repeated_msg_count=$((repeated_msg_count + 1))
                echo "⚠️  Same commit message repeated ($repeated_msg_count/$stall_threshold): $current_commit_msg"
                if [[ $repeated_msg_count -ge $stall_threshold ]]; then
                    # Before declaring stall, check if work is actually done
                    # The agent may commit the same cleanup message while done_check would pass
                    if check_done "$wt_path" "$done_criteria" "$change_name"; then
                        echo "⚠️  Repeated commit message but work is done — skipping stall"
                        repeated_msg_count=0
                    else
                        echo ""
                        echo "╔════════════════════════════════════════════════════════════════╗"
                        echo "║  🛑 STALLED: Same commit message $repeated_msg_count times          ║"
                        echo "║  \"${current_commit_msg:0:50}\"                                      ║"
                        echo "║  The agent appears stuck in a loop.                             ║"
                        echo "╚════════════════════════════════════════════════════════════════╝"
                        update_loop_state "$state_file" "status" '"stalled"'
                        update_terminal_title "Ralph: ${worktree_name}${title_suffix} [stalled]"
                        trap - EXIT SIGTERM SIGINT
                        exit 0
                    fi
                fi
            else
                repeated_msg_count=0
                last_commit_msg="$current_commit_msg"
            fi
        fi

        # FF retry tracking: if this was an ff: iteration, check if tasks.md was created
        local iter_ff_exhausted=false
        local iter_ff_recovered=false
        local iter_no_op=false
        if [[ "$done_criteria" == "openspec" && -n "$change_name" ]]; then
            local post_action
            post_action=$(detect_next_change_action "$wt_path" "$change_name")
            if [[ "$post_action" == ff:* ]]; then
                # FF ran but tasks.md still missing
                ff_attempts=$((ff_attempts + 1))
                update_loop_state "$state_file" "ff_attempts" "$ff_attempts"
                echo "FF attempt $ff_attempts/$ff_max_retries failed — tasks.md not created"
                if [[ $ff_attempts -ge $ff_max_retries ]]; then
                    # Try to recover by generating fallback tasks.md from proposal
                    if generate_fallback_tasks "$wt_path" "$change_name"; then
                        iter_ff_recovered=true
                        ff_attempts=0
                        update_loop_state "$state_file" "ff_attempts" "0"
                        echo "✓ Recovery: fallback tasks.md generated — continuing loop"
                    else
                        iter_ff_exhausted=true
                        echo ""
                        echo "╔════════════════════════════════════════════════════════════════╗"
                        echo "║  FF failed to create tasks.md after $ff_max_retries attempts       ║"
                        echo "║  No proposal.md found — cannot recover. Stalling.                  ║"
                        echo "╚════════════════════════════════════════════════════════════════╝"
                        # Record iteration, then exit
                    fi
                fi
            else
                # tasks.md exists (action is apply: or done) — reset counter
                if [[ $ff_attempts -gt 0 ]]; then
                    ff_attempts=0
                    update_loop_state "$state_file" "ff_attempts" "0"
                fi

                # ff→apply chaining: if this iteration transitioned from ff to apply, chain in same iteration
                # This eliminates the wasted iteration where memory injection confuses the agent
                # Uses action transition detection (pre_action→post_action) instead of dirty file check
                if [[ "$pre_action" == ff:* && "$post_action" == apply:* ]]; then
                    local chain_change="${post_action#apply:}"
                    echo ""
                    echo "🔗 Chaining: ff created tasks.md → running apply in same iteration"
                    echo ""

                    # Build apply prompt
                    local chain_prompt
                    chain_prompt=$(build_prompt "$task" "$iteration" "$max_iter" "$wt_path" "$done_criteria" "$chain_change")

                    # Run chained Claude invocation (fresh session — resume won't have apply context)
                    local chain_session_id chain_log_file chain_exit=0
                    chain_session_id=$(uuidgen 2>/dev/null || python3 -c 'import uuid; print(uuid.uuid4())' 2>/dev/null || cat /proc/sys/kernel/random/uuid 2>/dev/null)
                    chain_log_file="${iter_log_file%.log}-chain.log"

                    # See PTY wrapping rationale in main invocation above.
                    if [[ "${USE_PTY_WRAP:-0}" == "1" ]]; then
                        if [[ -n "$TIMEOUT_CMD" ]]; then
                            eval "echo \"\$chain_prompt\" | env -u CLAUDECODE script -E never -efqc \"$TIMEOUT_CMD --foreground --signal=TERM $timeout_seconds claude $perm_flags $model_flag --session-id $chain_session_id --verbose\" /dev/null 2>&1 | tr -d '\r' | tee -a \"\$chain_log_file\""
                        else
                            eval "echo \"\$chain_prompt\" | env -u CLAUDECODE script -E never -efqc \"claude $perm_flags $model_flag --session-id $chain_session_id --verbose\" /dev/null 2>&1 | tr -d '\r' | tee -a \"\$chain_log_file\""
                        fi
                        chain_exit=${PIPESTATUS[1]:-$?}
                    else
                        if [[ -n "$TIMEOUT_CMD" ]]; then
                            echo "$chain_prompt" | env -u CLAUDECODE $STDBUF_PREFIX $TIMEOUT_CMD --foreground --signal=TERM "$timeout_seconds" \
                                claude $perm_flags $model_flag --session-id "$chain_session_id" \
                                   --verbose 2>&1 | $STDBUF_PREFIX tee -a "$chain_log_file"
                        else
                            echo "$chain_prompt" | env -u CLAUDECODE $STDBUF_PREFIX claude $perm_flags $model_flag --session-id "$chain_session_id" \
                               --verbose 2>&1 | $STDBUF_PREFIX tee -a "$chain_log_file"
                        fi
                        chain_exit=${PIPESTATUS[0]:-$?}
                    fi

                    # Collect chained commits
                    local chain_commits
                    chain_commits=$(get_new_commits "$wt_path" "$iter_end")
                    if [[ "$chain_commits" != "[]" ]] && [[ -n "$chain_commits" ]]; then
                        echo "🔗 Chained apply produced commits"
                        # Merge chained commits into this iteration's commits
                        new_commits=$(echo "[$new_commits, $chain_commits]" | jq -s 'flatten' 2>/dev/null || echo "$new_commits")
                        # Reset stall counter — chained apply made progress
                        stall_count=0
                    fi

                    # Update iter_end and tokens after chain (per-type)
                    iter_end=$(date -Iseconds)
                    local chain_tokens_after_json chain_tokens_after
                    chain_tokens_after_json=$(get_current_tokens "$start_time")
                    chain_tokens_after=$(extract_token_field "$chain_tokens_after_json" "total_tokens")
                    local chain_tokens_used=$((chain_tokens_after - tokens_after))
                    [[ $chain_tokens_used -lt 0 ]] && chain_tokens_used=0
                    tokens_used=$((tokens_used + chain_tokens_used))

                    # Accumulate per-type deltas from chain
                    local chain_in chain_out chain_cr chain_cc
                    chain_in=$(extract_token_field "$chain_tokens_after_json" "input_tokens")
                    chain_out=$(extract_token_field "$chain_tokens_after_json" "output_tokens")
                    chain_cr=$(extract_token_field "$chain_tokens_after_json" "cache_read_tokens")
                    chain_cc=$(extract_token_field "$chain_tokens_after_json" "cache_create_tokens")
                    local chain_in_d=$((chain_in - in_after)); [[ $chain_in_d -lt 0 ]] && chain_in_d=0
                    local chain_out_d=$((chain_out - out_after)); [[ $chain_out_d -lt 0 ]] && chain_out_d=0
                    local chain_cr_d=$((chain_cr - cr_after)); [[ $chain_cr_d -lt 0 ]] && chain_cr_d=0
                    local chain_cc_d=$((chain_cc - cc_after)); [[ $chain_cc_d -lt 0 ]] && chain_cc_d=0
                    in_used=$((in_used + chain_in_d))
                    out_used=$((out_used + chain_out_d))
                    cr_used=$((cr_used + chain_cr_d))
                    cc_used=$((cc_used + chain_cc_d))

                    tokens_after=$chain_tokens_after
                    in_after=$chain_in; out_after=$chain_out; cr_after=$chain_cr; cc_after=$chain_cc
                    echo "🔗 Chain complete (exit: $chain_exit, +${chain_tokens_used} tokens)"
                fi
            fi
        fi

        # No-op iteration marker for session-end hooks
        if { [[ "$new_commits" == "[]" ]] || [[ -z "$new_commits" ]]; } && ! $has_artifact_progress; then
            iter_no_op=true
            echo "$(date -Iseconds)" > "$wt_path/.claude/loop-iteration-noop"
        else
            rm -f "$wt_path/.claude/loop-iteration-noop"
        fi

        # Check done
        local is_done=false
        if check_done "$wt_path" "$done_criteria" "$change_name"; then
            is_done=true
        fi

        # Universal done detection safety net
        # If primary criteria says not done, check if tasks.md has all tasks [x]
        # Skip fallback for test/build/merge — those have objective pass/fail criteria
        # Pass $change_name so we only find THIS change's tasks.md, not a sibling's
        if ! $is_done && [[ "$done_criteria" != "tasks" && "$done_criteria" != "test" && "$done_criteria" != "build" && "$done_criteria" != "merge" ]]; then
            if find_tasks_file "$wt_path" "$change_name" &>/dev/null && check_tasks_done "$wt_path" "$change_name" 2>/dev/null; then
                is_done=true
                warn "Done by tasks.md fallback (primary criteria '$done_criteria' said not done)"
            fi
        fi

        # Add iteration to state with token tracking + context breakdown
        add_iteration "$state_file" "$iteration" "$iter_start" "$iter_end" "$is_done" "$new_commits" "$tokens_used" "$iter_timed_out" "$tokens_estimated" "$iter_no_op" "$iter_ff_exhausted" "$iter_log_file" "$is_resumed" "$iter_ff_recovered" "$in_used" "$out_used" "$cr_used" "$cc_used" "$iter_team_spawned" "$iter_teammates_count" "$iter_team_tasks_parallel" "$ctx_base" "$ctx_memory" "$ctx_prompt" "$ctx_tools"

        # Handle ff exhaustion (after recording iteration)
        if $iter_ff_exhausted; then
            update_loop_state "$state_file" "status" '"stalled"'
            update_terminal_title "Ralph: ${worktree_name}${title_suffix} [stalled:ff]"
            trap - EXIT SIGTERM SIGINT
            notify-send "Ralph Loop Stalled" "$worktree_name: FF failed to create tasks.md after $ff_max_retries attempts" 2>/dev/null || true
            exit 0
        fi
        current_iter_started=""  # Clear so trap doesn't double-record

        # Update total tokens in state (all types)
        update_loop_state "$state_file" "total_tokens" "$tokens_after"
        update_loop_state "$state_file" "total_input_tokens" "$in_after"
        update_loop_state "$state_file" "total_output_tokens" "$out_after"
        update_loop_state "$state_file" "total_cache_read" "$cr_after"
        update_loop_state "$state_file" "total_cache_create" "$cc_after"

        # Token budget enforcement → waiting:budget human checkpoint
        if [[ "$token_budget" -gt 0 && "$tokens_after" -gt "$token_budget" ]] 2>/dev/null; then
            local budget_k=$((token_budget / 1000))
            local used_k=$((tokens_after / 1000))
            echo ""
            echo "╔════════════════════════════════════════════════════════════════╗"
            echo "║  ⏸  BUDGET CHECKPOINT: ${used_k}K / ${budget_k}K                 ║"
            echo "║  The loop exceeded the estimated token budget.                   ║"
            echo "║                                                                  ║"
            echo "║  Continue:  set-loop resume                                       ║"
            echo "║  Raise:     set-loop budget <N>                                   ║"
            echo "║  Stop:      set-loop stop                                         ║"
            echo "╚════════════════════════════════════════════════════════════════╝"
            update_loop_state "$state_file" "status" '"waiting:budget"'
            update_terminal_title "Ralph: ${worktree_name}${title_suffix} [waiting:budget]"
            notify-send "Ralph Loop — Budget Checkpoint" "$worktree_name: ${used_k}K / ${budget_k}K tokens — waiting for approval" 2>/dev/null || true

            # Wait loop: poll state file every 30s for status change
            while true; do
                sleep 30
                local current_budget_status
                current_budget_status=$(jq -r '.status' "$state_file" 2>/dev/null)
                if [[ "$current_budget_status" == "running" ]]; then
                    echo ""
                    echo "✅ Budget checkpoint approved, continuing..."
                    # Re-read token_budget in case it was updated via set-loop budget
                    token_budget=$(jq -r '.token_budget // 0' "$state_file")
                    break
                elif [[ "$current_budget_status" == "stopped" ]]; then
                    echo ""
                    echo "Loop stopped by user."
                    trap - EXIT SIGTERM SIGINT
                    exit 0
                fi
                # Still waiting:budget — continue polling
            done
        fi

        if $is_done; then
            # Calculate total time
            local done_time done_epoch start_epoch_done total_secs_done total_hours_done total_mins_done
            done_time=$(date '+%Y-%m-%d %H:%M:%S')
            done_epoch=$(date +%s)
            start_epoch_done=$(parse_date_to_epoch "$start_time")
            [[ "$start_epoch_done" -eq 0 ]] && start_epoch_done="$done_epoch"
            total_secs_done=$((done_epoch - start_epoch_done))
            total_hours_done=$((total_secs_done / 3600))
            total_mins_done=$(((total_secs_done % 3600) / 60))

            echo ""
            echo "╔════════════════════════════════════════════════════════════════╗"
            echo "║  ✅ TASK COMPLETE!                                              ║"
            echo "║  Finished: $done_time                              ║"
            echo "║  Iterations: $iteration | Runtime: ${total_hours_done}h ${total_mins_done}m                            ║"
            echo "╚════════════════════════════════════════════════════════════════╝"

            update_loop_state "$state_file" "status" '"done"'
            update_terminal_title "Ralph: ${worktree_name}${title_suffix} [done]"
            trap - EXIT SIGTERM SIGINT

            # Send notification
            notify-send "Ralph Loop Complete" "$worktree_name finished after $iteration iterations (${total_hours_done}h ${total_mins_done}m)" 2>/dev/null || true

            exit 0
        fi

        # Check if we should continue
        local current_status
        current_status=$(jq -r '.status' "$state_file" 2>/dev/null)
        if [[ "$current_status" == "stopped" ]]; then
            echo ""
            echo "Loop stopped by user."
            exit 0
        fi

        # Show iteration time
        local iter_end_epoch iter_start_epoch iter_duration
        iter_end_epoch=$(date +%s)
        iter_start_epoch=$(parse_date_to_epoch "$iter_start")
        [[ "$iter_start_epoch" -eq 0 ]] && iter_start_epoch="$iter_end_epoch"
        iter_duration=$((iter_end_epoch - iter_start_epoch))
        local iter_mins=$((iter_duration / 60))
        local iter_secs=$((iter_duration % 60))

        echo ""
        echo "Iteration $iteration completed in ${iter_mins}m ${iter_secs}s"
        echo "Not done yet. Continuing in 3 seconds..."
        echo "(Press Ctrl+C to stop)"
        sleep 3
    done

    # Max iterations reached — but first check if work is actually done
    # The agent may have completed everything but the done_check wasn't reached
    # (e.g., artifact file detection masked the no-commits path)
    if check_done "$wt_path" "$done_criteria" "$change_name"; then
        local done_time done_epoch start_epoch_done total_secs_done total_hours_done total_mins_done
        done_time=$(date '+%Y-%m-%d %H:%M:%S')
        done_epoch=$(date +%s)
        start_epoch_done=$(parse_date_to_epoch "$start_time")
        [[ "$start_epoch_done" -eq 0 ]] && start_epoch_done="$done_epoch"
        total_secs_done=$((done_epoch - start_epoch_done))
        total_hours_done=$((total_secs_done / 3600))
        total_mins_done=$(((total_secs_done % 3600) / 60))

        echo ""
        echo "╔════════════════════════════════════════════════════════════════╗"
        echo "║  ✅ TASK COMPLETE (caught at max-iterations boundary)           ║"
        echo "║  Finished: $done_time                              ║"
        echo "║  Iterations: $iteration | Runtime: ${total_hours_done}h ${total_mins_done}m                            ║"
        echo "╚════════════════════════════════════════════════════════════════╝"

        update_loop_state "$state_file" "status" '"done"'
        update_terminal_title "Ralph: ${worktree_name}${title_suffix} [done]"
        trap - EXIT SIGTERM SIGINT
        notify-send "Ralph Loop Complete" "$worktree_name finished after $iteration iterations" 2>/dev/null || true
        exit 0
    fi

    # Calculate total time
    local end_time end_epoch start_epoch total_secs total_hours total_mins
    end_time=$(date '+%Y-%m-%d %H:%M:%S')
    end_epoch=$(date +%s)
    start_epoch=$(parse_date_to_epoch "$start_time")
    [[ "$start_epoch" -eq 0 ]] && start_epoch="$end_epoch"
    total_secs=$((end_epoch - start_epoch))
    total_hours=$((total_secs / 3600))
    total_mins=$(((total_secs % 3600) / 60))

    echo ""
    echo "╔════════════════════════════════════════════════════════════════╗"
    echo "║  ⚠️  MAX ITERATIONS REACHED                                     ║"
    echo "║  Finished: $end_time                              ║"
    echo "║  Total runtime: ${total_hours}h ${total_mins}m                                      ║"
    echo "║  Task may not be complete. Review and resume if needed.        ║"
    echo "╚════════════════════════════════════════════════════════════════╝"

    update_loop_state "$state_file" "status" '"stuck"'
    update_terminal_title "Ralph: ${worktree_name}${title_suffix} [stuck]"
    trap - EXIT SIGTERM SIGINT

    # Send notification
    notify-send "Ralph Loop Stuck" "$worktree_name reached max iterations ($max_iter)" 2>/dev/null || true

    exit 1
}
