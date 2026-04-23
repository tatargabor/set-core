#!/usr/bin/env bash
# Tests for init_loop_state's session_id preservation guards (lib/loop/state.sh).
# Covers Findings 1 (poisoned-stall bash guard) and the new age check.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$REPO_ROOT/lib/loop/state.sh"

PASS=0
FAIL=0

assert_eq() {
    local actual="$1"; local expected="$2"; local label="$3"
    if [[ "$actual" == "$expected" ]]; then
        echo "PASS: $label"; PASS=$((PASS+1))
    else
        echo "FAIL: $label — expected '$expected', got '$actual'"; FAIL=$((FAIL+1))
    fi
}

# Tempdir for each test
mk_wt() {
    local d=$(mktemp -d)
    mkdir -p "$d/.set"
    echo "$d"
}

# Prior state with a session_id + matching change name + fresh started_at
seed_prior() {
    local wt="$1"; local change="$2"; local sid="$3"; local started="${4:-}"
    if [[ -z "$started" ]]; then started=$(date -Iseconds); fi
    cat > "$wt/.set/loop-state.json" <<EOF
{
  "change": "$change",
  "session_id": "$sid",
  "resume_failures": 0,
  "started_at": "$started"
}
EOF
}

# --- Test 1: no prior state → fresh session preserved as null
wt=$(mk_wt)
init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "null" "T1: no prior state → session_id null"
rm -rf "$wt"

# --- Test 2: matching change + fresh session → preserved
wt=$(mk_wt)
seed_prior "$wt" "foo" "abc-1234"
init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "abc-1234" "T2: matching change + fresh session preserved"
rm -rf "$wt"

# --- Test 3: mismatching change name → session_id dropped (legacy guard still works)
wt=$(mk_wt)
seed_prior "$wt" "bar" "abc-1234"  # prior was for `bar`
init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "null" "T3: change-name mismatch → session_id null"
rm -rf "$wt"

# --- Test 4: SET_LOOP_FRESH_SESSION=1 env → session_id dropped (poisoned-stall)
wt=$(mk_wt)
seed_prior "$wt" "foo" "abc-1234"
SET_LOOP_FRESH_SESSION=1 init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "null" "T4: SET_LOOP_FRESH_SESSION=1 → session_id null"
rm -rf "$wt"

# --- Test 5: stale session (> 60 min) → session_id dropped
wt=$(mk_wt)
# 2 hours ago
stale_ts=$(date -d "-2 hours" -Iseconds)
seed_prior "$wt" "foo" "abc-stale" "$stale_ts"
init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "null" "T5: session > 60 min → session_id null"
rm -rf "$wt"

# --- Test 6: session 30 min old → preserved
wt=$(mk_wt)
recent_ts=$(date -d "-30 min" -Iseconds)
seed_prior "$wt" "foo" "abc-recent" "$recent_ts"
init_loop_state "$wt" "wt-foo" "task" 5 "test" 80 2 90 "foo" "foo" >/dev/null
sid=$(jq -r '.session_id // "null"' "$wt/.set/loop-state.json")
assert_eq "$sid" "abc-recent" "T6: session 30 min old → preserved"
rm -rf "$wt"

echo ""
echo "Results: $PASS passed, $FAIL failed"
exit $FAIL
