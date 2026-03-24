#!/usr/bin/env bash
# lib/orchestration/digest.sh — Thin wrapper: logic lives in lib/set_orch/digest.py
#
# Sourced by bin/set-orchestrate after planner.sh.
# Python implementation: lib/set_orch/digest.py, cli.py:cmd_digest()

DIGEST_DIR="${WT_DIGEST_DIR:-set/orchestration/digest}"

# ─── Digest Entry Point ──────────────────────────────────────────────

cmd_digest() {
    local spec_path=""
    local dry_run=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --spec)    spec_path="$2"; shift 2 ;;
            --spec=*)  spec_path="${1#--spec=}"; shift ;;
            --dry-run) dry_run=true; shift ;;
            --help|-h)
                cat <<'USAGE'
Usage: set-orchestrate digest --spec <path> [--dry-run]

Generate a structured digest from a multi-file specification directory.

Options:
  --spec <path>    Path to spec directory or single file (required)
  --dry-run        Print digest output to stdout without writing files
USAGE
                return 0
                ;;
            *) error "Unknown option: $1"; return 1 ;;
        esac
    done

    if [[ -z "$spec_path" ]]; then
        if [[ -n "$SPEC_OVERRIDE" ]]; then
            spec_path="$SPEC_OVERRIDE"
        else
            error "Missing required --spec <path>"
            return 1
        fi
    fi

    if [[ ! -e "$spec_path" ]]; then
        error "Path not found: $spec_path"
        return 1
    fi

    local abs_spec_path
    abs_spec_path="$(cd "$(dirname "$spec_path")" && pwd)/$(basename "$spec_path")"

    emit_event "DIGEST_STARTED" "" "{}" 2>/dev/null || true

    local run_args=(--spec "$abs_spec_path")
    $dry_run && run_args+=(--dry-run)

    local result
    result=$(set-orch-core digest run "${run_args[@]}" 2>/dev/null) || {
        emit_event "DIGEST_FAILED" "" "{\"reason\":\"run_failed\"}" 2>/dev/null || true
        error "Digest generation failed"
        return 1
    }

    local status
    status=$(echo "$result" | jq -r '.status // "error"')
    if [[ "$status" != "ok" ]]; then
        local err_msg
        err_msg=$(echo "$result" | jq -r '.error // "unknown error"')
        error "Digest failed: $err_msg"
        return 1
    fi

    local req_count domain_count
    req_count=$(echo "$result" | jq -r '.req_count // 0')
    domain_count=$(echo "$result" | jq -r '.domain_count // 0')

    if $dry_run; then
        info "=== DRY RUN — Digest output ==="
        echo "$result" | jq .
    else
        success "Digest complete: $req_count requirements across $domain_count domain(s)"
        emit_event "DIGEST_COMPLETE" "" "{\"req_count\":$req_count,\"domain_count\":$domain_count}" 2>/dev/null || true
        generate_report 2>/dev/null || true
    fi
}

# ─── Thin wrappers delegating to set-orch-core ────────────────────────

scan_spec_directory() {
    local spec_path="$1"
    set-orch-core digest scan --spec "$spec_path"
}

check_digest_freshness() {
    local spec_path="$1"
    local result
    result=$(set-orch-core digest freshness --spec "$spec_path" 2>/dev/null) || {
        echo "error"
        return 1
    }
    echo "$result" | jq -r '.freshness'
}

populate_coverage() {
    local plan_file="$1"
    set-orch-core digest populate-coverage --plan-file "$plan_file" 2>/dev/null || {
        log_warn "populate_coverage: failed"
        return 1
    }
}

update_coverage_status() {
    local change_name="$1"
    local new_status="$2"
    set-orch-core digest update-coverage --change "$change_name" --status "$new_status" 2>/dev/null || true
}

# check_coverage_gaps() — removed, runs in Python via digest.py:check_coverage_gaps()

final_coverage_check() {
    local result
    result=$(set-orch-core digest final-coverage 2>/dev/null) || return 0
    echo "$result" | jq -r '.summary // ""'
}

# build_coverage_summary() — removed, runs in Python via digest.py:final_coverage_check()

generate_triage_md() {
    local amb_file="$1"
    local output_file="$2"
    local existing_triage="${3:-}"
    local args=(--amb-file "$amb_file" --output "$output_file")
    [[ -n "$existing_triage" ]] && args+=(--existing-triage "$existing_triage")
    set-orch-core digest generate-triage "${args[@]}" 2>/dev/null || true
}

