#!/usr/bin/env bash
# Test script for sentinel-v2 features: events, watchdog, context pruning,
# verification rules, state reconstruction, hooks, migration.
# Run with: ./tests/orchestrator/test-sentinel-v2.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

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

# ============================================================
# Setup: source set-orchestrate functions
# ============================================================

TEST_DIR="$SCRIPT_DIR"
eval "$(sed '/^main "\$@"/d; /^SCRIPT_DIR=/s|=.*|="'"$PROJECT_DIR/bin"'"|' "$PROJECT_DIR/bin/set-orchestrate")"

# Create temp dir for test artifacts
TMPDIR_TEST=$(mktemp -d)
trap "rm -rf $TMPDIR_TEST" EXIT

# ============================================================
# Test: Event emission and query (15.2)
# ============================================================

STATE_FILENAME="$TMPDIR_TEST/test-state.json"
EVENTS_LOG_FILE="$TMPDIR_TEST/test-events.jsonl"
EVENTS_ENABLED=true
touch "$EVENTS_LOG_FILE"

test_start "emit_event writes valid JSONL"
emit_event "TEST_EVENT" "test-change" '{"key":"value"}'
line=$(tail -1 "$EVENTS_LOG_FILE")
valid=0
echo "$line" | jq empty 2>/dev/null || valid=1
assert_equals "0" "$valid"

test_start "emit_event includes type field"
type=$(echo "$line" | jq -r '.type')
assert_equals "TEST_EVENT" "$type"

test_start "emit_event includes change field"
change=$(echo "$line" | jq -r '.change')
assert_equals "test-change" "$change"

test_start "emit_event includes data field"
key=$(echo "$line" | jq -r '.data.key')
assert_equals "value" "$key"

test_start "emit_event includes timestamp"
ts=$(echo "$line" | jq -r '.ts')
if [[ -n "$ts" && "$ts" != "null" ]]; then
    test_pass
else
    test_fail "non-empty timestamp" "$ts"
fi

test_start "emit_event without change omits change field"
emit_event "GLOBAL_EVENT" "" '{"info":"test"}'
line=$(tail -1 "$EVENTS_LOG_FILE")
has_change=$(echo "$line" | jq 'has("change")')
assert_equals "false" "$has_change"

# Add more events for query testing
emit_event "STATE_CHANGE" "alpha" '{"from":"pending","to":"running"}'
emit_event "STATE_CHANGE" "beta" '{"from":"pending","to":"running"}'
emit_event "STATE_CHANGE" "alpha" '{"from":"running","to":"done"}'
emit_event "TOKENS" "alpha" '{"delta":50000,"total":50000}'

test_start "query_events --type filters correctly"
results=$(query_events --type STATE_CHANGE --json)
count=$(echo "$results" | jq 'length')
assert_equals "3" "$count"

test_start "query_events --change filters correctly"
results=$(query_events --change alpha --json)
count=$(echo "$results" | jq 'length')
assert_equals "3" "$count"

test_start "query_events --last N limits results"
results=$(query_events --last 2 --json)
count=$(echo "$results" | jq 'length')
assert_equals "2" "$count"

# ============================================================
# Test: Event log rotation (15.2)
# ============================================================

test_start "rotate_events_log rotates when over max size"
EVENTS_MAX_SIZE=100  # tiny threshold
# Write enough to exceed 100 bytes
for i in $(seq 1 10); do
    emit_event "FILLER" "" '{"i":'$i'}'
done
rotate_events_log
archives=$(ls -1 "$TMPDIR_TEST"/test-events-*.jsonl 2>/dev/null | wc -l)
if [[ "$archives" -ge 1 ]]; then
    test_pass
else
    test_fail ">=1 archive" "$archives archives"
fi
EVENTS_MAX_SIZE=1048576  # restore default

# ============================================================
# Test: parse_directives — sentinel-v2 directives (15.1)
# ============================================================

V2_BRIEF=$(mktemp)
cat > "$V2_BRIEF" <<'EOF'
## Orchestrator Directives
- watchdog_timeout: 600
- watchdog_loop_threshold: 5
- max_tokens_per_change: 1000000
- context_pruning: false
- plan_approval: true
- model_routing: complexity
- events_max_size: 2097152
EOF

