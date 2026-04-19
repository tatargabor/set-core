#!/usr/bin/env bash
# Unit tests for the lineage-aware bash helpers in bin/set-common.sh.
# Verifies they mirror lib/set_orch/paths.py::LineagePaths.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Ensure we use the repo's set-common.sh (not any system install).
SET_TOOLS_ROOT="$REPO_ROOT"
# shellcheck disable=SC1091
source "$REPO_ROOT/bin/set-common.sh"

# Build an isolated runtime under a tmp dir and stub a project.
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

PROJECT_PATH="$TMP_DIR/myproject"
mkdir -p "$PROJECT_PATH"
(
    cd "$PROJECT_PATH"
    git init -q >/dev/null
    git -c user.email=t@t -c user.name=t commit --allow-empty -q -m init
)

# Override XDG_DATA_HOME so SetRuntime points into the tmp tree.
export XDG_DATA_HOME="$TMP_DIR/xdg"

test_lineage_slug_basic() {
    local out
    out=$(lineage_slug "docs/spec-v1.md")
    assert_equals "docs-spec-v1.md" "$out" "slug docs/spec-v1.md"
}

test_lineage_slug_empty() {
    local out
    out=$(lineage_slug "")
    assert_equals "_unknown" "$out" "slug empty -> _unknown"
}

test_lineage_plan_file_live() {
    local out
    out=$(lineage_plan_file "$PROJECT_PATH")
    assert_contains "$out" "orchestration-plan.json" "plan_file ends with orchestration-plan.json"
}

test_lineage_directives_file_is_project_relative() {
    local out
    out=$(lineage_directives_file "$PROJECT_PATH")
    assert_equals "$PROJECT_PATH/set/orchestration/directives.json" "$out" "directives_file"
}

test_lineage_issues_registry_is_project_relative() {
    local out
    out=$(lineage_issues_registry "$PROJECT_PATH")
    assert_equals "$PROJECT_PATH/.set/issues/registry.json" "$out" "issues_registry"
}

test_lineage_state_archive_includes_runtime_root() {
    local out
    out=$(lineage_state_archive "$PROJECT_PATH")
    assert_contains "$out" "state-archive.jsonl" "state_archive contains state-archive.jsonl"
    assert_contains "$out" "$XDG_DATA_HOME" "state_archive lives under XDG_DATA_HOME"
}

run_tests
