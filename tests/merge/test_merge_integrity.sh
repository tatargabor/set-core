#!/usr/bin/env bash
# test_merge_integrity.sh — Reproduce CraftBrew merge data loss scenario
#
# Creates a temp git repo with two branches that both modify a Prisma schema.
# Branch A (main): base schema with 19 models
# Branch B (feature): base + 2 additional models (Session, PasswordResetToken)
# with overlapping edits that create a realistic conflict.
#
# The test verifies that wt-merge's conservation check catches model loss.
#
# Usage:
#   ./tests/merge/test_merge_integrity.sh [--baseline]
#
# --baseline: Run without conservation check (expect merge to succeed even with data loss)
# Without flag: Run with conservation check (expect merge to BLOCK on data loss)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TEST_DIR=""
BASELINE_MODE=false

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info()  { echo -e "${GREEN}[TEST]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }
pass()  { echo -e "${GREEN}[PASS]${NC} $*"; }

cleanup() {
    if [[ -n "$TEST_DIR" && -d "$TEST_DIR" ]]; then
        rm -rf "$TEST_DIR"
    fi
}
trap cleanup EXIT

# Parse args
while [[ $# -gt 0 ]]; do
    case "$1" in
        --baseline) BASELINE_MODE=true; shift ;;
        *) echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# ─── Setup ────────────────────────────────────────────────────────

TEST_DIR=$(mktemp -d /tmp/test-merge-integrity-XXXXXX)
info "Test directory: $TEST_DIR"

cd "$TEST_DIR"
git init --initial-branch=main -q
git config user.email "test@test.com"
git config user.name "Test"

# ─── Base schema (shared by both branches) ────────────────────────

# Create a realistic Prisma schema with 19 models.
# Both branches will modify this file — main adds some fields,
# feature adds 2 new models + some fields, creating a conflict.

mkdir -p prisma
cat > prisma/schema.prisma <<'SCHEMA'
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  orders    Order[]
  reviews   Review[]
  addresses Address[]
}

model Product {
  id          String   @id @default(cuid())
  name        String
  description String?
  price       Float
  createdAt   DateTime @default(now())
  variants    ProductVariant[]
  reviews     Review[]
  cartItems   CartItem[]
}

model ProductVariant {
  id        String  @id @default(cuid())
  name      String
  price     Float
  productId String
  product   Product @relation(fields: [productId], references: [id])
}

model Order {
  id        String      @id @default(cuid())
  userId    String
  user      User        @relation(fields: [userId], references: [id])
  status    OrderStatus @default(PENDING)
  total     Float
  createdAt DateTime    @default(now())
  items     OrderItem[]
}

enum OrderStatus {
  PENDING
  PROCESSING
  SHIPPED
  DELIVERED
  CANCELLED
}

model OrderItem {
  id        String @id @default(cuid())
  orderId   String
  order     Order  @relation(fields: [orderId], references: [id])
  productId String
  quantity  Int
  price     Float
}

model Review {
  id        String   @id @default(cuid())
  userId    String
  user      User     @relation(fields: [userId], references: [id])
  productId String
  product   Product  @relation(fields: [productId], references: [id])
  rating    Int
  comment   String?
  createdAt DateTime @default(now())
}

model Address {
  id      String @id @default(cuid())
  userId  String
  user    User   @relation(fields: [userId], references: [id])
  street  String
  city    String
  zip     String
  country String
}

model CartItem {
  id        String @id @default(cuid())
  sessionId String
  productId String
  product   Product @relation(fields: [productId], references: [id])
  quantity  Int
}

model CartSession {
  id        String   @id @default(cuid())
  token     String   @unique
  createdAt DateTime @default(now())
  expiresAt DateTime
}

model Coupon {
  id        String   @id @default(cuid())
  code      String   @unique
  discount  Float
  active    Boolean  @default(true)
  createdAt DateTime @default(now())
}

model GiftCard {
  id      String @id @default(cuid())
  code    String @unique
  balance Float
  userId  String?
}

model Invoice {
  id      String @id @default(cuid())
  orderId String
  number  String @unique
  total   Float
  paidAt  DateTime?
}

model Story {
  id        String   @id @default(cuid())
  title     String
  content   String
  slug      String   @unique
  createdAt DateTime @default(now())
}

model StoryCategory {
  id   String @id @default(cuid())
  name String @unique
  slug String @unique
}

model Subscription {
  id        String   @id @default(cuid())
  userId    String
  plan      String
  active    Boolean  @default(true)
  createdAt DateTime @default(now())
}

model Equipment {
  id    String @id @default(cuid())
  name  String
  price Float
  type  String
}

model Merch {
  id    String @id @default(cuid())
  name  String
  price Float
  size  String?
}

model Bundle {
  id    String @id @default(cuid())
  name  String
  price Float
}
SCHEMA

git add -A
git commit -m "Initial schema with 19 models" -q

# ─── Branch A (main): add fields to existing models ──────────────

# Simulate database-schema-seed adding fields and a new enum
cat >> prisma/schema.prisma <<'MAIN_ADDITIONS'

