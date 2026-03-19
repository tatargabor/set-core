#!/usr/bin/env bash
# Integration tests for set-orch-core CLI bridge
# Tests: init_state round-trip, check-pid on live process, template proposal output

set -euo pipefail

PASS=0
FAIL=0
TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

_pass() { PASS=$((PASS + 1)); echo "  PASS: $1"; }
_fail() { FAIL=$((FAIL + 1)); echo "  FAIL: $1 — $2"; }

echo "=== set-orch-core integration tests ==="

# ─── 8.1: init_state → load_state round-trip ──────────────────────

echo ""
echo "--- 8.1: init_state round-trip ---"

# Create a plan fixture
cat > "$TMPDIR_TEST/plan.json" <<'EOF'
{
  "plan_version": 3,
  "brief_hash": "abc123",
  "plan_phase": "initial",
  "plan_method": "api",
  "changes": [
    {
      "name": "add-auth",
      "scope": "Add user authentication with JWT",
      "complexity": "M",
      "change_type": "foundational",
      "depends_on": [],
      "roadmap_item": "User auth system",
      "model": "opus",
      "skip_review": false,
      "skip_test": false,
      "has_manual_tasks": false,
      "requirements": ["REQ-AUTH-001"]
    },
    {
      "name": "add-products",
      "scope": "Product listing page",
      "complexity": "S",
      "change_type": "feature",
      "depends_on": ["add-auth"],
      "roadmap_item": "Product catalog",
      "model": null,
      "skip_review": false,
      "skip_test": false,
      "has_manual_tasks": true
    }
  ]
}
EOF

# Run init_state
if set-orch-core state init --plan-file "$TMPDIR_TEST/plan.json" --output "$TMPDIR_TEST/state.json" 2>/dev/null; then
    _pass "init_state completed without error"
else
    _fail "init_state" "exit code $?"
fi

# Validate output exists and is valid JSON
if [[ -f "$TMPDIR_TEST/state.json" ]] && jq empty "$TMPDIR_TEST/state.json" 2>/dev/null; then
    _pass "output is valid JSON"
else
    _fail "output validation" "file missing or invalid JSON"
fi

