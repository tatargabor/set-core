#!/usr/bin/env bash
# wt-audit shared helpers — output formatting, check registration, JSON building
# Source this file from check-*.sh functions and bin/wt-audit

# ─── Output arrays (populated by check functions) ───────────────────────────

# Each check entry: "dimension|id|status|detail"
# status: pass, warn, fail
declare -a AUDIT_CHECKS=()

# Each guidance entry: "dimension|action|sources"
# sources: semicolon-separated READ pointers
declare -a AUDIT_GUIDANCE=()

# Each source entry: "dimension|path"
declare -a AUDIT_SOURCES=()

# ─── Status icons ───────────────────────────────────────────────────────────

icon_pass="✅"
icon_warn="⚠️"
icon_fail="❌"

# ─── Check registration ────────────────────────────────────────────────────

# Add a check result.
# Usage: add_check <dimension> <id> <status> <detail>
# status: pass | warn | fail
add_check() {
    local dimension="$1" id="$2" status="$3" detail="$4"
    AUDIT_CHECKS+=("${dimension}|${id}|${status}|${detail}")
}

# Add guidance for a gap.
# Usage: add_guidance <dimension> <action> <sources>
# sources: semicolon-separated "READ: path — description" entries
add_guidance() {
    local dimension="$1" action="$2" sources="$3"
    AUDIT_GUIDANCE+=("${dimension}|${action}|${sources}")
}

# Track a source file for a dimension.
# Usage: add_source <dimension> <path>
add_source() {
    local dimension="$1" path="$2"
    AUDIT_SOURCES+=("${dimension}|${path}")
}

# ─── Human-readable output ─────────────────────────────────────────────────

# Print a dimension header
print_dimension_header() {
    local title="$1"
    echo ""
    echo -e "  ${BLUE}${title}${NC}"
}

# Print all checks for a dimension
print_dimension_checks() {
    local dimension="$1"
    for entry in "${AUDIT_CHECKS[@]}"; do
        IFS='|' read -r dim id status detail <<< "$entry"
        [[ "$dim" != "$dimension" ]] && continue
        local icon
        case "$status" in
            pass) icon="$icon_pass" ;;
            warn) icon="$icon_warn" ;;
            fail) icon="$icon_fail" ;;
        esac
        echo "  ${icon} ${detail}"
    done
}

# Print guidance for a dimension
print_dimension_guidance() {
    local dimension="$1"
    local has_guidance=false
    for entry in "${AUDIT_GUIDANCE[@]}"; do
        IFS='|' read -r dim action sources <<< "$entry"
        [[ "$dim" != "$dimension" ]] && continue
        if ! $has_guidance; then
            has_guidance=true
        fi
        echo "    → ${action}"
        # Split sources by semicolon
        IFS=';' read -ra source_list <<< "$sources"
        for src in "${source_list[@]}"; do
            src=$(echo "$src" | sed 's/^ *//')
            [[ -n "$src" ]] && echo "      ${src}"
        done
    done
}

# Print summary line
print_summary() {
    local pass=0 warn=0 fail=0
    for entry in "${AUDIT_CHECKS[@]}"; do
        IFS='|' read -r _ _ status _ <<< "$entry"
        case "$status" in
            pass) pass=$((pass + 1)) ;;
            warn) warn=$((warn + 1)) ;;
            fail) fail=$((fail + 1)) ;;
        esac
    done
    echo ""
    echo "  Summary: ${icon_pass} ${pass}  ${icon_warn} ${warn}  ${icon_fail} ${fail}"
}

# Print condensed summary (for wt-project init integration)
print_condensed_summary() {
    local pass=0 warn=0 fail=0
    for entry in "${AUDIT_CHECKS[@]}"; do
        IFS='|' read -r _ _ status _ <<< "$entry"
        case "$status" in
            pass) pass=$((pass + 1)) ;;
            warn) warn=$((warn + 1)) ;;
            fail) fail=$((fail + 1)) ;;
        esac
    done
    if [[ $fail -eq 0 && $warn -eq 0 ]]; then
        echo "  Health: ${icon_pass} all checks passed"
    else
        echo "  Health: ${icon_pass} ${pass}  ${icon_warn} ${warn}  ${icon_fail} ${fail} — run /wt:audit for details"
    fi
}