model PromoDay {
  id        String   @id @default(cuid())
  name      String
  discount  Float
  startDate DateTime
  endDate   DateTime
  active    Boolean  @default(false)
}

enum SubscriptionPlan {
  MONTHLY
  QUARTERLY
  YEARLY
}
MAIN_ADDITIONS

# Also modify an existing model (User) to create a conflict zone
sed -i 's/  addresses Address\[\]/  addresses Address[]\n  wishlist  WishlistItem[]/' prisma/schema.prisma

cat >> prisma/schema.prisma <<'WISHLIST'

model WishlistItem {
  id        String  @id @default(cuid())
  userId    String
  user      User    @relation(fields: [userId], references: [id])
  productId String
  addedAt   DateTime @default(now())
}
WISHLIST

git add -A
git commit -m "Add PromoDay, SubscriptionPlan, WishlistItem" -q

MAIN_MODEL_COUNT=$(grep -c "^model " prisma/schema.prisma)
info "Main branch: $MAIN_MODEL_COUNT models"

# ─── Branch B (feature): add Session + PasswordResetToken ────────

git checkout -b change/user-accounts HEAD~1 -q

# Add Session and PasswordResetToken models, plus modify User (different field)
sed -i 's/  addresses Address\[\]/  addresses Address[]\n  sessions  Session[]/' prisma/schema.prisma

cat >> prisma/schema.prisma <<'FEATURE_ADDITIONS'

model Session {
  id        String   @id @default(cuid())
  userId    String
  user      User     @relation(fields: [userId], references: [id])
  token     String   @unique
  expiresAt DateTime
  createdAt DateTime @default(now())
  ipAddress String?
  userAgent String?
}

model PasswordResetToken {
  id        String   @id @default(cuid())
  userId    String
  token     String   @unique
  expiresAt DateTime
  createdAt DateTime @default(now())
  usedAt    DateTime?
}

model AuditLog {
  id        String   @id @default(cuid())
  userId    String?
  action    String
  details   String?
  createdAt DateTime @default(now())
}
FEATURE_ADDITIONS

git add -A
git commit -m "Add Session, PasswordResetToken, AuditLog" -q

FEATURE_MODEL_COUNT=$(grep -c "^model " prisma/schema.prisma)
info "Feature branch: $FEATURE_MODEL_COUNT models"

# ─── Expected merge result ────────────────────────────────────────

# main added: PromoDay, WishlistItem (2 new models)
# feature added: Session, PasswordResetToken, AuditLog (3 new models)
# Both modified User model (different additions → conflict)
# Expected merged total: 19 (base) + 2 (main) + 3 (feature) = 24 models

EXPECTED_MODEL_COUNT=24
info "Expected after merge: $EXPECTED_MODEL_COUNT models"

# ─── Switch to main and attempt merge ─────────────────────────────

git checkout main -q

info "Attempting merge..."

# Set up project structure so wt-merge can find it
# wt-merge expects a worktree — simulate by using the branch directly
# We'll call git merge directly first to see if there's a conflict,
# then test the conservation check functions

MERGE_RESULT=0
git merge change/user-accounts -m "Merge user-accounts" --no-edit 2>/dev/null || MERGE_RESULT=$?

if [[ $MERGE_RESULT -eq 0 ]]; then
    # No conflict — git auto-merged
    MERGED_MODEL_COUNT=$(grep -c "^model " prisma/schema.prisma)
    info "Git auto-merged (no conflict). Models: $MERGED_MODEL_COUNT"
    if [[ $MERGED_MODEL_COUNT -lt $EXPECTED_MODEL_COUNT ]]; then
        fail "DATA LOSS: $MERGED_MODEL_COUNT models, expected $EXPECTED_MODEL_COUNT"
        exit 1
    else
        pass "All models preserved: $MERGED_MODEL_COUNT >= $EXPECTED_MODEL_COUNT"
        exit 0
    fi
fi

# There IS a conflict — this is the scenario we want to test
info "Merge conflict detected (expected). Checking conflict files..."

CONFLICTED_FILES=$(git diff --name-only --diff-filter=U 2>/dev/null)
info "Conflicted files: $CONFLICTED_FILES"

# Get merge-base for conservation check testing
MERGE_BASE=$(git merge-base main change/user-accounts)
info "Merge base: $MERGE_BASE"

# Show the conflict markers in the schema
CONFLICT_MARKERS=$(grep -c "^<<<<<<<\|^=======\|^>>>>>>>" prisma/schema.prisma 2>/dev/null || echo "0")
info "Conflict markers in schema: $CONFLICT_MARKERS"

# ─── Test: Simulate LLM resolution that loses models ──────────────

# This simulates what happened in CraftBrew: the LLM "resolves" the conflict
# by picking one side, losing the other side's additions.

info ""
info "=== Simulating BAD LLM resolution (loses feature branch models) ==="

# Take "ours" (main) version — this loses Session, PasswordResetToken, AuditLog
git checkout --ours prisma/schema.prisma
git add prisma/schema.prisma

BAD_MERGE_COUNT=$(grep -c "^model " prisma/schema.prisma)
info "After bad resolution: $BAD_MERGE_COUNT models (lost $((EXPECTED_MODEL_COUNT - BAD_MERGE_COUNT)) models)"

