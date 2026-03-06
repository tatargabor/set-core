#!/usr/bin/env bash
# lib/orchestration/dispatcher.sh — Change dispatch, lifecycle, monitor loop
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: state.sh (update_change_field, get_change_status, etc.), events.sh (emit_event),
#             planner.sh (auto_replan_cycle), watchdog.sh (watchdog_check, watchdog_heartbeat)

# ─── Base Build Health ───────────────────────────────────────────────

# Cached base build result: "pass", "fail:<output>", or "" (unchecked)
BASE_BUILD_STATUS=""
BASE_BUILD_OUTPUT=""
BASE_BUILD_FIX_ATTEMPTED=false

# Run build on the main project directory (not a worktree).
# Caches result in BASE_BUILD_STATUS / BASE_BUILD_OUTPUT for the session.
# Returns 0 if build passes, 1 if it fails.
check_base_build() {
    local project_path="$1"

    # Return cached result
    if [[ "$BASE_BUILD_STATUS" == "pass" ]]; then
        return 0
    elif [[ "$BASE_BUILD_STATUS" == "fail" ]]; then
        return 1
    fi

    # Detect build command + package manager
    local pm="npm"
    [[ -f "$project_path/pnpm-lock.yaml" ]] && pm="pnpm"
    [[ -f "$project_path/yarn.lock" ]] && pm="yarn"
    [[ -f "$project_path/bun.lockb" || -f "$project_path/bun.lock" ]] && pm="bun"

    local build_cmd=""
    if [[ -f "$project_path/package.json" ]]; then
        build_cmd=$(cd "$project_path" && node -e "
            const p = require('./package.json');
            const s = p.scripts || {};
            if (s['build:ci']) console.log('build:ci');
            else if (s['build']) console.log('build');
        " 2>/dev/null || true)
    fi

    if [[ -z "$build_cmd" ]]; then
        BASE_BUILD_STATUS="pass"  # No build command = nothing to check
        return 0
    fi

    log_info "Base build check: running $pm run $build_cmd in $project_path"
    local rc=0
    BASE_BUILD_OUTPUT=$(cd "$project_path" && timeout 300 "$pm" run "$build_cmd" 2>&1) || rc=$?

    if [[ $rc -eq 0 ]]; then
        BASE_BUILD_STATUS="pass"
        log_info "Base build check: PASS"
        return 0
    else
        BASE_BUILD_STATUS="fail"
        log_warn "Base build check: FAIL — main branch has build errors"
        return 1
    fi
}

# Attempt to fix the main branch build using an LLM agent.
# Commits the fix directly on main if successful.
# Resets BASE_BUILD_STATUS so the next check re-runs.
fix_base_build_with_llm() {
    local project_path="$1"

    # Guard: don't retry if both sonnet and opus already failed this session
    if [[ "$BASE_BUILD_FIX_ATTEMPTED" == "both" ]]; then
        log_info "Base build fix: both sonnet and opus failed this session — skipping"
        return 1
    fi

    log_info "Base build fix: attempting LLM-assisted fix on main branch"
    info "Main branch has build errors — attempting LLM fix..."

    # Detect build command for the prompt
    local pm="npm"
    [[ -f "$project_path/pnpm-lock.yaml" ]] && pm="pnpm"
    [[ -f "$project_path/yarn.lock" ]] && pm="yarn"
    [[ -f "$project_path/bun.lockb" || -f "$project_path/bun.lock" ]] && pm="bun"
    local build_cmd="build"
    if [[ -f "$project_path/package.json" ]]; then
        build_cmd=$(cd "$project_path" && node -e "
            const p = require('./package.json');
            const s = p.scripts || {};
            if (s['build:ci']) console.log('build:ci');
            else if (s['build']) console.log('build');
        " 2>/dev/null || echo "build")
    fi

    local fix_prompt
    fix_prompt=$(cat <<FIX_EOF
The main branch has build errors that are blocking all worktree builds.
Fix these TypeScript/build errors directly on the main branch.

Build command: $pm run $build_cmd
Build output (last 3000 chars):
${BASE_BUILD_OUTPUT: -3000}

Instructions:
1. Analyze the build errors above carefully
2. Fix the root cause (type errors, missing imports, missing @types packages, schema mismatches, etc.)
3. Run: $pm run $build_cmd — confirm it passes
4. Commit the fix with message: "fix: repair main branch build errors"

Do NOT create a worktree — fix directly in the current directory.
FIX_EOF
)

    # Try sonnet first, then escalate to opus if sonnet fails
    local model
    if [[ "$BASE_BUILD_FIX_ATTEMPTED" == "sonnet" ]]; then
        model="$(model_id opus)"
        log_info "Base build fix: sonnet failed previously, escalating to opus"
        info "Sonnet couldn't fix build — trying with Opus..."
    else
        model="$(model_id sonnet)"
    fi

    local fix_rc=0
    (cd "$project_path" && echo "$fix_prompt" | run_claude --model "$model" --max-turns 20) || fix_rc=$?

    if [[ $fix_rc -eq 0 ]]; then
        log_info "Base build fix: LLM fix attempted, re-checking build..."
        BASE_BUILD_STATUS=""  # Reset cache to re-check
        BASE_BUILD_OUTPUT=""
        if check_base_build "$project_path"; then
            log_info "Base build fix: SUCCESS — main branch now builds (model: $model)"
            info "Main branch build fixed successfully"
            orch_remember "LLM fixed main branch build errors (model: $model)" Learning "phase:build,scope:main"
            BASE_BUILD_FIX_ATTEMPTED="done"
            return 0
        fi
    fi

    # Mark which model we tried
    if [[ "$BASE_BUILD_FIX_ATTEMPTED" == "sonnet" ]]; then
        BASE_BUILD_FIX_ATTEMPTED="both"
        log_error "Base build fix: opus also failed — manual intervention needed"
    else
        BASE_BUILD_FIX_ATTEMPTED="sonnet"
        log_warn "Base build fix: sonnet failed — will try opus on next attempt"
        # Return 1 but allow retry with opus
    fi
    send_notification "wt-orchestrate" "Main branch build fix FAILED (tried: ${BASE_BUILD_FIX_ATTEMPTED}) — manual intervention needed" "critical"
    return 1
}

# Sync a worktree branch with main to pick up fixes that landed after the branch was created.
# Uses git merge (not rebase) to preserve commit history and avoid force-push issues.
# Returns 0 if sync succeeded (or was unnecessary), 1 if merge conflicts occurred.
sync_worktree_with_main() {
    local wt_path="$1"
    local change_name="$2"

    # Determine the main branch name
    local main_branch=""
    if git -C "$wt_path" show-ref --verify --quiet refs/heads/main 2>/dev/null; then
        main_branch="main"
    elif git -C "$wt_path" show-ref --verify --quiet refs/heads/master 2>/dev/null; then
        main_branch="master"
    else
        log_warn "Sync: could not find main/master branch for $change_name"
        return 1
    fi

    # Check if worktree is already up to date with main
    local wt_branch
    wt_branch=$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null)
    local main_head wt_merge_base
    main_head=$(git -C "$wt_path" rev-parse "$main_branch" 2>/dev/null)
    wt_merge_base=$(git -C "$wt_path" merge-base "$wt_branch" "$main_branch" 2>/dev/null)

    if [[ "$main_head" == "$wt_merge_base" ]]; then
        log_info "Sync: $change_name already up to date with $main_branch"
        return 0
    fi

    local behind_count
    behind_count=$(git -C "$wt_path" rev-list --count "$wt_merge_base..$main_head" 2>/dev/null || echo "?")
    log_info "Sync: $change_name is $behind_count commit(s) behind $main_branch — merging"

    # Merge main into the worktree branch
    local merge_rc=0
    local merge_output=""
    merge_output=$(git -C "$wt_path" merge "$main_branch" -m "Merge $main_branch into $wt_branch (auto-sync)" 2>&1) || merge_rc=$?

    if [[ $merge_rc -eq 0 ]]; then
        log_info "Sync: successfully merged $main_branch into $change_name"
        return 0
    fi

    # Try auto-resolving generated file conflicts (lock files, build artifacts)
    local conflicted_files
    conflicted_files=$(git -C "$wt_path" diff --name-only --diff-filter=U 2>/dev/null || true)

    if [[ -n "$conflicted_files" ]]; then
        # Check if all conflicts are in generated files
        local has_non_generated=false
        while IFS= read -r file; do
            [[ -z "$file" ]] && continue
            local basename
            basename=$(basename "$file")
            case "$basename" in
                *.tsbuildinfo|package-lock.json|yarn.lock|pnpm-lock.yaml) ;;
                *) has_non_generated=true; break ;;
            esac
        done <<< "$conflicted_files"

        if ! $has_non_generated; then
            # All conflicts in generated files — accept ours and continue
            while IFS= read -r file; do
                [[ -z "$file" ]] && continue
                git -C "$wt_path" checkout --ours "$file" 2>/dev/null
                git -C "$wt_path" add "$file" 2>/dev/null
            done <<< "$conflicted_files"
            git -C "$wt_path" commit --no-edit 2>/dev/null
            log_info "Sync: auto-resolved generated file conflicts for $change_name"
            return 0
        fi
    fi

    # Real conflicts — abort merge
    git -C "$wt_path" merge --abort 2>/dev/null || true
    log_warn "Sync: merge conflicts for $change_name — cannot auto-sync with $main_branch"
    return 1
}

