#!/usr/bin/env bash
# set-loop prompt building: detect next change action, build Claude prompts
# Dependencies: lib/loop/state.sh and lib/loop/tasks.sh must be sourced first

# Detect the next OpenSpec change action needed.
# Args: $1=wt_path, $2=target_change (optional — if set, only inspect that change)
# Returns: "ff:<change-name>" or "apply:<change-name>" or "done" or "none"
detect_next_change_action() {
    local wt_path="$1"
    local target_change="${2:-}"

    # If a specific change is targeted, only inspect that one
    if [[ -n "$target_change" ]]; then
        local change_dir="$wt_path/openspec/changes/$target_change"
        local tasks_file="$change_dir/tasks.md"

        if [[ ! -d "$change_dir" ]]; then
            # Check if change was archived (moved to archive/ with date prefix)
            local archived
            archived=$(find "$wt_path/openspec/changes/archive" -maxdepth 1 -type d -name "*-$target_change" 2>/dev/null | head -1)
            if [[ -n "$archived" ]]; then
                echo "done"
            else
                echo "none"
            fi
            return
        fi

        # Does tasks.md exist? (ff done)
        if [[ ! -f "$tasks_file" ]]; then
            echo "ff:$target_change"
            return
        fi

        # Are all tasks checked? (apply done)
        local unchecked
        unchecked=$(grep -cE '^\s*-\s*\[\s*\]' "$tasks_file" 2>/dev/null || true)
        unchecked=${unchecked//[^0-9]/}
        unchecked=${unchecked:-0}
        if [[ "$unchecked" -gt 0 ]]; then
            echo "apply:$target_change"
            return
        fi

        echo "done"
        return
    fi

    # No target change — scan all changes (used by check_done for solo loops
    # and benchmark mode with numbered files)
    local change_order=()
    if ls "$wt_path"/docs/benchmark/[0-9]*.md &>/dev/null; then
        # Derive from numbered benchmark files: 01-product-catalog.md → product-catalog
        for f in "$wt_path"/docs/benchmark/[0-9]*.md; do
            local name
            name=$(basename "$f" .md | sed 's/^[0-9]*-//')
            change_order+=("$name")
        done
    elif [[ -d "$wt_path/openspec/changes" ]]; then
        # Fallback: alphabetical order
        for d in "$wt_path"/openspec/changes/*/; do
            [[ -d "$d" ]] || continue
            local name
            name=$(basename "$d")
            [[ "$name" == "archive" ]] && continue
            change_order+=("$name")
        done
    fi

    if [[ ${#change_order[@]} -eq 0 ]]; then
        echo "none"
        return
    fi

    local change_idx=0
    for change in "${change_order[@]}"; do
        change_idx=$((change_idx + 1))
        local change_dir="$wt_path/openspec/changes/$change"
        local tasks_file="$change_dir/tasks.md"

        # Check 0: Does results file exist? (change fully done — test passed)
        local nn
        nn=$(printf "%02d" "$change_idx")
        if [[ -f "$wt_path/results/change-${nn}.json" ]]; then
            continue  # Skip — this change is verified complete
        fi

        # Check 0.5: Does the change directory exist? (may be archived)
        if [[ ! -d "$change_dir" ]]; then
            # Check if archived
            if [[ -d "$wt_path/openspec/changes/archive/$change" ]]; then
                continue  # Archived — skip
            fi
            echo "ff:$change"
            return
        fi

        # Check 1: Does tasks.md exist? (ff done)
        if [[ ! -f "$tasks_file" ]]; then
            echo "ff:$change"
            return
        fi

        # Check 2: Are all tasks checked? (apply done)
        local unchecked
        unchecked=$(grep -cE '^\s*-\s*\[\s*\]' "$tasks_file" 2>/dev/null || true)
        unchecked=${unchecked//[^0-9]/}  # Strip non-digit chars
        unchecked=${unchecked:-0}
        if [[ "$unchecked" -gt 0 ]]; then
            echo "apply:$change"
            return
        fi
    done

    echo "done"
}

# Build Agent Teams instructions block for the prompt.
# Returns the instruction text when team mode is enabled, empty string otherwise.
build_team_instructions() {
    cat <<'TEAM_EOF'

# Agent Teams — Parallel Task Execution

You have Agent Teams available to parallelize independent tasks within this iteration.

## When to Use Teams
- You have **3 or more independent tasks** that don't share files
- Tasks are implementation work (code changes), not planning or artifact creation
- The tasks can run simultaneously without conflicts

## When NOT to Use Teams
- Fewer than 3 independent tasks — work sequentially instead
- Tasks modify the same files (risk of conflicts)
- Tasks have dependencies on each other (task B needs task A's output)
- You're running /opsx:ff (artifact creation) — always sequential
- Only 1-2 tasks remain

## How to Use Teams

1. **Check for orphan teams first**: If ~/.claude/teams/ has leftover team dirs from a previous iteration, clean them up with TeamDelete before proceeding.

2. **Analyze tasks**: Read tasks.md and identify which unchecked tasks are independent (don't share files).

3. **Create a team**: Use TeamCreate with a descriptive team_name.

4. **Create tasks**: Use TaskCreate for each parallelizable task with clear descriptions.

5. **Spawn teammates** (max 3): Use the Agent tool for each teammate:
   - `subagent_type: "general-purpose"` (full tool access)
   - `mode: "bypassPermissions"` (no permission prompts)
   - `team_name: "<your-team>"` (joins the team)
   - Give each a clear prompt describing exactly which task(s) to implement
   - Run teammates in foreground (NOT background) — wait for results

6. **Teammates work**: Each teammate reads the relevant files, makes changes, and marks their tasks complete via TaskUpdate. Teammates do NOT create git commits.

7. **You commit**: After ALL teammates finish, review the combined changes, resolve any conflicts, and create a single coherent commit. Only YOU (the team lead) commit.

8. **Cleanup**: Send shutdown_request to each teammate, wait for shutdown_response, then call TeamDelete.

## Important Rules
- Maximum 3 teammates per iteration
- Only the team lead (you) creates git commits
- If a teammate reports a conflict or error, handle it yourself after they finish
- Always clean up teams before the iteration ends (TeamDelete)
- Mark tasks in tasks.md as [x] after verifying the implementation
TEAM_EOF
}

# Build the prompt for Claude
build_prompt() {
    local task="$1"
    local iteration="$2"
    local max_iter="$3"
    local wt_path="$4"
    local done_criteria="$5"
    local target_change="${6:-}"

    local prev_commits=""
    local state_file
    state_file=$(get_loop_state_file "$wt_path")

    if [[ -f "$state_file" ]]; then
        prev_commits=$(jq -r '[.iterations[].commits[]?] | join(", ")' "$state_file" 2>/dev/null || echo "")
    fi

    local prev_text=""
    if [[ -n "$prev_commits" ]]; then
        prev_text="Previous iterations made commits: $prev_commits"
    else
        prev_text="This is the first iteration."
    fi

    # Detect OpenSpec project and determine specific action
    local change_action=""
    local specific_task=""
    local openspec_instructions=""

    if [[ -d "$wt_path/openspec" ]] && [[ "$done_criteria" == "openspec" ]] && [[ -n "$target_change" ]]; then
        # Scoped detection: only inspect the assigned change
        change_action=$(detect_next_change_action "$wt_path" "$target_change")

        case "$change_action" in
            ff:*)
                local change_name="${change_action#ff:}"
                specific_task="Create artifacts for the '$change_name' change"
                openspec_instructions="
# YOUR TASK (MANDATORY — do this and ONLY this)
Run: /opsx:ff $change_name
This will create design.md, specs, and tasks.md for the '$change_name' change.
Do NOT implement any code. Do NOT work on any other changes.
After /opsx:ff completes, commit the artifacts and stop.
"
                ;;
            apply:*)
                local change_name="${change_action#apply:}"
                specific_task="Implement the '$change_name' change"
                openspec_instructions="
# YOUR TASK (MANDATORY — do this and ONLY this)
Run: /opsx:apply $change_name
This will implement the tasks defined in tasks.md for the '$change_name' change.
Do NOT work on any other changes. Focus ONLY on '$change_name'.
After implementation, commit your changes and stop.
"
                ;;
            done)
                specific_task="All changes are complete"
                openspec_instructions="
# ALL CHANGES COMPLETE
All OpenSpec changes have been implemented. There is nothing left to do.
Do NOT write any files. Do NOT create any commits. Simply stop.
"
                ;;
            *)
                # No OpenSpec or no changes detected — use generic task
                specific_task="$task"
                ;;
        esac
    fi

    # Use specific task if detected, otherwise fall back to generic task
    local effective_task="${specific_task:-$task}"

    # Skip reflection when all changes are done — it creates dirty files
    # that prevent stall detection from firing as a safety net
    local reflection_section=""
    if [[ "$change_action" != "done" ]]; then
        reflection_section="
# Reflection (MANDATORY — last step before finishing)
Before you stop, write .claude/reflection.md with 3-5 bullet points:
- Errors you encountered and how you fixed them
- Non-obvious things you learned about this codebase
- Workarounds or gotchas the next iteration should know about
If nothing notable happened, write \"No notable issues.\" to the file."
    fi

    # Detect manual tasks and add instruction to skip them
    local manual_task_instruction=""
    local manual_count
    manual_count=$(count_manual_tasks "$wt_path")
    if [[ "$manual_count" -gt 0 ]]; then
        manual_task_instruction="
# Manual Tasks
Tasks marked with [?] in tasks.md require human action (e.g., providing API keys, external setup).
Do NOT attempt to complete [?] tasks — skip them entirely and focus only on [ ] tasks.
If all [ ] tasks are done but [?] tasks remain, commit your work and stop."
    fi

    # Agent Teams instructions (opt-in via --team flag)
    local team_instructions=""
    if [[ -f "$state_file" ]]; then
        local is_team_mode
        is_team_mode=$(jq -r '.team_mode // false' "$state_file" 2>/dev/null)
        if [[ "$is_team_mode" == "true" ]] && [[ "$change_action" != "done" ]] && [[ "$change_action" != ff:* ]]; then
            team_instructions=$(build_team_instructions)
        fi
    fi

    cat <<EOF
# Task
$effective_task

# Context
This is iteration $iteration of $max_iter in an autonomous Ralph loop.
Previous work is visible in the git history and current file state.

# Instructions
1. Read CLAUDE.md first — it contains the project workflow and specific instructions
2. Follow the workflow described in CLAUDE.md exactly
3. Do ONLY what is specified in YOUR TASK above — nothing more
4. If stuck on the same issue, try a different approach
$openspec_instructions
$manual_task_instruction
$team_instructions
# Previous Work
$prev_text

# Important
- Do ONLY the task specified above — do NOT work on other changes
- CLAUDE.md is the authoritative source for your workflow — follow it
- Commit your changes before exiting
$reflection_section
EOF
}
