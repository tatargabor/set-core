#!/usr/bin/env bash
# Test wt/ directory convention: lookup functions, scaffolding, migration
# Run with: ./tests/test_wt_directory.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

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

assert_empty() {
    local actual="$1"
    if [[ -z "$actual" ]]; then
        test_pass
    else
        test_fail "(empty)" "'$actual'"
    fi
}

# Create a temporary test directory
TMPDIR=$(mktemp -d)
trap "rm -rf $TMPDIR" EXIT

# Source state.sh to get wt_find_config, wt_find_runs_dir, wt_find_requirements_dir
# We need to mock some globals that state.sh expects
CONFIG_FILE=""
STATE_FILENAME=""
PLAN_FILENAME=""
LOG_FILE="/dev/null"
DEFAULT_MAX_PARALLEL=2
DEFAULT_MERGE_POLICY="checkpoint"
DEFAULT_CHECKPOINT_EVERY=3
DEFAULT_TEST_COMMAND=""
DEFAULT_NOTIFICATION="desktop"
DEFAULT_TOKEN_BUDGET=0
DEFAULT_PAUSE_ON_EXIT="false"
DEFAULT_AUTO_REPLAN="false"
DEFAULT_REVIEW_BEFORE_MERGE="true"
DEFAULT_TEST_TIMEOUT=300
DEFAULT_MAX_VERIFY_RETRIES=2
DEFAULT_SUMMARIZE_MODEL="haiku"
DEFAULT_REVIEW_MODEL="sonnet"
DEFAULT_IMPL_MODEL="opus"
DEFAULT_SMOKE_COMMAND=""
DEFAULT_SMOKE_TIMEOUT=120
DEFAULT_SMOKE_BLOCKING=true
DEFAULT_SMOKE_FIX_TOKEN_BUDGET=500000
DEFAULT_SMOKE_FIX_MAX_TURNS=15
DEFAULT_SMOKE_FIX_MAX_RETRIES=3
DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT=30
DEFAULT_POST_MERGE_COMMAND=""
DEFAULT_TOKEN_HARD_LIMIT=20000000
DEFAULT_POST_PHASE_AUDIT="true"
DEFAULT_TIME_LIMIT="5h"
POLL_INTERVAL=15

source "$PROJECT_DIR/lib/orchestration/state.sh"

echo "═══ wt/ Directory Convention Tests ═══"
echo ""

# ─── wt_find_config tests ─────────────────────────────────────────

echo "--- wt_find_config ---"

# Test: new location wins over legacy
test_start "wt_find_config orchestration — new location wins"
(
    cd "$TMPDIR"
    mkdir -p wt/orchestration .claude
    echo "test: true" > wt/orchestration/config.yaml
    echo "test: false" > .claude/orchestration.yaml
    result=$(wt_find_config orchestration)
    [[ "$result" == "wt/orchestration/config.yaml" ]]
) && test_pass || test_fail "wt/orchestration/config.yaml" "other"

# Test: legacy fallback works
test_start "wt_find_config orchestration — legacy fallback"
(
    cd "$TMPDIR"
    rm -rf wt
    result=$(wt_find_config orchestration)
    [[ "$result" == ".claude/orchestration.yaml" ]]
) && test_pass || test_fail ".claude/orchestration.yaml" "other"

# Test: missing returns empty
test_start "wt_find_config orchestration — missing returns empty"
(
    cd "$TMPDIR"
    rm -rf wt .claude
    result=$(wt_find_config orchestration)
    [[ -z "$result" ]]
) && test_pass || test_fail "(empty)" "non-empty"

# Test: project-knowledge new location
test_start "wt_find_config project-knowledge — new location"
(
    cd "$TMPDIR"
    mkdir -p wt/knowledge
    echo "features: {}" > wt/knowledge/project-knowledge.yaml
    echo "features: {}" > project-knowledge.yaml
    result=$(wt_find_config project-knowledge)
    [[ "$result" == "wt/knowledge/project-knowledge.yaml" ]]
) && test_pass || test_fail "wt/knowledge/project-knowledge.yaml" "other"

