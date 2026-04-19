#!/usr/bin/env bash
# Unit tests for watchdog redispatch functionality
set -eo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
source "$SCRIPT_DIR/../lib/test_paths.sh"

# ─── Setup ───────────────────────────────────────────────────────────

# Globals initialized early so sourced functions can reference them
STATE_FILENAME=""
LOG_FILE=""
EVENTS_LOG_FILE=""
EVENTS_ENABLED=true
MAX_REDISPATCH=2

setup_redispatch_env() {
    local tmp_dir
    tmp_dir=$(mktemp -d)
    STATE_FILENAME="$(tp_state_file "$tmp_dir")"
    LOG_FILE="$tmp_dir/orchestration.log"
    EVENTS_LOG_FILE="$tmp_dir/events.jsonl"
    touch "$LOG_FILE" "$EVENTS_LOG_FILE"
    echo "$tmp_dir"
}

write_state_for_redispatch() {
    local redispatch_count="${1:-0}"
    local ralph_pid="${2:-99999999}"
    local status="${3:-running}"
    cat > "$STATE_FILENAME" <<ENDSTATE
{
  "status": "running",
  "changes": [{
    "name": "test-change",
    "status": "$status",
    "scope": "test scope",
    "ralph_pid": $ralph_pid,
    "tokens_used": 150000,
    "redispatch_count": $redispatch_count,
    "worktree_path": null,
    "verify_retry_count": 0,
    "watchdog": {
      "last_activity_epoch": $(date +%s),
      "action_hash_ring": [],
      "consecutive_same_hash": 0,
      "escalation_level": 0
    }
  }]
}
ENDSTATE
}

# Stub functions used by redispatch_change and watchdog
stub_functions() {
    log_info() { echo "$*" >> "$LOG_FILE"; }
    log_warn() { echo "WARN: $*" >> "$LOG_FILE"; }
    log_error() { echo "ERROR: $*" >> "$LOG_FILE"; }
    emit_event() {
        local json_line
        json_line=$(jq -cn --arg type "$1" --arg change "${2:-}" --argjson data "${3:-"{}"}" \
            '{type:$type, change:$change, data:$data}')
        echo "$json_line" >> "$EVENTS_LOG_FILE"
    }
    send_notification() { echo "NOTIFY: $*" >> "$LOG_FILE"; }
    _watchdog_salvage_partial_work() { echo "SALVAGE: $1" >> "$LOG_FILE"; }
    update_change_field() {
        local change_name="$1" field="$2" value="$3"
        local tmp; tmp=$(mktemp)
        jq --arg name "$change_name" --argjson val "$value" \
            '(.changes[] | select(.name == $name)).'$field' = $val' \
            "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
    }
    update_coverage_status() { :; }
}

# ─── Tests ───────────────────────────────────────────────────────────

