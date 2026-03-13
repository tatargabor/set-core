#!/usr/bin/env bash
# lib/orchestration/dispatcher.sh — Change lifecycle: dispatch, resume, pause
# Dependencies: config.sh, utils.sh, state.sh, events.sh, builder.sh

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
                # Use git rm for tracked files to avoid "uncommitted changes" on merge
                if git -C "$wt_path" ls-files --error-unmatch "$f" &>/dev/null; then
                    git -C "$wt_path" rm -q "$f" 2>/dev/null || rm -f "$f"
                else
                    rm -f "$f"
                fi
                pruned=$((pruned + 1))
            done
        done
    fi

    if [[ "$pruned" -gt 0 ]]; then
        log_info "Pruned $pruned orchestrator command(s) from worktree"
        # Commit the pruning so worktree stays clean for merge
        git -C "$wt_path" commit -m "chore: prune orchestrator commands from worktree" --no-verify 2>/dev/null || true
    fi
    return 0
}

# ─── Model Routing ───────────────────────────────────────────────────

# Resolve effective model for a change.
# Three-tier priority: explicit per-change model > complexity-based routing > default_model
# Args: change_name, default_model, model_routing (off|complexity)
resolve_change_model() {
    local change_name="$1"
    local default_model="${2:-opus}"
    local model_routing="${3:-off}"

    # Doc-named changes can use sonnet (mechanical text work, no code)
    local is_doc_change=false
    if [[ "$change_name" == doc-* || "$change_name" == *-doc-* || "$change_name" == *-docs || "$change_name" == *-docs-* ]]; then
        is_doc_change=true
    fi

    # 1. Per-change explicit model from plan (highest priority)
    local explicit_model
    explicit_model=$(jq -r --arg n "$change_name" \
        '.changes[] | select(.name == $n) | .model // empty' "$STATE_FILENAME")
    if [[ -n "$explicit_model" && "$explicit_model" != "null" ]]; then
        # Guard: sonnet only allowed for doc-named changes
        if [[ "$explicit_model" == "sonnet" && "$is_doc_change" == "false" ]]; then
            log_warn "Overriding planner model=sonnet → opus for code change '$change_name'"
            echo "opus"
        else
            echo "$explicit_model"
        fi
        return
    fi

    # 2. Complexity-based routing (when model_routing=complexity)
    if [[ "$model_routing" == "complexity" ]]; then
        local complexity change_type
        complexity=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .complexity // "M"' "$STATE_FILENAME")
        change_type=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .change_type // "feature"' "$STATE_FILENAME")

        # S-complexity non-feature changes route to sonnet
        if [[ "$complexity" == "S" && "$change_type" != "feature" ]]; then
            log_info "Model routing: $change_name → sonnet (S-complexity, type=$change_type)"
            echo "sonnet"
            return
        fi
        # Doc changes always sonnet
        if [[ "$is_doc_change" == "true" ]]; then
            echo "sonnet"
            return
        fi
    fi

    # 3. Default model from directive
    if [[ "$is_doc_change" == "true" ]]; then
        echo "sonnet"
        return
    fi

    echo "$default_model"
}

# ─── Recovery ────────────────────────────────────────────────────────

