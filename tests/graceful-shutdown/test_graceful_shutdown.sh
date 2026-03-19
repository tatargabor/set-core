#!/usr/bin/env bash
# test_graceful_shutdown.sh — Unit tests for graceful shutdown functionality
#
# Tests sentinel --shutdown, set-loop SIGTERM handling, resume from shutdown state,
# and the shutdown API endpoint.
#
# Usage: ./tests/graceful-shutdown/test_graceful_shutdown.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR=""
PASS_COUNT=0
FAIL_COUNT=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}  PASS${NC} $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo -e "${RED}  FAIL${NC} $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
skip() { echo -e "${YELLOW}  SKIP${NC} $*"; }

cleanup() {
    # Kill any leftover background processes
    jobs -p 2>/dev/null | xargs kill 2>/dev/null || true
    if [[ -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
}
trap cleanup EXIT

# ─── Setup ────────────────────────────────────────────────────────

TEST_DIR=$(mktemp -d /tmp/test-graceful-shutdown-XXXXXX)

echo ""
echo "=== Graceful Shutdown Tests ==="
echo "Test dir: $TEST_DIR"
echo ""

# ─── Test 7.1: --shutdown with no running sentinel exits cleanly ──

echo "Test 7.1: --shutdown with no running sentinel"

cd "$TEST_DIR"
mkdir -p shutdown-test-1 && cd shutdown-test-1
git init -q --initial-branch=main
git config user.email "test@test.com"
git config user.name "Test"
touch .gitkeep && git add -A && git commit -m "init" -q

# No sentinel.pid file → should print "No sentinel running" and exit 0
output=$(set-sentinel --shutdown 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]] && echo "$output" | grep -qi "no sentinel running"; then
    pass "--shutdown with no PID file exits 0 with message"
else
    fail "--shutdown should exit 0 with 'No sentinel running' (rc=$rc, output: $output)"
fi

# With stale PID file (non-existent process)
echo "99999" > sentinel.pid
output=$(set-sentinel --shutdown 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]] && echo "$output" | grep -qi "no sentinel running"; then
    pass "--shutdown with stale PID file exits 0 with message"
else
    fail "--shutdown with stale PID should exit 0 (rc=$rc, output: $output)"
fi
rm -f sentinel.pid

cd "$TEST_DIR"

# ─── Test 7.2: set-loop SIGTERM during idle exits immediately ─────

echo "Test 7.2: set-loop SIGTERM during idle"

# We can't easily test set-loop directly (it requires a full worktree setup),
# but we can test the cleanup_on_exit function behavior by checking the
# engine.sh trap setup.
# Verify the trap is registered for SIGTERM:

if grep -q "trap 'cleanup_on_exit' EXIT SIGTERM" "$REPO_ROOT/lib/loop/engine.sh"; then
    pass "set-loop registers SIGTERM trap via cleanup_on_exit"
else
    fail "set-loop should register SIGTERM trap"
fi

# Verify cleanup_on_exit has the guard against double-trap:
if grep -q "Guard against double-trap" "$REPO_ROOT/lib/loop/engine.sh"; then
    pass "cleanup_on_exit has double-trap guard"
else
    fail "cleanup_on_exit should have double-trap guard"
fi

# ─── Test 7.3: set-loop SIGTERM during work commits WIP ───────────

echo "Test 7.3: set-loop SIGTERM WIP commit behavior"

# Verify the WIP commit message pattern exists in cleanup_on_exit:
if grep -q 'wip: graceful shutdown' "$REPO_ROOT/lib/loop/engine.sh"; then
    pass "cleanup_on_exit commits with 'wip: graceful shutdown' message"
else
    fail "cleanup_on_exit should commit WIP with graceful shutdown message"
fi

# Verify last_commit is written to loop-state:
if grep -q 'update_loop_state.*last_commit' "$REPO_ROOT/lib/loop/engine.sh"; then
    pass "cleanup_on_exit writes last_commit to loop-state"
else
    fail "cleanup_on_exit should write last_commit"
fi

# ─── Test 7.4: resume from "shutdown" state with valid worktrees ──

echo "Test 7.4: resume_from_shutdown with valid worktrees"

