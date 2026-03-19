#!/usr/bin/env bash
# Unit tests for lib/memory/sync.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source dependencies
source "$SCRIPT_DIR/../../bin/set-common.sh"
# Source sync module (needs infra from set-memory)
_wt_memory_bin_dir="$SCRIPT_DIR/../../bin"
source "$_wt_memory_bin_dir/../lib/memory/sync.sh"

test_sync_resolve_identity() {
    local identity
    identity=$(sync_resolve_identity)
    # Should return user/hostname format
    assert_contains "$identity" "/" "identity has / separator"
}

test_sync_get_state_missing() {
    local tmpdir
    tmpdir=$(mktemp -d)
    local result
    result=$(sync_get_state "$tmpdir" "last_push")
    assert_equals "" "$result" "missing state returns empty"
    rm -rf "$tmpdir"
}

test_sync_update_and_get_state() {
    local tmpdir
    tmpdir=$(mktemp -d)
    sync_update_state "$tmpdir" "test_key" "test_value"
    local result
    result=$(sync_get_state "$tmpdir" "test_key")
    assert_equals "test_value" "$result" "update then get returns value"
    rm -rf "$tmpdir"
}

run_tests
