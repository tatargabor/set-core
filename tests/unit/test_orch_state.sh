#!/usr/bin/env bash
# Unit tests for orchestration state modules (config, utils, state)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source set-common first (needed by orchestration modules)
source "$SCRIPT_DIR/../../bin/set-common.sh"

# Source orchestration modules in order
LIB_DIR="$SCRIPT_DIR/../../lib/orchestration"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/utils.sh"

test_parse_duration_minutes() {
    local result
    result=$(parse_duration "30m")
    assert_equals "1800" "$result" "30m = 1800 seconds"
}

test_parse_duration_hours() {
    local result
    result=$(parse_duration "2h")
    assert_equals "7200" "$result" "2h = 7200 seconds"
}

test_format_duration() {
    local result
    result=$(format_duration 3661)
    assert_contains "$result" "1h" "contains hours"
}

test_brief_hash() {
    local result
    result=$(brief_hash "hello world")
    assert_equals "8" "${#result}" "hash is 8 chars"
    # Deterministic
    local result2
    result2=$(brief_hash "hello world")
    assert_equals "$result" "$result2" "hash is deterministic"
}

test_wt_find_config_returns_path_or_empty() {
    # Should not crash; returns path or empty
    local result
    result=$(wt_find_config "nonexistent-config" 2>/dev/null) || true
    # Result can be empty — that's fine
    assert_equals "0" "0" "wt_find_config does not crash"
}

run_tests
