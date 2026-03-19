#!/usr/bin/env bash
# Test script for editor detection and configuration functionality
# Tests the new 3-field format, permission modes, and editor open commands.
# Run with: ./tests/test_editor_detection.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source common functions
source "$PROJECT_DIR/bin/set-common.sh"

# Test counters
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

# Test helpers
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

assert_equals() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "$expected" "$actual"
    fi
}

assert_not_empty() {
    local actual="$1"
    if [[ -n "$actual" ]]; then
        test_pass
    else
        test_fail "non-empty string" "(empty)"
    fi
}

assert_empty() {
    local actual="$1"
    if [[ -z "$actual" ]]; then
        test_pass
    else
        test_fail "(empty)" "$actual"
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

# =============================================================================
# Tests: SUPPORTED_EDITORS format (3-field: name:command:type)
# =============================================================================

echo "=========================================="
echo "Editor Detection Tests (3-field format)"
echo "=========================================="
echo ""

echo "--- SUPPORTED_EDITORS array ---"

test_start "SUPPORTED_EDITORS array exists and is non-empty"
if [[ ${#SUPPORTED_EDITORS[@]} -gt 0 ]]; then
    test_pass
else
    test_fail "non-empty array" "empty or undefined"
fi

test_start "SUPPORTED_EDITORS has at least 10 entries (IDEs + terminals)"
if [[ ${#SUPPORTED_EDITORS[@]} -ge 10 ]]; then
    test_pass
else
    test_fail ">=10" "${#SUPPORTED_EDITORS[@]}"
fi

test_start "All entries have 3-field format (name:command:type)"
all_valid=true
for entry in "${SUPPORTED_EDITORS[@]}"; do
    IFS=':' read -r name cmd etype <<< "$entry"
    if [[ -z "$name" || -z "$cmd" || -z "$etype" ]]; then
        all_valid=false
        break
    fi
done
if $all_valid; then
    test_pass
else
    test_fail "all valid 3-field" "found invalid entry"
fi

test_start "All entries have type=ide or type=terminal"
all_valid=true
for entry in "${SUPPORTED_EDITORS[@]}"; do
    IFS=':' read -r name cmd etype <<< "$entry"
    if [[ "$etype" != "ide" && "$etype" != "terminal" ]]; then
        all_valid=false
        break
    fi
done
if $all_valid; then
    test_pass
else
    test_fail "all ide|terminal" "found invalid type"
fi

# =============================================================================
# Tests: get_editor_property (new 2-property format: command, type)
# =============================================================================

echo ""
echo "--- get_editor_property ---"

test_start "zed command = zed"
result=$(get_editor_property "zed" "command")
assert_equals "zed" "$result"

test_start "zed type = ide"
result=$(get_editor_property "zed" "type")
assert_equals "ide" "$result"

test_start "vscode command = code"
result=$(get_editor_property "vscode" "command")
assert_equals "code" "$result"

test_start "vscode type = ide"
result=$(get_editor_property "vscode" "type")
assert_equals "ide" "$result"

test_start "kitty command = kitty"
result=$(get_editor_property "kitty" "command")
assert_equals "kitty" "$result"

test_start "kitty type = terminal"
result=$(get_editor_property "kitty" "type")
assert_equals "terminal" "$result"

test_start "alacritty type = terminal"
result=$(get_editor_property "alacritty" "type")
assert_equals "terminal" "$result"

test_start "wezterm type = terminal"
result=$(get_editor_property "wezterm" "type")
assert_equals "terminal" "$result"

test_start "gnome-terminal type = terminal"
result=$(get_editor_property "gnome-terminal" "type")
assert_equals "terminal" "$result"

test_start "invalid editor returns error"
if get_editor_property "invalid_editor" "command" 2>/dev/null; then
    test_fail "should fail" "succeeded"
else
    test_pass
fi

# =============================================================================
# Tests: get_supported_editor_names
# =============================================================================

echo ""
echo "--- get_supported_editor_names ---"

test_start "returns zed"
result=$(get_supported_editor_names | tr '\n' ' ')
assert_contains "$result" "zed"

test_start "returns vscode"
assert_contains "$result" "vscode"

test_start "returns kitty"
assert_contains "$result" "kitty"

test_start "returns alacritty"
assert_contains "$result" "alacritty"

test_start "returns gnome-terminal"
assert_contains "$result" "gnome-terminal"

# =============================================================================
# Tests: detect_available_editors
# =============================================================================

echo ""
echo "--- detect_available_editors ---"

test_start "runs without error"
result=$(detect_available_editors 2>&1) || result="error"
if [[ "$result" != "error" ]]; then
    test_pass
else
    test_fail "successful run" "error"
fi

# =============================================================================
# Tests: get_active_editor
# =============================================================================

echo ""
echo "--- get_active_editor ---"

test_start "returns editor name"
result=$(get_active_editor) || result=""
assert_not_empty "$result"

# =============================================================================
# Tests: find_editor
# =============================================================================

echo ""
echo "--- find_editor ---"

test_start "returns command path"
result=$(find_editor) || result=""
assert_not_empty "$result"

# =============================================================================
# Tests: Configuration (with temp config dir)
# =============================================================================

echo ""
echo "--- Configuration (temp config) ---"
export WT_CONFIG_DIR=$(mktemp -d)
mkdir -p "$WT_CONFIG_DIR"

test_start "get_configured_editor default is auto"
ensure_editor_config
result=$(get_configured_editor)
assert_equals "auto" "$result"

test_start "set_configured_editor to vscode"
set_configured_editor "vscode"
result=$(get_configured_editor)
assert_equals "vscode" "$result"

test_start "set_configured_editor to kitty (terminal)"
set_configured_editor "kitty"
result=$(get_configured_editor)
assert_equals "kitty" "$result"

test_start "set_configured_editor rejects invalid editor"
if set_configured_editor "invalid_editor" 2>/dev/null; then
    test_fail "should fail" "succeeded"
else
    test_pass
fi

test_start "set_configured_editor to auto"
set_configured_editor "auto"
result=$(get_configured_editor)
assert_equals "auto" "$result"

# =============================================================================
# Tests: Permission Mode
# =============================================================================

echo ""
echo "--- Permission Mode ---"

test_start "get_claude_permission_mode default is auto-accept"
result=$(get_claude_permission_mode)
assert_equals "auto-accept" "$result"

test_start "set_claude_permission_mode to allowedTools"
set_claude_permission_mode "allowedTools"
result=$(get_claude_permission_mode)
assert_equals "allowedTools" "$result"

test_start "set_claude_permission_mode to plan"
set_claude_permission_mode "plan"
result=$(get_claude_permission_mode)
assert_equals "plan" "$result"

test_start "set_claude_permission_mode to auto-accept"
set_claude_permission_mode "auto-accept"
result=$(get_claude_permission_mode)
assert_equals "auto-accept" "$result"

test_start "set_claude_permission_mode rejects invalid mode"
if set_claude_permission_mode "invalid-mode" 2>/dev/null; then
    test_fail "should fail" "succeeded"
else
    test_pass
fi

# =============================================================================
# Tests: get_claude_permission_flags
# =============================================================================

echo ""
echo "--- get_claude_permission_flags ---"

test_start "auto-accept returns --dangerously-skip-permissions"
result=$(get_claude_permission_flags "auto-accept")
assert_equals "--dangerously-skip-permissions" "$result"

test_start "allowedTools returns --allowedTools flag"
result=$(get_claude_permission_flags "allowedTools")
assert_contains "$result" "allowedTools"

test_start "plan returns empty string"
result=$(get_claude_permission_flags "plan")
assert_empty "$result"

test_start "default (no arg) reads from config"
set_claude_permission_mode "plan"
result=$(get_claude_permission_flags)
assert_empty "$result"

test_start "default auto-accept from config"
set_claude_permission_mode "auto-accept"
result=$(get_claude_permission_flags)
assert_equals "--dangerously-skip-permissions" "$result"

# =============================================================================
# Tests: get_editor_open_command
# =============================================================================

echo ""
echo "--- get_editor_open_command ---"

test_start "zed (ide) returns 'zed <dir>'"
result=$(get_editor_open_command "zed" "/tmp/test-dir")
assert_contains "$result" "/tmp/test-dir"

test_start "kitty returns --directory flag"
result=$(get_editor_open_command "kitty" "/tmp/test-dir")
assert_contains "$result" "--directory"

test_start "alacritty returns --working-directory flag"
result=$(get_editor_open_command "alacritty" "/tmp/test-dir")
assert_contains "$result" "--working-directory"

test_start "wezterm returns start --cwd"
result=$(get_editor_open_command "wezterm" "/tmp/test-dir")
assert_contains "$result" "start --cwd"

test_start "konsole returns --workdir"
result=$(get_editor_open_command "konsole" "/tmp/test-dir")
assert_contains "$result" "--workdir"

# =============================================================================
# Tests: get_editor_claude_tip
# =============================================================================

echo ""
echo "--- get_editor_claude_tip ---"

test_start "zed tip mentions Ctrl+Shift+L"
result=$(get_editor_claude_tip "zed")
assert_contains "$result" "Ctrl+Shift+L"

test_start "cursor tip mentions Ctrl+L"
result=$(get_editor_claude_tip "cursor")
assert_contains "$result" "Ctrl+L"

test_start "kitty tip mentions 'claude'"
result=$(get_editor_claude_tip "kitty")
assert_contains "$result" "claude"

test_start "vscode tip mentions terminal"
result=$(get_editor_claude_tip "vscode")
assert_contains "$result" "terminal"

# =============================================================================
# Tests: get_editor_type
# =============================================================================

echo ""
echo "--- get_editor_type ---"

test_start "returns ide or terminal for active editor"
result=$(get_editor_type) || result=""
if [[ "$result" == "ide" || "$result" == "terminal" ]]; then
    test_pass
else
    test_fail "ide or terminal" "$result"
fi

# Cleanup
rm -rf "$WT_CONFIG_DIR"

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
