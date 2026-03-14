#!/usr/bin/env bash
# lib/orchestration/planner.sh — Planning, validation, replanning
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.

# ─── Spec Summarization ──────────────────────────────────────────────

# Estimate token count from word count (rough: words × 1.3)
# Migrated to: planner.py estimate_tokens()
estimate_tokens() {
    local file="$1"
    local words
    words=$(wc -w < "$file" 2>/dev/null || echo 0)
    echo $(( (words * 13 + 5) / 10 ))
}

# Summarize a large spec document for decomposition
# Migrated to: planner.py summarize_spec()
summarize_spec() {
    local spec_file="$1"
    local phase_hint="$2"
    local sum_model="${3:-$DEFAULT_SUMMARIZE_MODEL}"
    wt-orch-core plan summarize-spec --spec-file "$spec_file" \
        ${phase_hint:+--phase-hint "$phase_hint"} \
        ${sum_model:+--model "$sum_model"}
}

# ─── Test Infrastructure Detection ────────────────────────────────────

# Migrated to: planner.py detect_test_infra()
detect_test_infra() {
    local project_dir="${1:-.}"
    wt-orch-core plan detect-test-infra --project-dir "$project_dir"
}

# Migrated to: planner.py _auto_detect_test_command()
auto_detect_test_command() {
    local project_dir="${1:-.}"
    # Called only by detect_test_infra, now handled internally by Python
    detect_test_infra "$project_dir" | jq -r '.test_command'
}

# ─── Plan Validation ─────────────────────────────────────────────────

# Migrated to: planner.py validate_plan()
validate_plan() {
    local plan_file="$1"
    local digest_arg=""
    if [[ "${INPUT_MODE:-}" == "digest" && -n "${DIGEST_DIR:-}" ]]; then
        digest_arg="--digest-dir $DIGEST_DIR"
    fi
    local result
    result=$(wt-orch-core plan validate --plan-file "$plan_file" $digest_arg 2>&1)
    local rc=$?

    # Display errors and warnings from JSON output
    local errors warnings
    errors=$(echo "$result" | jq -r '.errors[]?' 2>/dev/null || true)
    warnings=$(echo "$result" | jq -r '.warnings[]?' 2>/dev/null || true)
    [[ -n "$errors" ]] && while IFS= read -r e; do error "$e"; done <<< "$errors"
    [[ -n "$warnings" ]] && while IFS= read -r w; do warn "$w"; done <<< "$warnings"

    return $rc
}

# Migrated to: planner.py check_scope_overlap()
check_scope_overlap() {
    local plan_file="$1"
    local state_arg="" pk_arg=""
    [[ -f "${STATE_FILENAME:-}" ]] && state_arg="--state-file $STATE_FILENAME"
    local pk_file
    pk_file=$(find_project_knowledge_file)
    [[ -n "$pk_file" ]] && pk_arg="--pk-file $pk_file"

    local result
    result=$(wt-orch-core plan check-scope-overlap --plan-file "$plan_file" $state_arg $pk_arg 2>/dev/null)
    local warning_count
    warning_count=$(echo "$result" | jq '.warnings | length' 2>/dev/null || echo 0)

    if [[ "$warning_count" -gt 0 ]]; then
        echo "$result" | jq -r '.warnings[] | "Scope overlap: \(.name_a) ↔ \(.name_b) (\(.similarity)%)"' | while IFS= read -r w; do
            warn "$w"
        done
        send_notification "wt-orchestrate" "Plan has $warning_count scope overlap warning(s) — review for duplicates" "normal"
    fi
}

# Find project-knowledge.yaml — delegates to wt_find_config fallback chain
find_project_knowledge_file() {
    wt_find_config project-knowledge
}

# ─── Triage Gate ─────────────────────────────────────────────────────

# Migrated to: planner.py check_triage_gate()
# NOTE: auto-defer mode in bash also calls generate_triage_md + merge_triage_to_ambiguities
# from digest.sh. The Python version only does the gate check; the bash caller handles
# triage generation/merging for auto-defer separately if needed.
check_triage_gate() {
    local auto_defer_flag=""
    [[ "${TRIAGE_AUTO_DEFER:-false}" == "true" ]] && auto_defer_flag="--auto-defer"

    local result
    result=$(wt-orch-core plan check-triage --digest-dir "${DIGEST_DIR:-}" $auto_defer_flag 2>/dev/null)

    # For auto-defer mode, still need to run the bash-side triage file generation
    if [[ "${TRIAGE_AUTO_DEFER:-false}" == "true" && "$result" == "passed" ]]; then
        if [[ ! -f "$DIGEST_DIR/triage.md" ]]; then
            generate_triage_md "$DIGEST_DIR/ambiguities.json" "$DIGEST_DIR/triage.md"
        fi
        local auto_decisions
        auto_decisions=$(jq '[.ambiguities[].id] | map({key: ., value: {decision: "defer", note: ""}}) | from_entries' "$DIGEST_DIR/ambiguities.json")
        merge_triage_to_ambiguities "$DIGEST_DIR/ambiguities.json" "$auto_decisions" "auto"
        local amb_count
        amb_count=$(jq '.ambiguities | length' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || echo 0)
        info "Auto-deferred $amb_count ambiguities (automated mode)"
    fi

    echo "$result"
}