parse_triage_md() {
    local triage_file="$1"
    set-orch-core digest parse-triage --triage-file "$triage_file" 2>/dev/null || echo '{}'
}

merge_triage_to_ambiguities() {
    local amb_file="$1"
    local triage_decisions="$2"
    local resolved_by="${3:-triage}"
    set-orch-core digest merge-triage --amb-file "$amb_file" --decisions "$triage_decisions" --resolved-by "$resolved_by" 2>/dev/null || true
}

merge_planner_resolutions() {
    local amb_file="$1"
    local plan_file="$2"
    set-orch-core digest merge-planner-resolutions --amb-file "$amb_file" --plan-file "$plan_file" 2>/dev/null || true
}

build_digest_prompt() {
    local spec_path="$1"
    local scan_result="$2"  # unused — Python rebuilds scan internally
    set-orch-core digest build-prompt --spec "$spec_path" 2>/dev/null
}

call_digest_api() {
    local prompt="$1"
    local output
    output=$(export RUN_CLAUDE_NO_MCP=1 RUN_CLAUDE_TIMEOUT=600; echo "$prompt" | run_claude --model "$(model_id opus)" --max-turns 1) || {
        log_error "Digest API call failed"
        return 1
    }
    echo "$output"
}

parse_digest_response() {
    local raw_response="$1"
    set-orch-core digest parse-response <<< "$raw_response"
}

write_digest_output() {
    local parsed="$1"
    local spec_path="$2"
    local scan_result="$3"  # unused — Python uses parsed data directly
    set-orch-core digest write-output --spec "$spec_path" <<< "$parsed"
}

validate_digest() {
    local parsed="$1"
    set-orch-core digest validate-raw <<< "$parsed"
}

stabilize_ids() {
    local new_parsed="$1"
    set-orch-core digest stabilize-ids <<< "$new_parsed"
}

# ─── Coverage Report ────────────────────────────────────────────────

cmd_coverage() {
    if [[ ! -d "$DIGEST_DIR" ]]; then
        info "No digest found. Run \`set-orchestrate digest --spec <path>\` first."
        return 0
    fi

    if [[ ! -f "$DIGEST_DIR/requirements.json" ]]; then
        info "No requirements.json found in digest."
        return 0
    fi

    local req_count
    req_count=$(jq '.requirements | length' "$DIGEST_DIR/requirements.json")

    if [[ ! -f "$DIGEST_DIR/coverage.json" ]] || \
       [[ "$(jq '.coverage | length' "$DIGEST_DIR/coverage.json")" -eq 0 ]]; then
        info "Requirements: $req_count total"
        info "No plan generated yet. All requirements uncovered."
        return 0
    fi

    echo ""
    info "═══ Coverage Report ═══"
    echo ""

    # Per-domain breakdown
    local domains
    domains=$(jq -r '[.requirements[] | select(.status != "removed") | .domain] | unique | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

    while IFS= read -r domain; do
        [[ -z "$domain" ]] && continue
        local domain_reqs
        domain_reqs=$(jq -r --arg d "$domain" '[.requirements[] | select(.domain == $d and .status != "removed") | .id] | .[]' "$DIGEST_DIR/requirements.json")
        local total=0 planned=0 dispatched=0 running=0 merged=0 uncovered=0

        while IFS= read -r req_id; do
            [[ -z "$req_id" ]] && continue
            total=$((total + 1))
            local status
            status=$(jq -r --arg id "$req_id" '.coverage[$id].status // "uncovered"' "$DIGEST_DIR/coverage.json")
            case "$status" in
                planned)     planned=$((planned + 1)) ;;
                dispatched)  dispatched=$((dispatched + 1)) ;;
                running)     running=$((running + 1)) ;;
                merged)      merged=$((merged + 1)) ;;
                *)           uncovered=$((uncovered + 1)) ;;
            esac
        done <<< "$domain_reqs"

        printf "  %-20s total=%d  planned=%d  dispatched=%d  running=%d  merged=%d" \
            "$domain" "$total" "$planned" "$dispatched" "$running" "$merged"
        if [[ $uncovered -gt 0 ]]; then
            printf "  UNCOVERED=%d" "$uncovered"
        fi
        echo ""
    done <<< "$domains"

    echo ""
}
