#!/usr/bin/env bash
# lib/orchestration/utils.sh — Parsing, duration, hashing, directive resolution
# Sourced by bin/wt-orchestrate after config.sh

parse_duration() {
    local input="$1"
    local total=0

    # Plain number → minutes
    if [[ "$input" =~ ^[0-9]+$ ]]; then
        total=$((input * 60))
        echo "$total"
        return 0
    fi

    # Extract hours
    if [[ "$input" =~ ([0-9]+)h ]]; then
        total=$((total + BASH_REMATCH[1] * 3600))
    fi

    # Extract minutes
    if [[ "$input" =~ ([0-9]+)m ]]; then
        total=$((total + BASH_REMATCH[1] * 60))
    fi

    if [[ "$total" -eq 0 ]]; then
        echo "0"
        return 1
    fi

    echo "$total"
}

# Check if any running Ralph loop has made recent progress.
# A loop is "active" if its loop-state.json was modified within the last 5 minutes.
# Returns 0 (true) if at least one loop is active, 1 (false) if all stalled.
any_loop_active() {
    local stale_threshold=300  # 5 minutes
    local now
    now=$(date +%s)
    local running
    running=$(get_changes_by_status "running" 2>/dev/null || true)
    [[ -z "$running" ]] && return 1

    while IFS= read -r name; do
        [[ -z "$name" ]] && continue
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME" 2>/dev/null)
        [[ -z "$wt_path" ]] && continue
        local loop_state="$wt_path/.claude/loop-state.json"
        if [[ -f "$loop_state" ]]; then
            local mtime
            mtime=$(stat --format='%Y' "$loop_state" 2>/dev/null || echo 0)
            local age=$((now - mtime))
            if [[ "$age" -lt "$stale_threshold" ]]; then
                return 0  # at least one loop is active
            fi
        fi
    done <<< "$running"
    return 1  # all loops stalled or no loop-state files
}

# Format seconds into human-readable duration
format_duration() {
    local secs="$1"
    local h=$((secs / 3600))
    local m=$(( (secs % 3600) / 60 ))
    if [[ "$h" -gt 0 && "$m" -gt 0 ]]; then
        echo "${h}h${m}m"
    elif [[ "$h" -gt 0 ]]; then
        echo "${h}h"
    else
        echo "${m}m"
    fi
}

# ─── Brief Parser ────────────────────────────────────────────────────

# Find the project brief file (legacy, used by find_input fallback)
find_brief() {
    # --brief override takes priority
    if [[ -n "$BRIEF_OVERRIDE" ]]; then
        if [[ -f "$BRIEF_OVERRIDE" ]]; then
            echo "$BRIEF_OVERRIDE"
        else
            echo ""
        fi
        return
    fi

    local openspec_dir
    openspec_dir=$(find_openspec_dir)

    if [[ -f "$openspec_dir/$BRIEF_FILENAME" ]]; then
        echo "$openspec_dir/$BRIEF_FILENAME"
    elif [[ -f "$openspec_dir/$BRIEF_FALLBACK" ]]; then
        echo "$openspec_dir/$BRIEF_FALLBACK"
    else
        echo ""
    fi
}

