#!/usr/bin/env bash
# Unit tests for safe_jq_update and with_state_lock
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source set-common first (needed by orchestration modules)
source "$SCRIPT_DIR/../../bin/set-common.sh"

# Source orchestration modules in order
LIB_DIR="$SCRIPT_DIR/../../lib/orchestration"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/utils.sh"

# Stubs for orchestration functions defined in bin/set-orchestrate
log_error() { echo "[ERROR] $*" >&2; }
log_info() { :; }
log_warn() { :; }
emit_event() { :; }
run_hook() { :; }

# Source state.sh for get_change_status, get_changes_by_status, etc.
source "$LIB_DIR/state.sh"

# ─── Setup / Teardown ────────────────────────────────────────────────

_TMPDIR=""
setup() {
    _TMPDIR=$(mktemp -d)
}

teardown() {
    rm -rf "$_TMPDIR"
}

# ─── safe_jq_update tests ────────────────────────────────────────────

test_safe_jq_update_success() {
    setup
    local f="$_TMPDIR/test.json"
    echo '{"status":"running"}' > "$f"

    safe_jq_update "$f" '.status = "done"'
    local result
    result=$(jq -r '.status' "$f")
    assert_equals "done" "$result" "status updated to done"
    teardown
}

test_safe_jq_update_preserves_on_bad_filter() {
    setup
    local f="$_TMPDIR/test.json"
    echo '{"status":"running"}' > "$f"
    local original
    original=$(cat "$f")

    set +e
    safe_jq_update "$f" '.invalid[[' 2>/dev/null
    local rc=$?
    set -e

    assert_equals "1" "$rc" "returns 1 on bad filter"
    local after
    after=$(cat "$f")
    assert_equals "$original" "$after" "file unchanged after bad filter"
    teardown
}

test_safe_jq_update_preserves_on_invalid_json() {
    setup
    local f="$_TMPDIR/test.json"
    echo 'not json at all' > "$f"
    local original
    original=$(cat "$f")

    set +e
    safe_jq_update "$f" '.status = "done"' 2>/dev/null
    local rc=$?
    set -e

    assert_equals "1" "$rc" "returns 1 on invalid source JSON"
    local after
    after=$(cat "$f")
    assert_equals "$original" "$after" "file unchanged after invalid JSON"
    teardown
}

test_safe_jq_update_cleans_temp_on_failure() {
    setup
    local f="$_TMPDIR/test.json"
    echo '{"x":1}' > "$f"

    local before_count
    before_count=$(find /tmp -maxdepth 1 -name 'tmp.*' -newer "$f" 2>/dev/null | wc -l)

    set +e
    safe_jq_update "$f" '.invalid[[' 2>/dev/null
    set -e

    local after_count
    after_count=$(find /tmp -maxdepth 1 -name 'tmp.*' -newer "$f" 2>/dev/null | wc -l)
    # Should not have leaked temp files
    assert_equals "$before_count" "$after_count" "no temp file leaked"
    teardown
}

test_safe_jq_update_complex_filter() {
    setup
    local f="$_TMPDIR/test.json"
    echo '{"changes":[{"name":"a","status":"running"},{"name":"b","status":"pending"}]}' > "$f"

    safe_jq_update "$f" --arg n "a" --arg s "merged" \
        '(.changes[] | select(.name == $n)).status = $s'

    local result
    result=$(jq -r '.changes[] | select(.name == "a") | .status' "$f")
    assert_equals "merged" "$result" "complex filter updates nested field"
    teardown
}

# ─── with_state_lock tests ───────────────────────────────────────────

test_with_state_lock_executes_command() {
    setup
    local f="$_TMPDIR/state.json"
    echo '{"status":"running"}' > "$f"
    STATE_FILENAME="$f"

    with_state_lock bash -c 'echo "locked" > "'"$_TMPDIR"'/proof.txt"'
    local result
    result=$(cat "$_TMPDIR/proof.txt")
    assert_equals "locked" "$result" "command executed under lock"
    teardown
}

test_with_state_lock_returns_command_exit_code() {
    setup
    local f="$_TMPDIR/state.json"
    echo '{}' > "$f"
    STATE_FILENAME="$f"

    set +e
    with_state_lock bash -c 'exit 42'
    local rc=$?
    set -e

    assert_equals "42" "$rc" "propagates wrapped command exit code"
    teardown
}

test_with_state_lock_creates_lock_file() {
    setup
    local f="$_TMPDIR/state.json"
    echo '{}' > "$f"
    STATE_FILENAME="$f"

    with_state_lock true
    assert_file_exists "${f}.lock" "lock file created"
    teardown
}

# ─── State corruption detection tests ────────────────────────────────

test_get_change_status_rejects_corrupt_json() {
    setup
    local f="$_TMPDIR/state.json"
    echo 'NOT VALID JSON' > "$f"
    STATE_FILENAME="$f"

    set +e
    local result
    result=$(get_change_status "test-change" 2>/dev/null)
    local rc=$?
    set -e

    assert_equals "1" "$rc" "returns 1 on corrupt JSON"
    teardown
}

test_get_changes_by_status_rejects_corrupt_json() {
    setup
    local f="$_TMPDIR/state.json"
    echo '{broken' > "$f"
    STATE_FILENAME="$f"

    set +e
    local result
    result=$(get_changes_by_status "running" 2>/dev/null)
    local rc=$?
    set -e

    assert_equals "1" "$rc" "returns 1 on corrupt JSON"
    teardown
}

test_safe_jq_update_refuses_corrupt_state() {
    setup
    local f="$_TMPDIR/state.json"
    echo 'CORRUPT' > "$f"
    local original
    original=$(cat "$f")

    set +e
    safe_jq_update "$f" '.status = "done"' 2>/dev/null
    local rc=$?
    set -e

    assert_equals "1" "$rc" "returns 1 on corrupt input"
    local after
    after=$(cat "$f")
    assert_equals "$original" "$after" "file unchanged"
    teardown
}

run_tests
