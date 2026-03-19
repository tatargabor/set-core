#!/usr/bin/env bash
# Test script for set-loop CWD-based operation and tasks.md lookup
# Tests: get_worktree_path_from_cwd, check_tasks_done, init_loop_state, build_prompt
# Run with: ./tests/test_wt_loop.sh

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
        test_fail "does not contain '$needle'" "$haystack"
    fi
}

assert_equals() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "'$expected'" "'$actual'"
    fi
}

# ============================================================
# Setup: create a temp git repo to simulate worktree
# ============================================================
TMPDIR_BASE=$(mktemp -d)
REPO_DIR="$TMPDIR_BASE/test-repo"
WT_DIR="$TMPDIR_BASE/test-repo-set-feature"

cleanup() {
    rm -rf "$TMPDIR_BASE"
}
trap cleanup EXIT

# Create a bare git repo and worktree
git init "$REPO_DIR" --quiet
cd "$REPO_DIR"
git commit --allow-empty -m "init" --quiet

# Create a worktree
git worktree add -b change/feature "$WT_DIR" --quiet

# Source the set-loop functions without running main
# We strip: the SCRIPT_DIR/source lines at the top, the main call at bottom
eval "$(sed -e '/^SCRIPT_DIR=/d' \
            -e '/^source.*set-common.sh/d' \
            -e '/^main "\$@"/d' \
            "$PROJECT_DIR/bin/set-loop")"

echo "=== set-loop tests ==="
echo ""

# ============================================================
# Test 7.1: CWD-based worktree detection inside a git worktree
# ============================================================
test_start "7.1 get_worktree_path_from_cwd inside worktree resolves correctly"
cd "$WT_DIR"
result=$(get_worktree_path_from_cwd)
assert_equals "$WT_DIR" "$result"

# ============================================================
# Test 7.2: set-loop outside a git repo shows error
# ============================================================
test_start "7.2 get_worktree_path_from_cwd outside git repo exits with error"
mkdir -p "$TMPDIR_BASE/not-a-repo"
# Run in a subshell to catch exit
output=$(cd "$TMPDIR_BASE/not-a-repo" && get_worktree_path_from_cwd 2>&1) && rc=0 || rc=$?
if [[ $rc -ne 0 ]]; then
    test_pass
else
    test_fail "non-zero exit code" "exit code $rc"
fi

# ============================================================
# Test 7.3: check_tasks_done finds tasks.md at worktree root
# ============================================================
test_start "7.3 check_tasks_done finds tasks.md at worktree root"
cd "$WT_DIR"
echo "- [x] Task 1
- [x] Task 2" > "$WT_DIR/tasks.md"
if check_tasks_done "$WT_DIR"; then
    test_pass
else
    test_fail "all done (exit 0)" "not done (exit 1)"
fi
rm -f "$WT_DIR/tasks.md"

# ============================================================
# Test 7.4: check_tasks_done fallback finds tasks.md in subdirectory
# ============================================================
test_start "7.4 check_tasks_done fallback finds tasks.md in subdirectory"
cd "$WT_DIR"
mkdir -p "$WT_DIR/subdir/nested"
echo "- [x] Done task" > "$WT_DIR/subdir/nested/tasks.md"
if check_tasks_done "$WT_DIR"; then
    test_pass
else
    test_fail "found in subdirectory (exit 0)" "not found (exit 1)"
fi
rm -rf "$WT_DIR/subdir"

# ============================================================
# Test 7.5: check_tasks_done ignores archive/ directory
# ============================================================
test_start "7.5 check_tasks_done ignores archive/ directory"
cd "$WT_DIR"
mkdir -p "$WT_DIR/archive"
echo "- [ ] Archived incomplete task" > "$WT_DIR/archive/tasks.md"
# Should not find the archived tasks.md, so check_tasks_done should fail (no tasks.md found)
if check_tasks_done "$WT_DIR" 2>/dev/null; then
    test_fail "should not find archive/tasks.md" "found archive/tasks.md and reported done"
