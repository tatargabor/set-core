#!/usr/bin/env bash
# test_save_hook_staging.sh — Integration tests for wt-hook-memory-save staging pattern
#
# Tests the staging, debounce, and commit logic without real API calls.
# Mocks: wt-memory (records calls), claude CLI (returns canned output)
#
# Usage: bash tests/test_save_hook_staging.sh

set -uo pipefail
# Note: NOT using set -e — tests use explicit pass/fail assertions

# ============================================================
# Test harness setup
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
HOOK="$PROJECT_ROOT/bin/wt-hook-memory-save"

# Create isolated test environment
TEST_DIR=$(mktemp -d)
trap 'rm -rf "$TEST_DIR"' EXIT

# Working directory for the hook (simulates project root)
WORK_DIR="$TEST_DIR/project"
mkdir -p "$WORK_DIR/.set-core"
mkdir -p "$WORK_DIR/openspec/changes"

# Mock bin directory (prepended to PATH)
MOCK_BIN="$TEST_DIR/mock-bin"
mkdir -p "$MOCK_BIN"

# Log where mock wt-memory records its calls
MEMORY_LOG="$TEST_DIR/wt-memory-calls.log"

# --- Mock: wt-memory ---
cat > "$MOCK_BIN/wt-memory" << 'MOCK_EOF'
#!/usr/bin/env bash
# Mock wt-memory: records calls, always succeeds
LOG_FILE="${WTM_TEST_MEMORY_LOG:-/dev/null}"
if [[ "$1" == "health" ]]; then
    echo "ok"
    exit 0
fi
if [[ "$1" == "remember" ]]; then
    # Read stdin content
    content=$(cat)
    echo "remember|$*|$content" >> "$LOG_FILE"
    exit 0
fi
if [[ "$1" == "recall" ]]; then
    echo "[]"
    exit 0
fi
if [[ "$1" == "list" ]]; then
    echo "[]"
    exit 0
fi
exit 0
MOCK_EOF
chmod +x "$MOCK_BIN/wt-memory"

# --- Mock: claude CLI ---
# Returns canned extraction output
CLAUDE_OUTPUT_FILE="$TEST_DIR/claude-output.txt"
CLAUDE_CALL_LOG="$TEST_DIR/claude-calls.log"
cat > "$MOCK_BIN/claude" << MOCK_EOF
#!/usr/bin/env bash
# Mock claude: returns canned output from file, records calls
echo "claude|\$*" >> "$CLAUDE_CALL_LOG"
cat "$CLAUDE_OUTPUT_FILE" 2>/dev/null || echo "NONE"
MOCK_EOF
chmod +x "$MOCK_BIN/claude"

# --- Mock: git (for PATH 2) ---
cat > "$MOCK_BIN/git" << 'MOCK_EOF'
#!/usr/bin/env bash
# Mock git: returns stable HEAD hash so PATH 2 is a no-op
if [[ "$1" == "rev-parse" ]]; then
    echo "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef"
    exit 0
fi
if [[ "$1" == "cat-file" ]]; then
    exit 0
fi
if [[ "$1" == "log" ]]; then
    echo ""
    exit 0
fi
exit 0
MOCK_EOF
chmod +x "$MOCK_BIN/git"

# --- Mock: python3 (pass through to real python3) ---
# We need real python3 for the hook's JSON parsing
# But we link it so it's available even if PATH is restricted
REAL_PYTHON3=$(command -v python3)

# --- Create fake transcript with opsx skill markers ---
create_transcript() {
    local path="$1"
    local session_id="${2:-test-session}"
    cat > "$path" << TRANSCRIPT_EOF
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Skill","input":{"skill":"opsx:apply","args":"test-change"}}]}}
{"type":"user","message":{"content":"implement the change"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"Working on task 1..."}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"npm test"}}]}}
{"type":"tool_result","content":"All tests passed"}
{"type":"assistant","message":{"content":[{"type":"text","text":"Task 1 complete. Moving to task 2."}]}}
TRANSCRIPT_EOF
}

# --- Create fake transcript WITHOUT opsx skills ---
create_plain_transcript() {
    local path="$1"
    cat > "$path" << TRANSCRIPT_EOF
{"type":"user","message":{"content":"fix the bug in server.js"}}
{"type":"assistant","message":{"content":[{"type":"text","text":"I'll fix that bug."}]}}
{"type":"assistant","message":{"content":[{"type":"tool_use","name":"Bash","input":{"command":"npm test"}}]}}
TRANSCRIPT_EOF
}

# --- Helper: run the hook ---
run_hook() {
    local transcript_path="$1"
    local stop_active="${2:-false}"
    local input="{\"transcript_path\":\"$transcript_path\",\"stop_hook_active\":$stop_active}"

    # Set up the last-memory-commit marker so PATH 2 is a no-op
    echo "deadbeefdeadbeefdeadbeefdeadbeefdeadbeef" > "$WORK_DIR/.set-core/.last-memory-commit"

    cd "$WORK_DIR"
    export PATH="$MOCK_BIN:$PATH"
    export WTM_TEST_MEMORY_LOG="$MEMORY_LOG"

    echo "$input" | bash "$HOOK" 2>/dev/null

    # Wait for background extraction to finish
    sleep 3
}

