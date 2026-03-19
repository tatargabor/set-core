#!/bin/bash
# Claude Code Status Line Script
# Shows: folder, branch, model, context usage, set-loop status

input=$(cat)

# Parse JSON input
model=$(echo "$input" | jq -r '.model.display_name')
dir=$(echo "$input" | jq -r '.workspace.current_dir')
folder=$(basename "$dir")

# Git branch
branch=$(cd "$dir" 2>/dev/null && git -c core.useBuiltinFSMonitor=false rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')
git_info=""
if [ -n "$branch" ]; then
    git_info=" ($branch)"
fi

# Context window
remaining=$(echo "$input" | jq -r '.context_window.remaining_percentage // empty')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
ctx_size=$(echo "$input" | jq -r '.context_window.context_window_size // empty')
total_input=$(echo "$input" | jq -r '.context_window.total_input_tokens // 0')
total_output=$(echo "$input" | jq -r '.context_window.total_output_tokens // 0')
agents=$(echo "$input" | jq -r '.agents // [] | length')

# set-loop status (check loop-state.json in current worktree)
ralph_status=""
state_file="$dir/.set/loop-state.json"
if [ -f "$state_file" ]; then
    status=$(jq -r '.status // empty' "$state_file" 2>/dev/null)
    iteration=$(jq -r '.current_iteration // 0' "$state_file" 2>/dev/null)
    max_iter=$(jq -r '.max_iterations // 0' "$state_file" 2>/dev/null)

    case "$status" in
        running)
            ralph_status=" | 🔄 set-ralph: $iteration/$max_iter"
            ;;
        done)
            ralph_status=" | ✅ set-ralph: done"
            ;;
        stuck)
            ralph_status=" | ⚠️ set-ralph: stuck"
            ;;
        stopped)
            ralph_status=" | ⏹️ set-ralph: stopped"
            ;;
    esac
fi

# Build output
if [ -n "$remaining" ]; then
    total_tokens=$((total_input + total_output))
    ctx_size_k=$((ctx_size / 1000))
    printf "[%s] %s%s | %s | Ctx: %s%% (%s/%sk)%s | Agents: %s" \
        "$folder" "$folder" "$git_info" "$model" "$used" "$total_tokens" "$ctx_size_k" "$ralph_status" "$agents"
else
    printf "[%s] %s%s | %s%s | Agents: %s" \
        "$folder" "$folder" "$git_info" "$model" "$ralph_status" "$agents"
fi
