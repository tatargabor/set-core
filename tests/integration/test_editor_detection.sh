#!/usr/bin/env bash
# Integration test for PPID chain editor detection
# Run on a real Linux/macOS desktop with xdotool/editor available.
#
# Usage: ./tests/integration/test_editor_detection.sh
#
# Requirements:
# - Linux: xdotool installed
# - A graphical session (X11/Wayland)
# - One of: zed, code, kitty, gnome-terminal, etc.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$SCRIPT_DIR/bin/set-common.sh"

PASS=0
FAIL=0

pass() { ((PASS++)); echo "  ✓ $1"; }
fail() { ((FAIL++)); echo "  ✗ $1"; }

echo "=== PPID Chain Detection Integration Tests ==="
echo ""

# Test 1: SUPPORTED_EDITORS format
echo "Test: SUPPORTED_EDITORS format"
for entry in "${SUPPORTED_EDITORS[@]}"; do
    IFS=':' read -r name cmd etype <<< "$entry"
    if [[ -z "$name" || -z "$cmd" || -z "$etype" ]]; then
        fail "Invalid entry: $entry"
    elif [[ "$etype" != "ide" && "$etype" != "terminal" ]]; then
        fail "Invalid type for $name: $etype (expected ide|terminal)"
    else
        pass "$name: $cmd ($etype)"
    fi
done

# Test 2: Permission flags
echo ""
echo "Test: get_claude_permission_flags()"
flags=$(get_claude_permission_flags "auto-accept")
[[ "$flags" == "--dangerously-skip-permissions" ]] && pass "auto-accept → $flags" || fail "auto-accept → $flags"

flags=$(get_claude_permission_flags "allowedTools")
[[ "$flags" == *"allowedTools"* ]] && pass "allowedTools → $flags" || fail "allowedTools → $flags"

flags=$(get_claude_permission_flags "plan")
[[ -z "$flags" ]] && pass "plan → (empty)" || fail "plan → $flags"

# Test 3: Editor detection
echo ""
echo "Test: detect_available_editors()"
available=$(detect_available_editors)
if [[ -n "$available" ]]; then
    while read -r name; do
        pass "Found: $name"
    done <<< "$available"
else
    fail "No editors found"
fi

# Test 4: Editor open command
echo ""
echo "Test: get_editor_open_command()"
editor=$(get_active_editor 2>/dev/null || echo "")
if [[ -n "$editor" ]]; then
    cmd=$(get_editor_open_command "$editor" "/tmp/test-dir")
    pass "Open command for $editor: $cmd"
else
    fail "No active editor to test"
fi

# Test 5: find_window_for_agent() with own PID
echo ""
echo "Test: find_window_for_agent() [self PID]"
if [[ "$PLATFORM" == "linux" ]] && command -v xdotool &>/dev/null; then
    source "$SCRIPT_DIR/bin/set-status"
    result=$(find_window_for_agent $$ 2>/dev/null) || result=""
    if [[ -n "$result" ]]; then
        wid="${result%%|*}"
        proc="${result#*|}"
        pass "Found window $wid (process: $proc) for PID $$"
    else
        pass "No window for PID $$ (expected if running in headless terminal)"
    fi
else
    pass "Skipped (no xdotool or not Linux)"
fi

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
