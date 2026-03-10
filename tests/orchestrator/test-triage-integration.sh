#!/usr/bin/env bash
# Integration tests for ambiguity-triage-gate
# Tests triage template generation, parsing, gate logic, resolution merging,
# planner prompt filtering, and HTML report rendering.
# No Claude API calls — all functions are tested directly.
#
# Run: ./tests/orchestrator/test-triage-integration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Source common functions (provides info, error, warn, success, colors)
source "$PROJECT_DIR/bin/wt-common.sh"

# Provide log/model stubs
LOG_FILE="/dev/null"
log_info()  { :; }
log_warn()  { :; }
log_error() { :; }
run_claude() { return 0; }
model_id()  { echo "test-model"; }
emit_event() { :; }
send_notification() { :; }

# Source modules
LIB_DIR="$PROJECT_DIR/lib/orchestration"
DIGEST_DIR="wt/orchestration/digest"
EVENTS_ENABLED="false"
source "$LIB_DIR/events.sh" 2>/dev/null || true
source "$LIB_DIR/digest.sh"

# ── Test framework ──

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

test_start() {
    TESTS_RUN=$((TESTS_RUN + 1))
    echo -n "  $TESTS_RUN. $1 ... "
}

test_pass() {
    TESTS_PASSED=$((TESTS_PASSED + 1))
    echo -e "${GREEN}PASS${NC}"
}

test_fail() {
    TESTS_FAILED=$((TESTS_FAILED + 1))
    echo -e "${RED}FAIL${NC}"
    echo "    Expected: $1"
    echo "    Got: $2"
}

assert_equals() {
    local expected="$1" actual="$2"
    if [[ "$expected" == "$actual" ]]; then
        test_pass
    else
        test_fail "'$expected'" "'$actual'"
    fi
}

assert_contains() {
    local haystack="$1" needle="$2"
    if [[ "$haystack" == *"$needle"* ]]; then
        test_pass
    else
        test_fail "contains '$needle'" "'${haystack:0:200}'"
    fi
}

assert_file_exists() {
    local path="$1"
    if [[ -f "$path" ]]; then
        test_pass
    else
        test_fail "file exists: $path" "not found"
    fi
}

assert_file_not_exists() {
    local path="$1"
    if [[ ! -f "$path" ]]; then
        test_pass
    else
        test_fail "file not exists: $path" "found"
    fi
}

# ── Setup ──

WORK_DIR=$(mktemp -d)
trap "rm -rf '$WORK_DIR'" EXIT
_ORIG_DIR=$(pwd)

# ── Sample ambiguities.json fixtures ──

make_ambiguities() {
    cat <<'JSON'
{
  "ambiguities": [
    {
      "id": "AMB-001",
      "type": "underspecified",
      "source": "cart-checkout.md",
      "section": "Cart Merge",
      "description": "Cart merge on login conflict strategy not specified",
      "affects_requirements": ["REQ-CART-003"]
    },
    {
      "id": "AMB-002",
      "type": "missing_reference",
      "source": "subscription.md",
      "section": "Payment Failure",
      "description": "Email notification on payment failure mentioned but no template defined",
      "affects_requirements": ["REQ-SUB-003", "REQ-EMAIL-007"]
    },
    {
      "id": "AMB-003",
      "type": "contradictory",
      "source": "promo-banner.md",
      "section": "Dismissal",
      "description": "Returns on page reload contradicts session cookie dismissal",
      "affects_requirements": ["REQ-PROMO-001"]
    }
  ]
}
JSON
}

make_empty_ambiguities() {
    echo '{"ambiguities": []}'
}

# ============================================================
echo "============================================================"
echo "1. Triage Template Generation"
echo "============================================================"

# Test 1: Fresh triage generation
test_start "Fresh triage.md generated from ambiguities"
cd "$WORK_DIR"
mkdir -p gen1
make_ambiguities > gen1/ambiguities.json
generate_triage_md gen1/ambiguities.json gen1/triage.md
assert_file_exists "gen1/triage.md"

test_start "Triage contains all three AMB IDs"
content=$(cat gen1/triage.md)
found=0
echo "$content" | grep -q "### AMB-001" && found=$((found+1))
echo "$content" | grep -q "### AMB-002" && found=$((found+1))
echo "$content" | grep -q "### AMB-003" && found=$((found+1))
assert_equals "3" "$found"

