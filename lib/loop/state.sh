#!/usr/bin/env bash
# set-loop state management: state file paths, init, update, token tracking
# Dependencies: set-common.sh must be sourced first (provides jq, SCRIPT_DIR)

# Parse ISO 8601 date to epoch seconds (cross-platform)
# Works on both Linux (GNU date) and macOS (BSD date)
parse_date_to_epoch() {
    local date_str="$1"
    local epoch

    if [[ "$(uname)" == "Darwin" ]]; then
        local clean_date
        clean_date=$(echo "$date_str" | sed -E 's/[+-][0-9]{2}:?[0-9]{2}$//')
        epoch=$(date -j -f "%Y-%m-%dT%H:%M:%S" "$clean_date" "+%s" 2>/dev/null || echo "0")
    else
        epoch=$(date -d "$date_str" +%s 2>/dev/null || echo "0")
    fi

    echo "$epoch"
}

# Get loop state file path for a worktree (per-agent ephemeral in .set/)
get_loop_state_file() {
    local wt_path="$1"
    echo "$wt_path/.set/loop-state.json"
}

get_loop_log_dir() {
    local wt_path="$1"
    echo "$wt_path/.set/logs"
}

get_iter_log_file() {
    local wt_path="$1"
    local iteration="$2"
    local log_dir
    log_dir=$(get_loop_log_dir "$wt_path")
    printf '%s/ralph-iter-%03d.log' "$log_dir" "$iteration"
}

# Get terminal PID file path
get_terminal_pid_file() {
    local wt_path="$1"
    echo "$wt_path/.set/ralph-terminal.pid"
}

# Initialize loop state
init_loop_state() {
    local wt_path="$1"
    local worktree_name="$2"
    local task="$3"
    local max_iter="$4"
    local done_criteria="$5"
    local capacity_limit="$6"
    local stall_threshold="${7:-$DEFAULT_STALL_THRESHOLD}"
    local iteration_timeout="${8:-45}"
    local label="${9:-}"
    local change="${10:-}"

    local state_file
    state_file=$(get_loop_state_file "$wt_path")

    # Ensure .set agent directory exists
    mkdir -p "$wt_path/.set" "$wt_path/.set/logs"

    # Preserve session_id and resume_failures from prior state (same worktree/change).
    # This allows Claude --resume to reuse the cached prefix across dispatcher-level
    # restarts (e.g. gate retry fixes), avoiding cold cache rebuilds on every retry.
    # If no prior state exists or session_id was never set, defaults to null/0.
    local preserved_session_id="null"
    local preserved_resume_failures="0"
    if [[ -f "$state_file" ]]; then
        local prior_change
        prior_change=$(jq -r '.change // ""' "$state_file" 2>/dev/null || echo "")
        local prior_sid
        prior_sid=$(jq -r '.session_id // empty' "$state_file" 2>/dev/null || echo "")
        # Only preserve if same change name (avoid cross-change cache poisoning)
        if [[ -n "$prior_sid" ]] && [[ "$prior_change" == "$change" ]]; then
            preserved_session_id="\"$prior_sid\""
            preserved_resume_failures=$(jq -r '.resume_failures // 0' "$state_file" 2>/dev/null || echo "0")
            # Validate resume_failures is an integer
            if ! [[ "$preserved_resume_failures" =~ ^[0-9]+$ ]]; then
                preserved_resume_failures="0"
            fi
        fi
    fi

    # Create initial state
    cat > "$state_file" <<EOF
{
  "worktree_name": "$worktree_name",
  "task": $(echo "$task" | jq -Rs .),
  "done_criteria": "$done_criteria",
  "max_iterations": $max_iter,
  "current_iteration": 0,
  "status": "starting",
  "terminal_pid": null,
  "started_at": "$(date -Iseconds)",
  "iterations": [],
  "capacity_limit_pct": $capacity_limit,
  "stall_threshold": $stall_threshold,
  "iteration_timeout_min": $iteration_timeout,
  "total_tokens": 0,
  "total_input_tokens": 0,
  "total_output_tokens": 0,
  "total_cache_read": 0,
  "total_cache_create": 0,
  "token_budget": 0,
  "ff_attempts": 0,
  "max_idle_iterations": 3,
  "idle_count": 0,
  "last_output_hash": null,
  "session_id": $preserved_session_id,
  "resume_failures": $preserved_resume_failures,
  "base_context_tokens": 0,
  "team_mode": false,
  "label": $(if [[ -n "$label" ]]; then printf '%s' "$label" | jq -Rs .; else echo "null"; fi),
  "change": $(if [[ -n "$change" ]]; then printf '%s' "$change" | jq -Rs .; else echo "null"; fi)
}
EOF
}