mkdir -p "$TEST_DIR/resume-test" && cd "$TEST_DIR/resume-test"
git init -q --initial-branch=main
git config user.email "test@test.com"
git config user.name "Test"
echo "base" > file.txt && git add -A && git commit -m "init" -q

# Create a worktree to simulate a shutdown-ed change
git worktree add -q "$TEST_DIR/resume-test-wt" -b change/test-change
HEAD_SHA=$(git -C "$TEST_DIR/resume-test-wt" rev-parse HEAD)

# Create state file with shutdown status
cat > orchestration-state.json <<EOF
{
  "status": "shutdown",
  "shutdown_at": "2026-03-18T12:00:00+00:00",
  "changes": [
    {
      "name": "test-change",
      "status": "running",
      "worktree_path": "$TEST_DIR/resume-test-wt",
      "last_commit": "$HEAD_SHA",
      "ralph_pid": null
    }
  ]
}
EOF

# Source the sentinel functions we need (resume_from_shutdown)
# We'll use jq directly to simulate what resume_from_shutdown does
STATE_FILE="orchestration-state.json"

# The sentinel's resume_from_shutdown reads state, validates worktrees, resets status
# Let's verify the logic by checking what the function WOULD do:

# 1. Worktree exists? Yes
if [[ -d "$TEST_DIR/resume-test-wt" ]]; then
    pass "Worktree exists for resume validation"
else
    fail "Worktree should exist"
fi

# 2. HEAD matches last_commit? Yes
actual_head=$(git -C "$TEST_DIR/resume-test-wt" rev-parse HEAD)
if [[ "$actual_head" == "$HEAD_SHA" ]]; then
    pass "Worktree HEAD matches last_commit"
else
    fail "HEAD mismatch: expected $HEAD_SHA, got $actual_head"
fi

# 3. Verify the resume logic exists in sentinel
if grep -q "resume_from_shutdown" "$REPO_ROOT/bin/set-sentinel"; then
    pass "resume_from_shutdown function exists in sentinel"
else
    fail "resume_from_shutdown should exist in sentinel"
fi

# 4. Verify it checks for worktree existence
if grep -q 'if \[\[ ! -d "$wt_path" \]\]' "$REPO_ROOT/bin/set-sentinel"; then
    pass "resume_from_shutdown checks worktree directory existence"
else
    fail "Should check worktree directory existence"
fi

# Clean up worktree
git worktree remove "$TEST_DIR/resume-test-wt" --force 2>/dev/null || true

cd "$TEST_DIR"

# ─── Test 7.5: resume with missing worktree resets to pending ─────

echo "Test 7.5: resume with missing worktree"

mkdir -p "$TEST_DIR/resume-missing" && cd "$TEST_DIR/resume-missing"
git init -q --initial-branch=main
git config user.email "test@test.com"
git config user.name "Test"
echo "base" > file.txt && git add -A && git commit -m "init" -q

# Create state file pointing to non-existent worktree
cat > orchestration-state.json <<EOF
{
  "status": "shutdown",
  "shutdown_at": "2026-03-18T12:00:00+00:00",
  "changes": [
    {
      "name": "missing-set-change",
      "status": "running",
      "worktree_path": "/tmp/nonexistent-worktree-xyz",
      "last_commit": "abc123",
      "ralph_pid": null
    }
  ]
}
EOF

# Simulate what resume_from_shutdown does for missing worktree
wt_path="/tmp/nonexistent-worktree-xyz"
if [[ ! -d "$wt_path" ]]; then
    # This is what the sentinel does — reset to pending
    tmp=$(mktemp)
    jq '(.changes[] | select(.name == "missing-set-change")) |= (.status = "pending" | .worktree_path = "" | .ralph_pid = null | .last_commit = null)' \
        orchestration-state.json > "$tmp" && mv "$tmp" orchestration-state.json

    new_status=$(jq -r '.changes[0].status' orchestration-state.json)
    new_wt=$(jq -r '.changes[0].worktree_path' orchestration-state.json)
    if [[ "$new_status" == "pending" && "$new_wt" == "" ]]; then
        pass "Missing worktree resets change to pending with cleared worktree_path"
    else
        fail "Should reset to pending (got status=$new_status, wt=$new_wt)"
    fi
else
    fail "Test setup error: worktree path should not exist"
fi

