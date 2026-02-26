#!/usr/bin/env bash
# Check: Code quality signals — large files, unused code tooling

check_code_signals() {
    local project_path="$1"
    local dim="code_signals"

    add_source "$dim" "package.json"

    # ── Large files ──────────────────────────────────────────────────────
    local -a extensions
    mapfile -t extensions < <(get_source_extensions)

    # Build find expression for extensions
    local find_expr=""
    for ext in "${extensions[@]}"; do
        if [[ -n "$find_expr" ]]; then
            find_expr="$find_expr -o"
        fi
        find_expr="$find_expr -name \"*.${ext}\""
    done

    # Find files > 400 lines, excluding common non-source directories
    local large_files=""
    if [[ -n "$find_expr" ]]; then
        large_files=$(eval "find \"$project_path\" \
            -not -path '*/node_modules/*' \
            -not -path '*/.next/*' \
            -not -path '*/dist/*' \
            -not -path '*/build/*' \
            -not -path '*/generated/*' \
            -not -path '*/.claude/*' \
            -not -path '*/openspec/*' \
            -not -path '*/.venv/*' \
            -not -path '*/venv/*' \
            -not -path '*/__pycache__/*' \
            -not -path '*/site-packages/*' \
            -not -path '*/.git/*' \
            -not -path '*/.vercel/*' \
            -not -path '*/.svelte-kit/*' \
            -not -path '*/.nuxt/*' \
            -not -path '*/.astro/*' \
            -type f \\( $find_expr \\)" 2>/dev/null | while read -r f; do
            local lines
            lines=$(wc -l < "$f" 2>/dev/null || echo 0)
            if [[ "$lines" -gt 400 ]]; then
                local rel_path="${f#"$project_path/"}"
                echo "${lines} ${rel_path}"
            fi
        done | sort -rn | head -10 || true)
    fi

    if [[ -n "$large_files" ]]; then
        local count
        count=$(echo "$large_files" | wc -l)
        add_check "$dim" "large_files" "warn" "${count} file(s) exceed 400-line guideline"

        # Add individual file details
        while IFS= read -r line; do
            local flines="${line%% *}"
            local fpath="${line#* }"
            add_check "$dim" "large_$(echo "$fpath" | tr '/' '_')" "warn" "  ${fpath}: ${flines} lines"
        done <<< "$large_files"
    else
        add_check "$dim" "large_files" "pass" "No source files exceed 400-line guideline"
    fi

    # ── Unused code tooling ──────────────────────────────────────────────
    if [[ -f "$project_path/package.json" ]]; then
        local has_knip=false
        local has_depcheck=false
        local script_name=""

        file_contains "$project_path/package.json" '"knip"' && has_knip=true
        file_contains "$project_path/package.json" '"depcheck"' && has_depcheck=true

        # Check scripts for unused-code commands
        script_name=$(jq -r '.scripts | to_entries[] | select(.value | test("knip|depcheck")) | .key' "$project_path/package.json" 2>/dev/null | head -1)

        if $has_knip || $has_depcheck; then
            local tool_name="knip"
            $has_depcheck && tool_name="depcheck"
            if [[ -n "$script_name" ]]; then
                add_check "$dim" "unused_tooling" "pass" "Unused code detection: ${tool_name} (${STACK_PKG_MANAGER:-npm} run ${script_name})"
            else
                add_check "$dim" "unused_tooling" "pass" "Unused code detection: ${tool_name} installed"
            fi
        else
            add_check "$dim" "unused_tooling" "warn" "No unused code detection tool (knip, depcheck)"
            add_guidance "$dim" "Add knip for unused exports/files/dependencies detection" "READ: package.json — add knip to devDependencies and scripts"
        fi
    fi
}