# ─── Subcommands ─────────────────────────────────────────────────────

cmd_plan() {
    local show_only=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --show) show_only=true; shift ;;
            *) error "Unknown option: $1"; return 1 ;;
        esac
    done

    # Show existing plan
    if $show_only; then
        if [[ ! -f "$PLAN_FILENAME" ]]; then
            error "No plan found. Run 'wt-orchestrate plan' first."
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

    # Auto-digest trigger: if directory input, ensure digest exists and is fresh
    if [[ "$INPUT_MODE" == "digest" ]]; then
        local freshness
        freshness=$(check_digest_freshness "$INPUT_PATH")
        case "$freshness" in
            fresh)
                info "Using existing digest (fresh)"
                ;;
            stale)
                # Double-check: recompute hash to catch false stale (finding #21)
                local _stored_hash _current_hash
                _stored_hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json" 2>/dev/null || echo "")
                _current_hash=$(scan_spec_directory "$INPUT_PATH" 2>/dev/null | jq -r '.source_hash' 2>/dev/null || echo "none")
                if [[ -n "$_stored_hash" && "$_stored_hash" == "$_current_hash" ]]; then
                    info "Hash re-check: still fresh, skipping re-digest"
                    log_info "Digest hash re-check passed — skipping re-digest (hash=$_stored_hash)"
                else
                    info "Digest is stale — auto-re-digesting..."
                    log_info "Auto-digest triggered (stale, stored=$_stored_hash current=$_current_hash)"
                    cmd_digest --spec "$INPUT_PATH" || {
                        error "Auto-digest failed"
                        return 1
                    }
                fi
                ;;
            missing)
                info "Auto-generating digest..."
                log_info "Auto-digest triggered (no existing digest)"
                cmd_digest --spec "$INPUT_PATH" || {
                    error "Auto-digest failed"
                    return 1
                }
                ;;
        esac
    fi

    # Triage gate: check ambiguities before planning
    if [[ "$INPUT_MODE" == "digest" ]]; then
        local triage_result
        triage_result=$(check_triage_gate)
        case "$triage_result" in
            no_ambiguities)
                ;; # proceed
            needs_triage)
                # Generate triage.md and pause
                generate_triage_md "$DIGEST_DIR/ambiguities.json" "$DIGEST_DIR/triage.md"
                local _nt_count
                _nt_count=$(jq '.ambiguities | length' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || echo 0)
                info "Triage required: $_nt_count ambiguities detected."
                info "Review $DIGEST_DIR/triage.md, then re-run plan."
                return 0
                ;;
            has_untriaged)
                local _ut_count
                _ut_count=$(parse_triage_md "$DIGEST_DIR/triage.md" | jq '[.[] | select(.decision == "")] | length')
                info "$_ut_count untriaged ambiguities remain. Review $DIGEST_DIR/triage.md."
                return 0
                ;;
            has_fixes)
                local _fx_count
                _fx_count=$(parse_triage_md "$DIGEST_DIR/triage.md" | jq '[.[] | select(.decision == "fix")] | length')
                info "$_fx_count ambiguities marked 'fix' — update specs and re-run digest."
                return 0
                ;;
            passed)
                local _triage_decisions
                _triage_decisions=$(parse_triage_md "$DIGEST_DIR/triage.md")
                merge_triage_to_ambiguities "$DIGEST_DIR/ambiguities.json" "$_triage_decisions"
                info "Triage complete — proceeding with planning"
                ;;
        esac
    fi

    # Resolve directives (4-level precedence chain)
    local directives
    # In digest mode, resolve from index.json (no document directives)
    if [[ "$INPUT_MODE" == "digest" ]]; then
        directives=$(load_config_file)
        # Apply defaults for missing keys
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

    # Export require_full_coverage for populate_coverage() to read
    export REQUIRE_FULL_COVERAGE
    REQUIRE_FULL_COVERAGE=$(echo "$directives" | jq -r '.require_full_coverage // false')

    # Check if agent-based planning is requested
    local plan_method
    plan_method=$(echo "$directives" | jq -r '.plan_method // "api"')
    if [[ "$plan_method" == "agent" ]]; then
        export _PLAN_METHOD="agent"
        info "Using agent-based decomposition (plan_method: agent)"
        if plan_via_agent "$INPUT_PATH" "${PHASE_HINT:-}"; then
            # Agent produced and validated the plan — add remaining metadata
            local plan_version=1
            if [[ -f "$PLAN_FILENAME" ]]; then
                plan_version=$(jq -r '.plan_version // 1' "$PLAN_FILENAME")
            fi

            # Save plan history
            local _proj_root
            _proj_root=$(dirname "$PLAN_FILENAME")
            if [[ -d "${_proj_root}/wt/orchestration/plans" ]]; then
                local plan_date
                plan_date=$(date +%Y%m%d)
                cp "$PLAN_FILENAME" "${_proj_root}/wt/orchestration/plans/plan-v${plan_version}-${plan_date}.json"
            fi

            success "Plan created: $(jq '.changes | length' "$PLAN_FILENAME") changes (v$plan_version, agent)"
            cmd_plan --show
            echo ""
            info "Review the plan above. Start with: wt-orchestrate start"
            return 0
        else
            warn "Agent-based planning failed — falling back to API method"
            log_warn "plan_via_agent failed, falling back to API-based planning"
            export _PLAN_METHOD="api"
        fi
    else
        export _PLAN_METHOD="api"
    fi

    # Brief mode: validate Next items exist (already checked in find_input, but log count)
    if [[ "$INPUT_MODE" == "brief" ]]; then
        local next_items
        next_items=$(parse_next_items "$INPUT_PATH")
        local item_count
        item_count=$(echo "$next_items" | jq 'length')
        info "Found $item_count roadmap items in Next section"
    fi

    # Collect context for Claude
    local existing_specs=""
    if [[ -d "openspec/specs" ]]; then
        existing_specs=$(ls -1 openspec/specs/ 2>/dev/null | head -20 | tr '\n' ', ')
    fi

    local active_changes=""
    if [[ -d "openspec/changes" ]]; then
        active_changes=$(ls -1 openspec/changes/ 2>/dev/null | { grep -v archive || true; } | head -10 | tr '\n' ', ')
    fi

    local memory_context=""
    if command -v wt-memory &>/dev/null; then
        if [[ "$INPUT_MODE" == "brief" ]]; then
            # Per-roadmap-item recall in brief mode
            local next_items
            next_items=$(parse_next_items "$INPUT_PATH")
            local item_texts=()
            while IFS= read -r item; do
                [[ -z "$item" ]] && continue
                local item_mem
                item_mem=$(orch_recall "$item" 2 "phase:planning" || true)
                [[ -n "$item_mem" ]] && item_texts+=("$item_mem")
            done < <(echo "$next_items" | jq -r '.[]' 2>/dev/null)
            # Also recall orchestrator operational context
            local orch_mem
            orch_mem=$(orch_recall "orchestration merge conflict test failure" 3 "phase:orchestration" || true)
            [[ -n "$orch_mem" ]] && item_texts+=("$orch_mem")
            memory_context=$(printf '%s\n' "${item_texts[@]}" | head -c 2000)
        else
            # Spec mode: recall using phase hint or general query + orchestrator context
            local spec_query="${PHASE_HINT:-project architecture and features}"
            memory_context=$(orch_recall "$spec_query" 3 "phase:planning" || true)
            local orch_mem
            orch_mem=$(orch_recall "orchestration merge conflict test failure" 3 "phase:orchestration" || true)
            [[ -n "$orch_mem" ]] && memory_context="${memory_context}
