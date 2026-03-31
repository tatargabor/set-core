#!/usr/bin/env bash
# lib/design/bridge.sh — Design tool abstraction layer
# Detects registered design MCP servers, exports config for run_claude --mcp-config,
# and generates design-aware prompt sections for planner/verifier/dispatcher.
#
# Usage: source this file after config.sh. All functions are non-fatal.
# If no design MCP is detected, functions return 1 silently.

# ─── Log Fallbacks ────────────────────────────────────────────────────
# When sourced standalone (e.g. from Python subprocess), set-common.sh
# may not be loaded.  Define no-op fallbacks so calls never fail.
type -t info  &>/dev/null || info()  { echo "[design-bridge] $*"; }
type -t warn  &>/dev/null || warn()  { echo "[design-bridge] WARN: $*" >&2; }
type -t error &>/dev/null || error() { echo "[design-bridge] ERROR: $*" >&2; }

# ─── Detection ────────────────────────────────────────────────────────

# Detect a registered design MCP server from .claude/settings.json.
# Prints the server name (e.g., "figma") and returns 0, or returns 1 if none found.
detect_design_mcp() {
    local project_root="${PROJECT_ROOT:-.}"
    local settings="$project_root/.claude/settings.json"
    [[ -f "$settings" ]] || return 1

    local design_server
    design_server=$(jq -r '
      .mcpServers // {} | keys[] |
      select(test("^(figma|penpot|sketch|zeplin)"))
    ' "$settings" 2>/dev/null | head -1)

    [[ -n "$design_server" ]] && echo "$design_server" || return 1
}

# ─── Config Export ────────────────────────────────────────────────────

# Extract a design MCP server's config into a temp JSON file for --mcp-config.
# Args: $1 = server name (from detect_design_mcp)
# Prints the temp file path to stdout.
get_design_mcp_config() {
    local server_name="$1"
    local project_root="${PROJECT_ROOT:-.}"
    local settings="$project_root/.claude/settings.json"
    [[ -f "$settings" ]] || return 1

    local config_file
    config_file=$(mktemp --suffix=.json)

    if ! jq --arg name "$server_name" '{
      mcpServers: { ($name): .mcpServers[$name] }
    }' "$settings" > "$config_file" 2>/dev/null; then
        rm -f "$config_file"
        return 1
    fi

    echo "$config_file"
}

# ─── Design File Reference ───────────────────────────────────────────

# Read design_file from .claude/orchestration.yaml and export as DESIGN_FILE_REF.
# Returns 1 if no design_file configured.
load_design_file_ref() {
    local project_root="${PROJECT_ROOT:-.}"
    # Check both possible config locations
    local config="$project_root/set/orchestration/config.yaml"
    [[ -f "$config" ]] || config="$project_root/.claude/orchestration.yaml"
    [[ -f "$config" ]] || return 1

    local ref
    # Try yq first (YAML-native), fall back to grep for simple key: value
    if command -v yq &>/dev/null; then
        ref=$(yq -r '.design_file // empty' "$config" 2>/dev/null)
    else
        ref=$(grep -E '^design_file:' "$config" 2>/dev/null | sed 's/^design_file:[[:space:]]*//' | tr -d '"'"'")
    fi

    if [[ -n "$ref" ]]; then
        export DESIGN_FILE_REF="$ref"
        return 0
    fi
    return 1
}

# ─── Prompt Enrichment ────────────────────────────────────────────────