# Find input document and determine mode.
# Sets global: INPUT_MODE ("spec" or "brief"), INPUT_PATH
find_input() {
    # --spec takes priority
    if [[ -n "$SPEC_OVERRIDE" ]]; then
        if [[ -f "$SPEC_OVERRIDE" ]]; then
            INPUT_MODE="spec"
            INPUT_PATH="$(cd "$(dirname "$SPEC_OVERRIDE")" && pwd)/$(basename "$SPEC_OVERRIDE")"
            return 0
        fi
        # Short-name resolution: try wt/orchestration/specs/
        local wt_spec="wt/orchestration/specs/${SPEC_OVERRIDE}.md"
        local wt_spec_sub="wt/orchestration/specs/${SPEC_OVERRIDE}"
        if [[ -f "$wt_spec" ]]; then
            INPUT_MODE="spec"
            INPUT_PATH="$(cd "$(dirname "$wt_spec")" && pwd)/$(basename "$wt_spec")"
            return 0
        elif [[ -f "$wt_spec_sub" ]]; then
            INPUT_MODE="spec"
            INPUT_PATH="$(cd "$(dirname "$wt_spec_sub")" && pwd)/$(basename "$wt_spec_sub")"
            return 0
        fi
        error "Spec file not found: $SPEC_OVERRIDE"
        error "  Checked: $SPEC_OVERRIDE, $wt_spec"
        return 1
    fi

    # --brief or auto-detect brief
    local brief_file
    brief_file=$(find_brief)
    if [[ -n "$brief_file" && -f "$brief_file" ]]; then
        # Check if brief has ### Next items
        local items
        items=$(parse_next_items "$brief_file")
        local count
        count=$(echo "$items" | jq 'length')
        if [[ "$count" -gt 0 ]]; then
            INPUT_MODE="brief"
            INPUT_PATH="$brief_file"
            return 0
        fi
        # Brief exists but ### Next is empty
        error "Brief found ($brief_file) but ### Next section is empty."
        error "Add items to ### Next, or use --spec <path> to provide a specification document."
        return 1
    fi

    # Nothing found
    error "No input found. Use --spec <path> or create openspec/$BRIEF_FILENAME"
    return 1
}

# Find openspec directory
find_openspec_dir() {
    if [[ -d "openspec" ]]; then
        echo "openspec"
    elif [[ -d "../openspec" ]]; then
        echo "../openspec"
    else
        echo "openspec"  # default, may not exist
    fi
}