# ─── JSON output ────────────────────────────────────────────────────────────

# Build JSON output from collected data
build_json() {
    local project_name="$1"
    local timestamp
    timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    local pass=0 warn=0 fail=0
    for entry in "${AUDIT_CHECKS[@]}"; do
        IFS='|' read -r _ _ status _ <<< "$entry"
        case "$status" in
            pass) pass=$((pass + 1)) ;;
            warn) warn=$((warn + 1)) ;;
            fail) fail=$((fail + 1)) ;;
        esac
    done

    # Build dimensions object with jq
    local dimensions_json="{}"

    # Get unique dimensions
    local -a dimensions=()
    for entry in "${AUDIT_CHECKS[@]}"; do
        local dim="${entry%%|*}"
        local found=false
        for d in "${dimensions[@]}"; do
            [[ "$d" == "$dim" ]] && found=true && break
        done
        $found || dimensions+=("$dim")
    done

    for dim in "${dimensions[@]}"; do
        # Collect checks for this dimension
        local checks_json="[]"
        for entry in "${AUDIT_CHECKS[@]}"; do
            IFS='|' read -r d id status detail <<< "$entry"
            [[ "$d" != "$dim" ]] && continue
            checks_json=$(echo "$checks_json" | jq \
                --arg id "$id" --arg status "$status" --arg detail "$detail" \
                '. + [{"id": $id, "status": $status, "detail": $detail}]')
        done

        # Collect sources for this dimension
        local sources_json="[]"
        for entry in "${AUDIT_SOURCES[@]}"; do
            IFS='|' read -r d path <<< "$entry"
            [[ "$d" != "$dim" ]] && continue
            sources_json=$(echo "$sources_json" | jq --arg p "$path" '. + [$p]')
        done

        # Collect guidance for this dimension
        local guidance_json="[]"
        for entry in "${AUDIT_GUIDANCE[@]}"; do
            IFS='|' read -r d action sources <<< "$entry"
            [[ "$d" != "$dim" ]] && continue
            local sources_arr="[]"
            IFS=';' read -ra source_list <<< "$sources"
            for src in "${source_list[@]}"; do
                src=$(echo "$src" | sed 's/^ *//')
                [[ -n "$src" ]] && sources_arr=$(echo "$sources_arr" | jq --arg s "$src" '. + [$s]')
            done
            guidance_json=$(echo "$guidance_json" | jq \
                --arg action "$action" --argjson sources "$sources_arr" \
                '. + [{"action": $action, "sources": $sources}]')
        done

        dimensions_json=$(echo "$dimensions_json" | jq \
            --arg dim "$dim" \
            --argjson checks "$checks_json" \
            --argjson sources "$sources_json" \
            --argjson guidance "$guidance_json" \
            '.[$dim] = {"checks": $checks, "sources": $sources, "guidance": $guidance}')
    done

    jq -n \
        --arg project "$project_name" \
        --arg timestamp "$timestamp" \
        --argjson dimensions "$dimensions_json" \
        --argjson pass "$pass" \
        --argjson warn "$warn" \
        --argjson fail "$fail" \
        '{
            "project": $project,
            "timestamp": $timestamp,
            "dimensions": $dimensions,
            "summary": {"pass": $pass, "warn": $warn, "fail": $fail}
        }'
}

# ─── Utility ────────────────────────────────────────────────────────────────

# Get line count of a file (0 if not exists)
file_lines() {
    local f="$1"
    if [[ -f "$f" ]]; then
        wc -l < "$f"
    else
        echo 0
    fi
}

# Get human-readable mtime
file_mtime_human() {
    local f="$1"
    if [[ -f "$f" ]]; then
        case "$PLATFORM" in
            macos) stat -f "%Sm" -t "%Y-%m-%d" "$f" 2>/dev/null ;;
            *)     date -r "$f" +"%Y-%m-%d" 2>/dev/null ;;
        esac
    fi
}

# Check if a file contains a pattern (quiet)
file_contains() {
    local f="$1" pattern="$2"
    [[ -f "$f" ]] && grep -q "$pattern" "$f" 2>/dev/null
}
