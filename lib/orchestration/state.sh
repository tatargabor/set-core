#!/usr/bin/env bash
# lib/orchestration/state.sh — State management, queries, utilities, memory helpers
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.

# ─── Duration Parsing ────────────────────────────────────────────────

# Parse a human-readable duration string into seconds.
# Supports: 30m, 4h, 2h30m, 1h15m, 90 (plain number = minutes)
# Returns 0 on invalid input.
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
        if [[ ! -f "$SPEC_OVERRIDE" ]]; then
            error "Spec file not found: $SPEC_OVERRIDE"
            return 1
        fi
        INPUT_MODE="spec"
        INPUT_PATH="$SPEC_OVERRIDE"
        return 0
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
                    if [[ "$val" =~ ^(desktop|gui|none)$ ]]; then
                        notification="$val"
                    else
                        warn "Invalid notification '$val', using default $DEFAULT_NOTIFICATION"
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
            events_max_size: $events_max_size
        }'
}

# Compute SHA-256 hash of input file
brief_hash() {
    local brief_file="$1"
    sha256sum "$brief_file" 2>/dev/null | cut -d' ' -f1 || \
    shasum -a 256 "$brief_file" 2>/dev/null | cut -d' ' -f1 || \
    echo "unknown"
}

# ─── Config & Directives ─────────────────────────────────────────────

