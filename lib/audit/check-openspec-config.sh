#!/usr/bin/env bash
# Check: OpenSpec config — config.yaml context and rules

check_openspec_config() {
    local project_path="$1"
    local config="$project_path/openspec/config.yaml"
    local dim="openspec_config"

    add_source "$dim" "openspec/config.yaml"

    if [[ ! -f "$config" ]]; then
        # Check if openspec is initialized at all
        if [[ ! -d "$project_path/openspec" ]]; then
            add_check "$dim" "openspec" "fail" "No openspec/ directory — not initialized"
            add_guidance "$dim" "Run 'openspec init' to initialize OpenSpec" ""
        else
            add_check "$dim" "config" "fail" "No openspec/config.yaml"
            add_guidance "$dim" "Create openspec/config.yaml with project context" "READ: package.json — tech stack; READ: CLAUDE.md — conventions; REFERENCE: lib/audit/reference.md#openspec-config"
        fi
        return
    fi

    # Check context field
    local context_content
    context_content=$(python3 -c "
import yaml, sys
with open(sys.argv[1]) as f:
    d = yaml.safe_load(f) or {}
c = d.get('context', '')
print(len(str(c)) if c else 0)
" "$config" 2>/dev/null || echo "0")

    if [[ "$context_content" -gt 50 ]]; then
        add_check "$dim" "context" "pass" "Config context populated (${context_content} chars)"
    elif [[ "$context_content" -gt 0 ]]; then
        add_check "$dim" "context" "warn" "Config context is sparse (${context_content} chars)"
        add_guidance "$dim" "Expand openspec/config.yaml context with tech stack, domain, key patterns" "READ: package.json; READ: CLAUDE.md; READ: docs/design/*.md (if exists)"
    else
        add_check "$dim" "context" "fail" "Config context is empty"
        local sources="READ: package.json — tech stack and dependencies"
        [[ -f "$project_path/CLAUDE.md" ]] && sources="${sources}; READ: CLAUDE.md — conventions and patterns"
        sources="${sources}; REFERENCE: lib/audit/reference.md#openspec-config"
        add_guidance "$dim" "Populate openspec/config.yaml context field" "$sources"
    fi

    # Check rules field
    local has_rules
    has_rules=$(python3 -c "
import yaml, sys
with open(sys.argv[1]) as f:
    d = yaml.safe_load(f) or {}
r = d.get('rules', {})
print(len(r) if isinstance(r, dict) else 0)
" "$config" 2>/dev/null || echo "0")

    if [[ "$has_rules" -gt 0 ]]; then
        add_check "$dim" "rules" "pass" "Config rules defined (${has_rules} artifact types)"
    else
        add_check "$dim" "rules" "warn" "No rules section in config"
        add_guidance "$dim" "Add rules section for artifact guidelines (proposal, design, specs, tasks)" "REFERENCE: lib/audit/reference.md#openspec-config"
    fi
}
