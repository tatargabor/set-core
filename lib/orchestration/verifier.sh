#!/usr/bin/env bash
# lib/orchestration/verifier.sh — Thin wrappers delegating to wt-orch-core verify
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Python implementation: lib/wt_orch/verifier.py

# ─── Test Runner ─────────────────────────────────────────────────────

# Run tests in a worktree with timeout. Sets TEST_OUTPUT variable.
# Returns 0 on pass, 1 on fail.
run_tests_in_worktree() {
    local wt_path="$1"
    local test_command="$2"
    local test_timeout="${3:-$DEFAULT_TEST_TIMEOUT}"
    local max_chars="${4:-2000}"

    TEST_OUTPUT=""
    local json_out
    json_out=$(wt-orch-core verify run-tests \
        --wt-path "$wt_path" \
        --command "$test_command" \
        --timeout "$test_timeout" \
        --max-chars "$max_chars" 2>/dev/null) || true

    TEST_OUTPUT=$(echo "$json_out" | jq -r '.output // ""' 2>/dev/null || true)
    local passed
    passed=$(echo "$json_out" | jq -r '.passed // false' 2>/dev/null || echo "false")
    [[ "$passed" == "true" ]] && return 0 || return 1
}

# ─── Requirement-Aware Review ────────────────────────────────────────

build_req_review_section() {
    local change_name="$1"
    wt-orch-core verify build-req-section \
        --change "$change_name" \
        --state "$STATE_FILENAME" 2>/dev/null || true
}

# ─── Code Review ─────────────────────────────────────────────────────

# Returns 0 if no CRITICAL issues, 1 if CRITICAL found. Sets REVIEW_OUTPUT.
review_change() {
    local change_name="$1"
    local wt_path="$2"
    local scope="$3"
    local rev_model="${4:-$DEFAULT_REVIEW_MODEL}"

    REVIEW_OUTPUT=""
    local json_out
    json_out=$(wt-orch-core verify review \
        --change "$change_name" \
        --wt-path "$wt_path" \
        --scope "$scope" \
        --model "$rev_model" \
        --state "$STATE_FILENAME" 2>/dev/null) || true

    REVIEW_OUTPUT=$(echo "$json_out" | jq -r '.output // ""' 2>/dev/null || true)
    local has_critical
    has_critical=$(echo "$json_out" | jq -r '.has_critical // false' 2>/dev/null || echo "false")
    [[ "$has_critical" == "true" ]] && return 1 || return 0
}

# ─── Verification Rules ──────────────────────────────────────────────

evaluate_verification_rules() {
    local change_name="$1"
    local wt_path="$2"

    wt-orch-core verify evaluate-rules \
        --change "$change_name" \
        --wt-path "$wt_path" \
        --state "$STATE_FILENAME" >/dev/null 2>&1
}

# ─── Scope Checks ────────────────────────────────────────────────────

verify_merge_scope() {
    local change_name="$1"
    wt-orch-core verify check-merge-scope --change "$change_name" >/dev/null 2>&1
}

verify_implementation_scope() {
    local change_name="$1"
    local wt_path="$2"
    wt-orch-core verify check-impl-scope \
        --change "$change_name" \
        --wt-path "$wt_path" >/dev/null 2>&1
}

# ─── Health Check ────────────────────────────────────────────────────

extract_health_check_url() {
    local smoke_cmd="$1"
    wt-orch-core verify extract-health-url --smoke-cmd "$smoke_cmd" 2>/dev/null
}

health_check() {
    local url="$1"
    local timeout_secs="${2:-30}"
    wt-orch-core verify health-check --url "$url" --timeout "$timeout_secs" >/dev/null 2>&1
}

# ─── Smoke Fix ───────────────────────────────────────────────────────

smoke_fix_scoped() {
    local change_name="$1"
    local smoke_cmd="$2"
    local smoke_tout="$3"
    local max_retries="${4:-3}"
    local max_turns="${5:-15}"
    local smoke_output="$6"

    wt-orch-core verify smoke-fix \
        --change "$change_name" \
        --smoke-cmd "$smoke_cmd" \
        --smoke-timeout "$smoke_tout" \
        --smoke-output "$smoke_output" \
        --state "$STATE_FILENAME" \
        --max-retries "$max_retries" \
        --max-turns "$max_turns" >/dev/null 2>&1
}

