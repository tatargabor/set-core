#!/usr/bin/env bash
# Test script for wt-orchestrate: brief parsing, state management, dependency graph
# Tests functions without Claude calls or git operations.
# Run with: ./tests/orchestrator/test-orchestrate.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source common functions for color codes
source "$PROJECT_DIR/bin/wt-common.sh"

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

assert_equals() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "'$expected'" "'$actual'"
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

assert_exit_code() {
    local expected="$1"
    local actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "exit code $expected" "exit code $actual"
    fi
}

# ============================================================
# Setup: source wt-orchestrate functions
# ============================================================

# Save test SCRIPT_DIR, then source wt-orchestrate with main() stripped.
# wt-orchestrate sets its own SCRIPT_DIR and sources wt-common.sh from bin/.
TEST_DIR="$SCRIPT_DIR"
eval "$(sed '/^main "\$@"/d; /^SCRIPT_DIR=/s|=.*|="'"$PROJECT_DIR/bin"'"|' "$PROJECT_DIR/bin/wt-orchestrate")"

SAMPLE_BRIEF="$TEST_DIR/sample-brief.md"

# ============================================================
# Test: parse_next_items
# ============================================================

test_start "parse_next_items extracts 3 items from sample brief"
items=$(parse_next_items "$SAMPLE_BRIEF")
count=$(echo "$items" | jq 'length')
assert_equals "3" "$count"

test_start "parse_next_items first item contains 'Alpha'"
first=$(echo "$items" | jq -r '.[0]')
assert_contains "$first" "Alpha"

test_start "parse_next_items second item contains 'Beta'"
second=$(echo "$items" | jq -r '.[1]')
assert_contains "$second" "Beta"

test_start "parse_next_items third item contains 'Charlie'"
third=$(echo "$items" | jq -r '.[2]')
assert_contains "$third" "Charlie"

# ============================================================
# Test: parse_directives
# ============================================================

test_start "parse_directives reads max_parallel"
directives=$(parse_directives "$SAMPLE_BRIEF")
mp=$(echo "$directives" | jq -r '.max_parallel')
assert_equals "2" "$mp"

test_start "parse_directives reads merge_policy"
policy=$(echo "$directives" | jq -r '.merge_policy')
assert_equals "eager" "$policy"

test_start "parse_directives reads checkpoint_every"
ce=$(echo "$directives" | jq -r '.checkpoint_every')
assert_equals "2" "$ce"

test_start "parse_directives reads test_command"
tc=$(echo "$directives" | jq -r '.test_command')
assert_contains "$tc" "test -f alpha.txt"

test_start "parse_directives reads notification"
notif=$(echo "$directives" | jq -r '.notification')
assert_equals "none" "$notif"

test_start "parse_directives reads token_budget"
tb=$(echo "$directives" | jq -r '.token_budget')
assert_equals "50000" "$tb"

test_start "parse_directives reads pause_on_exit"
poe=$(echo "$directives" | jq -r '.pause_on_exit')
assert_equals "false" "$poe"

# ============================================================
# Test: parse_directives with defaults
# ============================================================

MINIMAL_BRIEF=$(mktemp)
cat > "$MINIMAL_BRIEF" <<'EOF'
## Feature Roadmap
### Next
- Something to do

## Orchestrator Directives
EOF

test_start "parse_directives applies defaults for empty directives"
directives=$(parse_directives "$MINIMAL_BRIEF")
mp=$(echo "$directives" | jq -r '.max_parallel')
assert_equals "$DEFAULT_MAX_PARALLEL" "$mp"

test_start "parse_directives default merge_policy is checkpoint"
policy=$(echo "$directives" | jq -r '.merge_policy')
assert_equals "checkpoint" "$policy"

rm -f "$MINIMAL_BRIEF"

# ============================================================
# Test: parse_directives with invalid values
# ============================================================

INVALID_BRIEF=$(mktemp)
cat > "$INVALID_BRIEF" <<'EOF'
## Orchestrator Directives
- max_parallel: -5
- merge_policy: yolo
- notification: telegram
- checkpoint_every: abc
- token_budget: -100
- pause_on_exit: maybe
EOF