test_start "parse_directives reads watchdog_timeout"
directives=$(parse_directives "$V2_BRIEF")
wt=$(echo "$directives" | jq -r '.watchdog_timeout')
assert_equals "600" "$wt"

test_start "parse_directives reads watchdog_loop_threshold"
wlt=$(echo "$directives" | jq -r '.watchdog_loop_threshold')
assert_equals "5" "$wlt"

test_start "parse_directives reads max_tokens_per_change"
mtpc=$(echo "$directives" | jq -r '.max_tokens_per_change')
assert_equals "1000000" "$mtpc"

test_start "parse_directives reads context_pruning"
cp_val=$(echo "$directives" | jq -r '.context_pruning')
assert_equals "false" "$cp_val"

test_start "parse_directives reads plan_approval"
pa=$(echo "$directives" | jq -r '.plan_approval')
assert_equals "true" "$pa"

test_start "parse_directives reads model_routing"
mr=$(echo "$directives" | jq -r '.model_routing')
assert_equals "complexity" "$mr"

test_start "parse_directives reads events_max_size"
ems=$(echo "$directives" | jq -r '.events_max_size')
assert_equals "2097152" "$ems"

rm -f "$V2_BRIEF"

# ============================================================
# Test: Context pruning (15.4)
# ============================================================

MOCK_WT="$TMPDIR_TEST/mock-worktree"
mkdir -p "$MOCK_WT/.claude/commands/wt"
mkdir -p "$MOCK_WT/.claude/rules"
mkdir -p "$MOCK_WT/.claude/skills/wt"

# Create files that should be pruned
echo "orchestrate" > "$MOCK_WT/.claude/commands/wt/orchestrate.md"
echo "sentinel" > "$MOCK_WT/.claude/commands/wt/sentinel-start.md"
echo "manual" > "$MOCK_WT/.claude/commands/wt/manual-merge.md"

# Create files that should be preserved
echo "loop" > "$MOCK_WT/.claude/commands/wt/loop.md"
echo "rule" > "$MOCK_WT/.claude/rules/test-rule.md"
echo "skill" > "$MOCK_WT/.claude/skills/wt/SKILL.md"
echo "# CLAUDE.md" > "$MOCK_WT/CLAUDE.md"

prune_worktree_context "$MOCK_WT"

test_start "context pruning removes orchestrate*.md"
if [[ ! -f "$MOCK_WT/.claude/commands/wt/orchestrate.md" ]]; then
    test_pass
else
    test_fail "file removed" "file exists"
fi

test_start "context pruning removes sentinel*.md"
if [[ ! -f "$MOCK_WT/.claude/commands/wt/sentinel-start.md" ]]; then
    test_pass
else
    test_fail "file removed" "file exists"
fi

test_start "context pruning removes manual*.md"
if [[ ! -f "$MOCK_WT/.claude/commands/wt/manual-merge.md" ]]; then
    test_pass
else
    test_fail "file removed" "file exists"
fi

test_start "context pruning preserves loop.md"
if [[ -f "$MOCK_WT/.claude/commands/wt/loop.md" ]]; then
    test_pass
else
    test_fail "file preserved" "file missing"
fi

test_start "context pruning preserves .claude/rules/"
if [[ -f "$MOCK_WT/.claude/rules/test-rule.md" ]]; then
    test_pass
else
    test_fail "file preserved" "file missing"
fi

test_start "context pruning preserves .claude/skills/"
if [[ -f "$MOCK_WT/.claude/skills/wt/SKILL.md" ]]; then
    test_pass
else
    test_fail "file preserved" "file missing"
fi

test_start "context pruning preserves CLAUDE.md"
if [[ -f "$MOCK_WT/CLAUDE.md" ]]; then
    test_pass
else
    test_fail "file preserved" "file missing"
fi

# ============================================================
# Test: State reconstruction from events (15.8)
# ============================================================

# Create a state file with stale data
RECON_STATE="$TMPDIR_TEST/recon-state.json"
RECON_EVENTS="$TMPDIR_TEST/recon-events.jsonl"