# Check plan_version preserved
pv=$(jq '.plan_version' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$pv" == "3" ]]; then
    _pass "plan_version preserved (3)"
else
    _fail "plan_version" "expected 3, got $pv"
fi

# Check change count
cc=$(jq '.changes | length' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$cc" == "2" ]]; then
    _pass "2 changes created"
else
    _fail "change count" "expected 2, got $cc"
fi

# Check default status is pending
s1=$(jq -r '.changes[0].status' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$s1" == "pending" ]]; then
    _pass "default status is pending"
else
    _fail "default status" "expected pending, got $s1"
fi

# Check depends_on preserved
deps=$(jq -r '.changes[1].depends_on[0]' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$deps" == "add-auth" ]]; then
    _pass "depends_on preserved"
else
    _fail "depends_on" "expected add-auth, got $deps"
fi

# Check requirements preserved
req=$(jq -r '.changes[0].requirements[0]' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$req" == "REQ-AUTH-001" ]]; then
    _pass "requirements preserved"
else
    _fail "requirements" "expected REQ-AUTH-001, got $req"
fi

# Check has_manual_tasks preserved
hmt=$(jq '.changes[1].has_manual_tasks' "$TMPDIR_TEST/state.json" 2>/dev/null)
if [[ "$hmt" == "true" ]]; then
    _pass "has_manual_tasks preserved"
else
    _fail "has_manual_tasks" "expected true, got $hmt"
fi

# Round-trip: query changes via CLI
query_out=$(set-orch-core state query --file "$TMPDIR_TEST/state.json" --status pending 2>/dev/null)
qc=$(echo "$query_out" | jq 'length' 2>/dev/null)
if [[ "$qc" == "2" ]]; then
    _pass "query pending returns 2"
else
    _fail "query pending" "expected 2, got $qc"
fi

# ─── 8.2: check-pid on own PID ───────────────────────────────────

echo ""
echo "--- 8.2: check-pid on live process ---"

# Check own PID with bash pattern (should match)
own_pid=$$
check_out=$(set-orch-core process check-pid --pid "$own_pid" --expect-cmd "bash" 2>/dev/null) || true
alive=$(echo "$check_out" | jq '.alive' 2>/dev/null)
match=$(echo "$check_out" | jq '.match' 2>/dev/null)

if [[ "$alive" == "true" ]]; then
    _pass "own PID is alive"
else
    _fail "own PID alive" "expected true, got $alive"
fi

if [[ "$match" == "true" ]]; then
    _pass "own PID matches 'bash'"
else
    _fail "own PID match" "expected true, got $match"
fi

# Check own PID with wrong pattern (should be alive but not match)
check_out2=$(set-orch-core process check-pid --pid "$own_pid" --expect-cmd "nonexistent-process-xyz" 2>/dev/null) || true
match2=$(echo "$check_out2" | jq '.match' 2>/dev/null)

if [[ "$match2" == "false" ]]; then
    _pass "wrong pattern returns match=false"
else
    _fail "wrong pattern" "expected match=false, got $match2"
fi

# Check dead PID (PID 99999 is almost certainly dead)
check_out3=$(set-orch-core process check-pid --pid 99999 --expect-cmd "anything" 2>/dev/null) || true
alive3=$(echo "$check_out3" | jq '.alive' 2>/dev/null)

if [[ "$alive3" == "false" ]]; then
    _pass "dead PID returns alive=false"
else
    _fail "dead PID" "expected alive=false, got $alive3"
fi

# ─── 8.3: template proposal ──────────────────────────────────────

echo ""
echo "--- 8.3: template proposal output ---"

proposal_out=$(jq -n \
    --arg change_name "add-auth" \
    --arg scope "JWT-based authentication with login/register" \
    --arg roadmap_item "User authentication system" \
    --arg memory_ctx "Previous auth attempts used sessions" \
    --arg spec_ref "docs/spec.md" \
    '{change_name: $change_name, scope: $scope, roadmap_item: $roadmap_item, memory_ctx: $memory_ctx, spec_ref: $spec_ref}' \
| set-orch-core template proposal --input-file - 2>/dev/null)

if [[ -n "$proposal_out" ]]; then
    _pass "proposal generated non-empty output"
else
    _fail "proposal output" "empty output"
fi

if echo "$proposal_out" | grep -q "## Why"; then
    _pass "proposal contains '## Why' section"
else
    _fail "proposal sections" "missing '## Why'"
fi

if echo "$proposal_out" | grep -q "## What Changes"; then
    _pass "proposal contains '## What Changes' section"
else
    _fail "proposal sections" "missing '## What Changes'"
fi

if echo "$proposal_out" | grep -q "add-auth"; then
    _pass "proposal contains change name"
else
    _fail "proposal content" "missing change name"
fi

if echo "$proposal_out" | grep -q "## Context from Memory"; then
    _pass "proposal contains memory section"
else
    _fail "proposal content" "missing memory section"
fi

if echo "$proposal_out" | grep -q "## Source Spec"; then
    _pass "proposal contains spec reference"
else
    _fail "proposal content" "missing spec reference"
fi

# Template review
review_out=$(jq -n \
    --arg scope "Auth changes" \
    --arg diff_output "diff --git a/auth.ts\n+export function login() {}" \
    --arg req_section "" \
    '{scope: $scope, diff_output: $diff_output, req_section: $req_section}' \
| set-orch-core template review --input-file - 2>/dev/null)

if echo "$review_out" | grep -q "senior code reviewer"; then
    _pass "review template contains reviewer instruction"
else
    _fail "review template" "missing reviewer instruction"
fi

# Template fix (scoped variant)
fix_out=$(jq -n \
    --arg change_name "add-auth" \
    --arg scope "Auth module" \
    --arg output_tail "Error: login failed" \
    --arg smoke_cmd "npm test" \
    --arg variant "scoped" \
    '{change_name: $change_name, scope: $scope, output_tail: $output_tail, smoke_cmd: $smoke_cmd, variant: $variant}' \
| set-orch-core template fix --input-file - 2>/dev/null)

if echo "$fix_out" | grep -q "MAY ONLY modify files"; then
    _pass "scoped fix template contains constraints"
else
    _fail "scoped fix template" "missing constraints section"
fi

# ─── Summary ─────────────────────────────────────────────────────

echo ""
echo "=== Results: $PASS passed, $FAIL failed ==="
[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
