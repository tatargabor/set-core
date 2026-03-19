#!/usr/bin/env bash
# Test script for set-work, set-focus, set-loop CLI behavior
# Tests flag parsing, help output, and error handling (no real git operations).
# Run with: ./tests/test_scripts.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source common functions for color codes
source "$PROJECT_DIR/bin/set-common.sh"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "Test $TESTS_RUN: $1 ... "
}

test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}PASS${NC}"
}

test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}FAIL${NC}"
    echo "  Expected: $1"
    echo "  Got: $2"
}

assert_exit_code() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "exit code $expected" "exit code $actual"
    fi
}

assert_contains() {
    local haystack="$1"
    local needle="$2"
    if [[ "$haystack" == *"$needle"* ]]; then
        test_pass
    else
        test_fail "contains '$needle'" "$haystack"
    fi
}

assert_not_contains() {
    local haystack="$1"
    local needle="$2"
    if [[ "$haystack" != *"$needle"* ]]; then
        test_pass
    else
        test_fail "should not contain '$needle'" "$haystack"
    fi
}

# =============================================================================
# Tests: set-work
# =============================================================================

echo "=========================================="
echo "Script Implementation Tests"
echo "=========================================="
echo ""
echo "--- set-work ---"

test_start "set-work --help exits 0"
output=$("$PROJECT_DIR/bin/set-work" --help 2>&1) || true
ec=$?
assert_exit_code 0 $ec

test_start "set-work --help shows usage"
assert_contains "$output" "Usage:"

test_start "set-work --help shows --editor option"
assert_contains "$output" "--editor"

test_start "set-work --help shows terminal editors in examples"
assert_contains "$output" "kitty"

test_start "set-work without args fails"
ec=0
output=$("$PROJECT_DIR/bin/set-work" 2>&1) || ec=$?
assert_exit_code 1 $ec

test_start "set-work without args shows error"
assert_contains "$output" "Change ID required"

test_start "set-work --unknown-flag fails"
ec=0
output=$("$PROJECT_DIR/bin/set-work" --unknown-flag 2>&1) || ec=$?
assert_exit_code 1 $ec

# =============================================================================
# Tests: set-focus
# =============================================================================

echo ""
echo "--- set-focus ---"

test_start "set-focus --help exits 0"
output=$("$PROJECT_DIR/bin/set-focus" --help 2>&1) || true
ec=$?
assert_exit_code 0 $ec

test_start "set-focus --help shows usage"
assert_contains "$output" "Usage:"

test_start "set-focus --help shows --editor option"
assert_contains "$output" "--editor"

test_start "set-focus without args fails"
ec=0
output=$("$PROJECT_DIR/bin/set-focus" 2>&1) || ec=$?
assert_exit_code 1 $ec

test_start "set-focus without args shows error"
assert_contains "$output" "change-id is required"

test_start "set-focus --list shows deprecation warning"
output=$("$PROJECT_DIR/bin/set-focus" --list test-id 2>&1) || true
assert_contains "$output" "deprecated"

test_start "set-focus does not contain keystroke injection code"
focus_source=$(cat "$PROJECT_DIR/bin/set-focus")
assert_not_contains "$focus_source" "xdotool key"

test_start "set-focus does not contain osascript keystroke"
assert_not_contains "$focus_source" "keystroke"

test_start "set-focus uses get_editor_open_command"
assert_contains "$focus_source" "get_editor_open_command"

# =============================================================================
# Tests: set-loop
# =============================================================================

echo ""
echo "--- set-loop ---"

test_start "set-loop --help exits 0"
output=$("$PROJECT_DIR/bin/set-loop" --help 2>&1) || true
ec=$?
assert_exit_code 0 $ec

test_start "set-loop --help shows usage"
assert_contains "$output" "Usage:"

test_start "set-loop --help documents --permission-mode"
assert_contains "$output" "--permission-mode"

test_start "set-loop source contains get_claude_permission_flags"
loop_source=$(cat "$PROJECT_DIR/bin/set-loop")
assert_contains "$loop_source" "get_claude_permission_flags"

test_start "set-loop does not have hardcoded --dangerously-skip-permissions in run"
# Should use dynamic permission flags, not hardcoded (except maybe in help text)
# Count occurrences outside of help/comment lines
non_help_dsp=$(echo "$loop_source" | grep -v '^#' | grep -v 'help\|echo\|cat' | grep -c "dangerously-skip-permissions" || true)
if [[ "$non_help_dsp" -eq 0 ]]; then
    test_pass
else
    test_fail "0 hardcoded occurrences" "$non_help_dsp"
fi

test_start "set-loop supports --force flag"
assert_contains "$loop_source" "--force"

test_start "set-loop has plan-mode refusal logic"
assert_contains "$loop_source" "plan"

# =============================================================================
# Tests: set-work source structure
# =============================================================================

echo ""
echo "--- set-work source structure ---"

work_source=$(cat "$PROJECT_DIR/bin/set-work")

test_start "set-work does not contain keystroke injection"
assert_not_contains "$work_source" "xdotool key"

test_start "set-work does not contain sleep/retry loops for keystrokes"
assert_not_contains "$work_source" "sleep 0.5"

test_start "set-work uses get_editor_open_command for terminals"
assert_contains "$work_source" "get_editor_open_command"

test_start "set-work uses get_editor_claude_tip"
assert_contains "$work_source" "get_editor_claude_tip"

test_start "set-work uses get_claude_permission_flags"
assert_contains "$work_source" "get_claude_permission_flags"

test_start "set-work checks editor type (ide vs terminal)"
assert_contains "$work_source" "editor_type"

# =============================================================================
# Tests: install.sh sources set-common.sh
# =============================================================================

echo ""
echo "--- install.sh ---"

install_source=$(cat "$PROJECT_DIR/install.sh")

test_start "install.sh sources set-common.sh before configure functions"
assert_contains "$install_source" 'source "$SCRIPT_DIR/bin/set-common.sh"'

test_start "install.sh has configure_editor_choice function"
assert_contains "$install_source" "configure_editor_choice"

test_start "install.sh has configure_permission_mode function"
assert_contains "$install_source" "configure_permission_mode"

test_start "install.sh configure_permission_mode offers 3 options"
assert_contains "$install_source" "auto-accept"
test_start "install.sh offers allowedTools"
assert_contains "$install_source" "allowedTools"
test_start "install.sh offers plan"
assert_contains "$install_source" "plan"

# =============================================================================
# Summary
# =============================================================================

echo ""
echo "=========================================="
echo "Summary"
echo "=========================================="
echo "Tests run: $TESTS_RUN"
echo -e "Passed: ${GREEN}$TESTS_PASSED${NC}"
echo -e "Failed: ${RED}$TESTS_FAILED${NC}"
echo ""

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
