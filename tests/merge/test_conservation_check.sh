#!/usr/bin/env bash
# test_conservation_check.sh — Unit tests for set-merge conservation check functions
#
# Tests the conservation check, entity counting, and strategy matching
# functions directly by sourcing set-merge's function definitions.
#
# Usage: ./tests/merge/test_conservation_check.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WT_MERGE="$(which set-merge)"
TEST_DIR=""
PASS_COUNT=0
FAIL_COUNT=0

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m'

pass() { echo -e "${GREEN}  PASS${NC} $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
fail() { echo -e "${RED}  FAIL${NC} $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

cleanup() {
    if [[ -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
}
trap cleanup EXIT

# Source set-merge functions (skip main execution)
# We need the functions but not main(). Source set-common first.
WM_DIR="$(dirname "$WT_MERGE")"
source "$WM_DIR/set-common.sh" 2>/dev/null || true

# Source just the function definitions from set-merge (stop before main)
eval "$(sed -n '/^# ─── Conservation Check/,/^main()/{ /^main()/d; p; }' "$WT_MERGE")"
# Also source strategy functions
eval "$(sed -n '/^# ─── Merge Strategy Config/,/^main()/{ /^main()/d; p; }' "$WT_MERGE")"
# And the LLM_RESOLVED_FILES declaration + entity functions
eval "$(sed -n '/^# ─── Entity Counting/,/^# ─── Merge Strategy Config/{ /^# ─── Merge Strategy Config/d; p; }' "$WM_MERGE" 2>/dev/null || true)"

# ─── Setup test repo ──────────────────────────────────────────────

TEST_DIR=$(mktemp -d /tmp/test-conservation-XXXXXX)
cd "$TEST_DIR"
git init --initial-branch=main -q
git config user.email "test@test.com"
git config user.name "Test"

# Create base file
cat > schema.prisma <<'EOF'
model User {
  id    String @id
  email String @unique
  name  String?
}

model Product {
  id    String @id
  name  String
  price Float
}

model Order {
  id     String @id
  userId String
  total  Float
}
EOF
git add -A && git commit -m "base" -q
BASE_SHA=$(git rev-parse HEAD)

# Branch A (main): add Review model + modify User
cat >> schema.prisma <<'EOF'

model Review {
  id      String @id
  rating  Int
  comment String?
}
EOF
sed -i 's/name  String?/name  String?\n  role  String?/' schema.prisma
git add -A && git commit -m "main: add Review + User.role" -q
OURS_SHA=$(git rev-parse HEAD)

# Branch B (feature): add Session model + modify User differently
git checkout -b feature "$BASE_SHA" -q
cat >> schema.prisma <<'EOF'

model Session {
  id        String @id
  token     String @unique
  expiresAt String
}
EOF
sed -i 's/name  String?/name  String?\n  avatar String?/' schema.prisma
git add -A && git commit -m "feature: add Session + User.avatar" -q
THEIRS_SHA=$(git rev-parse HEAD)

git checkout main -q

echo ""
echo "=== Conservation Check Unit Tests ==="
echo ""

# ─── Test 1: Both sides preserved → PASS ─────────────────────────

echo "Test 1: Both sides additions preserved"

# Create a "good" merged version with all additions
cat > schema.prisma <<'EOF'
model User {
  id     String @id
  email  String @unique
  name   String?
  role   String?
  avatar String?
}

model Product {
  id    String @id
  name  String
  price Float
}

model Order {
  id     String @id
  userId String
  total  Float
}

model Review {
  id      String @id
  rating  Int
  comment String?
}

model Session {
  id        String @id
  token     String @unique
  expiresAt String
}
EOF

LLM_RESOLVED_FILES=("schema.prisma")
result=$(conservation_check "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" "schema.prisma" 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]]; then
    pass "Conservation check passes when all additions preserved"
else
    fail "Conservation check should pass but got rc=$rc: $result"
fi

# ─── Test 2: Feature additions lost → FAIL ────────────────────────

echo "Test 2: Feature branch additions lost (simulates CraftBrew bug)"

# Create a "bad" merged version — only main additions, feature lost
cat > schema.prisma <<'EOF'
model User {
  id    String @id
  email String @unique
  name  String?
  role  String?
}

model Product {
  id    String @id
  name  String
  price Float
}

model Order {
  id     String @id
  userId String
  total  Float
}

model Review {
  id      String @id
  rating  Int
  comment String?
}
EOF

result=$(conservation_check "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" "schema.prisma" 2>&1) && rc=0 || rc=$?
if [[ $rc -ne 0 ]]; then
    # Verify it mentions the missing content
    if echo "$result" | grep -q "CONSERVATION FAILED"; then
        pass "Conservation check blocks when feature additions lost"
    else
        fail "Conservation check failed but didn't produce expected message: $result"
    fi
else
    fail "Conservation check should FAIL but passed (rc=0)"
fi

# ─── Test 3: Main additions lost → FAIL ──────────────────────────

echo "Test 3: Main branch additions lost"

# Create merged version with only feature additions
cat > schema.prisma <<'EOF'
model User {
  id     String @id
  email  String @unique
  name   String?
  avatar String?
}

model Product {
  id    String @id
  name  String
  price Float
}

model Order {
  id     String @id
  userId String
  total  Float
}

model Session {
  id        String @id
  token     String @unique
  expiresAt String
}
EOF

result=$(conservation_check "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" "schema.prisma" 2>&1) && rc=0 || rc=$?
if [[ $rc -ne 0 ]] && echo "$result" | grep -q "CONSERVATION FAILED"; then
    pass "Conservation check blocks when main additions lost"
else
    fail "Conservation check should FAIL for lost main additions (rc=$rc)"
fi

# ─── Test 4: Entity counting — additive strategy ─────────────────

echo "Test 4: Entity count check"

# Good merge — all models present (5 total: 3 base + Review + Session)
cat > schema.prisma <<'EOF'
model User { id String @id }
model Product { id String @id }
model Order { id String @id }
model Review { id String @id }
model Session { id String @id }
EOF

result=$(entity_count_check "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" "schema.prisma" "^model " 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]]; then
    pass "Entity count passes when all models present"
else
    fail "Entity count should pass (rc=$rc): $result"
fi

# Bad merge — Session model missing (4 instead of 5)
cat > schema.prisma <<'EOF'
model User { id String @id }
model Product { id String @id }
model Order { id String @id }
model Review { id String @id }
EOF

result=$(entity_count_check "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" "schema.prisma" "^model " 2>&1) && rc=0 || rc=$?
if [[ $rc -ne 0 ]]; then
    pass "Entity count blocks when model lost"
else
    fail "Entity count should FAIL when Session model missing (rc=$rc)"
fi

# ─── Test 5: run_conservation_checks — integration ───────────────

echo "Test 5: run_conservation_checks integration"

# Good merge
cat > schema.prisma <<'EOF'
model User {
  id     String @id
  email  String @unique
  name   String?
  role   String?
  avatar String?
}

model Product {
  id    String @id
  name  String
  price Float
}

model Order {
  id     String @id
  userId String
  total  Float
}

model Review {
  id      String @id
  rating  Int
  comment String?
}

model Session {
  id        String @id
  token     String @unique
  expiresAt String
}
EOF

LLM_RESOLVED_FILES=("schema.prisma")
result=$(run_conservation_checks "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]]; then
    pass "run_conservation_checks passes with complete merge"
else
    fail "run_conservation_checks should pass (rc=$rc): $result"
fi

# ─── Test 6: Empty LLM_RESOLVED_FILES → pass ─────────────────────

echo "Test 6: No LLM-resolved files → pass"

LLM_RESOLVED_FILES=()
result=$(run_conservation_checks "$BASE_SHA" "$OURS_SHA" "$THEIRS_SHA" 2>&1) && rc=0 || rc=$?
if [[ $rc -eq 0 ]]; then
    pass "Empty LLM_RESOLVED_FILES passes"
else
    fail "Should pass with no files (rc=$rc)"
fi

# ─── Test 7: Strategy matching ───────────────────────────────────

echo "Test 7: Strategy matching"

STRATEGY_NAMES=("schema" "middleware")
STRATEGY_PATTERNS=("prisma/schema.prisma|*.prisma" "src/middleware.ts")
STRATEGY_TYPES=("additive" "additive")
STRATEGY_ENTITY_PATTERNS=("^model |^enum " "^export ")
STRATEGY_VALIDATE_CMDS=("" "")
STRATEGY_LLM_HINTS=("DB schema hint" "Middleware hint")

idx=$(match_strategy "prisma/schema.prisma" 2>/dev/null) && rc=0 || rc=$?
if [[ $rc -eq 0 && "$idx" == "0" ]]; then
    pass "Matches prisma/schema.prisma to schema strategy"
else
    fail "Should match prisma/schema.prisma (rc=$rc, idx=$idx)"
fi

idx=$(match_strategy "src/middleware.ts" 2>/dev/null) && rc=0 || rc=$?
if [[ $rc -eq 0 && "$idx" == "1" ]]; then
    pass "Matches src/middleware.ts to middleware strategy"
else
    fail "Should match src/middleware.ts (rc=$rc, idx=$idx)"
fi

idx=$(match_strategy "src/app.ts" 2>/dev/null) && rc=0 || rc=$?
if [[ $rc -ne 0 ]]; then
    pass "No match for src/app.ts (correct — defaults to conservation-only)"
else
    fail "Should not match src/app.ts"
fi

# ─── Test 8: LLM hint generation ─────────────────────────────────

echo "Test 8: LLM hint for matched file"

hint=$(get_llm_hint "prisma/schema.prisma" 2>/dev/null) || true
if echo "$hint" | grep -q "additive" && echo "$hint" | grep -q "DB schema hint"; then
    pass "LLM hint includes strategy type and custom hint"
else
    fail "LLM hint missing expected content: $hint"
fi

hint=$(get_llm_hint "src/app.ts" 2>/dev/null) || true
if [[ -z "$hint" ]]; then
    pass "No LLM hint for unmatched file"
else
    fail "Should have no hint for unmatched file: $hint"
fi

# Clean up strategy arrays
STRATEGY_NAMES=()
STRATEGY_PATTERNS=()
STRATEGY_TYPES=()
STRATEGY_ENTITY_PATTERNS=()
STRATEGY_VALIDATE_CMDS=()
STRATEGY_LLM_HINTS=()

# ─── Results ──────────────────────────────────────────────────────

echo ""
echo "=== Results ==="
echo -e "  ${GREEN}Passed: $PASS_COUNT${NC}"
if [[ $FAIL_COUNT -gt 0 ]]; then
    echo -e "  ${RED}Failed: $FAIL_COUNT${NC}"
    exit 1
else
    echo -e "  Failed: 0"
    echo ""
    echo -e "${GREEN}All tests passed.${NC}"
    exit 0
fi