# Update loop state
update_loop_state() {
    local state_file="$1"
    local field="$2"
    local value="$3"

    local tmp
    tmp=$(mktemp)
    jq ".$field = $value" "$state_file" > "$tmp" && mv "$tmp" "$state_file"
}

# Add iteration to state
add_iteration() {
    local state_file="$1"
    local iteration="$2"
    local started="$3"
    local ended="$4"
    local done_check="$5"
    local commits="$6"
    local tokens_used="${7:-0}"
    local timed_out="${8:-false}"
    local tokens_estimated="${9:-false}"
    local no_op="${10:-false}"
    local ff_exhausted="${11:-false}"
    local log_file="${12:-}"
    local resumed="${13:-false}"
    local ff_recovered="${14:-false}"
    local input_tokens="${15:-0}"
    local output_tokens="${16:-0}"
    local cache_read_tokens="${17:-0}"
    local cache_create_tokens="${18:-0}"
    local team_spawned="${19:-false}"
    local teammates_count="${20:-0}"
    local team_tasks_parallel="${21:-0}"
    local ctx_base="${22:-0}"
    local ctx_memory="${23:-0}"
    local ctx_prompt="${24:-0}"
    local ctx_tools="${25:-0}"

    local tmp
    tmp=$(mktemp)
    jq --argjson n "$iteration" \
       --arg started "$started" \
       --arg ended "$ended" \
       --argjson done "$done_check" \
       --argjson commits "$commits" \
       --argjson tokens "$tokens_used" \
       --argjson timed_out "$timed_out" \
       --argjson tokens_estimated "$tokens_estimated" \
       --argjson no_op "$no_op" \
       --argjson ff_exhausted "$ff_exhausted" \
       --arg log_file "$log_file" \
       --argjson resumed "$resumed" \
       --argjson ff_recovered "$ff_recovered" \
       --argjson in_tok "$input_tokens" \
       --argjson out_tok "$output_tokens" \
       --argjson cr_tok "$cache_read_tokens" \
       --argjson cc_tok "$cache_create_tokens" \
       --argjson t_spawned "$team_spawned" \
       --argjson t_count "$teammates_count" \
       --argjson t_parallel "$team_tasks_parallel" \
       --argjson cb_base "$ctx_base" \
       --argjson cb_mem "$ctx_memory" \
       --argjson cb_prompt "$ctx_prompt" \
       --argjson cb_tools "$ctx_tools" \
       '.iterations += [{
         "n": $n,
         "started": $started,
         "ended": $ended,
         "done_check": $done,
         "commits": $commits,
         "tokens_used": $tokens,
         "input_tokens": $in_tok,
         "output_tokens": $out_tok,
         "cache_read_tokens": $cr_tok,
         "cache_create_tokens": $cc_tok,
         "timed_out": $timed_out,
         "tokens_estimated": $tokens_estimated,
         "no_op": $no_op,
         "ff_exhausted": $ff_exhausted,
         "log_file": $log_file,
         "resumed": $resumed,
         "ff_recovered": $ff_recovered,
         "team_spawned": $t_spawned,
         "teammates_count": $t_count,
         "team_tasks_parallel": $t_parallel,
         "context_breakdown": {
           "base_context": $cb_base,
           "memory_injection": $cb_mem,
           "prompt_overhead": $cb_prompt,
           "tool_output": $cb_tools
         }
       }]
       | .total_tokens = ([.iterations[].tokens_used // 0] | add)
       | .total_input_tokens = ([.iterations[].input_tokens // 0] | add)
       | .total_output_tokens = ([.iterations[].output_tokens // 0] | add)
       | .total_cache_read = ([.iterations[].cache_read_tokens // 0] | add)
       | .total_cache_create = ([.iterations[].cache_create_tokens // 0] | add)
       ' "$state_file" > "$tmp" && mv "$tmp" "$state_file"
}

# Get current token usage from set-usage
# Returns JSON: {"input_tokens":N,"output_tokens":N,"cache_read_tokens":N,"cache_create_tokens":N,"total_tokens":N}
get_current_tokens() {
    local since="${1:-}"
    local usage_json
    local zero_json='{"input_tokens":0,"output_tokens":0,"cache_read_tokens":0,"cache_create_tokens":0,"total_tokens":0}'

    # Derive project dir from $PWD: replace / with -
    # Claude's project dirs keep the leading dash (e.g. -home-tg-code-project)
    # For worktrees: use the parent repo path (git common-dir → dirname),
    # since Claude tracks per-repo not per-worktree.
    local project_dir_flag=""
    local source_path="$PWD"
    local common_git
    common_git=$(git rev-parse --git-common-dir 2>/dev/null || true)
    if [[ -n "$common_git" ]]; then
        # Convert to absolute path if relative
        if [[ "$common_git" != /* ]]; then
            common_git="$PWD/$common_git"
        fi
        # Parent of .git is the repo root
        local parent_repo
        parent_repo=$(dirname "$common_git")
        if [[ -d "$parent_repo" ]]; then
            source_path="$parent_repo"
        fi
    fi
    local derived_dir
    derived_dir=$(echo "$source_path" | sed 's|/|-|g')
    local claude_projects_dir="$HOME/.claude/projects"
    if [[ -d "$claude_projects_dir/$derived_dir" ]]; then
        project_dir_flag="--project-dir=$derived_dir"
    fi
    # No warning when not found — caller has unfiltered fallback by design

    if [[ -n "$since" ]]; then
        usage_json=$("$SCRIPT_DIR/set-usage" --since "$since" $project_dir_flag --format json 2>/dev/null || echo "$zero_json")
    else
        usage_json=$("$SCRIPT_DIR/set-usage" $project_dir_flag --format json 2>/dev/null || echo "$zero_json")
    fi

    # Extract all token types
    # input_tokens includes cache_read — this is the true prompt size the model sees
    # total_tokens = input + output (API billing tokens, excludes cache)
    echo "$usage_json" | jq -c '{
        input_tokens: ((.input_tokens // 0) + (.cache_read_tokens // 0)),
        output_tokens: (.output_tokens // 0),
        cache_read_tokens: (.cache_read_tokens // 0),
        cache_create_tokens: (.cache_creation_tokens // 0),
        total_tokens: ((.input_tokens // 0) + (.output_tokens // 0))
    }' 2>/dev/null || echo "$zero_json"
}

# Helper: extract a field from get_current_tokens() JSON
# Usage: tokens_total=$(extract_token_field "$json" "total_tokens")
extract_token_field() {
    echo "$1" | jq -r ".$2 // 0" 2>/dev/null || echo "0"
}

# Estimate tokens from session file size growth
# Rough heuristic: ~4 tokens per byte of JSONL
estimate_tokens_from_files() {
    local wt_path="$1"
    local since_epoch="$2"

    local total_bytes=0
    local claude_dir="$HOME/.claude/projects"

    if [[ ! -d "$claude_dir" ]]; then
        echo "0"
        return
    fi

    # Find JSONL files modified since the given epoch
    while IFS= read -r -d '' jsonl_file; do
        local file_mtime
        file_mtime=$(stat -c %Y "$jsonl_file" 2>/dev/null || stat -f %m "$jsonl_file" 2>/dev/null || echo "0")
        if [[ "$file_mtime" -ge "$since_epoch" ]]; then
            local file_size
            file_size=$(stat -c %s "$jsonl_file" 2>/dev/null || stat -f %z "$jsonl_file" 2>/dev/null || echo "0")
            total_bytes=$((total_bytes + file_size))
        fi
    done < <(find "$claude_dir" -name "*.jsonl" -print0 2>/dev/null)

    # Rough estimate: 4 tokens per byte
    echo $((total_bytes / 4))
}

# Update terminal window title
update_terminal_title() {
    local title="$1"
    printf '\033]0;%s\007' "$title"
}
