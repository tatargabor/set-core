#!/usr/bin/env bash
# set-loop task detection: find tasks, check completion, manual tasks, done criteria
# Dependencies: lib/loop/state.sh must be sourced first

# Find tasks.md generically in a worktree (no openspec-specific paths)
find_tasks_file() {
    local wt_path="$1"

    # Prefer worktree root
    if [[ -f "$wt_path/tasks.md" ]]; then
        echo "$wt_path/tasks.md"
        return
    fi

    # Fallback: search in subdirectories (maxdepth 4), excluding archive/node_modules
    # Depth 4 needed for openspec/changes/<name>/tasks.md
    local found
    found=$(find "$wt_path" -maxdepth 4 -name "tasks.md" -type f \
        ! -path "*/archive/*" ! -path "*/node_modules/*" 2>/dev/null | head -1)
    if [[ -n "$found" ]]; then
        echo "$found"
        return
    fi

    # Not found
    return 1
}

# Count manual/human tasks ([?] pattern) in tasks.md
count_manual_tasks() {
    local wt_path="$1"

    local tasks_file
    tasks_file=$(find_tasks_file "$wt_path")
    [[ -z "$tasks_file" ]] && echo 0 && return

    local count
    count=$(grep -cE '^\s*-\s*\[\?\]' "$tasks_file" 2>/dev/null || true)
    count=${count//[^0-9]/}
    echo "${count:-0}"
}

# Parse manual tasks into JSON array: [{id, description, type, input_key}]
parse_manual_tasks() {
    local wt_path="$1"

    local tasks_file
    tasks_file=$(find_tasks_file "$wt_path")
    [[ -z "$tasks_file" ]] && echo "[]" && return

    local result="["
    local first=true

    while IFS= read -r line; do
        # Extract task id (e.g. "3.3") and rest of the line
        local task_id="" description="" task_type="confirm" input_key=""

        # Match: - [?] 3.3 Description [input:KEY] or [confirm]
        if [[ "$line" =~ ^[[:space:]]*-[[:space:]]*\[\?\][[:space:]]+([0-9]+\.[0-9]+)[[:space:]]+(.*) ]]; then
            task_id="${BASH_REMATCH[1]}"
            local rest="${BASH_REMATCH[2]}"

            # Extract type annotation if present
            if [[ "$rest" =~ \[input:([^\]]+)\] ]]; then
                task_type="input"
                input_key="${BASH_REMATCH[1]}"
                description="${rest% \[input:*}"
            elif [[ "$rest" =~ \[confirm\] ]]; then
                task_type="confirm"
                description="${rest% \[confirm\]}"
            else
                description="$rest"
            fi

            $first || result+=","
            first=false
            result+=$(printf '{"id":"%s","description":%s,"type":"%s","input_key":"%s"}' \
                "$task_id" "$(echo "$description" | jq -Rs .)" "$task_type" "$input_key")
        fi
    done < <(grep -E '^\s*-\s*\[\?\]' "$tasks_file" 2>/dev/null)

    result+="]"
    echo "$result"
}

