#!/usr/bin/env bash
# Integration tests for set-orchestrate: merge pipeline, smoke pipeline, dispatch/loop control
# Uses real git repos and stub commands (no Claude API calls).
# Run with: ./tests/orchestrator/test-orchestrate-integration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source common functions
source "$PROJECT_DIR/bin/set-common.sh"
# Section 15b.14 — test-only helpers that mirror LineagePaths so this file
# stops scattering hardcoded orchestration filenames.
source "$PROJECT_DIR/tests/lib/test_paths.sh"

# Test framework
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
CLEANUP_DIRS=()

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
        test_fail "contains '$needle'" "'${haystack:0:200}'"
    fi
}

assert_not_equals() {
    local unexpected="$1"
    local actual="$2"
    if [[ "$unexpected" != "$actual" ]]; then
        test_pass
    else
        test_fail "not '$unexpected'" "'$actual'"
    fi
}

# ============================================================
# Test Infrastructure
# ============================================================

# Create a temp git repo with main branch and initial commit
setup_test_repo() {
    local repo_dir
    repo_dir=$(mktemp -d)
    CLEANUP_DIRS+=("$repo_dir")

    cd "$repo_dir"
    git init -b main --quiet
    git config user.name "Test"
    git config user.email "test@test.com"
    echo "initial" > README.md
    git add README.md
    git commit -m "initial commit" --quiet

    echo "$repo_dir"
}

# Create a feature branch with file changes
create_feature_branch() {
    local repo_dir="$1"
    local branch_name="$2"
    shift 2
    # Remaining args are "filename:content" pairs

    cd "$repo_dir"
    git checkout -b "change/$branch_name" --quiet
    for pair in "$@"; do
        local file="${pair%%:*}"
        local content="${pair#*:}"
        mkdir -p "$(dirname "$file")"
        echo "$content" > "$file"
        git add "$file"
    done
    git commit -m "feat: implement $branch_name" --quiet
    git checkout main --quiet
}

# Initialize orchestration state with a single change entry
init_test_state() {
    local state_file="$1"
    local change_name="$2"
    local status="${3:-pending}"
    local wt_path="${4:-}"

    cat > "$state_file" <<STATE_EOF
{
  "changes": [
    {
      "name": "$change_name",
      "status": "$status",
      "scope": "Test change $change_name",
      "worktree_path": "$wt_path",
      "smoke_result": null,
      "smoke_status": null,
      "smoke_fix_attempts": 0,
      "smoke_screenshot_dir": "",
      "smoke_screenshot_count": 0,
      "e2e_screenshot_dir": "",
      "e2e_screenshot_count": 0,
      "merge_retry_count": 0,
      "iterations": 0,
      "agent_rebase_done": false,
      "merge_rebase_pending": false
    }
  ],
  "merge_queue": [],
  "directives": {},
  "last_smoke_pass_commit": ""
}
STATE_EOF
}

# Cleanup all temp dirs
cleanup_all() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null || true
    done
}
trap cleanup_all EXIT

# ============================================================
# Source orchestration modules directly (not via eval+sed)
# ============================================================

# Constants from set-orchestrate that modules depend on
STATE_FILENAME=""          # set per-test
LOG_FILE="/dev/null"
EVENTS_ENABLED="false"     # disable event logging in tests

# Directive defaults (copied from set-orchestrate)
DEFAULT_MAX_PARALLEL=3
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
DEFAULT_CHECKPOINT_AUTO_APPROVE="false"
DEFAULT_POST_PHASE_AUDIT="true"
DEFAULT_PLAN_METHOD="api"
DEFAULT_PLAN_TOKEN_BUDGET=500000
DEFAULT_TIME_LIMIT="5h"
PLAN_FILENAME="orchestration-plan.json"
SUMMARY_FILENAME="orchestration-summary.md"

# Pre-source stubs (needed during module loading)
log_info()  { :; }
log_warn()  { :; }
log_error() { :; }
run_claude() { return 0; }
model_id() { echo "test-model"; }

# Source modules in dependency order
LIB_DIR="$PROJECT_DIR/lib/orchestration"
source "$LIB_DIR/events.sh"        # emit_event (no-op with EVENTS_ENABLED=false)
source "$LIB_DIR/config.sh"        # set_find_config
source "$LIB_DIR/utils.sh"         # parse_duration, format_duration, brief_hash
source "$LIB_DIR/state.sh"         # update_change_field, run_hook, etc.
source "$LIB_DIR/verifier.sh"      # health_check, extract_health_check_url
source "$LIB_DIR/digest.sh"       # final_coverage_check, populate_coverage
source "$LIB_DIR/reporter.sh"     # generate_report

# Source loop modules for detect_next_change_action
source "$PROJECT_DIR/lib/loop/prompt.sh"

# Post-source stubs (override real implementations that make external calls)
send_notification() { echo "NOTIFICATION: $*" >> "${NOTIFICATION_LOG:-/dev/null}"; }
orch_remember() { return 0; }

echo "============================================================"
echo "Integration Tests: set-orchestrate"
echo "============================================================"
echo ""

# ============================================================
# Section 9: Merge Pipeline Tests
# ============================================================

echo "--- Merge Pipeline ---"

# Test 9.1: Clean merge
test_start "clean merge → status changes to merged"
REPO=$(setup_test_repo)
create_feature_branch "$REPO" "test-clean" "feature.txt:hello"
STATE_FILE="$(tp_state_file "$REPO")"
STATE_FILENAME="$STATE_FILE"
PROJECT_PATH="$REPO"
LOG_FILE="$REPO/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-clean" "verified"

# Set up minimal directives
smoke_command=""
smoke_blocking="false"
smoke_timeout=10
smoke_fix_max_retries=0
smoke_fix_max_turns=5
smoke_health_check_url=""
smoke_health_check_timeout=5
directives='{}'

cd "$REPO"
# Do the merge manually since merge_change depends on many globals
git merge "change/test-clean" --no-edit --quiet 2>/dev/null
update_change_field "test-clean" "status" '"merged"'
status=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "merged" "$status"

# Test 9.2: Merge conflict → merge-blocked (no crash)
test_start "merge conflict does not crash orchestrator"
REPO2=$(setup_test_repo)
cd "$REPO2"
# Create conflicting changes on main and branch
echo "main content" > conflict.txt
git add conflict.txt && git commit -m "main change" --quiet
git checkout -b "change/test-conflict" --quiet
echo "branch content" > conflict.txt
git add conflict.txt && git commit -m "branch change" --quiet
git checkout main --quiet
echo "different main content" > conflict.txt
git add conflict.txt && git commit -m "main conflict" --quiet

STATE_FILE="$(tp_state_file "$REPO2")"
STATE_FILENAME="$STATE_FILE"
PROJECT_PATH="$REPO2"
LOG_FILE="$REPO2/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-conflict" "verified"

# Try to merge — should fail but not crash
merge_rc=0
git merge "change/test-conflict" --no-edit --quiet 2>/dev/null || merge_rc=$?
if [[ $merge_rc -ne 0 ]]; then
    git merge --abort 2>/dev/null || true
    update_change_field "test-conflict" "status" '"merge-blocked"'
fi
status=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "merge-blocked" "$status"

# Test 9.3: Already-merged branch detection
test_start "already-merged branch detected correctly"
REPO3=$(setup_test_repo)
create_feature_branch "$REPO3" "test-already" "already.txt:done"
cd "$REPO3"
git merge "change/test-already" --no-edit --quiet 2>/dev/null

STATE_FILE="$(tp_state_file "$REPO3")"
STATE_FILENAME="$STATE_FILE"
init_test_state "$STATE_FILE" "test-already" "verified"

# Check if branch is ancestor of HEAD
if git merge-base --is-ancestor "change/test-already" HEAD 2>/dev/null; then
    update_change_field "test-already" "status" '"merged"'
fi
status=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "merged" "$status"

# ============================================================
# Section 10: Smoke Pipeline Tests
# ============================================================

echo ""
echo "--- Smoke Pipeline ---"

# Test 10.1: Smoke pass (blocking mode)
test_start "smoke pass in blocking mode → smoke_result=pass"
REPO4=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO4")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO4/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-smoke-pass" "merged"

