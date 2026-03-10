#!/usr/bin/env bash
# lib/orchestration/planner.sh — Planning, validation, replanning
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.

# ─── Spec Summarization ──────────────────────────────────────────────

# Estimate token count from word count (rough: words × 1.3)
estimate_tokens() {
    local file="$1"
    local words
    words=$(wc -w < "$file" 2>/dev/null || echo 0)
    echo $(( (words * 13 + 5) / 10 ))
}

# Summarize a large spec document for decomposition
summarize_spec() {
    local spec_file="$1"
    local phase_hint="$2"
    local sum_model="${3:-$DEFAULT_SUMMARIZE_MODEL}"
    local spec_content
    spec_content=$(cat "$spec_file")

    local phase_instruction=""
    if [[ -n "$phase_hint" ]]; then
        phase_instruction="The user wants to focus on phase: $phase_hint. Extract that phase in full detail."
    fi

    local summary_prompt
    summary_prompt=$(cat <<SUMMARY_EOF
You are a technical analyst. This specification document is too large to process in full.
Create a structured summary for a software architect who needs to decompose it into implementable changes.

## Specification Document
$spec_content

## Task
Create a condensed summary containing:
1. **Table of Contents** with completion status for each section/phase (use markers from the document: checkboxes, emoji, "done"/"implemented"/"kész" etc.)
2. **Next Actionable Phase** — extract the FULL content of the first incomplete phase/priority section
$phase_instruction

Output ONLY the summary in markdown. Keep it under 3000 words.
Do NOT add commentary — just the structured summary.
SUMMARY_EOF
)

    local summary_output
    summary_output=$(echo "$summary_prompt" | run_claude --model "$(model_id "$sum_model")") || {
        log_error "Spec summarization failed — falling back to truncation"
        head -c 32000 "$spec_file"
        return
    }
    log_info "Spec summarization complete (${#summary_output} chars)"
    echo "$summary_output"
}

# ─── Test Infrastructure Detection ────────────────────────────────────