cat > "$RECON_STATE" <<'EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "status": "running",
  "changes": [
    {"name": "alpha", "status": "running", "ralph_pid": 99999, "tokens_used": 0, "scope": "test alpha"},
    {"name": "beta", "status": "pending", "ralph_pid": null, "tokens_used": 0, "scope": "test beta"}
  ]
}
EOF

# Create events that show alpha finished
cat > "$RECON_EVENTS" <<'EOF'
{"ts":"2026-03-07T10:00:00+01:00","type":"STATE_CHANGE","change":"alpha","data":{"from":"pending","to":"running"}}
{"ts":"2026-03-07T10:05:00+01:00","type":"TOKENS","change":"alpha","data":{"delta":50000,"total":50000}}
{"ts":"2026-03-07T10:10:00+01:00","type":"STATE_CHANGE","change":"alpha","data":{"from":"running","to":"done"}}
{"ts":"2026-03-07T10:15:00+01:00","type":"STATE_CHANGE","change":"beta","data":{"from":"pending","to":"running"}}
{"ts":"2026-03-07T10:20:00+01:00","type":"TOKENS","change":"beta","data":{"delta":30000,"total":30000}}
EOF

# Make events newer than state
touch -d "2026-03-07 10:25:00" "$RECON_EVENTS" 2>/dev/null || touch "$RECON_EVENTS"
sleep 0.1

# Save/restore globals
OLD_STATE="$STATE_FILENAME"
OLD_EVENTS="$EVENTS_LOG_FILE"
STATE_FILENAME="$RECON_STATE"
EVENTS_LOG_FILE="$RECON_EVENTS"

test_start "reconstruct_state_from_events succeeds"
rc=0
reconstruct_state_from_events "$RECON_EVENTS" "$RECON_STATE" 2>/dev/null || rc=$?
assert_equals "0" "$rc"

test_start "reconstruction sets alpha to done"
alpha_status=$(jq -r '.changes[] | select(.name == "alpha") | .status' "$RECON_STATE")
assert_equals "done" "$alpha_status"

test_start "reconstruction sets beta to stalled (was running, PID dead)"
beta_status=$(jq -r '.changes[] | select(.name == "beta") | .status' "$RECON_STATE")
assert_equals "stalled" "$beta_status"

test_start "reconstruction restores alpha tokens"
alpha_tokens=$(jq '.changes[] | select(.name == "alpha") | .tokens_used' "$RECON_STATE")
assert_equals "50000" "$alpha_tokens"

test_start "reconstruction restores beta tokens"
beta_tokens=$(jq '.changes[] | select(.name == "beta") | .tokens_used' "$RECON_STATE")
assert_equals "30000" "$beta_tokens"

test_start "reconstruction sets orchestration status to stopped"
orch_status=$(jq -r '.status' "$RECON_STATE")
assert_equals "stopped" "$orch_status"

# Restore globals
STATE_FILENAME="$OLD_STATE"
EVENTS_LOG_FILE="$OLD_EVENTS"

# ============================================================
# Test: Hooks — run_hook (15.9)
# ============================================================

# Create a passing hook
HOOK_PASS="$TMPDIR_TEST/hook-pass.sh"
cat > "$HOOK_PASS" <<'HOOKEOF'
#!/usr/bin/env bash
echo "hook ran: $1 $2 $3"
exit 0
HOOKEOF
chmod +x "$HOOK_PASS"

# Create a failing hook
HOOK_FAIL="$TMPDIR_TEST/hook-fail.sh"
cat > "$HOOK_FAIL" <<'HOOKEOF'
#!/usr/bin/env bash
echo "blocking reason" >&2
exit 1
HOOKEOF
chmod +x "$HOOK_FAIL"

hook_pre_dispatch="$HOOK_PASS"

test_start "run_hook succeeds with passing hook"
rc=0
run_hook "pre_dispatch" "test-change" "running" "/tmp" 2>/dev/null || rc=$?
assert_equals "0" "$rc"

hook_pre_dispatch="$HOOK_FAIL"