test_start "parse_directives rejects invalid max_parallel"
directives=$(parse_directives "$INVALID_BRIEF" 2>/dev/null)
mp=$(echo "$directives" | jq -r '.max_parallel')
assert_equals "$DEFAULT_MAX_PARALLEL" "$mp"

test_start "parse_directives rejects invalid merge_policy"
policy=$(echo "$directives" | jq -r '.merge_policy')
assert_equals "$DEFAULT_MERGE_POLICY" "$policy"

test_start "parse_directives rejects invalid notification"
notif=$(echo "$directives" | jq -r '.notification')
assert_equals "$DEFAULT_NOTIFICATION" "$notif"

test_start "parse_directives rejects invalid checkpoint_every"
ce=$(echo "$directives" | jq -r '.checkpoint_every')
assert_equals "$DEFAULT_CHECKPOINT_EVERY" "$ce"

test_start "parse_directives rejects invalid pause_on_exit"
poe=$(echo "$directives" | jq -r '.pause_on_exit')
assert_equals "$DEFAULT_PAUSE_ON_EXIT" "$poe"

rm -f "$INVALID_BRIEF"

# ============================================================
# Test: brief_hash
# ============================================================

test_start "brief_hash is deterministic"
h1=$(brief_hash "$SAMPLE_BRIEF")
h2=$(brief_hash "$SAMPLE_BRIEF")
assert_equals "$h1" "$h2"

test_start "brief_hash is not empty or 'unknown'"
if [[ -n "$h1" && "$h1" != "unknown" ]]; then
    test_pass
else
    test_fail "non-empty hash" "$h1"
fi

test_start "brief_hash changes when content changes"
modified=$(mktemp)
echo "different content" > "$modified"
h3=$(brief_hash "$modified")
rm -f "$modified"
if [[ "$h1" != "$h3" ]]; then
    test_pass
else
    test_fail "different hash" "same hash"
fi

# ============================================================
# Test: topological_sort
# ============================================================

PLAN_LINEAR=$(mktemp)
cat > "$PLAN_LINEAR" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "c", "depends_on": ["b"]},
    {"name": "a", "depends_on": []},
    {"name": "b", "depends_on": ["a"]}
  ]
}
EOF

test_start "topological_sort produces correct linear order"
order=$(topological_sort "$PLAN_LINEAR" | tr '\n' ',')
assert_equals "a,b,c," "$order"
rm -f "$PLAN_LINEAR"

PLAN_DIAMOND=$(mktemp)
cat > "$PLAN_DIAMOND" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "d", "depends_on": ["b", "c"]},
    {"name": "b", "depends_on": ["a"]},
    {"name": "c", "depends_on": ["a"]},
    {"name": "a", "depends_on": []}
  ]
}
EOF

test_start "topological_sort handles diamond dependency"
order=$(topological_sort "$PLAN_DIAMOND" | tr '\n' ',')
# a must be first, d must be last, b and c in between
if [[ "$order" == a,b,c,d, ]] || [[ "$order" == a,c,b,d, ]]; then
    test_pass
else
    test_fail "a,{b,c},d" "$order"
fi
rm -f "$PLAN_DIAMOND"

PLAN_INDEPENDENT=$(mktemp)
cat > "$PLAN_INDEPENDENT" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "x", "depends_on": []},
    {"name": "y", "depends_on": []},
    {"name": "z", "depends_on": []}
  ]
}
EOF

test_start "topological_sort handles all-independent changes"
order=$(topological_sort "$PLAN_INDEPENDENT" | tr '\n' ',')
assert_equals "x,y,z," "$order"
rm -f "$PLAN_INDEPENDENT"

# ============================================================
# Test: circular dependency detection
# ============================================================

PLAN_CIRCULAR=$(mktemp)
cat > "$PLAN_CIRCULAR" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "a", "depends_on": ["b"]},
    {"name": "b", "depends_on": ["c"]},
    {"name": "c", "depends_on": ["a"]}
  ]
}
EOF