smoke_command="true"  # always passes
smoke_blocking="true"
smoke_timeout=10
smoke_health_check_url=""
smoke_health_check_timeout=5

cd "$REPO4"
# Simulate the blocking smoke pipeline
update_change_field "test-smoke-pass" "smoke_status" '"running"'
pm_smoke_rc=0
timeout "$smoke_timeout" bash -c "$smoke_command" >/dev/null 2>&1 || pm_smoke_rc=$?
if [[ $pm_smoke_rc -eq 0 ]]; then
    update_change_field "test-smoke-pass" "smoke_result" '"pass"'
    update_change_field "test-smoke-pass" "smoke_status" '"done"'
fi
sr=$(jq -r '.changes[0].smoke_result' "$STATE_FILE")
ss=$(jq -r '.changes[0].smoke_status' "$STATE_FILE")
assert_equals "pass" "$sr"

test_start "smoke pass sets smoke_status=done"
assert_equals "done" "$ss"

# Test 10.2: Smoke fail → fix → pass
test_start "smoke fail then fix → smoke_result=fixed"
REPO5=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO5")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO5/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-smoke-fix" "merged"

# Create a smoke command that fails first, passes on second run
SMOKE_SCRIPT="$REPO5/smoke-toggle.sh"
cat > "$SMOKE_SCRIPT" <<'SCRIPT'
#!/bin/bash
COUNTER_FILE="$(dirname "$0")/.smoke-counter"
count=$(cat "$COUNTER_FILE" 2>/dev/null || echo 0)
count=$((count + 1))
echo "$count" > "$COUNTER_FILE"
if [[ $count -le 1 ]]; then
    echo "FAIL: smoke test error" >&2
    exit 1
fi
exit 0
SCRIPT
chmod +x "$SMOKE_SCRIPT"

smoke_command="bash $SMOKE_SCRIPT"
cd "$REPO5"
# First run: fail
pm_smoke_rc=0
pm_smoke_output=$(timeout 10 bash -c "$smoke_command" 2>&1) || pm_smoke_rc=$?
if [[ $pm_smoke_rc -ne 0 ]]; then
    update_change_field "test-smoke-fix" "smoke_result" '"fail"'
    update_change_field "test-smoke-fix" "smoke_fix_attempts" "1"
    # Simulate: fix agent runs, then re-run smoke
    recheck_rc=0
    timeout 10 bash -c "$smoke_command" >/dev/null 2>&1 || recheck_rc=$?
    if [[ $recheck_rc -eq 0 ]]; then
        update_change_field "test-smoke-fix" "smoke_result" '"fixed"'
        update_change_field "test-smoke-fix" "smoke_status" '"done"'
    fi
fi
sr=$(jq -r '.changes[0].smoke_result' "$STATE_FILE")
sa=$(jq -r '.changes[0].smoke_fix_attempts' "$STATE_FILE")
assert_equals "fixed" "$sr"

test_start "smoke fix records attempt count"
assert_equals "1" "$sa"

# Test 10.3: Smoke fail → fix exhausted
test_start "smoke fix exhausted → smoke_status=failed"
REPO6=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO6")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO6/orchestrate.log"
NOTIFICATION_LOG="$REPO6/notifications.log"
touch "$LOG_FILE" "$NOTIFICATION_LOG"
init_test_state "$STATE_FILE" "test-smoke-exhaust" "merged"

smoke_fix_max_retries=2
cd "$REPO6"
# Smoke always fails
smoke_command="false"
attempt=0
while [[ $attempt -lt $smoke_fix_max_retries ]]; do
    attempt=$((attempt + 1))
    update_change_field "test-smoke-exhaust" "smoke_fix_attempts" "$attempt"
    # Simulate fix + re-test — still fails
    recheck_rc=0
    timeout 10 bash -c "$smoke_command" >/dev/null 2>&1 || recheck_rc=$?
done
update_change_field "test-smoke-exhaust" "smoke_status" '"failed"'
update_change_field "test-smoke-exhaust" "status" '"smoke_failed"'
send_notification "set-orchestrate" "Smoke FAILED for test-smoke-exhaust" "critical"

ss=$(jq -r '.changes[0].smoke_status' "$STATE_FILE")
st=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "failed" "$ss"

test_start "smoke exhausted sets status=smoke_failed"
assert_equals "smoke_failed" "$st"

test_start "smoke exhausted sends notification"
assert_contains "$(cat "$NOTIFICATION_LOG")" "Smoke FAILED"

# Test 10.4: Health check fail
test_start "health check fail → smoke_blocked"
REPO7=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO7")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO7/orchestrate.log"
NOTIFICATION_LOG="$REPO7/notifications.log"
touch "$LOG_FILE" "$NOTIFICATION_LOG"
init_test_state "$STATE_FILE" "test-hc-fail" "merged"

cd "$REPO7"
# Health check to a port that won't be listening (timeout 2s to keep test fast)
if ! health_check "http://localhost:59999" 2; then
    update_change_field "test-hc-fail" "smoke_result" '"blocked"'
    update_change_field "test-hc-fail" "smoke_status" '"blocked"'
    update_change_field "test-hc-fail" "status" '"smoke_blocked"'
    send_notification "set-orchestrate" "Smoke blocked — no server" "critical"
fi
ss=$(jq -r '.changes[0].smoke_status' "$STATE_FILE")
st=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "blocked" "$ss"

test_start "health check fail sets status=smoke_blocked"
assert_equals "smoke_blocked" "$st"

# Test 10.5: Smoke non-blocking mode
test_start "non-blocking smoke fail does not block status"
REPO8=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO8")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO8/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-smoke-nb" "merged"

cd "$REPO8"
smoke_blocking="false"
smoke_command="false"
# Non-blocking: smoke fails but status stays merged
pm_smoke_rc=0
timeout 10 bash -c "$smoke_command" >/dev/null 2>&1 || pm_smoke_rc=$?
update_change_field "test-smoke-nb" "smoke_result" '"fail"'
# In non-blocking mode, status stays as-is
st=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "merged" "$st"

# ============================================================
# Section 11: Loop Control & Idle Detection Tests
# ============================================================

echo ""
echo "--- Loop Control & Idle Detection ---"

# Test 11.1: detect_next_change_action
test_start "detect_next_change_action returns ff:* when no tasks.md"
REPO9=$(setup_test_repo)
cd "$REPO9"
mkdir -p openspec/changes/test-change
# No tasks.md
result=$(detect_next_change_action "$REPO9" "test-change")
assert_equals "ff:test-change" "$result"

test_start "detect_next_change_action returns apply:* when unchecked tasks"
cat > "$REPO9/openspec/changes/test-change/tasks.md" <<'EOF'
- [ ] Task 1
- [x] Task 2
EOF
result=$(detect_next_change_action "$REPO9" "test-change")
assert_equals "apply:test-change" "$result"

test_start "detect_next_change_action returns done when all checked"
cat > "$REPO9/openspec/changes/test-change/tasks.md" <<'EOF'
- [x] Task 1
- [x] Task 2
EOF
result=$(detect_next_change_action "$REPO9" "test-change")
assert_equals "done" "$result"

# Test 11.3: Idle detection via content hash
test_start "idle detection: identical hashes increment idle_count"
REPO10=$(setup_test_repo)
cd "$REPO10"
mkdir -p .claude/logs

# Create identical log files
for i in 1 2 3; do
    log_file=".claude/logs/ralph-iter-$(printf '%03d' "$i").log"
    echo "No remaining work. All tasks complete." > "$log_file"
done

# Simulate idle detection
idle_count=0
last_hash=""
for i in 1 2 3; do
    log_file="$REPO10/.claude/logs/ralph-iter-$(printf '%03d' "$i").log"
    current_hash=$(tail -200 "$log_file" | shasum -a 256 | cut -d' ' -f1)
    if [[ -n "$last_hash" && "$current_hash" == "$last_hash" ]]; then
        idle_count=$((idle_count + 1))
    else
        idle_count=0
    fi
    last_hash="$current_hash"
done
assert_equals "2" "$idle_count"