# Load directives from .claude/orchestration.yaml
# Outputs JSON with only the keys found in the file (partial)
load_config_file() {
    if [[ ! -f "$CONFIG_FILE" ]]; then
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
init_state() {
    local plan_file="$1"

    local plan_version
    plan_version=$(jq -r '.plan_version' "$plan_file")
    local plan_brief_hash
    plan_brief_hash=$(jq -r '.brief_hash' "$plan_file")

    # Build changes array from plan
    local changes
    changes=$(jq '[.changes[] | {
        name: .name,
        scope: .scope,
        complexity: .complexity,
        change_type: (.change_type // "feature"),
        depends_on: .depends_on,
        roadmap_item: .roadmap_item,
        model: (.model // null),
        skip_review: (.skip_review // false),
        skip_test: (.skip_test // false),
        has_manual_tasks: (.has_manual_tasks // false),
        status: "pending",
        worktree_path: null,
        ralph_pid: null,
        started_at: null,
        completed_at: null,
        tokens_used: 0,
        tokens_used_prev: 0,
        test_result: null,
        smoke_result: null,


        verify_retry_count: 0
    }]' "$plan_file")

    jq -n \
        --argjson plan_version "$plan_version" \
        --arg brief_hash "$plan_brief_hash" \
        --arg created_at "$(date -Iseconds)" \
        --argjson changes "$changes" \
        '{
            plan_version: $plan_version,
            brief_hash: $brief_hash,
            status: "running",
            created_at: $created_at,
            changes: $changes,
            checkpoints: [],
            merge_queue: [],
            changes_since_checkpoint: 0,
            cycle_started_at: null
        }' > "$STATE_FILENAME"

    local change_count
    change_count=$(echo "$changes" | jq 'length')
    log_info "State initialized with $change_count changes (plan v$plan_version)"
}

# Update a top-level field in state
update_state_field() {
    local field="$1"
    local value="$2"
    local tmp
    tmp=$(mktemp)
    jq ".$field = $value" "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
}

# Update a change's field in state
# Automatically emits STATE_CHANGE event when status field changes
update_change_field() {
    local change_name="$1"
    local field="$2"
    local value="$3"

    # Capture old status before update for event emission
    local old_status=""
    if [[ "$field" == "status" ]]; then
        old_status=$(jq -r --arg name "$change_name" '.changes[] | select(.name == $name) | .status // ""' "$STATE_FILENAME" 2>/dev/null)
    fi

    local tmp
    tmp=$(mktemp)
    jq --arg name "$change_name" --argjson val "$value" \
        '(.changes[] | select(.name == $name)).'$field' = $val' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # Emit STATE_CHANGE event on status transitions
    if [[ "$field" == "status" && -n "$old_status" ]]; then
        local new_status
        new_status=$(echo "$value" | tr -d '"')
        if [[ "$old_status" != "$new_status" ]]; then
            emit_event "STATE_CHANGE" "$change_name" \
                "{\"from\":\"$old_status\",\"to\":\"$new_status\"}"
        fi
    fi

    # Emit TOKENS event on significant token updates
    if [[ "$field" == "tokens_used" ]]; then
        local prev_tokens
        prev_tokens=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .tokens_used // 0' "$STATE_FILENAME" 2>/dev/null)
        local delta=$((value - prev_tokens))
        # Only emit on significant deltas (>10K tokens)
        if [[ "$delta" -gt 10000 || "$delta" -lt -10000 ]]; then
            emit_event "TOKENS" "$change_name" \
                "{\"delta\":$delta,\"total\":$value}"
        fi
    fi
}

# Get a change's status
get_change_status() {
    local change_name="$1"
    jq -r --arg name "$change_name" '.changes[] | select(.name == $name) | .status' "$STATE_FILENAME"
}

# Get all changes with a specific status
get_changes_by_status() {
    local status="$1"
    jq -r --arg s "$status" '[.changes[] | select(.status == $s) | .name] | .[]' "$STATE_FILENAME"
}

# Count changes with a specific status
count_changes_by_status() {
    local status="$1"
    jq --arg s "$status" '[.changes[] | select(.status == $s)] | length' "$STATE_FILENAME"
}

# Check if all depends_on for a change are merged
deps_satisfied() {
    local change_name="$1"
    local deps
    deps=$(jq -r --arg name "$change_name" \
        '.changes[] | select(.name == $name) | .depends_on[]?' "$STATE_FILENAME" 2>/dev/null)

    [[ -z "$deps" ]] && return 0  # no dependencies

    while IFS= read -r dep; do
        local dep_status
        dep_status=$(get_change_status "$dep")
        if [[ "$dep_status" != "merged" ]]; then
            return 1
        fi
    done <<< "$deps"

    return 0
}

# ─── Dependency Graph ────────────────────────────────────────────────

# Topological sort of changes (returns names in execution order)
topological_sort() {
    local plan_file="$1"

    _TOPO_FILE="$plan_file" python3 -c "
import json, sys, os

with open(os.environ['_TOPO_FILE']) as f:
    plan = json.load(f)

changes = {c['name']: c.get('depends_on', []) for c in plan['changes']}

# Build adjacency: if B depends on A, then A -> B
adj = {name: [] for name in changes}
in_deg = {name: 0 for name in changes}
for name, deps in changes.items():
    for d in deps:
        if d in adj:
            adj[d].append(name)
            in_deg[name] += 1

queue = [n for n in changes if in_deg[n] == 0]
queue.sort()  # deterministic order
result = []
while queue:
    node = queue.pop(0)
    result.append(node)
    for neighbor in sorted(adj[node]):
        in_deg[neighbor] -= 1
        if in_deg[neighbor] == 0:
            queue.append(neighbor)

if len(result) != len(changes):
    print('ERROR:circular', file=sys.stderr)
    sys.exit(1)

for name in result:
    print(name)
"
}

# ─── Notifications ───────────────────────────────────────────────────

send_notification() {
    local title="$1"
    local body="$2"
    local urgency="${3:-normal}"  # normal or critical

    local notification_type="$DEFAULT_NOTIFICATION"
    # Only resolve from INPUT_PATH if already set — do NOT call find_input here
    # as it mutates global INPUT_MODE/INPUT_PATH mid-run
    if [[ -n "${INPUT_PATH:-}" && -f "$INPUT_PATH" ]]; then
        notification_type=$(resolve_directives "$INPUT_PATH" | jq -r '.notification')
    fi

    if [[ "$notification_type" == "none" ]]; then
        return 0
    fi

    if [[ "$notification_type" == "desktop" ]] && command -v notify-send &>/dev/null; then
        notify-send -u "$urgency" "$title" "$body" 2>/dev/null || true
    fi

    log_info "Notification [$urgency]: $title — $body"
}

# ─── Memory Helpers ──────────────────────────────────────────────────

# Cumulative memory operation stats (reset per orchestration run)
_MEM_OPS_COUNT=0
_MEM_OPS_TOTAL_MS=0
_MEM_RECALL_COUNT=0
_MEM_RECALL_TOTAL_MS=0

# Save a memory with source:orchestrator tag prefix.
# Usage: orch_remember "content" [type] [extra,tags]
orch_remember() {
    local content="$1"
    local type="${2:-Learning}"
    local tags="$3"
    command -v wt-memory &>/dev/null || return 0
    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))
    echo "$content" | wt-memory remember --type "$type" --tags "source:orchestrator${tags:+,$tags}" 2>/dev/null || true
    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))
    _MEM_OPS_COUNT=$((_MEM_OPS_COUNT + 1))
    _MEM_OPS_TOTAL_MS=$((_MEM_OPS_TOTAL_MS + elapsed_ms))
    log_info "Memory save: ${elapsed_ms}ms (type=$type, tags=source:orchestrator${tags:+,$tags})"
}