test_start "topological_sort detects 3-node circular dependency"
if ! topological_sort "$PLAN_CIRCULAR" &>/dev/null; then
    test_pass
else
    test_fail "exit code 1 (circular)" "exit code 0"
fi
rm -f "$PLAN_CIRCULAR"

PLAN_SELF=$(mktemp)
cat > "$PLAN_SELF" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "a", "depends_on": ["a"]}
  ]
}
EOF

test_start "topological_sort detects self-dependency"
if ! topological_sort "$PLAN_SELF" &>/dev/null; then
    test_pass
else
    test_fail "exit code 1 (circular)" "exit code 0"
fi
rm -f "$PLAN_SELF"

# ============================================================
# Test: validate_plan
# ============================================================

PLAN_VALID=$(mktemp)
cat > "$PLAN_VALID" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "abc123",
  "changes": [
    {"name": "add-feature", "depends_on": [], "scope": "test", "complexity": "S", "roadmap_item": "test"},
    {"name": "fix-bug", "depends_on": ["add-feature"], "scope": "test", "complexity": "S", "roadmap_item": "test"}
  ]
}
EOF

test_start "validate_plan accepts valid plan"
rc=0
validate_plan "$PLAN_VALID" &>/dev/null || rc=$?
assert_exit_code "0" "$rc"
rm -f "$PLAN_VALID"

PLAN_BAD_NAME=$(mktemp)
cat > "$PLAN_BAD_NAME" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "abc123",
  "changes": [
    {"name": "CamelCase", "depends_on": [], "scope": "test", "complexity": "S", "roadmap_item": "test"}
  ]
}
EOF

test_start "validate_plan rejects non-kebab-case names"
rc=0
validate_plan "$PLAN_BAD_NAME" &>/dev/null || rc=$?
if [[ "$rc" -ne 0 ]]; then
    test_pass
else
    test_fail "non-zero exit (invalid name)" "exit 0"
fi
rm -f "$PLAN_BAD_NAME"

PLAN_BAD_DEP=$(mktemp)
cat > "$PLAN_BAD_DEP" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "abc123",
  "changes": [
    {"name": "a", "depends_on": ["nonexistent"]}
  ]
}
EOF

test_start "validate_plan rejects dangling dependency reference"
rc=0
validate_plan "$PLAN_BAD_DEP" &>/dev/null || rc=$?
if [[ "$rc" -ne 0 ]]; then
    test_pass
else
    test_fail "non-zero exit (bad dep)" "exit 0"
fi
rm -f "$PLAN_BAD_DEP"

# ============================================================
# Test: State management (init_state, update, query)
# ============================================================

PLAN_FOR_STATE=$(mktemp)
STATE_FILENAME=$(mktemp)
cat > "$PLAN_FOR_STATE" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "testhash",
  "changes": [
    {"name": "alpha", "depends_on": [], "scope": "Create alpha", "complexity": "S", "roadmap_item": "Alpha feature"},
    {"name": "beta", "depends_on": ["alpha"], "scope": "Create beta", "complexity": "M", "roadmap_item": "Beta feature"}
  ]
}
EOF

test_start "init_state creates valid state JSON"
init_state "$PLAN_FOR_STATE"
rc=0
jq empty "$STATE_FILENAME" 2>/dev/null || rc=$?
assert_exit_code "0" "$rc"

test_start "init_state has correct status"
status=$(jq -r '.status' "$STATE_FILENAME")
assert_equals "running" "$status"

test_start "init_state has 2 changes"
count=$(jq '.changes | length' "$STATE_FILENAME")
assert_equals "2" "$count"

test_start "init_state changes start as pending"
s1=$(jq -r '.changes[0].status' "$STATE_FILENAME")
s2=$(jq -r '.changes[1].status' "$STATE_FILENAME")
if [[ "$s1" == "pending" && "$s2" == "pending" ]]; then
    test_pass
else
    test_fail "both pending" "$s1, $s2"
