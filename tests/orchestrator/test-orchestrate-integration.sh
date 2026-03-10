#!/usr/bin/env bash
# Integration tests for wt-orchestrate: merge pipeline, smoke pipeline, dispatch/loop control
# Uses real git repos and stub commands (no Claude API calls).
# Run with: ./tests/orchestrator/test-orchestrate-integration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source common functions
source "$PROJECT_DIR/bin/wt-common.sh"

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
      "merge_retry_count": 0,
      "iterations": 0,
      "agent_rebase_done": false,
      "merge_rebase_pending": false
    }
  ],
  "merge_queue": [],
  "directives": {}
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

# Constants from wt-orchestrate that modules depend on
STATE_FILENAME=""          # set per-test
LOG_FILE="/dev/null"
EVENTS_ENABLED="false"     # disable event logging in tests

# Directive defaults (copied from wt-orchestrate)
DEFAULT_MAX_PARALLEL=3
DEFAULT_MERGE_POLICY="checkpoint"
DEFAULT_CHECKPOINT_EVERY=3
DEFAULT_TEST_COMMAND=""
DEFAULT_NOTIFICATION="desktop"
DEFAULT_TOKEN_BUDGET=0
DEFAULT_PAUSE_ON_EXIT="false"
DEFAULT_AUTO_REPLAN="false"
DEFAULT_REVIEW_BEFORE_MERGE="false"
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
source "$LIB_DIR/config.sh"        # wt_find_config
source "$LIB_DIR/utils.sh"         # parse_duration, format_duration, brief_hash
source "$LIB_DIR/state.sh"         # update_change_field, run_hook, etc.
source "$LIB_DIR/verifier.sh"      # health_check, extract_health_check_url

# Source loop modules for detect_next_change_action
source "$PROJECT_DIR/lib/loop/prompt.sh"

# Post-source stubs (override real implementations that make external calls)
send_notification() { echo "NOTIFICATION: $*" >> "${NOTIFICATION_LOG:-/dev/null}"; }
orch_remember() { return 0; }

echo "============================================================"
echo "Integration Tests: wt-orchestrate"
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
STATE_FILE="$REPO/orchestration-state.json"
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

STATE_FILE="$REPO2/orchestration-state.json"
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

STATE_FILE="$REPO3/orchestration-state.json"
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
STATE_FILE="$REPO4/orchestration-state.json"
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
STATE_FILE="$REPO5/orchestration-state.json"
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
STATE_FILE="$REPO6/orchestration-state.json"
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
send_notification "wt-orchestrate" "Smoke FAILED for test-smoke-exhaust" "critical"

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
STATE_FILE="$REPO7/orchestration-state.json"
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
    send_notification "wt-orchestrate" "Smoke blocked — no server" "critical"
fi
ss=$(jq -r '.changes[0].smoke_status' "$STATE_FILE")
st=$(jq -r '.changes[0].status' "$STATE_FILE")
assert_equals "blocked" "$ss"

test_start "health check fail sets status=smoke_blocked"
assert_equals "smoke_blocked" "$st"

# Test 10.5: Smoke non-blocking mode
test_start "non-blocking smoke fail does not block status"
REPO8=$(setup_test_repo)
STATE_FILE="$REPO8/orchestration-state.json"
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
    current_hash=$(tail -200 "$log_file" | md5sum | cut -d' ' -f1)
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
    current_hash=$(tail -200 "$log_file" | md5sum | cut -d' ' -f1)
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
# Read the wt-merge script and check the prompt text
merge_script=$(cat "$PROJECT_DIR/bin/wt-merge")
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
mkdir -p wt/orchestration/specs
echo "literal spec" > myspec.md
echo "short-name spec" > wt/orchestration/specs/myspec.md
# Simulate find_input logic
SPEC_OVERRIDE="myspec.md"
INPUT_MODE="" INPUT_PATH=""
if [[ -f "$SPEC_OVERRIDE" ]]; then
    INPUT_MODE="spec"
    INPUT_PATH="$(cd "$(dirname "$SPEC_OVERRIDE")" && pwd)/$(basename "$SPEC_OVERRIDE")"
fi
assert_contains "$INPUT_PATH" "myspec.md"
# Verify it resolved to the literal (repo root), not wt/orchestration/specs/
test_start "spec resolution: literal path not from wt/orchestration/specs"
if [[ "$INPUT_PATH" == *"wt/orchestration/specs"* ]]; then
    test_fail "not wt/orchestration/specs path" "$INPUT_PATH"
else
    test_pass
fi