test_start "Triage contains instructions header"
assert_contains "$content" "## Instructions"

test_start "Triage contains Decision and Note fields"
decision_count=$(grep -c '\*\*Decision:\*\*' gen1/triage.md)
note_count=$(grep -c '\*\*Note:\*\*' gen1/triage.md)
assert_equals "3" "$decision_count"

# Test 2: No triage for empty ambiguities
test_start "No triage.md when zero ambiguities"
mkdir -p gen2
make_empty_ambiguities > gen2/ambiguities.json
generate_triage_md gen2/ambiguities.json gen2/triage.md
assert_file_not_exists "gen2/triage.md"

# Test 3: Preservation on re-digest
test_start "Re-digest preserves existing decisions"
mkdir -p gen3

# Create initial triage with decisions filled in
make_ambiguities > gen3/ambiguities.json
generate_triage_md gen3/ambiguities.json gen3/triage.md

# Edit triage: set decision for AMB-001
sed -i '/### AMB-001/,/---/{s/\*\*Decision:\*\* *$/\*\*Decision:\*\* defer/}' gen3/triage.md
sed -i '/### AMB-001/,/---/{s/\*\*Note:\*\* *$/\*\*Note:\*\* planner will handle/}' gen3/triage.md

# Re-generate with same ambiguities — should preserve
generate_triage_md gen3/ambiguities.json gen3/triage-new.md gen3/triage.md

result=$(parse_triage_md gen3/triage-new.md)
amb1_decision=$(echo "$result" | jq -r '.["AMB-001"].decision')
assert_equals "defer" "$amb1_decision"

# Test 4: Removed ambiguities marked [REMOVED]
test_start "Removed ambiguity gets [REMOVED] marker"
mkdir -p gen4

# Create triage with 3 ambiguities
make_ambiguities > gen4/ambiguities.json
generate_triage_md gen4/ambiguities.json gen4/triage.md
# Set a decision for AMB-003
sed -i '/### AMB-003/,/---/{s/\*\*Decision:\*\* *$/\*\*Decision:\*\* ignore/}' gen4/triage.md

# New ambiguities without AMB-003
jq '.ambiguities = [.ambiguities[] | select(.id != "AMB-003")]' gen4/ambiguities.json > gen4/ambiguities-new.json

generate_triage_md gen4/ambiguities-new.json gen4/triage-new.md gen4/triage.md
assert_contains "$(cat gen4/triage-new.md)" "[REMOVED]"

# Test 5: New ambiguities appended
test_start "New ambiguity appended to existing triage"
mkdir -p gen5

make_ambiguities > gen5/ambiguities.json
generate_triage_md gen5/ambiguities.json gen5/triage.md

# Add AMB-004 to ambiguities
jq '.ambiguities += [{"id":"AMB-004","type":"implicit_assumption","source":"admin.md","section":"Auth","description":"Admin auth assumes session store exists","affects_requirements":["REQ-ADMIN-001"]}]' gen5/ambiguities.json > gen5/ambiguities-new.json

generate_triage_md gen5/ambiguities-new.json gen5/triage-new.md gen5/triage.md
assert_contains "$(cat gen5/triage-new.md)" "### AMB-004"

echo ""

# ============================================================
echo "============================================================"
echo "2. Triage Parsing"
echo "============================================================"

test_start "Valid decisions parsed correctly"
mkdir -p parse1
cat > parse1/triage.md <<'TRIAGE'
# Ambiguity Triage

### AMB-001 [underspecified]
**Decision:** defer
**Note:** planner handles

### AMB-002 [missing_reference]
**Decision:** fix
**Note:** add email template to spec

### AMB-003 [contradictory]
**Decision:** ignore
**Note:** out of scope
TRIAGE

result=$(parse_triage_md parse1/triage.md)
d1=$(echo "$result" | jq -r '.["AMB-001"].decision')
d2=$(echo "$result" | jq -r '.["AMB-002"].decision')
d3=$(echo "$result" | jq -r '.["AMB-003"].decision')
assert_equals "defer" "$d1"

test_start "Fix decision parsed"
assert_equals "fix" "$d2"

