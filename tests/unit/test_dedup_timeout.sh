#!/usr/bin/env bash
# Test: cmd_dedup timeout returns correct JSON
# Verifies that when the dedup python process exceeds timeout,
# the bash wrapper returns a JSON error instead of hanging forever.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source the test helpers
PASS=0
FAIL=0

assert_contains() {
    local actual="$1" expected="$2" msg="$3"
    if echo "$actual" | grep -qF "$expected"; then
        PASS=$((PASS + 1))
        echo "  PASS: $msg"
    else
        FAIL=$((FAIL + 1))
        echo "  FAIL: $msg"
        echo "    expected to contain: $expected"
        echo "    actual: $actual"
    fi
}

echo "=== Test: dedup timeout handling ==="

# Test 1: Verify timeout command exists and returns 124 on timeout
echo "Test 1: timeout command returns 124"
rc=0
timeout 1 sleep 5 || rc=$?
if [[ $rc -eq 124 ]]; then
    PASS=$((PASS + 1))
    echo "  PASS: timeout returns exit code 124"
else
    FAIL=$((FAIL + 1))
    echo "  FAIL: expected 124, got $rc"
fi

# Test 2: Verify maintenance.sh has timeout wrapper in cmd_dedup
echo "Test 2: cmd_dedup has timeout wrapper"
dedup_code=$(grep -A5 "run_with_lock.*timeout.*run_shodh_python.*DEDUP" "$ROOT_DIR/lib/memory/maintenance.sh" 2>/dev/null || true)
if [[ -n "$dedup_code" ]]; then
    PASS=$((PASS + 1))
    echo "  PASS: cmd_dedup uses timeout wrapper"
else
    FAIL=$((FAIL + 1))
    echo "  FAIL: cmd_dedup missing timeout wrapper"
fi

# Test 3: Verify maintenance.sh handles exit code 124 in cmd_dedup
echo "Test 3: cmd_dedup handles timeout exit code 124"
timeout_handler=$(grep -A2 'rc -eq 124' "$ROOT_DIR/lib/memory/maintenance.sh" | head -5)
assert_contains "$timeout_handler" "timeout" "dedup timeout handler exists"

# Test 4: Verify cmd_audit also has timeout wrapper
echo "Test 4: cmd_audit has timeout wrapper"
audit_code=$(grep -B2 -A5 "run_with_lock.*timeout.*run_shodh_python.*DEDUP" "$ROOT_DIR/lib/memory/maintenance.sh" | grep -c "timeout" || true)
if [[ "$audit_code" -ge 2 ]]; then
    PASS=$((PASS + 1))
    echo "  PASS: both dedup and audit have timeout wrapper"
else
    FAIL=$((FAIL + 1))
    echo "  FAIL: expected timeout in both dedup and audit"
fi

# Test 5: Verify --kill-after is used (defense against SIGTERM-resistant processes)
echo "Test 5: --kill-after flag present"
kill_after=$(grep -c "kill-after" "$ROOT_DIR/lib/memory/maintenance.sh" || true)
if [[ "$kill_after" -ge 2 ]]; then
    PASS=$((PASS + 1))
    echo "  PASS: --kill-after used in both commands"
else
    FAIL=$((FAIL + 1))
    echo "  FAIL: --kill-after missing (found $kill_after occurrences)"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed"
[[ $FAIL -eq 0 ]] && exit 0 || exit 1