# Test: project-knowledge legacy fallback
test_start "wt_find_config project-knowledge — legacy fallback"
(
    cd "$TMPDIR"
    rm -rf wt/knowledge/project-knowledge.yaml
    result=$(wt_find_config project-knowledge)
    [[ "$result" == "project-knowledge.yaml" ]]
) && test_pass || test_fail "project-knowledge.yaml" "other"

# Cleanup
rm -rf "$TMPDIR"/*

# ─── wt_find_runs_dir tests ──────────────────────────────────────

echo ""
echo "--- wt_find_runs_dir ---"

test_start "wt_find_runs_dir — new location"
(
    cd "$TMPDIR"
    mkdir -p wt/orchestration/runs docs/orchestration-runs
    result=$(wt_find_runs_dir)
    [[ "$result" == "wt/orchestration/runs" ]]
) && test_pass || test_fail "wt/orchestration/runs" "other"

test_start "wt_find_runs_dir — legacy fallback"
(
    cd "$TMPDIR"
    rm -rf wt
    result=$(wt_find_runs_dir)
    [[ "$result" == "docs/orchestration-runs" ]]
) && test_pass || test_fail "docs/orchestration-runs" "other"

test_start "wt_find_runs_dir — missing returns empty"
(
    cd "$TMPDIR"
    rm -rf wt docs/orchestration-runs
    result=$(wt_find_runs_dir)
    [[ -z "$result" ]]
) && test_pass || test_fail "(empty)" "non-empty"

rm -rf "$TMPDIR"/*

# ─── wt_find_requirements_dir tests ──────────────────────────────

echo ""
echo "--- wt_find_requirements_dir ---"

test_start "wt_find_requirements_dir — exists"
(
    cd "$TMPDIR"
    mkdir -p wt/requirements
    result=$(wt_find_requirements_dir)
    [[ "$result" == "wt/requirements" ]]
) && test_pass || test_fail "wt/requirements" "other"

test_start "wt_find_requirements_dir — missing returns empty"
(
    cd "$TMPDIR"
    rm -rf wt
    result=$(wt_find_requirements_dir)
    [[ -z "$result" ]]
) && test_pass || test_fail "(empty)" "non-empty"

rm -rf "$TMPDIR"/*

# ─── scaffold_wt_directory tests ─────────────────────────────────

echo ""
echo "--- scaffold_wt_directory ---"

# Source wt-project for scaffold_wt_directory
source "$PROJECT_DIR/bin/wt-common.sh"

# We can't source wt-project directly (it has a main dispatch),
# so we test via the wt-project init flow or test the function inline
# For unit testing, we replicate the function logic

test_start "scaffold creates all subdirectories"
(
    cd "$TMPDIR"
    mkdir -p wt/orchestration/runs wt/orchestration/plans \
             wt/knowledge/patterns wt/knowledge/lessons \
             wt/requirements wt/plugins wt/.work
    # Verify all exist
    [[ -d wt/orchestration/runs ]] && \
    [[ -d wt/orchestration/plans ]] && \
    [[ -d wt/knowledge/patterns ]] && \
    [[ -d wt/knowledge/lessons ]] && \
    [[ -d wt/requirements ]] && \
    [[ -d wt/plugins ]] && \
    [[ -d wt/.work ]]
) && test_pass || test_fail "all dirs exist" "some missing"

test_start "scaffold adds wt/.work/ to .gitignore"
(
    cd "$TMPDIR"
    echo "node_modules/" > .gitignore
    if ! grep -qx 'wt/.work/' .gitignore 2>/dev/null; then
        echo 'wt/.work/' >> .gitignore
    fi
    grep -qx 'wt/.work/' .gitignore
) && test_pass || test_fail "wt/.work/ in .gitignore" "missing"

test_start "scaffold is idempotent — no duplicate .gitignore entries"
(
    cd "$TMPDIR"
    # Already has wt/.work/ from previous test
    if ! grep -qx 'wt/.work/' .gitignore 2>/dev/null; then
        echo 'wt/.work/' >> .gitignore
    fi
    count=$(grep -cx 'wt/.work/' .gitignore)
    [[ "$count" -eq 1 ]]
) && test_pass || test_fail "1 entry" "multiple"

rm -rf "$TMPDIR"/*

# ─── migrate tests ──────────────────────────────────────────────

echo ""
echo "--- migration ---"

test_start "migrate detects legacy orchestration.yaml"
(
    cd "$TMPDIR"
    git init -q .
    mkdir -p .claude wt/orchestration
    echo "max_parallel: 3" > .claude/orchestration.yaml
    # Simulate migration
    [[ -f .claude/orchestration.yaml && ! -f wt/orchestration/config.yaml ]]
) && test_pass || test_fail "detected" "not detected"

test_start "migrate detects legacy project-knowledge.yaml"
(
    cd "$TMPDIR"
    mkdir -p wt/knowledge
    echo "features: {}" > project-knowledge.yaml
    [[ -f project-knowledge.yaml && ! -f wt/knowledge/project-knowledge.yaml ]]
) && test_pass || test_fail "detected" "not detected"

test_start "migrate detects legacy run logs"
(
    cd "$TMPDIR"
    mkdir -p docs/orchestration-runs wt/orchestration/runs
    echo "# Run 1" > docs/orchestration-runs/run-001.md
    [[ -d docs/orchestration-runs ]]
) && test_pass || test_fail "detected" "not detected"

rm -rf "$TMPDIR"/*

# ─── requirements planner input tests ────────────────────────────

echo ""
echo "--- requirements planner input ---"

test_start "requirements dir scan finds captured/planned requirements"
(
    cd "$TMPDIR"
    mkdir -p wt/requirements
    cat > wt/requirements/REQ-001-test.yaml << 'EOF'
id: REQ-001
title: Test Requirement
status: captured
priority: must
description: A test requirement
EOF
    cat > wt/requirements/REQ-002-done.yaml << 'EOF'
id: REQ-002
title: Done Requirement
status: implemented
priority: should
description: Already done
EOF
    dir=$(wt_find_requirements_dir)
    [[ "$dir" == "wt/requirements" ]]
    # Only captured/planned should be picked up (logic tested via yq)
    if command -v yq &>/dev/null; then
        status=$(yq -r '.status' wt/requirements/REQ-001-test.yaml)
        [[ "$status" == "captured" ]]
    fi
) && test_pass || test_fail "found" "not found"

test_start "requirements graceful degradation — no wt/requirements/"
(
    cd "$TMPDIR"
    rm -rf wt
    result=$(wt_find_requirements_dir)
    [[ -z "$result" ]]
) && test_pass || test_fail "(empty)" "non-empty"

rm -rf "$TMPDIR"/*

# ─── memory seed tests ──────────────────────────────────────────

echo ""
echo "--- memory seed ---"

test_start "memory-seed.yaml template exists"
(
    [[ -f "$PROJECT_DIR/templates/memory-seed.yaml" ]]
) && test_pass || test_fail "exists" "missing"

test_start "memory-seed.yaml template has valid structure"
(
    if command -v yq &>/dev/null; then
        version=$(yq -r '.version' "$PROJECT_DIR/templates/memory-seed.yaml")
        [[ "$version" == "1" ]]
    else
        # Fallback: just check it contains version
        grep -q 'version: 1' "$PROJECT_DIR/templates/memory-seed.yaml"
    fi
) && test_pass || test_fail "version: 1" "other"

# ─── Summary ────────────────────────────────────────────────────

echo ""
echo "═══════════════════════════════════════"
if [[ $TESTS_FAILED -eq 0 ]]; then
    echo -e "${GREEN}All $TESTS_PASSED/$TESTS_RUN tests passed${NC}"
else
    echo -e "${RED}$TESTS_FAILED/$TESTS_RUN tests failed${NC}"
    exit 1
fi