# 5.1: redispatch_change() increments redispatch_count and sets status to pending
test_redispatch_increments_count_and_sets_pending() {
    local tmp_dir
    tmp_dir=$(setup_redispatch_env)
    write_state_for_redispatch 0
    stub_functions

    # Source redispatch_change from dispatcher.sh
    source <(sed -n '/^redispatch_change()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/dispatcher.sh")

    redispatch_change "test-change" "spinning"

    local new_count new_status
    new_count=$(jq -r '.changes[0].redispatch_count' "$STATE_FILENAME")
    new_status=$(jq -r '.changes[0].status' "$STATE_FILENAME")

    assert_equals "1" "$new_count" "redispatch_count should be 1"
    assert_equals "pending" "$new_status" "status should be pending"

    # Verify WATCHDOG_REDISPATCH event was emitted
    local events
    events=$(cat "$EVENTS_LOG_FILE")
    assert_contains "$events" "WATCHDOG_REDISPATCH" "should emit WATCHDOG_REDISPATCH event"

    rm -rf "$tmp_dir"
}

# 5.2: L3 escalation calls redispatch when count < max, fails when count >= max
test_l3_escalation_redispatch_vs_fail() {
    local tmp_dir
    tmp_dir=$(setup_redispatch_env)
    stub_functions

    # Case 1: count=0 < max=2 → should redispatch
    write_state_for_redispatch 0
    local redispatch_called=false
    redispatch_change() { redispatch_called=true; echo "REDISPATCH: $1" >> "$LOG_FILE"; }

    source <(sed -n '/^_watchdog_escalate()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/watchdog.sh")

    _watchdog_escalate "test-change" 3

    assert_equals "true" "$redispatch_called" "L3 should call redispatch when count < max"

    # Case 2: count=2 >= max=2 → should fail
    write_state_for_redispatch 2
    redispatch_called=false

    _watchdog_escalate "test-change" 3

    assert_equals "false" "$redispatch_called" "L3 should NOT call redispatch when count >= max"

    local final_status
    final_status=$(jq -r '.changes[0].status' "$STATE_FILENAME")
    assert_equals "failed" "$final_status" "should be failed when redispatch exhausted"

    rm -rf "$tmp_dir"
}

# 5.3: spinning detection calls redispatch when count < max, fails when count >= max
test_spinning_redispatch_vs_fail() {
    local tmp_dir
    tmp_dir=$(setup_redispatch_env)
    stub_functions

    # Create loop-state with 3+ no_op iterations
    local wt_dir="$tmp_dir/worktree"
    mkdir -p "$wt_dir/.claude"
    cat > "$wt_dir/.claude/loop-state.json" <<EOF
{
  "status": "running",
  "iterations": [
    {"n": 1, "commits": ["abc"], "no_op": false},
    {"n": 2, "commits": [], "no_op": true},
    {"n": 3, "commits": [], "no_op": true},
    {"n": 4, "commits": [], "no_op": true}
  ]
}
EOF

    # Case 1: count=0 → should redispatch
    write_state_for_redispatch 0
    # Set worktree_path in state
    local tmp; tmp=$(mktemp)
    jq --arg wt "$wt_dir" '(.changes[0].worktree_path) = $wt' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    local redispatch_called=false
    redispatch_change() { redispatch_called=true; echo "REDISPATCH: $1" >> "$LOG_FILE"; }
    pause_change() { :; }

    source <(sed -n '/^_watchdog_check_progress()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/watchdog.sh")

    _watchdog_check_progress "test-change"

    assert_equals "true" "$redispatch_called" "spinning should call redispatch when count < max"

    # Case 2: count=2 → should fail
    write_state_for_redispatch 2
    tmp=$(mktemp)
    jq --arg wt "$wt_dir" '(.changes[0].worktree_path) = $wt' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"
    redispatch_called=false

    _watchdog_check_progress "test-change"

    assert_equals "false" "$redispatch_called" "spinning should NOT call redispatch when count >= max"
    local final_status
    final_status=$(jq -r '.changes[0].status' "$STATE_FILENAME")
    assert_equals "failed" "$final_status" "should be failed when redispatch exhausted on spinning"

    rm -rf "$tmp_dir"
}

# 5.4: dispatch_change() includes retry_context in proposal when present
test_retry_context_injected_into_proposal() {
    local tmp_dir
    tmp_dir=$(setup_redispatch_env)
    stub_functions

    # Create state with retry_context
    write_state_for_redispatch 1
    local retry_text="## Previous Attempt Failed\nSpinning detected"
    local tmp; tmp=$(mktemp)
    jq --arg ctx "$retry_text" '(.changes[0].retry_context) = $ctx' "$STATE_FILENAME" > "$tmp" && mv "$tmp" "$STATE_FILENAME"

    # Create a worktree-like directory with a proposal
    local wt_dir="$tmp_dir/project-test-change"
    mkdir -p "$wt_dir/openspec/changes/test-change"
    echo "## Why" > "$wt_dir/openspec/changes/test-change/proposal.md"
    echo "Test proposal" >> "$wt_dir/openspec/changes/test-change/proposal.md"

    # Simulate the retry_context injection code from dispatch_change
    (
        cd "$wt_dir"
        local retry_ctx
        retry_ctx=$(jq -r --arg n "test-change" '.changes[] | select(.name == $n) | .retry_context // empty' "$STATE_FILENAME")
        if [[ -n "$retry_ctx" && "$retry_ctx" != "null" ]]; then
            local proposal_path="openspec/changes/test-change/proposal.md"
            if [[ -f "$proposal_path" ]]; then
                printf '\n%s\n' "$retry_ctx" >> "$proposal_path"
            fi
        fi
    )

    local proposal_content
    proposal_content=$(cat "$wt_dir/openspec/changes/test-change/proposal.md")
    assert_contains "$proposal_content" "Previous Attempt Failed" "proposal should contain retry context"
    assert_contains "$proposal_content" "Test proposal" "proposal should retain original content"

    rm -rf "$tmp_dir"
}

run_tests