# Generate a design-aware prompt section for planner/verifier prompts.
# Args: $1 = server name (e.g., "figma"), $2 = optional snapshot dir
# Uses DESIGN_FILE_REF env var if set.
# When a cached snapshot exists at $2/design-snapshot.md, returns its content
# instead of generic instructions.
design_prompt_section() {
    local server_name="$1"
    local snapshot_dir="${2:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local snapshot_file="$snapshot_dir/design-snapshot.md"
    local design_file_ref="${DESIGN_FILE_REF:-}"

    # Prefer cached snapshot if available
    if [[ -f "$snapshot_file" && -s "$snapshot_file" ]]; then
        cat <<EOF
## Design Context (Snapshot)

The following design snapshot was extracted from the $server_name design tool.
Use this data for planning — map changes to specific frames, use exact token values,
and follow the component hierarchy. The $server_name MCP is also available for live
queries during implementation.

EOF
        cat "$snapshot_file"

        cat <<'EOF'

When planning changes that involve UI:
- Reference specific frames and components from the snapshot above
- Use exact design token values (colors, spacing, typography)
- IMPORTANT: Embed specific design token values (e.g., "bg-blue-600", "text-3xl", "rounded-lg") and frame names directly in each change scope description. The agent will NOT see this snapshot — only the scope text you write.
- If a required frame/page is MISSING from the snapshot, flag it as an ambiguity with type "design_gap"
- Include design frame references in change scope descriptions
EOF

        # Append data model section if Figma sources contain interfaces/types
        local data_model
        data_model=$(design_data_model_section "$snapshot_dir" 2>/dev/null) || true
        if [[ -n "$data_model" ]]; then
            echo ""
            echo "$data_model"
        fi

        return 0
    fi

    # Fallback: generic instructions (no snapshot available)
    cat <<EOF
## Design Context

A design tool ($server_name) is available via MCP. You can query it for:
- Frame/page inventory: what screens/views are designed
- Component details: properties, variants, states
- Design tokens: colors, spacing, typography, shadows
- Layout information: auto-layout, constraints, dimensions
EOF

    if [[ -n "$design_file_ref" ]]; then
        echo ""
        echo "Design file reference: $design_file_ref"
    fi

    cat <<'EOF'

When planning changes that involve UI:
- Query the design tool to understand what frames exist
- Map each change to specific design frames
- If a required frame/page is MISSING from the design, flag it as an ambiguity with type "design_gap"
- Include design frame references in change scope descriptions
EOF
}

# ─── Health Check ────────────────────────────────────────────────

# Test MCP connectivity by running a lightweight probe via run_claude.
# Requires DESIGN_MCP_CONFIG to be set (call setup_design_bridge first).
# Returns 0 if MCP responds successfully, 1 if auth fails or timeout.
check_design_mcp_health() {
    local config="${DESIGN_MCP_CONFIG:-}"
    local server_name="${DESIGN_MCP_NAME:-unknown}"
    [[ -n "$config" && -f "$config" ]] || return 1

    local probe_prompt="Call the $server_name MCP whoami tool to verify authentication. If authenticated, respond with exactly: MCP_HEALTHY. If not authenticated or any error, respond with exactly: MCP_AUTH_FAILED"

    local output rc=0
    output=$(export RUN_CLAUDE_TIMEOUT=30; echo "$probe_prompt" | run_claude --output-format text --mcp-config "$config" 2>/dev/null) || rc=$?

    if [[ $rc -ne 0 ]]; then
        warn "Design MCP health check timed out or failed (rc=$rc)"
        return 1
    fi

    if echo "$output" | grep -q "MCP_HEALTHY"; then
        info "Design MCP health check passed: $server_name"
        return 0
    else
        warn "Design MCP not authenticated: $server_name"
        return 1
    fi
}

# ─── Design Snapshot ─────────────────────────────────────────────────

