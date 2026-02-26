#!/usr/bin/env bash
# Check: Claude Code config — permissions, hooks, agents, rules

check_claude_config() {
    local project_path="$1"
    local settings="$project_path/.claude/settings.json"
    local dim="claude_config"

    add_source "$dim" ".claude/settings.json"

    # ── Permissions ──────────────────────────────────────────────────────
    if [[ -f "$settings" ]]; then
        local allow_count deny_count
        allow_count=$(jq -r '.permissions.allow // [] | length' "$settings" 2>/dev/null || echo 0)
        deny_count=$(jq -r '.permissions.deny // [] | length' "$settings" 2>/dev/null || echo 0)

        if [[ "$allow_count" -gt 0 ]]; then
            add_check "$dim" "permissions" "pass" "Permissions configured (${allow_count} allow, ${deny_count} deny)"
        else
            add_check "$dim" "permissions" "fail" "No permission allowlist configured"
            local guidance_sources="READ: package.json — identify build/test/lint commands"
            if [[ -n "$STACK_PKG_MANAGER" ]]; then
                local rec_cmds
                rec_cmds=$(get_recommended_safe_commands | head -5 | tr '\n' ', ' | sed 's/,$//')
                guidance_sources="${guidance_sources}; Recommended: ${rec_cmds}"
            fi
            add_guidance "$dim" "Add permissions.allow to .claude/settings.json with safe commands" "$guidance_sources"
        fi
    else
        add_check "$dim" "permissions" "fail" "No .claude/settings.json found"
        add_guidance "$dim" "Run wt-project init to create .claude/settings.json" "READ: package.json — for stack-specific safe commands"
    fi

    # ── Memory hooks ─────────────────────────────────────────────────────
    if [[ -f "$settings" ]]; then
        if file_contains "$settings" "wt-hook-memory"; then
            local hook_events
            hook_events=$(grep -c "wt-hook-memory" "$settings" 2>/dev/null || echo 0)
            add_check "$dim" "memory_hooks" "pass" "Memory hooks deployed (${hook_events} events)"
        else
            add_check "$dim" "memory_hooks" "fail" "No wt-hook-memory hooks found"
            add_guidance "$dim" "Run wt-deploy-hooks to install memory hooks" ""
        fi
    fi

    # ── Verification hook ────────────────────────────────────────────────
    if [[ -f "$settings" ]]; then
        if file_contains "$settings" "verify-ts\|tsc --noEmit"; then
            add_check "$dim" "verify_hook" "pass" "TypeScript verification hook active"
        elif $STACK_TYPESCRIPT; then
            add_check "$dim" "verify_hook" "warn" "No TypeScript verification hook (PostToolUse:Edit/Write)"
            add_guidance "$dim" "Add verify-ts.sh hook for PostToolUse:Edit and PostToolUse:Write" "READ: scripts/hooks/verify-ts.sh (if exists); REFERENCE: lib/audit/reference.md#hooks"
        fi
    fi

    # ── Agents ───────────────────────────────────────────────────────────
    local agents_dir="$project_path/.claude/agents"
    add_source "$dim" ".claude/agents/"

    if [[ -d "$agents_dir" ]] && ls "$agents_dir"/*.md &>/dev/null; then
        local agent_list=""
        local agent_count=0
        for f in "$agents_dir"/*.md; do
            local aname
            aname=$(basename "$f" .md)
            local amodel
            amodel=$(grep -oP 'model:\s*\K\S+' "$f" 2>/dev/null || echo "default")
            agent_list="${agent_list}${aname}(${amodel}), "
            agent_count=$((agent_count + 1))
        done
        agent_list="${agent_list%, }"
        add_check "$dim" "agents" "pass" "Agents: ${agent_list}"

        # Check for stale agents — look for references to non-existent test frameworks
        for f in "$agents_dir"/*.md; do
            if grep -q "pytest" "$f" 2>/dev/null && [[ ! -d "$project_path/tests" ]] && ! file_contains "$project_path/package.json" "pytest"; then
                local stale_name
                stale_name=$(basename "$f" .md)
                add_check "$dim" "agent_stale_${stale_name}" "warn" "Agent '${stale_name}' references pytest but no tests/ directory found"
                add_guidance "$dim" "Update ${stale_name} agent to match actual test framework" "READ: .claude/agents/${stale_name}.md; READ: package.json (test framework)"
            fi
        done
    else
        add_check "$dim" "agents" "warn" "No custom agents defined"
        add_guidance "$dim" "Create .claude/agents/code-reviewer.md with project-specific review checklist" "READ: docs/design/*.md (conventions to enforce); READ: CLAUDE.md (project patterns); REFERENCE: lib/audit/reference.md#agents"
    fi

    # ── Rules ────────────────────────────────────────────────────────────
    local rules_dir="$project_path/.claude/rules"
    add_source "$dim" ".claude/rules/"

    if [[ -d "$rules_dir" ]] && ls "$rules_dir"/*.md &>/dev/null; then
        local wt_managed=0
        local project_specific=0
        for f in "$rules_dir"/*.md; do
            local rname
            rname=$(basename "$f")
            if [[ "$rname" == wt-* ]]; then
                wt_managed=$((wt_managed + 1))
            else
                project_specific=$((project_specific + 1))
            fi
        done

        if [[ $project_specific -gt 0 ]]; then
            add_check "$dim" "rules" "pass" "Rules: ${project_specific} project-specific, ${wt_managed} wt-managed"
        else
            add_check "$dim" "rules" "warn" "Only wt-managed rules (${wt_managed}), no project-specific rules"
            add_guidance "$dim" "Create path-scoped rules for distinct code areas" "READ: src/ directory structure — identify distinct code areas (UI, API, DB); REFERENCE: lib/audit/reference.md#rules"
        fi
    else
        add_check "$dim" "rules" "warn" "No .claude/rules/ directory"
        add_guidance "$dim" "Create .claude/rules/ with path-scoped rules for distinct code areas" "REFERENCE: lib/audit/reference.md#rules"
    fi
}
