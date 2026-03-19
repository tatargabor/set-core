#!/usr/bin/env bash
# Unit tests for lib/loop/tasks.sh — task detection modes
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source dependencies
source "$SCRIPT_DIR/../../bin/set-common.sh"

# Source loop modules in order
LIB_DIR="$SCRIPT_DIR/../../lib/loop"
source "$LIB_DIR/state.sh"
source "$LIB_DIR/tasks.sh"
source "$LIB_DIR/prompt.sh"

# Create temp worktree structure for testing
TEST_WT=$(mktemp -d)
trap 'rm -rf "$TEST_WT"' EXIT

test_find_tasks_file_root() {
    echo "- [ ] task one" > "$TEST_WT/tasks.md"
    local result
    result=$(find_tasks_file "$TEST_WT")
    assert_contains "$result" "tasks.md" "finds root tasks.md"
    rm -f "$TEST_WT/tasks.md"
}

test_find_tasks_file_nested() {
    mkdir -p "$TEST_WT/openspec/changes/test-change"
    echo "- [ ] task one" > "$TEST_WT/openspec/changes/test-change/tasks.md"
    local result
    result=$(find_tasks_file "$TEST_WT")
    assert_contains "$result" "tasks.md" "finds nested tasks.md"
    rm -rf "$TEST_WT/openspec"
}

test_find_tasks_file_missing() {
    if find_tasks_file "$TEST_WT" 2>/dev/null; then
        echo "    FAIL: should return 1 when no tasks.md"
        return 1
    fi
}

test_check_tasks_done_complete() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [x] task two
EOF
    check_tasks_done "$TEST_WT"
    assert_equals "0" "$?" "all tasks complete"
    rm -f "$TEST_WT/tasks.md"
}

test_check_tasks_done_incomplete() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [ ] task two
- [x] task three
EOF
    if check_tasks_done "$TEST_WT" 2>/dev/null; then
        echo "    FAIL: should return 1 when tasks incomplete"
        return 1
    fi
    rm -f "$TEST_WT/tasks.md"
}

test_count_manual_tasks() {
    cat > "$TEST_WT/tasks.md" <<'EOF'
- [x] task one
- [?] 3.1 Set up API key [input:API_KEY]
- [ ] task three
- [?] 3.2 Verify webhook [confirm]
EOF
    local result
    result=$(count_manual_tasks "$TEST_WT")
    assert_equals "2" "$result" "counts 2 manual tasks"
    rm -f "$TEST_WT/tasks.md"
}

test_detect_next_change_action_ff() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    # No tasks.md → needs ff
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    assert_equals "ff:my-change" "$result" "needs ff when no tasks.md"
    rm -rf "$TEST_WT/openspec"
}

test_detect_next_change_action_apply() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    echo "- [ ] implement something" > "$TEST_WT/openspec/changes/my-change/tasks.md"
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    assert_equals "apply:my-change" "$result" "needs apply when tasks unchecked"
    rm -rf "$TEST_WT/openspec"
}

test_detect_next_change_action_done() {
    mkdir -p "$TEST_WT/openspec/changes/my-change"
    echo "- [x] implement something" > "$TEST_WT/openspec/changes/my-change/tasks.md"
    local result
    result=$(detect_next_change_action "$TEST_WT" "my-change")
    assert_equals "done" "$result" "done when all tasks checked"
    rm -rf "$TEST_WT/openspec"
}

run_tests