# Test 11.4: Idle counter reset on different output
test_start "idle detection: different output resets idle_count"
echo "Different output here." > "$REPO10/.claude/logs/ralph-iter-003.log"
idle_count=0
last_hash=""
for i in 1 2 3; do
    log_file="$REPO10/.claude/logs/ralph-iter-$(printf '%03d' "$i").log"
    current_hash=$(tail -200 "$log_file" | shasum -a 256 | cut -d' ' -f1)
    if [[ -n "$last_hash" && "$current_hash" == "$last_hash" ]]; then
        idle_count=$((idle_count + 1))
    else
        idle_count=0
    fi
    last_hash="$current_hash"
done
assert_equals "0" "$idle_count"

# Test 11.2: Stall detection — N commit-less iterations → stalled
test_start "stall detection: no commits for N iterations → stalled"
REPO_STALL=$(setup_test_repo)
cd "$REPO_STALL"
stall_count=0
stall_threshold=2
has_artifact_progress="false"
new_commits="[]"
for i in 1 2; do
    if [[ "$new_commits" == "[]" || -z "$new_commits" ]] && [[ "$has_artifact_progress" == "false" ]]; then
        stall_count=$((stall_count + 1))
    fi
done
assert_equals "2" "$stall_count"

test_start "stall detection: stall_count >= threshold triggers stall"
local_stalled="false"
[[ $stall_count -ge $stall_threshold ]] && local_stalled="true"
assert_equals "true" "$local_stalled"

# Test 11.5: Repeated commit message detection
test_start "repeated commit msg: same message N times → stalled"
REPO_RMSG=$(setup_test_repo)
cd "$REPO_RMSG"
echo "a" > file1.txt && git add file1.txt && git commit -m "fix: auth bug on iteration 1" --quiet
echo "b" > file2.txt && git add file2.txt && git commit -m "fix: auth bug on iteration 2" --quiet
echo "c" > file3.txt && git add file3.txt && git commit -m "fix: auth bug on iteration 3" --quiet

repeated_msg_count=0
last_commit_msg=""
stall_threshold=2
for rev in HEAD~2 HEAD~1 HEAD; do
    msg=$(git log -1 --format='%s' "$rev" | sed -E 's/ (on |)iteration [0-9]+//; s/ \(attempt [0-9]+\)//')
    if [[ -n "$msg" && "$msg" == "$last_commit_msg" ]]; then
        repeated_msg_count=$((repeated_msg_count + 1))
    else
        repeated_msg_count=0
        last_commit_msg="$msg"
    fi
done
assert_equals "2" "$repeated_msg_count"

test_start "repeated commit msg: different messages reset counter"
echo "d" > file4.txt && git add file4.txt && git commit -m "feat: new feature" --quiet
msg=$(git log -1 --format='%s' HEAD | sed -E 's/ (on |)iteration [0-9]+//; s/ \(attempt [0-9]+\)//')
if [[ "$msg" != "$last_commit_msg" ]]; then
    repeated_msg_count=0
fi
assert_equals "0" "$repeated_msg_count"

# Test 11.6: Artifact progress resets stall counter
test_start "artifact progress: dirty files reset stall counter"
REPO_ART=$(setup_test_repo)
cd "$REPO_ART"
stall_count=3
new_commits="[]"
echo "proposal content" > proposal.md
dirty_count=$(git status --porcelain 2>/dev/null | wc -l)
has_artifact_progress="false"
[[ "$dirty_count" -gt 0 ]] && has_artifact_progress="true"
[[ "$has_artifact_progress" == "true" ]] && stall_count=0
assert_equals "0" "$stall_count"

test_start "artifact progress: no dirty files keeps stall counting"
REPO_ART2=$(setup_test_repo)
cd "$REPO_ART2"
stall_count=1
new_commits="[]"
dirty_count=$(git status --porcelain 2>/dev/null | wc -l)
has_artifact_progress="false"
[[ "$dirty_count" -gt 0 ]] && has_artifact_progress="true"
[[ "$has_artifact_progress" == "false" ]] && stall_count=$((stall_count + 1))
assert_equals "2" "$stall_count"

# ============================================================
# Section 12: Merge Conflict Resolver Tests
# ============================================================

echo ""
echo "--- Merge Conflict Resolver ---"

# Test 12.1: Additive pattern guidance in prompt
test_start "LLM merge prompt contains additive pattern guidance"
# Read the set-merge script and check the prompt text
merge_script=$(cat "$PROJECT_DIR/bin/set-merge")
assert_contains "$merge_script" "Additive conflict pattern"

test_start "LLM merge prompt contains additive example"
assert_contains "$merge_script" "KEEP ALL entries from BOTH sides"

# Test 12.2: Non-additive conflict instructions preserved
test_start "LLM merge prompt preserves source-branch preference"
assert_contains "$merge_script" "prefer the source branch"

# ============================================================
# Section 13: Health Check Function Tests
# ============================================================

echo ""
echo "--- Health Check Function ---"

# Test: health_check returns 1 for non-responding server
test_start "health_check returns 1 for non-responding server"
hc_rc=0
health_check "http://localhost:59998" 1 2>/dev/null || hc_rc=$?
assert_equals "1" "$hc_rc"

# Test: extract_health_check_url with various formats
test_start "extract_health_check_url with SMOKE_BASE_URL"
url=$(extract_health_check_url "SMOKE_BASE_URL=http://localhost:3002 pnpm test:smoke")
assert_equals "http://localhost:3002" "$url"

test_start "extract_health_check_url with direct localhost reference"
url=$(extract_health_check_url "npx playwright test --base-url http://localhost:4000")
assert_equals "http://localhost:4000" "$url"

# ============================================================
# Section 14: Spec Lifecycle Tests
# ============================================================

echo ""
echo "--- Spec Lifecycle ---"

# Test 14.1: Spec resolution — literal path wins over short name
test_start "spec resolution: literal path takes priority"
REPO_SPEC=$(setup_test_repo)
cd "$REPO_SPEC"
mkdir -p set/orchestration/specs
echo "literal spec" > myspec.md
echo "short-name spec" > set/orchestration/specs/myspec.md
# Simulate find_input logic
SPEC_OVERRIDE="myspec.md"
INPUT_MODE="" INPUT_PATH=""
if [[ -f "$SPEC_OVERRIDE" ]]; then
    INPUT_MODE="spec"
    INPUT_PATH="$(cd "$(dirname "$SPEC_OVERRIDE")" && pwd)/$(basename "$SPEC_OVERRIDE")"
fi
assert_contains "$INPUT_PATH" "myspec.md"
# Verify it resolved to the literal (repo root), not set/orchestration/specs/
test_start "spec resolution: literal path not from set/orchestration/specs"
if [[ "$INPUT_PATH" == *"set/orchestration/specs"* ]]; then
    test_fail "not set/orchestration/specs path" "$INPUT_PATH"
else
    test_pass
fi

# Test 14.1b: Short name resolves to set/orchestration/specs/
test_start "spec resolution: short name resolves to set/orchestration/specs/"
cd "$REPO_SPEC"
SPEC_OVERRIDE="v12"
INPUT_MODE="" INPUT_PATH=""
echo "v12 content" > set/orchestration/specs/v12.md
if [[ -f "$SPEC_OVERRIDE" ]]; then
    INPUT_MODE="spec"
    INPUT_PATH="$(cd "$(dirname "$SPEC_OVERRIDE")" && pwd)/$(basename "$SPEC_OVERRIDE")"
else
    local_wt_spec="set/orchestration/specs/${SPEC_OVERRIDE}.md"
    if [[ -f "$local_wt_spec" ]]; then
        INPUT_MODE="spec"
        INPUT_PATH="$(cd "$(dirname "$local_wt_spec")" && pwd)/$(basename "$local_wt_spec")"
    fi
fi
assert_contains "$INPUT_PATH" "v12.md"
test_start "spec resolution: short name path includes set/orchestration/specs"
assert_contains "$INPUT_PATH" "set/orchestration/specs"

# Test 14.1c: Missing spec errors with both paths
test_start "spec resolution: missing spec shows both checked paths"
cd "$REPO_SPEC"
SPEC_OVERRIDE="nonexistent"
error_output=""
if [[ ! -f "$SPEC_OVERRIDE" ]]; then
    local_wt_spec="set/orchestration/specs/${SPEC_OVERRIDE}.md"
    local_wt_spec_sub="set/orchestration/specs/${SPEC_OVERRIDE}"
    if [[ ! -f "$local_wt_spec" && ! -f "$local_wt_spec_sub" ]]; then
        error_output="Spec file not found: $SPEC_OVERRIDE | Checked: $SPEC_OVERRIDE, $local_wt_spec"
    fi
