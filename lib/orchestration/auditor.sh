#!/usr/bin/env bash
# lib/orchestration/auditor.sh — Thin wrapper: logic lives in lib/wt_orch/auditor.py
#
# Sourced by bin/set-orchestrate for backward compatibility.
# Python implementation: lib/wt_orch/auditor.py, cli.py:cmd_audit()

# Run post-phase audit. Delegates to Python.
# Sets _REPLAN_AUDIT_GAPS for replan prompt injection (exported).
run_post_phase_audit() {
    local cycle="${1:-1}"

    local audit_args=(
        --state "$STATE_FILENAME"
        --cycle "$cycle"
    )
    [[ "${INPUT_MODE:-}" == "digest" ]] && audit_args+=(--input-mode digest)
    [[ -n "${INPUT_PATH:-}" ]] && audit_args+=(--input-path "$INPUT_PATH")

    local rev_model="${DEFAULT_REVIEW_MODEL:-sonnet}"
    if [[ -n "${STATE_FILENAME:-}" && -f "${STATE_FILENAME:-}" ]]; then
        local dir_model
        dir_model=$(jq -r '.directives.review_model // ""' "$STATE_FILENAME" 2>/dev/null || true)
        [[ -n "$dir_model" && "$dir_model" != "null" ]] && rev_model="$dir_model"
    fi
    audit_args+=(--model "$rev_model")

    local result
    result=$(set-orch-core audit run "${audit_args[@]}" 2>/dev/null) || {
        warn "Post-phase audit: failed, skipping (non-blocking)"
        export _REPLAN_AUDIT_GAPS=""
        return 0
    }

    local audit_result gap_count
    audit_result=$(echo "$result" | jq -r '.audit_result // "unknown"')
    gap_count=$(echo "$result" | jq -r '.gap_count // 0')

    # Store result in state
    local summary duration_ms
    summary=$(echo "$result" | jq -r '.summary // ""')
    duration_ms=$(echo "$result" | jq -r '.duration_ms // 0')

    safe_jq_update "$STATE_FILENAME" \
        --argjson cycle "$cycle" \
        --argjson ms "$duration_ms" \
        --arg model "$rev_model" \
        --arg mode "${INPUT_MODE:-spec}" \
        --arg result_val "$audit_result" \
        --argjson gaps "$(echo "$result" | jq '.gaps // []')" \
        --arg summary "$summary" \
        '.phase_audit_results = (.phase_audit_results // []) + [{
            cycle: $cycle,
            audit_result: $result_val,
            model: $model,
            mode: $mode,
            duration_ms: $ms,
            gaps: $gaps,
            summary: $summary,
            timestamp: (now | todate)
        }]'

    if [[ "$audit_result" == "gaps_found" || "$gap_count" -gt 0 ]]; then
        local critical_count minor_count
        critical_count=$(echo "$result" | jq '[.gaps[] | select(.severity == "critical")] | length')
        minor_count=$(echo "$result" | jq '[.gaps[] | select(.severity == "minor")] | length')
        warn "Post-phase audit: $gap_count gaps ($critical_count critical, $minor_count minor)"
        emit_event "AUDIT_GAPS" "" "{\"cycle\":$cycle,\"gap_count\":$gap_count,\"critical_count\":$critical_count}"

        local gap_descriptions
        gap_descriptions=$(echo "$result" | jq -r '
            [.gaps[] | "- [\(.severity)] \(.description) (ref: \(.spec_reference // "n/a"))\n  Suggested scope: \(.suggested_scope // "n/a")"] | join("\n")
        ')
        export _REPLAN_AUDIT_GAPS="$gap_descriptions"
    else
        info "Post-phase audit: all spec sections covered"
        emit_event "AUDIT_CLEAN" "" "{\"cycle\":$cycle,\"duration_ms\":$duration_ms}"
        export _REPLAN_AUDIT_GAPS=""
    fi
}

# Build audit prompt (for direct invocation / testing).
build_audit_prompt() {
    local cycle="${1:-1}"
    set-orch-core audit prompt --state "$STATE_FILENAME" --cycle "$cycle" \
        ${INPUT_MODE:+--input-mode "$INPUT_MODE"} \
        ${INPUT_PATH:+--input-path "$INPUT_PATH"} 2>/dev/null
}

# Parse audit result JSON (delegates to Python).
parse_audit_result() {
    local raw_file="$1"
    set-orch-core audit parse --raw-file "$raw_file" 2>/dev/null
}
