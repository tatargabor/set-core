#!/usr/bin/env bash
# lib/orchestration/planner.sh — Thin wrapper: logic lives in lib/wt_orch/planner.py
#
# Sourced by bin/set-orchestrate for backward compatibility.
# Python implementation: lib/wt_orch/planner.py, cli.py:cmd_plan()
#
# auto_replan_cycle() runs in Python via engine.py:_handle_auto_replan()

# ─── Delegated helpers (thin wrappers to set-orch-core) ───────────────

estimate_tokens() {
    local file="$1"
    local words
    words=$(wc -w < "$file" 2>/dev/null || echo 0)
    echo $(( (words * 13 + 5) / 10 ))
}

summarize_spec() {
    local spec_file="$1"
    local phase_hint="$2"
    local sum_model="${3:-$DEFAULT_SUMMARIZE_MODEL}"
    set-orch-core plan summarize-spec --spec-file "$spec_file" \
        ${phase_hint:+--phase-hint "$phase_hint"} \
        ${sum_model:+--model "$sum_model"}
}

detect_test_infra() {
    local project_dir="${1:-.}"
    set-orch-core plan detect-test-infra --project-dir "$project_dir"
}

validate_plan() {
    local plan_file="$1"
    local digest_arg=""
    if [[ "${INPUT_MODE:-}" == "digest" && -n "${DIGEST_DIR:-}" ]]; then
        digest_arg="--digest-dir $DIGEST_DIR"
    fi
    local result
    result=$(set-orch-core plan validate --plan-file "$plan_file" $digest_arg 2>&1)
    local rc=$?
    local errors warnings
    errors=$(echo "$result" | jq -r '.errors[]?' 2>/dev/null || true)
    warnings=$(echo "$result" | jq -r '.warnings[]?' 2>/dev/null || true)
    [[ -n "$errors" ]] && while IFS= read -r e; do error "$e"; done <<< "$errors"
    [[ -n "$warnings" ]] && while IFS= read -r w; do warn "$w"; done <<< "$warnings"
    return $rc
}

check_scope_overlap() {
    local plan_file="$1"
    local state_arg="" pk_arg=""
    [[ -f "${STATE_FILENAME:-}" ]] && state_arg="--state-file $STATE_FILENAME"
    local pk_file
    pk_file=$(find_project_knowledge_file)
    [[ -n "$pk_file" ]] && pk_arg="--pk-file $pk_file"
    local result
    result=$(set-orch-core plan check-scope-overlap --plan-file "$plan_file" $state_arg $pk_arg 2>/dev/null)
    local warning_count
    warning_count=$(echo "$result" | jq '.warnings | length' 2>/dev/null || echo 0)
    if [[ "$warning_count" -gt 0 ]]; then
        echo "$result" | jq -r '.warnings[] | "Scope overlap: \(.name_a) ↔ \(.name_b) (\(.similarity)%)"' | while IFS= read -r w; do
            warn "$w"
        done
    fi
}

find_project_knowledge_file() {
    wt_find_config project-knowledge
}

check_triage_gate() {
    local auto_defer_flag=""
    [[ "${TRIAGE_AUTO_DEFER:-false}" == "true" ]] && auto_defer_flag="--auto-defer"
    set-orch-core plan check-triage --digest-dir "${DIGEST_DIR:-}" $auto_defer_flag 2>/dev/null
}

# ─── Main CLI entry points ───────────────────────────────────────────