else
    test_pass
fi
rm -rf "$WT_DIR/archive"

# ============================================================
# Test 7.6: check_tasks_done correctly detects all-done
# ============================================================
test_start "7.6 check_tasks_done correctly detects all-done (no [ ] remaining)"
cd "$WT_DIR"
echo "- [x] Task 1
- [x] Task 2
- [x] Task 3" > "$WT_DIR/tasks.md"
if check_tasks_done "$WT_DIR"; then
    test_pass
else
    test_fail "all done (exit 0)" "not done (exit 1)"
fi
rm -f "$WT_DIR/tasks.md"

# ============================================================
# Test 7.7: check_tasks_done correctly detects not-done
# ============================================================
test_start "7.7 check_tasks_done correctly detects not-done ([ ] remaining)"
cd "$WT_DIR"
echo "- [x] Task 1
- [ ] Task 2
- [x] Task 3" > "$WT_DIR/tasks.md"
if check_tasks_done "$WT_DIR"; then
    test_fail "not done (exit 1)" "all done (exit 0)"
else
    test_pass
fi
rm -f "$WT_DIR/tasks.md"

# ============================================================
# Test 7.8: init_loop_state writes worktree_name instead of change_id
# ============================================================
test_start "7.8 init_loop_state writes worktree_name instead of change_id"
cd "$WT_DIR"
init_loop_state "$WT_DIR" "test-set-feature" "Test task" 10 "tasks" 80 2 45
state_file="$WT_DIR/.claude/loop-state.json"
if [[ -f "$state_file" ]]; then
    wt_name=$(jq -r '.worktree_name' "$state_file")
    has_change_id=$(jq 'has("change_id")' "$state_file")
    if [[ "$wt_name" == "test-set-feature" ]] && [[ "$has_change_id" == "false" ]]; then
        test_pass
    else
        test_fail "worktree_name=test-set-feature, no change_id" "worktree_name=$wt_name, has_change_id=$has_change_id"
    fi
else
    test_fail "state file exists" "state file not found"
fi
rm -rf "$WT_DIR/.claude"

# ============================================================
# Test 7.9: build_prompt does not reference change-id
# ============================================================
test_start "7.9 build_prompt does not reference change-id"
cd "$WT_DIR"
mkdir -p "$WT_DIR/.claude"
# Create minimal state file for build_prompt
echo '{"iterations": []}' > "$WT_DIR/.claude/loop-state.json"
prompt=$(build_prompt "Test task" 1 5 "$WT_DIR" "tasks")
if [[ "$prompt" == *"change_id"* ]] || [[ "$prompt" == *"change-id"* ]] || [[ "$prompt" == *"change id"* ]]; then
    test_fail "no change-id reference" "found change-id in prompt"
else
    test_pass
fi
rm -rf "$WT_DIR/.claude"

# ============================================================
# Test 7.10: cmd_start falls back to manual when no tasks.md exists
# ============================================================
test_start "7.10 set-loop start falls back to manual when no tasks.md"
cd "$WT_DIR"
# Ensure no tasks.md exists
rm -f "$WT_DIR/tasks.md"
find "$WT_DIR" -name "tasks.md" -delete 2>/dev/null || true
# Run set-loop start and capture output (will fail because no terminal, but we
# check that the state file has done_criteria=manual)
output=$("$PROJECT_DIR/bin/set-loop" start "Test task" --max 1 2>&1 || true)
state_file="$WT_DIR/.claude/loop-state.json"
if [[ -f "$state_file" ]]; then
    criteria=$(jq -r '.done_criteria' "$state_file")
    assert_equals "manual" "$criteria"
else
    # The command may fail before writing state (no terminal), so check the output
    if [[ "$output" == *"manual"* ]]; then
        test_pass
    else
        test_fail "manual done criteria or warning" "$output"
    fi
fi
rm -rf "$WT_DIR/.claude"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=========================="
echo "Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
echo "=========================="

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