# Extract items from ## Next section
parse_next_items() {
    local brief_file="$1"
    local in_next=false
    local items=()

    while IFS= read -r line; do
        # Detect ### Next header
        if [[ "$line" =~ ^###[[:space:]]+Next ]]; then
            in_next=true
            continue
        fi
        # Detect any other ### header → stop
        if [[ "$line" =~ ^### ]] && $in_next; then
            break
        fi
        # Detect ## header → stop
        if [[ "$line" =~ ^## ]] && $in_next; then
            break
        fi
        # Collect bullet items
        if $in_next && [[ "$line" =~ ^[[:space:]]*-[[:space:]](.+) ]]; then
            local item="${BASH_REMATCH[1]}"
            # Strip leading/trailing whitespace
            item=$(echo "$item" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            [[ -n "$item" ]] && items+=("$item")
        fi
    done < "$brief_file"

    # Output as JSON array
    if [[ ${#items[@]} -eq 0 ]]; then
        echo '[]'
    else
        printf '%s\n' "${items[@]}" | jq -R . | jq -s .
    fi
}

# ─── Directives ──────────────────────────────────────────────────────

# Parse orchestrator directives from brief
parse_directives() {
    local brief_file="$1"
    local in_directives=false
    local max_parallel="$DEFAULT_MAX_PARALLEL"
    local merge_policy="$DEFAULT_MERGE_POLICY"
    local checkpoint_every="$DEFAULT_CHECKPOINT_EVERY"
    local test_command="$DEFAULT_TEST_COMMAND"
    local notification="$DEFAULT_NOTIFICATION"
    local token_budget="$DEFAULT_TOKEN_BUDGET"
    local pause_on_exit="$DEFAULT_PAUSE_ON_EXIT"
    local auto_replan="$DEFAULT_AUTO_REPLAN"
    local review_before_merge="$DEFAULT_REVIEW_BEFORE_MERGE"
    local test_timeout="$DEFAULT_TEST_TIMEOUT"
    local max_verify_retries="$DEFAULT_MAX_VERIFY_RETRIES"
    local summarize_model="$DEFAULT_SUMMARIZE_MODEL"
    local review_model="$DEFAULT_REVIEW_MODEL"
    local default_model="$DEFAULT_IMPL_MODEL"
    local smoke_command="$DEFAULT_SMOKE_COMMAND"
    local smoke_timeout="$DEFAULT_SMOKE_TIMEOUT"
    local smoke_blocking="$DEFAULT_SMOKE_BLOCKING"
    local smoke_fix_token_budget="$DEFAULT_SMOKE_FIX_TOKEN_BUDGET"
    local smoke_fix_max_turns="$DEFAULT_SMOKE_FIX_MAX_TURNS"
    local smoke_fix_max_retries="$DEFAULT_SMOKE_FIX_MAX_RETRIES"
    local smoke_health_check_url=""
    local smoke_health_check_timeout="$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT"

    local post_merge_command="$DEFAULT_POST_MERGE_COMMAND"
    local token_hard_limit="$DEFAULT_TOKEN_HARD_LIMIT"
    local events_log="true"
    local events_max_size="$EVENTS_MAX_SIZE"
    local watchdog_timeout=""
    local watchdog_loop_threshold=""
    local max_tokens_per_change=""
    local context_pruning="true"
    local plan_approval="false"
    local checkpoint_auto_approve="$DEFAULT_CHECKPOINT_AUTO_APPROVE"
    local plan_method="$DEFAULT_PLAN_METHOD"
    local model_routing="off"
    local hook_pre_dispatch=""
    local hook_post_verify=""
    local hook_pre_merge=""
    local hook_post_merge=""
    local hook_on_fail=""

    while IFS= read -r line; do
        # Detect ## Orchestrator Directives header
        if [[ "$line" =~ ^##[[:space:]]+Orchestrator[[:space:]]+Directives ]]; then
            in_directives=true
            continue
        fi
        # Detect any other ## header → stop
        if [[ "$line" =~ ^## ]] && $in_directives; then
            break
        fi
        # Parse key: value lines
        if $in_directives; then
            local key="" val=""
            if [[ "$line" =~ ^[[:space:]]*-?[[:space:]]*([a-z_]+):[[:space:]]*(.+) ]]; then
                key="${BASH_REMATCH[1]}"
                val="${BASH_REMATCH[2]}"
                val=$(echo "$val" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
            fi
            [[ -z "$key" ]] && continue

            case "$key" in
                max_parallel)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        max_parallel="$val"
                    else
                        warn "Invalid max_parallel '$val', using default $DEFAULT_MAX_PARALLEL"
                    fi
                    ;;
                merge_policy)
                    if [[ "$val" =~ ^(eager|checkpoint|manual)$ ]]; then
                        merge_policy="$val"
                    else
                        warn "Invalid merge_policy '$val', using default $DEFAULT_MERGE_POLICY"
                    fi
                    ;;
                checkpoint_every)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        checkpoint_every="$val"
                    else
                        warn "Invalid checkpoint_every '$val', using default $DEFAULT_CHECKPOINT_EVERY"
                    fi
                    ;;
                test_command)
                    test_command="$val"
                    ;;
                notification)
                    if [[ "$val" =~ ^(desktop|email|desktop\+email|gui|none)$ ]]; then
                        notification="$val"
                    else
                        warn "Invalid notification '$val' (valid: desktop, email, desktop+email, none), using default $DEFAULT_NOTIFICATION"
                    fi
                    ;;
                token_budget)
                    if [[ "$val" =~ ^[0-9]+$ ]]; then
                        token_budget="$val"
                    else
                        warn "Invalid token_budget '$val', using default $DEFAULT_TOKEN_BUDGET"
                    fi
                    ;;
                token_hard_limit)
                    if [[ "$val" =~ ^[0-9]+$ ]]; then
                        token_hard_limit="$val"
                    else
                        warn "Invalid token_hard_limit '$val', using default $DEFAULT_TOKEN_HARD_LIMIT"
                    fi
                    ;;
                pause_on_exit)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        pause_on_exit="$val"
                    else
                        warn "Invalid pause_on_exit '$val', using default $DEFAULT_PAUSE_ON_EXIT"
                    fi
                    ;;
                auto_replan)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        auto_replan="$val"
                    else
                        warn "Invalid auto_replan '$val', using default $DEFAULT_AUTO_REPLAN"
                    fi
                    ;;
                review_before_merge)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        review_before_merge="$val"
                    else
                        warn "Invalid review_before_merge '$val', using default $DEFAULT_REVIEW_BEFORE_MERGE"
                    fi
                    ;;
                test_timeout)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        test_timeout="$val"
                    else
                        warn "Invalid test_timeout '$val', using default $DEFAULT_TEST_TIMEOUT"
                    fi
                    ;;
                max_verify_retries)
                    if [[ "$val" =~ ^[0-9]+$ ]]; then
                        max_verify_retries="$val"
                    else
                        warn "Invalid max_verify_retries '$val', using default $DEFAULT_MAX_VERIFY_RETRIES"
                    fi
                    ;;
                summarize_model)
                    if [[ "$val" =~ ^(haiku|sonnet|opus)$ ]]; then
                        summarize_model="$val"
                    else
                        warn "Invalid summarize_model '$val', using default $DEFAULT_SUMMARIZE_MODEL"
                    fi
                    ;;
                review_model)
                    if [[ "$val" =~ ^(haiku|sonnet|opus)$ ]]; then
                        review_model="$val"
                    else
                        warn "Invalid review_model '$val', using default $DEFAULT_REVIEW_MODEL"
                    fi
                    ;;
                default_model)
                    if [[ "$val" =~ ^(haiku|sonnet|opus)$ ]]; then
                        default_model="$val"
                    else
                        warn "Invalid default_model '$val', using default $DEFAULT_IMPL_MODEL"
                    fi
                    ;;
                smoke_command)
                    smoke_command="$val"
                    ;;
                smoke_timeout)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        smoke_timeout="$val"
                    else
                        warn "Invalid smoke_timeout '$val', using default $DEFAULT_SMOKE_TIMEOUT"
                    fi
                    ;;
                smoke_blocking)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        smoke_blocking="$val"
                    else
                        warn "Invalid smoke_blocking '$val', using default $DEFAULT_SMOKE_BLOCKING"
                    fi
                    ;;
                smoke_fix_token_budget)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        smoke_fix_token_budget="$val"
                    else
                        warn "Invalid smoke_fix_token_budget '$val', using default $DEFAULT_SMOKE_FIX_TOKEN_BUDGET"
                    fi
                    ;;
                smoke_fix_max_turns)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        smoke_fix_max_turns="$val"
                    else
                        warn "Invalid smoke_fix_max_turns '$val', using default $DEFAULT_SMOKE_FIX_MAX_TURNS"
                    fi
                    ;;
                smoke_fix_max_retries)
                    if [[ "$val" =~ ^[0-9]+$ ]]; then
                        smoke_fix_max_retries="$val"
                    else
                        warn "Invalid smoke_fix_max_retries '$val', using default $DEFAULT_SMOKE_FIX_MAX_RETRIES"
                    fi
                    ;;
                smoke_health_check_url)
                    smoke_health_check_url="$val"
                    ;;
                smoke_health_check_timeout)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        smoke_health_check_timeout="$val"
                    else
                        warn "Invalid smoke_health_check_timeout '$val', using default $DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT"
                    fi
                    ;;

                post_merge_command)
                    post_merge_command="$val"
                    ;;
                events_log)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        events_log="$val"
                    fi
                    ;;
                events_max_size)
                    if [[ "$val" =~ ^[0-9]+$ ]]; then
                        events_max_size="$val"
                    fi
                    ;;
                watchdog_timeout)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        watchdog_timeout="$val"
                    else
                        warn "Invalid watchdog_timeout '$val', ignoring"
                    fi
                    ;;
                watchdog_loop_threshold)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        watchdog_loop_threshold="$val"
                    else
                        warn "Invalid watchdog_loop_threshold '$val', ignoring"
                    fi
                    ;;
                max_tokens_per_change)
                    if [[ "$val" =~ ^[0-9]+$ ]] && [[ "$val" -gt 0 ]]; then
                        max_tokens_per_change="$val"
                    else
                        warn "Invalid max_tokens_per_change '$val', ignoring"
                    fi
                    ;;
                context_pruning)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        context_pruning="$val"
                    else
                        warn "Invalid context_pruning '$val', using default true"
                    fi
                    ;;
                plan_approval)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        plan_approval="$val"
                    else
                        warn "Invalid plan_approval '$val', using default false"
                    fi
                    ;;
                checkpoint_auto_approve)
                    if [[ "$val" =~ ^(true|false)$ ]]; then
                        checkpoint_auto_approve="$val"
                    else
                        warn "Invalid checkpoint_auto_approve '$val', using default $DEFAULT_CHECKPOINT_AUTO_APPROVE"
                    fi
                    ;;
                plan_method)
                    if [[ "$val" =~ ^(api|agent)$ ]]; then
                        plan_method="$val"
                    else
                        warn "Invalid plan_method '$val', using default $DEFAULT_PLAN_METHOD"
                    fi
                    ;;
                model_routing)
                    if [[ "$val" =~ ^(off|complexity)$ ]]; then
                        model_routing="$val"
                    else
                        warn "Invalid model_routing '$val', using default off"
                    fi
                    ;;
                hook_pre_dispatch)  hook_pre_dispatch="$val" ;;
                hook_post_verify)   hook_post_verify="$val" ;;
                hook_pre_merge)     hook_pre_merge="$val" ;;
                hook_post_merge)    hook_post_merge="$val" ;;
                hook_on_fail)       hook_on_fail="$val" ;;
                *)
                    warn "Unknown directive '$key', ignoring"
                    ;;
            esac
        fi
    done < "$brief_file"

    # Auto-detect test_command if not set explicitly
    if [[ -z "$test_command" ]]; then
        test_command=$(auto_detect_test_command "." 2>/dev/null || true)
        if [[ -n "$test_command" ]]; then
            log_info "Auto-detected test command: $test_command"
        fi
    fi

    # Output as JSON
    jq -n \
        --argjson max_parallel "$max_parallel" \
        --arg merge_policy "$merge_policy" \
        --argjson checkpoint_every "$checkpoint_every" \
        --arg test_command "$test_command" \
        --arg notification "$notification" \
        --argjson token_budget "$token_budget" \
        --argjson pause_on_exit "$pause_on_exit" \
        --argjson auto_replan "$auto_replan" \
        --argjson review_before_merge "$review_before_merge" \
        --argjson test_timeout "$test_timeout" \
        --argjson max_verify_retries "$max_verify_retries" \
        --arg summarize_model "$summarize_model" \
        --arg review_model "$review_model" \
        --arg default_model "$default_model" \
        --arg smoke_command "$smoke_command" \
        --argjson smoke_timeout "$smoke_timeout" \
        --argjson smoke_blocking "$smoke_blocking" \
        --argjson smoke_fix_token_budget "$smoke_fix_token_budget" \
        --argjson smoke_fix_max_turns "$smoke_fix_max_turns" \
        --argjson smoke_fix_max_retries "$smoke_fix_max_retries" \
        --arg smoke_health_check_url "$smoke_health_check_url" \
        --argjson smoke_health_check_timeout "$smoke_health_check_timeout" \
        --arg post_merge_command "$post_merge_command" \
        --argjson token_hard_limit "$token_hard_limit" \
        --arg events_log "$events_log" \
        --argjson events_max_size "$events_max_size" \
        --arg watchdog_timeout "$watchdog_timeout" \
        --arg watchdog_loop_threshold "$watchdog_loop_threshold" \
        --arg max_tokens_per_change "$max_tokens_per_change" \
        --argjson context_pruning "$context_pruning" \
        --argjson plan_approval "$plan_approval" \
        --argjson checkpoint_auto_approve "$checkpoint_auto_approve" \
        --arg plan_method "$plan_method" \
        --arg model_routing "$model_routing" \
        --arg hook_pre_dispatch "$hook_pre_dispatch" \
        --arg hook_post_verify "$hook_post_verify" \
        --arg hook_pre_merge "$hook_pre_merge" \
        --arg hook_post_merge "$hook_post_merge" \
        --arg hook_on_fail "$hook_on_fail" \
        '{
            max_parallel: $max_parallel,
            merge_policy: $merge_policy,
            checkpoint_every: $checkpoint_every,
            test_command: $test_command,
            notification: $notification,
            token_budget: $token_budget,
            pause_on_exit: $pause_on_exit,
            auto_replan: $auto_replan,
            review_before_merge: $review_before_merge,
            test_timeout: $test_timeout,
            max_verify_retries: $max_verify_retries,
            summarize_model: $summarize_model,
            review_model: $review_model,
            default_model: $default_model,
            smoke_command: $smoke_command,
            smoke_timeout: $smoke_timeout,
            smoke_blocking: $smoke_blocking,
            smoke_fix_token_budget: $smoke_fix_token_budget,
            smoke_fix_max_turns: $smoke_fix_max_turns,
            smoke_fix_max_retries: $smoke_fix_max_retries,
            smoke_health_check_url: $smoke_health_check_url,
            smoke_health_check_timeout: $smoke_health_check_timeout,
            post_merge_command: $post_merge_command,
            token_hard_limit: $token_hard_limit,
            events_log: $events_log,
            events_max_size: $events_max_size,
            watchdog_timeout: (if $watchdog_timeout != "" then ($watchdog_timeout | tonumber) else null end),
            watchdog_loop_threshold: (if $watchdog_loop_threshold != "" then ($watchdog_loop_threshold | tonumber) else null end),
            max_tokens_per_change: (if $max_tokens_per_change != "" then ($max_tokens_per_change | tonumber) else null end),
            context_pruning: $context_pruning,
            plan_approval: $plan_approval,
            checkpoint_auto_approve: $checkpoint_auto_approve,
            plan_method: $plan_method,
            model_routing: $model_routing,
            hook_pre_dispatch: (if $hook_pre_dispatch != "" then $hook_pre_dispatch else null end),
            hook_post_verify: (if $hook_post_verify != "" then $hook_post_verify else null end),
            hook_pre_merge: (if $hook_pre_merge != "" then $hook_pre_merge else null end),
            hook_post_merge: (if $hook_post_merge != "" then $hook_post_merge else null end),
            hook_on_fail: (if $hook_on_fail != "" then $hook_on_fail else null end)
        } | with_entries(select(.value != null))'
}

