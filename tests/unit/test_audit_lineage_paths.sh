#!/usr/bin/env bash
# Unit tests for scripts/audit-lineage-paths.sh (Section 17.5/17.6).

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$SCRIPT_DIR/helpers.sh"

AUDIT="$REPO_ROOT/scripts/audit-lineage-paths.sh"
TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

# Fabricate a tiny "fake repo" by copying just the audit script + a few
# dummy code files into it.  This avoids running against the real repo
# (which currently has known migration-debt residuals).
mkdir -p "$TMP_DIR/lib/set_orch" "$TMP_DIR/scripts" "$TMP_DIR/bin"
cp "$AUDIT" "$TMP_DIR/scripts/audit-lineage-paths.sh"

test_audit_passes_when_no_literals() {
    rm -rf "$TMP_DIR/lib/set_orch"/*.py
    cat > "$TMP_DIR/lib/set_orch/clean.py" <<'PY'
"""A pristine module with no hardcoded orchestration path literals."""
def hello():
    return "no paths here"
PY
    pushd "$TMP_DIR" >/dev/null
    "$TMP_DIR/scripts/audit-lineage-paths.sh" >/dev/null 2>&1
    local rc=$?
    popd >/dev/null
    assert_equals "0" "$rc" "audit script exits 0 when no residual literals"
}

test_audit_fails_when_literal_present() {
    rm -rf "$TMP_DIR/lib/set_orch"/*.py
    cat > "$TMP_DIR/lib/set_orch/dirty.py" <<'PY'
# Hardcoded literal that should trigger the gate.
PLAN = "orchestration-plan.json"
PY
    pushd "$TMP_DIR" >/dev/null
    local out
    out=$("$TMP_DIR/scripts/audit-lineage-paths.sh" 2>&1)
    local rc=$?
    popd >/dev/null
    assert_equals "1" "$rc" "audit script exits non-zero when residuals exist"
    assert_contains "$out" "dirty.py" "report names the offending file"
}

test_audit_writes_report_to_file() {
    rm -rf "$TMP_DIR/lib/set_orch"/*.py
    cat > "$TMP_DIR/lib/set_orch/dirty.py" <<'PY'
# Hardcoded literal that should trigger the gate.
PLAN = "orchestration-plan.json"
PY
    local report="$TMP_DIR/audit.out"
    pushd "$TMP_DIR" >/dev/null
    "$TMP_DIR/scripts/audit-lineage-paths.sh" --report "$report" >/dev/null 2>&1 || true
    popd >/dev/null
    [[ -f "$report" ]] && assert_equals "yes" "yes" "report file written to disk" || \
        assert_equals "yes" "no" "report file written to disk"
}

test_audit_ignores_documentation_files() {
    rm -rf "$TMP_DIR/lib/set_orch"/*.py
    cat > "$TMP_DIR/lib/set_orch/clean.py" <<'PY'
def hello(): return "x"
PY
    # Markdown / template references should NOT trip the gate.
    mkdir -p "$TMP_DIR/lib/set_orch/templates"
    cat > "$TMP_DIR/lib/set_orch/templates/example.md" <<'MD'
The plan lives at `orchestration-plan.json` in the runtime dir.
MD
    pushd "$TMP_DIR" >/dev/null
    "$TMP_DIR/scripts/audit-lineage-paths.sh" >/dev/null 2>&1
    local rc=$?
    popd >/dev/null
    assert_equals "0" "$rc" "audit ignores .md template references"
}

run_tests
