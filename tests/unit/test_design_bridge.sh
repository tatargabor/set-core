#!/usr/bin/env bash
# Unit tests for lib/design/bridge.sh
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/helpers.sh"

# Source the module under test
source "$SCRIPT_DIR/../../lib/design/bridge.sh"

# ─── Setup / Teardown ────────────────────────────────────────────────

_TMPDIR=""
setup() {
    _TMPDIR=$(mktemp -d)
    export PROJECT_ROOT="$_TMPDIR"
    unset DESIGN_FILE_REF DESIGN_MCP_CONFIG DESIGN_MCP_NAME
}

teardown() {
    rm -rf "$_TMPDIR"
    unset PROJECT_ROOT DESIGN_FILE_REF DESIGN_MCP_CONFIG DESIGN_MCP_NAME
}

# ─── detect_design_mcp ───────────────────────────────────────────────

test_detect_figma_mcp() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{
  "mcpServers": {
    "set-core": {"command": "uv", "args": ["run"]},
    "figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}
  }
}
JSON

    local result
    result=$(detect_design_mcp)
    assert_equals "figma" "$result" "should detect figma"
    teardown
}

test_detect_penpot_mcp() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"penpot": {"command": "node", "args": ["server.js"]}}}
JSON

    local result
    result=$(detect_design_mcp)
    assert_equals "penpot" "$result" "should detect penpot"
    teardown
}

test_detect_no_design_mcp() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"set-core": {"command": "uv"}}}
JSON

    local rc=0
    detect_design_mcp > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 when no design MCP"
    teardown
}

test_detect_missing_settings() {
    setup
    # No .claude/settings.json at all
    local rc=0
    detect_design_mcp > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 when settings missing"
    teardown
}

test_detect_multiple_design_mcps() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"url": "x"}, "penpot": {"command": "y"}}}
JSON

    local result
    result=$(detect_design_mcp)
    # Should return the first match (alphabetical from jq keys)
    assert_equals "figma" "$result" "should return first match"
    teardown
}

# ─── get_design_mcp_config ───────────────────────────────────────────

test_config_export() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{
  "mcpServers": {
    "figma": {"type": "http", "url": "https://mcp.figma.com/mcp"},
    "set-core": {"command": "uv"}
  }
}
JSON

    local config_file
    config_file=$(get_design_mcp_config "figma")

    # Should contain only the figma server
    local server_count
    server_count=$(jq '.mcpServers | keys | length' "$config_file")
    assert_equals "1" "$server_count" "should export only figma config"

    local url
    url=$(jq -r '.mcpServers.figma.url' "$config_file")
    assert_equals "https://mcp.figma.com/mcp" "$url" "should preserve URL"

    rm -f "$config_file"
    teardown
}

# ─── load_design_file_ref ────────────────────────────────────────────

test_load_design_file_ref() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
max_parallel: 3
design_file: "https://www.figma.com/file/ABC123/MyDesign"
merge_policy: checkpoint
YAML

    load_design_file_ref
    assert_equals "https://www.figma.com/file/ABC123/MyDesign" "$DESIGN_FILE_REF" "should export ref"
    teardown
}

test_load_design_file_ref_missing() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
max_parallel: 3
YAML

    local rc=0
    load_design_file_ref || rc=$?
    assert_equals "1" "$rc" "should return 1 when no design_file"
    teardown
}

# ─── design_prompt_section ───────────────────────────────────────────

test_prompt_section_with_ref() {
    setup
    export DESIGN_FILE_REF="https://figma.com/file/XYZ"

    local output
    output=$(design_prompt_section "figma")

    assert_contains "$output" "figma" "should mention tool name"
    assert_contains "$output" "Design file reference: https://figma.com/file/XYZ" "should include ref"
    assert_contains "$output" "design_gap" "should mention ambiguity type"
    teardown
}

test_prompt_section_without_ref() {
    setup
    unset DESIGN_FILE_REF

    local output
    output=$(design_prompt_section "penpot")

    assert_contains "$output" "penpot" "should mention tool name"
    assert_not_contains "$output" "Design file reference:" "should not include ref line"
    teardown
}

# ─── setup_design_bridge ─────────────────────────────────────────────

test_setup_design_bridge_full() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
design_file: "https://figma.com/file/TEST"
YAML

    setup_design_bridge
    assert_equals "figma" "$DESIGN_MCP_NAME" "should set MCP name"
    assert_file_exists "$DESIGN_MCP_CONFIG" "should create config file"
    assert_equals "https://figma.com/file/TEST" "$DESIGN_FILE_REF" "should load file ref"

    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_setup_design_bridge_no_mcp() {
    setup
    # No settings.json
    local rc=0
    setup_design_bridge || rc=$?
    assert_equals "1" "$rc" "should return 1 without design MCP"
    assert_equals "" "${DESIGN_MCP_CONFIG:-}" "should not set config"
    teardown
}