test_start "run_hook blocks with failing hook"
rc=0
run_hook "pre_dispatch" "test-change" "running" "/tmp" 2>/dev/null || rc=$?
if [[ "$rc" -ne 0 ]]; then
    test_pass
else
    test_fail "non-zero (blocked)" "0"
fi

hook_pre_dispatch=""

test_start "run_hook no-ops without configured hook"
rc=0
run_hook "pre_dispatch" "test-change" "running" "/tmp" 2>/dev/null || rc=$?
assert_equals "0" "$rc"

# ============================================================
# Test: Watchdog token budget helpers — REMOVED (15.3)
# Per-change token budget replaced by progress-based trend detection.
# See: openspec/changes/trend-based-watchdog/
# ============================================================

# ============================================================
# Test: Merge-blocked state (15.7)
# ============================================================

MERGE_STATE="$TMPDIR_TEST/merge-state.json"
cat > "$MERGE_STATE" <<'EOF'
{
  "plan_version": 1,
  "status": "running",
  "changes": [
    {"name": "blocked-change", "status": "done", "tokens_used": 0},
    {"name": "other-change", "status": "running", "ralph_pid": null, "tokens_used": 0}
  ]
}
EOF

OLD_STATE="$STATE_FILENAME"
OLD_EVENTS="$EVENTS_LOG_FILE"
STATE_FILENAME="$MERGE_STATE"
EVENTS_LOG_FILE="$TMPDIR_TEST/merge-events.jsonl"
touch "$EVENTS_LOG_FILE"

test_start "merge-blocked state can be set via update_change_field"
update_change_field "blocked-change" "status" '"merge-blocked"'
s=$(get_change_status "blocked-change")
assert_equals "merge-blocked" "$s"

test_start "cmd_approve handles merge-blocked"
# Set up for cmd_approve
update_change_field "blocked-change" "status" '"merge-blocked"'
cmd_approve "blocked-change" 2>/dev/null || true
s=$(get_change_status "blocked-change")
# Should transition to done (ready for merge retry)
assert_equals "done" "$s"

STATE_FILENAME="$OLD_STATE"
EVENTS_LOG_FILE="$OLD_EVENTS"

# ============================================================
# Test: Sentinel — failure classification (15.3)
# ============================================================

# Source sentinel functions by extracting just the functions we need
eval "$(sed -n '/^is_transient_failure/,/^}/p' "$PROJECT_DIR/bin/set-sentinel")"
eval "$(sed -n '/^calculate_backoff/,/^}/p' "$PROJECT_DIR/bin/set-sentinel")"

test_start "is_transient_failure: crash is transient"
if is_transient_failure 1 "running"; then
    test_pass
else
    test_fail "transient" "permanent"
fi

test_start "is_transient_failure: done is permanent"
if ! is_transient_failure 0 "done"; then
    test_pass
else
    test_fail "permanent" "transient"
fi

test_start "is_transient_failure: stopped is permanent"
if ! is_transient_failure 0 "stopped"; then
    test_pass
else
    test_fail "permanent" "transient"
fi

test_start "is_transient_failure: plan_review is permanent"
if ! is_transient_failure 0 "plan_review"; then
    test_pass
else
    test_fail "permanent" "transient"
fi

test_start "calculate_backoff returns value >= base"
backoff=$(calculate_backoff 30)
if [[ "$backoff" -ge 30 ]]; then
    test_pass
else
    test_fail ">=30" "$backoff"
fi

test_start "calculate_backoff returns value <= base * 1.25"
backoff=$(calculate_backoff 100)
if [[ "$backoff" -le 125 ]]; then
    test_pass
else
    test_fail "<=125" "$backoff"
fi

# ============================================================
# Test: set-project version tracking (15.10)
# ============================================================

test_start "set-project _get_set_tools_version returns non-empty"
# Extract just the version function without executing the main script
eval "$(sed -n '/^_get_set_tools_version()/,/^}/p' "$PROJECT_DIR/bin/set-project")"
WT_TOOLS_ROOT="$PROJECT_DIR"
version=$(_get_set_tools_version)
if [[ -n "$version" && "$version" != "unknown" ]]; then
    test_pass
else
    test_fail "non-empty version" "$version"
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
