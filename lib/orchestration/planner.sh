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

    if [[ $warnings -gt 0 ]]; then
        send_notification "wt-orchestrate" "Plan has $warnings scope overlap warning(s) — review for duplicates" "normal"
    fi
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

    # Find and validate input (spec or brief)
    find_input || return 1

    info "Reading input ($INPUT_MODE): $INPUT_PATH"

    # Resolve directives (4-level precedence chain)
    local directives
    directives=$(resolve_directives "$INPUT_PATH")
    info "Directives: $(echo "$directives" | jq -c .)"

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
                item_mem=$(orch_recall "$item" 2 "" || true)
                [[ -n "$item_mem" ]] && item_texts+=("$item_mem")
            done < <(echo "$next_items" | jq -r '.[]' 2>/dev/null)
            # Also recall orchestrator operational context
            local orch_mem
            orch_mem=$(orch_recall "orchestration merge conflict test failure" 3 "source:orchestrator" || true)
            [[ -n "$orch_mem" ]] && item_texts+=("$orch_mem")
            memory_context=$(printf '%s\n' "${item_texts[@]}" | head -c 2000)
        else
            # Spec mode: recall using phase hint or general query + orchestrator context
            local spec_query="${PHASE_HINT:-project architecture and features}"
            memory_context=$(orch_recall "$spec_query" 3 "" || true)
            local orch_mem
            orch_mem=$(orch_recall "orchestration merge conflict test failure" 3 "source:orchestrator" || true)
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

    # Build decomposition prompt (dual-mode: brief vs spec)
    local input_content
    local hash
    hash=$(brief_hash "$INPUT_PATH")

    if [[ "$INPUT_MODE" == "spec" ]]; then
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
        input_content=$(cat "$INPUT_PATH")
    fi

    local prompt
    if [[ "$INPUT_MODE" == "spec" ]]; then
        # Spec-mode prompt: LLM determines what's next
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

## $test_infra_context
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
- Each change should be completable in 1-3 Ralph loop sessions (not too large, not too granular)
- Use kebab-case names (e.g., add-user-auth, refactor-payment-flow)
- Define dependencies: if change B needs code from change A, list A in depends_on
- Changes with no dependencies can run in parallel
- Complexity: S (< 10 tasks), M (10-25 tasks), L (25+ tasks)
- Skip already-active changes listed above
- Every change scope MUST include specific test requirements (happy path, error cases, security boundaries)
- For security-related changes: include tenant isolation tests, auth guard tests
- If no test infrastructure exists, the FIRST change MUST be "test-infrastructure-setup" setting up the test framework, config, helpers, and an example test. ALL other changes MUST depend on it.
- If test infrastructure exists, follow existing test patterns (framework and naming conventions noted above)

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

Smoke test awareness:
- If the project has smoke tests configured (smoke_command directive), changes that modify user-facing flows (login, navigation, forms, API endpoints) should include updates to relevant smoke test files as part of the change scope
- Organize smoke tests by functional group (auth, CRUD, navigation), not per-change

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
      "roadmap_item": "The spec section/item this implements"
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

## $test_infra_context

## Task
Analyze the "Next" section of the brief and decompose it into concrete, implementable OpenSpec changes.

Rules:
- Each change should be completable in 1-3 Ralph loop sessions (not too large, not too granular)
- Use kebab-case names (e.g., add-user-auth, refactor-payment-flow)
- Define dependencies: if change B needs code from change A, list A in depends_on
- Changes with no dependencies can run in parallel
- Complexity: S (< 10 tasks), M (10-25 tasks), L (25+ tasks)
- Every change scope MUST include specific test requirements (happy path, error cases, security boundaries)
- For security-related changes: include tenant isolation tests, auth guard tests
- If no test infrastructure exists, the FIRST change MUST be "test-infrastructure-setup" setting up the test framework, config, helpers, and an example test. ALL other changes MUST depend on it.
- If test infrastructure exists, follow existing test patterns (framework and naming conventions noted above)

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

Smoke test awareness:
- If the project has smoke tests configured (smoke_command directive), changes that modify user-facing flows (login, navigation, forms, API endpoints) should include updates to relevant smoke test files as part of the change scope
- Organize smoke tests by functional group (auth, CRUD, navigation), not per-change

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
    claude_output=$(export RUN_CLAUDE_TIMEOUT=300; echo "$prompt" | run_claude --model "$(model_id opus)") || {
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
    echo "$plan_json" | jq \
        --argjson pv "$plan_version" \
        --arg hash "$hash" \
        --arg created "$(date -Iseconds)" \
        --arg imode "$INPUT_MODE" \
        --arg ipath "$INPUT_PATH" \
        --arg ihash "$input_content_hash" \
        '. + {plan_version: $pv, brief_hash: $hash, created_at: $created, input_mode: $imode, input_path: $ipath, input_hash: $ihash}' \
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

    local change_count
    change_count=$(jq '.changes | length' "$PLAN_FILENAME")

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

    # Recall orchestrator operational history for replan context
    local replan_memory
    replan_memory=$(orch_recall "orchestration merge conflict test failure review" 5 "source:orchestrator" || true)
    if [[ -n "$replan_memory" ]]; then
        export _REPLAN_MEMORY="${replan_memory:0:2000}"
    fi

    # Restore input path from plan so cmd_plan's find_input() can find it
    local plan_input_mode plan_input_path
    plan_input_mode=$(jq -r '.input_mode // empty' "$PLAN_FILENAME")
    plan_input_path=$(jq -r '.input_path // empty' "$PLAN_FILENAME")
    if [[ "$plan_input_mode" == "spec" && -n "$plan_input_path" ]]; then
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