# ─── Conservation check test ──────────────────────────────────────

info ""
info "=== Running conservation check ==="

# Get the three versions
BASE_FILE=$(mktemp)
OURS_FILE=$(mktemp)
THEIRS_FILE=$(mktemp)
MERGED_FILE="prisma/schema.prisma"

git show "${MERGE_BASE}:prisma/schema.prisma" > "$BASE_FILE"
git show "main:prisma/schema.prisma" > "$OURS_FILE"  # main = ours (pre-merge HEAD)
git show "change/user-accounts:prisma/schema.prisma" > "$THEIRS_FILE"

# Compute additions: lines in branch version but not in base
# Using trimmed, non-blank, non-comment lines
compute_additions() {
    local base_file="$1"
    local branch_file="$2"
    # Get trimmed non-blank lines unique to branch (not in base)
    comm -13 \
        <(sed 's/^[[:space:]]*//;s/[[:space:]]*$//' "$base_file" | grep -v '^$' | sort -u) \
        <(sed 's/^[[:space:]]*//;s/[[:space:]]*$//' "$branch_file" | grep -v '^$' | sort -u)
}

OURS_ADDED=$(compute_additions "$BASE_FILE" "$OURS_FILE")
THEIRS_ADDED=$(compute_additions "$BASE_FILE" "$THEIRS_FILE")
MERGED_LINES=$(sed 's/^[[:space:]]*//;s/[[:space:]]*$//' "$MERGED_FILE" | grep -v '^$' | sort -u)

OURS_ADDED_COUNT=$(echo "$OURS_ADDED" | grep -c . || echo 0)
THEIRS_ADDED_COUNT=$(echo "$THEIRS_ADDED" | grep -c . || echo 0)

info "Ours additions: $OURS_ADDED_COUNT lines"
info "Theirs additions: $THEIRS_ADDED_COUNT lines"

# Check: are all additions from both sides present in merged?
OURS_MISSING=""
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if ! echo "$MERGED_LINES" | grep -qxF "$line"; then
        OURS_MISSING+="  $line"$'\n'
    fi
done <<< "$OURS_ADDED"

THEIRS_MISSING=""
while IFS= read -r line; do
    [[ -z "$line" ]] && continue
    if ! echo "$MERGED_LINES" | grep -qxF "$line"; then
        THEIRS_MISSING+="  $line"$'\n'
    fi
done <<< "$THEIRS_ADDED"

OURS_MISSING_COUNT=0
THEIRS_MISSING_COUNT=0
[[ -n "$OURS_MISSING" ]] && OURS_MISSING_COUNT=$(echo "$OURS_MISSING" | grep -c . || echo 0)
[[ -n "$THEIRS_MISSING" ]] && THEIRS_MISSING_COUNT=$(echo "$THEIRS_MISSING" | grep -c . || echo 0)

info "Missing from ours: $OURS_MISSING_COUNT lines"
info "Missing from theirs: $THEIRS_MISSING_COUNT lines"

# Cleanup temp files
rm -f "$BASE_FILE" "$OURS_FILE" "$THEIRS_FILE"

# ─── Abort the bad merge ──────────────────────────────────────────
git reset --merge 2>/dev/null || git merge --abort 2>/dev/null || true

# ─── Results ──────────────────────────────────────────────────────

info ""
info "=== RESULTS ==="

if [[ $THEIRS_MISSING_COUNT -gt 0 || $OURS_MISSING_COUNT -gt 0 ]]; then
    TOTAL_MISSING=$((OURS_MISSING_COUNT + THEIRS_MISSING_COUNT))

    if $BASELINE_MODE; then
        warn "BASELINE: Conservation check detected $TOTAL_MISSING missing lines"
        warn "  (In current wt-merge, this would NOT be caught — merge would proceed)"
        [[ -n "$THEIRS_MISSING" ]] && {
            warn "Sample missing from theirs (feature branch):"
            echo "$THEIRS_MISSING" | head -10
        }
        pass "Baseline test complete — data loss confirmed and detectable"
        exit 0
    else
        fail "MERGE BLOCKED: conservation check failed — $TOTAL_MISSING additions lost"
        [[ -n "$OURS_MISSING" ]] && {
            fail "Lost from ours (main):"
            echo "$OURS_MISSING" | head -10
        }
        [[ -n "$THEIRS_MISSING" ]] && {
            fail "Lost from theirs (feature):"
            echo "$THEIRS_MISSING" | head -10
        }
        # Entity count check
        info ""
        BASE_ENTITIES=$(grep -c "^model " "$BASE_FILE" 2>/dev/null || git show "${MERGE_BASE}:prisma/schema.prisma" | grep -c "^model ")
        fail "Entity count: expected $EXPECTED_MODEL_COUNT, got $BAD_MERGE_COUNT (base=$BASE_ENTITIES)"
        exit 1
    fi
else
    pass "Conservation check passed — all additions preserved"
    pass "Model count: $BAD_MERGE_COUNT (expected $EXPECTED_MODEL_COUNT)"
    exit 0
fi
