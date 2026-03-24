#!/usr/bin/env bash
# Integration tests for spec-digest-pipeline
# Tests scan, prompt build, parse, validate, write, freshness, stabilize, coverage
# using the scaffold-complex CraftBrew fixture (17 files).
# This fixture is a local copy of the CraftBrew spec (github.com/tatargabor/craftbrew).
# No Claude API calls — run_claude is stubbed.
#
# Run: ./tests/orchestrator/test-digest-integration.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
SPEC_DIR="$PROJECT_DIR/tests/e2e/scaffold-complex/docs"

# Source common functions (provides info, error, warn, success, colors)
source "$PROJECT_DIR/bin/set-common.sh"

# Provide log/model stubs that digest.sh depends on (normally from set-orchestrate)
LOG_FILE="/dev/null"
log_info()  { :; }
log_warn()  { :; }
log_error() { :; }
run_claude() { return 0; }
model_id()  { echo "test-model"; }

# Source digest module and its dependency (events.sh for emit_event)
LIB_DIR="$PROJECT_DIR/lib/orchestration"
DIGEST_DIR="set/orchestration/digest"
EVENTS_ENABLED="false"
source "$LIB_DIR/events.sh"
source "$LIB_DIR/digest.sh"

# ── Test framework ──

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
CLEANUP_DIRS=()

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