# ─── Worktree Bootstrap ──────────────────────────────────────────────

# Bootstrap a worktree: copy missing .env files + install deps if needed.
# Safe to call on already-bootstrapped worktrees (idempotent).
bootstrap_worktree() {
    local project_path="$1"
    local wt_path="$2"

    [[ -d "$wt_path" ]] || return 0

    # Copy .env files
    local copied=0
    for envfile in .env .env.local .env.development .env.development.local; do
        if [[ -f "$project_path/$envfile" && ! -f "$wt_path/$envfile" ]]; then
            cp "$project_path/$envfile" "$wt_path/$envfile"
            copied=$((copied + 1))
        fi
    done
    [[ $copied -gt 0 ]] && log_info "Bootstrap: copied $copied env file(s) to $wt_path"

    # Install dependencies
    if [[ -f "$wt_path/package.json" && ! -d "$wt_path/node_modules" ]]; then
        local pm=""
        [[ -f "$wt_path/pnpm-lock.yaml" ]] && pm="pnpm"
        [[ -f "$wt_path/yarn.lock" ]] && pm="yarn"
        [[ -f "$wt_path/bun.lockb" || -f "$wt_path/bun.lock" ]] && pm="bun"
        [[ -f "$wt_path/package-lock.json" ]] && pm="npm"

        if [[ -n "$pm" ]] && command -v "$pm" &>/dev/null; then
            log_info "Bootstrap: installing deps with $pm in $wt_path"
            (cd "$wt_path" && "$pm" install --frozen-lockfile 2>/dev/null || "$pm" install 2>/dev/null) || \
                log_warn "Bootstrap: dep install failed in $wt_path (non-fatal)"
        fi
    fi
}