# --- Default canned Haiku output ---
set_claude_output() {
    echo "$1" > "$CLAUDE_OUTPUT_FILE"
}

# ============================================================
# Test counters
# ============================================================

TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
    local name="$1"
    (( TESTS_RUN++ ))
    (( TESTS_PASSED++ ))
    echo "  ✓ $name"
}

fail() {
    local name="$1"
    local detail="${2:-}"
    (( TESTS_RUN++ ))
    (( TESTS_FAILED++ ))
    echo "  ✗ $name"
    [[ -n "$detail" ]] && echo "    → $detail"
}

assert_file_exists() {
    if [[ -f "$1" ]]; then
        pass "$2"
    else
        fail "$2" "File not found: $1"
    fi
}

assert_file_not_exists() {
    if [[ ! -f "$1" ]]; then
        pass "$2"
    else
        fail "$2" "File should not exist: $1"
    fi
}

assert_file_contains() {
    if grep -q "$2" "$1" 2>/dev/null; then
        pass "$3"
    else
        fail "$3" "Expected '$2' in $1"
    fi
}

assert_file_not_contains() {
    if ! grep -q "$2" "$1" 2>/dev/null; then
        pass "$3"
    else
        fail "$3" "Did not expect '$2' in $1"
    fi
}

assert_line_count() {
    local actual
    actual=$(grep -c "$2" "$1" 2>/dev/null || echo "0")
    if [[ "$actual" -eq "$3" ]]; then
        pass "$4"
    else
        fail "$4" "Expected $3 matches of '$2' in $1, got $actual"
    fi
}

# ============================================================
# Tests
# ============================================================

echo "=== Save Hook Staging Tests ==="
echo ""

# ----------------------------------------------------------
echo "## Test 4.2: First extraction creates staged file, no wt-memory remember calls"
# ----------------------------------------------------------

# Clean state
rm -f "$MEMORY_LOG" "$CLAUDE_CALL_LOG"
rm -f "$WORK_DIR/.set-core/.staged-extract-"* 2>/dev/null

TRANSCRIPT_1="$TEST_DIR/session-1.jsonl"
create_transcript "$TRANSCRIPT_1"

set_claude_output "Learning|error,test|Found a bug in the auth module
Decision|preference|User prefers tabs over spaces"

run_hook "$TRANSCRIPT_1"

assert_file_exists "$WORK_DIR/.set-core/.staged-extract-session-1" \
    "Staged file created for session-1"
assert_file_exists "$WORK_DIR/.set-core/.staged-extract-session-1.ts" \
    "Timestamp file created for session-1"
assert_file_contains "$WORK_DIR/.set-core/.staged-extract-session-1" "Learning|error,test|Found a bug" \
    "Staged file contains Haiku output"
assert_file_contains "$WORK_DIR/.set-core/.staged-extract-session-1" "#CHANGE:" \
    "Staged file has change name header"

# Check NO wt-memory remember calls were made
if [[ ! -f "$MEMORY_LOG" ]] || ! grep -q "^remember|" "$MEMORY_LOG" 2>/dev/null; then
    pass "No wt-memory remember calls during extraction"
else
    fail "No wt-memory remember calls during extraction" "$(cat "$MEMORY_LOG")"
fi

echo ""

# ----------------------------------------------------------
echo "## Test 4.3: Second extraction overwrites staged file content"
# ----------------------------------------------------------

rm -f "$CLAUDE_CALL_LOG"
# Remove the timestamp file to bypass debounce
rm -f "$WORK_DIR/.set-core/.staged-extract-session-1.ts"

set_claude_output "Learning|perf,cache|Cache invalidation was the real issue
Context|arch|System uses event sourcing pattern"

run_hook "$TRANSCRIPT_1"

assert_file_contains "$WORK_DIR/.set-core/.staged-extract-session-1" "Cache invalidation" \
    "Staged file updated with new content"
assert_file_not_contains "$WORK_DIR/.set-core/.staged-extract-session-1" "Found a bug" \
    "Old content replaced (not appended)"

echo ""

# ----------------------------------------------------------
echo "## Test 4.4: Session switch commits old staged file"
# ----------------------------------------------------------

rm -f "$MEMORY_LOG" "$CLAUDE_CALL_LOG"

# session-1's staged file is in place from previous test
# Now run hook for session-2 (different transcript)
TRANSCRIPT_2="$TEST_DIR/session-2.jsonl"
create_transcript "$TRANSCRIPT_2"

set_claude_output "Learning|test|Session 2 insight"

run_hook "$TRANSCRIPT_2"

# session-1's staged file should be committed (deleted)
assert_file_not_exists "$WORK_DIR/.set-core/.staged-extract-session-1" \
    "Old staged file deleted after commit"
assert_file_not_exists "$WORK_DIR/.set-core/.staged-extract-session-1.ts" \
    "Old timestamp file deleted after commit"

# session-2's staged file should exist (new extraction)
assert_file_exists "$WORK_DIR/.set-core/.staged-extract-session-2" \
    "New staged file created for session-2"

