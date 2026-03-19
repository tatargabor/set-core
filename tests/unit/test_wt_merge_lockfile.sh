#!/usr/bin/env bash
# Unit tests for wt-merge lockfile helpers and runtime cleanup
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

WT_TOOLS_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Source wt-common.sh directly (provides info/warn/error/success helpers)
source "$WT_TOOLS_ROOT/bin/wt-common.sh"

# Extract function definitions from wt-merge without running main()
# Skip the first line (shebang), the SCRIPT_DIR/source lines, and main()
_WM_FUNCS=$(awk '
    /^SCRIPT_DIR=/ { next }
    /^source.*wt-common/ { next }
    /^main\(\) \{$/,0 { exit }
    { print }
' "$WT_TOOLS_ROOT/bin/wt-merge")
eval "$_WM_FUNCS"

# ─── is_lockfile tests ──────────────────────────────────────────────

test_is_lockfile_pnpm() {
    is_lockfile "pnpm-lock.yaml"
    assert_equals "pnpm" "$LOCKFILE_PM" "pnpm-lock.yaml should map to pnpm"
}

test_is_lockfile_yarn() {
    is_lockfile "yarn.lock"
    assert_equals "yarn" "$LOCKFILE_PM" "yarn.lock should map to yarn"
}

test_is_lockfile_npm() {
    is_lockfile "package-lock.json"
    assert_equals "npm" "$LOCKFILE_PM" "package-lock.json should map to npm"
}

test_is_lockfile_with_path() {
    is_lockfile "some/nested/pnpm-lock.yaml"
    assert_equals "pnpm" "$LOCKFILE_PM" "nested path should extract basename"
}

test_is_not_lockfile_tsbuildinfo() {
    local rc=0
    is_lockfile "tsconfig.tsbuildinfo" || rc=$?
    assert_equals "1" "$rc" "tsbuildinfo is not a lock file"
    assert_equals "" "$LOCKFILE_PM" "PM should be empty for non-lock files"
}

test_is_not_lockfile_dist() {
    local rc=0
    is_lockfile "dist/index.js" || rc=$?
    assert_equals "1" "$rc" "dist files are not lock files"
}

test_is_not_lockfile_package_json() {
    local rc=0
    is_lockfile "package.json" || rc=$?
    assert_equals "1" "$rc" "package.json is not a lock file"
}

# ─── regenerate_lockfile tests (mock install command) ────────────────

test_regenerate_lockfile_empty_pm() {
    local rc=0
    regenerate_lockfile "some.lock" "" 2>/dev/null || rc=$?
    assert_equals "1" "$rc" "empty PM should fail"
}

test_regenerate_lockfile_calls_install() {
    # Create a temp dir to work in
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git init --quiet
    touch pnpm-lock.yaml
    git add pnpm-lock.yaml
    git commit -m "init" --quiet

    # Mock pnpm install by creating a fake pnpm script
    local fake_bin="$tmpdir/.fake-bin"
    mkdir -p "$fake_bin"
    cat > "$fake_bin/pnpm" << 'FAKESCRIPT'
#!/bin/bash
# Fake pnpm — just touch the lock file to simulate install
echo "fake-lock-content" > pnpm-lock.yaml
exit 0
FAKESCRIPT
    chmod +x "$fake_bin/pnpm"

    PATH="$fake_bin:$PATH" regenerate_lockfile "pnpm-lock.yaml" "pnpm"
    local rc=$?

    # Verify success
    assert_equals "0" "$rc" "regenerate should succeed with mock install"

    # Verify the lock file was staged
    local staged
    staged=$(git diff --cached --name-only)
    assert_contains "$staged" "pnpm-lock.yaml" "lock file should be staged"

    cd /
    rm -rf "$tmpdir"
}

# ─── cleanup_runtime_files tests ────────────────────────────────────

test_cleanup_runtime_files_removes_tracked() {
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git init --quiet

    # Create and track runtime files
    mkdir -p .set-core/agents
    echo "commit-hash" > .set-core/.last-memory-commit
    echo "agent-data" > .set-core/agents/agent1.json
    git add .set-core/
    git commit -m "init with runtime files" --quiet

    # Verify they are tracked
    local tracked
    tracked=$(git ls-files .set-core/)
    assert_contains "$tracked" ".last-memory-commit" "file should be tracked before cleanup"

    cleanup_runtime_files "$tmpdir"

    # Verify removed from index
    tracked=$(git ls-files .set-core/.last-memory-commit 2>/dev/null || true)
    assert_equals "" "$tracked" ".last-memory-commit should be removed from index"

    # Verify .gitignore updated
    assert_file_exists "$tmpdir/.gitignore" ".gitignore should exist"
    local gitignore_content
    gitignore_content=$(cat "$tmpdir/.gitignore")
    assert_contains "$gitignore_content" ".set-core/.last-memory-commit" ".gitignore should have runtime pattern"
    assert_contains "$gitignore_content" ".set-core/agents/" ".gitignore should have agents pattern"
    assert_contains "$gitignore_content" ".set-core/orphan-detect/" ".gitignore should have orphan-detect pattern"

    cd /
    rm -rf "$tmpdir"
}

test_cleanup_runtime_files_noop_when_clean() {
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git init --quiet
    touch README.md
    git add README.md
    git commit -m "init" --quiet

    # Add all patterns to .gitignore already
    cat > .gitignore << 'EOF'
.set-core/.last-memory-commit
.set-core/agents/
.set-core/orphan-detect/
EOF
    git add .gitignore
    git commit -m "add gitignore" --quiet

    local rc=0
    cleanup_runtime_files "$tmpdir" || rc=$?
    assert_equals "1" "$rc" "should return 1 when nothing to clean"

    cd /
    rm -rf "$tmpdir"
}

test_cleanup_gitignore_no_duplicates() {
    local tmpdir
    tmpdir=$(mktemp -d)
    cd "$tmpdir"
    git init --quiet
    touch README.md
    git add README.md
    git commit -m "init" --quiet

    # Pre-populate .gitignore with one pattern
    echo ".set-core/.last-memory-commit" > .gitignore
    git add .gitignore
    git commit -m "partial gitignore" --quiet

    cleanup_runtime_files "$tmpdir"

    # Count occurrences of the pre-existing pattern
    local count
    count=$(grep -c ".set-core/.last-memory-commit" .gitignore)
    assert_equals "1" "$count" "should not duplicate existing pattern"

    # But the others should be added
    local gitignore_content
    gitignore_content=$(cat .gitignore)
    assert_contains "$gitignore_content" ".set-core/agents/" "missing agents/ pattern should be added"

    cd /
    rm -rf "$tmpdir"
}

run_tests