assert_gt() {
    local actual="$1" threshold="$2"
    if [[ "$actual" -gt "$threshold" ]]; then
        test_pass
    else
        test_fail "> $threshold" "$actual"
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

assert_valid_json() {
    local file="$1"
    if jq empty "$file" 2>/dev/null; then
        test_pass
    else
        test_fail "valid JSON: $file" "parse error"
    fi
}


# ── Cleanup ──

cleanup_all() {
    for d in "${CLEANUP_DIRS[@]}"; do
        rm -rf "$d" 2>/dev/null || true
    done
}
trap cleanup_all EXIT

# Create a temp working directory (digest writes to $DIGEST_DIR relative to cwd)
WORK_DIR=$(mktemp -d)
CLEANUP_DIRS+=("$WORK_DIR")
cd "$WORK_DIR"

# Override log functions to write to temp log
LOG_FILE="$WORK_DIR/test.log"

echo "============================================================"
echo "Integration Tests: spec-digest-pipeline"
echo "  Fixture: scaffold-complex/docs (CraftBrew, 17 files)"
echo "============================================================"
echo ""

# ============================================================
# Section 1: scan_spec_directory
# ============================================================

echo "── scan_spec_directory ──"

test_start "scans all 17 .md files"
scan_result=$(scan_spec_directory "$SPEC_DIR")
file_count=$(echo "$scan_result" | jq -r '.file_count')
assert_equals "17" "$file_count"

test_start "detects master file as v1-craftbrew.md"
master=$(echo "$scan_result" | jq -r '.master_file')
assert_equals "v1-craftbrew.md" "$master"

test_start "produces a non-empty source_hash"
hash=$(echo "$scan_result" | jq -r '.source_hash')
assert_gt "${#hash}" "10"

test_start "hash is deterministic (same on second scan)"
scan2=$(scan_spec_directory "$SPEC_DIR")
hash2=$(echo "$scan2" | jq -r '.source_hash')
assert_equals "$hash" "$hash2"

test_start "file list includes subdirectory files"
has_cart=$(echo "$scan_result" | jq -r '.files[]' | grep -c 'cart-checkout.md' || true)
assert_equals "1" "$has_cart"

test_start "file list includes catalog files"
has_coffees=$(echo "$scan_result" | jq -r '.files[]' | grep -c 'coffees.md' || true)
assert_equals "1" "$has_coffees"

test_start "spec_base_dir is absolute path"
base_dir=$(echo "$scan_result" | jq -r '.spec_base_dir')
assert_contains "$base_dir" "/tests/e2e/scaffold-complex/docs"

test_start "single file mode works"
single_result=$(scan_spec_directory "$SPEC_DIR/v1-craftbrew.md")
single_count=$(echo "$single_result" | jq -r '.file_count')
assert_equals "1" "$single_count"

echo ""

# ============================================================
# Section 2: build_digest_prompt
# ============================================================

echo "── build_digest_prompt ──"

test_start "prompt includes master file content first"
prompt=$(build_digest_prompt "$SPEC_DIR" "$scan_result")
# Master file marker should appear before feature files
first_file_marker=$(echo "$prompt" | grep -n '=== FILE:' | head -1)
assert_contains "$first_file_marker" "v1-craftbrew.md"

test_start "prompt includes all spec files"
file_markers=$(echo "$prompt" | grep -c '=== FILE:' || true)
assert_equals "17" "$file_markers"

test_start "prompt includes structured instructions"
assert_contains "$prompt" "Requirement Extraction"

test_start "prompt includes output format specification"
assert_contains "$prompt" "REQ-{DOMAIN_SHORT}-{NNN}"

test_start "prompt is substantial (>5000 chars)"
prompt_len=${#prompt}
assert_gt "$prompt_len" "5000"

test_start "prompt includes CRUD granularity rule"
assert_contains "$prompt" "CRUD"

test_start "prompt includes compound description granularity rule"
assert_contains "$prompt" "Compound"

echo ""

# ============================================================
# Section 3: parse_digest_response
# ============================================================

echo "── parse_digest_response ──"

# Synthetic digest JSON mimicking Claude output for CraftBrew
SAMPLE_DIGEST='{
  "file_classifications": {
    "v1-craftbrew.md": "execution",
    "catalog/coffees.md": "data",
    "catalog/equipment.md": "data",
    "catalog/merch.md": "data",
    "catalog/bundles.md": "data",
    "features/product-catalog.md": "feature",
    "features/cart-checkout.md": "feature",
    "features/subscription.md": "feature",
    "features/user-accounts.md": "feature",
    "features/reviews-wishlist.md": "feature",
    "features/promotions.md": "feature",
    "features/content-stories.md": "feature",
    "features/email-notifications.md": "feature",
    "features/admin.md": "feature",
    "features/i18n.md": "convention",
    "features/seo.md": "feature",
    "design/design-system.md": "convention"
  },
  "conventions": {
    "categories": [
      {"name": "Currency", "rules": ["HUF integer format", "No decimals"]},
      {"name": "i18n", "rules": ["/hu and /en routes", "Default /hu"]}
    ]
  },
  "data_definitions": "## Coffees\n8 specialty coffees with variants\n\n## Equipment\n7 brewing items",
  "requirements": [
    {"id": "REQ-CAT-001", "title": "Product listing with filters", "source": "features/product-catalog.md", "source_section": "Search and Filter", "domain": "catalog", "brief": "Products can be filtered by category, origin, and roast level"},
    {"id": "REQ-CAT-002", "title": "Variant selection", "source": "features/product-catalog.md", "source_section": "Variants", "domain": "catalog", "brief": "Each coffee has form and size variants with independent pricing"},
    {"id": "REQ-CART-001", "title": "Add to cart", "source": "features/cart-checkout.md", "source_section": "Cart Operations", "domain": "cart", "brief": "Anonymous users can add products with selected variant to cart"},
    {"id": "REQ-CART-002", "title": "Checkout with Stripe", "source": "features/cart-checkout.md", "source_section": "Checkout", "domain": "cart", "brief": "Cart checkout creates Stripe payment intent in test mode"},
    {"id": "REQ-SUB-001", "title": "Coffee subscription", "source": "features/subscription.md", "source_section": "Subscription Plans", "domain": "subscription", "brief": "Users can subscribe to recurring coffee deliveries"},
    {"id": "REQ-AUTH-001", "title": "User registration", "source": "features/user-accounts.md", "source_section": "Registration", "domain": "auth", "brief": "New users register with email and password"},
    {"id": "REQ-PROMO-001", "title": "ELSO10 coupon", "source": "features/promotions.md", "source_section": "Coupons", "domain": "promotions", "brief": "ELSO10 coupon gives 10% discount on first order only"},
    {"id": "REQ-ADMIN-001", "title": "Admin dashboard", "source": "features/admin.md", "source_section": "Dashboard", "domain": "admin", "brief": "Admin sees order count, revenue, and recent activity"},
    {"id": "REQ-INTL-001", "title": "Route-based language switching", "source": "features/i18n.md", "source_section": "Routing", "domain": "i18n", "brief": "All pages available under /hu and /en prefixes", "cross_cutting": true, "affects_domains": ["catalog", "cart", "auth"]},
    {"id": "REQ-SEO-001", "title": "Meta tags per page", "source": "features/seo.md", "source_section": "Meta Tags", "domain": "seo", "brief": "Every page has unique title, description, and OG tags"}
  ],
  "domains": [
    {"name": "catalog", "summary": "Product catalog with search, filter, variants, and cross-sell"},
    {"name": "cart", "summary": "Shopping cart and Stripe checkout"},
    {"name": "subscription", "summary": "Recurring coffee delivery subscriptions"},
    {"name": "auth", "summary": "User registration, login, profile management"},
    {"name": "promotions", "summary": "Coupons, promo days, gift cards"},
    {"name": "admin", "summary": "Admin dashboard and CRUD operations"},
    {"name": "i18n", "summary": "HU/EN internationalization"},
    {"name": "seo", "summary": "SEO meta tags, schema.org, sitemap"}
  ],
  "dependencies": [
    {"from": "REQ-CART-001", "to": "REQ-CAT-002", "type": "depends_on"},
    {"from": "REQ-SUB-001", "to": "REQ-AUTH-001", "type": "depends_on"},
    {"from": "REQ-PROMO-001", "to": "REQ-CART-001", "type": "depends_on"}
  ],
  "ambiguities": [
    {"id": "AMB-001", "type": "underspecified", "source": "features/subscription.md", "section": "Delivery Scheduling", "description": "Delivery frequency options not fully enumerated", "affects_requirements": ["REQ-SUB-001"]}
  ],
  "execution_hints": {"suggested_order": ["auth", "catalog", "cart", "subscription"]}
}'

test_start "parses clean JSON"
parsed=$(parse_digest_response "$SAMPLE_DIGEST" "$SPEC_DIR" "$scan_result")
req_count=$(echo "$parsed" | jq '.requirements | length')
assert_equals "10" "$req_count"

test_start "parses JSON wrapped in markdown fences"
fenced_response='```json
'"$SAMPLE_DIGEST"'
```'
parsed_fenced=$(parse_digest_response "$fenced_response" "$SPEC_DIR" "$scan_result")
fenced_count=$(echo "$parsed_fenced" | jq '.requirements | length')
assert_equals "10" "$fenced_count"

test_start "parses JSON with leading commentary"
commented_response="Here is the digest output:

$SAMPLE_DIGEST"
parsed_commented=$(parse_digest_response "$commented_response" "$SPEC_DIR" "$scan_result")
commented_count=$(echo "$parsed_commented" | jq '.requirements | length')
assert_equals "10" "$commented_count"

test_start "rejects garbage input"
set +e
parse_digest_response "this is not json at all" "$SPEC_DIR" "$scan_result" 2>/dev/null
parse_rc=$?
set -e
assert_equals "1" "$parse_rc"

echo ""

# ============================================================
# Section 4: validate_digest
# ============================================================

echo "── validate_digest ──"

test_start "valid digest passes validation"
set +e
validate_digest "$SAMPLE_DIGEST" 2>/dev/null
valid_rc=$?
set -e
assert_equals "0" "$valid_rc"

test_start "accepts alphanumeric domain IDs (e.g. REQ-I18N-001)"
i18n_digest=$(echo "$SAMPLE_DIGEST" | jq '.requirements[0].id = "REQ-I18N-001"')
set +e
validate_digest "$i18n_digest" 2>/dev/null
i18n_rc=$?
set -e
assert_equals "0" "$i18n_rc"

test_start "rejects invalid requirement ID format"
bad_id_digest=$(echo "$SAMPLE_DIGEST" | jq '.requirements[0].id = "INVALID-ID"')
set +e
validate_digest "$bad_id_digest" 2>/dev/null
bad_id_rc=$?
set -e
assert_gt "$bad_id_rc" "0"

test_start "rejects duplicate requirement IDs"
dup_digest=$(echo "$SAMPLE_DIGEST" | jq '.requirements[1].id = .requirements[0].id')
set +e
validate_digest "$dup_digest" 2>/dev/null
dup_rc=$?
set -e
assert_gt "$dup_rc" "0"

test_start "rejects orphan domain reference"
orphan_digest=$(echo "$SAMPLE_DIGEST" | jq '.requirements[0].domain = "nonexistent-domain"')
set +e
validate_digest "$orphan_digest" 2>/dev/null
orphan_rc=$?
set -e
assert_gt "$orphan_rc" "0"

test_start "rejects dependency referencing missing requirement"
bad_dep_digest=$(echo "$SAMPLE_DIGEST" | jq '.dependencies[0].from = "REQ-FAKE-999"')
set +e
validate_digest "$bad_dep_digest" 2>/dev/null
bad_dep_rc=$?
set -e
assert_gt "$bad_dep_rc" "0"

test_start "cross-cutting without affects_domains flagged"
cc_digest=$(echo "$SAMPLE_DIGEST" | jq '.requirements[8].affects_domains = []')
set +e
validate_digest "$cc_digest" 2>/dev/null
cc_rc=$?
set -e
assert_gt "$cc_rc" "0"

echo ""

# ============================================================
# Section 5: write_digest_output + freshness check
# ============================================================

echo "── write_digest_output + check_digest_freshness ──"

test_start "freshness returns 'missing' when no digest"
freshness=$(check_digest_freshness "$SPEC_DIR")
assert_equals "missing" "$freshness"

test_start "write_digest_output creates all expected files"
write_digest_output "$SAMPLE_DIGEST" "$SPEC_DIR" "$scan_result"
# Check each file
all_exist=true
for f in index.json conventions.json requirements.json dependencies.json ambiguities.json coverage.json data-definitions.md; do
    [[ -f "$DIGEST_DIR/$f" ]] || { all_exist=false; break; }
done
if $all_exist; then test_pass; else test_fail "all files exist" "missing: $f"; fi

test_start "index.json is valid and contains source_hash"
assert_valid_json "$DIGEST_DIR/index.json"

test_start "index.json source_hash matches scan"
stored_hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json")
expected_hash=$(echo "$scan_result" | jq -r '.source_hash')
assert_equals "$expected_hash" "$stored_hash"

test_start "requirements.json has 10 requirements"
req_in_file=$(jq '.requirements | length' "$DIGEST_DIR/requirements.json")
assert_equals "10" "$req_in_file"

test_start "conventions.json has categories"
cat_count=$(jq '.categories | length' "$DIGEST_DIR/conventions.json")
assert_equals "2" "$cat_count"

test_start "dependencies.json has 3 entries"
dep_count=$(jq '.dependencies | length' "$DIGEST_DIR/dependencies.json")
assert_equals "3" "$dep_count"

test_start "ambiguities.json has 1 entry"
amb_count=$(jq '.ambiguities | length' "$DIGEST_DIR/ambiguities.json")
assert_equals "1" "$amb_count"

test_start "domain summary files created"
domain_files=$(ls "$DIGEST_DIR/domains/"*.md 2>/dev/null | wc -l)
assert_equals "8" "$domain_files"

test_start "coverage.json starts empty"
cov_count=$(jq '.coverage | length' "$DIGEST_DIR/coverage.json")
assert_equals "0" "$cov_count"

test_start "freshness returns 'fresh' after write"
freshness2=$(check_digest_freshness "$SPEC_DIR")
assert_equals "fresh" "$freshness2"

test_start "hash re-check: stored hash matches recomputed hash (skip re-digest scenario)"
_stored_hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json" 2>/dev/null)
_recomputed=$(scan_spec_directory "$SPEC_DIR" 2>/dev/null | jq -r '.source_hash' 2>/dev/null)
assert_equals "$_stored_hash" "$_recomputed"

echo ""

# ============================================================
# Section 6: stabilize_ids
# ============================================================

echo "── stabilize_ids ──"

# Simulate a re-digest with one requirement changed and one removed
REDIGEST=$(echo "$SAMPLE_DIGEST" | jq '
  .requirements = [.requirements[] | select(.id != "REQ-SEO-001")] |
  .requirements += [{"id": "REQ-EMAIL-001", "title": "Order confirmation email", "source": "features/email-notifications.md", "source_section": "Transactional Emails", "domain": "catalog", "brief": "Send order confirmation email after checkout"}]
')

test_start "stabilize_ids preserves matching IDs"
stabilized=$(stabilize_ids "$REDIGEST")
# REQ-CAT-001 should survive (same source+section)
has_cat001=$(echo "$stabilized" | jq '[.requirements[] | select(.id == "REQ-CAT-001")] | length')
assert_equals "1" "$has_cat001"

test_start "stabilize_ids marks removed requirements"
removed=$(echo "$stabilized" | jq '[.requirements[] | select(.status == "removed")] | length')
assert_gt "$removed" "0"

test_start "stabilize_ids includes new requirements"
has_email=$(echo "$stabilized" | jq '[.requirements[] | select(.id == "REQ-EMAIL-001")] | length')
assert_equals "1" "$has_email"

echo ""

# ============================================================
# Section 7: populate_coverage + coverage gaps
# ============================================================

echo "── populate_coverage ──"

# Create a mock plan file
PLAN_FILE="$WORK_DIR/plan.json"
cat > "$PLAN_FILE" <<'PLAN'
{
  "changes": [
    {
      "name": "setup-catalog",
      "requirements": ["REQ-CAT-001", "REQ-CAT-002", "REQ-INTL-001"],
      "also_affects_reqs": []
    },
    {
      "name": "setup-i18n",
      "requirements": [],
      "also_affects_reqs": ["REQ-INTL-001"]
    },
    {
      "name": "setup-cart",
      "requirements": ["REQ-CART-001", "REQ-CART-002"],
      "also_affects_reqs": []
    },
    {
      "name": "setup-auth",
      "requirements": ["REQ-AUTH-001"],
      "also_affects_reqs": []
    }
  ]
}
PLAN

test_start "populate_coverage maps requirements to changes"
populate_coverage "$PLAN_FILE"
covered=$(jq '.coverage | length' "$DIGEST_DIR/coverage.json")
assert_equals "6" "$covered"

test_start "coverage tracks correct change ownership"
cart_change=$(jq -r '.coverage["REQ-CART-001"].change' "$DIGEST_DIR/coverage.json")
assert_equals "setup-cart" "$cart_change"

test_start "coverage status starts as 'planned'"
cart_status=$(jq -r '.coverage["REQ-CART-001"].status' "$DIGEST_DIR/coverage.json")
assert_equals "planned" "$cart_status"

test_start "cross-cutting also_affects tracked"
intl_also=$(jq -r '.coverage["REQ-INTL-001"].also_affects[0] // empty' "$DIGEST_DIR/coverage.json")
assert_equals "setup-i18n" "$intl_also"

test_start "uncovered requirements detected"
uncovered=$(jq '.uncovered | length' "$DIGEST_DIR/coverage.json")
# 10 total - 6 covered = 4 uncovered (SUB-001, PROMO-001, ADMIN-001, SEO-001)
assert_gt "$uncovered" "0"

echo ""

# ============================================================
# Section 8: update_coverage_status
# ============================================================

echo "── update_coverage_status ──"

test_start "status transitions to 'dispatched'"
update_coverage_status "setup-cart" "dispatched"
new_status=$(jq -r '.coverage["REQ-CART-001"].status' "$DIGEST_DIR/coverage.json")
assert_equals "dispatched" "$new_status"

test_start "status transitions to 'running'"
update_coverage_status "setup-cart" "running"
run_status=$(jq -r '.coverage["REQ-CART-001"].status' "$DIGEST_DIR/coverage.json")
assert_equals "running" "$run_status"

test_start "status transitions to 'merged'"
update_coverage_status "setup-cart" "merged"
merge_status=$(jq -r '.coverage["REQ-CART-001"].status' "$DIGEST_DIR/coverage.json")
assert_equals "merged" "$merge_status"

test_start "other changes unaffected by status update"
cat_status=$(jq -r '.coverage["REQ-CAT-001"].status' "$DIGEST_DIR/coverage.json")
assert_equals "planned" "$cat_status"

echo ""

# ============================================================
# Section 9: cmd_digest --dry-run (no API, synthetic response)
# ============================================================

echo "── cmd_digest --dry-run (with stubbed API) ──"

# Override call_digest_api to return our sample digest
call_digest_api() { echo "$SAMPLE_DIGEST"; }

# Clean digest dir for this test
rm -rf "$DIGEST_DIR"

test_start "dry-run does not write files"
cmd_digest --spec "$SPEC_DIR" --dry-run >/dev/null 2>&1
if [[ ! -d "$DIGEST_DIR" ]]; then
    test_pass
else
    test_fail "no $DIGEST_DIR" "directory exists"
fi

test_start "full run writes digest"
cmd_digest --spec "$SPEC_DIR" >/dev/null 2>&1
if [[ -f "$DIGEST_DIR/requirements.json" ]]; then
    test_pass
else
    test_fail "requirements.json exists" "not found"
fi

echo ""

# ============================================================
# Section: Coverage Enforcement (require_full_coverage)
# ============================================================

echo "── coverage enforcement ──"

# Setup: create a working digest dir with requirements
COV_WORK=$(mktemp -d)
CLEANUP_DIRS+=("$COV_WORK")
_ORIG_DIR=$(pwd)
cd "$COV_WORK"
DIGEST_DIR="set/orchestration/digest"
mkdir -p "$DIGEST_DIR"

# Create requirements.json with 4 REQs
cat > "$DIGEST_DIR/requirements.json" <<'REQ_EOF'
{
  "requirements": [
    {"id": "REQ-CART-001", "title": "Add to cart", "domain": "cart"},
    {"id": "REQ-CART-002", "title": "Remove from cart", "domain": "cart"},
    {"id": "REQ-AUTH-001", "title": "Login", "domain": "auth"},
    {"id": "REQ-I18N-001", "title": "i18n routing", "domain": "i18n"}
  ]
}
REQ_EOF

# Plan that covers only 2 of 4 REQs
cat > "$COV_WORK/plan-partial.json" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {
      "name": "add-cart",
      "scope": "Cart",
      "complexity": "medium",
      "depends_on": [],
      "requirements": ["REQ-CART-001", "REQ-CART-002"]
    }
  ]
}
PLAN_EOF

# Plan that covers all 4 REQs
cat > "$COV_WORK/plan-full.json" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {
      "name": "add-cart",
      "scope": "Cart",
      "complexity": "medium",
      "depends_on": [],
      "requirements": ["REQ-CART-001", "REQ-CART-002"]
    },
    {
      "name": "add-auth",
      "scope": "Auth",
      "complexity": "medium",
      "depends_on": [],
      "requirements": ["REQ-AUTH-001", "REQ-I18N-001"]
    }
  ]
}
PLAN_EOF

# Plan with REQ in also_affects but not in requirements
cat > "$COV_WORK/plan-also-only.json" <<'PLAN_EOF'
{
  "plan_version": 1,
  "brief_hash": "test",
  "changes": [
    {
      "name": "add-cart",
      "scope": "Cart",
      "complexity": "medium",
      "depends_on": [],
      "requirements": ["REQ-CART-001", "REQ-CART-002"],
      "also_affects_reqs": ["REQ-I18N-001"]
    },
    {
      "name": "add-auth",
      "scope": "Auth",
      "complexity": "medium",
      "depends_on": [],
      "requirements": ["REQ-AUTH-001"]
    }
  ]
}
PLAN_EOF

test_start "REQUIRE_FULL_COVERAGE=true + uncovered → returns 1"
REQUIRE_FULL_COVERAGE=true
populate_coverage "$COV_WORK/plan-partial.json" 2>/dev/null && cov_rc=0 || cov_rc=$?
if [[ "$cov_rc" -eq 1 ]]; then
    test_pass
else
    test_fail "rc=1" "rc=$cov_rc"
fi

test_start "REQUIRE_FULL_COVERAGE=false + uncovered → returns 0, warns"
REQUIRE_FULL_COVERAGE=false
cov_output=$(populate_coverage "$COV_WORK/plan-partial.json" 2>&1) && cov_rc=0 || cov_rc=$?
if [[ "$cov_rc" -eq 0 ]]; then
    test_pass
else
    test_fail "rc=0" "rc=$cov_rc"
fi

test_start "all REQs covered → returns 0 regardless of directive"
REQUIRE_FULL_COVERAGE=true
populate_coverage "$COV_WORK/plan-full.json" 2>/dev/null && cov_rc=0 || cov_rc=$?
if [[ "$cov_rc" -eq 0 ]]; then
    test_pass
else
    test_fail "rc=0" "rc=$cov_rc"
fi

test_start "REQ in also_affects but not in requirements → counted as uncovered"
REQUIRE_FULL_COVERAGE=true
populate_coverage "$COV_WORK/plan-also-only.json" 2>/dev/null && cov_rc=0 || cov_rc=$?
# REQ-I18N-001 is only in also_affects, so it's uncovered → should return 1
if [[ "$cov_rc" -eq 1 ]]; then
    test_pass
else
    test_fail "rc=1 (REQ-I18N-001 uncovered)" "rc=$cov_rc"
fi

# Reset
REQUIRE_FULL_COVERAGE=false
cd "$_ORIG_DIR"

echo ""

# ============================================================
# Summary
# ============================================================

echo "============================================================"
echo "Results: $TESTS_PASSED passed, $TESTS_FAILED failed (of $TESTS_RUN)"
echo "============================================================"

[[ $TESTS_FAILED -eq 0 ]]