# Recall memories with optional tag filtering.
# Usage: orch_recall "query" [limit] [tags]
orch_recall() {
    local query="$1"
    local limit="${2:-3}"
    local tags="${3:-source:orchestrator}"
    command -v wt-memory &>/dev/null || return 0
    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))
    local result
    result=$(wt-memory recall "$query" --limit "$limit" --tags "$tags" --mode hybrid 2>/dev/null | \
        jq -r '.[].content' 2>/dev/null | head -c 2000 || true)
    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))
    local result_len=${#result}
    _MEM_RECALL_COUNT=$((_MEM_RECALL_COUNT + 1))
    _MEM_RECALL_TOTAL_MS=$((_MEM_RECALL_TOTAL_MS + elapsed_ms))
    log_info "Memory recall: ${elapsed_ms}ms, ${result_len} chars (query='${query:0:60}', limit=$limit)"
    echo "$result"
}

# Log cumulative memory stats. Called periodically from monitor loop.
orch_memory_stats() {
    local total_ops=$((_MEM_OPS_COUNT + _MEM_RECALL_COUNT))
    [[ "$total_ops" -eq 0 ]] && return 0
    local total_ms=$((_MEM_OPS_TOTAL_MS + _MEM_RECALL_TOTAL_MS))
    local avg_save_ms=0 avg_recall_ms=0
    [[ "$_MEM_OPS_COUNT" -gt 0 ]] && avg_save_ms=$((_MEM_OPS_TOTAL_MS / _MEM_OPS_COUNT))
    [[ "$_MEM_RECALL_COUNT" -gt 0 ]] && avg_recall_ms=$((_MEM_RECALL_TOTAL_MS / _MEM_RECALL_COUNT))
    log_info "Memory stats: ${total_ops} ops (${_MEM_OPS_COUNT} saves, ${_MEM_RECALL_COUNT} recalls), total ${total_ms}ms (save avg ${avg_save_ms}ms, recall avg ${avg_recall_ms}ms)"
    info "Memory: ${total_ops} ops, ${total_ms}ms total (save avg ${avg_save_ms}ms, recall avg ${avg_recall_ms}ms)"
}

# Periodic memory audit — check health + validate recent orchestrator memories.
orch_memory_audit() {
    command -v wt-memory &>/dev/null || return 0

    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))

    # 1. Health check
    if ! wt-memory health &>/dev/null 2>&1; then
        log_error "Memory audit: wt-memory health check FAILED"
        return 1
    fi

    # 2. Count orchestrator memories
    local orch_mems
    orch_mems=$(wt-memory recall "orchestration" --limit 20 --tags "source:orchestrator" --mode hybrid 2>/dev/null | jq 'length' 2>/dev/null || echo "0")

    # 3. Spot-check: most recent orchestrator memory has content
    local latest_content
    latest_content=$(wt-memory recall "orchestration" --limit 1 --tags "source:orchestrator" --mode hybrid 2>/dev/null | jq -r '.[0].content // ""' 2>/dev/null || true)
    local latest_len=${#latest_content}

    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))

    if [[ "$orch_mems" -eq 0 ]]; then
        log_info "Memory audit: OK (${elapsed_ms}ms) — no orchestrator memories yet"
    elif [[ "$latest_len" -lt 10 ]]; then
        log_warn "Memory audit: WARN (${elapsed_ms}ms) — $orch_mems memories exist but latest has only $latest_len chars"
    else
        log_info "Memory audit: OK (${elapsed_ms}ms) — $orch_mems orchestrator memories, latest: ${latest_content:0:80}..."
    fi
}