fi

test_start "get_change_status returns pending"
s=$(get_change_status "alpha")
assert_equals "pending" "$s"

test_start "update_change_field updates status"
update_change_field "alpha" "status" '"running"'
s=$(get_change_status "alpha")
assert_equals "running" "$s"

test_start "get_changes_by_status finds running changes"
running=$(get_changes_by_status "running")
assert_equals "alpha" "$running"

test_start "count_changes_by_status counts correctly"
c=$(count_changes_by_status "pending")
assert_equals "1" "$c"

test_start "deps_satisfied returns true for no-dep change"
update_change_field "alpha" "status" '"pending"'
if deps_satisfied "alpha"; then
    test_pass
else
    test_fail "true (no deps)" "false"
fi

test_start "deps_satisfied returns false when dep not merged"
if ! deps_satisfied "beta"; then
    test_pass
else
    test_fail "false (alpha not merged)" "true"
fi

test_start "deps_satisfied returns true when dep is merged"
update_change_field "alpha" "status" '"merged"'
if deps_satisfied "beta"; then
    test_pass
else
    test_fail "true (alpha merged)" "false"
fi

test_start "update_state_field updates top-level field"
update_state_field "status" '"checkpoint"'
s=$(jq -r '.status' "$STATE_FILENAME")
assert_equals "checkpoint" "$s"

rm -f "$PLAN_FOR_STATE" "$STATE_FILENAME"

# ============================================================
# Test: parse_next_items edge cases
# ============================================================

BRIEF_EMPTY_NEXT=$(mktemp)
cat > "$BRIEF_EMPTY_NEXT" <<'EOF'
## Feature Roadmap
### Next
### Ideas
- Some idea
EOF

test_start "parse_next_items returns empty for empty Next section"
items=$(parse_next_items "$BRIEF_EMPTY_NEXT")
count=$(echo "$items" | jq 'length')
assert_equals "0" "$count"
rm -f "$BRIEF_EMPTY_NEXT"

BRIEF_NO_NEXT=$(mktemp)
cat > "$BRIEF_NO_NEXT" <<'EOF'
## Feature Roadmap
### Done
- Something done
### Ideas
- Future stuff
EOF

test_start "parse_next_items returns empty when no Next section"
items=$(parse_next_items "$BRIEF_NO_NEXT")
count=$(echo "$items" | jq 'length')
assert_equals "0" "$count"
rm -f "$BRIEF_NO_NEXT"

# ============================================================
# Test: Ralph PID and SIGTERM compatibility (9.1-9.3 verification)
# ============================================================

test_start "wt-loop has ralph-terminal.pid write (line 590)"
if grep -q 'echo "\$\$" > "\$(get_terminal_pid_file' "$PROJECT_DIR/bin/wt-loop"; then
    test_pass
else
    test_fail "PID write found" "not found"
fi

test_start "wt-loop cleanup_on_exit sets status to stopped"
if grep -q 'update_loop_state.*status.*stopped' "$PROJECT_DIR/bin/wt-loop"; then
    test_pass
else
    test_fail "stopped status in cleanup" "not found"
fi

test_start "wt-loop trap handles SIGTERM"
if grep -q "trap 'cleanup_on_exit' EXIT SIGTERM" "$PROJECT_DIR/bin/wt-loop"; then
    test_pass
else
    test_fail "SIGTERM trap found" "not found"
fi

test_start "detect_next_change_action checks unchecked tasks for restart"
if grep -q 'grep.*\-cE.*\\\[.*\\\]' "$PROJECT_DIR/bin/wt-loop"; then
    test_pass
else
    test_fail "unchecked task grep found" "not found"
fi

# ============================================================
# Test: parse_directives — smoke blocking directives
# ============================================================

SMOKE_BRIEF=$(mktemp)
cat > "$SMOKE_BRIEF" <<'EOF'
## Orchestrator Directives
- smoke_command: SMOKE_BASE_URL=http://localhost:3002 pnpm test:smoke
- smoke_timeout: 180
- smoke_blocking: true
- smoke_fix_token_budget: 300000
- smoke_fix_max_turns: 10
- smoke_fix_max_retries: 5
- smoke_health_check_url: http://localhost:3002
- smoke_health_check_timeout: 60
EOF