# ─── Context Pruning ─────────────────────────────────────────────────

# Remove orchestrator-level commands/skills from worktree .claude/ directory.
# Agent workers don't need orchestrate, sentinel, or manual commands.
# Preserves: .claude/rules/, .claude/skills/, CLAUDE.md, loop*.md
prune_worktree_context() {
    local wt_path="$1"
    [[ -d "$wt_path/.claude" ]] || return 0

    local pruned=0
    local cmd_dir="$wt_path/.claude/commands/wt"
    if [[ -d "$cmd_dir" ]]; then
        for pattern in orchestrate sentinel manual; do
            for f in "$cmd_dir"/${pattern}*.md; do
                [[ -f "$f" ]] || continue
                rm -f "$f"
                pruned=$((pruned + 1))
            done
        done
    fi

    [[ "$pruned" -gt 0 ]] && log_info "Pruned $pruned orchestrator command(s) from worktree"
    return 0
}

# ─── Model Routing ───────────────────────────────────────────────────

# Resolve effective model for a change: explicit > directive > heuristic
# Args: change_name, default_model (from directives)
resolve_change_model() {
    local change_name="$1"
    local default_model="${2:-opus}"

    # Doc-named changes can use sonnet (mechanical text work, no code)
    local is_doc_change=false
    if [[ "$change_name" == doc-* || "$change_name" == *-doc-* || "$change_name" == *-docs || "$change_name" == *-docs-* ]]; then
        is_doc_change=true
    fi

    # 1. Per-change explicit model from plan
    local explicit_model
    explicit_model=$(jq -r --arg n "$change_name" \
        '.changes[] | select(.name == $n) | .model // empty' "$STATE_FILENAME")
    if [[ -n "$explicit_model" && "$explicit_model" != "null" ]]; then
        # Guard: sonnet only allowed for doc-named changes
        # All code-writing changes MUST use opus regardless of what the planner suggested
        if [[ "$explicit_model" == "sonnet" && "$is_doc_change" == "false" ]]; then
            log_warn "Overriding planner model=sonnet → opus for code change '$change_name'"
            echo "opus"
        else
            echo "$explicit_model"
        fi
        return
    fi

    # 2. Directive default_model
    if [[ "$is_doc_change" == "true" ]]; then
        echo "sonnet"
        return
    fi

    echo "$default_model"
}