test_start "Ignore decision parsed"
assert_equals "ignore" "$d3"

test_start "Notes parsed correctly"
n1=$(echo "$result" | jq -r '.["AMB-001"].note')
assert_equals "planner handles" "$n1"

test_start "Invalid decision treated as untriaged"
mkdir -p parse2
cat > parse2/triage.md <<'TRIAGE'
### AMB-001 [underspecified]
**Decision:** maybe
**Note:** not sure
TRIAGE

result=$(parse_triage_md parse2/triage.md)
d=$(echo "$result" | jq -r '.["AMB-001"].decision')
assert_equals "" "$d"

test_start "Blank decision treated as untriaged"
mkdir -p parse3
cat > parse3/triage.md <<'TRIAGE'
### AMB-001 [underspecified]
**Decision:**
**Note:**
TRIAGE

result=$(parse_triage_md parse3/triage.md)
d=$(echo "$result" | jq -r '.["AMB-001"].decision')
assert_equals "" "$d"

test_start "[REMOVED] entries skipped"
mkdir -p parse4
cat > parse4/triage.md <<'TRIAGE'
### AMB-001 [underspecified]
**Decision:** defer
**Note:** ok

### AMB-002 [REMOVED]
**Decision:** fix
**Note:** was removed
TRIAGE

result=$(parse_triage_md parse4/triage.md)
has_amb2=$(echo "$result" | jq 'has("AMB-002")')
assert_equals "false" "$has_amb2"

test_start "Non-existent triage file returns empty JSON"
result=$(parse_triage_md "/nonexistent/triage.md")
assert_equals "{}" "$result"

echo ""

# ============================================================
echo "============================================================"
echo "3. Triage Gate"
echo "============================================================"

# Source planner for check_triage_gate (needs some stubs)
PLAN_FILENAME="$WORK_DIR/orchestration-plan.json"
STATE_FILENAME="$WORK_DIR/orchestration-state.json"
INPUT_MODE="digest"
find_input() { return 0; }
topological_sort() { return 0; }
wt_find_config() { return 1; }
generate_report() { :; }
source "$LIB_DIR/planner.sh" 2>/dev/null || true

test_start "No ambiguities → no_ambiguities"
mkdir -p "$WORK_DIR/gate1"
cd "$WORK_DIR/gate1"
mkdir -p "$DIGEST_DIR"
make_empty_ambiguities > "$DIGEST_DIR/ambiguities.json"
result=$(check_triage_gate)
assert_equals "no_ambiguities" "$result"

test_start "Missing ambiguities.json → no_ambiguities"
cd "$WORK_DIR"
mkdir -p gate2/$DIGEST_DIR
cd gate2
# No ambiguities.json
rm -f "$DIGEST_DIR/ambiguities.json"
result=$(check_triage_gate)
assert_equals "no_ambiguities" "$result"

test_start "Ambiguities exist, no triage.md → needs_triage"
cd "$WORK_DIR"
mkdir -p gate3/$DIGEST_DIR
cd gate3
make_ambiguities > "$DIGEST_DIR/ambiguities.json"
rm -f "$DIGEST_DIR/triage.md"
result=$(check_triage_gate)
assert_equals "needs_triage" "$result"

test_start "Triage exists with blank decisions → has_untriaged"
cd "$WORK_DIR"
mkdir -p gate4/$DIGEST_DIR
cd gate4
make_ambiguities > "$DIGEST_DIR/ambiguities.json"
generate_triage_md "$DIGEST_DIR/ambiguities.json" "$DIGEST_DIR/triage.md"
result=$(check_triage_gate)
assert_equals "has_untriaged" "$result"

test_start "All triaged with fix items → has_fixes"
cd "$WORK_DIR"
mkdir -p gate5/$DIGEST_DIR
cd gate5
make_ambiguities > "$DIGEST_DIR/ambiguities.json"
cat > "$DIGEST_DIR/triage.md" <<'TRIAGE'
### AMB-001 [underspecified]
**Decision:** defer
**Note:**

### AMB-002 [missing_reference]
**Decision:** fix
**Note:** needs template

### AMB-003 [contradictory]
**Decision:** ignore
**Note:**
TRIAGE
result=$(check_triage_gate)
assert_equals "has_fixes" "$result"