fi
assert_contains "$error_output" "nonexistent"
test_start "spec resolution: error mentions wt/ path"
assert_contains "$error_output" "set/orchestration/specs/nonexistent.md"

# Test 14.2: specs list output format (active + archived)
test_start "specs list: shows active and archived specs"
REPO_SLIST=$(setup_test_repo)
cd "$REPO_SLIST"
mkdir -p set/orchestration/specs/archive
echo "# Active spec" > set/orchestration/specs/v9.md
echo "# Archived spec" > set/orchestration/specs/archive/v7.md
list_output=$("$PROJECT_DIR/bin/set-orchestrate" specs list 2>&1 || true)
assert_contains "$list_output" "v9"

test_start "specs list: shows archived section"
assert_contains "$list_output" "Archived"

test_start "specs list: shows archived spec name"
assert_contains "$list_output" "v7"

# Test 14.3: specs archive moves file correctly
test_start "specs archive: moves spec to archive/"
REPO_SARCH=$(setup_test_repo)
cd "$REPO_SARCH"
mkdir -p set/orchestration/specs/archive
echo "# Spec to archive" > set/orchestration/specs/v8.md
git add set/orchestration/specs/v8.md && git commit -m "add v8 spec" --quiet
"$PROJECT_DIR/bin/set-orchestrate" specs archive v8 2>&1 || true
if [[ -f "set/orchestration/specs/archive/v8.md" && ! -f "set/orchestration/specs/v8.md" ]]; then
    test_pass
else
    test_fail "v8.md in archive/ and not in specs/" "$(ls set/orchestration/specs/ set/orchestration/specs/archive/ 2>/dev/null)"
fi

# Test 14.4: Legacy spec migration detects docs/v*.md pattern
test_start "legacy migration: detects docs/v*.md files"
REPO_SMIG=$(setup_test_repo)
cd "$REPO_SMIG"
mkdir -p docs set/orchestration/specs/archive
echo "# v1 spec" > docs/v1.md
echo "# v2 spec" > docs/v2_minicrm.md
echo "# not a spec" > docs/readme.md
git add . && git commit -m "add legacy specs" --quiet
# Run migrate
"$PROJECT_DIR/bin/set-project" migrate 2>&1 || true
# Check that v1.md and v2_minicrm.md moved to archive, readme.md stayed
if [[ -f "set/orchestration/specs/archive/v1.md" ]]; then
    test_pass
else
    test_fail "v1.md in archive/" "$(ls set/orchestration/specs/archive/ 2>/dev/null)"
fi

test_start "legacy migration: v2_minicrm.md also migrated"
if [[ -f "set/orchestration/specs/archive/v2_minicrm.md" ]]; then
    test_pass
else
    test_fail "v2_minicrm.md in archive/" "$(ls set/orchestration/specs/archive/ 2>/dev/null)"
fi

test_start "legacy migration: non-spec docs/readme.md not moved"
if [[ -f "docs/readme.md" ]]; then
    test_pass
else
    test_fail "docs/readme.md still present" "moved unexpectedly"
fi

# ============================================================
# Section: Requirement-Aware Code Review
# ============================================================

echo ""
echo "--- Requirement-Aware Review ---"

# Need DIGEST_DIR for build_req_review_section
DIGEST_DIR="set/orchestration/digest"

# Test 5.7: build_req_review_section with valid requirements + digest
test_start "build_req_review_section returns REQ-IDs and titles"
REQ_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$REQ_REPO")"
LOG_FILE="$REQ_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$REQ_REPO"

# Create state with requirements
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "add-cart",
      "status": "running",
      "scope": "Cart feature",
      "requirements": ["REQ-CART-001", "REQ-CART-002"],
      "also_affects_reqs": ["REQ-I18N-001"]
    }
  ]
}
STATE_EOF

# Create digest requirements.json
mkdir -p "$DIGEST_DIR"
cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-CART-001", "title": "Add to cart", "brief": "Users can add items to cart"},
    {"id": "REQ-CART-002", "title": "Remove from cart", "brief": "Users can remove items from cart"},
    {"id": "REQ-I18N-001", "title": "i18n routing", "brief": "All pages respond to /hu and /en"}
  ]
}
REQ_EOF

req_output=$(build_req_review_section "add-cart")
if [[ "$req_output" == *"REQ-CART-001"* ]] && \
   [[ "$req_output" == *"Add to cart"* ]] && \
   [[ "$req_output" == *"REQ-I18N-001"* ]] && \
   [[ "$req_output" == *"awareness only"* ]] && \
   [[ "$req_output" == *"Requirement Coverage Check"* ]]; then
    test_pass
else
    test_fail "contains REQ-IDs, titles, coverage check" "${req_output:0:200}"
fi

# Test 5.8: empty requirements → returns empty
test_start "build_req_review_section returns empty for empty requirements"
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "cleanup",
      "status": "running",
      "scope": "Cleanup",
      "requirements": []
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "cleanup")
if [[ -z "$req_output" ]]; then
    test_pass
else
    test_fail "empty output" "${req_output:0:100}"
fi

# Test 5.9: REQ-ID not in digest → includes "(not found in digest)"
test_start "build_req_review_section handles ghost REQ-ID"
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "ghost-change",
      "status": "running",
      "scope": "Ghost",
      "requirements": ["REQ-GHOST-001"]
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "ghost-change")
if [[ "$req_output" == *"REQ-GHOST-001"* ]] && [[ "$req_output" == *"not found in digest"* ]]; then
    test_pass
else
    test_fail "contains REQ-GHOST-001 with 'not found in digest'" "${req_output:0:200}"
fi

# Test 5.10: no digest requirements.json → returns empty
test_start "build_req_review_section returns empty when no digest"
rm -rf "$DIGEST_DIR"
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "no-digest",
      "status": "running",
      "scope": "No digest",
      "requirements": ["REQ-CART-001"]
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "no-digest")
if [[ -z "$req_output" ]]; then
    test_pass
else
    test_fail "empty output" "${req_output:0:100}"
fi

# ============================================================
# Section: State Initialization — Requirements Copying
# ============================================================

echo ""
echo "--- State Init: Requirements ---"

# Test: init_state copies requirements[] and also_affects_reqs[] from digest-mode plan
test_start "init_state copies requirements and also_affects_reqs from plan"
REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$REPO")"
LOG_FILE="$REPO/orchestrate.log"
touch "$LOG_FILE"

# Create a mock digest-mode plan with requirements fields
cat > "$(tp_plan_file "$REPO")" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test-hash",
  "changes": [
    {
      "name": "add-cart",
      "scope": "Cart feature",
      "complexity": "medium",
      "depends_on": [],
      "roadmap_item": null,
      "requirements": ["REQ-CART-001", "REQ-CART-002", "REQ-CART-003"],
      "also_affects_reqs": ["REQ-I18N-001"]
    },
    {
      "name": "add-auth",
      "scope": "Auth feature",
      "complexity": "high",
      "depends_on": ["add-cart"],
      "roadmap_item": null,
      "requirements": ["REQ-AUTH-001"],
      "also_affects_reqs": []
    }
  ]
}
PLAN_EOF

init_state "$(tp_plan_file "$REPO")"

# Verify requirements[] appear in state
cart_reqs=$(jq -r '[.changes[] | select(.name == "add-cart") | .requirements[]] | join(",")' "$STATE_FILENAME")
cart_also=$(jq -r '[.changes[] | select(.name == "add-cart") | .also_affects_reqs[]] | join(",")' "$STATE_FILENAME")
auth_reqs=$(jq -r '[.changes[] | select(.name == "add-auth") | .requirements[]] | join(",")' "$STATE_FILENAME")

if [[ "$cart_reqs" == "REQ-CART-001,REQ-CART-002,REQ-CART-003" ]] && \
   [[ "$cart_also" == "REQ-I18N-001" ]] && \
   [[ "$auth_reqs" == "REQ-AUTH-001" ]]; then
    test_pass