# Aggregate quality gate cost summary across all changes.
orch_gate_stats() {
    [[ ! -f "$STATE_FILENAME" ]] && return 0

    local total_gate_ms=0 total_retry_tokens=0 total_retry_count=0 changes_with_gate=0

    while IFS=$'\t' read -r name gate_ms retry_tok retry_cnt; do
        [[ -z "$name" || "$gate_ms" == "null" || "$gate_ms" == "0" ]] && continue
        total_gate_ms=$((total_gate_ms + gate_ms))
        total_retry_tokens=$((total_retry_tokens + ${retry_tok:-0}))
        total_retry_count=$((total_retry_count + ${retry_cnt:-0}))
        changes_with_gate=$((changes_with_gate + 1))
    done < <(jq -r '.changes[] | [.name, (.gate_total_ms // 0), (.gate_retry_tokens // 0), (.gate_retry_count // 0)] | @tsv' "$STATE_FILENAME" 2>/dev/null)

    [[ "$changes_with_gate" -eq 0 ]] && return 0

    local active_seconds
    active_seconds=$(jq -r '.active_seconds // 1' "$STATE_FILENAME")
    local active_ms=$((active_seconds * 1000))
    local gate_pct=0
    [[ "$active_ms" -gt 0 ]] && gate_pct=$((total_gate_ms * 100 / active_ms))

    local gate_secs=$((total_gate_ms / 1000))
    local retry_tok_k=$((total_retry_tokens / 1000))

    log_info "Gate stats: ${changes_with_gate} changes gated, total ${gate_secs}s (${gate_pct}% of active time), ${total_retry_count} retries (+${retry_tok_k}k tokens)"
    info "Quality Gate: ${gate_secs}s across ${changes_with_gate} changes (${gate_pct}% of active), ${total_retry_count} retries (+${retry_tok_k}k tokens)"
}

# ─── Subcommands: status, approve ────────────────────────────────────

