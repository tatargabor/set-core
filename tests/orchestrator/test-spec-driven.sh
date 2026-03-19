#!/usr/bin/env bash
# Test script for spec-driven orchestration features:
# find_input(), load_config_file(), resolve_directives(), estimate_tokens()
# Run with: ./tests/orchestrator/test-spec-driven.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

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
        test_fail "contains '$needle'" "'$haystack'"
    fi
}

# ============================================================
# Setup: source set-orchestrate functions
# ============================================================

TEST_DIR="$SCRIPT_DIR"
eval "$(sed '/^main "\$@"/d; /^SCRIPT_DIR=/s|=.*|="'"$PROJECT_DIR/bin"'"|' "$PROJECT_DIR/bin/set-orchestrate")"

SAMPLE_BRIEF="$TEST_DIR/sample-brief.md"
SAMPLE_SPEC="$TEST_DIR/sample-spec.md"

# Create temp dir for test files
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# ============================================================
# Test: find_input() with --spec
# ============================================================

echo ""
echo "=== find_input() ==="

test_start "find_input with --spec resolves to spec mode"
SPEC_OVERRIDE="$SAMPLE_SPEC"
BRIEF_OVERRIDE=""
find_input 2>/dev/null
assert_equals "spec" "$INPUT_MODE"

test_start "find_input with --spec sets INPUT_PATH"
assert_equals "$SAMPLE_SPEC" "$INPUT_PATH"

test_start "find_input with --spec and missing file fails"
SPEC_OVERRIDE="$TMPDIR_TEST/nonexistent.md"
BRIEF_OVERRIDE=""
INPUT_MODE=""
INPUT_PATH=""
if find_input 2>/dev/null; then
    test_fail "should fail" "succeeded"
else
    test_pass
fi

test_start "find_input with --brief resolves to brief mode"
SPEC_OVERRIDE=""
BRIEF_OVERRIDE="$SAMPLE_BRIEF"
INPUT_MODE=""
INPUT_PATH=""
find_input 2>/dev/null
assert_equals "brief" "$INPUT_MODE"

test_start "find_input with empty Next section fails"
SPEC_OVERRIDE=""
cat > "$TMPDIR_TEST/empty-brief.md" <<'EOF'
## Feature Roadmap
### Next
### Ideas
- future stuff
EOF
BRIEF_OVERRIDE="$TMPDIR_TEST/empty-brief.md"
INPUT_MODE=""
INPUT_PATH=""
if find_input 2>/dev/null; then
    test_fail "should fail (empty Next)" "succeeded"
else
    test_pass
fi

# Reset
SPEC_OVERRIDE=""
BRIEF_OVERRIDE=""

# ============================================================
# Test: load_config_file()
# ============================================================

echo ""
echo "=== load_config_file() ==="

test_start "load_config_file with missing file returns empty JSON"
CONFIG_FILE="$TMPDIR_TEST/nonexistent.yaml"
result=$(load_config_file)
assert_equals "{}" "$result"

test_start "load_config_file parses valid YAML/key-value"
cat > "$TMPDIR_TEST/orch.yaml" <<'EOF'
max_parallel: 4
merge_policy: eager
test_command: npm test
pause_on_exit: true
EOF
CONFIG_FILE="$TMPDIR_TEST/orch.yaml"
result=$(load_config_file)
mp=$(echo "$result" | jq -r '.max_parallel')
assert_equals "4" "$mp"

test_start "load_config_file reads merge_policy"
mp=$(echo "$result" | jq -r '.merge_policy')
assert_equals "eager" "$mp"

test_start "load_config_file reads boolean"
pe=$(echo "$result" | jq -r '.pause_on_exit')
assert_equals "true" "$pe"

test_start "load_config_file reads test_command"
tc=$(echo "$result" | jq -r '.test_command')
assert_equals "npm test" "$tc"

# ============================================================
# Test: resolve_directives() precedence
# ============================================================

echo ""
echo "=== resolve_directives() ==="

test_start "resolve_directives uses doc directives as base"
CONFIG_FILE="$TMPDIR_TEST/nonexistent.yaml"
CLI_MAX_PARALLEL=""
result=$(resolve_directives "$SAMPLE_SPEC")
mp=$(echo "$result" | jq -r '.max_parallel')
assert_equals "2" "$mp"

test_start "resolve_directives doc test_command from spec"
tc=$(echo "$result" | jq -r '.test_command')
assert_equals "npm test" "$tc"

test_start "resolve_directives config overrides doc"
cat > "$TMPDIR_TEST/override.yaml" <<'EOF'
max_parallel: 5
EOF
CONFIG_FILE="$TMPDIR_TEST/override.yaml"
CLI_MAX_PARALLEL=""
result=$(resolve_directives "$SAMPLE_SPEC")
mp=$(echo "$result" | jq -r '.max_parallel')
assert_equals "5" "$mp"

test_start "resolve_directives config does not clobber unset doc values"
tc=$(echo "$result" | jq -r '.test_command')
assert_equals "npm test" "$tc"

test_start "resolve_directives CLI overrides everything"
CONFIG_FILE="$TMPDIR_TEST/override.yaml"
CLI_MAX_PARALLEL="8"
result=$(resolve_directives "$SAMPLE_SPEC")
mp=$(echo "$result" | jq -r '.max_parallel')
assert_equals "8" "$mp"

# Reset
CONFIG_FILE=".claude/orchestration.yaml"
CLI_MAX_PARALLEL=""

# ============================================================
# Test: estimate_tokens()
# ============================================================

echo ""
echo "=== estimate_tokens() ==="

test_start "estimate_tokens returns reasonable value for sample spec"
tokens=$(estimate_tokens "$SAMPLE_SPEC")
# sample-spec.md has ~200 words, * 1.3 ≈ 260
if [[ "$tokens" -gt 100 && "$tokens" -lt 1000 ]]; then
    test_pass
else
    test_fail "100 < tokens < 1000" "$tokens"
fi

test_start "estimate_tokens returns 0 for empty file"
touch "$TMPDIR_TEST/empty.md"
tokens=$(estimate_tokens "$TMPDIR_TEST/empty.md")
assert_equals "0" "$tokens"

# ============================================================
# Test: spec-mode prompt selection
# ============================================================

echo ""
echo "=== Prompt mode selection ==="

test_start "PHASE_HINT is empty by default"
assert_equals "" "$PHASE_HINT"

test_start "spec has Orchestrator Directives section"
result=$(parse_directives "$SAMPLE_SPEC")
mp=$(echo "$result" | jq -r '.max_parallel')
assert_equals "2" "$mp"

test_start "spec has notification: none in directives"
notif=$(echo "$result" | jq -r '.notification')
assert_equals "none" "$notif"

# ============================================================
# Summary
# ============================================================

echo ""
echo "================================="
echo "Tests run:    $TESTS_RUN"
echo -e "Passed:       ${GREEN}$TESTS_PASSED${NC}"
if [[ "$TESTS_FAILED" -gt 0 ]]; then
    echo -e "Failed:       ${RED}$TESTS_FAILED${NC}"
    exit 1
else
    echo "Failed:       0"
    echo -e "${GREEN}All tests passed!${NC}"
fi