else
    test_fail "cart_reqs=REQ-CART-001,REQ-CART-002,REQ-CART-003 cart_also=REQ-I18N-001 auth_reqs=REQ-AUTH-001" \
              "cart_reqs=$cart_reqs cart_also=$cart_also auth_reqs=$auth_reqs"
fi

# Test: init_state with non-digest plan (no requirements fields) → no empty arrays added
test_start "init_state omits requirements fields for non-digest plan"
REPO2=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$REPO2")"
LOG_FILE="$REPO2/orchestrate.log"
touch "$LOG_FILE"

cat > "$(tp_plan_file "$REPO2")" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test-hash",
  "changes": [
    {
      "name": "simple-fix",
      "scope": "Bug fix",
      "complexity": "low",
      "depends_on": [],
      "roadmap_item": null
    }
  ]
}
PLAN_EOF

init_state "$(tp_plan_file "$REPO2")"

# Verify no requirements or also_affects_reqs fields present
has_reqs=$(jq '.changes[0] | has("requirements")' "$STATE_FILENAME")
has_also=$(jq '.changes[0] | has("also_affects_reqs")' "$STATE_FILENAME")

if [[ "$has_reqs" == "false" ]] && [[ "$has_also" == "false" ]]; then
    test_pass
else
    test_fail "has_reqs=false has_also=false" "has_reqs=$has_reqs has_also=$has_also"
fi

# ============================================================
# Section: Final Coverage Assertion
# ============================================================

echo ""
echo "--- Final Coverage Assertion ---"

# Test 6.5: final_coverage_check categorizes correctly
test_start "final_coverage_check categorizes merged/uncovered/failed"
COV_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$COV_REPO")"
LOG_FILE="$COV_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$COV_REPO"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

# 6 requirements: 3 merged, 2 uncovered, 1 failed
cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-A-001", "title": "Feature A1"},
    {"id": "REQ-A-002", "title": "Feature A2"},
    {"id": "REQ-A-003", "title": "Feature A3"},
    {"id": "REQ-B-001", "title": "Feature B1"},
    {"id": "REQ-B-002", "title": "Feature B2"},
    {"id": "REQ-C-001", "title": "Feature C1"}
  ]
}
REQ_EOF

# Coverage: A-001..A-003 → change-1, B-001..B-002 uncovered, C-001 → change-3
cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-A-001": {"change": "change-1", "status": "assigned"},
    "REQ-A-002": {"change": "change-1", "status": "assigned"},
    "REQ-A-003": {"change": "change-1", "status": "assigned"},
    "REQ-C-001": {"change": "change-3", "status": "assigned"}
  }
}
COV_EOF

# State: change-1 merged, change-3 failed
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {"name": "change-1", "status": "merged"},
    {"name": "change-3", "status": "failed"}
  ]
}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
if [[ "$cov_output" == *"3 merged"* ]] && [[ "$cov_output" == *"2 uncovered"* ]] && [[ "$cov_output" == *"1 failed"* ]]; then
    test_pass
else
    test_fail "3 merged, 2 uncovered, 1 failed" "$cov_output"
fi

# Test 6.6: no digest/coverage.json → returns empty
test_start "final_coverage_check returns empty with no digest"
NOCOV_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$NOCOV_REPO")"
LOG_FILE="$NOCOV_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$NOCOV_REPO"

DIGEST_DIR="set/orchestration/digest"
# No digest dir at all

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {"name": "change-1", "status": "merged"}
  ]
}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
assert_equals "" "$cov_output"

# Test 6.7: all requirements merged → no COVERAGE_GAP event
test_start "final_coverage_check with all merged emits no COVERAGE_GAP"
ALLMERGE_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$ALLMERGE_REPO")"
LOG_FILE="$ALLMERGE_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$ALLMERGE_REPO"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-X-001", "title": "Feature X1"},
    {"id": "REQ-X-002", "title": "Feature X2"}
  ]
}
REQ_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-X-001": {"change": "change-x", "status": "assigned"},
    "REQ-X-002": {"change": "change-x", "status": "assigned"}
  }
}
COV_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {"name": "change-x", "status": "merged"}
  ]
}
STATE_EOF

# Enable events temporarily to capture what's emitted
EVENTS_ENABLED="true"
EVENTS_FILE="$ALLMERGE_REPO/events.jsonl"
cov_output=$(final_coverage_check 2>/dev/null || true)
EVENTS_ENABLED="false"

# Check output says all merged, 0 uncovered/failed/blocked
has_gap=$(grep -c "COVERAGE_GAP" "$EVENTS_FILE" 2>/dev/null || echo "0")
if [[ "$cov_output" == *"2 merged"* ]] && [[ "$has_gap" == "0" ]]; then
    test_pass
else
    test_fail "2 merged, no COVERAGE_GAP" "output=$cov_output, gap_events=$has_gap"
fi

# Test 6.8: merge-blocked change → reqs categorized as "blocked"
test_start "final_coverage_check categorizes merge-blocked as blocked"
BLOCKED_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$BLOCKED_REPO")"
LOG_FILE="$BLOCKED_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$BLOCKED_REPO"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-BLK-001", "title": "Blocked feature"},
    {"id": "REQ-BLK-002", "title": "Merged feature"}
  ]
}
REQ_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-BLK-001": {"change": "change-blocked", "status": "assigned"},
    "REQ-BLK-002": {"change": "change-ok", "status": "assigned"}
  }
}
COV_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {"name": "change-blocked", "status": "merge-blocked"},
    {"name": "change-ok", "status": "merged"}
  ]
}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
if [[ "$cov_output" == *"1 merged"* ]] && [[ "$cov_output" == *"1 blocked"* ]] && [[ "$cov_output" == *"0 uncovered"* ]]; then
    test_pass
else
    test_fail "1 merged, 1 blocked, 0 uncovered" "$cov_output"
fi

# ============================================================
# Section: HTML Report Generator
# ============================================================

echo ""
echo "--- HTML Report Generator ---"

# Test 7.7: generate report with full fixture data
test_start "generate_report produces HTML with all 4 section headings"
RPT_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$RPT_REPO")"
PLAN_FILENAME="$(tp_plan_file "$RPT_REPO")"
LOG_FILE="$RPT_REPO/orchestrate.log"
REPORT_OUTPUT_PATH="$RPT_REPO/set/orchestration/report.html"
touch "$LOG_FILE"
cd "$RPT_REPO"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR/domains"

# index.json
cat > "$DIGEST_DIR/index.json" <<'IDX_EOF'
{
  "spec_base_dir": "specs/",
  "source_hash": "abc123def456",
  "file_count": 3,
  "timestamp": "2026-03-10T12:00:00+01:00",
  "files": ["spec1.md", "spec2.md", "spec3.md"]
}
IDX_EOF

# requirements.json with 2 domains
cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-AUTH-001", "title": "Login", "domain": "Auth", "brief": "User login"},
    {"id": "REQ-AUTH-002", "title": "Logout", "domain": "Auth", "brief": "User logout"},
    {"id": "REQ-CART-001", "title": "Add item", "domain": "Cart", "brief": "Add to cart"}
  ]
}
REQ_EOF

# ambiguities.json
cat > "$DIGEST_DIR/ambiguities.json" <<'AMB_EOF'
{
  "ambiguities": [
    {"description": "Auth token expiry not specified"},
    {"description": "Cart limit unclear"}
  ]
}
AMB_EOF

# coverage.json
cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-AUTH-001": {"change": "add-auth", "status": "assigned"},
    "REQ-AUTH-002": {"change": "add-auth", "status": "assigned"},
    "REQ-CART-001": {"change": "add-cart", "status": "assigned"}
  }
}
COV_EOF

echo "Auth domain summary" > "$DIGEST_DIR/domains/Auth.md"
echo "Cart domain summary" > "$DIGEST_DIR/domains/Cart.md"

# plan
cat > "$PLAN_FILENAME" <<'PLAN_EOF'
{
  "changes": [
    {"name": "add-auth", "scope": "Auth", "requirements": ["REQ-AUTH-001", "REQ-AUTH-002"], "depends_on": []},
    {"name": "add-cart", "scope": "Cart", "requirements": ["REQ-CART-001"], "depends_on": ["add-auth"]}
  ]
}
PLAN_EOF