cmd_status() {
    if [[ ! -f "$STATE_FILENAME" ]]; then
        if [[ -f "$PLAN_FILENAME" ]]; then
            info "Plan exists but orchestrator hasn't started. Run 'wt-orchestrate start'."
            cmd_plan --show
        else
            info "No orchestration state. Run 'wt-orchestrate plan' to create a plan."
        fi
        return 0
    fi

    local status
    status=$(jq -r '.status' "$STATE_FILENAME")
    local plan_version
    plan_version=$(jq -r '.plan_version' "$STATE_FILENAME")
    local total
    total=$(jq '.changes | length' "$STATE_FILENAME")
    local merged
    merged=$(count_changes_by_status "merged")
    local done_count
    done_count=$(count_changes_by_status "done")
    local running
    running=$(count_changes_by_status "running")
    local pending
    pending=$(count_changes_by_status "pending")
    local failed
    failed=$(count_changes_by_status "failed")
    local stalled
    stalled=$(count_changes_by_status "stalled")

    # Detect stale "running" status (process crashed without cleanup)
    if [[ "$status" == "running" ]]; then
        local state_mtime now_epoch staleness
        state_mtime=$(stat --format='%Y' "$STATE_FILENAME" 2>/dev/null || echo 0)
        now_epoch=$(date +%s)
        staleness=$((now_epoch - state_mtime))
        if [[ "$staleness" -gt 120 ]]; then
            status="stopped (stale — process crashed ~$(format_duration "$staleness") ago)"
            update_state_field "status" '"stopped"'
        fi
    fi

    echo ""
    info "═══ Orchestrator Status ═══"
    echo ""
    echo "  Status:   $status (plan v$plan_version)"
    local verifying
    verifying=$(count_changes_by_status "verifying")
    local verify_failed
    verify_failed=$(count_changes_by_status "verify-failed")

    echo "  Progress: $merged merged, $done_count done, $running running, $pending pending"
    [[ "$verifying" -gt 0 ]] && echo "  Verifying: $verifying"
    [[ "$verify_failed" -gt 0 ]] && echo "  Verify-failed: $verify_failed"
    [[ "$failed" -gt 0 ]] && echo "  Failed:   $failed"
    [[ "$stalled" -gt 0 ]] && echo "  Stalled:  $stalled"

    local waiting_budget
    waiting_budget=$(count_changes_by_status "waiting:budget")
    local budget_exceeded
    budget_exceeded=$(count_changes_by_status "budget_exceeded")
    local total_budget=$((waiting_budget + budget_exceeded))
    [[ "$total_budget" -gt 0 ]] && echo "  ⏸ Budget: $total_budget waiting for budget approval"

    local waiting_human
    waiting_human=$(count_changes_by_status "waiting:human")
    [[ "$waiting_human" -gt 0 ]] && echo "  ⏸ Human:  $waiting_human waiting for manual input"

    local replan_cycle
    replan_cycle=$(jq '.replan_cycle // 0' "$STATE_FILENAME" 2>/dev/null)
    [[ "$replan_cycle" -gt 0 ]] && echo "  Replan:   cycle $replan_cycle"

    # Show elapsed time (wall clock + active) and remaining limit
    local started_epoch
    started_epoch=$(jq -r '.started_epoch // 0' "$STATE_FILENAME" 2>/dev/null)
    local limit_secs
    limit_secs=$(jq -r '.time_limit_secs // 0' "$STATE_FILENAME" 2>/dev/null)
    local active_secs
    active_secs=$(jq -r '.active_seconds // 0' "$STATE_FILENAME" 2>/dev/null)
    if [[ "$started_epoch" -gt 0 ]]; then
        local now wall_elapsed
        now=$(date +%s)
        wall_elapsed=$((now - started_epoch))
        local time_info="  Active:   $(format_duration "$active_secs")"
        if [[ "$limit_secs" -gt 0 ]]; then
            local remaining=$((limit_secs - active_secs))
            if [[ "$remaining" -gt 0 ]]; then
                time_info="$time_info / $(format_duration "$limit_secs") limit ($(format_duration "$remaining") remaining)"
            else
                time_info="$time_info / $(format_duration "$limit_secs") limit (exceeded)"
            fi
        fi
        echo "$time_info"
        # Show wall clock if different from active (indicates wait time)
        if [[ "$wall_elapsed" -gt $((active_secs + 120)) ]]; then
            local wait_time=$((wall_elapsed - active_secs))
            echo "  Wall:     $(format_duration "$wall_elapsed") ($(format_duration "$wait_time") idle/waiting)"
        fi
    fi

    if [[ "$status" == "time_limit" ]]; then
        echo "  Note:     Stopped by time limit. Run 'wt-orchestrate start' to continue."
    fi

    # Input staleness check
    local stored_path
    stored_path=$(jq -r '.input_path // empty' "$STATE_FILENAME" 2>/dev/null)
    [[ -z "$stored_path" ]] && stored_path=$(jq -r '.input_path // empty' "$PLAN_FILENAME" 2>/dev/null)
    if [[ -z "$stored_path" ]]; then
        # Legacy: try find_brief for old state files
        stored_path=$(find_brief 2>/dev/null)
    fi
    if [[ -n "$stored_path" && -f "$stored_path" ]]; then
        local current_hash
        current_hash=$(brief_hash "$stored_path")
        local stored_hash
        stored_hash=$(jq -r '.brief_hash' "$STATE_FILENAME")
        if [[ "$current_hash" != "$stored_hash" ]]; then
            warn "  Input has changed since plan was created. Consider: wt-orchestrate replan"
        fi
    fi

    echo ""
    # Per-change table
    printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "Change" "Status" "Progress" "Tests" "Review" "Tokens" "Gate Cost"
    printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "─────────────────────────" "──────────────" "───────────────" "────────" "────────" "──────────" "──────────────"

    jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used)\t\(.test_result // "-")\t\(.review_result // "-")\t\(.gate_total_ms // 0)\t\(.gate_retry_tokens // 0)\t\(.gate_retry_count // 0)"' "$STATE_FILENAME" | \
    while IFS=$'\t' read -r name change_status tokens test_res review_res g_ms g_rtok g_rcnt; do
        local progress="-"
        # Try to read iteration progress from worktree
        local wt_path
        wt_path=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
        if [[ -n "$wt_path" && -f "$wt_path/.claude/loop-state.json" ]]; then
            local iter max_iter
            iter=$(jq -r '.current_iteration // 0' "$wt_path/.claude/loop-state.json" 2>/dev/null)
            max_iter=$(jq -r '.max_iterations // "?"' "$wt_path/.claude/loop-state.json" 2>/dev/null)
            progress="iter $iter/$max_iter"
        fi
        # Format gate cost column
        local gate_col="-"
        if [[ "$g_ms" -gt 0 ]]; then
            local g_secs=$(( g_ms / 1000 ))
            local g_frac=$(( (g_ms % 1000) / 100 ))
            gate_col="${g_secs}.${g_frac}s"
            if [[ "$g_rcnt" -gt 0 ]]; then
                local rtok_k=$(( g_rtok / 1000 ))
                gate_col="${gate_col} +${rtok_k}k"
            fi
        fi
        printf "  %-25s %-14s %-15s %-8s %-8s %-10s %-14s\n" "$name" "$change_status" "$progress" "$test_res" "$review_res" "$tokens" "$gate_col"
    done

    # Manual task hints for waiting:human changes
    if [[ "$waiting_human" -gt 0 ]]; then
        echo ""
        info "⏸ Changes waiting for manual input:"
        jq -r '.changes[] | select(.status == "waiting:human") | .name' "$STATE_FILENAME" | while read -r wh_name; do
            local wh_wt
            wh_wt=$(jq -r --arg n "$wh_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
            local wh_summary=""
            if [[ -n "$wh_wt" && -f "$wh_wt/.claude/loop-state.json" ]]; then
                wh_summary=$(jq -r '.manual_tasks[0]? | "[\(.id)] \(.description)"' "$wh_wt/.claude/loop-state.json" 2>/dev/null)
            fi
            echo "  $wh_name: ${wh_summary:-details unavailable}"
            echo "    → wt-manual show $wh_name"
        done
    fi

    # Merge queue
    local queue_size
    queue_size=$(jq '.merge_queue | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
    if [[ "$queue_size" -gt 0 ]]; then
        echo ""
        info "Merge queue ($queue_size):"
        jq -r '.merge_queue[]' "$STATE_FILENAME" | while read -r name; do
            echo "  - $name"
        done
    fi

    # Total tokens
    local total_tokens
    total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
    echo ""
    echo "  Total tokens: $total_tokens"

    # Aggregate gate costs
    local agg_gate_ms agg_retry_tok agg_retry_cnt agg_gated
    agg_gate_ms=$(jq '[.changes[].gate_total_ms // 0] | add // 0' "$STATE_FILENAME")
    agg_retry_tok=$(jq '[.changes[].gate_retry_tokens // 0] | add // 0' "$STATE_FILENAME")
    agg_retry_cnt=$(jq '[.changes[].gate_retry_count // 0] | add // 0' "$STATE_FILENAME")
    agg_gated=$(jq '[.changes[] | select((.gate_total_ms // 0) > 0)] | length' "$STATE_FILENAME")
    if [[ "$agg_gated" -gt 0 ]]; then
        local agg_secs=$((agg_gate_ms / 1000))
        local agg_frac=$(( (agg_gate_ms % 1000) / 100 ))
        local rtok_k=$((agg_retry_tok / 1000))
        local gate_pct=0
        [[ "$active_secs" -gt 0 ]] && gate_pct=$((agg_gate_ms * 100 / (active_secs * 1000)))
        echo "  Gate cost:  ${agg_secs}.${agg_frac}s across $agg_gated changes (${gate_pct}% of active), ${agg_retry_cnt} retries (+${rtok_k}k tokens)"
    fi
    echo ""
}

cmd_approve() {
    local merge_flag=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --merge) merge_flag=true; shift ;;
            *) error "Unknown option: $1"; return 1 ;;
        esac
    done

    if [[ ! -f "$STATE_FILENAME" ]]; then
        error "No orchestration state found."
        return 1
    fi

    local status
    status=$(jq -r '.status' "$STATE_FILENAME")
    if [[ "$status" != "checkpoint" ]]; then
        warn "Orchestrator is not waiting for approval (status: $status)"
        return 1
    fi

    # Mark latest checkpoint as approved
    local tmp
    tmp=$(mktemp)
    jq '(.checkpoints[-1]).approved = true' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
    update_state_field "status" '"running"'

    log_info "Checkpoint approved (merge=$merge_flag)"
    success "Checkpoint approved"

    if $merge_flag; then
        info "Executing merge queue..."
        execute_merge_queue
    fi
}