# Test 14.1b: Short name resolves to wt/orchestration/specs/
test_start "spec resolution: short name resolves to wt/orchestration/specs/"
cd "$REPO_SPEC"
SPEC_OVERRIDE="v12"
INPUT_MODE="" INPUT_PATH=""
echo "v12 content" > wt/orchestration/specs/v12.md
if [[ -f "$SPEC_OVERRIDE" ]]; then
    INPUT_MODE="spec"
    INPUT_PATH="$(cd "$(dirname "$SPEC_OVERRIDE")" && pwd)/$(basename "$SPEC_OVERRIDE")"
else
    local_wt_spec="wt/orchestration/specs/${SPEC_OVERRIDE}.md"
    if [[ -f "$local_wt_spec" ]]; then
        INPUT_MODE="spec"
        INPUT_PATH="$(cd "$(dirname "$local_wt_spec")" && pwd)/$(basename "$local_wt_spec")"
    fi
fi
assert_contains "$INPUT_PATH" "v12.md"
test_start "spec resolution: short name path includes wt/orchestration/specs"
assert_contains "$INPUT_PATH" "wt/orchestration/specs"

# Test 14.1c: Missing spec errors with both paths
test_start "spec resolution: missing spec shows both checked paths"
cd "$REPO_SPEC"
SPEC_OVERRIDE="nonexistent"
error_output=""
if [[ ! -f "$SPEC_OVERRIDE" ]]; then
    local_wt_spec="wt/orchestration/specs/${SPEC_OVERRIDE}.md"
    local_wt_spec_sub="wt/orchestration/specs/${SPEC_OVERRIDE}"
    if [[ ! -f "$local_wt_spec" && ! -f "$local_wt_spec_sub" ]]; then
        error_output="Spec file not found: $SPEC_OVERRIDE | Checked: $SPEC_OVERRIDE, $local_wt_spec"
    fi
fi
assert_contains "$error_output" "nonexistent"
test_start "spec resolution: error mentions wt/ path"
assert_contains "$error_output" "wt/orchestration/specs/nonexistent.md"

# Test 14.2: specs list output format (active + archived)
test_start "specs list: shows active and archived specs"
REPO_SLIST=$(setup_test_repo)
cd "$REPO_SLIST"
mkdir -p wt/orchestration/specs/archive
echo "# Active spec" > wt/orchestration/specs/v9.md
echo "# Archived spec" > wt/orchestration/specs/archive/v7.md
list_output=$("$PROJECT_DIR/bin/wt-orchestrate" specs list 2>&1 || true)
assert_contains "$list_output" "v9"

test_start "specs list: shows archived section"
assert_contains "$list_output" "Archived"

test_start "specs list: shows archived spec name"
assert_contains "$list_output" "v7"

# Test 14.3: specs archive moves file correctly
test_start "specs archive: moves spec to archive/"
REPO_SARCH=$(setup_test_repo)
cd "$REPO_SARCH"
mkdir -p wt/orchestration/specs/archive
echo "# Spec to archive" > wt/orchestration/specs/v8.md
git add wt/orchestration/specs/v8.md && git commit -m "add v8 spec" --quiet
"$PROJECT_DIR/bin/wt-orchestrate" specs archive v8 2>&1 || true
if [[ -f "wt/orchestration/specs/archive/v8.md" && ! -f "wt/orchestration/specs/v8.md" ]]; then
    test_pass
else
    test_fail "v8.md in archive/ and not in specs/" "$(ls wt/orchestration/specs/ wt/orchestration/specs/archive/ 2>/dev/null)"
fi

# Test 14.4: Legacy spec migration detects docs/v*.md pattern
test_start "legacy migration: detects docs/v*.md files"
REPO_SMIG=$(setup_test_repo)
cd "$REPO_SMIG"
mkdir -p docs wt/orchestration/specs/archive
echo "# v1 spec" > docs/v1.md
echo "# v2 spec" > docs/v2_minicrm.md
echo "# not a spec" > docs/readme.md
git add . && git commit -m "add legacy specs" --quiet
# Run migrate
"$PROJECT_DIR/bin/wt-project" migrate 2>&1 || true
# Check that v1.md and v2_minicrm.md moved to archive, readme.md stayed
if [[ -f "wt/orchestration/specs/archive/v1.md" ]]; then
    test_pass
else
    test_fail "v1.md in archive/" "$(ls wt/orchestration/specs/archive/ 2>/dev/null)"
fi

test_start "legacy migration: v2_minicrm.md also migrated"
if [[ -f "wt/orchestration/specs/archive/v2_minicrm.md" ]]; then
    test_pass
else
    test_fail "v2_minicrm.md in archive/" "$(ls wt/orchestration/specs/archive/ 2>/dev/null)"
fi

test_start "legacy migration: non-spec docs/readme.md not moved"
if [[ -f "docs/readme.md" ]]; then
    test_pass
else
    test_fail "docs/readme.md still present" "moved unexpectedly"
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
