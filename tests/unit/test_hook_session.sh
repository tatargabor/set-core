#!/usr/bin/env bash
# Unit tests for lib/hooks/session.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Set up minimal environment for hooks
export WT_TOOLS_ROOT="$SCRIPT_DIR/../.."
export SESSION_ID="test-session-$$"
SESSION_CACHE="/tmp/set-memory-session-${SESSION_ID}.json"

# Source dependencies
source "$WT_TOOLS_ROOT/lib/hooks/util.sh"
source "$WT_TOOLS_ROOT/lib/hooks/session.sh"

# Cleanup
trap 'rm -f "$SESSION_CACHE"' EXIT

test_make_dedup_key() {
    local key1 key2
    key1=$(make_dedup_key "PostToolUse" "Read" "some query")
    key2=$(make_dedup_key "PostToolUse" "Read" "different query")
    # Same inputs should give same key
    local key1b
    key1b=$(make_dedup_key "PostToolUse" "Read" "some query")
    assert_equals "$key1" "$key1b" "deterministic key"
    # Different inputs should give different key
    if [[ "$key1" == "$key2" ]]; then
        echo "    FAIL: different inputs gave same key"
        return 1
    fi
}

test_gen_context_id_uniqueness() {
    # Initialize session cache
    echo '{}' > "$SESSION_CACHE"
    local id1 id2
    id1=$(_gen_context_id)
    id2=$(_gen_context_id)
    # IDs should be 4-char hex
    assert_equals "4" "${#id1}" "id1 is 4 chars"
    assert_equals "4" "${#id2}" "id2 is 4 chars"
    # Should be different
    if [[ "$id1" == "$id2" ]]; then
        echo "    FAIL: generated duplicate IDs"
        return 1
    fi
}

run_tests