# ─── Checkpoint & Summary ────────────────────────────────────────────

trigger_checkpoint() {
    local reason="$1"

    log_info "Checkpoint triggered: $reason"
    emit_event "CHECKPOINT" "" "{\"reason\":\"$reason\"}"

    # Generate summary
    generate_summary "$reason"

    # Add checkpoint to state
    local tmp
    tmp=$(mktemp)
    jq --arg at "$(date -Iseconds)" --arg reason "$reason" \
        '.checkpoints += [{at: $at, type: $reason, approved: false}]' \
        "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # Reset counter
    update_state_field "changes_since_checkpoint" "0"

    # Send notification
    local total
    total=$(jq '.changes | length' "$STATE_FILENAME")
    local done_count
    done_count=$(jq '[.changes[] | select(.status == "done" or .status == "merged")] | length' "$STATE_FILENAME")
    local running
    running=$(count_changes_by_status "running")
    send_notification "wt-orchestrate" "Checkpoint ($reason): $done_count/$total done, $running running. Run 'wt-orchestrate approve' to continue."

    # Set status and wait for approval
    update_state_field "status" '"checkpoint"'
    info "Checkpoint: $reason. Waiting for approval..."
    info "Run 'wt-orchestrate approve' (or 'approve --merge') to continue."

    # Wait for approval
    while true; do
        sleep "$APPROVAL_POLL"
        local approved
        approved=$(jq -r '.checkpoints[-1].approved' "$STATE_FILENAME" 2>/dev/null)
        local orch_status
        orch_status=$(jq -r '.status' "$STATE_FILENAME" 2>/dev/null)
        if [[ "$approved" == "true" ]] || [[ "$orch_status" == "running" ]]; then
            log_info "Checkpoint approved"
            break
        fi
        if [[ "$orch_status" == "stopped" ]]; then
            log_info "Orchestrator stopped during checkpoint"
            return
        fi
    done
}

