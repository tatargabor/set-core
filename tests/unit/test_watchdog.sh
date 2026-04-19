#!/usr/bin/env bash
# Unit tests for watchdog PID-alive guard on hash loop detection
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"
source "$SCRIPT_DIR/../lib/test_paths.sh"

# ─── Setup ───────────────────────────────────────────────────────────

setup_watchdog_env() {
    local tmp_dir
    tmp_dir=$(mktemp -d)
    export STATE_FILENAME="$(tp_state_file "$tmp_dir")"
    export PLAN_FILENAME="$(tp_plan_file "$tmp_dir")"
    export LOG_FILE="$tmp_dir/orchestration.log"
    export EVENTS_FILE="$tmp_dir/events.jsonl"
    touch "$LOG_FILE" "$EVENTS_FILE"
    echo "$tmp_dir"
}

write_state_with_watchdog() {
    local ralph_pid="$1"
    local consecutive="$2"
    cat > "$STATE_FILENAME" <<ENDSTATE
{
  "status": "running",
  "changes": [{
    "name": "test-change",
    "status": "running",
    "ralph_pid": $ralph_pid,
    "tokens_used": 100000,
    "watchdog": {
      "last_activity_epoch": $(date +%s),
      "action_hash_ring": ["aaa","aaa","aaa","aaa","aaa"],
      "consecutive_same_hash": $consecutive,
      "escalation_level": 0,
      "progress_baseline": 1
    }
  }]
}
ENDSTATE
}

# ─── Tests ───────────────────────────────────────────────────────────

test_hash_loop_pid_alive_no_escalation() {
    local tmp_dir
    tmp_dir=$(setup_watchdog_env)

    # Use current shell PID (guaranteed alive)
    write_state_with_watchdog "$$" 6

    # Source watchdog + dependencies (stub what we need)
    log_info() { echo "$*" >> "$LOG_FILE"; }
    log_warn() { echo "WARN: $*" >> "$LOG_FILE"; }
    emit_event() { echo "{\"event\":\"$1\",\"change\":\"$2\",\"data\":$3}" >> "$EVENTS_FILE"; }
    _watchdog_timeout_for_status() { echo 600; }
    _watchdog_escalate() { echo "ESCALATED $1 $2" >> "$LOG_FILE"; }
    _watchdog_update() { :; }
    _watchdog_check_progress() { :; }
    export WATCHDOG_LOOP_THRESHOLD=5
    export WATCHDOG_HASH_RING_SIZE=5

    # Source just the watchdog_check function
    source <(sed -n '/^watchdog_check()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/watchdog.sh")

    watchdog_check "test-change"

    # Should warn but NOT escalate
    local log_content
    log_content=$(cat "$LOG_FILE")
    assert_contains "$log_content" "skipping escalation" "should log PID-alive skip"
    assert_not_contains "$log_content" "ESCALATED" "should NOT escalate"

    # Should emit WATCHDOG_WARN event
    local events
    events=$(cat "$EVENTS_FILE")
    assert_contains "$events" "hash_loop_pid_alive" "should emit warn event"

    rm -rf "$tmp_dir"
}

test_hash_loop_pid_dead_escalates() {
    local tmp_dir
    tmp_dir=$(setup_watchdog_env)

    # Use PID 99999999 (guaranteed dead)
    write_state_with_watchdog "99999999" 6

    log_info() { echo "$*" >> "$LOG_FILE"; }
    log_warn() { echo "WARN: $*" >> "$LOG_FILE"; }
    emit_event() { echo "{\"event\":\"$1\",\"change\":\"$2\"}" >> "$EVENTS_FILE"; }
    _watchdog_timeout_for_status() { echo 600; }
    _watchdog_escalate() { echo "ESCALATED $1 level=$2" >> "$LOG_FILE"; }
    _watchdog_update() { :; }
    _watchdog_check_progress() { :; }
    export WATCHDOG_LOOP_THRESHOLD=5
    export WATCHDOG_HASH_RING_SIZE=5

    source <(sed -n '/^watchdog_check()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/watchdog.sh")

    watchdog_check "test-change"

    local log_content
    log_content=$(cat "$LOG_FILE")
    assert_contains "$log_content" "ESCALATED" "should escalate when PID dead"
    assert_contains "$log_content" "dead" "should mention PID dead"

    rm -rf "$tmp_dir"
}

test_below_threshold_no_action() {
    local tmp_dir
    tmp_dir=$(setup_watchdog_env)

    # Below threshold — no escalation regardless of PID
    write_state_with_watchdog "$$" 3

    log_info() { echo "$*" >> "$LOG_FILE"; }
    log_warn() { echo "WARN: $*" >> "$LOG_FILE"; }
    emit_event() { :; }
    _watchdog_timeout_for_status() { echo 600; }
    _watchdog_escalate() { echo "ESCALATED" >> "$LOG_FILE"; }
    _watchdog_update() { :; }
    _watchdog_check_progress() { :; }
    export WATCHDOG_LOOP_THRESHOLD=5
    export WATCHDOG_HASH_RING_SIZE=5

    source <(sed -n '/^watchdog_check()/,/^}/p' "$SCRIPT_DIR/../../lib/orchestration/watchdog.sh")

    watchdog_check "test-change"

    local log_content
    log_content=$(cat "$LOG_FILE")
    assert_not_contains "$log_content" "ESCALATED" "should not escalate below threshold"
    assert_not_contains "$log_content" "loop" "should not mention loop below threshold"

    rm -rf "$tmp_dir"
}

run_tests
