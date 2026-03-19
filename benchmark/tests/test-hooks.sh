#!/usr/bin/env bash
# test-hooks.sh - Isolated tests for memory hook fixes
#
# Uses a temporary shodh-memory storage directory (not production).
# Tests: auto_ingest, change: tags, code-map generation, convention extraction.
#
# Usage:
#   bash benchmark/tests/test-hooks.sh          # Run isolated hook tests
#   bash benchmark/tests/test-hooks.sh --smoke   # Run single-change smoke test (C01)

set -uo pipefail

PASS=0; FAIL=0; SKIP=0
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

check() {
    local name="$1" condition="$2"
    if eval "$condition"; then
        echo "  PASS: $name"; ((PASS++))
    else
        echo "  FAIL: $name"; ((FAIL++))
    fi
}

skip() {
    echo "  SKIP: $1"; ((SKIP++))
}

# Ensure set-memory is available
if ! command -v set-memory &>/dev/null; then
    echo "ERROR: set-memory not found on PATH"
    exit 1
fi

if ! set-memory health &>/dev/null; then
    echo "ERROR: set-memory health check failed"
    exit 1
fi

# --- Smoke test mode ---
if [[ "${1:-}" == "--smoke" ]]; then
    echo "=== Smoke Test Mode ==="
    echo "NOTE: Smoke test requires a CraftBazaar worktree with C01 completed."
    echo "This test validates memory quality after a real change implementation."
    echo ""
    echo "Checking memory store for recent C01 artifacts..."

    # Check for product-catalog memories
    PC_MEMORIES=$(set-memory recall "product-catalog" --limit 10 --mode hybrid 2>/dev/null)
    PC_COUNT=$(echo "$PC_MEMORIES" | python3 -c "import sys,json; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    check "At least 1 memory about product-catalog" '[ "$PC_COUNT" -ge 1 ]'

    # Check for change: tag
    TAGGED=$(echo "$PC_MEMORIES" | python3 -c "
import sys, json
mems = json.load(sys.stdin)
tagged = [m for m in mems if any('change:product-catalog' in t for t in m.get('tags', []))]
print(len(tagged))
" 2>/dev/null || echo 0)
    check "At least 1 memory with change:product-catalog tag" '[ "$TAGGED" -ge 1 ]'

    # Check for zero Conversation noise
    CONV_COUNT=$(set-memory list 2>/dev/null | python3 -c "
import sys, json
mems = json.load(sys.stdin)
conv = [m for m in mems if m.get('experience_type') == 'Conversation']
print(len(conv))
" 2>/dev/null || echo 0)
    check "Zero Conversation type memories (proactive-context noise)" '[ "$CONV_COUNT" -eq 0 ]'

    # Check for code-map
    CODEMAP=$(set-memory recall "product-catalog code map" --limit 3 --mode semantic 2>/dev/null | python3 -c "
import sys, json
mems = json.load(sys.stdin)
cm = [m for m in mems if any('code-map' in t for t in m.get('tags', []))]
print(len(cm))
" 2>/dev/null || echo 0)
    check "Code-map memory exists for product-catalog" '[ "$CODEMAP" -ge 1 ]'

    # Check noise rate via stats
    NOISE=$(set-memory stats --json 2>/dev/null | python3 -c "
import sys, json
d = json.load(sys.stdin)
print(d.get('noise_ratio', 1.0))
" 2>/dev/null || echo "1.0")
    NOISE_OK=$(python3 -c "print('yes' if float('$NOISE') < 0.20 else 'no')" 2>/dev/null)
    check "Memory noise rate < 20% (actual: $NOISE)" '[ "$NOISE_OK" = "yes" ]'

    echo ""
    echo "Smoke test results: $PASS passed, $FAIL failed, $SKIP skipped"
    exit $((FAIL > 0 ? 1 : 0))
fi

# --- Isolated hook tests ---
echo "=== Memory Hook Tests (isolated) ==="
echo ""

# Create temp storage
TEMP_STORAGE=$(mktemp -d)
trap "rm -rf $TEMP_STORAGE" EXIT

echo "Using temp storage: $TEMP_STORAGE"
echo ""

# Test 1: auto_ingest=False
echo "--- Test 1: auto_ingest=False ---"

# Run proactive with temp storage
_SHODH_STORAGE="$TEMP_STORAGE" \
python3 -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
# First add a test memory so proactive has something to work with
m.remember('test memory for proactive', memory_type='Learning', tags=['test'])
# Now call proactive with auto_ingest=False
if hasattr(m, 'proactive_context'):
    raw = m.proactive_context('Working on change: test-change', max_results=5, auto_ingest=False)
    results = raw.get('memories', []) if isinstance(raw, dict) else raw
    print(json.dumps({'proactive_returned': len(results)}, default=str))
else:
    print(json.dumps({'proactive_returned': 'N/A - no proactive_context method'}))
" 2>/dev/null || echo '{"error": "proactive call failed"}'

# Count Conversation memories in temp storage
CONV_IN_TEMP=$(_SHODH_STORAGE="$TEMP_STORAGE" python3 -c "
import sys; sys._shodh_star_shown = True
import json, os
from shodh_memory import Memory
m = Memory(storage_path=os.environ['_SHODH_STORAGE'])
mems = m.list_memories() if hasattr(m, 'list_memories') else []
conv = [x for x in mems if x.get('experience_type') == 'Conversation']
print(len(conv))
" 2>/dev/null || echo "-1")
check "No Conversation memories created by proactive (count: $CONV_IN_TEMP)" '[ "$CONV_IN_TEMP" -eq 0 ]'

echo ""

# Test 2: change: tag in source code
echo "--- Test 2: change: tag propagation ---"
HOOK_FILE="$PROJECT_ROOT/bin/set-hook-memory-save"
HAS_CHANGE_TAG=$(grep -c 'change:\$first_change' "$HOOK_FILE" 2>/dev/null || echo 0)
check "set-hook-memory-save has change:\$first_change tag injection" '[ "$HAS_CHANGE_TAG" -ge 1 ]'

HAS_FIRST_CHANGE=$(grep -c 'first_change=' "$HOOK_FILE" 2>/dev/null || echo 0)
check "set-hook-memory-save extracts first_change variable" '[ "$HAS_FIRST_CHANGE" -ge 1 ]'

HAS_EMPTY_CHECK=$(grep -c 'first_change.*""' "$HOOK_FILE" 2>/dev/null || echo 0)
# Alternative pattern
HAS_EMPTY_CHECK2=$(grep -c '-n.*first_change' "$HOOK_FILE" 2>/dev/null || echo 0)
check "set-hook-memory-save has empty change name guard" '[ "$((HAS_EMPTY_CHECK + HAS_EMPTY_CHECK2))" -ge 1 ]'

echo ""

# Test 3: Convention extraction in prompt
echo "--- Test 3: Convention extraction ---"
HAS_CONVENTION_PROMPT=$(grep -c 'Convention|' "$HOOK_FILE" 2>/dev/null || echo 0)
check "LLM prompt contains Convention extraction format" '[ "$HAS_CONVENTION_PROMPT" -ge 1 ]'

HAS_CONVENTION_PARSE=$(grep -c '"Convention"' "$HOOK_FILE" 2>/dev/null || echo 0)
check "Convention type parsing exists in hook" '[ "$HAS_CONVENTION_PARSE" -ge 1 ]'

HAS_CONV_CAP=$(grep -c 'conv_count' "$HOOK_FILE" 2>/dev/null || echo 0)
check "Convention count cap exists (conv_count)" '[ "$HAS_CONV_CAP" -ge 1 ]'

echo ""

# Test 4: Code-map safety net
echo "--- Test 4: Code-map improvements ---"
HAS_ALL_HASHES=$(grep -c 'all_hashes' "$HOOK_FILE" 2>/dev/null || echo 0)
check "Code-map aggregates all commits (all_hashes)" '[ "$HAS_ALL_HASHES" -ge 1 ]'

HAS_SORT_U=$(grep -c 'sort -u' "$HOOK_FILE" 2>/dev/null || echo 0)
check "Code-map deduplicates files (sort -u)" '[ "$HAS_SORT_U" -ge 1 ]'

HAS_OPENSPEC_FALLBACK=$(grep -c 'openspec/changes' "$HOOK_FILE" 2>/dev/null || echo 0)
check "Code-map has openspec/changes fallback for change name" '[ "$HAS_OPENSPEC_FALLBACK" -ge 1 ]'

echo ""

# Test 5: auto_ingest in set-memory
echo "--- Test 5: set-memory proactive ---"
WM_FILE="$PROJECT_ROOT/bin/set-memory"
HAS_AUTO_INGEST=$(grep -c 'auto_ingest=False' "$WM_FILE" 2>/dev/null || echo 0)
check "set-memory proactive passes auto_ingest=False" '[ "$HAS_AUTO_INGEST" -ge 1 ]'

echo ""
echo "=== Hook Test Results ==="
echo "Results: $PASS passed, $FAIL failed, $SKIP skipped"
exit $((FAIL > 0 ? 1 : 0))