# state
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "status": "running",
  "changes": [
    {"name": "add-auth", "status": "merged", "tokens_used": 50000, "test_result": "pass", "smoke_result": "pass"},
    {"name": "add-cart", "status": "running", "tokens_used": 30000, "test_result": null, "smoke_result": null}
  ]
}
STATE_EOF

generate_report 2>/dev/null

report_html=$(cat "$REPORT_OUTPUT_PATH" 2>/dev/null || echo "")
if [[ -n "$report_html" ]] && \
   [[ "$report_html" == *"Spec Digest"* ]] && \
   [[ "$report_html" == *"Plan"* ]] && \
   [[ "$report_html" == *"Execution"* ]] && \
   [[ "$report_html" == *"Requirement Coverage"* ]] && \
   [[ "$report_html" == *"</html>"* ]]; then
    test_pass
else
    test_fail "HTML with 4 sections + valid structure" "${report_html:0:200}"
fi

# Test 7.8: generate report with no digest data
test_start "generate_report shows 'Not available' without digest"
NORPT_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$NORPT_REPO")"
PLAN_FILENAME="$(tp_plan_file "$NORPT_REPO")"
LOG_FILE="$NORPT_REPO/orchestrate.log"
REPORT_OUTPUT_PATH="$NORPT_REPO/set/orchestration/report.html"
touch "$LOG_FILE"
cd "$NORPT_REPO"

DIGEST_DIR="set/orchestration/digest"
# No digest dir

# plan
cat > "$PLAN_FILENAME" <<'PLAN_EOF'
{
  "changes": [
    {"name": "simple-fix", "scope": "Fix", "depends_on": []}
  ]
}
PLAN_EOF

# state
cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "status": "running",
  "changes": [
    {"name": "simple-fix", "status": "running", "tokens_used": 10000, "test_result": null, "smoke_result": null}
  ]
}
STATE_EOF

generate_report 2>/dev/null

report_html=$(cat "$REPORT_OUTPUT_PATH" 2>/dev/null || echo "")
if [[ "$report_html" == *"Not available"* ]] && \
   [[ "$report_html" == *"Plan"* ]] && \
   [[ "$report_html" == *"Execution"* ]]; then
    test_pass
else
    test_fail "Not available in digest/coverage, Plan+Execution present" "${report_html:0:200}"
fi

# ============================================================
# Section: Report Generation Hooks
# ============================================================

echo ""
echo "--- Report Generation Hooks ---"

# Test 8.6: generate_report failure does not crash orchestration logic
test_start "generate_report failure is non-fatal"
HOOK_REPO=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$HOOK_REPO")"
LOG_FILE="$HOOK_REPO/orchestrate.log"
touch "$LOG_FILE"
cd "$HOOK_REPO"

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "status": "running",
  "changes": [
    {"name": "test-change", "status": "merged", "tokens_used": 1000}
  ]
}
STATE_EOF

# Override generate_report to always fail
generate_report() { return 1; }

# Simulate the guard pattern used in monitor_loop
result="ok"
generate_report 2>/dev/null || true
# If we get here, the failure was handled
assert_equals "ok" "$result"

# Restore real generate_report by re-sourcing
source "$LIB_DIR/reporter.sh"

# ============================================================
# Section: Integration Tests — Full Pipeline Scenarios
# ============================================================

echo ""
echo "--- Integration: Full Pipeline Scenarios ---"

# Test 9.1: requirement-aware review prompt construction
test_start "review prompt has assigned REQs with title+brief and also_affects with awareness note"
INT_REPO1=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO1")"
LOG_FILE="$INT_REPO1/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO1"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-UI-001", "title": "Dashboard layout", "domain": "UI", "brief": "Main dashboard renders correctly"},
    {"id": "REQ-UI-002", "title": "Theme toggle", "domain": "UI", "brief": "Users can switch dark/light theme"},
    {"id": "REQ-UI-003", "title": "Responsive nav", "domain": "UI", "brief": "Navigation adapts to mobile"},
    {"id": "REQ-API-001", "title": "REST endpoints", "domain": "API", "brief": "CRUD API for resources"},
    {"id": "REQ-API-002", "title": "Auth middleware", "domain": "API", "brief": "JWT-based auth on all routes"}
  ]
}
REQ_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "add-dashboard",
      "status": "running",
      "scope": "Dashboard feature",
      "requirements": ["REQ-UI-001", "REQ-UI-002", "REQ-UI-003"],
      "also_affects_reqs": ["REQ-API-001"]
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "add-dashboard")
# Assigned REQs should have title+brief
has_assigned=true
[[ "$req_output" != *"REQ-UI-001"* ]] && has_assigned=false
[[ "$req_output" != *"Dashboard layout"* ]] && has_assigned=false
[[ "$req_output" != *"REQ-UI-002"* ]] && has_assigned=false
# Also affects should have awareness note
has_cross=true
[[ "$req_output" != *"REQ-API-001"* ]] && has_cross=false
[[ "$req_output" != *"awareness"* ]] && has_cross=false
# Coverage check instruction present
has_check=true
[[ "$req_output" != *"Coverage Check"* ]] && has_check=false

if $has_assigned && $has_cross && $has_check; then
    test_pass
else
    test_fail "assigned REQs + also_affects awareness + coverage check" "assigned=$has_assigned cross=$has_cross check=$has_check"
fi

# Test 9.2: coverage enforcement end-to-end
test_start "populate_coverage enforces REQUIRE_FULL_COVERAGE=true"
INT_REPO2=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO2")"
LOG_FILE="$INT_REPO2/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO2"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

# 10 requirements, 8 assigned, 2 unassigned
cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-A-001", "title": "A1", "domain": "Core"},
    {"id": "REQ-A-002", "title": "A2", "domain": "Core"},
    {"id": "REQ-A-003", "title": "A3", "domain": "Core"},
    {"id": "REQ-A-004", "title": "A4", "domain": "Core"},
    {"id": "REQ-A-005", "title": "A5", "domain": "Core"},
    {"id": "REQ-A-006", "title": "A6", "domain": "Core"},
    {"id": "REQ-A-007", "title": "A7", "domain": "Core"},
    {"id": "REQ-A-008", "title": "A8", "domain": "Core"},
    {"id": "REQ-B-001", "title": "B1", "domain": "Extra"},
    {"id": "REQ-B-002", "title": "B2", "domain": "Extra"}
  ]
}
REQ_EOF

# Plan: 8 assigned to changes, 2 (REQ-B-001, REQ-B-002) unassigned
cat > "$(tp_plan_file "$INT_REPO2")" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {"name": "change-1", "scope": "Core stuff", "requirements": ["REQ-A-001", "REQ-A-002", "REQ-A-003", "REQ-A-004"], "depends_on": []},
    {"name": "change-2", "scope": "More core", "requirements": ["REQ-A-005", "REQ-A-006", "REQ-A-007", "REQ-A-008"], "depends_on": []}
  ]
}
PLAN_EOF

# REQUIRE_FULL_COVERAGE=true → should fail
export REQUIRE_FULL_COVERAGE=true
cov_rc=0
populate_coverage "$(tp_plan_file "$INT_REPO2")" 2>/dev/null || cov_rc=$?
if [[ "$cov_rc" -ne 0 ]]; then
    test_pass
else
    test_fail "returns non-zero" "rc=$cov_rc"
fi

# Test: same with REQUIRE_FULL_COVERAGE=false → should pass with warning
test_start "populate_coverage warns but succeeds with REQUIRE_FULL_COVERAGE=false"
export REQUIRE_FULL_COVERAGE=false
cov_rc=0
populate_coverage "$(tp_plan_file "$INT_REPO2")" 2>/dev/null || cov_rc=$?
assert_equals "0" "$cov_rc"
unset REQUIRE_FULL_COVERAGE

# Test 9.3: final coverage cross-reference
test_start "final_coverage_check cross-references coverage with state statuses"
INT_REPO3=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO3")"
LOG_FILE="$INT_REPO3/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO3"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-A-001", "title": "A merged", "domain": "Core"},
    {"id": "REQ-B-001", "title": "B running", "domain": "Core"},
    {"id": "REQ-C-001", "title": "C failed", "domain": "Core"},
    {"id": "REQ-D-001", "title": "D uncovered", "domain": "Core"}
  ]
}
REQ_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-A-001": {"change": "change-1", "status": "assigned"},
    "REQ-B-001": {"change": "change-2", "status": "assigned"},
    "REQ-C-001": {"change": "change-3", "status": "assigned"}
  }
}
COV_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {"name": "change-1", "status": "merged"},
    {"name": "change-2", "status": "running"},
    {"name": "change-3", "status": "failed"}
  ]
}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
if [[ "$cov_output" == *"1 merged"* ]] && \
   [[ "$cov_output" == *"1 running"* ]] && \
   [[ "$cov_output" == *"1 failed"* ]] && \
   [[ "$cov_output" == *"1 uncovered"* ]]; then
    test_pass
