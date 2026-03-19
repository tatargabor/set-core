#!/usr/bin/env bash
# Test script for auditor.sh: prompt building and result parsing
# Tests functions without Claude calls or git operations.
# Run with: ./tests/orchestrator/test-auditor.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source common functions
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
        test_fail "$expected" "$actual"
    fi
}

assert_contains() {
    local needle="$1"
    local haystack="$2"
    if [[ "$haystack" == *"$needle"* ]]; then
        test_pass
    else
        test_fail "contains '$needle'" "${haystack:0:200}..."
    fi
}

# ─── Setup mock environment ──────────────────────────────────────────

TMPDIR_TEST=$(mktemp -d)
trap 'rm -rf "$TMPDIR_TEST"' EXIT

# Mock globals that auditor.sh depends on
STATE_FILENAME="$TMPDIR_TEST/state.json"
INPUT_MODE="spec"
INPUT_PATH="$TMPDIR_TEST/spec.md"
DIGEST_DIR="$TMPDIR_TEST/digest"
DEFAULT_REVIEW_MODEL="sonnet"
DEFAULT_POST_PHASE_AUDIT="true"
EVENTS_ENABLED="false"  # Disable event emission in tests
EVENTS_LOG_FILE="/dev/null"
LOG_FILE="/dev/null"

# Create mock spec
cat > "$INPUT_PATH" <<'EOF'
# Test App Specification

## Feature: User Authentication
Login, logout, password reset.

## Feature: Dashboard
Display user metrics and activity.

## Feature: Settings
User profile and notification preferences.
EOF

# Create mock state with merged changes
cat > "$STATE_FILENAME" <<'EOF'
{
  "status": "running",
  "replan_cycle": 0,
  "changes": [
    {
      "name": "add-auth",
      "status": "merged",
      "scope": "Implement login, logout, and session management",
      "merge_commit": ""
    },
    {
      "name": "add-dashboard",
      "status": "merged",
      "scope": "Create dashboard page with user metrics",
      "merge_commit": ""
    },
    {
      "name": "add-settings",
      "status": "failed",
      "scope": "Settings page with profile editing"
    }
  ]
}
EOF

# Mock functions that auditor.sh calls
emit_event() { :; }
log_info() { :; }
log_error() { :; }
info() { :; }
warn() { :; }
error() { :; }
success() { :; }
model_id() { echo "$1"; }
safe_jq_update() {
    local file="$1"
    shift
    local tmp
    tmp=$(mktemp)
    jq "$@" "$file" > "$tmp" && mv "$tmp" "$file"
}
update_state_field() { :; }

# Source auditor
source "$PROJECT_DIR/lib/orchestration/auditor.sh"

echo "═══ Auditor Unit Tests ═══"
echo ""

# ─── Test: build_audit_prompt spec mode ──────────────────────────────

test_start "build_audit_prompt in spec mode produces prompt with spec text"
prompt=$(build_audit_prompt 1)
assert_contains "User Authentication" "$prompt"

test_start "build_audit_prompt includes merged change names"
prompt=$(build_audit_prompt 1)
assert_contains "add-auth" "$prompt"

test_start "build_audit_prompt includes change scopes"
prompt=$(build_audit_prompt 1)
assert_contains "Implement login, logout" "$prompt"

test_start "build_audit_prompt includes failed changes"
prompt=$(build_audit_prompt 1)
assert_contains "add-settings" "$prompt"

test_start "build_audit_prompt output contains JSON format instruction"
prompt=$(build_audit_prompt 1)
assert_contains "audit_result" "$prompt"

# ─── Test: build_audit_prompt digest mode ────────────────────────────

test_start "build_audit_prompt in digest mode uses requirements"
mkdir -p "$DIGEST_DIR"
cat > "$DIGEST_DIR/requirements.json" <<'EOF'
{
  "requirements": [
    {"id": "REQ-AUTH-001", "title": "User Login", "brief": "Standard login with email/password"},
    {"id": "REQ-DASH-001", "title": "Dashboard Metrics", "brief": "Show KPIs on main page"}
  ]
}
EOF
cat > "$DIGEST_DIR/coverage.json" <<'EOF'
{
  "coverage": {
    "REQ-AUTH-001": {"status": "merged", "change": "add-auth"},
    "REQ-DASH-001": {"status": "merged", "change": "add-dashboard"}
  }
}
EOF
INPUT_MODE="digest"
prompt=$(build_audit_prompt 1)
assert_contains "REQ-AUTH-001" "$prompt"

test_start "build_audit_prompt digest mode includes coverage"
assert_contains "merged" "$prompt"

# Reset to spec mode
INPUT_MODE="spec"
rm -rf "$DIGEST_DIR"

# ─── Test: parse_audit_result with valid gaps ────────────────────────

test_start "parse_audit_result parses gaps_found JSON"
raw_file=$(mktemp)
cat > "$raw_file" <<'EOF'
{
  "audit_result": "gaps_found",
  "gaps": [
    {
      "id": "GAP-1",
      "description": "Settings page not implemented",
      "spec_reference": "Feature: Settings",
      "severity": "critical",
      "suggested_scope": "Implement settings page"
    }
  ],
  "summary": "1 critical gap found"
}
EOF
result=$(parse_audit_result "$raw_file")
audit_result=$(echo "$result" | jq -r '.audit_result')
assert_equals "gaps_found" "$audit_result"
rm -f "$raw_file"

test_start "parse_audit_result extracts gap count"
raw_file=$(mktemp)
cat > "$raw_file" <<'EOF'
{
  "audit_result": "gaps_found",
  "gaps": [
    {"id": "GAP-1", "description": "Missing feature", "severity": "critical"},
    {"id": "GAP-2", "description": "Incomplete feature", "severity": "minor"}
  ],
  "summary": "2 gaps"
}
EOF
result=$(parse_audit_result "$raw_file")
gap_count=$(echo "$result" | jq '[.gaps[]] | length')
assert_equals "2" "$gap_count"
rm -f "$raw_file"

# ─── Test: parse_audit_result clean ──────────────────────────────────

test_start "parse_audit_result parses clean result"
raw_file=$(mktemp)
cat > "$raw_file" <<'EOF'
{
  "audit_result": "clean",
  "gaps": [],
  "summary": "All sections covered"
}
EOF
result=$(parse_audit_result "$raw_file")
audit_result=$(echo "$result" | jq -r '.audit_result')
assert_equals "clean" "$audit_result"
rm -f "$raw_file"

# ─── Test: parse_audit_result with markdown wrapper ──────────────────

test_start "parse_audit_result handles markdown-wrapped JSON"
raw_file=$(mktemp)
cat > "$raw_file" <<'EOF'
Here is the audit result:

```json
{
  "audit_result": "clean",
  "gaps": [],
  "summary": "All good"
}
```
EOF
result=$(parse_audit_result "$raw_file")
audit_result=$(echo "$result" | jq -r '.audit_result')
assert_equals "clean" "$audit_result"
rm -f "$raw_file"

# ─── Test: parse_audit_result with invalid JSON ──────────────────────

test_start "parse_audit_result fails on invalid JSON"
raw_file=$(mktemp)
echo "This is not JSON at all" > "$raw_file"
if parse_audit_result "$raw_file" >/dev/null 2>&1; then
    test_fail "exit code 1" "exit code 0"
else
    test_pass
fi
rm -f "$raw_file"

# ─── Summary ─────────────────────────────────────────────────────────

echo ""
echo "═══ Results: $TESTS_PASSED/$TESTS_RUN passed ═══"
[[ $TESTS_FAILED -eq 0 ]] && exit 0 || exit 1