test_start "All triaged, no fixes → passed"
cd "$WORK_DIR"
mkdir -p gate6/$DIGEST_DIR
cd gate6
make_ambiguities > "$DIGEST_DIR/ambiguities.json"
cat > "$DIGEST_DIR/triage.md" <<'TRIAGE'
### AMB-001 [underspecified]
**Decision:** defer
**Note:**

### AMB-002 [missing_reference]
**Decision:** defer
**Note:**

### AMB-003 [contradictory]
**Decision:** ignore
**Note:**
TRIAGE
result=$(check_triage_gate)
assert_equals "passed" "$result"

test_start "Automated mode auto-defers all"
cd "$WORK_DIR"
mkdir -p gate7/$DIGEST_DIR
cd gate7
make_ambiguities > "$DIGEST_DIR/ambiguities.json"
rm -f "$DIGEST_DIR/triage.md"
TRIAGE_AUTO_DEFER=true
result=$(check_triage_gate 2>/dev/null | tail -1)
TRIAGE_AUTO_DEFER=false
assert_equals "passed" "$result"

test_start "Auto-defer sets resolved_by to auto"
resolved_by=$(jq -r '.ambiguities[0].resolved_by' "$DIGEST_DIR/ambiguities.json")
assert_equals "auto" "$resolved_by"

echo ""

# ============================================================
echo "============================================================"
echo "4. Resolution Merging"
echo "============================================================"

test_start "Triage merge sets resolution fields"
cd "$WORK_DIR"
mkdir -p merge1
make_ambiguities > merge1/ambiguities.json
decisions='{"AMB-001":{"decision":"defer","note":"planner handles"},"AMB-002":{"decision":"fix","note":"add template"},"AMB-003":{"decision":"ignore","note":""}}'
merge_triage_to_ambiguities merge1/ambiguities.json "$decisions"
res=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolution' merge1/ambiguities.json)
assert_equals "deferred" "$res"

test_start "Fix resolution mapped correctly"
res=$(jq -r '.ambiguities[] | select(.id == "AMB-002") | .resolution' merge1/ambiguities.json)
assert_equals "fixed" "$res"

test_start "Ignore resolution mapped correctly"
res=$(jq -r '.ambiguities[] | select(.id == "AMB-003") | .resolution' merge1/ambiguities.json)
assert_equals "ignored" "$res"

test_start "resolved_by set to triage"
by=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolved_by' merge1/ambiguities.json)
assert_equals "triage" "$by"

test_start "resolution_note preserved"
note=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolution_note' merge1/ambiguities.json)
assert_equals "planner handles" "$note"

test_start "Planner resolution merge works"
cd "$WORK_DIR"
mkdir -p merge2
make_ambiguities > merge2/ambiguities.json
cat > merge2/plan.json <<'JSON'
{
  "plan_version": 1,
  "brief_hash": "abc",
  "changes": [
    {
      "name": "cart-management",
      "scope": "cart features",
      "complexity": "M",
      "depends_on": [],
      "resolved_ambiguities": [
        {"id": "AMB-001", "resolution_note": "Sum quantities on merge"}
      ]
    }
  ]
}
JSON
merge_planner_resolutions merge2/ambiguities.json merge2/plan.json
res=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolution' merge2/ambiguities.json)
assert_equals "planner-resolved" "$res"

test_start "Planner resolution_note captured"
note=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolution_note' merge2/ambiguities.json)
assert_equals "Sum quantities on merge" "$note"

test_start "Planner resolved_by set to planner"
by=$(jq -r '.ambiguities[] | select(.id == "AMB-001") | .resolved_by' merge2/ambiguities.json)
assert_equals "planner" "$by"

test_start "Auto-defer merge sets resolved_by to auto"
cd "$WORK_DIR"
mkdir -p merge3
make_ambiguities > merge3/ambiguities.json
decisions='{"AMB-001":{"decision":"defer","note":""},"AMB-002":{"decision":"defer","note":""},"AMB-003":{"decision":"defer","note":""}}'
merge_triage_to_ambiguities merge3/ambiguities.json "$decisions" "auto"
by=$(jq -r '.ambiguities[0].resolved_by' merge3/ambiguities.json)
assert_equals "auto" "$by"

echo ""

