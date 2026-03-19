#!/usr/bin/env bash
# Unit tests for milestone orchestration: server detection, phase advancement, phase-gated dispatch
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source set-common first (needed by orchestration modules)
source "$SCRIPT_DIR/../../bin/set-common.sh"

# Source orchestration modules in order
LIB_DIR="$SCRIPT_DIR/../../lib/orchestration"
source "$LIB_DIR/events.sh"
source "$LIB_DIR/config.sh"
source "$LIB_DIR/utils.sh"
source "$LIB_DIR/state.sh"
source "$LIB_DIR/server-detect.sh"

# ─── Test Setup ──────────────────────────────────────────────────────

_setup_test_dir() {
    local tmpdir
    tmpdir=$(mktemp -d)
    echo "$tmpdir"
}

_teardown_test_dir() {
    rm -rf "$1"
}

# ─── detect_dev_server tests ─────────────────────────────────────────

test_detect_dev_server_explicit_override() {
    local result
    result=$(detect_dev_server "." "my-custom-server --port 3000" "")
    assert_equals "my-custom-server --port 3000" "$result" "explicit override used"
}

test_detect_dev_server_smoke_fallback() {
    local result
    result=$(detect_dev_server "." "" "npx next dev --port 3002")
    assert_equals "npx next dev --port 3002" "$result" "smoke fallback used"
}

test_detect_dev_server_package_json() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    echo '{"scripts":{"dev":"next dev"}}' > "$tmpdir/package.json"

    local result
    result=$(detect_dev_server "$tmpdir" "" "")
    assert_equals "npm run dev" "$result" "package.json scripts.dev detected with npm"

    _teardown_test_dir "$tmpdir"
}

test_detect_dev_server_bun() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    echo '{"scripts":{"dev":"next dev"}}' > "$tmpdir/package.json"
    touch "$tmpdir/bun.lockb"

    local result
    result=$(detect_dev_server "$tmpdir" "" "")
    assert_equals "bun run dev" "$result" "bun detected from lockfile"

    _teardown_test_dir "$tmpdir"
}

test_detect_dev_server_docker_compose() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    touch "$tmpdir/docker-compose.yml"

    local result
    result=$(detect_dev_server "$tmpdir" "" "")
    assert_equals "docker compose up" "$result" "docker-compose detected"

    _teardown_test_dir "$tmpdir"
}

test_detect_dev_server_makefile() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    printf 'dev:\n\tnpm run dev\n' > "$tmpdir/Makefile"

    local result
    result=$(detect_dev_server "$tmpdir" "" "")
    assert_equals "make dev" "$result" "Makefile dev target detected"

    _teardown_test_dir "$tmpdir"
}

test_detect_dev_server_django() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    touch "$tmpdir/manage.py"

    local result
    result=$(detect_dev_server "$tmpdir" "" "")
    assert_equals "python manage.py runserver" "$result" "Django manage.py detected"

    _teardown_test_dir "$tmpdir"
}

test_detect_dev_server_none() {
    local tmpdir
    tmpdir=$(_setup_test_dir)

    local result rc=0
    result=$(detect_dev_server "$tmpdir" "" "" 2>/dev/null) || rc=$?
    assert_equals "1" "$rc" "returns 1 when no server detected"

    _teardown_test_dir "$tmpdir"
}

# ─── detect_package_manager tests ────────────────────────────────────

test_detect_package_manager_npm_default() {
    local tmpdir
    tmpdir=$(_setup_test_dir)

    local result
    result=$(detect_package_manager "$tmpdir")
    assert_equals "npm" "$result" "defaults to npm"

    _teardown_test_dir "$tmpdir"
}

test_detect_package_manager_pnpm() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    touch "$tmpdir/pnpm-lock.yaml"

    local result
    result=$(detect_package_manager "$tmpdir")
    assert_equals "pnpm" "$result" "pnpm from lockfile"

    _teardown_test_dir "$tmpdir"
}

test_detect_package_manager_yarn() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    touch "$tmpdir/yarn.lock"

    local result
    result=$(detect_package_manager "$tmpdir")
    assert_equals "yarn" "$result" "yarn from lockfile"

    _teardown_test_dir "$tmpdir"
}

# ─── advance_phase tests ────────────────────────────────────────────

test_advance_phase_basic() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"
    EVENTS_ENABLED="false"

    # Create state with 3 phases
    cat > "$STATE_FILENAME" <<'EOF'
{
    "current_phase": 1,
    "phases": {
        "1": {"status": "running", "tag": null, "server_port": null, "server_pid": null, "completed_at": null},
        "2": {"status": "pending", "tag": null, "server_port": null, "server_pid": null, "completed_at": null},
        "3": {"status": "pending", "tag": null, "server_port": null, "server_pid": null, "completed_at": null}
    },
    "changes": [
        {"name": "a", "phase": 1, "status": "merged", "tokens_used": 0, "depends_on": []},
        {"name": "b", "phase": 2, "status": "pending", "tokens_used": 0, "depends_on": []},
        {"name": "c", "phase": 3, "status": "pending", "tokens_used": 0, "depends_on": []}
    ]
}
EOF

    # Advance from phase 1 to 2
    local rc=0
    advance_phase || rc=$?
    assert_equals "0" "$rc" "advance_phase returns 0"

    # Check new current_phase
    local new_cp
    new_cp=$(jq -r '.current_phase' "$STATE_FILENAME")
    assert_equals "2" "$new_cp" "current_phase advanced to 2"

    # Check phase 1 is completed
    local p1_status
    p1_status=$(jq -r '.phases["1"].status' "$STATE_FILENAME")
    assert_equals "completed" "$p1_status" "phase 1 marked completed"

    # Check phase 1 has completed_at
    local p1_ts
    p1_ts=$(jq -r '.phases["1"].completed_at' "$STATE_FILENAME")
    assert_not_contains "$p1_ts" "null" "phase 1 has completed_at timestamp"

    # Check phase 2 is running
    local p2_status
    p2_status=$(jq -r '.phases["2"].status' "$STATE_FILENAME")
    assert_equals "running" "$p2_status" "phase 2 marked running"

    _teardown_test_dir "$tmpdir"
}

