#!/usr/bin/env bash
# Unit tests for post-modularization fixes
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source set-common for shared functions
source "$SCRIPT_DIR/../../bin/set-common.sh"

# --- Test cmd_repair exists and is callable ---

test_cmd_repair_defined() {
    # Source maintenance module (needs some infra stubs)
    SHODH_PYTHON="${SHODH_PYTHON:-python3}"
    get_storage_path() { echo "/tmp/set-test-storage-$$"; }
    run_with_lock() { "$@"; }
    run_shodh_python() { "$@"; }
    cmd_health() { return 1; }  # shodh not available in test

    source "$SCRIPT_DIR/../../lib/memory/maintenance.sh" 2>/dev/null || true

    # Verify cmd_repair is defined
    if declare -f cmd_repair >/dev/null 2>&1; then
        echo "    PASS: cmd_repair is defined"
    else
        echo "    FAIL: cmd_repair is not defined"
        return 1
    fi

    # Call it — should return gracefully when health check fails
    local output
    output=$(cmd_repair 2>/dev/null)
    assert_contains "$output" "repaired" "cmd_repair returns JSON with repaired field"
}

# --- Test init_loop_state JSON escaping ---

test_init_loop_state_special_chars() {
    source "$SCRIPT_DIR/../../lib/loop/state.sh"

    local test_dir
    test_dir=$(mktemp -d)
    trap 'rm -rf "$test_dir"' RETURN
    mkdir -p "$test_dir/.claude"

    # Label with double quotes and backslash — should not corrupt JSON
    local tricky_label='test "with quotes" and \backslash'
    local tricky_change='change-name'

    # Stub variables that init_loop_state expects
    local worktree_name="test-wt"
    local task="do something"
    local done_criteria="manual"
    local max_iter=5
    local capacity_limit=80
    local stall_threshold=3
    local iteration_timeout=30
    local label="$tricky_label"
    local change="$tricky_change"

    # Signature: wt_path worktree_name task max_iter done_criteria capacity_limit stall_threshold iteration_timeout label change
    DEFAULT_STALL_THRESHOLD=3
    init_loop_state "$test_dir" "$worktree_name" "$task" "$max_iter" "$done_criteria" \
        "$capacity_limit" "$stall_threshold" "$iteration_timeout" \
        "$label" "$change"

    local state_file="$test_dir/.claude/loop-state.json"
    if [[ ! -f "$state_file" ]]; then
        echo "    FAIL: state file not created"
        return 1
    fi

    # Verify it's valid JSON
    if ! jq empty "$state_file" 2>/dev/null; then
        echo "    FAIL: state file is not valid JSON"
        cat "$state_file" >&2
        return 1
    fi

    # Verify label was preserved
    local parsed_label
    parsed_label=$(jq -r '.label' "$state_file")
    assert_contains "$parsed_label" "with quotes" "label with special chars preserved in JSON"
}

run_tests