# ============================================================
echo "============================================================"
echo "5. Planner Prompt Filtering"
echo "============================================================"

test_start "Only deferred ambiguities included in filter"
cd "$WORK_DIR"
mkdir -p prompt1
# Ambiguities with mixed resolutions
cat > prompt1/ambiguities.json <<'JSON'
{
  "ambiguities": [
    {"id": "AMB-001", "type": "underspecified", "description": "defer me", "resolution": "deferred", "resolved_by": "triage"},
    {"id": "AMB-002", "type": "missing_reference", "description": "fixed in spec", "resolution": "fixed", "resolved_by": "triage"},
    {"id": "AMB-003", "type": "contradictory", "description": "ignored", "resolution": "ignored", "resolved_by": "triage"}
  ]
}
JSON
filtered=$(jq '{ambiguities: [.ambiguities[] | select(.resolution == "deferred" or (has("resolution") | not))]}' prompt1/ambiguities.json)
count=$(echo "$filtered" | jq '.ambiguities | length')
assert_equals "1" "$count"

test_start "Fixed ambiguities excluded from prompt"
has_fixed=$(echo "$filtered" | jq '[.ambiguities[].id] | any(. == "AMB-002")')
assert_equals "false" "$has_fixed"

test_start "Ignored ambiguities excluded from prompt"
has_ignored=$(echo "$filtered" | jq '[.ambiguities[].id] | any(. == "AMB-003")')
assert_equals "false" "$has_ignored"

test_start "Unresolved ambiguities included in prompt"
cd "$WORK_DIR"
mkdir -p prompt2
cat > prompt2/ambiguities.json <<'JSON'
{
  "ambiguities": [
    {"id": "AMB-001", "type": "underspecified", "description": "no resolution field"}
  ]
}
JSON
filtered=$(jq '{ambiguities: [.ambiguities[] | select(.resolution == "deferred" or (has("resolution") | not))]}' prompt2/ambiguities.json)
count=$(echo "$filtered" | jq '.ambiguities | length')
assert_equals "1" "$count"

echo ""

# ============================================================
echo "============================================================"
echo "6. HTML Report Rendering"
echo "============================================================"

source "$LIB_DIR/reporter.sh" 2>/dev/null || true

test_start "Ambiguity table rendered with resolution columns"
cd "$WORK_DIR"
mkdir -p report1/$DIGEST_DIR
cd report1
cat > "$DIGEST_DIR/index.json" <<'JSON'
{"spec_base_dir":"/tmp","source_hash":"abc","file_count":1,"timestamp":"2026-03-10"}
JSON
cat > "$DIGEST_DIR/ambiguities.json" <<'JSON'
{
  "ambiguities": [
    {"id": "AMB-001", "type": "underspecified", "description": "test desc", "resolution": "deferred", "resolution_note": "planner decides", "resolved_by": "triage"}
  ]
}
JSON
echo '{"requirements":[]}' > "$DIGEST_DIR/requirements.json"
html=$(render_digest_section 2>/dev/null)
assert_contains "$html" "<table>"

test_start "Resolution column present in HTML"
assert_contains "$html" "deferred"

test_start "Color-coding applied (blue for deferred)"
assert_contains "$html" "background:#2a3a4e"

test_start "Zero ambiguities → no table rendered"
cd "$WORK_DIR"
mkdir -p report2/$DIGEST_DIR
cd report2
cat > "$DIGEST_DIR/index.json" <<'JSON'
{"spec_base_dir":"/tmp","source_hash":"abc","file_count":1,"timestamp":"2026-03-10"}
JSON
make_empty_ambiguities > "$DIGEST_DIR/ambiguities.json"
echo '{"requirements":[]}' > "$DIGEST_DIR/requirements.json"
html=$(render_digest_section 2>/dev/null)
no_table=true
echo "$html" | grep -q "Ambiguities" && no_table=false
if $no_table; then test_pass; else test_fail "no ambiguity section" "section found"; fi

cd "$_ORIG_DIR"
echo ""

# ============================================================
# Summary
# ============================================================

echo "============================================================"
echo "Results: $TESTS_PASSED passed, $TESTS_FAILED failed (of $TESTS_RUN)"
echo "============================================================"

[[ $TESTS_FAILED -eq 0 ]]