cmd_plan() {
    local show_only=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --show) show_only=true; shift ;;
            *) error "Unknown option: $1"; return 1 ;;
        esac
    done

    # Show existing plan (pure display — stays in bash)
    if $show_only; then
        if [[ ! -f "$PLAN_FILENAME" ]]; then
            error "No plan found. Run 'set-orchestrate plan' first."
            return 1
        fi
        echo ""
        info "═══ Orchestration Plan ═══"
        echo ""
        local pp pm
        pp=$(jq -r '.plan_phase // "initial"' "$PLAN_FILENAME")
        pm=$(jq -r '.plan_method // "api"' "$PLAN_FILENAME")
        echo "  Phase: $pp | Method: $pm"
        echo ""
        jq -r '.changes[] | "  \(.name) [\(.complexity)] (\(.change_type // "feature")) — \(.scope[:80])...\n    depends_on: \(.depends_on | if length == 0 then "(none)" else join(", ") end)"' "$PLAN_FILENAME"
        echo ""
        info "Dependency order:"
        local order
        order=$(topological_sort "$PLAN_FILENAME")
        local i=1
        while IFS= read -r name; do
            echo "  $i. $name"
            i=$((i + 1))
        done <<< "$order"
        echo ""
        return 0
    fi

    # Pre-decomposition memory hygiene (best-effort)
    plan_memory_hygiene || true

    # Find and validate input (spec or brief)
    find_input || return 1

    info "Reading input ($INPUT_MODE): $INPUT_PATH"

    # Resolve directives
    local directives
    if [[ "$INPUT_MODE" == "digest" ]]; then
        directives=$(load_config_file)
        directives=$(echo '{}' | jq --argjson cfg "$directives" \
            --argjson mp "$DEFAULT_MAX_PARALLEL" \
            --arg mpol "$DEFAULT_MERGE_POLICY" \
            --argjson cp "$DEFAULT_CHECKPOINT_EVERY" \
            '{
                max_parallel: ($cfg.max_parallel // $mp),
                merge_policy: ($cfg.merge_policy // $mpol),
                checkpoint_every: ($cfg.checkpoint_every // $cp)
            } + $cfg')
    else
        directives=$(resolve_directives "$INPUT_PATH")
    fi
    info "Directives: $(echo "$directives" | jq -c .)"

    export REQUIRE_FULL_COVERAGE
    REQUIRE_FULL_COVERAGE=$(echo "$directives" | jq -r '.require_full_coverage // false')

    local plan_method
    plan_method=$(echo "$directives" | jq -r '.plan_method // "api"')

    # Auto-digest trigger (needs cmd_digest from bash — stays here)
    if [[ "$INPUT_MODE" == "digest" ]]; then
        local freshness
        freshness=$(check_digest_freshness "$INPUT_PATH")
        case "$freshness" in
            fresh) info "Using existing digest (fresh)" ;;
            stale)
                local _stored_hash _current_hash
                _stored_hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json" 2>/dev/null || echo "")
                _current_hash=$(set-orch-core digest scan --spec "$INPUT_PATH" 2>/dev/null | jq -r '.source_hash' 2>/dev/null || echo "none")
                if [[ -n "$_stored_hash" && "$_stored_hash" == "$_current_hash" ]]; then
                    info "Hash re-check: still fresh, skipping re-digest"
                else
                    info "Digest is stale — auto-re-digesting..."
                    cmd_digest --spec "$INPUT_PATH" || { error "Auto-digest failed"; return 1; }
                fi
                ;;
            missing)
                info "Auto-generating digest..."
                cmd_digest --spec "$INPUT_PATH" || { error "Auto-digest failed"; return 1; }
                ;;
        esac
    fi

    # Delegate planning to Python
    local plan_args=(
        --input-mode "$INPUT_MODE"
        --input-path "${INPUT_PATH}"
        --output "$PLAN_FILENAME"
        --method "$plan_method"
    )
    [[ -f "${STATE_FILENAME:-}" ]] && plan_args+=(--state-file "$STATE_FILENAME")
    [[ -n "${PHASE_HINT:-}" ]] && plan_args+=(--phase-hint "$PHASE_HINT")
    [[ -n "${_REPLAN_CYCLE:-}" ]] && plan_args+=(--replan-cycle "$_REPLAN_CYCLE")
    [[ "${TEAM_MODE:-false}" == "true" ]] && plan_args+=(--team)

    info "Calling Claude for decomposition..."

    local result
    local stderr_file="/tmp/set-decompose-stderr-$$.log"
    result=$(set-orch-core plan run "${plan_args[@]}" 2>"$stderr_file") || {
        local stderr_content
        stderr_content=$(tail -20 "$stderr_file" 2>/dev/null)
        error "Claude decomposition failed."
        [[ -n "$stderr_content" ]] && error "Details: $stderr_content"
        rm -f "$stderr_file"
        return 1
    }
    rm -f "$stderr_file"

    local status
    status=$(echo "$result" | jq -r '.status // "error"')
    if [[ "$status" != "ok" ]]; then
        local err_msg
        err_msg=$(echo "$result" | jq -r '.error // "unknown"')
        error "Planning failed: $err_msg"
        return 1
    fi

    # Post-plan: coverage population (uses digest functions)
    if [[ "$INPUT_MODE" == "digest" && -f "$DIGEST_DIR/requirements.json" ]]; then
        populate_coverage "$PLAN_FILENAME" || { error "Coverage check failed"; return 1; }
    fi
    if [[ "$INPUT_MODE" == "digest" && -f "$DIGEST_DIR/ambiguities.json" ]]; then
        merge_planner_resolutions "$DIGEST_DIR/ambiguities.json" "$PLAN_FILENAME"
    fi

    generate_report 2>/dev/null || true

    local change_count
    change_count=$(jq '.changes | length' "$PLAN_FILENAME")
    local plan_version
    plan_version=$(jq -r '.plan_version // 1' "$PLAN_FILENAME")

    success "Plan created: $change_count changes (v$plan_version)"
    cmd_plan --show
    echo ""
    info "Review the plan above. Start with: set-orchestrate start"
}

cmd_replan() {
    find_input || return 1
    info "Replanning from updated input ($INPUT_MODE: $INPUT_PATH)..."
    cmd_plan
    info "Replan complete. Review and run 'set-orchestrate start' to apply."
}

# auto_replan_cycle() runs in Python via engine.py:_handle_auto_replan()