recover_orphaned_changes() {
    local recovered=0
    local change_names
    change_names=$(jq -r '.changes[] | select(.status == "running" or .status == "verifying" or .status == "stalled") | .name' "$STATE_FILENAME" 2>/dev/null || true)

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue

        local wt_path ralph_pid
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        ralph_pid=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .ralph_pid // 0' "$STATE_FILENAME")

        # Skip if worktree still exists — existing resume logic handles it
        if [[ -n "$wt_path" && -d "$wt_path" ]]; then
            continue
        fi

        # Skip if Ralph PID is still alive — process is running somewhere
        if [[ -n "$ralph_pid" && "$ralph_pid" != "0" && "$ralph_pid" != "null" ]]; then
            if wt-orch-core process check-pid --pid "$ralph_pid" --expect-cmd "wt-loop" >/dev/null 2>&1; then
                log_warn "Change $name has live process PID $ralph_pid, skipping recovery"
                warn "Change $name has live process PID $ralph_pid, skipping recovery"
                continue
            fi
        fi

        # Orphaned: no worktree, no live PID — reset to pending
        log_info "Recovering orphaned change: $name (was $(get_change_status "$name"))"
        info "Recovering orphaned change: $name"
        update_change_field "$name" "status" '"pending"'
        update_change_field "$name" "worktree_path" 'null'
        update_change_field "$name" "ralph_pid" 'null'
        update_change_field "$name" "verify_retry_count" '0'
        update_change_field "$name" "failure_reason" 'null'
        emit_event "CHANGE_RECOVERED" "$name" "{\"reason\":\"orphaned_after_crash\"}"
        recovered=$((recovered + 1))
    done <<< "$change_names"

    if [[ "$recovered" -gt 0 ]]; then
        log_info "Recovered $recovered orphaned change(s)"
        info "Recovered $recovered orphaned change(s)"
    fi
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

    # Reset token counters for fresh dispatch.
    # On restart, stale tokens_used_prev from a previous run would inflate the
    # watchdog's budget calculation (tokens_used = tokens_used_prev + current).
    # resume_change() intentionally preserves cumulative tokens; only dispatch resets.
    update_change_field "$change_name" "tokens_used_prev" "0"
    update_change_field "$change_name" "tokens_used" "0"
    update_change_field "$change_name" "input_tokens" "0"
    update_change_field "$change_name" "output_tokens" "0"
    update_change_field "$change_name" "cache_read_tokens" "0"
    update_change_field "$change_name" "cache_create_tokens" "0"
    update_change_field "$change_name" "input_tokens_prev" "0"
    update_change_field "$change_name" "output_tokens_prev" "0"
    update_change_field "$change_name" "cache_read_tokens_prev" "0"
    update_change_field "$change_name" "cache_create_tokens_prev" "0"

    # Create worktree
    local project_path
    project_path=$(pwd)
    local wt_path
    wt_path="${project_path}-${change_name}"

    if [[ -d "$wt_path" ]]; then
        info "Worktree already exists: $wt_path"
        # Clean up stale loop state from previous run so wt-loop start
        # doesn't refuse with "Loop already running".
        local old_loop_state="$wt_path/.claude/loop-state.json"
        if [[ -f "$old_loop_state" ]]; then
            local old_pid
            old_pid=$(jq -r '.terminal_pid // 0' "$old_loop_state" 2>/dev/null)
            if [[ "$old_pid" -gt 0 ]] && ! kill -0 "$old_pid" 2>/dev/null; then
                log_info "Removing stale loop-state.json (PID $old_pid dead) for $change_name"
                rm -f "$old_loop_state"
            fi
        fi
    else
        # Clean up stale branch from previous failed run (worktree gone but branch remains)
        if git rev-parse --verify "change/$change_name" &>/dev/null; then
            log_info "Removing stale branch change/$change_name before worktree creation"
            git branch -D "change/$change_name" 2>/dev/null || true
        fi
        local wt_new_output
        wt_new_output=$(wt-new "$change_name" --skip-open 2>&1) || {
            error "Failed to create worktree for $change_name"
            log_error "wt-new output: $wt_new_output"
            update_change_field "$change_name" "status" '"failed"'
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
    dispatch_memory=$(orch_recall "$scope" 3 "phase:execution" || true)
    dispatch_memory="${dispatch_memory:0:1000}"

    # Build cross-cutting context from project-knowledge.yaml
    local pk_context=""
    local pk_file
    pk_file=$(find_project_knowledge_file 2>/dev/null || true)
    if [[ -n "$pk_file" && -f "$pk_file" ]] && command -v yq &>/dev/null; then
        # Check if change touches any known feature
        local feature_touches=""
        local feature_names
        feature_names=$(yq -r '.features | keys[]? // empty' "$pk_file" 2>/dev/null || true)
        if [[ -n "$feature_names" ]]; then
            while IFS= read -r fname; do
                [[ -z "$fname" ]] && continue
                # Match feature name against change scope
                if echo "$scope" | grep -qi "$fname"; then
                    local touches
                    touches=$(yq -r ".features.\"$fname\".touches[]? // empty" "$pk_file" 2>/dev/null || true)
                    local ref_impl
                    ref_impl=$(yq -r ".features.\"$fname\".reference_impl // false" "$pk_file" 2>/dev/null || true)
                    if [[ -n "$touches" ]]; then
                        feature_touches+="Feature '$fname' touches: $touches"$'\n'
                    fi
                    if [[ "$ref_impl" == "true" ]]; then
                        feature_touches+="Feature '$fname' has a reference implementation — follow existing patterns."$'\n'
                    fi
                fi
            done <<< "$feature_names"
        fi

        # Cross-cutting files context
        local cc_files
        cc_files=$(yq -r '.cross_cutting_files[]? | "- \(.path): \(.description // "")"' "$pk_file" 2>/dev/null || true)
        if [[ -n "$cc_files" || -n "$feature_touches" ]]; then
            pk_context="## Project Knowledge"$'\n'
            [[ -n "$feature_touches" ]] && pk_context+="$feature_touches"$'\n'
            [[ -n "$cc_files" ]] && pk_context+="Cross-cutting files (coordinate with other changes):"$'\n'"$cc_files"$'\n'
        fi
    fi

    # Build sibling status summary
    local sibling_context=""
    local siblings
    siblings=$(jq -r '.changes[] | select(.status == "running" or .status == "dispatched" or .status == "verifying") | "\(.name): \(.scope[:80])"' "$STATE_FILENAME" 2>/dev/null || true)
    if [[ -n "$siblings" ]]; then
        sibling_context="## Active Sibling Changes (avoid conflicts)"$'\n'"$siblings"$'\n'
    fi

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
            # Generate core proposal via Python template (replaces 3 heredocs)
            local _spec_ref=""
            [[ "${INPUT_MODE:-}" == "spec" && -n "${INPUT_PATH:-}" ]] && _spec_ref="$INPUT_PATH"
            jq -n \
                --arg change_name "$change_name" \
                --arg scope "$scope" \
                --arg roadmap_item "$roadmap_item" \
                --arg memory_ctx "${dispatch_memory:-}" \
                --arg spec_ref "$_spec_ref" \
                '{change_name: $change_name, scope: $scope, roadmap_item: $roadmap_item, memory_ctx: $memory_ctx, spec_ref: $spec_ref}' \
            | wt-orch-core template proposal --input-file - > "$proposal_path"

            # Append additional context sections (simple appends, no heredoc risk)
            if [[ -n "$pk_context" ]]; then
                echo "" >> "$proposal_path"
                echo "$pk_context" >> "$proposal_path"
            fi
            if [[ -n "$sibling_context" ]]; then
                echo "" >> "$proposal_path"
                echo "$sibling_context" >> "$proposal_path"
            fi

            # Design reference: if planner provided a design_ref, append to proposal
            local design_ref
            design_ref=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .design_ref // empty' "$STATE_FILENAME" 2>/dev/null || true)
            if [[ -n "$design_ref" ]]; then
                echo "" >> "$proposal_path"
                echo "## Design Reference" >> "$proposal_path"
                echo "Query the design tool for this frame/page: \`$design_ref\`" >> "$proposal_path"
            fi

            # Digest mode: add spec context references and requirement IDs to proposal
            if [[ "${INPUT_MODE:-}" == "digest" ]]; then
                local digest_dir="$project_path/$DIGEST_DIR"

                # Add Source Specifications section (spec files copied to worktree)
                local spec_files_list
                spec_files_list=$(jq -r --arg n "$change_name" \
                    '.changes[] | select(.name == $n) | .spec_files[]? // empty' "$STATE_FILENAME" 2>/dev/null || true)
                if [[ -n "$spec_files_list" ]]; then
                    echo "" >> "$proposal_path"
                    echo "## Source Specifications" >> "$proposal_path"
                    echo "Read these for detailed requirements:" >> "$proposal_path"
                    while IFS= read -r sf; do
                        [[ -z "$sf" ]] && continue
                        echo "- \`.claude/spec-context/$sf\`" >> "$proposal_path"
                    done <<< "$spec_files_list"
                fi

                # Add Requirements section
                local change_reqs
                change_reqs=$(jq -r --arg n "$change_name" \
                    '.changes[] | select(.name == $n) | .requirements[]? // empty' "$STATE_FILENAME" 2>/dev/null || true)
                if [[ -n "$change_reqs" && -f "$digest_dir/requirements.json" ]]; then
                    echo "" >> "$proposal_path"
                    echo "## Requirements" >> "$proposal_path"
                    echo "This change covers:" >> "$proposal_path"
                    while IFS= read -r rid; do
                        [[ -z "$rid" ]] && continue
                        local rtitle rbrief
                        rtitle=$(jq -r --arg id "$rid" '.requirements[] | select(.id == $id) | .title // ""' "$digest_dir/requirements.json" 2>/dev/null || true)
                        rbrief=$(jq -r --arg id "$rid" '.requirements[] | select(.id == $id) | .brief // ""' "$digest_dir/requirements.json" 2>/dev/null || true)
                        echo "- $rid: $rtitle — $rbrief" >> "$proposal_path"
                    done <<< "$change_reqs"
                fi

                # Add Cross-Cutting Requirements section
                local also_affects
                also_affects=$(jq -r --arg n "$change_name" \
                    '.changes[] | select(.name == $n) | .also_affects_reqs[]? // empty' "$STATE_FILENAME" 2>/dev/null || true)
                if [[ -n "$also_affects" && -f "$digest_dir/requirements.json" ]]; then
                    echo "" >> "$proposal_path"
                    echo "## Cross-Cutting Requirements" >> "$proposal_path"
                    echo "These requirements are owned by other changes — incorporate their constraints, do not re-implement from scratch:" >> "$proposal_path"
                    while IFS= read -r rid; do
                        [[ -z "$rid" ]] && continue
                        local rtitle rbrief
                        rtitle=$(jq -r --arg id "$rid" '.requirements[] | select(.id == $id) | .title // ""' "$digest_dir/requirements.json" 2>/dev/null || true)
                        rbrief=$(jq -r --arg id "$rid" '.requirements[] | select(.id == $id) | .brief // ""' "$digest_dir/requirements.json" 2>/dev/null || true)
                        echo "- $rid: $rtitle — $rbrief" >> "$proposal_path"
                    done <<< "$also_affects"
                fi
            fi

            log_info "Pre-created proposal.md for $change_name"
        fi

        # Digest mode: copy spec files to worktree .claude/spec-context/
        if [[ "${INPUT_MODE:-}" == "digest" ]]; then
            local digest_dir="$project_path/$DIGEST_DIR"
            if [[ -f "$digest_dir/index.json" ]]; then
                local spec_base_dir
                spec_base_dir=$(jq -r '.spec_base_dir' "$digest_dir/index.json")

                # Copy change-specific spec files
                local spec_files_json
                spec_files_json=$(jq -r --arg n "$change_name" \
                    '.changes[] | select(.name == $n) | .spec_files[]? // empty' "$STATE_FILENAME" 2>/dev/null || true)
                if [[ -n "$spec_files_json" ]]; then
                    mkdir -p ".claude/spec-context"
                    while IFS= read -r sf; do
                        [[ -z "$sf" ]] && continue
                        local src_file="$spec_base_dir/$sf"
                        if [[ -f "$src_file" ]]; then
                            local target_dir=".claude/spec-context/$(dirname "$sf")"
                            mkdir -p "$target_dir"
                            cp "$src_file" "$target_dir/"
                        else
                            log_warn "Spec file not found: $src_file"
                        fi
                    done <<< "$spec_files_json"
                fi

                # Copy conventions.json and data-definitions.md to every worktree
                if [[ -f "$digest_dir/conventions.json" ]]; then
                    mkdir -p ".claude/spec-context"
                    cp "$digest_dir/conventions.json" ".claude/spec-context/"
                fi
                if [[ -f "$digest_dir/data-definitions.md" ]]; then
                    mkdir -p ".claude/spec-context"
                    cp "$digest_dir/data-definitions.md" ".claude/spec-context/"
                fi

                # Add .claude/spec-context/ to .gitignore
                if [[ -f ".gitignore" ]]; then
                    if ! grep -qxF '.claude/spec-context/' ".gitignore" 2>/dev/null; then
                        echo '.claude/spec-context/' >> ".gitignore"
                    fi
                else
                    echo '.claude/spec-context/' > ".gitignore"
                fi
            fi
        fi

        # Inject retry_context into proposal for redispatched changes
        local retry_ctx
        retry_ctx=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .retry_context // empty' "$STATE_FILENAME")
        if [[ -n "$retry_ctx" && "$retry_ctx" != "null" ]]; then
            local proposal_path="openspec/changes/$change_name/proposal.md"
            if [[ -f "$proposal_path" ]]; then
                printf '\n%s\n' "$retry_ctx" >> "$proposal_path"
                log_info "Injected retry_context into proposal for $change_name"
            fi
            # Clear retry_context after injection
            update_change_field "$change_name" "retry_context" "null"
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

    # Update coverage status → dispatched
    update_coverage_status "$change_name" "dispatched" 2>/dev/null || true

    # Pre-dispatch hook
    if ! run_hook "pre_dispatch" "$change_name" "dispatched" "$wt_path"; then
        log_warn "pre_dispatch hook blocked $change_name"
        update_change_field "$change_name" "status" '"pending"'
        return 1
    fi

    # Dispatch via backend (default: wt-loop)
    local impl_model
    impl_model=$(resolve_change_model "$change_name" "$DEFAULT_IMPL_MODEL" "${MODEL_ROUTING:-off}")
    dispatch_via_wt_loop "$change_name" "$impl_model" "$wt_path" "$scope"
}

# Dispatch backend: wt-loop (default)
# Interface: receives change name, model, worktree path, scope; starts agent, sets PID + status
dispatch_via_wt_loop() {
    local change_name="$1"
    local impl_model="$2"
    local wt_path="$3"
    local scope="$4"

    local task_desc="Implement $change_name: ${scope:0:200}"

    # Token budget disabled — iteration limit (--max) provides the safety net.
    local token_budget_flag=""

    # Team mode flag (from config directive)
    local team_flag=""
    if [[ "${TEAM_MODE:-false}" == "true" ]]; then
        team_flag="--team"
    fi

    log_info "Dispatch $change_name with model=$impl_model (default=$DEFAULT_IMPL_MODEL) budget=unlimited (iter limit: --max 30) team=${TEAM_MODE:-false}"

    (
        cd "$wt_path" || exit 1
        wt-loop start "$task_desc" --max 30 --done openspec --label "$change_name" --model "$impl_model" --change "$change_name" $token_budget_flag $team_flag
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

    # Update coverage status → running
    update_coverage_status "$change_name" "running" 2>/dev/null || true
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

    # Get pending changes in topological order.
    # Use STATE_FILENAME (not PLAN_FILENAME) because after replan the state
    # carries forward changes from previous cycles that may not be in the
    # current plan file.  topological_sort only needs {name, depends_on}.
    local order
    order=$(topological_sort "$STATE_FILENAME" 2>/dev/null || true)

    # Collect ready-to-dispatch changes, then sort by complexity (L first)
    local ready_names=()
    while IFS= read -r name; do
        [[ -z "$name" ]] && continue

        local status
        status=$(get_change_status "$name")
        [[ "$status" != "pending" ]] && continue

        if deps_satisfied "$name"; then
            ready_names+=("$name")
        fi
    done <<< "$order"

    # Sort ready changes: L > M > S (larger first to reduce tail latency)
    if [[ ${#ready_names[@]} -gt 1 ]]; then
        local sorted_names=()
        for priority in L M S; do
            for name in "${ready_names[@]}"; do
                local complexity
                complexity=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .complexity // "M"' "$STATE_FILENAME" 2>/dev/null)
                if [[ "$complexity" == "$priority" ]]; then
                    sorted_names+=("$name")
                fi
            done
        done
        ready_names=("${sorted_names[@]}")
    fi

    # Dispatch in priority order
    for name in "${ready_names[@]}"; do
        [[ "$running" -ge "$max_parallel" ]] && break
        dispatch_change "$name"
        running=$((running + 1))
    done
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
        if wt-orch-core process check-pid --pid "$pid" --expect-cmd "wt-loop" >/dev/null 2>&1; then
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

    # Store progress baseline for watchdog: only evaluate iterations after this point
    local loop_state_file="$wt_path/.claude/loop-state.json"
    if [[ -f "$loop_state_file" ]]; then
        local iter_count
        iter_count=$(jq '[.iterations // [] | length] | .[0]' "$loop_state_file" 2>/dev/null || echo 0)
        safe_jq_update "$STATE_FILENAME" --arg n "$change_name" --argjson b "$iter_count" \
            '(.changes[] | select(.name == $n) | .watchdog.progress_baseline) = $b'
        log_info "Set watchdog progress_baseline=$iter_count for $change_name"
    fi

    # Snapshot cumulative tokens before new loop resets total_tokens to 0.
    # tokens_used already = tokens_used_prev + current_loop_tokens, so just carry it forward.
    local cumulative_tokens
    cumulative_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME")
    update_change_field "$change_name" "tokens_used_prev" "$cumulative_tokens"
    # Snapshot per-type tokens for retry accumulation
    local cum_in cum_out cum_cr cum_cc
    cum_in=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .input_tokens // 0' "$STATE_FILENAME")
    cum_out=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .output_tokens // 0' "$STATE_FILENAME")
    cum_cr=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .cache_read_tokens // 0' "$STATE_FILENAME")
    cum_cc=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .cache_create_tokens // 0' "$STATE_FILENAME")
    update_change_field "$change_name" "input_tokens_prev" "$cum_in"
    update_change_field "$change_name" "output_tokens_prev" "$cum_out"
    update_change_field "$change_name" "cache_read_tokens_prev" "$cum_cr"
    update_change_field "$change_name" "cache_create_tokens_prev" "$cum_cc"

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
    impl_model=$(resolve_change_model "$change_name" "$DEFAULT_IMPL_MODEL" "${MODEL_ROUTING:-off}")
    # Team mode flag (from config directive)
    local team_flag=""
    if [[ "${TEAM_MODE:-false}" == "true" ]]; then
        team_flag="--team"
    fi
    log_info "Resume $change_name with model=$impl_model (done=$done_criteria, max=$max_iter) team=${TEAM_MODE:-false}"
    (
        cd "$wt_path" || exit 1
        wt-loop start "$task_desc" --max "$max_iter" --done "$done_criteria" --label "$change_name" --model "$impl_model" --change "$change_name" $team_flag
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

# Redispatch a stuck change to a fresh worktree.
# Kills Ralph, salvages partial work, builds retry_context, cleans up worktree,
# resets watchdog state, sets status to pending for natural re-dispatch.
redispatch_change() {
    local change_name="$1"
    local failure_pattern="${2:-stuck}"  # spinning|stuck|timeout

    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    local tokens_used
    tokens_used=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME")
    local redispatch_count
    redispatch_count=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .redispatch_count // 0' "$STATE_FILENAME")

    log_info "Redispatching $change_name (attempt $((redispatch_count + 1))/${MAX_REDISPATCH:-2}, pattern=$failure_pattern)"

    # 1. Kill Ralph PID (identity-verified safe kill)
    local ralph_pid
    ralph_pid=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .ralph_pid // 0' "$STATE_FILENAME")
    if [[ "$ralph_pid" -gt 0 ]]; then
        local kill_result
        kill_result=$(wt-orch-core process safe-kill --pid "$ralph_pid" --expect-cmd "wt-loop" --timeout 5 2>/dev/null) || true
        log_info "Redispatch: safe-kill PID $ralph_pid for $change_name: $kill_result"
    fi

    # 2. Salvage partial work (captures diff + file list in state)
    _watchdog_salvage_partial_work "$change_name"

    # 3. Build retry_context from failure info
    local partial_files
    partial_files=$(jq -r --arg n "$change_name" \
        '.changes[] | select(.name == $n) | .partial_diff_files // [] | join(", ")' "$STATE_FILENAME" 2>/dev/null || true)
    local iter_count=0
    if [[ -n "$wt_path" && -f "$wt_path/.claude/loop-state.json" ]]; then
        iter_count=$(jq '[.iterations // [] | length] | .[0]' "$wt_path/.claude/loop-state.json" 2>/dev/null || echo 0)
    fi

    local retry_prompt
    retry_prompt="## Previous Attempt Failed (redispatch ${redispatch_count}/$((redispatch_count + 1)))

Failure pattern: $failure_pattern
Iterations completed: $iter_count
Tokens used: $tokens_used

Files modified in failed attempt: $partial_files

Start fresh — do not repeat the same approach that led to $failure_pattern."

    update_change_field "$change_name" "retry_context" "$(printf '%s' "$retry_prompt" | jq -Rs .)"

    # 4. Increment redispatch_count
    local new_count=$((redispatch_count + 1))
    update_change_field "$change_name" "redispatch_count" "$new_count"

    # 5. Emit event
    emit_event "WATCHDOG_REDISPATCH" "$change_name" \
        "{\"redispatch_count\":$new_count,\"failure_pattern\":\"$failure_pattern\",\"tokens_used\":$tokens_used,\"iterations\":$iter_count}"

    # 6. Clean up old worktree
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        local branch_name
        branch_name=$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null || true)
        git worktree remove --force "$wt_path" 2>/dev/null || {
            log_warn "Redispatch: git worktree remove failed for $wt_path, trying rm"
            rm -rf "$wt_path"
        }
        if [[ -n "$branch_name" && "$branch_name" != "HEAD" ]]; then
            git branch -D "$branch_name" 2>/dev/null || true
        fi
        log_info "Redispatch: cleaned up worktree $wt_path"
    fi

    # 7. Reset watchdog sub-object
    safe_jq_update "$STATE_FILENAME" --arg n "$change_name" \
        '(.changes[] | select(.name == $n) | .watchdog) = {
            last_activity_epoch: (now | floor),
            action_hash_ring: [],
            consecutive_same_hash: 0,
            escalation_level: 0
        }'

    # 8. Clear worktree-specific fields and set status to pending
    update_change_field "$change_name" "worktree_path" "null"
    update_change_field "$change_name" "ralph_pid" "null"
    update_change_field "$change_name" "status" '"pending"'

    send_notification "wt-orchestrate" \
        "Redispatching '$change_name' ($failure_pattern, attempt $new_count/${MAX_REDISPATCH:-2})" "normal"
    log_info "Redispatch complete for $change_name — status set to pending"
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
    # In automated mode, auto-defer untriaged ambiguities instead of pausing
    export TRIAGE_AUTO_DEFER=true

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
        # Resolve cli_input to absolute path using the same logic as find_input():
        # short names like "v12" → wt/orchestration/specs/v12.md, relative paths → absolute
        local resolved_cli="$cli_input"
        if [[ -n "$SPEC_OVERRIDE" ]]; then
            if [[ -d "$cli_input" ]]; then
                # Directory spec (digest mode)
                resolved_cli="$(cd "$cli_input" && pwd)"
            elif [[ -f "$cli_input" ]]; then
                resolved_cli="$(cd "$(dirname "$cli_input")" && pwd)/$(basename "$cli_input")"
            else
                # Try short-name resolution: wt/orchestration/specs/<name>.md
                local wt_spec="wt/orchestration/specs/${cli_input}.md"
                local wt_spec_sub="wt/orchestration/specs/${cli_input}"
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

        # Plan approval gate: if directive set, wait for user to approve
        local directives_for_gate
        directives_for_gate=$(parse_directives "$INPUT_PATH")
        local need_approval
        need_approval=$(echo "$directives_for_gate" | jq -r '.plan_approval // false')
        if [[ "$need_approval" == "true" ]]; then
            info "Plan generated. Review with 'wt-orchestrate plan --show'"
            info "Approve with 'wt-orchestrate approve' to begin dispatch."
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
                if wt-orch-core process check-pid --pid "$pid" --expect-cmd "wt-loop" >/dev/null 2>&1; then
                    has_live_pid=true
                    break
                fi
            done <<< "$running_pids"
            if [[ "$has_live_pid" == true ]]; then
                warn "Orchestrator is already running. Use 'wt-orchestrate status' to check progress."
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
            info "Plan is pending approval. Review with 'wt-orchestrate plan --show'"
            info "Approve with 'wt-orchestrate approve' to begin dispatch."
            return 0
        fi
        # Resume from time_limit or stopped: continue where we left off
        if [[ -f "$STATE_FILENAME" ]] && [[ "$current_status" == "time_limit" || "$current_status" == "stopped" ]]; then
            info "Resuming from previous run (status: $current_status)"
            log_info "Resuming orchestration (was: $current_status)"
            update_state_field "status" '"running"'

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

            # Recover orphaned changes (running/verifying with no worktree/PID)
            recover_orphaned_changes
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