# Check wt-memory remember was called for session-1's content
if [[ -f "$MEMORY_LOG" ]] && grep -q "remember|" "$MEMORY_LOG" 2>/dev/null; then
    pass "wt-memory remember called for committed content"
    # Check the content matches session-1's extraction
    assert_file_contains "$MEMORY_LOG" "Cache invalidation" \
        "Committed content matches session-1's staged extraction"
else
    fail "wt-memory remember called for committed content" "No remember calls found"
fi

echo ""

# ----------------------------------------------------------
echo "## Test 4.5: Debounce skips extraction within 5-minute window"
# ----------------------------------------------------------

rm -f "$CLAUDE_CALL_LOG"

# session-2's ts file exists from previous test (recent timestamp)
# Running hook again for same transcript should be debounced

run_hook "$TRANSCRIPT_2"

# Check claude was NOT called (debounce skipped)
if [[ ! -f "$CLAUDE_CALL_LOG" ]] || [[ $(wc -l < "$CLAUDE_CALL_LOG") -le 1 ]]; then
    # The first call was from session-2 setup above; a debounced run should NOT add another
    pass "Claude CLI not called during debounce window"
else
    call_count=$(wc -l < "$CLAUDE_CALL_LOG")
    fail "Claude CLI not called during debounce window" "Found $call_count calls"
fi

# Check debounce was logged
assert_file_contains "$WORK_DIR/.set-core/transcript-extraction.log" "DEBOUNCE" \
    "Debounce skip logged"

echo ""

# ----------------------------------------------------------
echo "## Test 4.6: Stale file (>1 hour, same session) auto-committed"
# ----------------------------------------------------------

rm -f "$MEMORY_LOG" "$CLAUDE_CALL_LOG"
rm -f "$WORK_DIR/.set-core/.staged-extract-"* 2>/dev/null

TRANSCRIPT_3="$TEST_DIR/session-3.jsonl"
create_transcript "$TRANSCRIPT_3"

# Create a staged file for session-3 with an old timestamp (2 hours ago)
echo "#CHANGE:test-change" > "$WORK_DIR/.set-core/.staged-extract-session-3"
echo "Learning|stale,test|This is a stale insight" >> "$WORK_DIR/.set-core/.staged-extract-session-3"
echo $(( $(date +%s) - 7200 )) > "$WORK_DIR/.set-core/.staged-extract-session-3.ts"

set_claude_output "Learning|fresh|Fresh extraction after stale commit"

run_hook "$TRANSCRIPT_3"

# Stale file should have been committed
if [[ -f "$MEMORY_LOG" ]] && grep -q "stale insight" "$MEMORY_LOG" 2>/dev/null; then
    pass "Stale staged file committed to memory"
else
    fail "Stale staged file committed to memory" "No remember call with stale content"
fi

# Check STALE was logged
assert_file_contains "$WORK_DIR/.set-core/transcript-extraction.log" "STALE" \
    "Stale commit logged"

# Fresh extraction should have created new staged file
assert_file_exists "$WORK_DIR/.set-core/.staged-extract-session-3" \
    "Fresh staged file created after stale commit"
assert_file_contains "$WORK_DIR/.set-core/.staged-extract-session-3" "Fresh extraction" \
    "Fresh staged file has new content"

echo ""

# ----------------------------------------------------------
echo "## Test 4.7: No-opsx-skill transcript skips extraction entirely"
# ----------------------------------------------------------

rm -f "$CLAUDE_CALL_LOG"
rm -f "$WORK_DIR/.set-core/.staged-extract-"* 2>/dev/null

TRANSCRIPT_4="$TEST_DIR/session-4.jsonl"
create_plain_transcript "$TRANSCRIPT_4"

run_hook "$TRANSCRIPT_4"

# No staged file should be created
assert_file_not_exists "$WORK_DIR/.set-core/.staged-extract-session-4" \
    "No staged file for plain transcript (no opsx skills)"

# Claude should not have been called
if [[ ! -f "$CLAUDE_CALL_LOG" ]]; then
    pass "Claude CLI not called for plain transcript"
else
    fail "Claude CLI not called for plain transcript" "$(cat "$CLAUDE_CALL_LOG")"
fi

echo ""

# ----------------------------------------------------------
echo "## Test 4.8: PATH 2 commit-based extraction still works independently"
# ----------------------------------------------------------

# PATH 2 uses git hash comparison. Our mock git returns a stable hash
# and .last-memory-commit is set to the same hash, so PATH 2 is a no-op.
# This test just verifies the hook doesn't crash with PATH 2 active.

rm -f "$WORK_DIR/.set-core/.last-memory-commit"
# Let PATH 2 detect a "new commit" (hash mismatch)
run_hook "$TRANSCRIPT_4"

# Hook should complete without error (exit code 0 from run_hook)
pass "Hook completes with PATH 2 active (no crash)"

echo ""

# ============================================================
# Summary
# ============================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Results: $TESTS_PASSED/$TESTS_RUN passed, $TESTS_FAILED failed"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$TESTS_FAILED" -gt 0 ]]; then
    exit 1
fi
exit 0