# ─── Run ──────────────────────────────────────────────────────────────


# ─── check_design_mcp_health ────────────────────────────────────

test_health_check_success() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    setup_design_bridge

    # Mock run_claude to return healthy response
    run_claude() { echo "MCP_HEALTHY"; return 0; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    check_design_mcp_health || rc=$?
    assert_equals "0" "$rc" "should return 0 when MCP is healthy"

    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_health_check_auth_failure() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    setup_design_bridge

    # Mock run_claude to return auth failure
    run_claude() { echo "MCP_AUTH_FAILED: needs authentication"; return 0; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    check_design_mcp_health || rc=$?
    assert_equals "1" "$rc" "should return 1 when MCP auth fails"

    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_health_check_timeout() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    setup_design_bridge

    # Mock run_claude to simulate timeout (non-zero exit)
    run_claude() { return 124; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    check_design_mcp_health || rc=$?
    assert_equals "1" "$rc" "should return 1 on timeout"

    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_health_check_no_config() {
    setup
    unset DESIGN_MCP_CONFIG DESIGN_MCP_NAME
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    check_design_mcp_health || rc=$?
    assert_equals "1" "$rc" "should return 1 without config"

    teardown
}

# ─── fetch_design_snapshot ──────────────────────────────────────

test_snapshot_success() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
design_file: "https://figma.com/file/TEST"
YAML
    setup_design_bridge

    local _snap_dir
    _snap_dir=$(mktemp -d)
    export DESIGN_SNAPSHOT_DIR="$_snap_dir"

    # Mock run_claude to return sample snapshot
    run_claude() {
        cat <<'MD'
# Design Snapshot

## Pages & Frames
| Page | Frame | Dimensions | Description |
|------|-------|------------|-------------|
| Desktop | Homepage | 1280x4200 | Main landing |
| Mobile | Homepage | 375x5100 | Mobile landing |

## Design Tokens
### Colors
- primary: #78350F
- secondary: #D97706

### Typography
- Headings: Playfair Display
- Body: Inter

### Spacing
- base: 4px

### Shadows
- card: 0 2px 8px rgba(0,0,0,0.1)

## Component Hierarchy
### Homepage
- Header (sticky)
  - Logo
  - NavBar

## Layout Breakpoints
- Desktop: 1280px
- Mobile: 375px

## Visual Descriptions
### Homepage
Full-width hero with amber gradient
MD
        return 0
    }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    fetch_design_snapshot || rc=$?
    assert_equals "0" "$rc" "should return 0 on success"
    assert_file_exists "$_snap_dir/design-snapshot.md" "should create snapshot file"
    local content
    content=$(cat "$_snap_dir/design-snapshot.md")
    assert_contains "$content" "Design Snapshot" "should contain snapshot header"
    assert_contains "$content" "#78350F" "should contain color token"

    rm -rf "$_snap_dir"
    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_snapshot_cache_hit() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
design_file: "https://figma.com/file/TEST"
YAML
    setup_design_bridge

    local _snap_dir
    _snap_dir=$(mktemp -d)
    export DESIGN_SNAPSHOT_DIR="$_snap_dir"

    # Pre-create cached snapshot
    echo "# Cached Snapshot" > "$_snap_dir/design-snapshot.md"

    # Mock run_claude — should NOT be called
    run_claude() { echo "ERROR: run_claude should not be called"; return 1; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    fetch_design_snapshot || rc=$?
    assert_equals "0" "$rc" "should return 0 using cache"

    local content
    content=$(cat "$_snap_dir/design-snapshot.md")
    assert_contains "$content" "Cached Snapshot" "should preserve cached content"

    rm -rf "$_snap_dir"
    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_snapshot_force_refetch() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
design_file: "https://figma.com/file/TEST"
YAML
    setup_design_bridge

    local _snap_dir
    _snap_dir=$(mktemp -d)
    export DESIGN_SNAPSHOT_DIR="$_snap_dir"

    # Pre-create cached snapshot
    echo "# Old Cached" > "$_snap_dir/design-snapshot.md"

    # Mock run_claude to return new snapshot
    run_claude() { echo "# Fresh Snapshot"; return 0; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    fetch_design_snapshot "force" || rc=$?
    assert_equals "0" "$rc" "should return 0 on force refetch"

    local content
    content=$(cat "$_snap_dir/design-snapshot.md")
    assert_contains "$content" "Fresh Snapshot" "should overwrite with fresh content"
    assert_not_contains "$content" "Old Cached" "should not contain old cache"

    rm -rf "$_snap_dir"
    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_snapshot_timeout_failure() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    cat > "$_TMPDIR/.claude/orchestration.yaml" <<'YAML'
design_file: "https://figma.com/file/TEST"
YAML
    setup_design_bridge

    local _snap_dir
    _snap_dir=$(mktemp -d)
    export DESIGN_SNAPSHOT_DIR="$_snap_dir"

    # Mock run_claude to simulate timeout
    run_claude() { return 124; }
    export -f run_claude
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    fetch_design_snapshot || rc=$?
    assert_equals "1" "$rc" "should return 1 on timeout"

    # Snapshot file should NOT be created
    if [[ -f "$_snap_dir/design-snapshot.md" ]]; then
        echo "    FAIL: snapshot file should not exist after failure"
        rm -rf "$_snap_dir"
        rm -f "$DESIGN_MCP_CONFIG"
        teardown
        return 1
    fi

    rm -rf "$_snap_dir"
    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

test_snapshot_no_design_ref() {
    setup
    mkdir -p "$_TMPDIR/.claude"
    cat > "$_TMPDIR/.claude/settings.json" <<'JSON'
{"mcpServers": {"figma": {"type": "http", "url": "https://mcp.figma.com/mcp"}}}
JSON
    # No orchestration.yaml → no DESIGN_FILE_REF
    setup_design_bridge

    local _snap_dir
    _snap_dir=$(mktemp -d)
    export DESIGN_SNAPSHOT_DIR="$_snap_dir"
    log_info() { :; }
    log_warn() { :; }

    local rc=0
    fetch_design_snapshot || rc=$?
    assert_equals "1" "$rc" "should return 1 without design ref"

    rm -rf "$_snap_dir"
    rm -f "$DESIGN_MCP_CONFIG"
    teardown
}

# ─── design_prompt_section (snapshot-aware) ─────────────────────

test_prompt_section_with_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)

    # Create a snapshot file
    cat > "$_snap_dir/design-snapshot.md" <<'MD'
# Design Snapshot
## Pages & Frames
| Page | Frame | Dimensions |
|------|-------|------------|
| Desktop | Homepage | 1280x4200 |
MD

    local output
    output=$(design_prompt_section "figma" "$_snap_dir")

    assert_contains "$output" "Design Context (Snapshot)" "should have snapshot header"
    assert_contains "$output" "Homepage" "should contain snapshot content"
    assert_contains "$output" "1280x4200" "should contain dimensions"
    assert_contains "$output" "also available for live" "should mention live MCP"
    assert_not_contains "$output" "You can query it for" "should NOT contain generic instructions"

    rm -rf "$_snap_dir"
    teardown
}

test_prompt_section_without_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    # No snapshot file
    export DESIGN_FILE_REF="https://figma.com/file/XYZ"

    local output
    output=$(design_prompt_section "figma" "$_snap_dir")

    assert_contains "$output" "You can query it for" "should contain generic instructions"
    assert_contains "$output" "Design file reference: https://figma.com/file/XYZ" "should include ref"
    assert_not_contains "$output" "Design Context (Snapshot)" "should NOT have snapshot header"

    rm -rf "$_snap_dir"
    teardown
}

test_prompt_section_empty_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    # Create empty snapshot file
    touch "$_snap_dir/design-snapshot.md"

    local output
    output=$(design_prompt_section "figma" "$_snap_dir")

    assert_contains "$output" "You can query it for" "should fallback to generic for empty snapshot"
    assert_not_contains "$output" "Design Context (Snapshot)" "should NOT use snapshot for empty file"

    rm -rf "$_snap_dir"
    teardown
}

# ─── design_context_for_dispatch ────────────────────────────────

_create_test_snapshot() {
    local dir="$1"
    cat > "$dir/design-snapshot.md" <<'MD'
# Design Snapshot

## Design Tokens
### Colors
- primary: #2563eb (blue-600)
- background: #ffffff
- foreground: #030213
- accent: #f59e0b

### Typography
- h1: text-3xl font-bold
- h2: text-xl font-semibold
- body: text-base

### Spacing
- base: 4px
- section-gap: 2rem

### Shadows
- card: 0 2px 8px rgba(0,0,0,0.1)

## Component Hierarchy

### Homepage (Desktop)
- Header (sticky)
  - Logo
  - NavBar
    - NavLink × 4
  - CartIcon (badge count)
- HeroSection
  - HeroTitle (h1)
  - HeroSubtitle
  - CTAButton (primary)

### Product Grid (Desktop)
- SectionHeading (h2)
- Grid (3-col)
  - ProductCard × n
    - ProductImage
    - ProductTitle
    - ProductPrice
    - AddToCartButton

### Cart Sidebar
- CartHeader
- CartItemList
  - CartItem × n
    - ItemName
    - QuantitySelector
    - ItemTotal
- CartTotal
- CheckoutButton

## Layout Breakpoints
- Desktop: 1280px
- Mobile: 375px
MD
}

test_dispatch_context_with_matching_frame() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    _create_test_snapshot "$_snap_dir"

    local output
    output=$(design_context_for_dispatch "Build the Homepage hero section with CTA" "$_snap_dir")

    assert_contains "$output" "## Design Context" "should have design context header"
    assert_contains "$output" "## Design Tokens" "should include tokens"
    assert_contains "$output" "#2563eb" "should include primary color"
    assert_contains "$output" "### Homepage" "should include matched Homepage frame"
    assert_contains "$output" "HeroSection" "should include Homepage hierarchy"
    assert_contains "$output" "CTAButton" "should include CTA button from hierarchy"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_multiple_frame_match() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    _create_test_snapshot "$_snap_dir"

    local output
    output=$(design_context_for_dispatch "Homepage layout and Cart sidebar" "$_snap_dir")

    assert_contains "$output" "### Homepage" "should match Homepage frame"
    assert_contains "$output" "### Cart Sidebar" "should match Cart frame"
    assert_contains "$output" "## Relevant Component Hierarchies" "should have hierarchy header"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_no_frame_match() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    _create_test_snapshot "$_snap_dir"

    local output
    output=$(design_context_for_dispatch "Add unit tests for API" "$_snap_dir")

    assert_contains "$output" "## Design Tokens" "should still include tokens"
    assert_contains "$output" "#2563eb" "should still have primary color"
    assert_contains "$output" "No specific frame matches" "should show no-match fallback"
    assert_not_contains "$output" "### Homepage" "should not include any frame"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_case_insensitive() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    _create_test_snapshot "$_snap_dir"

    local output
    output=$(design_context_for_dispatch "PRODUCT GRID display" "$_snap_dir")

    assert_contains "$output" "### Product Grid" "should match case-insensitively"
    assert_contains "$output" "ProductCard" "should include product grid hierarchy"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_empty_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    touch "$_snap_dir/design-snapshot.md"

    local rc=0
    design_context_for_dispatch "anything" "$_snap_dir" > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 for empty snapshot"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_missing_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    # No snapshot file

    local rc=0
    design_context_for_dispatch "anything" "$_snap_dir" > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 for missing snapshot"

    rm -rf "$_snap_dir"
    teardown
}