test_start "parse_directives reads smoke_blocking"
directives=$(parse_directives "$SMOKE_BRIEF")
sb=$(echo "$directives" | jq -r '.smoke_blocking')
assert_equals "true" "$sb"

test_start "parse_directives reads smoke_fix_token_budget"
sftb=$(echo "$directives" | jq -r '.smoke_fix_token_budget')
assert_equals "300000" "$sftb"

test_start "parse_directives reads smoke_fix_max_turns"
sfmt=$(echo "$directives" | jq -r '.smoke_fix_max_turns')
assert_equals "10" "$sfmt"

test_start "parse_directives reads smoke_fix_max_retries"
sfmr=$(echo "$directives" | jq -r '.smoke_fix_max_retries')
assert_equals "5" "$sfmr"

test_start "parse_directives reads smoke_health_check_url"
shcu=$(echo "$directives" | jq -r '.smoke_health_check_url')
assert_equals "http://localhost:3002" "$shcu"

test_start "parse_directives reads smoke_health_check_timeout"
shct=$(echo "$directives" | jq -r '.smoke_health_check_timeout')
assert_equals "60" "$shct"

rm -f "$SMOKE_BRIEF"

# Test defaults for smoke directives
MINIMAL_BRIEF2=$(mktemp)
cat > "$MINIMAL_BRIEF2" <<'EOF'
## Orchestrator Directives
EOF

test_start "parse_directives defaults smoke_blocking to true"
directives=$(parse_directives "$MINIMAL_BRIEF2" 2>/dev/null)
sb=$(echo "$directives" | jq -r '.smoke_blocking')
assert_equals "true" "$sb"

test_start "parse_directives defaults smoke_fix_max_retries to 3"
sfmr=$(echo "$directives" | jq -r '.smoke_fix_max_retries')
assert_equals "3" "$sfmr"

test_start "parse_directives defaults smoke_health_check_timeout to 30"
shct=$(echo "$directives" | jq -r '.smoke_health_check_timeout')
assert_equals "30" "$shct"

rm -f "$MINIMAL_BRIEF2"

# Test invalid smoke directive values
INVALID_SMOKE_BRIEF=$(mktemp)
cat > "$INVALID_SMOKE_BRIEF" <<'EOF'
## Orchestrator Directives
- smoke_blocking: maybe
- smoke_fix_token_budget: -100
- smoke_fix_max_turns: abc
- smoke_fix_max_retries: -1
- smoke_health_check_timeout: zero
EOF

test_start "parse_directives rejects invalid smoke_blocking"
directives=$(parse_directives "$INVALID_SMOKE_BRIEF" 2>/dev/null)
sb=$(echo "$directives" | jq -r '.smoke_blocking')
assert_equals "true" "$sb"

test_start "parse_directives rejects invalid smoke_fix_token_budget"
sftb=$(echo "$directives" | jq -r '.smoke_fix_token_budget')
assert_equals "500000" "$sftb"

test_start "parse_directives rejects invalid smoke_fix_max_turns"
sfmt=$(echo "$directives" | jq -r '.smoke_fix_max_turns')
assert_equals "15" "$sfmt"

test_start "parse_directives rejects invalid smoke_health_check_timeout"
shct=$(echo "$directives" | jq -r '.smoke_health_check_timeout')
assert_equals "30" "$shct"

rm -f "$INVALID_SMOKE_BRIEF"

# ============================================================
# Test: extract_health_check_url
# ============================================================

test_start "extract_health_check_url extracts from smoke command"
url=$(extract_health_check_url "SMOKE_BASE_URL=http://localhost:3002 pnpm test:smoke")
assert_equals "http://localhost:3002" "$url"

test_start "extract_health_check_url returns empty for no URL"
url=$(extract_health_check_url "pnpm test:smoke")
assert_equals "" "$url"