# Fetch full design content via sequential focused MCP calls and save as markdown.
# Uses scripts/fetch-figma-design.py for reliable extraction (no single-prompt confusion).
# Args: $1 = optional "force" to re-fetch even if cached
# Requires: DESIGN_MCP_CONFIG, DESIGN_FILE_REF, DESIGN_SNAPSHOT_DIR (or pwd)
# Returns 0 if snapshot saved, 1 on failure/skip.
fetch_design_snapshot() {
    local force="${1:-}"
    local config="${DESIGN_MCP_CONFIG:-}"
    local server_name="${DESIGN_MCP_NAME:-unknown}"
    local design_ref="${DESIGN_FILE_REF:-}"
    local snapshot_dir="${DESIGN_SNAPSHOT_DIR:-.}"
    local snapshot_file="$snapshot_dir/design-snapshot.md"

    [[ -n "$config" && -f "$config" ]] || return 1

    if [[ -z "$design_ref" ]]; then
        warn "No design file reference — skipping snapshot"
        return 1
    fi

    # Cache check: skip if snapshot exists and not forcing
    if [[ "$force" != "force" && -f "$snapshot_file" && -s "$snapshot_file" ]]; then
        info "Using cached design snapshot"
        return 0
    fi

    info "Fetching design snapshot from $server_name MCP..."

    # Emit heartbeat so sentinel knows we're alive during long MCP calls
    if type -t emit_event &>/dev/null; then
        emit_event "DESIGN_PREFLIGHT" "" "{\"phase\":\"snapshot_fetch\",\"server\":\"$server_name\"}" 2>/dev/null || true
    fi

    # Locate the fetcher script
    local script_dir
    script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/scripts"
    local fetcher="$script_dir/fetch-figma-design.py"

    if [[ ! -f "$fetcher" ]]; then
        warn "fetch-figma-design.py not found at $fetcher"
        return 1
    fi

    # Run fetcher with periodic heartbeat to prevent sentinel stuck detection.
    # The fetcher makes 4 sequential MCP calls (~4-5 min total).
    # We emit heartbeat events every 60s so sentinel sees activity.
    local rc=0
    local _hb_count=0
    python3 "$fetcher" --mcp-config "$config" "$design_ref" -o "$snapshot_dir" 2>&1 | while IFS= read -r line; do
        info "  $line"
        # Emit heartbeat on each step progress line (contains [N/4])
        if [[ "$line" == *"/"*"]"* ]] && type -t emit_event &>/dev/null; then
            _hb_count=$((_hb_count + 1))
            emit_event "DESIGN_HEARTBEAT" "" "{\"step\":$_hb_count,\"detail\":\"$(echo "$line" | head -c 80)\"}" 2>/dev/null || true
        fi
    done || rc=$?

    if [[ $rc -ne 0 ]]; then
        warn "Design snapshot fetch failed (rc=$rc)"
        return 1
    fi

    if [[ ! -s "$snapshot_file" ]]; then
        warn "Design snapshot fetch returned empty output"
        return 1
    fi

    info "Design snapshot saved ($(wc -c < "$snapshot_file") bytes)"

    # Copy to shared runtime dir so all worktrees can find it
    local _script_dir
    _script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
    if [[ -f "$_script_dir/bin/set-paths" ]]; then
        source "$_script_dir/bin/set-paths" 2>/dev/null || true
        if [[ -n "$WT_RUNTIME_DIR" ]]; then
            mkdir -p "$WT_RUNTIME_DIR"
            cp "$snapshot_file" "$WT_RUNTIME_DIR/design-snapshot.md"
            info "Design snapshot copied to shared runtime"
        fi
    fi

    # Legacy: also copy to project root
    local project_root="${PROJECT_ROOT:-.}"
    local root_snapshot="$project_root/design-snapshot.md"
    if [[ "$snapshot_file" != "$root_snapshot" ]]; then
        cp "$snapshot_file" "$root_snapshot"
        info "Design snapshot copied to project root (legacy)"
    fi

    return 0
}

# ─── Snapshot finder ─────────────────────────────────────────────────

# Recursively find the first design-snapshot.md under a directory.
# Args: $1 = search root (defaults to DESIGN_SNAPSHOT_DIR or .)
# Prints the path to stdout. Returns 1 if not found.
_find_design_snapshot() {
    local search_root="${1:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local found
    found=$(find "$search_root" -name "design-snapshot.md" -type f 2>/dev/null | head -1)
    [[ -n "$found" && -s "$found" ]] || return 1
    echo "$found"
}

# ─── Dispatch Context ────────────────────────────────────────────────