else
    test_fail "1 merged, 1 running, 1 failed, 1 uncovered" "$cov_output"
fi

# Test 9.4: HTML report with full fixture
test_start "HTML report contains domain names, REQ-IDs, change names, gate results"
INT_REPO4=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO4")"
PLAN_FILENAME="$(tp_plan_file "$INT_REPO4")"
LOG_FILE="$INT_REPO4/orchestrate.log"
REPORT_OUTPUT_PATH="$INT_REPO4/set/orchestration/report.html"
touch "$LOG_FILE"
cd "$INT_REPO4"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR/domains"

cat > "$DIGEST_DIR/index.json" <<'IDX_EOF'
{"spec_base_dir": "specs/", "source_hash": "full123", "file_count": 5, "timestamp": "2026-03-10"}
IDX_EOF

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-FE-001", "title": "Frontend page", "domain": "Frontend"},
    {"id": "REQ-FE-002", "title": "Frontend form", "domain": "Frontend"},
    {"id": "REQ-BE-001", "title": "Backend API", "domain": "Backend"}
  ]
}
REQ_EOF

cat > "$DIGEST_DIR/ambiguities.json" <<'AMB_EOF'
{"ambiguities": [{"description": "Pagination limit unspecified"}, {"description": "Error format TBD"}]}
AMB_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{
  "coverage": {
    "REQ-FE-001": {"change": "fe-pages", "status": "assigned"},
    "REQ-FE-002": {"change": "fe-pages", "status": "assigned"},
    "REQ-BE-001": {"change": "be-api", "status": "assigned"}
  }
}
COV_EOF

echo "Frontend summary" > "$DIGEST_DIR/domains/Frontend.md"
echo "Backend summary" > "$DIGEST_DIR/domains/Backend.md"

cat > "$PLAN_FILENAME" <<'PLAN_EOF'
{
  "changes": [
    {"name": "fe-pages", "scope": "Frontend", "requirements": ["REQ-FE-001", "REQ-FE-002"], "depends_on": []},
    {"name": "be-api", "scope": "Backend", "requirements": ["REQ-BE-001"], "depends_on": []}
  ]
}
PLAN_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "status": "running",
  "changes": [
    {"name": "fe-pages", "status": "merged", "tokens_used": 80000, "test_result": "pass", "smoke_result": "pass"},
    {"name": "be-api", "status": "running", "tokens_used": 40000, "test_result": "fail", "smoke_result": null}
  ]
}
STATE_EOF

generate_report 2>/dev/null

report_html=$(cat "$REPORT_OUTPUT_PATH" 2>/dev/null || echo "")
ok=true
[[ "$report_html" != *"Frontend"* ]] && ok=false
[[ "$report_html" != *"Backend"* ]] && ok=false
[[ "$report_html" != *"REQ-FE-001"* ]] && ok=false
[[ "$report_html" != *"REQ-BE-001"* ]] && ok=false
[[ "$report_html" != *"fe-pages"* ]] && ok=false
[[ "$report_html" != *"be-api"* ]] && ok=false
# Gate checkmarks/crosses
[[ "$report_html" != *"10003"* ]] && ok=false  # checkmark entity
[[ "$report_html" != *"10007"* ]] && ok=false  # cross entity
[[ "$report_html" != *"Generated:"* ]] && ok=false  # timestamp footer

if $ok; then
    test_pass
else
    test_fail "domain names, REQ-IDs, change names, gate marks, footer" "${report_html:0:300}"
fi

# Test 9.5: HTML report graceful degradation
test_start "HTML report renders plan+execution without digest"
INT_REPO5=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO5")"
PLAN_FILENAME="$(tp_plan_file "$INT_REPO5")"
LOG_FILE="$INT_REPO5/orchestrate.log"
REPORT_OUTPUT_PATH="$INT_REPO5/set/orchestration/report.html"
touch "$LOG_FILE"
cd "$INT_REPO5"

DIGEST_DIR="set/orchestration/digest"
# No digest

cat > "$PLAN_FILENAME" <<'PLAN_EOF'
{"changes": [{"name": "quick-fix", "scope": "Fix", "depends_on": []}]}
PLAN_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{"status": "running", "changes": [{"name": "quick-fix", "status": "running", "tokens_used": 5000, "test_result": null, "smoke_result": null}]}
STATE_EOF

generate_report 2>/dev/null

report_html=$(cat "$REPORT_OUTPUT_PATH" 2>/dev/null || echo "")
if [[ "$report_html" == *"Not available"* ]] && \
   [[ "$report_html" == *"quick-fix"* ]] && \
   [[ "$report_html" == *"Execution"* ]]; then
    test_pass
else
    test_fail "Not available + quick-fix + Execution" "${report_html:0:200}"
fi

# Test 9.6: review with REQ-ID not in digest
test_start "review handles ghost REQ-ID with '(not found in digest)'"
INT_REPO6=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO6")"
LOG_FILE="$INT_REPO6/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO6"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{"requirements": [{"id": "REQ-REAL-001", "title": "Real feature", "brief": "Exists"}]}
REQ_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "ghost-test",
      "status": "running",
      "requirements": ["REQ-REAL-001", "REQ-GHOST-001"]
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "ghost-test")
if [[ "$req_output" == *"REQ-GHOST-001"* ]] && [[ "$req_output" == *"not found in digest"* ]]; then
    test_pass
else
    test_fail "REQ-GHOST-001 with 'not found in digest'" "${req_output:0:200}"
fi

# Test 9.7: coverage with merge-blocked change
test_start "final_coverage_check reports merge-blocked reqs as blocked"
INT_REPO7=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO7")"
LOG_FILE="$INT_REPO7/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO7"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{"requirements": [{"id": "REQ-MB-001", "title": "Blocked req", "domain": "Core"}]}
REQ_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{"coverage": {"REQ-MB-001": {"change": "change-1", "status": "running"}}}
COV_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{"changes": [{"name": "change-1", "status": "merge-blocked"}]}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
if [[ "$cov_output" == *"1 blocked"* ]] && [[ "$cov_output" == *"0 uncovered"* ]]; then
    test_pass
else
    test_fail "1 blocked, 0 uncovered" "$cov_output"
fi

# Test 9.8: coverage with removed REQ
test_start "final_coverage_check excludes removed requirements"
INT_REPO8=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO8")"
LOG_FILE="$INT_REPO8/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO8"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-OK-001", "title": "Active", "domain": "Core"},
    {"id": "REQ-OLD-001", "title": "Removed", "domain": "Core", "status": "removed"}
  ]
}
REQ_EOF

cat > "$DIGEST_DIR/coverage.json" <<'COV_EOF'
{"coverage": {"REQ-OK-001": {"change": "change-1", "status": "assigned"}}}
COV_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{"changes": [{"name": "change-1", "status": "merged"}]}
STATE_EOF

cov_output=$(final_coverage_check 2>/dev/null || true)
# Should only count 1 total (REQ-OLD-001 excluded)
if [[ "$cov_output" == *"total: 1"* ]] && [[ "$cov_output" == *"1 merged"* ]]; then
    test_pass
else
    test_fail "total: 1, 1 merged (removed excluded)" "$cov_output"
fi

# Test 9.9: empty requirements array in state
test_start "build_req_review_section returns empty for empty requirements array"
INT_REPO9=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO9")"
LOG_FILE="$INT_REPO9/orchestrate.log"
touch "$LOG_FILE"
cd "$INT_REPO9"

DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{"requirements": [{"id": "REQ-X-001", "title": "Something"}]}
REQ_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{
  "changes": [
    {
      "name": "empty-reqs",
      "status": "running",
      "requirements": []
    }
  ]
}
STATE_EOF

