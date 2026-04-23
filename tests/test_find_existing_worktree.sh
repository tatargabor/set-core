#!/usr/bin/env bash
# Test find_existing_worktree ambiguity resolution.
# Run with: ./tests/test_find_existing_worktree.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

source "$PROJECT_DIR/bin/set-common.sh"

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
    echo "  Got:      $2"
}
assert_equals() {
    if [[ "$1" == "$2" ]]; then test_pass; else test_fail "'$1'" "'$2'"; fi
}

# Build a disposable repo with multiple worktrees.
TMP_ROOT=$(mktemp -d)
trap 'rm -rf "$TMP_ROOT"' EXIT

REPO="$TMP_ROOT/acme"
mkdir -p "$REPO"
(
    cd "$REPO"
    git init -q
    git checkout -q -b main
    git config user.email "t@t"
    git config user.name "t"
    echo seed > README
    git add README
    git commit -q -m init
)

add_wt() {
    local path="$1" branch="$2"
    git -C "$REPO" worktree add -b "$branch" "$path" >/dev/null 2>&1
}

# ---- Scenario: single unambiguous match (bash convention) ----
test_start "single bash-convention match"
add_wt "$TMP_ROOT/acme-wt-single" change/single
result=$(find_existing_worktree "$REPO" "single" 2>/dev/null)
assert_equals "$TMP_ROOT/acme-wt-single" "$result"

# ---- Scenario: single Python-convention match ----
test_start "single python-convention match"
add_wt "$TMP_ROOT/acme-plain" change/plain
result=$(find_existing_worktree "$REPO" "plain" 2>/dev/null)
assert_equals "$TMP_ROOT/acme-plain" "$result"

# ---- Scenario: no match returns empty ----
test_start "no match returns empty"
result=$(find_existing_worktree "$REPO" "nonexistent" 2>/dev/null)
assert_equals "" "$result"

# ---- Scenario: two-level bash-convention ambiguity, -2 wins ----
test_start "two-level bash ambiguity — -2 wins"
add_wt "$TMP_ROOT/acme-wt-ambig" change/ambig
add_wt "$TMP_ROOT/acme-wt-ambig-2" change/ambig-2
result=$(find_existing_worktree "$REPO" "ambig" 2>/dev/null)
assert_equals "$TMP_ROOT/acme-wt-ambig-2" "$result"

# ---- Scenario: three-level ambiguity, -3 wins ----
test_start "three-level ambiguity — -3 wins"
add_wt "$TMP_ROOT/acme-wt-ambig-3" change/ambig-3
result=$(find_existing_worktree "$REPO" "ambig" 2>/dev/null)
assert_equals "$TMP_ROOT/acme-wt-ambig-3" "$result"

# ---- Scenario: Python-convention suffix — -2 wins ----
test_start "python-convention suffix — -2 wins"
add_wt "$TMP_ROOT/acme-pyambig" change/pyambig
add_wt "$TMP_ROOT/acme-pyambig-2" change/pyambig-2
result=$(find_existing_worktree "$REPO" "pyambig" 2>/dev/null)
assert_equals "$TMP_ROOT/acme-pyambig-2" "$result"

# ---- Scenario: substring false positives excluded ----
test_start "substring not matched (foo vs foobar)"
add_wt "$TMP_ROOT/acme-wt-foobar" change/foobar
result=$(find_existing_worktree "$REPO" "foo" 2>/dev/null)
assert_equals "" "$result"

# ---- Scenario: WARN emitted on stderr under ambiguity, exit 0 ----
test_start "WARN emitted on ambiguity; exit 0"
stderr_capture=$(find_existing_worktree "$REPO" "ambig" 2>&1 >/dev/null)
exit_code=$?
if [[ $exit_code -eq 0 ]] && echo "$stderr_capture" | grep -q "candidate worktrees matched"; then
    test_pass
else
    test_fail "exit=0 + WARN" "exit=$exit_code + stderr=$stderr_capture"
fi

# ---- Summary ----
echo ""
echo "─────────────────────────────────────────"
echo "Tests run:    $TESTS_RUN"
echo "Tests passed: $TESTS_PASSED"
echo "Tests failed: $TESTS_FAILED"

if [[ $TESTS_FAILED -gt 0 ]]; then
    exit 1
fi