${orch_mem}"
            memory_context=$(echo "$memory_context" | head -c 2000)
        fi
    fi

    # Detect test infrastructure (TP-1)
    local test_infra_json
    test_infra_json=$(detect_test_infra ".")
    log_info "Test infrastructure scan: $test_infra_json"

    local test_infra_context=""
    local ti_framework ti_config ti_count ti_helpers ti_cmd
    ti_framework=$(echo "$test_infra_json" | jq -r '.framework')
    ti_config=$(echo "$test_infra_json" | jq -r '.config_exists')
    ti_count=$(echo "$test_infra_json" | jq -r '.test_file_count')
    ti_helpers=$(echo "$test_infra_json" | jq -r '.has_helpers')
    ti_cmd=$(echo "$test_infra_json" | jq -r '.test_command')

    if [[ "$ti_config" == "true" || "$ti_count" -gt 0 ]]; then
        test_infra_context="Test Infrastructure:
- Framework: $ti_framework ($([[ "$ti_config" == "true" ]] && echo "config found" || echo "no config"))
- Test files: $ti_count existing
- Helpers: $([[ "$ti_helpers" == "true" ]] && echo "found" || echo "none")
- Test command: ${ti_cmd:-none detected}"
    else
        test_infra_context="Test Infrastructure: NONE — first change must set up test framework"
    fi

    # Detect design MCP and validate connectivity (preflight gate)
    local design_context=""
    # Snapshot dir: same directory as STATE_FILENAME (project root for orchestration files)
    local _snapshot_dir
    _snapshot_dir="$(dirname "${STATE_FILENAME:-orchestration-state.json}")"
    export DESIGN_SNAPSHOT_DIR="$_snapshot_dir"

    if setup_design_bridge 2>/dev/null; then
        log_info "Design bridge active: $DESIGN_MCP_NAME (ref: ${DESIGN_FILE_REF:-none})"

        # Preflight: verify MCP is authenticated before decomposition
        if check_design_mcp_health 2>/dev/null; then
            log_info "Design MCP preflight passed"

            # Fetch design snapshot (re-fetch on replan cycles)
            local _snap_force=""
            [[ -n "${_REPLAN_CYCLE:-}" ]] && _snap_force="force"
            if fetch_design_snapshot "$_snap_force" 2>/dev/null; then
                log_info "Design snapshot available"
            else
                log_warn "Design snapshot fetch failed — using generic design context"
            fi

            design_context=$(design_prompt_section "$DESIGN_MCP_NAME" "$_snapshot_dir")
        else
            log_warn "Design MCP preflight failed — triggering mcp_auth checkpoint"
            trigger_checkpoint "mcp_auth"

            # After approval, retry once
            if check_design_mcp_health 2>/dev/null; then
                log_info "Design MCP preflight passed after approval"

                # Also fetch snapshot after successful retry
                local _snap_force=""
                [[ -n "${_REPLAN_CYCLE:-}" ]] && _snap_force="force"
                if fetch_design_snapshot "$_snap_force" 2>/dev/null; then
                    log_info "Design snapshot available"
                else
                    log_warn "Design snapshot fetch failed — using generic design context"
                fi

                design_context=$(design_prompt_section "$DESIGN_MCP_NAME" "$_snapshot_dir")
            else
                log_warn "Design MCP still not authenticated after approval — proceeding without design context"
            fi
        fi
    fi

    # Migrated to: planner.py build_decomposition_context() + _build_digest_content()
    # Compute hash (still needed for metadata)
    local hash
    if [[ "$INPUT_MODE" == "digest" ]]; then
        hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json")
    else
        hash=$(brief_hash "$INPUT_PATH")
    fi

    # Build replan context object
    local replan_json='{}'
    if [[ -n "${_REPLAN_COMPLETED:-}" || -n "${_REPLAN_MEMORY:-}" || -n "${_REPLAN_E2E_FAILURES:-}" || -n "${_REPLAN_AUDIT_GAPS:-}" ]]; then
        replan_json=$(jq -n \
            --arg completed "${_REPLAN_COMPLETED:-}" \
            --argjson cycle "${_REPLAN_CYCLE:-1}" \
            --arg memory "${_REPLAN_MEMORY:-}" \
            --arg e2e_failures "${_REPLAN_E2E_FAILURES:-}" \
            --arg audit_gaps "${_REPLAN_AUDIT_GAPS:-}" \
            '{completed: $completed, cycle: $cycle, memory: $memory, e2e_failures: $e2e_failures, audit_gaps: $audit_gaps}')
    fi

    # Pre-compute coverage info for digest mode
    local coverage_info=""
    if [[ "$INPUT_MODE" == "digest" && -f "$DIGEST_DIR/coverage.json" ]]; then
        local cov_merged cov_running
        cov_merged=$(jq -r '[.coverage | to_entries[] | select(.value.status == "merged") | .key] | join(", ")' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
        cov_running=$(jq -r '[.coverage | to_entries[] | select(.value.status == "running") | .key] | join(", ")' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
        [[ -n "$cov_merged" ]] && coverage_info+="Already covered (merged): $cov_merged"$'\n'
        [[ -n "$cov_running" ]] && coverage_info+="Already covered (running): $cov_running"
    fi

    # Build input JSON and render via Python (handles digest content building + prompt rendering)
    local _input_path_for_python
    if [[ "$INPUT_MODE" == "digest" ]]; then
        _input_path_for_python="$DIGEST_DIR"
    else
        _input_path_for_python="$INPUT_PATH"
    fi

    local _plan_input_file
    _plan_input_file=$(mktemp)
    jq -n \
        --arg input_path "$_input_path_for_python" \
        --arg input_mode "$INPUT_MODE" \
        --arg specs "$existing_specs" \
        --arg memory "${memory_context:-}" \
        --argjson replan_ctx "$replan_json" \
        --arg phase_instruction "${PHASE_HINT:+The user requested phase: $PHASE_HINT. Focus decomposition on items matching this phase.}" \
        --arg test_infra_context "$test_infra_context" \
        --arg active_changes "$active_changes" \
        --arg coverage_info "$coverage_info" \
        --arg design_context "${design_context:-}" \
        --argjson team_mode "$([ "${TEAM_MODE:-false}" = "true" ] && echo true || echo false)" \
        '{input_path: $input_path, input_mode: $input_mode, specs: $specs, memory: $memory, replan_ctx: $replan_ctx, phase_instruction: $phase_instruction, test_infra_context: $test_infra_context, active_changes: $active_changes, coverage_info: $coverage_info, design_context: $design_context, team_mode: $team_mode}' \
        > "$_plan_input_file"

    local prompt
    prompt=$(wt-orch-core plan build-context --input-file "$_plan_input_file")
    rm -f "$_plan_input_file"

    info "Calling Claude for decomposition..."
    log_info "Plan decomposition started (brief hash: $hash)"

    # Heartbeat: emit periodic events so sentinel doesn't think we're stuck during long API call
    local _hb_marker
    _hb_marker=$(mktemp)
    (
        local _hb_count=0
        while [[ -f "$_hb_marker" ]]; do
            sleep 60
            [[ -f "$_hb_marker" ]] || break
            _hb_count=$((_hb_count + 1))
            emit_event "PLAN_HEARTBEAT" "" "{\"minutes\":$_hb_count}" 2>/dev/null || true
        done
    ) &
    local _heartbeat_pid=$!

    local claude_output
    # NOTE: No MCP tools for decompose — design context is already in the prompt text.
    # RUN_CLAUDE_NO_MCP: prevents both DESIGN_MCP_CONFIG injection AND .claude/settings.json
    # MCP registrations (e.g. Figma) from consuming turns with tool calls.
    claude_output=$(export RUN_CLAUDE_NO_MCP=1 RUN_CLAUDE_TIMEOUT=2400; echo "$prompt" | run_claude --model "$(model_id opus)" --max-turns 1) || {
        rm -f "$_hb_marker"
        kill "$_heartbeat_pid" 2>/dev/null; wait "$_heartbeat_pid" 2>/dev/null || true
        error "Claude decomposition failed. Check your Claude CLI setup."
        log_error "Claude decomposition failed"
        return 1
    }
    rm -f "$_hb_marker"
    kill "$_heartbeat_pid" 2>/dev/null; wait "$_heartbeat_pid" 2>/dev/null || true

    log_info "Claude decomposition response received (${#claude_output} chars)"
    # Save raw output for debugging
    local response_file=".claude/orchestration-last-response.txt"
    printf '%s' "$claude_output" > "$response_file" 2>/dev/null

    # Extract JSON from response (Claude may wrap in markdown)
    local plan_json
    plan_json=$(python3 - "$response_file" <<'PYEOF'
import json, sys, re
with open(sys.argv[1]) as f:
    raw = f.read()
# Strategy: try multiple extraction methods
best_err = ''
# 1. Direct parse
try:
    data = json.loads(raw)
    if 'changes' in data:
        print(json.dumps(data))
        sys.exit(0)
except Exception as e:
    best_err = str(e)
# 2. Strip markdown code fences and retry
stripped = re.sub(r'```(?:json|JSON)?\s*\n?', '', raw).strip()
try:
    data = json.loads(stripped)
    if 'changes' in data:
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
                if 'changes' in data:
                    print(json.dumps(data))
                    sys.exit(0)
            except Exception:
                continue
print('ERROR: Could not parse JSON from Claude output', file=sys.stderr)
print('Parse error: ' + best_err, file=sys.stderr)
print('Raw (first 1000): ' + repr(raw[:1000]), file=sys.stderr)
sys.exit(1)
PYEOF
) || {
        error "Could not parse Claude's response as JSON"
        log_error "JSON parse failed from Claude output"
        return 1
    }

    # Migrated to: planner.py enrich_plan_metadata()
    # Write raw plan JSON, then enrich via Python CLI
    echo "$plan_json" > "$PLAN_FILENAME"

    local enrich_args=(
        --plan-file "$PLAN_FILENAME"
        --hash "$hash"
        --input-mode "$INPUT_MODE"
        --input-path "$INPUT_PATH"
    )
    [[ -n "${_REPLAN_CYCLE:-}" ]] && enrich_args+=(--replan-cycle "$_REPLAN_CYCLE")
    [[ -n "${_REPLAN_CYCLE:-}" && -f "$STATE_FILENAME" ]] && enrich_args+=(--state-file "$STATE_FILENAME")

    wt-orch-core plan enrich-metadata "${enrich_args[@]}"

    # Validate
    if ! validate_plan "$PLAN_FILENAME"; then
        error "Plan validation failed. Review $PLAN_FILENAME manually."
        return 1
    fi

    # Populate coverage mapping for digest-mode plans
    if [[ "$INPUT_MODE" == "digest" && -f "$DIGEST_DIR/requirements.json" ]]; then
        if ! populate_coverage "$PLAN_FILENAME"; then
            error "Plan validation failed: incomplete requirement coverage"
            return 1
        fi
    fi

    # Merge planner's ambiguity resolutions back into ambiguities.json
    if [[ "$INPUT_MODE" == "digest" && -f "$DIGEST_DIR/ambiguities.json" ]]; then
        merge_planner_resolutions "$DIGEST_DIR/ambiguities.json" "$PLAN_FILENAME"
    fi

    generate_report 2>/dev/null || true

    local change_count
    change_count=$(jq '.changes | length' "$PLAN_FILENAME")

    # Save plan history copy to wt/orchestration/plans/ if directory exists
    local plans_dir
    plans_dir=$(dirname "$PLAN_FILENAME")
    # Check for wt/orchestration/plans/ relative to project root
    local _proj_root
    _proj_root=$(dirname "$PLAN_FILENAME")  # PLAN_FILENAME is absolute
    # Go up to project root (PLAN_FILENAME is at project root level)
    if [[ -d "${_proj_root}/wt/orchestration/plans" ]]; then
        local plan_date
        plan_date=$(date +%Y%m%d)
        local plan_copy="${_proj_root}/wt/orchestration/plans/plan-v${plan_version}-${plan_date}.json"
        cp "$PLAN_FILENAME" "$plan_copy"
        log_info "Plan history saved: $plan_copy"
    fi

    success "Plan created: $change_count changes (v$plan_version)"
    log_info "Plan created: $change_count changes (v$plan_version, mode=$INPUT_MODE)"

    # Show phase detection for digest mode
    if [[ "$INPUT_MODE" == "digest" ]]; then
        local phase_detected
        phase_detected=$(jq -r '.phase_detected // empty' "$PLAN_FILENAME")
        if [[ -n "$phase_detected" ]]; then
            echo ""
            info "Phase detected: $phase_detected"
        fi
        local reasoning
        reasoning=$(jq -r '.reasoning // empty' "$PLAN_FILENAME")
        if [[ -n "$reasoning" ]]; then
            info "Reasoning: $reasoning"
        fi
    fi

    # Show summary
    cmd_plan --show
    echo ""
    info "Review the plan above. Start with: wt-orchestrate start"
}

# Agent-based planning: create a planning worktree, dispatch Ralph loop with
# decomposition skill, wait for completion, extract orchestration-plan.json.
# Returns 0 on success (plan extracted), 1 on failure (caller should fallback to API).
plan_via_agent() {
    local spec_path="$1"
    local phase_hint="${2:-}"

    # Determine planning worktree name
    local plan_version=1
    if [[ -f "$PLAN_FILENAME" ]]; then
        plan_version=$(( $(jq -r '.plan_version // 0' "$PLAN_FILENAME") + 1 ))
    fi
    local wt_name="wt-planning-v${plan_version}"

    info "Agent-based decomposition: creating planning worktree $wt_name..."
    log_info "plan_via_agent: starting (spec=$spec_path, phase_hint=$phase_hint)"

    # Create planning worktree
    local wt_path
    wt_path=$(wt-new "$wt_name" 2>/dev/null) || {
        log_error "plan_via_agent: failed to create worktree $wt_name"
        return 1
    }
    # wt-new outputs the path on stdout
    if [[ -z "$wt_path" || ! -d "$wt_path" ]]; then
        # Try finding it
        wt_path=$(git worktree list --porcelain 2>/dev/null | grep "^worktree.*${wt_name}" | head -1 | sed 's/^worktree //')
        if [[ -z "$wt_path" || ! -d "$wt_path" ]]; then
            log_error "plan_via_agent: worktree path not found for $wt_name"
            return 1
        fi
    fi
    log_info "plan_via_agent: worktree created at $wt_path"

    # Build task description for Ralph
    local task_desc="Decompose the specification at '$spec_path' into an orchestration execution plan."
    if [[ -n "$phase_hint" ]]; then
        task_desc="$task_desc Focus on phase: $phase_hint."
    fi
    task_desc="$task_desc Use the /wt:decompose skill. Write the result to orchestration-plan.json in the project root."

    # Set environment for the planning agent
    export SPEC_PATH="$spec_path"
    [[ -n "$phase_hint" ]] && export PHASE_HINT="$phase_hint"

    # Dispatch Ralph loop
    info "Dispatching planning agent..."
    local loop_rc=0
    (
        cd "$wt_path" || exit 1
        wt-loop start "$task_desc" \
            --max 10 \
            --model opus \
            --label "$wt_name" \
            --change "$wt_name" 2>&1
    ) || loop_rc=$?

    unset SPEC_PATH PHASE_HINT

    # Check if plan was produced
    local agent_plan="$wt_path/orchestration-plan.json"
    if [[ ! -f "$agent_plan" ]]; then
        log_error "plan_via_agent: no orchestration-plan.json produced (loop rc=$loop_rc)"
        # Cleanup
        wt-close "$wt_name" --force 2>/dev/null || true
        return 1
    fi

    # Validate the agent-produced plan
    if ! validate_plan "$agent_plan"; then
        log_error "plan_via_agent: agent plan failed validation"
        wt-close "$wt_name" --force 2>/dev/null || true
        return 1
    fi

    # Extract plan to project root
    cp "$agent_plan" "$PLAN_FILENAME"
    log_info "plan_via_agent: plan extracted from $agent_plan"

    # Add agent-specific metadata
    local tmp_plan
    tmp_plan=$(mktemp)
    jq --arg wt "$wt_name" '. + {planning_worktree: $wt}' "$PLAN_FILENAME" > "$tmp_plan" && mv "$tmp_plan" "$PLAN_FILENAME"

    # Cleanup planning worktree
    info "Cleaning up planning worktree..."
    wt-close "$wt_name" --force 2>/dev/null || {
        log_warn "plan_via_agent: failed to cleanup worktree $wt_name (non-fatal)"
    }

    success "Agent-based decomposition complete"
    return 0
}

cmd_replan() {
    find_input || return 1

    info "Replanning from updated input ($INPUT_MODE: $INPUT_PATH)..."

    # Gather current state context
    local state_context=""
    if [[ -f "$STATE_FILENAME" ]]; then
        state_context=$(jq '{
            merged: [.changes[] | select(.status == "merged") | .name],
            running: [.changes[] | select(.status == "running") | .name],
            pending: [.changes[] | select(.status == "pending") | .name],
            failed: [.changes[] | select(.status == "failed" or .status == "stalled") | .name]
        }' "$STATE_FILENAME")
    fi

    # Call plan with state context injected
    cmd_plan
    info "Replan complete. Review and run 'wt-orchestrate start' to apply."
}

# Auto-replan cycle: re-run plan from spec, integrate new changes into state.
# Returns 0 if new changes were found and dispatched, 1 if nothing new.
auto_replan_cycle() {
    local directives="$1"
    local cycle="$2"
    local max_parallel
    max_parallel=$(echo "$directives" | jq -r '.max_parallel')

    # Migrated to: planner.py collect_replan_context()
    local replan_ctx
    replan_ctx=$(wt-orch-core plan replan-context --state-file "$STATE_FILENAME")

    local completed_names completed_roadmap
    completed_names=$(echo "$replan_ctx" | jq -r '.completed_names')
    completed_roadmap=$(echo "$replan_ctx" | jq -r '.completed_roadmap')

    log_info "========== REPLAN CYCLE $cycle =========="
    info "Completed so far: $completed_names"
    log_info "Auto-replan cycle $cycle — completed: $completed_names"

    # Git history protection: tag the phase boundary for recovery
    git tag -f "orch/phase-${cycle}-complete" HEAD 2>/dev/null || true
    log_info "Tagged: orch/phase-${cycle}-complete"

    emit_event "REPLAN" "" "{\"cycle\":$cycle,\"completed\":\"$completed_names\"}"

    # Re-run plan (cmd_plan knows how to handle spec mode, phase hints, etc.)
    local old_plan
    old_plan=$(mktemp)
    cp "$PLAN_FILENAME" "$old_plan"

    # Store completed info for the planner prompt to use
    export _REPLAN_COMPLETED="$completed_roadmap"
    export _REPLAN_CYCLE="$cycle"

    # Append file context from Python replan-context output
    local completed_file_context
    completed_file_context=$(echo "$replan_ctx" | jq -r '.file_context')
    if [[ -n "$completed_file_context" ]]; then
        _REPLAN_COMPLETED="${_REPLAN_COMPLETED}

Files modified by completed changes (avoid re-implementing):
$completed_file_context"
        export _REPLAN_COMPLETED
    fi

    # Recall orchestrator operational history for replan context (bash-side — uses wt-memory)
    local replan_memory
    replan_memory=$(orch_recall "orchestration merge conflict test failure review" 5 "phase:orchestration" || true)
    if [[ -n "$replan_memory" ]]; then
        export _REPLAN_MEMORY="${replan_memory:0:2000}"
    fi

    # E2E failure context from Python replan-context output
    local phase_e2e_ctx
    phase_e2e_ctx=$(echo "$replan_ctx" | jq -r '.e2e_failures')
    if [[ -n "$phase_e2e_ctx" ]]; then
        export _REPLAN_E2E_FAILURES="$phase_e2e_ctx"
    fi

    # Restore input path from plan so cmd_plan's find_input() can find it
    local plan_input_mode plan_input_path
    plan_input_mode=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
    plan_input_path=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
    if [[ "$plan_input_mode" == "spec" && -n "$plan_input_path" ]]; then
        SPEC_OVERRIDE="$plan_input_path"
    elif [[ "$plan_input_mode" == "digest" && -n "$plan_input_path" ]]; then
        SPEC_OVERRIDE="$plan_input_path"
    elif [[ "$plan_input_mode" == "brief" && -n "$plan_input_path" ]]; then
        BRIEF_OVERRIDE="$plan_input_path"
    fi

    if ! cmd_plan &>>"$LOG_FILE"; then
        log_error "Auto-replan failed — cmd_plan returned error"
        rm -f "$old_plan"
        unset _REPLAN_COMPLETED _REPLAN_CYCLE _REPLAN_MEMORY _REPLAN_E2E_FAILURES _REPLAN_AUDIT_GAPS
        return 2  # Error (distinct from 1=no new work)
    fi
    unset _REPLAN_COMPLETED _REPLAN_CYCLE _REPLAN_MEMORY _REPLAN_E2E_FAILURES

    # Check if new plan has actionable changes not already completed
    local new_changes
    new_changes=$(jq -c '[.changes[].name]' "$PLAN_FILENAME")
    local completed_changes
    completed_changes=$(jq -c '[.changes[]? | select(.status == "done" or .status == "merged" or .status == "merge-blocked") | .name]' "$STATE_FILENAME")
    rm -f "$old_plan"

    local novel_count
    novel_count=$(python3 -c "
import json, sys
new = set(json.loads(sys.argv[1]))
completed = set(json.loads(sys.argv[2]))
novel = new - completed
print(len(novel))
" "$new_changes" "$completed_changes" 2>/dev/null || echo "0")

    if [[ "$novel_count" -eq 0 ]]; then
        log_info "No new changes found in replan — all work done"
        return 1
    fi

    # Check if ALL novel changes are just re-discoveries of previously failed changes
    local failed_changes
    failed_changes=$(jq -c '[.changes[]? | select(.status == "failed") | .name]' "$STATE_FILENAME")
    local all_failed
    all_failed=$(python3 -c "
import json, sys
new = set(json.loads(sys.argv[1]))
completed = set(json.loads(sys.argv[2]))
failed = set(json.loads(sys.argv[3]))
novel = new - completed
print('true' if novel and novel <= failed else 'false')
" "$new_changes" "$completed_changes" "$failed_changes" 2>/dev/null || echo "false")

    if [[ "$all_failed" == "true" ]]; then
        log_info "Replan only found previously-failed changes — no genuinely new work"
        return 1
    fi

    info "Replan found $novel_count new change(s)"
    log_info "Replan cycle $cycle found $novel_count new changes"

    emit_event "REPLAN" "" "{\"cycle\":$cycle,\"novel_count\":$novel_count,\"status\":\"dispatching\"}"

    # Archive completed changes before re-init (so web can show cumulative tokens)
    local archive_file
    archive_file="$(dirname "$STATE_FILENAME")/state-archive.jsonl"
    jq -c --arg cycle "$cycle" --arg ts "$(date -Iseconds)" \
        '{cycle: ($cycle|tonumber), archived_at: $ts, changes: [.changes[] | select(.status == "done" or .status == "merged" or .status == "merge-blocked" or .status == "failed" or .status == "verify-failed" or .status == "skip_merged")]}' \
        "$STATE_FILENAME" >> "$archive_file" 2>/dev/null || true
    log_info "Archived completed changes to state-archive.jsonl (cycle $cycle)"

    # Re-initialize state from new plan, preserving history
    local prev_total_tokens
    prev_total_tokens=$(jq '[.changes[].tokens_used] | add // 0' "$STATE_FILENAME")
    local prev_cycles
    prev_cycles=$(jq '.replan_cycle // 0' "$STATE_FILENAME")
    local prev_active_seconds
    prev_active_seconds=$(jq '.active_seconds // 0' "$STATE_FILENAME")
    local prev_started_epoch
    prev_started_epoch=$(jq '.started_epoch // 0' "$STATE_FILENAME")
    local prev_time_limit
    prev_time_limit=$(jq '.time_limit_secs // 0' "$STATE_FILENAME")
    local prev_audit_results
    prev_audit_results=$(jq -c '.phase_audit_results // []' "$STATE_FILENAME")
    local prev_e2e_results
    prev_e2e_results=$(jq -c '.phase_e2e_results // []' "$STATE_FILENAME")

    init_state "$PLAN_FILENAME"

    # Restore cumulative metadata
    update_state_field "replan_cycle" "$cycle"
    update_state_field "prev_total_tokens" "$prev_total_tokens"
    update_state_field "active_seconds" "$prev_active_seconds"
    update_state_field "started_epoch" "$prev_started_epoch"
    update_state_field "time_limit_secs" "$prev_time_limit"
    update_state_field "cycle_started_at" "\"$(date -Iseconds)\""
    update_state_field "directives" "$(echo "$directives" | jq -c .)"
    if [[ "$prev_audit_results" != "[]" ]]; then
        safe_jq_update "$STATE_FILENAME" --argjson ar "$prev_audit_results" \
            '.phase_audit_results = $ar'
    fi
    if [[ "$prev_e2e_results" != "[]" ]]; then
        safe_jq_update "$STATE_FILENAME" --argjson er "$prev_e2e_results" \
            '.phase_e2e_results = $er'
    fi

    # Dispatch newly ready changes
    dispatch_ready_changes "$max_parallel"

    return 0
}