# ============================================================
# Test: plan metadata fields (plan_phase, plan_method)
# ============================================================

TMPDIR_META=$(mktemp -d)
trap 'rm -rf "$TMPDIR_META"' EXIT

test_start "init_state preserves plan_phase and plan_method from plan"
cat > "$TMPDIR_META/plan.json" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "abc123",
  "plan_phase": "initial",
  "plan_method": "agent",
  "changes": [{"name": "test-change", "scope": "test", "complexity": "S", "depends_on": [], "roadmap_item": "test"}]
}
EOF
PLAN_FILENAME="$TMPDIR_META/plan.json"
STATE_FILENAME="$TMPDIR_META/state.json"
init_state "$PLAN_FILENAME"
pp=$(jq -r '.plan_phase' "$STATE_FILENAME")
pm=$(jq -r '.plan_method' "$STATE_FILENAME")
assert_equals "initial" "$pp"

test_start "init_state sets plan_method from plan"
assert_equals "agent" "$pm"

test_start "init_state defaults plan_phase to initial when missing"
cat > "$TMPDIR_META/plan2.json" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "abc123",
  "changes": [{"name": "test-change", "scope": "test", "complexity": "S", "depends_on": [], "roadmap_item": "test"}]
}
EOF
PLAN_FILENAME="$TMPDIR_META/plan2.json"
STATE_FILENAME="$TMPDIR_META/state2.json"
init_state "$PLAN_FILENAME"
pp2=$(jq -r '.plan_phase' "$STATE_FILENAME")
pm2=$(jq -r '.plan_method' "$STATE_FILENAME")
assert_equals "initial" "$pp2"

test_start "init_state defaults plan_method to api when missing"
assert_equals "api" "$pm2"

# ============================================================
# Test: plan_method directive parsing
# ============================================================

test_start "resolve_directives parses plan_method: agent"
TMPDIR_DIRECTIVE=$(mktemp -d)
cat > "$TMPDIR_DIRECTIVE/brief.md" <<'EOF'
## Orchestrator Directives
- plan_method: agent
- max_parallel: 3

## Next
- Test item
EOF
result=$(resolve_directives "$TMPDIR_DIRECTIVE/brief.md")
pmval=$(echo "$result" | jq -r '.plan_method')
assert_equals "agent" "$pmval"
rm -rf "$TMPDIR_DIRECTIVE"

test_start "resolve_directives defaults plan_method to api"
TMPDIR_DIRECTIVE2=$(mktemp -d)
cat > "$TMPDIR_DIRECTIVE2/brief.md" <<'EOF'
## Orchestrator Directives
- max_parallel: 2

## Next
- Test item
EOF
result2=$(resolve_directives "$TMPDIR_DIRECTIVE2/brief.md")
pmval2=$(echo "$result2" | jq -r '.plan_method')
assert_equals "api" "$pmval2"
rm -rf "$TMPDIR_DIRECTIVE2"

# ============================================================
# Test: plan_memory_hygiene runs without error when wt-memory unavailable
# ============================================================

test_start "plan_memory_hygiene succeeds when wt-memory not in PATH"
(
    PATH="/usr/bin:/bin"
    plan_memory_hygiene 2>/dev/null
)
rc=$?
assert_equals "0" "$rc"

# ============================================================
# Test: orch_recall phase tag filtering passes tags through
# ============================================================

test_start "orch_recall passes tags parameter (verified by log output)"
# We can't test actual recall without wt-memory, but verify the function
# accepts phase tags without error
(
    PATH="/usr/bin:/bin"  # wt-memory unavailable
    result=$(orch_recall "test query" 3 "phase:planning" 2>/dev/null)
    # Should return empty string gracefully
    [[ -z "$result" ]]
) && test_pass || test_fail "empty result" "error"

# ============================================================
# Summary
# ============================================================

echo ""
echo "================================"
echo "Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
echo "================================"

if [[ "$TESTS_FAILED" -gt 0 ]]; then
    exit 1
fi
