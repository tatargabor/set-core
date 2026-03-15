#!/usr/bin/env bash
# lib/design/bridge.sh — Design tool abstraction layer
# Detects registered design MCP servers, exports config for run_claude --mcp-config,
# and generates design-aware prompt sections for planner/verifier/dispatcher.
#
# Usage: source this file after config.sh. All functions are non-fatal.
# If no design MCP is detected, functions return 1 silently.

# ─── Log Fallbacks ────────────────────────────────────────────────────
# When sourced standalone (e.g. from Python subprocess), wt-common.sh
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
    local config="$project_root/wt/orchestration/config.yaml"
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

    # Copy to project root so worktree agents can find it via design-bridge rule
    local project_root="${PROJECT_ROOT:-.}"
    local root_snapshot="$project_root/design-snapshot.md"
    if [[ "$snapshot_file" != "$root_snapshot" ]]; then
        cp "$snapshot_file" "$root_snapshot"
        info "Design snapshot copied to project root"
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
# Returns Design Tokens + relevant Component Hierarchy sections (max 150 lines).
# Args: $1 = scope text, $2 = snapshot dir (optional, defaults to DESIGN_SNAPSHOT_DIR or .)
# Prints filtered markdown to stdout. Returns 1 if no snapshot available.
design_context_for_dispatch() {
    local scope_text="$1"
    local snapshot_dir="${2:-${DESIGN_SNAPSHOT_DIR:-.}}"
    local snapshot_file
    snapshot_file=$(_find_design_snapshot "$snapshot_dir") || return 1
    local max_lines=150

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