# ─── Dispatch ────────────────────────────────────────────────────────

dispatch_change() {
    local change_name="$1"
    local scope
    scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope' "$STATE_FILENAME")
    local roadmap_item
    roadmap_item=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .roadmap_item' "$STATE_FILENAME")

    log_info "Dispatching change: $change_name"
    info "Dispatching: $change_name"
    emit_event "DISPATCH" "$change_name" "{\"scope\":$(printf '%s' "$scope" | jq -Rs .)}"

    # Create worktree
    local project_path
    project_path=$(pwd)
    local wt_path
    wt_path="${project_path}-${change_name}"

    if [[ -d "$wt_path" ]]; then
        info "Worktree already exists: $wt_path"
    else
        wt-new "$change_name" --skip-open 2>/dev/null || {
            error "Failed to create worktree for $change_name"
            update_change_field "$change_name" "status" '"failed"'
            log_error "Failed to create worktree for $change_name"
            return 1
        }
    fi

    # Find actual worktree path
    wt_path=$(find_existing_worktree "$(pwd)" "$change_name" 2>/dev/null || echo "${project_path}-${change_name}")

    # Bootstrap existing worktrees that missed wt-new bootstrap
    bootstrap_worktree "$project_path" "$wt_path"

    # Prune orchestrator-level context from worktree (agent doesn't need to orchestrate itself)
    if [[ "${CONTEXT_PRUNING:-true}" == "true" ]]; then
        prune_worktree_context "$wt_path"
    fi

    # Recall change-specific memories for proposal enrichment
    local dispatch_memory=""
    dispatch_memory=$(orch_recall "$scope" 3 "" || true)
    dispatch_memory="${dispatch_memory:0:1000}"

    # Create change directory + proposal in worktree
    (
        cd "$wt_path" || exit 1

        # Initialize OpenSpec change if not exists
        if [[ ! -d "openspec/changes/$change_name" ]]; then
            local _opsx_err
            if ! _opsx_err=$(openspec new change "$change_name" 2>&1); then
                log_error "openspec new change failed for $change_name: $_opsx_err"
            fi
            if [[ ! -d "openspec/changes/$change_name" ]]; then
                log_error "openspec change directory not created for $change_name"
            fi
        fi

        # Pre-create proposal.md from scope
        local proposal_path="openspec/changes/$change_name/proposal.md"
        if [[ ! -f "$proposal_path" ]]; then
            cat > "$proposal_path" <<PROPOSAL_EOF
## Why

$roadmap_item

## What Changes

$scope

## Capabilities

### New Capabilities
- \`$change_name\`: $roadmap_item

### Modified Capabilities

## Impact

To be determined during design phase.
PROPOSAL_EOF
            # Append memory context if available
            if [[ -n "$dispatch_memory" ]]; then
                cat >> "$proposal_path" <<MEMORY_EOF

## Context from Memory

$dispatch_memory
MEMORY_EOF
            fi
            log_info "Pre-created proposal.md for $change_name"
        fi

        # Check artifact readiness — if tasks.md exists, agent can go straight to apply
        local tasks_path="openspec/changes/$change_name/tasks.md"
        if [[ -f "$tasks_path" ]]; then
            log_info "Artifacts ready for $change_name — starting apply"
        else
            log_info "No tasks.md for $change_name — first iteration will create artifacts"
        fi
    ) || {
        error "Failed to setup change in worktree"
        update_change_field "$change_name" "status" '"failed"'
        return 1
    }

    # Update state
    update_change_field "$change_name" "status" '"dispatched"'
    update_change_field "$change_name" "worktree_path" "\"$wt_path\""
    update_change_field "$change_name" "started_at" "\"$(date -Iseconds)\""

    # Start Ralph loop in worktree
    # wt-loop spawns a terminal process and returns, so we check loop-state.json
    local task_desc="Implement $change_name: ${scope:0:200}"
    local impl_model
    impl_model=$(resolve_change_model "$change_name" "$DEFAULT_IMPL_MODEL")

    # Token budget disabled — iteration limit (--max) provides the safety net.
    # See: docs/tanulsagok/wt-orchestration-tanulsagok.md B1 (budget restart cascade)
    local token_budget_flag=""

    log_info "Dispatch $change_name with model=$impl_model (default=$DEFAULT_IMPL_MODEL) budget=unlimited (iter limit: --max 30)"
    (
        cd "$wt_path" || exit 1
        wt-loop start "$task_desc" --max 30 --done openspec --label "$change_name" --model "$impl_model" --change "$change_name" $token_budget_flag
    ) &
    wait $! 2>/dev/null || true

    # Verify wt-loop actually started by checking for loop-state.json
    local loop_state="$wt_path/.claude/loop-state.json"
    local retries=0
    while [[ ! -f "$loop_state" && $retries -lt 10 ]]; do
        sleep 1
        retries=$((retries + 1))
    done

    if [[ ! -f "$loop_state" ]]; then
        error "wt-loop failed to start for $change_name (no loop-state.json after ${retries}s)"
        log_error "wt-loop failed to start for $change_name"
        emit_event "ERROR" "$change_name" '{"error":"wt-loop failed to start"}'
        update_change_field "$change_name" "status" '"failed"'
        return 1
    fi

    local terminal_pid
    terminal_pid=$(jq -r '.terminal_pid // empty' "$loop_state" 2>/dev/null)
    update_change_field "$change_name" "ralph_pid" "${terminal_pid:-0}"
    update_change_field "$change_name" "status" '"running"'
    log_info "Ralph started for $change_name in $wt_path (terminal PID ${terminal_pid:-unknown})"
}

# Resume changes that were running when the orchestrator was interrupted.
# Called on restart before dispatch_ready_changes() so stopped changes
# get picked up without manual intervention.
resume_stopped_changes() {
    local stopped_changes
    stopped_changes=$(jq -r '.changes[] | select(.status == "stopped") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        if [[ -n "$wt_path" && -d "$wt_path" ]]; then
            log_info "Resuming stopped change: $name"
            info "Resuming stopped change: $name"
            resume_change "$name" || true
        else
            log_info "Resetting stopped change $name to pending (worktree missing)"
            info "Resetting stopped change $name to pending (worktree missing)"
            update_change_field "$name" "status" '"pending"'
        fi
    done <<< "$stopped_changes"
}

dispatch_ready_changes() {
    local max_parallel="$1"

    local running
    running=$(count_changes_by_status "running")
    running=$((running + $(count_changes_by_status "dispatched")))

    # Get pending changes in topological order
    local order
    order=$(topological_sort "$PLAN_FILENAME" 2>/dev/null || true)

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        [[ "$running" -ge "$max_parallel" ]] && break

        local status
        status=$(get_change_status "$name")
        [[ "$status" != "pending" ]] && continue

        if deps_satisfied "$name"; then
            dispatch_change "$name"
            running=$((running + 1))
        fi
    done <<< "$order"
}

pause_change() {
    local change_name="$1"
    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")

    if [[ -z "$wt_path" ]]; then
        warn "No worktree found for $change_name"
        return 1
    fi

    local pid_file="$wt_path/.claude/ralph-terminal.pid"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill -TERM "$pid" 2>/dev/null || true
            info "Sent SIGTERM to Ralph (PID $pid) for $change_name"
            log_info "Paused $change_name (SIGTERM to PID $pid)"
        fi
    fi

    update_change_field "$change_name" "status" '"paused"'
}

resume_change() {
    local change_name="$1"
    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")

    if [[ -z "$wt_path" || ! -d "$wt_path" ]]; then
        error "Worktree not found for $change_name"
        return 1
    fi

    info "Resuming: $change_name"
    log_info "Resuming $change_name in $wt_path"

    # Snapshot cumulative tokens before new loop resets total_tokens to 0.
    # tokens_used already = tokens_used_prev + current_loop_tokens, so just carry it forward.
    local cumulative_tokens
    cumulative_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME")
    update_change_field "$change_name" "tokens_used_prev" "$cumulative_tokens"

    local scope
    scope=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .scope // empty' "$STATE_FILENAME")

    # Read retry_context from state (stored via --argjson, jq -r gives raw text directly)
    local retry_ctx
    retry_ctx=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .retry_context // empty' "$STATE_FILENAME")

    local task_desc
    local done_criteria="openspec"
    local max_iter=30
    if [[ -n "$retry_ctx" ]]; then
        task_desc="$retry_ctx"
        log_info "Resuming $change_name with retry context (${#retry_ctx} chars)"
        # Clear retry_context to prevent stale context on future resumes
        update_change_field "$change_name" "retry_context" "null"

        # Differentiate merge-conflict retry from build/test retry
        local is_merge_retry
        is_merge_retry=$(jq -r --arg n "$change_name" \
            '.changes[] | select(.name == $n) | .merge_rebase_pending // false' "$STATE_FILENAME")
        if [[ "$is_merge_retry" == "true" ]]; then
            # Merge retries: agent resolves conflicts, done when branch merges cleanly
            done_criteria="merge"
            max_iter=5
        else
            # Build/test fix retries: done when build passes
            done_criteria="build"
            max_iter=3
        fi
    else
        task_desc="Continue $change_name: ${scope:0:200}"
    fi
    local impl_model
    impl_model=$(resolve_change_model "$change_name" "$DEFAULT_IMPL_MODEL")
    log_info "Resume $change_name with model=$impl_model (done=$done_criteria, max=$max_iter)"
    (
        cd "$wt_path" || exit 1
        wt-loop start "$task_desc" --max "$max_iter" --done "$done_criteria" --label "$change_name" --model "$impl_model" --change "$change_name"
    ) &
    wait $! 2>/dev/null || true

    # Verify wt-loop started via loop-state.json
    local loop_state="$wt_path/.claude/loop-state.json"
    local retries=0
    while [[ ! -f "$loop_state" && $retries -lt 10 ]]; do
        sleep 1
        retries=$((retries + 1))
    done

    if [[ ! -f "$loop_state" ]]; then
        error "wt-loop failed to resume for $change_name"
        log_error "wt-loop failed to resume for $change_name"
        emit_event "ERROR" "$change_name" '{"error":"wt-loop failed to resume"}'
        update_change_field "$change_name" "status" '"failed"'
        return 1
    fi

    local terminal_pid
    terminal_pid=$(jq -r '.terminal_pid // empty' "$loop_state" 2>/dev/null)
    update_change_field "$change_name" "ralph_pid" "${terminal_pid:-0}"
    update_change_field "$change_name" "status" '"running"'
}

# Resume stalled changes after a cooldown period.
# Stalled changes get a 5-minute cooldown before resume attempt.
# This handles transient failures like API rate limits.
resume_stalled_changes() {
    local now
    now=$(date +%s)
    local stalled
    stalled=$(jq -r '.changes[] | select(.status == "stalled") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local stalled_at
        stalled_at=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .stalled_at // 0' "$STATE_FILENAME")
        local cooldown=$((now - stalled_at))
        if [[ "$cooldown" -ge 300 ]]; then
            log_info "Resuming stalled change $name after ${cooldown}s cooldown"
            resume_change "$name" || true
        fi
    done <<< "$stalled"
}

# Retry failed builds: give build failures a chance to self-repair
# before triggering a full replan cycle.
retry_failed_builds() {
    local max_retries="${1:-2}"
    local failed_builds
    failed_builds=$(jq -r '.changes[] | select(.status == "failed" and .build_result == "fail") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local gate_retry_count
        gate_retry_count=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .gate_retry_count // 0' "$STATE_FILENAME")
        if [[ "$gate_retry_count" -ge "$max_retries" ]]; then
            continue  # already exhausted retries
        fi
        gate_retry_count=$((gate_retry_count + 1))
        update_change_field "$name" "gate_retry_count" "$gate_retry_count"
        log_info "Retrying failed build for $name (attempt $gate_retry_count/$max_retries)"
        info "Retrying build failure: $name ($gate_retry_count/$max_retries)"

        # Set retry context with build output
        local build_output
        build_output=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .build_output // ""' "$STATE_FILENAME")
        local scope
        scope=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")
        local retry_prompt="Build failed. Fix the build error.\n\nBuild output:\n${build_output:0:2000}\n\nOriginal scope: $scope"
        update_change_field "$name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"
        update_change_field "$name" "status" '"pending"'
        resume_change "$name" || true
    done <<< "$failed_builds"
}

# ─── Command Handlers ────────────────────────────────────────────────

cmd_start() {
    # Auto-plan if no plan exists or CLI --spec/--brief differs from plan's input
    local need_plan=false
    if [[ ! -f "$PLAN_FILENAME" ]]; then
        need_plan=true
    elif [[ -n "$SPEC_OVERRIDE" || -n "$BRIEF_OVERRIDE" ]]; then
        # CLI spec/brief provided — check if it matches the existing plan
        local plan_input_path
        plan_input_path=$(jq -r '.input_path // ""' "$PLAN_FILENAME" 2>/dev/null)
        local cli_input=""
        [[ -n "$SPEC_OVERRIDE" ]] && cli_input="$SPEC_OVERRIDE"
        [[ -n "$BRIEF_OVERRIDE" ]] && cli_input="$BRIEF_OVERRIDE"
        # Normalize paths for comparison (resolve ./ prefix, etc.)
        local norm_plan norm_cli
        norm_plan=$(realpath -m "$plan_input_path" 2>/dev/null || echo "$plan_input_path")
        norm_cli=$(realpath -m "$cli_input" 2>/dev/null || echo "$cli_input")
        if [[ "$norm_plan" != "$norm_cli" ]]; then
            info "CLI input ($cli_input) differs from plan ($plan_input_path) — replanning"
            log_info "Input mismatch detected: CLI=$cli_input plan=$plan_input_path — auto-replanning"
            need_plan=true
        else
            # Same path — check if content changed since last plan
            local plan_hash current_hash
            plan_hash=$(jq -r '.input_hash // ""' "$PLAN_FILENAME" 2>/dev/null)
            current_hash=$(sha256sum "$cli_input" 2>/dev/null | cut -d' ' -f1)
            if [[ -n "$plan_hash" && -n "$current_hash" && "$plan_hash" != "$current_hash" ]]; then
                info "Spec content changed since last plan — replanning"
                log_info "Content hash mismatch: plan=$plan_hash current=$current_hash"
                need_plan=true
            fi
        fi
    fi

    if [[ "$need_plan" == true ]]; then
        # Clean slate: remove all previous plan/state artifacts
        local stale_files=("$PLAN_FILENAME" "$STATE_FILENAME" "$SUMMARY_FILENAME"
                           ".claude/orchestration-last-response.txt")
        for f in "${stale_files[@]}"; do
            if [[ -f "$f" ]]; then
                log_info "Removing stale file: $f"
                rm -f "$f"
            fi
        done
        info "Creating plan..."
        cmd_plan || return 1
    fi

    # Record start time for time-limit tracking
    ORCHESTRATOR_START_EPOCH=$(date +%s)

    if [[ -f "$STATE_FILENAME" ]]; then
        local current_status
        current_status=$(jq -r '.status' "$STATE_FILENAME")
        if [[ "$current_status" == "running" ]]; then
            warn "Orchestrator is already running. Use 'wt-orchestrate status' to check progress."
            return 1
        fi
        # Previous run completed — start fresh
        if [[ "$current_status" == "done" ]]; then
            log_info "Previous run completed (status=done) — starting fresh"
            rm -f "$STATE_FILENAME"
        fi
        # Resume from time_limit or stopped: continue where we left off
        if [[ -f "$STATE_FILENAME" ]] && [[ "$current_status" == "time_limit" || "$current_status" == "stopped" ]]; then
            info "Resuming from previous run (status: $current_status)"
            log_info "Resuming orchestration (was: $current_status)"
            update_state_field "status" '"running"'

            # Restore input path from plan
            if [[ -z "${INPUT_PATH:-}" || ! -f "${INPUT_PATH:-}" ]]; then
                INPUT_MODE=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
                INPUT_PATH=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
                if [[ -z "$INPUT_PATH" || ! -f "$INPUT_PATH" ]]; then
                    error "Cannot find input file from plan: $INPUT_PATH"
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

            # Retry merge queue immediately on resume (don't wait 30s)
            retry_merge_queue
            # Resume changes that were running when we were interrupted
            resume_stopped_changes
            # Dispatch any remaining pending changes
            dispatch_ready_changes "$max_parallel"
            monitor_loop "$directives"
            return 0
        fi
    fi

    info "Starting orchestration..."
    log_info "Orchestration started"

    # Restore input path from plan (so --spec is not needed again)
    if [[ -z "${INPUT_PATH:-}" || ! -f "${INPUT_PATH:-}" ]]; then
        INPUT_MODE=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
        INPUT_PATH=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
        if [[ -z "$INPUT_PATH" || ! -f "$INPUT_PATH" ]]; then
            error "Cannot find input file from plan: $INPUT_PATH"
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

    # Resume any stopped changes from a previous interrupted run
    resume_stopped_changes
    # Dispatch initial changes
    dispatch_ready_changes "$max_parallel"

    # Monitor loop
    monitor_loop "$directives"
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
        error "Usage: wt-orchestrate pause <change-name> | --all"
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
        error "Usage: wt-orchestrate resume <change-name> | --all"
        return 1
    fi
}

# ─── Monitor Loop ────────────────────────────────────────────────────

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
    local wd_max_tokens
    wd_max_tokens=$(echo "$directives" | jq -r '.max_tokens_per_change // empty')
    [[ -n "$wd_max_tokens" ]] && WATCHDOG_MAX_TOKENS_PER_CHANGE="$wd_max_tokens"

    # Apply context pruning directive to global
    CONTEXT_PRUNING=$(echo "$directives" | jq -r '.context_pruning // true')

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
            break
        fi

        # Check if we've been stopped externally
        local orch_status
        orch_status=$(jq -r '.status' "$STATE_FILENAME" 2>/dev/null || echo "unknown")
        if [[ "$orch_status" == "stopped" || "$orch_status" == "done" ]]; then
            break
        fi
        # Skip monitoring if paused or at checkpoint
        if [[ "$orch_status" == "paused" || "$orch_status" == "checkpoint" ]]; then
            continue
        fi

        # Poll each active change (running + verifying — verifying may have been interrupted mid-gate)
        local active_changes
        active_changes=$(jq -r '.changes[]? | select(.status == "running" or .status == "verifying") | .name' "$STATE_FILENAME" 2>/dev/null || true)
        while IFS= read -r name; do
            [[ -z "$name" ]] && continue
            poll_change "$name" "$test_command" "$merge_policy" \
                "$test_timeout" "$max_verify_retries" "$review_before_merge" "$review_model" \
                "$smoke_command" "$smoke_timeout" "$smoke_blocking" \
                "$smoke_fix_max_retries" "$smoke_fix_max_turns" \
                "$smoke_health_check_url" "$smoke_health_check_timeout"
            watchdog_check "$name"
        done <<< "$active_changes"

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

        # Watchdog heartbeat (sentinel monitors events.jsonl mtime)
        watchdog_heartbeat

        # Check if checkpoint needed
        local changes_since
        changes_since=$(jq -r '.changes_since_checkpoint // 0' "$STATE_FILENAME")
        if [[ "$changes_since" -ge "$checkpoint_every" ]]; then
            trigger_checkpoint "periodic"
            continue
        fi

        # Check if all done — only merged/done count as complete, not merge-blocked/failed
        local total_changes
        total_changes=$(jq '.changes | length' "$STATE_FILENAME")
        local truly_complete
        truly_complete=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$STATE_FILENAME")
        local merge_blocked_count
        merge_blocked_count=$(jq '[.changes[] | select(.status == "merge-blocked")] | length' "$STATE_FILENAME")
        local active_count
        active_count=$(jq '[.changes[] | select(.status == "running" or .status == "pending" or .status == "verifying" or .status == "stalled")] | length' "$STATE_FILENAME")

        if [[ "$active_count" -eq 0 && "$merge_blocked_count" -gt 0 ]]; then
            log_info "$truly_complete changes complete, $merge_blocked_count merge-blocked — not triggering replan"
        fi

        if [[ "$truly_complete" -ge "$total_changes" ]]; then
            log_info "All $total_changes changes complete"
            send_notification "wt-orchestrate" "All $total_changes changes complete!" "normal"

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
                log_info "Orchestration complete"
                break
            fi
        fi
    done
}