# Compute SHA-256 hash of input file
brief_hash() {
    local brief_file="$1"
    sha256sum "$brief_file" 2>/dev/null | cut -d' ' -f1 || \
    shasum -a 256 "$brief_file" 2>/dev/null | cut -d' ' -f1 || \
    echo "unknown"
}

# ─── Config & Directives ─────────────────────────────────────────────

# Load directives from orchestration config (wt/orchestration/config.yaml or .claude/orchestration.yaml)
# Outputs JSON with only the keys found in the file (partial)
load_config_file() {
    if [[ -z "$CONFIG_FILE" || ! -f "$CONFIG_FILE" ]]; then
        echo '{}'
        return 0
    fi

    python3 -c "
import sys, json
try:
    import yaml
except ImportError:
    # No PyYAML — fall back to simple key:value parsing
    result = {}
    for line in open('$CONFIG_FILE'):
        line = line.strip()
        if ':' in line and not line.startswith('#'):
            key, _, val = line.partition(':')
            key, val = key.strip(), val.strip()
            if val.isdigit():
                result[key] = int(val)
            elif val in ('true', 'false'):
                result[key] = val == 'true'
            else:
                result[key] = val
    print(json.dumps(result))
    sys.exit(0)

try:
    with open('$CONFIG_FILE') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        print('{}')
        sys.exit(0)
    print(json.dumps(data))
except Exception as e:
    print(json.dumps({'_error': str(e)}), file=sys.stderr)
    print('{}')
" 2>/dev/null || {
        warn "Could not parse $CONFIG_FILE"
        echo '{}'
    }
}

# Resolve directives with 4-level precedence:
# CLI flags > .claude/orchestration.yaml > in-document directives > defaults
resolve_directives() {
    local input_file="$1"

    # Level 4: defaults (built into parse_directives)
    # Level 3: in-document directives
    local doc_directives
    doc_directives=$(parse_directives "$input_file")

    # Level 2: config file
    local config_directives
    config_directives=$(load_config_file)

    # Merge: config overrides doc
    local merged
    merged=$(echo "$doc_directives" | jq --argjson cfg "$config_directives" '
        . as $base |
        reduce ($cfg | to_entries[]) as $e ($base;
            if $e.value != null then .[$e.key] = $e.value else . end
        )
    ')

    # Level 1: CLI flags override everything
    if [[ -n "$CLI_MAX_PARALLEL" ]]; then
        merged=$(echo "$merged" | jq --argjson v "$CLI_MAX_PARALLEL" '.max_parallel = $v')
    fi

    echo "$merged"
}

# ─── State Management ────────────────────────────────────────────────

# Initialize orchestration state