# ─── Phase-End E2E ───────────────────────────────────────────────────

run_phase_end_e2e() {
    local e2e_command="$1"
    local e2e_timeout="${2:-180}"

    wt-orch-core verify phase-e2e \
        --command "$e2e_command" \
        --state "$STATE_FILENAME" \
        --timeout "$e2e_timeout" >/dev/null 2>&1
    return 0  # Non-blocking
}

# ─── Poll Change ─────────────────────────────────────────────────────

poll_change() {
    local change_name="$1"
    local test_command="$2"
    local merge_policy="$3"
    local test_timeout="${4:-$DEFAULT_TEST_TIMEOUT}"
    local max_verify_retries="${5:-$DEFAULT_MAX_VERIFY_RETRIES}"
    local review_before_merge="${6:-false}"
    local review_model="${7:-$DEFAULT_REVIEW_MODEL}"
    local smoke_command="${8:-}"
    local smoke_timeout="${9:-$DEFAULT_SMOKE_TIMEOUT}"
    local smoke_blocking="${10:-false}"
    local smoke_fix_max_retries="${11:-$DEFAULT_SMOKE_FIX_MAX_RETRIES}"
    local smoke_fix_max_turns="${12:-$DEFAULT_SMOKE_FIX_MAX_TURNS}"
    local smoke_health_check_url="${13:-}"
    local smoke_health_check_timeout="${14:-$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT}"
    local e2e_command="${15:-}"
    local e2e_timeout="${16:-120}"

    local poll_args=(
        wt-orch-core verify poll
        --change "$change_name"
        --state "$STATE_FILENAME"
        --test-command "$test_command"
        --merge-policy "$merge_policy"
        --test-timeout "$test_timeout"
        --max-verify-retries "$max_verify_retries"
        --review-model "$review_model"
        --smoke-command "$smoke_command"
        --smoke-timeout "$smoke_timeout"
        --e2e-command "${e2e_command:-}"
        --e2e-timeout "$e2e_timeout"
    )
    [[ "$review_before_merge" == "true" ]] && poll_args+=(--review-before-merge)

    "${poll_args[@]}" >/dev/null 2>&1 || true
}

# ─── Handle Change Done ─────────────────────────────────────────────

handle_change_done() {
    local change_name="$1"
    local wt_path="$2"
    local test_command="$3"
    local merge_policy="$4"
    local test_timeout="${5:-$DEFAULT_TEST_TIMEOUT}"
    local max_verify_retries="${6:-$DEFAULT_MAX_VERIFY_RETRIES}"
    local review_before_merge="${7:-false}"
    local review_model="${8:-$DEFAULT_REVIEW_MODEL}"
    local smoke_command="${9:-}"
    local smoke_timeout="${10:-$DEFAULT_SMOKE_TIMEOUT}"
    local smoke_blocking="${11:-false}"
    local smoke_fix_max_retries="${12:-$DEFAULT_SMOKE_FIX_MAX_RETRIES}"
    local smoke_fix_max_turns="${13:-$DEFAULT_SMOKE_FIX_MAX_TURNS}"
    local smoke_health_check_url="${14:-}"
    local smoke_health_check_timeout="${15:-$DEFAULT_SMOKE_HEALTH_CHECK_TIMEOUT}"
    local e2e_command="${16:-}"
    local e2e_timeout="${17:-120}"

    local done_args=(
        wt-orch-core verify handle-done
        --change "$change_name"
        --state "$STATE_FILENAME"
        --test-command "$test_command"
        --merge-policy "$merge_policy"
        --test-timeout "$test_timeout"
        --max-verify-retries "$max_verify_retries"
        --review-model "$review_model"
        --smoke-command "$smoke_command"
        --smoke-timeout "$smoke_timeout"
        --e2e-command "${e2e_command:-}"
        --e2e-timeout "$e2e_timeout"
    )
    [[ "$review_before_merge" == "true" ]] && done_args+=(--review-before-merge)

    "${done_args[@]}" >/dev/null 2>&1 || true
}

# ─── Screenshot Collection ───────────────────────────────────────────
# Internal helper used by smoke fix — now handled in Python
_collect_smoke_screenshots() {
    :  # No-op: handled by Python verifier
}