detect_test_infra() {
    local project_dir="${1:-.}"
    local framework=""
    local config_exists=false
    local test_file_count=0
    local has_helpers=false
    local test_command=""

    # Check for test framework configs
    if ls "$project_dir"/vitest.config.* 2>/dev/null | head -1 >/dev/null; then
        framework="vitest"
        config_exists=true
    elif ls "$project_dir"/jest.config.* 2>/dev/null | head -1 >/dev/null; then
        framework="jest"
        config_exists=true
    elif [[ -f "$project_dir/pytest.ini" || -f "$project_dir/pyproject.toml" ]] && grep -q '\[tool\.pytest' "$project_dir/pyproject.toml" 2>/dev/null; then
        framework="pytest"
        config_exists=true
    fi

    # Check package.json for test framework in devDependencies
    if [[ -z "$framework" && -f "$project_dir/package.json" ]]; then
        local pkg_framework
        pkg_framework=$(jq -r '
            (.devDependencies // {} | keys[]) as $k |
            if ($k == "vitest") then "vitest"
            elif ($k == "jest") then "jest"
            elif ($k == "mocha") then "mocha"
            else empty end
        ' "$project_dir/package.json" 2>/dev/null | head -1)
        if [[ -n "$pkg_framework" ]]; then
            framework="$pkg_framework"
        fi
    fi

    # Count test files
    test_file_count=$(find "$project_dir" -type f \( -name "*.test.*" -o -name "*.spec.*" -o -name "test_*.py" \) \
        -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | wc -l)

    # Check for test helper directories and files
    for dir in "src/test" "__tests__" "test" "tests" "src/__tests__"; do
        if [[ -d "$project_dir/$dir" ]]; then
            has_helpers=true
            break
        fi
    done
    if [[ "$has_helpers" != "true" ]]; then
        local helper_count
        helper_count=$(find "$project_dir" -type f \( -name "*test-helper*" -o -name "*factory*" -o -name "*fixtures*" \) \
            -not -path "*/node_modules/*" -not -path "*/.git/*" 2>/dev/null | wc -l)
        [[ "$helper_count" -gt 0 ]] && has_helpers=true
    fi

    # Detect test command from package.json
    test_command=$(auto_detect_test_command "$project_dir")

    jq -n \
        --arg framework "$framework" \
        --argjson config_exists "$config_exists" \
        --argjson test_file_count "$test_file_count" \
        --argjson has_helpers "$has_helpers" \
        --arg test_command "$test_command" \
        '{
            framework: $framework,
            config_exists: $config_exists,
            test_file_count: $test_file_count,
            has_helpers: $has_helpers,
            test_command: $test_command
        }'
}

auto_detect_test_command() {
    local project_dir="${1:-.}"

    [[ ! -f "$project_dir/package.json" ]] && return

    # Detect package manager from lockfile
    local pkg_mgr="npm"
    if [[ -f "$project_dir/pnpm-lock.yaml" ]]; then
        pkg_mgr="pnpm"
    elif [[ -f "$project_dir/yarn.lock" ]]; then
        pkg_mgr="yarn"
    elif [[ -f "$project_dir/bun.lockb" || -f "$project_dir/bun.lock" ]]; then
        pkg_mgr="bun"
    fi

    # Check scripts in priority order: test → test:unit → test:ci
    local script_name=""
    for candidate in "test" "test:unit" "test:ci"; do
        local has_script
        has_script=$(jq -r --arg s "$candidate" '.scripts[$s] // empty' "$project_dir/package.json" 2>/dev/null)
        if [[ -n "$has_script" ]]; then
            script_name="$candidate"
            break
        fi
    done

    [[ -z "$script_name" ]] && return

    echo "$pkg_mgr run $script_name"
}

# ─── Plan Validation ─────────────────────────────────────────────────

validate_plan() {
    local plan_file="$1"
    local errors=0

    # Check JSON structure
    if ! jq empty "$plan_file" 2>/dev/null; then
        error "Plan file is not valid JSON"
        return 1
    fi

    # Check required fields
    for field in plan_version brief_hash changes; do
        if [[ "$(jq -r ".$field // empty" "$plan_file")" == "" ]]; then
            error "Plan missing required field: $field"
            errors=$((errors + 1))
        fi
    done

    # Check change names are kebab-case
    local bad_names
    bad_names=$(jq -r '.changes[].name' "$plan_file" | grep -vE '^[a-z][a-z0-9-]*$' || true)
    if [[ -n "$bad_names" ]]; then
        error "Invalid change names (must be kebab-case): $bad_names"
        errors=$((errors + 1))
    fi

    # Check depends_on references exist
    local all_names
    all_names=$(jq -r '.changes[].name' "$plan_file" | sort)
    local all_deps
    all_deps=$(jq -r '.changes[].depends_on[]?' "$plan_file" 2>/dev/null | sort -u)

    if [[ -n "$all_deps" ]]; then
        local missing
        missing=$(comm -23 <(echo "$all_deps") <(echo "$all_names"))
        if [[ -n "$missing" ]]; then
            error "depends_on references non-existent changes: $missing"
            errors=$((errors + 1))
        fi
    fi

    # Check for circular dependencies
    local sort_result
    sort_result=$(topological_sort "$plan_file" 2>&1)
    if echo "$sort_result" | grep -q "ERROR:circular"; then
        error "Circular dependency detected in change graph"
        errors=$((errors + 1))
    fi

    # Digest-mode validation: check spec_files, requirements, also_affects_reqs
    if [[ "${INPUT_MODE:-}" == "digest" && -f "$DIGEST_DIR/requirements.json" ]]; then
        local all_req_ids
        all_req_ids=$(jq -r '[.requirements[]? | select(.status != "removed") | .id] | .[]' "$DIGEST_DIR/requirements.json" 2>/dev/null || true)

        # Check requirements reference valid IDs
        local plan_req_ids
        plan_req_ids=$(jq -r '.changes[]? | (.requirements[]?, .also_affects_reqs[]?)' "$plan_file" 2>/dev/null || true)
        if [[ -n "$plan_req_ids" ]]; then
            while IFS= read -r rid; do
                [[ -z "$rid" ]] && continue
                if ! echo "$all_req_ids" | grep -qxF "$rid"; then
                    warn "Plan references non-existent requirement: $rid"
                    # Non-fatal warning, don't increment errors
                fi
            done <<< "$plan_req_ids"
        fi

        # Check also_affects_reqs have a primary owner
        local also_affects_ids
        also_affects_ids=$(jq -r '.changes[]? | .also_affects_reqs[]?' "$plan_file" 2>/dev/null | sort -u || true)
        if [[ -n "$also_affects_ids" ]]; then
            local primary_owned_ids
            primary_owned_ids=$(jq -r '.changes[]? | .requirements[]?' "$plan_file" 2>/dev/null | sort -u || true)
            while IFS= read -r aaid; do
                [[ -z "$aaid" ]] && continue
                if ! echo "$primary_owned_ids" | grep -qxF "$aaid"; then
                    warn "also_affects_reqs '$aaid' has no primary owner in any change's requirements[]"
                fi
            done <<< "$also_affects_ids"
        fi
    fi

    # Check for scope overlap between planned changes
    check_scope_overlap "$plan_file"

    return $errors
}

# Detect overlapping scopes between changes in a plan (and vs active/merged changes).
check_scope_overlap() {
    local plan_file="$1"

    local change_count
    change_count=$(jq '.changes | length' "$plan_file")
    [[ "$change_count" -lt 2 ]] && return 0

    local warnings=0

    # Build keyword sets for each change (name → lowercase words from scope)
    local -A scope_words
    local names=()
    while IFS= read -r name; do
        names+=("$name")
        local scope_text
        scope_text=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .scope // ""' "$plan_file")
        # Extract lowercase words (3+ chars), deduplicate
        scope_words["$name"]=$(echo "$scope_text" | tr '[:upper:]' '[:lower:]' | grep -oE '[a-z]{3,}' | sort -u | tr '\n' ' ')
    done < <(jq -r '.changes[].name' "$plan_file")

    # Pairwise jaccard comparison
    for ((i=0; i<${#names[@]}; i++)); do
        for ((j=i+1; j<${#names[@]}; j++)); do
            local name_a="${names[$i]}"
            local name_b="${names[$j]}"
            local words_a="${scope_words[$name_a]}"
            local words_b="${scope_words[$name_b]}"

            # Skip if either has very few words
            local count_a count_b
            count_a=$(echo "$words_a" | wc -w)
            count_b=$(echo "$words_b" | wc -w)
            [[ "$count_a" -lt 3 || "$count_b" -lt 3 ]] && continue

            # Compute jaccard: |intersection| / |union|
            local intersection union
            intersection=$(comm -12 <(echo "$words_a" | tr ' ' '\n' | sort) <(echo "$words_b" | tr ' ' '\n' | sort) | wc -l)
            union=$(cat <(echo "$words_a" | tr ' ' '\n') <(echo "$words_b" | tr ' ' '\n') | sort -u | grep -c . || true)

            if [[ "$union" -gt 0 ]]; then
                local similarity=$((intersection * 100 / union))
                if [[ "$similarity" -ge 40 ]]; then
                    warn "Scope overlap detected: '$name_a' ↔ '$name_b' (${similarity}% keyword similarity)"
                    log_warn "Scope overlap: $name_a ↔ $name_b = ${similarity}% (intersection=$intersection, union=$union)"
                    warnings=$((warnings + 1))
                fi
            fi
        done
    done

    # Also check against active worktrees (if state file exists)
    if [[ -f "$STATE_FILENAME" ]]; then
        local active_changes
        active_changes=$(jq -r '.changes[]? | select(.status == "running" or .status == "dispatched" or .status == "done") | .name' "$STATE_FILENAME" 2>/dev/null || true)

        if [[ -n "$active_changes" ]]; then
            while IFS= read -r active_name; do
                local active_scope
                active_scope=$(jq -r --arg n "$active_name" '.changes[] | select(.name == $n) | .scope // ""' "$STATE_FILENAME")
                local active_words
                active_words=$(echo "$active_scope" | tr '[:upper:]' '[:lower:]' | grep -oE '[a-z]{3,}' | sort -u | tr '\n' ' ')
                local active_count
                active_count=$(echo "$active_words" | wc -w)
                [[ "$active_count" -lt 3 ]] && continue

                for name in "${names[@]}"; do
                    [[ "$name" == "$active_name" ]] && continue
                    local words="${scope_words[$name]}"
                    local wcount
                    wcount=$(echo "$words" | wc -w)
                    [[ "$wcount" -lt 3 ]] && continue

                    local intersection union
                    intersection=$(comm -12 <(echo "$words" | tr ' ' '\n' | sort) <(echo "$active_words" | tr ' ' '\n' | sort) | wc -l)
                    union=$(cat <(echo "$words" | tr ' ' '\n') <(echo "$active_words" | tr ' ' '\n') | sort -u | grep -c . || true)

                    if [[ "$union" -gt 0 ]]; then
                        local similarity=$((intersection * 100 / union))
                        if [[ "$similarity" -ge 40 ]]; then
                            warn "New change '$name' overlaps with ACTIVE change '$active_name' (${similarity}% similarity)"
                            log_warn "Overlap with active: $name ↔ $active_name = ${similarity}%"
                            warnings=$((warnings + 1))
                        fi
                    fi
                done
            done <<< "$active_changes"
        fi
    fi

    # Check cross-cutting file mentions if project-knowledge.yaml exists
    local pk_file
    pk_file=$(find_project_knowledge_file)
    if [[ -n "$pk_file" ]]; then
        local cc_paths
        cc_paths=$(yq -r '.cross_cutting_files[]?.path // empty' "$pk_file" 2>/dev/null || true)
        if [[ -n "$cc_paths" ]]; then
            while IFS= read -r cc_path; do
                [[ -z "$cc_path" ]] && continue
                local cc_basename
                cc_basename=$(basename "$cc_path")
                local touching_changes=()
                for name in "${names[@]}"; do
                    local scope_text
                    scope_text=$(jq -r --arg n "$name" '.changes[] | select(.name == $n) | .scope // ""' "$plan_file")
                    if echo "$scope_text" | grep -qi "$cc_basename"; then
                        touching_changes+=("$name")
                    fi
                done
                if [[ ${#touching_changes[@]} -ge 2 ]]; then
                    warn "Cross-cutting file '$cc_path' may be touched by: ${touching_changes[*]}"
                    log_warn "Cross-cutting hazard: $cc_path touched by ${touching_changes[*]}"
                    warnings=$((warnings + 1))
                fi
            done <<< "$cc_paths"
        fi
    fi

    if [[ $warnings -gt 0 ]]; then
        send_notification "wt-orchestrate" "Plan has $warnings scope overlap warning(s) — review for duplicates" "normal"
    fi
}

# Find project-knowledge.yaml — delegates to wt_find_config fallback chain
find_project_knowledge_file() {
    wt_find_config project-knowledge
}

# ─── Triage Gate ─────────────────────────────────────────────────────

# Check triage status for ambiguities. Returns one of:
#   no_ambiguities — zero ambiguities, skip entirely
#   needs_triage   — ambiguities exist but no triage.md
#   has_untriaged  — triage.md exists but has blank decisions
#   has_fixes      — all triaged but some marked "fix" (spec needs correction)
#   passed         — all triaged, no fixes, ready to proceed
check_triage_gate() {
    if [[ ! -f "$DIGEST_DIR/ambiguities.json" ]]; then
        echo "no_ambiguities"
        return 0
    fi

    local amb_count
    amb_count=$(jq '.ambiguities | length' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || echo 0)
    if [[ "$amb_count" -eq 0 ]]; then
        echo "no_ambiguities"
        return 0
    fi

    # In automated mode (orchestrator), auto-defer everything
    if [[ "${TRIAGE_AUTO_DEFER:-false}" == "true" ]]; then
        # Auto-defer: generate triage if missing, mark all as defer
        if [[ ! -f "$DIGEST_DIR/triage.md" ]]; then
            generate_triage_md "$DIGEST_DIR/ambiguities.json" "$DIGEST_DIR/triage.md"
        fi
        # Build auto-defer decisions for all ambiguities
        local auto_decisions
        auto_decisions=$(jq '[.ambiguities[].id] | map({key: ., value: {decision: "defer", note: ""}}) | from_entries' "$DIGEST_DIR/ambiguities.json")
        merge_triage_to_ambiguities "$DIGEST_DIR/ambiguities.json" "$auto_decisions" "auto"
        info "Auto-deferred $amb_count ambiguities (automated mode)"
        echo "passed"
        return 0
    fi

    if [[ ! -f "$DIGEST_DIR/triage.md" ]]; then
        echo "needs_triage"
        return 0
    fi

    # Parse triage decisions
    local decisions
    decisions=$(parse_triage_md "$DIGEST_DIR/triage.md")

    # Check for untriaged items (blank decision)
    local untriaged_count
    untriaged_count=$(jq -r --argjson decisions "$decisions" \
        '[.ambiguities[].id] | map(. as $id | if $decisions[$id].decision == "" or ($decisions[$id] | not) then 1 else 0 end) | add // 0' \
        "$DIGEST_DIR/ambiguities.json")

    if [[ "$untriaged_count" -gt 0 ]]; then
        echo "has_untriaged"
        return 0
    fi

    # Check for "fix" items
    local fix_count
    fix_count=$(echo "$decisions" | jq '[.[] | select(.decision == "fix")] | length')

    if [[ "$fix_count" -gt 0 ]]; then
        echo "has_fixes"
        return 0
    fi

    echo "passed"
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
                info "Digest is stale — auto-re-digesting..."
                log_info "Auto-digest triggered (stale)"
                cmd_digest --spec "$INPUT_PATH" || {
                    error "Auto-digest failed"
                    return 1
                }
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

    # Build decomposition prompt (tri-mode: digest vs spec vs brief)
    local input_content
    local hash

    if [[ "$INPUT_MODE" == "digest" ]]; then
        # Digest mode: read structured digest instead of raw spec
        hash=$(jq -r '.source_hash' "$DIGEST_DIR/index.json")

        # Build digest content for planner prompt
        local digest_content=""

        # Conventions first (project-wide rules)
        if [[ -f "$DIGEST_DIR/conventions.json" ]]; then
            local conv_content
            conv_content=$(cat "$DIGEST_DIR/conventions.json")
            digest_content+="## Project Conventions (apply to ALL changes)
$conv_content

"
        fi

        # Data model reference
        if [[ -f "$DIGEST_DIR/data-definitions.md" ]]; then
            local data_content
            data_content=$(cat "$DIGEST_DIR/data-definitions.md")
            digest_content+="## Data Model Reference
$data_content

"
        fi

        # Execution hints (optional guidance)
        local exec_hints
        exec_hints=$(jq -r '.execution_hints // {} | if . == {} then empty else tostring end' "$DIGEST_DIR/index.json" 2>/dev/null || true)
        if [[ -n "$exec_hints" ]]; then
            digest_content+="## Execution Hints (optional guidance from spec author)
$exec_hints

"
        fi

        # Domain summaries
        if [[ -d "$DIGEST_DIR/domains" ]]; then
            digest_content+="## Domain Summaries
"
            for domain_file in "$DIGEST_DIR/domains"/*.md; do
                [[ -f "$domain_file" ]] || continue
                local dname
                dname=$(basename "$domain_file" .md)
                digest_content+="### $dname
$(cat "$domain_file")

"
            done
        fi

        # Requirements
        if [[ -f "$DIGEST_DIR/requirements.json" ]]; then
            local reqs_content
            reqs_content=$(cat "$DIGEST_DIR/requirements.json")
            local req_count
            req_count=$(echo "$reqs_content" | jq '.requirements | length')
            digest_content+="## Requirements ($req_count total)
$reqs_content

"
        fi

        # Dependencies
        if [[ -f "$DIGEST_DIR/dependencies.json" ]]; then
            local deps_content
            deps_content=$(cat "$DIGEST_DIR/dependencies.json")
            digest_content+="## Cross-references
$deps_content

"
        fi

        # Ambiguities — only include deferred items that need planner resolution
        if [[ -f "$DIGEST_DIR/ambiguities.json" ]]; then
            local deferred_ambs
            deferred_ambs=$(jq '{ambiguities: [.ambiguities[] | select(.resolution == "deferred" or (has("resolution") | not))]}' "$DIGEST_DIR/ambiguities.json" 2>/dev/null || echo '{"ambiguities":[]}')
            local deferred_count
            deferred_count=$(echo "$deferred_ambs" | jq '.ambiguities | length')
            if [[ "$deferred_count" -gt 0 ]]; then
                digest_content+="## Deferred Ambiguities ($deferred_count items — you MUST resolve each)
For each deferred ambiguity below, include a \"resolved_ambiguities\" entry in the change that addresses the affected requirements. Specify your decision and rationale.

$deferred_ambs

"
            fi
        fi

        input_content="$digest_content"
    elif [[ "$INPUT_MODE" == "spec" ]]; then
        hash=$(brief_hash "$INPUT_PATH")
        # Spec mode: check if summarization is needed
        local token_est
        token_est=$(estimate_tokens "$INPUT_PATH")
        if [[ "$token_est" -gt 8000 ]]; then
            # Check spec summary cache
            local cache_file=".claude/spec-summary-cache.json"
            local cached_hash=""
            if [[ -f "$cache_file" ]]; then
                cached_hash=$(jq -r '.brief_hash // ""' "$cache_file" 2>/dev/null)
            fi
            if [[ "$cached_hash" == "$hash" && -n "$cached_hash" ]]; then
                log_info "Using cached spec summary (hash=$hash)"
                input_content=$(jq -r '.summary' "$cache_file")
            else
                info "Large spec detected (~${token_est} tokens). Summarizing..."
                log_info "Spec summarization triggered (est. $token_est tokens)"
                local sum_model
                sum_model=$(echo "$directives" | jq -r '.summarize_model // "haiku"')
                input_content=$(summarize_spec "$INPUT_PATH" "$PHASE_HINT" "$sum_model")
                # Cache the summary
                mkdir -p .claude
                jq -n --arg bh "$hash" --arg sum "$input_content" --arg ca "$(date -Iseconds)" \
                    '{brief_hash: $bh, summary: $sum, created_at: $ca}' > "$cache_file"
                log_info "Spec summary cached (hash=$hash)"
            fi
        else
            input_content=$(cat "$INPUT_PATH")
        fi
    else
        hash=$(brief_hash "$INPUT_PATH")
        input_content=$(cat "$INPUT_PATH")
    fi

    # Build project knowledge context if project-knowledge.yaml exists
    local pk_context=""
    local pk_file
    pk_file=$(find_project_knowledge_file)
    if [[ -n "$pk_file" ]]; then
        local cc_files
        cc_files=$(yq -r '.cross_cutting_files[]? | "- \(.path): \(.description // "")"' "$pk_file" 2>/dev/null || true)
        if [[ -n "$cc_files" ]]; then
            pk_context="## Cross-Cutting Files (merge hazards)
These files are shared across features. Changes touching them should be serialized via depends_on:
$cc_files"
        fi
    fi

    # Scan wt/requirements/ for active requirements (status: captured or planned)
    local req_context=""
    local req_dir
    req_dir=$(wt_find_requirements_dir)
    if [[ -n "$req_dir" && -d "$req_dir" ]]; then
        local req_entries=""
        for req_file in "$req_dir"/*.yaml "$req_dir"/*.yml; do
            [[ -f "$req_file" ]] || continue
            local req_status
            req_status=$(yq -r '.status // "unknown"' "$req_file" 2>/dev/null || true)
            if [[ "$req_status" == "captured" || "$req_status" == "planned" ]]; then
                local req_id req_title req_desc req_priority
                req_id=$(yq -r '.id // "?"' "$req_file" 2>/dev/null || true)
                req_title=$(yq -r '.title // "Untitled"' "$req_file" 2>/dev/null || true)
                req_desc=$(yq -r '.description // ""' "$req_file" 2>/dev/null | head -5 || true)
                req_priority=$(yq -r '.priority // "unknown"' "$req_file" 2>/dev/null || true)
                req_entries+="- **$req_id: $req_title** (priority: $req_priority, status: $req_status)
  $req_desc
"
            fi
        done
        if [[ -n "$req_entries" ]]; then
            req_context="## Business Requirements (captured/planned)
Consider these requirements when decomposing — they represent business needs that may map to changes:
$req_entries"
        fi
    fi

    local prompt
    if [[ "$INPUT_MODE" == "spec" || "$INPUT_MODE" == "digest" ]]; then
        # Spec/digest-mode prompt: LLM determines what's next
        local phase_instruction=""
        if [[ -n "$PHASE_HINT" ]]; then
            phase_instruction="The user requested phase: $PHASE_HINT. Focus decomposition on items matching this phase."
        fi

        prompt=$(cat <<PROMPT_EOF
You are a software architect analyzing a project specification to plan the next batch of implementation work.

## Project Specification
$input_content

## Existing OpenSpec Specs
$existing_specs

## Active Changes (already in progress)
$active_changes
$(if [[ -n "$memory_context" ]]; then
cat <<MEM_CTX

## Project Memory
$memory_context
MEM_CTX
fi)
$(if [[ -n "$pk_context" ]]; then
echo ""
echo "$pk_context"
fi)
$(if [[ -n "$req_context" ]]; then
echo ""
echo "$req_context"
fi)

## $test_infra_context
$(if [[ "${INPUT_MODE:-}" == "digest" && -f "$DIGEST_DIR/coverage.json" ]]; then
    local cov_merged cov_running
    cov_merged=$(jq -r '[.coverage | to_entries[] | select(.value.status == "merged") | .key] | join(", ")' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
    cov_running=$(jq -r '[.coverage | to_entries[] | select(.value.status == "running") | .key] | join(", ")' "$DIGEST_DIR/coverage.json" 2>/dev/null || true)
    if [[ -n "$cov_merged" || -n "$cov_running" ]]; then
        echo ""
        echo "## Coverage Status (from digest)"
        [[ -n "$cov_merged" ]] && echo "Already covered (merged): $cov_merged"
        [[ -n "$cov_running" ]] && echo "Already covered (running): $cov_running"
        echo "Do NOT re-plan requirements that are already merged or running."
    fi
fi)
$(if [[ -n "${_REPLAN_COMPLETED:-}" ]]; then
cat <<REPLAN_CTX

## IMPORTANT: Already Completed (cycle ${_REPLAN_CYCLE:-1})
The following roadmap items have ALREADY been implemented and merged.
Roadmap items: $_REPLAN_COMPLETED

CRITICAL INSTRUCTIONS FOR REPLAN:
- DO NOT regenerate changes for any of these completed items
- You MUST advance to the NEXT phase/priority group in the spec
- If Phase/Priority 1 items are all completed, plan Phase/Priority 2 items
- Generate changes with NEW names (not the same names as completed changes)
- If no more phases remain in the spec, return an empty changes array: {"changes": [], "phase_detected": "all done", "reasoning": "all phases completed"}
REPLAN_CTX
fi)
$(if [[ -n "${_REPLAN_MEMORY:-}" ]]; then
cat <<ORCH_HIST

## Orchestration History
Past operational events from previous cycles — use this to avoid repeating mistakes:
$_REPLAN_MEMORY
ORCH_HIST
fi)

## Task
1. **Analyze the specification** — identify which items are completed (look for status markers: checkboxes, emoji, "done"/"implemented"/"kész"/"ready" text, strikethrough, progress tables) and which are pending. Also consider the "Already Completed" section above if present.
2. **Determine the next batch** — respect explicit phases, priorities, or numbered ordering in the document. Pick the first incomplete phase/priority group.
$phase_instruction
3. **Decompose** the selected batch into concrete, implementable OpenSpec changes.

Rules:
- Each change should be completable in 1 Ralph loop session (not too large, not too granular)
- Use kebab-case names (e.g., add-user-auth, refactor-payment-flow)
- Define dependencies: if change B needs code from change A, list A in depends_on
- Changes with no dependencies can run in parallel
- Complexity: S (< 8 tasks, preferred), M (8-15 tasks, maximum). L (15+ tasks) is NOT ALLOWED — split into smaller changes.
- Max 6 requirements per change. If a feature domain has more than 6 requirements, split it into sub-domain changes.
- Scope text should be 800-1500 chars. If you need more than 2000 chars to describe a change, it is too large — split it.
- Skip already-active changes listed above
- Every change scope MUST include specific test requirements (happy path, error cases, security boundaries)
- For security-related changes: include tenant isolation tests, auth guard tests
- If no test infrastructure exists, the FIRST change MUST be "test-infrastructure-setup" setting up the test framework, config, helpers, and an example test. ALL other changes MUST depend on it.
- If test infrastructure exists, follow existing test patterns (framework and naming conventions noted above)
- NEVER create a standalone "e2e-consolidation", "playwright-e2e", or "e2e-tests" change that only writes E2E tests. This anti-pattern overloads one agent with all cross-feature tests and wastes tokens. Each feature change MUST include its OWN E2E tests inline.

Sub-domain dependency chaining:
- When splitting a large feature domain into multiple changes, those changes MUST form a depends_on chain (sequential execution within the domain)
- Different domain chains can still run in parallel with each other
- Example: splitting "product-catalog" (22 reqs) into product-list → product-detail → product-search — each depends_on the previous, but all can run in parallel with an unrelated "user-auth" chain

Split heuristics for common patterns:
- List page + detail page → split into separate changes if combined requirements exceed 6
- CRUD operations → separate from read-only views when the domain is large
- Search/filtering with its own API routes → separate change
- Auth + profile + password management → split auth/login from profile/account management

Dependency ordering heuristics — classify each change by type and apply ordering:
- Classify each change as one of: infrastructure (test/build setup, CI), schema (DB migrations, model changes), foundational (auth, shared types, base components), feature (new functionality), cleanup-before (refactor/rename/reorganize existing code), cleanup-after (dead code removal, cosmetic fixes)
- infrastructure changes run first — all others depend on them
- schema/migration changes run before data-layer or API changes that use those tables
- foundational changes (auth, shared types) run before features that consume them
- cleanup-before/refactor changes run before feature changes that touch the same area (e.g., a UI cleanup should complete before new UI features are built on that code)
- cleanup-after changes run last — they depend on the features they clean up around
- If the spec contains explicit dependency hints (e.g., "depends_on: X", "requires X", "after X is complete"), preserve them in the output depends_on array

Shared resource awareness:
- If 2+ parallel changes would likely modify the same shared file (conventions docs, shared types, config files, common UI components), chain them via depends_on to prevent merge conflicts
- Prefer serialization over parallel execution when shared files are involved
- Common shared resources: design/convention docs, shared type definitions, package.json, layout components

Test-per-change requirement:
- Each change that adds a user-facing route, feature, or API endpoint MUST include its own tests. Do NOT defer all testing to a final "e2e" change.
- The quality gate BLOCKS changes without test files for feature/infrastructure types.
- Explicitly list test files in scope (e.g., "Tests: Create orders.test.ts").

Playwright E2E test planning (when e2e_command is configured):
- The infrastructure/foundation change (first in dependency order) MUST set up Playwright alongside Jest:
  * Create playwright.config.ts with PW_PORT env var support and webServer auto-start
  * Add testPathIgnorePatterns: ["/node_modules/", "/tests/e2e/"] to jest.config (Jest crashes on Playwright .spec.ts imports in jsdom)
  * Add @playwright/test to devDependencies + run npx playwright install chromium
  * Create tests/e2e/global-setup.ts: prisma generate → prisma db push --force-reset → prisma db seed
- Each subsequent feature change creating a user-facing route MUST create tests/e2e/<feature>.spec.ts as an explicit file deliverable in scope (e.g., "Create tests/e2e/cart.spec.ts")
- Include CONCRETE test scenarios per feature:
  * Page URL to visit
  * User interactions: what to click, what data to type, what to select
  * Expected outcomes: visible text, redirects, error messages
  * Auth scenarios: verify protected routes redirect unauthenticated users
  * Error scenarios: invalid form input, missing required fields
  * COLD-VISIT test: navigate directly to the page as the FIRST action (no prior login, no add-to-cart, no session cookie). This catches Server Component cookie/session bugs where cookies().set() crashes outside a Server Action.
- Example scope:
  Create tests/e2e/orders.spec.ts:
  - Cold visit: go to /cart directly (no prior actions) → should show empty state, NOT crash
  - Visit /products → click "Add to Cart" on first product → cart badge shows "1"
  - Visit /cart → verify product name and price → click "Checkout" → fill form → verify redirect to /orders/[id]
  - Visit /admin/orders without login → verify redirect to /admin/login
- Do NOT defer all E2E tests to a consolidation change — this overloads a single agent. Each feature change owns its tests.
- Do NOT just list "Functional test scenarios:" as descriptions — create actual test files.
- E2E tests run pre-merge in the worktree via e2e_command against an auto-started dev server with isolated port and DB.

Model selection — suggest a model per change based on task nature:
- "opus" for ALL changes that write functional code (features, bug fixes, refactors, cleanup, tests)
- "sonnet" ONLY for doc-only changes (doc sync, doc audit, README updates) — zero code writing
- Sonnet cannot follow OpenSpec workflows, make architecture decisions, or write quality code
- When in doubt, always use "opus"

Manual tasks — flag changes that require human intervention:
- Set "has_manual_tasks": true when a change involves: external API keys/secrets (Stripe, AWS, Firebase), third-party account/project creation, OAuth app registration, DNS configuration, webhook setup, or any step that cannot be automated
- Examples: "integrate Stripe payments" (needs API key), "set up Firebase auth" (needs project creation), "configure custom domain" (needs DNS records)
- When false or omitted, all tasks are assumed automatable

$(if [[ "$INPUT_MODE" == "digest" ]]; then
cat <<'DIGEST_FIELDS'
Digest-mode additional requirements:
- Each change MUST include "spec_files": an array of raw spec file paths (relative to spec base dir) that this change needs for implementation. These files will be copied into the worktree.
- Each change MUST include "requirements": an array of REQ-* IDs from the digest that this change owns and implements.
- If a change must incorporate a cross-cutting requirement owned by another change, list it in "also_affects_reqs" (not in "requirements").
- Every non-removed REQ-* ID in the digest MUST appear in exactly one change's "requirements" array. Cross-cutting requirements appear in one change's "requirements" (primary owner) and other changes' "also_affects_reqs".
DIGEST_FIELDS
fi)

Output ONLY valid JSON (no markdown, no explanation):
{
  "phase_detected": "Description of which phase/section was selected and why",
  "reasoning": "Brief explanation of the decomposition choices",
  "changes": [
    {
      "name": "change-name",
      "scope": "Detailed description of what this change implements, including key requirements and constraints. This becomes the proposal for the change. Tests: describe required tests.",
      "complexity": "S|M|L",
      "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
      "model": "opus|sonnet",
      "has_manual_tasks": false,
      "depends_on": ["other-change-name"],
      "roadmap_item": "The spec section/item this implements"$(if [[ "$INPUT_MODE" == "digest" ]]; then echo ',
      "spec_files": ["path/relative/to/spec-base-dir.md"],
      "requirements": ["REQ-DOMAIN-001"],
      "also_affects_reqs": ["REQ-CROSS-001"],
      "resolved_ambiguities": [{"id": "AMB-001", "resolution_note": "Decision rationale"}]'; fi)
    }
  ]
}
PROMPT_EOF
)
    else
        # Brief-mode prompt: existing behavior
        prompt=$(cat <<PROMPT_EOF
You are a software architect decomposing a project brief into OpenSpec changes.

## Project Brief
$input_content

## Existing Specs
$existing_specs

## Active Changes
$active_changes
$(if [[ -n "$memory_context" ]]; then
cat <<MEM_CTX

## Project Memory
$memory_context
MEM_CTX
fi)
$(if [[ -n "$pk_context" ]]; then
echo ""
echo "$pk_context"
fi)
$(if [[ -n "$req_context" ]]; then
echo ""
echo "$req_context"
fi)

## $test_infra_context

## Task
Analyze the "Next" section of the brief and decompose it into concrete, implementable OpenSpec changes.

Rules:
- Each change should be completable in 1 Ralph loop session (not too large, not too granular)
- Use kebab-case names (e.g., add-user-auth, refactor-payment-flow)
- Define dependencies: if change B needs code from change A, list A in depends_on
- Changes with no dependencies can run in parallel
- Complexity: S (< 8 tasks, preferred), M (8-15 tasks, maximum). L (15+ tasks) is NOT ALLOWED — split into smaller changes.
- Max 6 requirements per change. If a feature domain has more than 6 requirements, split it into sub-domain changes.
- Scope text should be 800-1500 chars. If you need more than 2000 chars to describe a change, it is too large — split it.
- Every change scope MUST include specific test requirements (happy path, error cases, security boundaries)
- For security-related changes: include tenant isolation tests, auth guard tests
- If no test infrastructure exists, the FIRST change MUST be "test-infrastructure-setup" setting up the test framework, config, helpers, and an example test. ALL other changes MUST depend on it.
- If test infrastructure exists, follow existing test patterns (framework and naming conventions noted above)
- NEVER create a standalone "e2e-consolidation", "playwright-e2e", or "e2e-tests" change that only writes E2E tests. This anti-pattern overloads one agent with all cross-feature tests and wastes tokens. Each feature change MUST include its OWN E2E tests inline.

Sub-domain dependency chaining:
- When splitting a large feature domain into multiple changes, those changes MUST form a depends_on chain (sequential execution within the domain)
- Different domain chains can still run in parallel with each other
- Example: splitting "product-catalog" (22 reqs) into product-list → product-detail → product-search — each depends_on the previous, but all can run in parallel with an unrelated "user-auth" chain

Split heuristics for common patterns:
- List page + detail page → split into separate changes if combined requirements exceed 6
- CRUD operations → separate from read-only views when the domain is large
- Search/filtering with its own API routes → separate change
- Auth + profile + password management → split auth/login from profile/account management

Dependency ordering heuristics — classify each change by type and apply ordering:
- Classify each change as one of: infrastructure (test/build setup, CI), schema (DB migrations, model changes), foundational (auth, shared types, base components), feature (new functionality), cleanup-before (refactor/rename/reorganize existing code), cleanup-after (dead code removal, cosmetic fixes)
- infrastructure changes run first — all others depend on them
- schema/migration changes run before data-layer or API changes that use those tables
- foundational changes (auth, shared types) run before features that consume them
- cleanup-before/refactor changes run before feature changes that touch the same area (e.g., a UI cleanup should complete before new UI features are built on that code)
- cleanup-after changes run last — they depend on the features they clean up around
- If the spec contains explicit dependency hints (e.g., "depends_on: X", "requires X", "after X is complete"), preserve them in the output depends_on array

Shared resource awareness:
- If 2+ parallel changes would likely modify the same shared file (conventions docs, shared types, config files, common UI components), chain them via depends_on to prevent merge conflicts
- Prefer serialization over parallel execution when shared files are involved
- Common shared resources: design/convention docs, shared type definitions, package.json, layout components

Test-per-change requirement:
- Each change that adds a user-facing route, feature, or API endpoint MUST include its own tests. Do NOT defer all testing to a final "e2e" change.
- The quality gate BLOCKS changes without test files for feature/infrastructure types.
- Explicitly list test files in scope (e.g., "Tests: Create orders.test.ts").

Playwright E2E test planning (when e2e_command is configured):
- The infrastructure/foundation change (first in dependency order) MUST set up Playwright alongside Jest:
  * Create playwright.config.ts with PW_PORT env var support and webServer auto-start
  * Add testPathIgnorePatterns: ["/node_modules/", "/tests/e2e/"] to jest.config (Jest crashes on Playwright .spec.ts imports in jsdom)
  * Add @playwright/test to devDependencies + run npx playwright install chromium
  * Create tests/e2e/global-setup.ts: prisma generate → prisma db push --force-reset → prisma db seed
- Each subsequent feature change creating a user-facing route MUST create tests/e2e/<feature>.spec.ts as an explicit file deliverable in scope (e.g., "Create tests/e2e/cart.spec.ts")
- Include CONCRETE test scenarios per feature:
  * Page URL to visit
  * User interactions: what to click, what data to type, what to select
  * Expected outcomes: visible text, redirects, error messages
  * Auth scenarios: verify protected routes redirect unauthenticated users
  * Error scenarios: invalid form input, missing required fields
  * COLD-VISIT test: navigate directly to the page as the FIRST action (no prior login, no add-to-cart, no session cookie). This catches Server Component cookie/session bugs where cookies().set() crashes outside a Server Action.
- Example scope:
  Create tests/e2e/orders.spec.ts:
  - Cold visit: go to /cart directly (no prior actions) → should show empty state, NOT crash
  - Visit /products → click "Add to Cart" on first product → cart badge shows "1"
  - Visit /cart → verify product name and price → click "Checkout" → fill form → verify redirect to /orders/[id]
  - Visit /admin/orders without login → verify redirect to /admin/login
- Do NOT defer all E2E tests to a consolidation change — this overloads a single agent. Each feature change owns its tests.
- Do NOT just list "Functional test scenarios:" as descriptions — create actual test files.
- E2E tests run pre-merge in the worktree via e2e_command against an auto-started dev server with isolated port and DB.

Model selection — suggest a model per change based on task nature:
- "opus" for ALL changes that write functional code (features, bug fixes, refactors, cleanup, tests)
- "sonnet" ONLY for doc-only changes (doc sync, doc audit, README updates) — zero code writing
- Sonnet cannot follow OpenSpec workflows, make architecture decisions, or write quality code
- When in doubt, always use "opus"

Manual tasks — flag changes that require human intervention:
- Set "has_manual_tasks": true when a change involves: external API keys/secrets (Stripe, AWS, Firebase), third-party account/project creation, OAuth app registration, DNS configuration, webhook setup, or any step that cannot be automated
- Examples: "integrate Stripe payments" (needs API key), "set up Firebase auth" (needs project creation), "configure custom domain" (needs DNS records)
- When false or omitted, all tasks are assumed automatable

Output ONLY valid JSON (no markdown, no explanation):
{
  "changes": [
    {
      "name": "change-name",
      "scope": "Detailed description of what this change implements, including key requirements and constraints. This becomes the proposal for the change. Tests: describe required tests.",
      "complexity": "S|M|L",
      "change_type": "infrastructure|schema|foundational|feature|cleanup-before|cleanup-after",
      "model": "opus|sonnet",
      "has_manual_tasks": false,
      "depends_on": ["other-change-name"],
      "roadmap_item": "The exact Next bullet this implements"
    }
  ]
}
PROMPT_EOF
)
    fi

    info "Calling Claude for decomposition..."
    log_info "Plan decomposition started (brief hash: $hash)"

    local claude_output
    claude_output=$(export RUN_CLAUDE_TIMEOUT=600; echo "$prompt" | run_claude --model "$(model_id opus)") || {
        error "Claude decomposition failed. Check your Claude CLI setup."
        log_error "Claude decomposition failed"
        return 1
    }

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

    # Add metadata to plan
    local plan_version=1
    if [[ -f "$PLAN_FILENAME" ]]; then
        plan_version=$(( $(jq -r '.plan_version // 0' "$PLAN_FILENAME") + 1 ))
    fi

    local input_content_hash=""
    if [[ -n "$INPUT_PATH" && -f "$INPUT_PATH" ]]; then
        input_content_hash=$(sha256sum "$INPUT_PATH" 2>/dev/null | cut -d' ' -f1)
    fi
    # Determine plan_phase: "iteration" if inside a replan cycle, "initial" otherwise
    local plan_phase="initial"
    [[ -n "${_REPLAN_CYCLE:-}" ]] && plan_phase="iteration"

    # plan_method: "agent" if dispatched via agent planning, "api" otherwise
    local plan_method="${_PLAN_METHOD:-api}"

    echo "$plan_json" | jq \
        --argjson pv "$plan_version" \
        --arg hash "$hash" \
        --arg created "$(date -Iseconds)" \
        --arg imode "$INPUT_MODE" \
        --arg ipath "$INPUT_PATH" \
        --arg ihash "$input_content_hash" \
        --arg pphase "$plan_phase" \
        --arg pmethod "$plan_method" \
        '. + {plan_version: $pv, brief_hash: $hash, created_at: $created, input_mode: $imode, input_path: $ipath, input_hash: $ihash, plan_phase: $pphase, plan_method: $pmethod}' \
        > "$PLAN_FILENAME"

    # During replan, strip depends_on references to completed changes from prior cycles
    if [[ -n "${_REPLAN_CYCLE:-}" && -f "$STATE_FILENAME" ]]; then
        local completed_names_json
        completed_names_json=$(jq -c '[.changes[]? | select(.status == "done" or .status == "merged" or .status == "merge-blocked") | .name]' "$STATE_FILENAME" 2>/dev/null || echo "[]")
        if [[ "$completed_names_json" != "[]" ]]; then
            local plan_names_json
            plan_names_json=$(jq -c '[.changes[].name]' "$PLAN_FILENAME")
            local tmp_plan
            tmp_plan=$(mktemp)
            jq --argjson completed "$completed_names_json" --argjson plan_names "$plan_names_json" '
                .changes = [.changes[] | .depends_on = [(.depends_on // [])[] | select(. as $d | $plan_names | index($d) != null)]]
            ' "$PLAN_FILENAME" > "$tmp_plan" && mv "$tmp_plan" "$PLAN_FILENAME"
            log_info "Replan: stripped resolved depends_on references from prior cycles"
        fi
    fi

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

    # Show phase detection for spec mode
    if [[ "$INPUT_MODE" == "spec" ]]; then
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

    # Collect completed change names for context (include merge-blocked — work is done, just merge issues)
    local completed_names
    completed_names=$(jq -r '[.changes[] | select(.status == "done" or .status == "merged" or .status == "merge-blocked") | .name] | join(", ")' "$STATE_FILENAME")
    local completed_roadmap
    completed_roadmap=$(jq -r '[.changes[] | select(.status == "done" or .status == "merged" or .status == "merge-blocked") | .roadmap_item] | join("; ")' "$STATE_FILENAME")

    log_info "========== REPLAN CYCLE $cycle =========="
    info "Completed so far: $completed_names"
    log_info "Auto-replan cycle $cycle — completed: $completed_names"

    emit_event "REPLAN" "" "{\"cycle\":$cycle,\"completed\":\"$completed_names\"}"

    # Re-run plan (cmd_plan knows how to handle spec mode, phase hints, etc.)
    local old_plan
    old_plan=$(mktemp)
    cp "$PLAN_FILENAME" "$old_plan"

    # Store completed info for the planner prompt to use
    export _REPLAN_COMPLETED="$completed_roadmap"
    export _REPLAN_CYCLE="$cycle"

    # Inject git log of completed changes with their file lists to prevent duplication
    local completed_file_context=""
    local merged_names
    merged_names=$(jq -r '.changes[] | select(.status == "merged") | .name' "$STATE_FILENAME" 2>/dev/null || true)
    if [[ -n "$merged_names" ]]; then
        while IFS= read -r cname; do
            [[ -z "$cname" ]] && continue
            # Get files from the merge commit (branch was squash-merged to main)
            local branch_name="$cname"
            local files_list
            files_list=$(git log --all --oneline --diff-filter=ACMR --name-only --format="" --grep="$cname" -- 2>/dev/null | sort -u | head -20 || true)
            if [[ -n "$files_list" ]]; then
                completed_file_context+="$cname: $files_list"$'\n'
            fi
        done <<< "$merged_names"
        if [[ -n "$completed_file_context" ]]; then
            _REPLAN_COMPLETED="${_REPLAN_COMPLETED}

Files modified by completed changes (avoid re-implementing):
$completed_file_context"
            export _REPLAN_COMPLETED
        fi
    fi

    # Recall orchestrator operational history for replan context
    local replan_memory
    replan_memory=$(orch_recall "orchestration merge conflict test failure review" 5 "phase:orchestration" || true)
    if [[ -n "$replan_memory" ]]; then
        export _REPLAN_MEMORY="${replan_memory:0:2000}"
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
        unset _REPLAN_COMPLETED _REPLAN_CYCLE _REPLAN_MEMORY
        return 2  # Error (distinct from 1=no new work)
    fi
    unset _REPLAN_COMPLETED _REPLAN_CYCLE _REPLAN_MEMORY

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

    init_state "$PLAN_FILENAME"

    # Restore cumulative metadata
    update_state_field "replan_cycle" "$cycle"
    update_state_field "prev_total_tokens" "$prev_total_tokens"
    update_state_field "active_seconds" "$prev_active_seconds"
    update_state_field "started_epoch" "$prev_started_epoch"
    update_state_field "time_limit_secs" "$prev_time_limit"
    update_state_field "cycle_started_at" "\"$(date -Iseconds)\""
    update_state_field "directives" "$(echo "$directives" | jq -c .)"

    # Dispatch newly ready changes
    dispatch_ready_changes "$max_parallel"

    return 0
}
