#!/usr/bin/env bash
# lib/orchestration/auditor.sh — Post-phase LLM audit: spec-vs-implementation gap detection
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Depends on: state.sh (safe_jq_update), events.sh (emit_event), utils.sh (model_id)

# ─── Audit Prompt Builder ────────────────────────────────────────────

# Build the audit input JSON for wt-orch-core template audit.
# Reads spec/digest + merged changes from state to construct audit context.
# Args: cycle_number
# Outputs: JSON string to stdout
build_audit_prompt() {
    local cycle="${1:-1}"
    local audit_input_file
    audit_input_file=$(mktemp)

    # Collect merged changes with scopes and file lists
    local changes_json="[]"
    local change_names
    change_names=$(jq -r '.changes[] | select(.status == "merged") | .name' "$STATE_FILENAME" 2>/dev/null || true)

    if [[ -n "$change_names" ]]; then
        local _changes_arr="[]"
        while IFS= read -r cname; do
            [[ -z "$cname" ]] && continue
            local cscope
            cscope=$(jq -r --arg n "$cname" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME" 2>/dev/null || true)
            # Get file list from git log (max 50 files per change)
            local cfiles=""
            local merge_commit
            merge_commit=$(jq -r --arg n "$cname" '.changes[] | select(.name == $n) | .merge_commit // ""' "$STATE_FILENAME" 2>/dev/null || true)
            if [[ -n "$merge_commit" && "$merge_commit" != "null" ]]; then
                cfiles=$(git diff-tree --no-commit-id --name-only -r "$merge_commit" 2>/dev/null | head -50 | paste -sd $'\n' || true)
            fi
            _changes_arr=$(echo "$_changes_arr" | jq \
                --arg name "$cname" \
                --arg scope "$cscope" \
                --arg status "merged" \
                --arg file_list "$cfiles" \
                '. + [{name: $name, scope: $scope, status: $status, file_list: $file_list}]')
        done <<< "$change_names"
        changes_json="$_changes_arr"
    fi

    # Also include failed/skipped changes for context
    local other_names
    other_names=$(jq -r '.changes[] | select(.status == "failed" or .status == "skipped") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    if [[ -n "$other_names" ]]; then
        while IFS= read -r cname; do
            [[ -z "$cname" ]] && continue
            local cscope cstatus
            cscope=$(jq -r --arg n "$cname" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME" 2>/dev/null || true)
            cstatus=$(jq -r --arg n "$cname" '.changes[] | select(.name == $n) | .status // ""' "$STATE_FILENAME" 2>/dev/null || true)
            changes_json=$(echo "$changes_json" | jq \
                --arg name "$cname" \
                --arg scope "$cscope" \
                --arg status "$cstatus" \
                --arg file_list "" \
                '. + [{name: $name, scope: $scope, status: $status, file_list: $file_list}]')
        done <<< "$other_names"
    fi

    # Build input based on mode
    local audit_mode="spec"
    if [[ "${INPUT_MODE:-}" == "digest" && -f "${DIGEST_DIR:-wt/orchestration/digest}/requirements.json" ]]; then
        audit_mode="digest"
        local reqs_json coverage_text=""
        reqs_json=$(jq '[.requirements[] | {id, title, brief}]' "${DIGEST_DIR:-wt/orchestration/digest}/requirements.json" 2>/dev/null || echo "[]")

        if [[ -f "${DIGEST_DIR:-wt/orchestration/digest}/coverage.json" ]]; then
            coverage_text=$(jq -r '
                .coverage | to_entries[] |
                "\(.key): \(.value.status // "unknown") — \(.value.change // "unassigned")"
            ' "${DIGEST_DIR:-wt/orchestration/digest}/coverage.json" 2>/dev/null || true)
        fi

        jq -n \
            --argjson requirements "$reqs_json" \
            --argjson changes "$changes_json" \
            --arg coverage "$coverage_text" \
            --arg mode "digest" \
            '{requirements: $requirements, changes: $changes, coverage: $coverage, mode: $mode}' \
            > "$audit_input_file"
    else
        # Spec/brief mode — use raw input text
        local spec_text=""
        if [[ -n "${INPUT_PATH:-}" && -f "${INPUT_PATH:-}" ]]; then
            spec_text=$(head -c 30000 "$INPUT_PATH" 2>/dev/null || true)
        fi

        jq -n \
            --arg spec_text "$spec_text" \
            --argjson changes "$changes_json" \
            --arg mode "spec" \
            '{spec_text: $spec_text, changes: $changes, mode: $mode}' \
            > "$audit_input_file"
    fi

    # Render prompt via wt-orch-core
    wt-orch-core template audit --input-file "$audit_input_file"
    local rc=$?
    rm -f "$audit_input_file"
    return $rc
}

# ─── Audit Result Parser ─────────────────────────────────────────────

# Parse JSON from LLM audit output. Same strategy as planner.sh JSON parser.
# Args: raw_output_file
# Outputs: parsed JSON to stdout, returns 0 on success, 1 on parse failure
parse_audit_result() {
    local raw_file="$1"

    python3 - "$raw_file" <<'PYEOF'
import json, sys, re
with open(sys.argv[1]) as f:
    raw = f.read()
# Strategy: try multiple extraction methods
best_err = ''
# 1. Direct parse
try:
    data = json.loads(raw)
    if 'audit_result' in data:
        print(json.dumps(data))
        sys.exit(0)
except Exception as e:
    best_err = str(e)
# 2. Strip markdown code fences and retry
stripped = re.sub(r'```(?:json|JSON)?\s*\n?', '', raw).strip()
try:
    data = json.loads(stripped)
    if 'audit_result' in data:
        print(json.dumps(data))
        sys.exit(0)
except Exception:
    pass
# 3. Find JSON by trying from first { to each } from end backwards
first_brace = raw.find('{')
if first_brace >= 0:
    for j in range(len(raw) - 1, first_brace, -1):
        if raw[j] == '}':
            try:
                data = json.loads(raw[first_brace:j+1])
                if 'audit_result' in data:
                    print(json.dumps(data))
                    sys.exit(0)
            except Exception:
                continue
print('ERROR: Could not parse audit JSON from LLM output', file=sys.stderr)
print('Parse error: ' + best_err, file=sys.stderr)
sys.exit(1)
PYEOF
}

# ─── Main Audit Entry Point ──────────────────────────────────────────

# Run post-phase audit: build prompt, call LLM, parse result, update state.
# Args: cycle_number
# Sets: _REPLAN_AUDIT_GAPS (exported for replan prompt injection)
run_post_phase_audit() {
    local cycle="${1:-1}"
    local start_ts
    start_ts=$(date +%s%3N 2>/dev/null || date +%s)

    local audit_mode="spec"
    [[ "${INPUT_MODE:-}" == "digest" ]] && audit_mode="digest"

    local rev_model="${DEFAULT_REVIEW_MODEL:-sonnet}"
    # Read review_model from directives if available
    if [[ -n "${STATE_FILENAME:-}" && -f "${STATE_FILENAME:-}" ]]; then
        local dir_model
        dir_model=$(jq -r '.directives.review_model // ""' "$STATE_FILENAME" 2>/dev/null || true)
        [[ -n "$dir_model" && "$dir_model" != "null" ]] && rev_model="$dir_model"
    fi

    info "Post-phase audit starting (cycle $cycle, mode=$audit_mode, model=$rev_model)"
    log_info "Post-phase audit cycle $cycle: mode=$audit_mode, model=$rev_model"
    emit_event "AUDIT_START" "" "{\"cycle\":$cycle,\"mode\":\"$audit_mode\",\"model\":\"$rev_model\"}"

    # Build prompt
    local audit_prompt
    audit_prompt=$(build_audit_prompt "$cycle") || {
        warn "Post-phase audit: prompt build failed, skipping"
        log_error "Post-phase audit cycle $cycle: prompt build failed"
        return 0  # Non-blocking
    }

    # Call LLM with timeout
    local raw_output rc=0
    raw_output=$(export RUN_CLAUDE_TIMEOUT=120; echo "$audit_prompt" | run_claude --model "$(model_id "$rev_model")") || rc=$?

    local end_ts
    end_ts=$(date +%s%3N 2>/dev/null || date +%s)
    local duration_ms=$(( end_ts - start_ts ))

    # Write debug log
    local debug_log="wt/orchestration/audit-cycle-${cycle}.log"
    mkdir -p "$(dirname "$debug_log")"
    {
        echo "=== AUDIT PROMPT (cycle $cycle) ==="
        echo "$audit_prompt"
        echo ""
        echo "=== RAW LLM RESPONSE ==="
        echo "$raw_output"
        echo ""
        echo "=== METADATA ==="
        echo "model: $rev_model"
        echo "duration_ms: $duration_ms"
        echo "exit_code: $rc"
    } > "$debug_log" 2>/dev/null

    if [[ $rc -ne 0 ]]; then
        warn "Post-phase audit: LLM call failed (rc=$rc), skipping"
        log_error "Post-phase audit cycle $cycle: LLM call failed (rc=$rc) in ${duration_ms}ms"
        return 0  # Non-blocking
    fi

    # Parse result
    local raw_file
    raw_file=$(mktemp)
    printf '%s' "$raw_output" > "$raw_file"

    local parsed_json
    parsed_json=$(parse_audit_result "$raw_file") || {
        # Parse failure — store raw output, don't block
        warn "Post-phase audit: could not parse LLM output as JSON"
        log_error "Post-phase audit cycle $cycle: JSON parse failed"

        safe_jq_update "$STATE_FILENAME" \
            --argjson cycle "$cycle" \
            --argjson ms "$duration_ms" \
            --arg model "$rev_model" \
            --arg mode "$audit_mode" \
            --arg raw "$(head -c 5000 "$raw_file" | jq -Rs .)" \
            '.phase_audit_results = (.phase_audit_results // []) + [{
                cycle: $cycle,
                audit_result: "parse_error",
                model: $model,
                mode: $mode,
                duration_ms: $ms,
                phase_audit_raw: $raw,
                timestamp: (now | todate)
            }]'

        rm -f "$raw_file"
        return 0
    }
    rm -f "$raw_file"

    # Extract results
    local audit_result gap_count critical_count minor_count summary
    audit_result=$(echo "$parsed_json" | jq -r '.audit_result // "unknown"')
    gap_count=$(echo "$parsed_json" | jq '[.gaps // [] | .[] ] | length')
    critical_count=$(echo "$parsed_json" | jq '[.gaps // [] | .[] | select(.severity == "critical")] | length')
    minor_count=$(echo "$parsed_json" | jq '[.gaps // [] | .[] | select(.severity == "minor")] | length')
    summary=$(echo "$parsed_json" | jq -r '.summary // ""')

    # Store result in state
    safe_jq_update "$STATE_FILENAME" \
        --argjson cycle "$cycle" \
        --argjson ms "$duration_ms" \
        --arg model "$rev_model" \
        --arg mode "$audit_mode" \
        --arg result "$audit_result" \
        --argjson gaps "$(echo "$parsed_json" | jq '.gaps // []')" \
        --arg summary "$summary" \
        '.phase_audit_results = (.phase_audit_results // []) + [{
            cycle: $cycle,
            audit_result: $result,
            model: $model,
            mode: $mode,
            duration_ms: $ms,
            gaps: $gaps,
            summary: $summary,
            timestamp: (now | todate)
        }]'

    # Log and emit events
    local duration_secs=$(( duration_ms / 1000 ))
    if [[ "$audit_result" == "gaps_found" || "$gap_count" -gt 0 ]]; then
        log_info "Post-phase audit cycle $cycle: $gap_count gaps ($critical_count critical, $minor_count minor) in ${duration_secs}s"
        warn "Post-phase audit: $gap_count gaps found ($critical_count critical, $minor_count minor)"
        emit_event "AUDIT_GAPS" "" "{\"cycle\":$cycle,\"gap_count\":$gap_count,\"critical_count\":$critical_count,\"minor_count\":$minor_count,\"duration_ms\":$duration_ms}"

        # Export gap descriptions for replan prompt injection
        local gap_descriptions
        gap_descriptions=$(echo "$parsed_json" | jq -r '
            [.gaps // [] | .[] | "- [\(.severity)] \(.description) (ref: \(.spec_reference // "n/a"))\n  Suggested scope: \(.suggested_scope // "n/a")"] | join("\n")
        ')
        export _REPLAN_AUDIT_GAPS="$gap_descriptions"
    else
        log_info "Post-phase audit cycle $cycle: clean in ${duration_secs}s"
        info "Post-phase audit: all spec sections covered"
        emit_event "AUDIT_CLEAN" "" "{\"cycle\":$cycle,\"duration_ms\":$duration_ms}"
        export _REPLAN_AUDIT_GAPS=""
    fi
}