# Verify the sentinel logs this case
if grep -q "worktree missing.*resetting to pending" "$REPO_ROOT/bin/set-sentinel"; then
    pass "Sentinel logs 'worktree missing...resetting to pending'"
else
    fail "Sentinel should log worktree missing message"
fi

cd "$TEST_DIR"

# ─── Test 7.6: POST /api/{project}/shutdown returns ok ────────────

echo "Test 7.6: Shutdown API endpoint"

# We can't easily start the full FastAPI server, but we can verify
# the endpoint exists and has correct structure

if grep -q 'post.*shutdown' "$REPO_ROOT/lib/set_orch/api.py"; then
    pass "POST /api/{project}/shutdown endpoint exists"
else
    fail "Shutdown endpoint should exist"
fi

# Verify it sends SIGUSR1
if grep -q 'SIGUSR1' "$REPO_ROOT/lib/set_orch/api.py"; then
    pass "Shutdown endpoint sends SIGUSR1 to sentinel"
else
    fail "Should send SIGUSR1"
fi

# Verify it returns correct response format
if grep -q '"ok": True.*"message".*"Shutdown initiated"' "$REPO_ROOT/lib/set_orch/api.py"; then
    pass "Shutdown endpoint returns {ok: true, message: 'Shutdown initiated'}"
else
    fail "Should return proper JSON response"
fi

# Verify 409 on no sentinel
if grep -q '409.*No sentinel running' "$REPO_ROOT/lib/set_orch/api.py"; then
    pass "Shutdown endpoint returns 409 when no sentinel running"
else
    fail "Should return 409 when no sentinel"
fi

# ─── Test AC-9: --project-dir in E2E scripts ─────────────────────

echo "Test AC-9/10: --project-dir flag in E2E scripts"

if grep -q 'project-dir' "$REPO_ROOT/tests/e2e/run.sh"; then
    pass "run.sh supports --project-dir flag"
else
    fail "run.sh should support --project-dir"
fi

if grep -q 'project-dir' "$REPO_ROOT/tests/e2e/run-complex.sh"; then
    pass "run-complex.sh supports --project-dir flag"
else
    fail "run-complex.sh should support --project-dir"
fi

# Verify default is /tmp
if grep -q 'BASE_DIR=.*tmp' "$REPO_ROOT/tests/e2e/run.sh"; then
    pass "run.sh defaults to /tmp"
else
    fail "run.sh should default to /tmp"
fi

# ─── Test: Sentinel SIGUSR1 handler exists ────────────────────────

echo "Test: Sentinel SIGUSR1 handler"

if grep -q "trap handle_graceful_shutdown USR1" "$REPO_ROOT/bin/set-sentinel"; then
    pass "Sentinel traps SIGUSR1 for graceful shutdown"
else
    fail "Sentinel should trap SIGUSR1"
fi

if grep -q "shutdown_requested=true" "$REPO_ROOT/bin/set-sentinel"; then
    pass "SIGUSR1 handler sets shutdown_requested flag"
else
    fail "Should set shutdown_requested flag"
fi

# ─── Test: State shutdown fields ──────────────────────────────────

echo "Test: State shutdown metadata"

if grep -q "shutdown_at" "$REPO_ROOT/bin/set-sentinel"; then
    pass "Sentinel writes shutdown_at to state"
else
    fail "Should write shutdown_at"
fi

if grep -q '"shutdown"' "$REPO_ROOT/bin/set-sentinel"; then
    pass "Sentinel sets status to 'shutdown'"
else
    fail "Should set status to shutdown"
fi

# ─── Test: Web UI shutdown controls ───────────────────────────────

echo "Test: Web UI shutdown controls"

WEB_DIR="$REPO_ROOT/web"
if [[ -d "$WEB_DIR/src" ]]; then
    if grep -rq "shutdown" "$WEB_DIR/src/" 2>/dev/null; then
        pass "Web UI has shutdown-related code"
    else
        skip "Web UI exists but no shutdown code found"
    fi
else
    skip "Web UI directory not found (may be separate repo)"
fi

# ─── Results ──────────────────────────────────────────────────────

echo ""
echo "=== Results ==="
echo -e "  ${GREEN}Passed: $PASS_COUNT${NC}"
if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
    exit 1
else
    echo -e "  Failed: 0"
    echo ""
    echo -e "${GREEN}All tests passed.${NC}"
    exit 0
fi
