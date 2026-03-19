#!/usr/bin/env bash
# Check: CLAUDE.md structure — conventions, imports, managed sections

check_claude_md() {
    local project_path="$1"
    local claude_md="$project_path/CLAUDE.md"
    local dim="claude_md"

    add_source "$dim" "CLAUDE.md"

    if [[ ! -f "$claude_md" ]]; then
        add_check "$dim" "exists" "fail" "No CLAUDE.md found"
        add_guidance "$dim" "Create CLAUDE.md with project conventions" "READ: docs/design/*.md (if exists) — summarize conventions; READ: package.json — tech stack; REFERENCE: lib/audit/reference.md#claudemd-structure"
        return
    fi

    local lines
    lines=$(file_lines "$claude_md")
    add_check "$dim" "exists" "pass" "CLAUDE.md exists (${lines} lines)"

    # ── Convention references ────────────────────────────────────────────
    if file_contains "$claude_md" "docs/design\|conventions\|Conventions"; then
        add_check "$dim" "conventions" "pass" "References design docs or conventions"
    else
        add_check "$dim" "conventions" "warn" "No convention references found"
        add_guidance "$dim" "Add convention summaries pointing to docs/design/*.md" "READ: CLAUDE.md — current content; READ: docs/design/*.md — conventions to reference"
    fi

    # ── Managed sections ─────────────────────────────────────────────────
    if file_contains "$claude_md" "Persistent Memory"; then
        add_check "$dim" "memory_section" "pass" "Persistent Memory section present"
    else
        add_check "$dim" "memory_section" "warn" "No Persistent Memory section"
        add_guidance "$dim" "Run set-project init to add Persistent Memory section" ""
    fi

    if file_contains "$claude_md" "Auto-Commit After Apply"; then
        add_check "$dim" "commit_section" "pass" "Auto-Commit section present"
    else
        add_check "$dim" "commit_section" "warn" "No Auto-Commit After Apply section"
        add_guidance "$dim" "Run set-project init to add Auto-Commit section" ""
    fi

    # ── @import usage ────────────────────────────────────────────────────
    if file_contains "$claude_md" "^@"; then
        add_check "$dim" "imports" "pass" "Uses @import for automatic doc loading"
    fi
}
