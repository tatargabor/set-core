#!/usr/bin/env bash
# Check: Gitignore coverage — sensitive files and Claude-specific patterns

check_gitignore() {
    local project_path="$1"
    local gitignore="$project_path/.gitignore"
    local dim="gitignore"

    add_source "$dim" ".gitignore"

    if [[ ! -f "$gitignore" ]]; then
        add_check "$dim" "exists" "fail" "No .gitignore found"
        add_guidance "$dim" "Create .gitignore with sensitive file patterns" "REFERENCE: lib/audit/reference.md#gitignore-coverage"
        return
    fi

    # Required patterns
    local -a required_patterns=(".env" "CLAUDE.local.md" ".claude/settings.local.json")
    local -a pattern_descriptions=("Environment secrets" "Personal Claude instructions" "Personal Claude settings")
    local missing=0

    for i in "${!required_patterns[@]}"; do
        local pattern="${required_patterns[$i]}"
        local desc="${pattern_descriptions[$i]}"

        # Check if gitignore covers this pattern (exact or glob)
        if grep -q "^${pattern}" "$gitignore" 2>/dev/null || \
           grep -q "^\.env\*" "$gitignore" 2>/dev/null && [[ "$pattern" == ".env" ]]; then
            add_check "$dim" "pattern_${i}" "pass" "${pattern} covered (${desc})"
        else
            add_check "$dim" "pattern_${i}" "warn" "Missing: ${pattern} (${desc})"
            missing=$((missing + 1))
        fi
    done

    if [[ $missing -gt 0 ]]; then
        add_guidance "$dim" "Add missing patterns to .gitignore" "REFERENCE: lib/audit/reference.md#gitignore-coverage"
    fi
}
