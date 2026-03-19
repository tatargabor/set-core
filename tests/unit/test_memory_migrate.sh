#!/usr/bin/env bash
# Unit tests for lib/memory/migrate.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source dependencies
source "$SCRIPT_DIR/../../bin/set-common.sh"
_wt_memory_bin_dir="$SCRIPT_DIR/../../bin"
source "$_wt_memory_bin_dir/../lib/memory/migrate.sh"

test_migrations_read_missing() {
    local tmpdir
    tmpdir=$(mktemp -d)
    local result
    result=$(migrations_read "$tmpdir/.migrations")
    assert_equals '{"applied":[]}' "$result" "missing file returns empty applied"
    rm -rf "$tmpdir"
}

test_migration_is_applied_false() {
    local tmpdir
    tmpdir=$(mktemp -d)
    echo '{"applied":[]}' > "$tmpdir/.migrations"
    set +e
    migration_is_applied "$tmpdir/.migrations" "001_branch_tags"
    local rc=$?
    set -e
    # Should return 1 (not applied)
    assert_equals "1" "$rc" "unapplied migration returns 1"
    rm -rf "$tmpdir"
}

test_migration_mark_and_check() {
    local tmpdir
    tmpdir=$(mktemp -d)
    echo '{"applied":[]}' > "$tmpdir/.migrations"
    migration_mark_applied "$tmpdir/.migrations" "001_test"
    migration_is_applied "$tmpdir/.migrations" "001_test"
    local rc=$?
    assert_equals "0" "$rc" "marked migration is applied"
    rm -rf "$tmpdir"
}

run_tests