test_advance_phase_last_phase() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"
    EVENTS_ENABLED="false"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "current_phase": 2,
    "phases": {
        "1": {"status": "completed", "tag": "milestone/phase-1", "completed_at": "2026-03-14T10:00:00"},
        "2": {"status": "running", "tag": null}
    },
    "changes": [
        {"name": "a", "phase": 1, "status": "merged", "tokens_used": 0, "depends_on": []},
        {"name": "b", "phase": 2, "status": "merged", "tokens_used": 0, "depends_on": []}
    ]
}
EOF

    # Advance from last phase — should return 1
    local rc=0
    advance_phase || rc=$?
    assert_equals "1" "$rc" "returns 1 when no more phases"

    # Phase 2 should be completed
    local p2_status
    p2_status=$(jq -r '.phases["2"].status' "$STATE_FILENAME")
    assert_equals "completed" "$p2_status" "last phase marked completed"

    _teardown_test_dir "$tmpdir"
}

# ─── all_phase_changes_terminal tests ────────────────────────────────

test_all_phase_changes_terminal_true() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "changes": [
        {"name": "a", "phase": 1, "status": "merged"},
        {"name": "b", "phase": 1, "status": "failed"},
        {"name": "c", "phase": 2, "status": "pending"}
    ]
}
EOF

    all_phase_changes_terminal 1
    assert_equals "0" "$?" "all phase 1 changes terminal"
}

test_all_phase_changes_terminal_false() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "changes": [
        {"name": "a", "phase": 1, "status": "merged"},
        {"name": "b", "phase": 1, "status": "running"},
        {"name": "c", "phase": 2, "status": "pending"}
    ]
}
EOF

    local rc=0
    all_phase_changes_terminal 1 || rc=$?
    assert_equals "1" "$rc" "phase 1 not all terminal (b is running)"
}

# ─── Phase-gated dispatch test ───────────────────────────────────────

test_phase_gated_dispatch() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"
    EVENTS_ENABLED="false"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "current_phase": 1,
    "phases": {
        "1": {"status": "running"},
        "2": {"status": "pending"}
    },
    "changes": [
        {"name": "infra", "phase": 1, "status": "pending", "complexity": "S", "depends_on": [], "tokens_used": 0},
        {"name": "feature", "phase": 2, "status": "pending", "complexity": "S", "depends_on": [], "tokens_used": 0}
    ]
}
EOF

    # Read current_phase and filter
    local current_phase
    current_phase=$(jq -r '.current_phase // 999' "$STATE_FILENAME")
    assert_equals "1" "$current_phase" "current_phase is 1"

    # Only phase-1 changes should be dispatchable
    local phase1_count phase2_count
    phase1_count=$(jq --argjson cp "$current_phase" '[.changes[] | select(.status == "pending" and (.phase // 1) <= $cp)] | length' "$STATE_FILENAME")
    phase2_count=$(jq --argjson cp "$current_phase" '[.changes[] | select(.status == "pending" and (.phase // 1) > $cp)] | length' "$STATE_FILENAME")

    assert_equals "1" "$phase1_count" "1 change dispatchable in phase 1"
    assert_equals "1" "$phase2_count" "1 change gated in phase 2"

    _teardown_test_dir "$tmpdir"
}

# ─── _init_phase_state test ──────────────────────────────────────────

test_init_phase_state_creates_phases() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"
    EVENTS_ENABLED="false"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "changes": [
        {"name": "a", "phase": 1, "status": "pending"},
        {"name": "b", "phase": 1, "status": "pending"},
        {"name": "c", "phase": 2, "status": "pending"},
        {"name": "d", "phase": 3, "status": "pending"}
    ]
}
EOF

    _init_phase_state

    local phase_count current_phase
    phase_count=$(jq '.phases | length' "$STATE_FILENAME")
    current_phase=$(jq -r '.current_phase' "$STATE_FILENAME")

    assert_equals "3" "$phase_count" "3 phases created"
    assert_equals "1" "$current_phase" "current_phase starts at 1"

    local p1_status p2_status
    p1_status=$(jq -r '.phases["1"].status' "$STATE_FILENAME")
    p2_status=$(jq -r '.phases["2"].status' "$STATE_FILENAME")
    assert_equals "running" "$p1_status" "phase 1 is running"
    assert_equals "pending" "$p2_status" "phase 2 is pending"
}

test_init_phase_state_skips_single_phase() {
    local tmpdir
    tmpdir=$(_setup_test_dir)
    STATE_FILENAME="$tmpdir/state.json"
    EVENTS_ENABLED="false"

    cat > "$STATE_FILENAME" <<'EOF'
{
    "changes": [
        {"name": "a", "phase": 1, "status": "pending"},
        {"name": "b", "phase": 1, "status": "pending"}
    ]
}
EOF

    _init_phase_state

    local has_phases
    has_phases=$(jq 'has("phases")' "$STATE_FILENAME")
    assert_equals "false" "$has_phases" "no phases object for single-phase plans"
}

run_tests