# Extract frame-filtered design context from design-snapshot.md for agent dispatch.
# Returns Design Tokens + relevant Component Hierarchy sections (max 100 lines).
# Args: $1 = scope text, $2 = snapshot dir (optional, defaults to DESIGN_SNAPSHOT_DIR or .)
# Prints filtered markdown to stdout. Returns 1 if no snapshot available.
design_context_for_dispatch() {
    local scope_text="$1"
    local snapshot_dir="${2:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local max_lines=200

    # Priority 1: design-system.md (structured, from set-design-sync)
    local design_system=""
    for ds_path in "docs/design-system.md" "design-system.md" "docs/design/design-system.md"; do
        if [[ -f "$ds_path" ]] && grep -q "## Design Tokens" "$ds_path" 2>/dev/null; then
            design_system="$ds_path"
            break
        fi
    done

    if [[ -n "$design_system" ]]; then
        _dispatch_from_design_system "$scope_text" "$design_system" "$max_lines"
        return $?
    fi

    # Priority 2: design-snapshot.md (legacy — may contain Tailwind class stats)
    local snapshot_file
    snapshot_file=$(_find_design_snapshot "$snapshot_dir") || return 1

    local output=""
    local tokens_section=""
    local matched_frames=""

    # Extract Design Tokens section (always included)
    tokens_section=$(awk '
        /^## Design Tokens$/,/^## / {
            if (/^## / && !/^## Design Tokens$/) exit
            print
        }
    ' "$snapshot_file")

    # Extract frame names from Component Hierarchy section
    local frame_names
    frame_names=$(awk '
        /^### / { gsub(/^### /, ""); gsub(/ \(.*/, ""); print }
    ' "$snapshot_file")

    # Match frame names against scope text (case-insensitive substring)
    local scope_lower
    scope_lower=$(echo "$scope_text" | tr '[:upper:]' '[:lower:]')

    while IFS= read -r frame_name; do
        [[ -z "$frame_name" ]] && continue
        local frame_lower
        frame_lower=$(echo "$frame_name" | tr '[:upper:]' '[:lower:]')
        if echo "$scope_lower" | grep -qi "$frame_lower"; then
            # Extract this frame's hierarchy block
            local block
            block=$(awk -v fname="$frame_name" '
                $0 ~ "^### " fname {found=1}
                found {print}
                found && /^### / && !($0 ~ "^### " fname) {exit}
            ' "$snapshot_file")
            if [[ -n "$block" ]]; then
                matched_frames+="$block"$'\n'
            fi
        fi
    done <<< "$frame_names"

    # Build output
    output="## Design Context"$'\n'$'\n'
    output+="Use these exact design values when implementing UI. Do NOT use shadcn defaults if they differ."$'\n'$'\n'

    if [[ -n "$tokens_section" ]]; then
        output+="$tokens_section"$'\n'
    fi

    if [[ -n "$matched_frames" ]]; then
        output+=$'\n'"## Relevant Component Hierarchies"$'\n'$'\n'
        output+="$matched_frames"
    else
        output+=$'\n'"_No specific frame matches found in scope — refer to design-snapshot.md for full component hierarchy._"$'\n'
    fi

    # Enforce max lines limit
    local line_count
    line_count=$(echo "$output" | wc -l)
    if [[ $line_count -gt $max_lines ]]; then
        echo "$output" | head -n "$max_lines"
        echo ""
        echo "...truncated — read design-snapshot.md for full hierarchy"
    else
        echo "$output"
    fi
}

# ─── Design System Dispatch ──────────────────────────────────────────

# Extract design context from structured design-system.md (generated by set-design-sync).
# Always includes Design Tokens section. Matches Page Layouts subsections against scope.
# Args: $1 = scope text, $2 = design-system.md path, $3 = max lines
_dispatch_from_design_system() {
    local scope_text="$1"
    local ds_file="$2"
    local max_lines="${3:-200}"

    local output=""

    # Always include Design Tokens section
    local tokens
    tokens=$(awk '
        /^## Design Tokens$/,/^## [^D]/ {
            if (/^## / && !/^## Design Tokens$/) exit
            print
        }
    ' "$ds_file")

    output="## Design Context (from design-system.md)"$'\n'$'\n'
    output+="Use these EXACT values. Do NOT fall back to shadcn/Tailwind defaults."$'\n'$'\n'

    if [[ -n "$tokens" ]]; then
        output+="$tokens"$'\n'
    fi

    # Match Page Layouts subsections against scope
    local scope_lower
    scope_lower=$(echo "$scope_text" | tr '[:upper:]' '[:lower:]')

    local page_names
    page_names=$(awk '/^## Page Layouts$/,/^## [^P]/ { if (/^### /) { gsub(/^### /, ""); print } }' "$ds_file")

    local matched=""
    while IFS= read -r page_name; do
        [[ -z "$page_name" ]] && continue
        local page_lower
        page_lower=$(echo "$page_name" | tr '[:upper:]' '[:lower:]')
        # Match bidirectionally: scope contains page name OR page name contains scope word
        local _matched=false
        if echo "$scope_lower" | grep -qi "$page_lower"; then
            _matched=true
        elif echo "$page_lower" | grep -qiE "$(echo "$scope_lower" | tr ' ' '|')"; then
            _matched=true
        fi
        if [[ "$_matched" == "true" ]]; then
            local block
            block=$(awk -v pname="$page_name" '
                /^## Page Layouts$/,/^## [^P]/ {
                    if ($0 ~ "^### " pname) { found=1 }
                    if (found && /^### / && !($0 ~ "^### " pname)) { exit }
                    if (found) { print }
                }
            ' "$ds_file")
            if [[ -n "$block" ]]; then
                matched+="$block"$'\n'
            fi
        fi
    done <<< "$page_names"

    if [[ -n "$matched" ]]; then
        output+=$'\n'"## Matched Page Layouts"$'\n'$'\n'
        output+="$matched"
    fi

    # Components section (always include — it's short)
    local components
    components=$(awk '
        /^## Components$/,/^## [^C]/ {
            if (/^## / && !/^## Components$/) exit
            print
        }
    ' "$ds_file")
    if [[ -n "$components" ]]; then
        output+=$'\n'"$components"
    fi

    # Truncate
    local line_count
    line_count=$(echo "$output" | wc -l)
    if [[ $line_count -gt $max_lines ]]; then
        echo "$output" | head -n "$max_lines"
        echo ""
        echo "...truncated — read design-system.md for full details"
    else
        echo "$output"
    fi
}

# ─── Source File Dispatch ────────────────────────────────────────────

# Find figma-raw sources directories.
# Args: $1 = search root (defaults to DESIGN_SNAPSHOT_DIR or .)
# Prints the first sources directory found. Returns 1 if not found.
_find_figma_sources_dir() {
    local search_root="${1:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local found
    found=$(find "$search_root" -path "*/figma-raw/*/sources" -type d 2>/dev/null | head -1)
    [[ -n "$found" ]] || return 1
    echo "$found"
}

# Decode a figma-raw source filename to a readable path.
# src__app__components__ProductCard.tsx → src/app/components/ProductCard.tsx
_decode_source_filename() {
    echo "$1" | sed 's/__/\//g'
}

# Check if a decoded path is a UI primitive (shadcn/ui component).
_is_ui_primitive() {
    local decoded="$1"
    [[ "$decoded" == */ui/* ]] && return 0
    return 1
}

# Check if a filename matches shared data file patterns.
_is_data_file() {
    local filename="$1"
    case "$filename" in
        *mockData*|*mock-data*|*mock_data*) return 0 ;;
        *data*) return 0 ;;
        *types*|*models*) return 0 ;;
    esac
    return 1
}

# Extract keywords from scope text for matching.
# Splits on whitespace/punctuation, lowercases, filters short words.
_extract_scope_keywords() {
    local scope="$1"
    echo "$scope" | tr '[:upper:]' '[:lower:]' | \
        tr -cs '[:alnum:]' '\n' | \
        awk 'length >= 3' | \
        grep -vE '^(the|and|for|with|from|that|this|will|are|was|has|have|not|but|all|can|its|use|our|also|into|each|then|when|must|only|been|more|some|such|than|them|very|what|your|create|should|where|which|these|those|after|before|other|first|would)$' | \
        sort -u
}

# Extract and inject relevant Figma source files for agent dispatch.
# Matches source files against change scope keywords, excludes UI primitives,
# always includes shared data files when other files match.
# Args: $1 = scope text, $2 = snapshot dir (optional)
# Prints markdown-formatted source file contents to stdout. Returns 1 if no sources.
design_sources_for_dispatch() {
    local scope_text="$1"
    local snapshot_dir="${2:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local max_lines=300

    local sources_dir
    sources_dir=$(_find_figma_sources_dir "$snapshot_dir") || return 1

    # List all source files, decode names, filter UI primitives
    local -a all_files=()
    local -a decoded_names=()
    local -a file_sizes=()
    local -a is_data=()

    while IFS= read -r filepath; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        # Skip UI primitives
        if _is_ui_primitive "$decoded"; then
            continue
        fi

        all_files+=("$filepath")
        decoded_names+=("$decoded")
        file_sizes+=($(wc -l < "$filepath"))
        if _is_data_file "$filename"; then
            is_data+=(1)
        else
            is_data+=(0)
        fi
    done < <(find "$sources_dir" -type f \( -name "*.tsx" -o -name "*.ts" -o -name "*.css" -o -name "*.jsx" -o -name "*.js" \) 2>/dev/null | sort)

    [[ ${#all_files[@]} -eq 0 ]] && return 1

    # Extract keywords from scope
    local -a keywords=()
    while IFS= read -r kw; do
        [[ -n "$kw" ]] && keywords+=("$kw")
    done < <(_extract_scope_keywords "$scope_text")

    [[ ${#keywords[@]} -eq 0 ]] && return 1

    # Score each file by keyword matches against decoded path segments
    local -a scores=()
    local any_non_data_match=0

    for i in "${!all_files[@]}"; do
        local score=0
        local path_lower
        path_lower=$(echo "${decoded_names[$i]}" | tr '[:upper:]' '[:lower:]')
        # Split path into segments for matching
        local segments
        segments=$(echo "$path_lower" | tr '/' '\n' | sed 's/\.[^.]*$//')

        for kw in "${keywords[@]}"; do
            if echo "$segments" | grep -qi "$kw"; then
                ((score++)) || true
            fi
        done

        scores+=("$score")
        if [[ $score -gt 0 && ${is_data[$i]} -eq 0 ]]; then
            any_non_data_match=1
        fi
    done

    # No non-data files matched — nothing to return
    [[ $any_non_data_match -eq 0 ]] && return 1

    # Build ranked list: matched non-data files + data files (always included)
    # Sort by score desc, then file size asc
    local -a ranked_indices=()

    # First: scored non-data files (score > 0)
    local scored_list=""
    for i in "${!all_files[@]}"; do
        if [[ ${scores[$i]} -gt 0 && ${is_data[$i]} -eq 0 ]]; then
            scored_list+="$i ${scores[$i]} ${file_sizes[$i]}"$'\n'
        fi
    done
    if [[ -n "$scored_list" ]]; then
        while IFS=' ' read -r idx _score _size; do
            [[ -n "$idx" ]] && ranked_indices+=("$idx")
        done < <(echo "$scored_list" | sort -t' ' -k2,2rn -k3,3n)
    fi

    # Then: data files (always included when any non-data matched)
    for i in "${!all_files[@]}"; do
        if [[ ${is_data[$i]} -eq 1 ]]; then
            # Avoid duplicates if data file was also keyword-matched
            local already=0
            for ri in "${ranked_indices[@]}"; do
                [[ "$ri" == "$i" ]] && { already=1; break; }
            done
            [[ $already -eq 0 ]] && ranked_indices+=("$i")
        fi
    done

    [[ ${#ranked_indices[@]} -eq 0 ]] && return 1

    # Emit files within budget
    local output=""
    local lines_used=0
    local -a overflow_names=()

    for idx in "${ranked_indices[@]}"; do
        local fsize=${file_sizes[$idx]}
        local decoded="${decoded_names[$idx]}"

        # Header + code fence = 4 extra lines (header, ```, content, ```)
        local needed=$((fsize + 4))

        if [[ $((lines_used + needed)) -le $max_lines ]]; then
            local ext="${decoded##*.}"
            output+="## Figma Source: $decoded"$'\n'$'\n'
            output+='```'"$ext"$'\n'
            output+=$(cat "${all_files[$idx]}")$'\n'
            output+='```'$'\n'$'\n'
            lines_used=$((lines_used + needed))
        else
            overflow_names+=("$decoded")
        fi
    done

    if [[ ${#overflow_names[@]} -gt 0 ]]; then
        output+="Also relevant (read directly from \`docs/figma-raw/*/sources/\`):"$'\n'
        for name in "${overflow_names[@]}"; do
            output+="- $name"$'\n'
        done
        output+=$'\n'
    fi

    [[ -z "$output" ]] && return 1
    echo "$output"
}

# ─── Data Model Extraction ───────────────────────────────────────────

# Extract TypeScript interfaces and seed data names from Figma source files.
# Finds data/model/types files in figma-raw sources, parses interface blocks
# and array literal entity names for planner context.
# Args: $1 = snapshot dir (optional)
# Prints "## Design Data Model" markdown section. Returns 1 if no data files found.
design_data_model_section() {
    local snapshot_dir="${1:-${DESIGN_SNAPSHOT_DIR:-.}}"

    local sources_dir
    sources_dir=$(_find_figma_sources_dir "$snapshot_dir") || return 1

    # Find data/model/types files (excluding UI primitives)
    local -a data_files=()
    while IFS= read -r filepath; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        _is_ui_primitive "$decoded" && continue
        _is_data_file "$filename" && data_files+=("$filepath")
    done < <(find "$sources_dir" -type f \( -name "*.tsx" -o -name "*.ts" -o -name "*.js" -o -name "*.jsx" \) 2>/dev/null | sort)

    [[ ${#data_files[@]} -eq 0 ]] && return 1

    local output=""
    local has_content=0

    # Extract interfaces and type definitions
    local interfaces=""
    for filepath in "${data_files[@]}"; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        # Extract TypeScript interface/type blocks
        local ifaces
        ifaces=$(awk '
            /^export (interface|type) / { found=1 }
            found { print }
            found && /^\}/ { found=0; print "" }
        ' "$filepath" 2>/dev/null)

        if [[ -n "$ifaces" ]]; then
            interfaces+="From \`$decoded\`:"$'\n'
            interfaces+='```typescript'$'\n'
            interfaces+="$ifaces"$'\n'
            interfaces+='```'$'\n'$'\n'
            has_content=1
        fi
    done

    # Extract seed data entity names from array literals
    local seed_names=""
    for filepath in "${data_files[@]}"; do
        # Look for patterns like: { name: "Wireless Earbuds Pro" }
        local names
        names=$(grep -oP '(?<=name:\s")[^"]+' "$filepath" 2>/dev/null || \
                grep -oP "(?<=name:\s')[^']+" "$filepath" 2>/dev/null || true)

        if [[ -n "$names" ]]; then
            seed_names+="$names"$'\n'
            has_content=1
        fi
    done

    [[ $has_content -eq 0 ]] && return 1

    output="## Design Data Model"$'\n'$'\n'
    output+="The following data model definitions were extracted from Figma source files."$'\n'
    output+="Embed these field names and entity names in change scope descriptions —"$'\n'
    output+="implementing agents will NOT see this section, only your scope text."$'\n'$'\n'

    if [[ -n "$interfaces" ]]; then
        output+="### Interfaces & Types"$'\n'$'\n'
        output+="$interfaces"
    fi

    if [[ -n "$seed_names" ]]; then
        output+="### Seed Data Names"$'\n'$'\n'
        output+="Seed data MUST use these exact entity names from the design:"$'\n'
        while IFS= read -r name; do
            [[ -n "$name" ]] && output+="- $name"$'\n'
        done <<< "$seed_names"
        output+=$'\n'
    fi

    echo "$output"
}

# ─── Review Context ──────────────────────────────────────────────────

# Extract concise design token summary for code review prompts.
# Returns key UI tokens (colors, radius, typography) — max ~20 tokens.
# Args: $1 = snapshot dir (optional)
# Prints token summary to stdout. Returns 1 if no snapshot available.
build_design_review_section() {
    local snapshot_dir="${1:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local snapshot_file
    snapshot_file=$(_find_design_snapshot "$snapshot_dir") || return 1

    local tokens_section
    tokens_section=$(awk '
        /^## Design Tokens$/,/^## / {
            if (/^## / && !/^## Design Tokens$/) exit
            print
        }
    ' "$snapshot_file")

    [[ -z "$tokens_section" ]] && return 1

    # Filter to UI-critical tokens only (colors, typography, spacing, radius)
    local filtered
    filtered=$(echo "$tokens_section" | grep -E '^(Colors:|Typography:|Spacing:|Shadows:|- (background|foreground|primary|destructive|accent|border|muted|ring|radius|input|font|h[1-4]|label|button|base-font):)' || true)

    cat <<EOF
## Design Compliance Check

Compare Tailwind classes in the diff against these design token values.
Report mismatches as [WARNING] (not [CRITICAL]).

$tokens_section

Key checks:
- Interactive elements (buttons, links): verify correct color class matches design primary/accent
- Headings: verify text size classes match typography scale (h1=text-2xl, h2=text-xl, etc.)
- Border radius: verify rounded classes match radius tokens
- Shadows: verify shadow classes match design shadow definitions
- Do NOT flag as issues: responsive variants, hover states, or tokens not in the list above
EOF

    # Component Structure subsection — extract from Figma source files
    local sources_dir
    sources_dir=$(_find_figma_sources_dir "$snapshot_dir") || return 0

    local structure_items=""
    local item_count=0

    # 5.1: Icon extraction — lucide-react imports
    while IFS= read -r filepath; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        _is_ui_primitive "$decoded" && continue

        # Extract icon imports from lucide-react
        local icons
        icons=$(grep -oP 'import\s*\{[^}]+\}\s*from\s*['\''"]lucide-react['\''"]' "$filepath" 2>/dev/null | \
            sed 's/import\s*{//; s/}\s*from.*//' | tr ',' '\n' | sed 's/^\s*//;s/\s*$//' | grep -v '^$' || true)

        if [[ -n "$icons" ]]; then
            while IFS= read -r icon; do
                [[ -n "$icon" && $item_count -lt 20 ]] || continue
                structure_items+="- [WARNING] Icon: \`$icon\` used in \`$decoded\`"$'\n'
                ((item_count++)) || true
            done <<< "$icons"
        fi
    done < <(find "$sources_dir" -type f \( -name "*.tsx" -o -name "*.ts" -o -name "*.jsx" -o -name "*.js" \) 2>/dev/null | sort)

    # 5.2: Image/thumbnail patterns — w-N h-N classes on images
    while IFS= read -r filepath; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        _is_ui_primitive "$decoded" && continue

        local img_patterns
        img_patterns=$(grep -oP 'w-\d+\s+h-\d+' "$filepath" 2>/dev/null | sort -u || true)

        if [[ -n "$img_patterns" ]]; then
            while IFS= read -r pat; do
                [[ -n "$pat" && $item_count -lt 20 ]] || continue
                structure_items+="- [WARNING] Image pattern: \`$pat\` in \`$decoded\`"$'\n'
                ((item_count++)) || true
            done <<< "$img_patterns"
        fi
    done < <(find "$sources_dir" -type f \( -name "*.tsx" -o -name "*.jsx" \) 2>/dev/null | sort)

    # 5.3: Layout patterns — grid/flex containers with specific classes
    while IFS= read -r filepath; do
        local filename
        filename=$(basename "$filepath")
        local decoded
        decoded=$(_decode_source_filename "$filename")

        _is_ui_primitive "$decoded" && continue

        local layouts
        layouts=$(grep -oP '(grid\s+grid-cols-\d+|flex\s+(?:flex-col|items-center|justify-between|gap-\d+))' "$filepath" 2>/dev/null | sort -u | head -3 || true)

        if [[ -n "$layouts" ]]; then
            while IFS= read -r lay; do
                [[ -n "$lay" && $item_count -lt 20 ]] || continue
                structure_items+="- [WARNING] Layout: \`$lay\` in \`$decoded\`"$'\n'
                ((item_count++)) || true
            done <<< "$layouts"
        fi
    done < <(find "$sources_dir" -type f \( -name "*.tsx" -o -name "*.jsx" \) 2>/dev/null | sort)

    # 5.4: Append Component Structure subsection
    if [[ -n "$structure_items" ]]; then
        cat <<EOF

### Component Structure (from Figma sources)

Verify the diff matches these design patterns. All mismatches are [WARNING] severity.

$structure_items
EOF
    fi
}

# ─── Convenience ──────────────────────────────────────────────────────

# One-call setup: detect, load config, export DESIGN_MCP_CONFIG.
# Returns 0 if design MCP is available and config exported, 1 otherwise.
# After this call, DESIGN_MCP_CONFIG is set (or empty).
setup_design_bridge() {
    local server_name
    server_name=$(detect_design_mcp) || return 1

    local config_file
    config_file=$(get_design_mcp_config "$server_name") || return 1

    load_design_file_ref || true  # non-fatal, file ref is optional

    export DESIGN_MCP_CONFIG="$config_file"
    export DESIGN_MCP_NAME="$server_name"
    return 0
}