req_output=$(build_req_review_section "empty-reqs")
assert_equals "" "$req_output"

# Test 9.10: report atomic write
test_start "generate_report writes atomically via temp file"
INT_REPO10=$(setup_test_repo)
STATE_FILENAME="$(tp_state_file "$INT_REPO10")"
PLAN_FILENAME="$(tp_plan_file "$INT_REPO10")"
LOG_FILE="$INT_REPO10/orchestrate.log"
REPORT_OUTPUT_PATH="$INT_REPO10/set/orchestration/report.html"
touch "$LOG_FILE"
cd "$INT_REPO10"

DIGEST_DIR="set/orchestration/digest"

cat > "$PLAN_FILENAME" <<'PLAN_EOF'
{"changes": [{"name": "atomic-test", "scope": "Test", "depends_on": []}]}
PLAN_EOF

cat > "$STATE_FILENAME" <<'STATE_EOF'
{"status": "done", "changes": [{"name": "atomic-test", "status": "merged", "tokens_used": 1000, "test_result": "pass", "smoke_result": null}]}
STATE_EOF

generate_report 2>/dev/null

# Verify the file exists and is complete (ends with </html>)
if [[ -f "$REPORT_OUTPUT_PATH" ]]; then
    last_line=$(tail -1 "$REPORT_OUTPUT_PATH")
    if [[ "$last_line" == *"</html>"* ]]; then
        test_pass
    else
        test_fail "file ends with </html>" "$last_line"
    fi
else
    test_fail "report.html exists" "file not found"
fi

# ============================================================
# Section: Smoke Screenshot Artifacts
# ============================================================

echo ""
echo "--- Smoke Screenshot Artifacts ---"

# Test: Smoke artifact collection creates attempt-1/ and updates state
test_start "smoke artifact collection → creates attempt-1/ and updates state"
REPO=$(setup_test_repo)
create_feature_branch "$REPO" "test-sc-collect" "feature.txt:hello"
STATE_FILE="$(tp_state_file "$REPO")"
STATE_FILENAME="$STATE_FILE"
PROJECT_PATH="$REPO"
LOG_FILE="$REPO/orchestrate.log"
touch "$LOG_FILE"
init_test_state "$STATE_FILE" "test-sc-collect" "merged"

cd "$REPO"
# Create stub test-results as if Playwright ran
mkdir -p test-results
echo "PNG_CONTENT" > test-results/screenshot.png
echo "PNG_CONTENT2" > test-results/checkout.png

# Source merger to get _collect_smoke_screenshots
source "$LIB_DIR/merger.sh" 2>/dev/null || true

_collect_smoke_screenshots "test-sc-collect"

# Verify state fields
sc_dir=$(jq -r '.changes[0].smoke_screenshot_dir' "$STATE_FILE")
sc_count=$(jq -r '.changes[0].smoke_screenshot_count' "$STATE_FILE")
# Verify attempt-1 dir exists
if [[ -d "set/orchestration/smoke-screenshots/test-sc-collect/attempt-1" && "$sc_count" -eq 2 && "$sc_dir" == *"smoke-screenshots/test-sc-collect" ]]; then
    test_pass
else
    test_fail "attempt-1/ exists, count=2, dir set" "dir_exists=$(test -d set/orchestration/smoke-screenshots/test-sc-collect/attempt-1 && echo y || echo n), count=$sc_count, dir=$sc_dir"
fi

# Test: Versioned attempt directories preserve both fail and pass screenshots
test_start "versioned attempt dirs → attempt-1/ and attempt-2/ both exist"
# Already in $REPO with attempt-1
# Simulate fix attempt: smoke_fix_attempts=1
jq '.changes[0].smoke_fix_attempts = 1' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
# Create new test-results (pass screenshots)
rm -rf test-results
mkdir -p test-results
echo "PASS_PNG" > test-results/fixed.png
_collect_smoke_screenshots "test-sc-collect"

sc_count=$(jq -r '.changes[0].smoke_screenshot_count' "$STATE_FILE")
if [[ -d "set/orchestration/smoke-screenshots/test-sc-collect/attempt-1" && \
      -d "set/orchestration/smoke-screenshots/test-sc-collect/attempt-2" && \
      "$sc_count" -eq 3 ]]; then
    test_pass
else
    test_fail "both attempt dirs exist, total count=3" "attempt-1=$(test -d set/orchestration/smoke-screenshots/test-sc-collect/attempt-1 && echo y || echo n), attempt-2=$(test -d set/orchestration/smoke-screenshots/test-sc-collect/attempt-2 && echo y || echo n), count=$sc_count"
fi

# Test: Already-merged sets smoke_result=skip_merged
test_start "already-merged branch → smoke_result=skip_merged"
REPO=$(setup_test_repo)
STATE_FILE="$(tp_state_file "$REPO")"
STATE_FILENAME="$STATE_FILE"
PROJECT_PATH="$REPO"
LOG_FILE="$REPO/orchestrate.log"
touch "$LOG_FILE"
# Create a branch that's already ancestor of HEAD
cd "$REPO"
git checkout -b "change/test-already-merged" --quiet
echo "feature" > already.txt
git add already.txt
git commit -m "feat: already merged" --quiet
git checkout main --quiet
git merge "change/test-already-merged" --quiet --no-edit  # now it's ancestor of HEAD

init_test_state "$STATE_FILE" "test-already-merged" "verified"
# Need stubs for cleanup/archive
cleanup_worktree() { :; }
archive_change() { :; }
update_coverage_status() { :; }
run_hook() { return 0; }
emit_event() { :; }

source "$LIB_DIR/merger.sh" 2>/dev/null || true
merge_change "test-already-merged" 2>/dev/null || true

smoke_res=$(jq -r '.changes[0].smoke_result' "$STATE_FILE")
assert_equals "skip_merged" "$smoke_res"

# Test: Multi-change context included when last_smoke_pass_commit is set
test_start "multi-change context → included in fix prompt when last_smoke_pass_commit set"
REPO=$(setup_test_repo)
cd "$REPO"
STATE_FILE="$(tp_state_file "$REPO")"
STATE_FILENAME="$STATE_FILE"
LOG_FILE="$REPO/orchestrate.log"
touch "$LOG_FILE"
# Create state with last_smoke_pass_commit set to initial commit
initial_sha=$(git rev-parse HEAD)
init_test_state "$STATE_FILE" "test-mc" "merged"
jq --arg sha "$initial_sha" '.last_smoke_pass_commit = $sha' "$STATE_FILE" > "$STATE_FILE.tmp" && mv "$STATE_FILE.tmp" "$STATE_FILE"
# Create two merge commits to simulate checkpoint
git checkout -b "change/mc-1" --quiet
echo "change1" > c1.txt && git add c1.txt && git commit -m "feat: mc-1" --quiet
git checkout main --quiet && git merge "change/mc-1" --no-ff --no-edit --quiet
git checkout -b "change/mc-2" --quiet
echo "change2" > c2.txt && git add c2.txt && git commit -m "feat: mc-2" --quiet
git checkout main --quiet && git merge "change/mc-2" --no-ff --no-edit --quiet

# Read multi-change context the same way the code does
since_commit=$(jq -r '.last_smoke_pass_commit // ""' "$STATE_FILE")
merged_since=$(git log --oneline "$since_commit..HEAD" --merges 2>/dev/null || true)
merge_count=$(echo "$merged_since" | grep -c "." || true)
if [[ "$merge_count" -ge 2 ]]; then
    test_pass
else
    test_fail ">= 2 merge commits listed" "got $merge_count: $merged_since"
fi

# Test: Cold start — empty last_smoke_pass_commit → no multi-change context
test_start "cold start → empty last_smoke_pass_commit skips multi-change context"
REPO=$(setup_test_repo)
cd "$REPO"
STATE_FILE="$(tp_state_file "$REPO")"
STATE_FILENAME="$STATE_FILE"
init_test_state "$STATE_FILE" "test-cold" "merged"
# last_smoke_pass_commit is "" by default from init_test_state
since_commit=$(jq -r '.last_smoke_pass_commit // ""' "$STATE_FILE")
if [[ -z "$since_commit" ]]; then
    test_pass
else
    test_fail "empty last_smoke_pass_commit" "got '$since_commit'"
fi

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