# Check if tasks.md is complete (all auto-tasks checked)
check_tasks_done() {
    local wt_path="$1"

    # Find tasks.md generically
    local tasks_file
    tasks_file=$(find_tasks_file "$wt_path")

    if [[ -z "$tasks_file" ]]; then
        warn "No tasks.md found in $wt_path"
        return 1
    fi

    # Count incomplete auto-tasks (- [ ] pattern only)
    # Note: [?] manual tasks are NOT counted here — they are handled
    # separately by the waiting:human detection. The regex \[\s*\] matches
    # only whitespace inside brackets, so [?] is naturally excluded.
    local count
    count=$(grep -cE '^\s*-\s*\[\s*\]' "$tasks_file" 2>/dev/null || true)
    count=${count//[^0-9]/}  # Strip any non-digit characters
    count=${count:-0}

    if [[ "$count" -eq 0 ]]; then
        return 0  # All auto-tasks done
    else
        return 1  # Not done
    fi
}

# Generate a minimal fallback tasks.md when ff exhausted (no tasks.md created by opsx:ff).
# Reads proposal.md (and design.md if present) to give the agent enough context.
# Returns 0 if tasks.md was created, 1 if insufficient context (no proposal.md).
generate_fallback_tasks() {
    local wt_path="$1"
    local change_name="$2"
    local change_dir="$wt_path/openspec/changes/$change_name"

    # Need at least proposal.md to generate meaningful tasks
    if [[ ! -f "$change_dir/proposal.md" ]]; then
        return 1
    fi

    local tasks_file="$change_dir/tasks.md"

    # Don't overwrite existing tasks.md
    if [[ -f "$tasks_file" ]]; then
        return 0
    fi

    # Read scope from proposal
    local scope
    scope=$(head -20 "$change_dir/proposal.md" 2>/dev/null | tail -15)

    local context_note="proposal.md"
    if [[ -f "$change_dir/design.md" ]]; then
        context_note="proposal.md and design.md"
    fi

    cat > "$tasks_file" <<FALLBACK_EOF
# Tasks

- [ ] Implement the change as described in $context_note. Read the artifacts in openspec/changes/$change_name/ for full scope and design details.
FALLBACK_EOF

    warn "Generated fallback tasks.md from proposal (ff exhausted)"
    return 0
}

# Check done criteria
check_done() {
    local wt_path="$1"
    local criteria="$2"
    local target_change="${3:-}"

    case "$criteria" in
        tasks)
            check_tasks_done "$wt_path"
            ;;
        openspec)
            # When --change is set, only check that specific change
            # When --change is not set, scan all changes (existing behavior)
            local action
            action=$(detect_next_change_action "$wt_path" "$target_change")
            [[ "$action" == "done" ]]
            ;;
        manual)
            # Check if user marked done in state file
            local state_file
            state_file=$(get_loop_state_file "$wt_path")
            local manual_done
            manual_done=$(jq -r '.manual_done // false' "$state_file" 2>/dev/null)
            [[ "$manual_done" == "true" ]]
            ;;
        build)
            # Build command passes = done
            local pm="npm"
            [[ -f "$wt_path/pnpm-lock.yaml" ]] && pm="pnpm"
            [[ -f "$wt_path/yarn.lock" ]] && pm="yarn"
            [[ -f "$wt_path/bun.lockb" || -f "$wt_path/bun.lock" ]] && pm="bun"
            local build_cmd=""
            if [[ -f "$wt_path/package.json" ]]; then
                build_cmd=$(cd "$wt_path" && node -e "
                    const p = require('./package.json');
                    const s = p.scripts || {};
                    if (s['build:ci']) console.log('build:ci');
                    else if (s['build']) console.log('build');
                " 2>/dev/null || true)
            fi
            if [[ -n "$build_cmd" ]]; then
                (cd "$wt_path" && timeout 300 "$pm" run "$build_cmd" >/dev/null 2>&1)
            else
                return 0  # No build command = pass
            fi
            ;;
        test)
            # Test command passes = done
            # Read test_command from loop state (set by --test-command flag)
            local state_file
            state_file=$(get_loop_state_file "$wt_path")
            local test_cmd
            test_cmd=$(jq -r '.test_command // empty' "$state_file" 2>/dev/null)
            if [[ -z "$test_cmd" ]]; then
                # No test command configured — fall back to build check
                local pm="npm"
                [[ -f "$wt_path/pnpm-lock.yaml" ]] && pm="pnpm"
                [[ -f "$wt_path/yarn.lock" ]] && pm="yarn"
                [[ -f "$wt_path/bun.lockb" || -f "$wt_path/bun.lock" ]] && pm="bun"
                if [[ -f "$wt_path/package.json" ]]; then
                    local build_cmd
                    build_cmd=$(cd "$wt_path" && node -e "
                        const p = require('./package.json');
                        const s = p.scripts || {};
                        if (s['build:ci']) console.log('build:ci');
                        else if (s['build']) console.log('build');
                    " 2>/dev/null || true)
                    if [[ -n "$build_cmd" ]]; then
                        (cd "$wt_path" && timeout 300 "$pm" run "$build_cmd" >/dev/null 2>&1)
                    else
                        return 0
                    fi
                else
                    return 0  # No package.json, no test — pass
                fi
            else
                (cd "$wt_path" && timeout 300 bash -c "$test_cmd" >/dev/null 2>&1)
            fi
            ;;
        merge)
            # Branch merges cleanly with main = done
            local main_ref
            main_ref=$(git -C "$wt_path" symbolic-ref refs/remotes/origin/HEAD 2>/dev/null \
                | sed 's@^refs/remotes/origin/@@' || echo "main")
            git -C "$wt_path" fetch origin "$main_ref" 2>/dev/null || true
            local cur_branch
            cur_branch=$(git -C "$wt_path" rev-parse --abbrev-ref HEAD 2>/dev/null)
            local mb
            mb=$(git -C "$wt_path" merge-base "$cur_branch" "origin/$main_ref" 2>/dev/null || true)
            if [[ -n "$mb" ]]; then
                ! git -C "$wt_path" merge-tree "$mb" "origin/$main_ref" "$cur_branch" 2>/dev/null | grep -q "^<<<<<<<"
            else
                return 1
            fi
            ;;
        *)
            warn "Unknown done criteria: $criteria"
            return 1
            ;;
    esac
}

# Get commits since last iteration
get_new_commits() {
    local wt_path="$1"
    local since="${2:-}"

    cd "$wt_path" || return

    if [[ -n "$since" ]]; then
        git log --since="$since" --format='%h' 2>/dev/null | jq -R . | jq -s .
    else
        echo "[]"
    fi
}