test_dispatch_context_line_limit() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)

    # Create a snapshot with huge component hierarchy (200+ lines)
    {
        echo "## Design Tokens"
        echo "### Colors"
        echo "- primary: #2563eb"
        echo ""
        echo "## Component Hierarchy"
        echo "### BigPage"
        for i in $(seq 1 200); do
            echo "- Component$i"
            echo "  - SubComponent${i}A"
        done
    } > "$_snap_dir/design-snapshot.md"

    local output
    output=$(design_context_for_dispatch "BigPage implementation" "$_snap_dir")
    local line_count
    line_count=$(echo "$output" | wc -l)

    # Should be truncated — max 150 lines + truncation notice
    if [[ $line_count -gt 155 ]]; then
        echo "    FAIL: output exceeds line limit ($line_count lines)"
        rm -rf "$_snap_dir"
        teardown
        return 1
    fi
    assert_contains "$output" "truncated" "should show truncation notice"

    rm -rf "$_snap_dir"
    teardown
}

# ─── build_design_review_section ────────────────────────────────

test_review_section_extracts_tokens() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    _create_test_snapshot "$_snap_dir"

    local output
    output=$(build_design_review_section "$_snap_dir")

    assert_contains "$output" "Design Compliance Check" "should have compliance header"
    assert_contains "$output" "#2563eb" "should include primary color"
    assert_contains "$output" "text-3xl" "should include typography"
    assert_contains "$output" "card:" "should include shadows"
    assert_contains "$output" "WARNING" "should mention WARNING severity"
    assert_not_contains "$output" "CRITICAL" "should not mention CRITICAL for design"

    rm -rf "$_snap_dir"
    teardown
}

test_review_section_empty_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)
    touch "$_snap_dir/design-snapshot.md"

    local rc=0
    build_design_review_section "$_snap_dir" > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 for empty snapshot"

    rm -rf "$_snap_dir"
    teardown
}

test_review_section_missing_snapshot() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)

    local rc=0
    build_design_review_section "$_snap_dir" > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 for missing snapshot"

    rm -rf "$_snap_dir"
    teardown
}

test_review_section_no_tokens() {
    setup
    local _snap_dir
    _snap_dir=$(mktemp -d)

    # Snapshot with no Design Tokens section
    cat > "$_snap_dir/design-snapshot.md" <<'MD'
# Design Snapshot
## Component Hierarchy
### Homepage
- Header
- Footer
MD

    local rc=0
    build_design_review_section "$_snap_dir" > /dev/null 2>&1 || rc=$?
    assert_equals "1" "$rc" "should return 1 when no tokens section"

    rm -rf "$_snap_dir"
    teardown
}

run_tests
