#!/usr/bin/env bash
# Unit tests for lib/editor.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source dependencies (set-common.sh provides PLATFORM, CONFIG_DIR, etc.)
source "$SCRIPT_DIR/../../bin/set-common.sh"

test_supported_editors_defined() {
    assert_contains "${SUPPORTED_EDITORS[*]}" "zed:zed:ide" "has zed"
    assert_contains "${SUPPORTED_EDITORS[*]}" "vscode:code:ide" "has vscode"
    assert_contains "${SUPPORTED_EDITORS[*]}" "gnome-terminal:gnome-terminal:terminal" "has gnome-terminal"
}

test_get_editor_property_command() {
    local cmd
    cmd=$(get_editor_property "vscode" "command")
    assert_equals "code" "$cmd" "vscode command is code"
}

test_get_editor_property_type() {
    local etype
    etype=$(get_editor_property "vscode" "type")
    assert_equals "ide" "$etype" "vscode is ide"

    etype=$(get_editor_property "kitty" "type")
    assert_equals "terminal" "$etype" "kitty is terminal"
}

test_get_editor_property_invalid() {
    set +e
    get_editor_property "nonexistent-editor" "command" >/dev/null 2>&1
    local rc=$?
    set -e
    assert_equals "1" "$rc" "invalid editor returns 1"
}

test_get_supported_editor_names() {
    local names
    names=$(get_supported_editor_names)
    assert_contains "$names" "zed" "names include zed"
    assert_contains "$names" "vscode" "names include vscode"
    assert_contains "$names" "cursor" "names include cursor"
}

test_get_claude_permission_flags_modes() {
    local flags
    flags=$(get_claude_permission_flags "auto-accept")
    assert_equals "--dangerously-skip-permissions" "$flags" "auto-accept mode"

    flags=$(get_claude_permission_flags "plan")
    assert_equals "" "$flags" "plan mode has no flags"
}

test_get_editor_open_command_ide() {
    # Mock: just test the output format for an IDE
    local cmd
    cmd=$(get_editor_open_command "vscode" "/tmp/test-dir") || true
    assert_contains "$cmd" "/tmp/test-dir" "ide opens directory"
}

test_get_editor_claude_tip() {
    local tip
    tip=$(get_editor_claude_tip "zed")
    assert_contains "$tip" "Zed" "zed tip mentions Zed"

    tip=$(get_editor_claude_tip "kitty")
    assert_contains "$tip" "terminal" "terminal tip mentions terminal"
}

run_tests