generate_summary() {
    local reason="$1"
    local timestamp
    timestamp=$(date -Iseconds)

    {
        echo "# Orchestration Summary"
        echo ""
        echo "**Generated:** $timestamp"
        echo "**Reason:** $reason"
        echo ""
        echo "## Changes"
        echo ""
        printf "| %-25s | %-12s | %-10s | %-8s |\n" "Change" "Status" "Tokens" "Tests"
        printf "| %-25s | %-12s | %-10s | %-8s |\n" "-------------------------" "------------" "----------" "--------"
        jq -r '.changes[] | "\(.name)\t\(.status)\t\(.tokens_used)\t\(.test_result // "-")"' "$STATE_FILENAME" | \
        while IFS=$'\t' read -r name status tokens tests; do
            printf "| %-25s | %-12s | %-10s | %-8s |\n" "$name" "$status" "$tokens" "$tests"
        done
        echo ""

        local queue_size
        queue_size=$(jq '.merge_queue | length' "$STATE_FILENAME" 2>/dev/null || echo 0)
        if [[ "$queue_size" -gt 0 ]]; then
            echo "## Merge Queue"
            echo ""
            jq -r '.merge_queue[]' "$STATE_FILENAME" | while read -r name; do
                echo "- $name"
            done
            echo ""
        fi

        local total_tokens
        total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
        echo "## Totals"
        echo ""
        echo "- **Total tokens:** $total_tokens"
        echo ""

        # Event-based timeline (if events log exists)
        if [[ -n "${EVENTS_LOG_FILE:-}" && -f "${EVENTS_LOG_FILE:-}" ]]; then
            local event_count
            event_count=$(wc -l < "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)
            if [[ "$event_count" -gt 0 ]]; then
                echo "## Event Timeline"
                echo ""
                echo "- **Total events:** $event_count"
                # Count by type
                local type_counts
                type_counts=$(jq -r '.type' "$EVENTS_LOG_FILE" 2>/dev/null | sort | uniq -c | sort -rn | head -10)
                if [[ -n "$type_counts" ]]; then
                    echo "- **By type:**"
                    echo "$type_counts" | while read -r cnt typ; do
                        echo "  - $typ: $cnt"
                    done
                fi
                # Show errors
                local error_count
                error_count=$(jq -r 'select(.type == "ERROR") | .change' "$EVENTS_LOG_FILE" 2>/dev/null | wc -l)
                if [[ "$error_count" -gt 0 ]]; then
                    echo "- **Errors:** $error_count"
                fi
                echo ""
            fi
        fi
    } > "$SUMMARY_FILENAME"

    log_info "Summary written to $SUMMARY_FILENAME"
}
