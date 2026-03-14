#!/usr/bin/env bash
# CraftBrew E2E Test Runner
# Clones the CraftBrew spec repo, initializes it as a wt-project, and prepares
# it for orchestration. The spec is a multi-file business specification (docs/)
# with 17+ files. The sentinel auto-triggers digest before planning, then agents
# build from the structured digest.
#
# Usage:
#   ./tests/e2e/run-complex.sh              # Auto-increment: /tmp/craftbrew-run1, run2, ...
#   ./tests/e2e/run-complex.sh /path/to/dir # Clone to specified dir
#
# The spec source repo: https://github.com/tatargabor/craftbrew

set -euo pipefail

CRAFTBREW_REPO="https://github.com/tatargabor/craftbrew.git"
CRAFTBREW_BRANCH="main"
BASE_DIR="${TMPDIR:-/tmp}"

# Auto-increment run number: find highest existing craftbrew-runN, use N+1
next_run_number() {
    local max=0
    for d in "$BASE_DIR"/craftbrew-run*; do
        [[ -d "$d" ]] || continue
        local n="${d##*craftbrew-run}"
        n="${n%%-*}"  # strip worktree suffixes like -wt-catalog-list
        [[ "$n" =~ ^[0-9]+$ ]] && (( n > max )) && max=$n
    done
    echo $(( max + 1 ))
}

if [[ -n "${1:-}" ]]; then
    TEST_DIR="$1"
    PROJECT_NAME="$(basename "$TEST_DIR")"
else
    RUN_NUM=$(next_run_number)
    TEST_DIR="$BASE_DIR/craftbrew-run${RUN_NUM}"
    PROJECT_NAME="craftbrew-run${RUN_NUM}"
fi

# ── Colors ──

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[info]${NC} $*"; }
success() { echo -e "${GREEN}[ok]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC} $*"; }
error()   { echo -e "${RED}[error]${NC} $*" >&2; }
step()    { echo -e "\n${BLUE}=== $* ===${NC}"; }

die() { error "$*"; echo "  Test dir: $TEST_DIR"; exit 1; }

# ── Preflight checks ──

preflight() {
    step "Preflight checks"

    command -v wt-project &>/dev/null || die "wt-project not found in PATH"
    command -v node &>/dev/null || die "node not found in PATH"
    command -v pnpm &>/dev/null || die "pnpm not found in PATH"
    command -v git &>/dev/null || die "git not found in PATH"

    if ! wt-project list-types 2>/dev/null | grep -q "web"; then
        die "wt-project-web plugin not installed (wt-project list-types does not show 'web')"
    fi

    success "All prerequisites met"
}

# ── Name conflict handling ──

handle_name_conflict() {
    local existing_path
    existing_path=$(wt-project list 2>/dev/null | grep "$PROJECT_NAME" | sed 's/.*-> //' || true)

    if [[ -n "$existing_path" ]]; then
        local abs_test_dir
        abs_test_dir=$(cd "$TEST_DIR" 2>/dev/null && pwd || echo "$TEST_DIR")

        if [[ "$existing_path" != "$abs_test_dir" ]]; then
            warn "Project '$PROJECT_NAME' already registered at: $existing_path"
            info "Removing old registration..."
            wt-project remove "$PROJECT_NAME" 2>/dev/null || true
        fi
    fi
}

# ── History protection guard ──

check_history_guard() {
    local registered_path
    registered_path=$(wt-project list 2>/dev/null | grep "$PROJECT_NAME" | sed 's/.*-> //' || true)

    if [[ -n "$registered_path" && -d "$registered_path" && ! -d "$registered_path/.git" ]]; then
        error "HISTORY PROTECTION: Project '$PROJECT_NAME' is registered at $registered_path"
        error "but .git directory is MISSING. The git history was likely deleted externally."
        error ""
        error "This guard prevents accidental loss of orchestration work."
        error "If the previous run had orch/* tags, they are now lost."
        error ""
        error "To force a fresh start, first unregister:"
        error "  wt-project remove $PROJECT_NAME"
        error "  rm -rf $registered_path"
        error "  $0 $*"
        exit 1
    fi
}

# ── Existing dir detection ──

check_existing() {
    if [[ -d "$TEST_DIR/.git" ]]; then
        step "Existing test project detected"
        info "Directory: $TEST_DIR"
        echo ""
        info "Git tags:"
        (cd "$TEST_DIR" && git tag 2>/dev/null | sort -V) || true
        echo ""
        info "To continue with sentinel:"
        echo "  cd $TEST_DIR && wt-sentinel --spec docs/"
        echo ""
        info "To reset from a checkpoint:"
        echo "  cd $TEST_DIR"
        echo "  git worktree list  # remove any worktrees"
        echo "  git checkout -b resume-<tag> <tag>"
        echo "  wt-project init --name $PROJECT_NAME --project-type web"
        echo "  rm -f orchestration-state.json orchestration-plan.json"
        echo "  rm -rf wt/orchestration/digest/"
        echo "  wt-sentinel --spec docs/"
        exit 0
    fi
}

# ── Main initialization ──

init_project() {
    step "Clone CraftBrew spec repo"
    git clone --branch "$CRAFTBREW_BRANCH" "$CRAFTBREW_REPO" "$TEST_DIR"
    cd "$TEST_DIR"

    local file_count
    file_count=$(find "$TEST_DIR/docs" -name '*.md' | wc -l)
    success "Cloned CraftBrew repo ($file_count spec files in docs/)"

    step "Tag spec baseline"
    git tag v0-spec
    success "Tagged v0-spec"

    step "Clean stale memory"
    local mem_storage="${SHODH_STORAGE:-${HOME}/.local/share/wt-tools/memory}/${PROJECT_NAME}"
    if [[ -d "$mem_storage" ]]; then
        info "Removing stale memory storage: $mem_storage"
        rm -rf "$mem_storage"
        success "Memory storage cleaned"
    fi

    step "wt-project init"
    handle_name_conflict
    wt-project init --name "$PROJECT_NAME" --project-type web --template nextjs || true

    if [[ ! -d ".claude" ]]; then
        die ".claude/ directory not created by wt-project init"
    fi
    success "wt-project initialized (configs, rules, CLAUDE.md deployed)"

    step "Figma MCP registration"
    # Register the official Figma MCP (HTTP transport, OAuth-based).
    # Supports Design + Make + FigJam files.
    # NOTE: User must authenticate once via /mcp → figma → Authenticate in Claude Code
    # before orchestration can use it non-interactively.
    local settings_file=".claude/settings.json"
    if [[ -f "$settings_file" ]]; then
        local tmp_settings
        tmp_settings=$(mktemp)
        if jq '.mcpServers.figma = {"type": "http", "url": "https://mcp.figma.com/mcp"}' \
            "$settings_file" > "$tmp_settings" 2>/dev/null; then
            mv "$tmp_settings" "$settings_file"
            success "Registered official Figma MCP (https://mcp.figma.com/mcp)"
        else
            rm -f "$tmp_settings"
            warn "Failed to register Figma MCP — continuing without it"
        fi
    fi

    step "Orchestration config"
    mkdir -p wt/orchestration
    # Read design_file from docs/design/design-system.md if it exists
    local design_file_url=""
    local design_system="docs/design/design-system.md"
    if [[ -f "$design_system" ]]; then
        # Extract first figma.com URL (Design or Make)
        design_file_url=$(grep -oP 'https://www\.figma\.com/(design|make)/[^\s)]+' "$design_system" | head -1 || true)
    fi

    cat > wt/orchestration/config.yaml <<YAML
# Orchestration config for CraftBrew E2E
test_command: pnpm test
e2e_command: npx playwright test
e2e_timeout: 180
smoke_command: pnpm build && pnpm test
smoke_blocking: true
max_parallel: 2
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
max_replan_cycles: 3
YAML

    if [[ -n "$design_file_url" ]]; then
        echo "design_file: \"$design_file_url\"" >> wt/orchestration/config.yaml
        success "Design file reference: $design_file_url"
    fi
    success "Created wt/orchestration/config.yaml"

    git add -A
    git commit -m "chore: wt-project init + orchestration config"
    git tag v1-ready
    success "Tagged v1-ready"
}

# ── Completion info ──

show_completion() {
    step "Ready!"
    echo ""
    info "Test project: $TEST_DIR"
    info "Source repo: $CRAFTBREW_REPO"
    info "Git tags: $(cd "$TEST_DIR" && git tag | tr '\n' ' ')"
    info "Spec files: $(find "$TEST_DIR/docs" -name '*.md' | wc -l)"
    echo ""
    info "To start the E2E test (digest pipeline):"
    echo "  cd $TEST_DIR"
    echo "  wt-sentinel --spec docs/"
    echo ""
    info "The sentinel will:"
    echo "  1. Detect directory spec → auto-trigger digest"
    echo "  2. Generate wt/orchestration/digest/ (requirements, domains, conventions)"
    echo "  3. Plan changes from structured digest"
    echo "  4. Dispatch agents with spec-context per worktree"
    echo "  5. Track requirement coverage through execution"
    echo ""
    warn "IMPORTANT: Mid-run wt-tools fixes"
    echo "  Symlinks are NOT enough — .claude/ files must be real copies."
    echo "  After fixing a bug in wt-tools during a run:"
    echo "    1. wt-project init --name $PROJECT_NAME   # re-deploy to main worktree"
    echo "    2. Sync to active agent worktrees:"
    echo "       for wt in \$(git worktree list --porcelain | grep '^worktree ' | awk '{print \$2}'); do"
    echo "         cp -r .claude/commands/ \"\$wt/.claude/commands/\""
    echo "         cp -r .claude/skills/ \"\$wt/.claude/skills/\""
    echo "         cp .claude/CLAUDE.md \"\$wt/.claude/CLAUDE.md\" 2>/dev/null || true"
    echo "       done"
    echo "  Running agents pick up the new files on their next iteration."
    echo ""
    info "To check requirement coverage during/after run:"
    echo "  cd $TEST_DIR && wt-orchestrate coverage"
    echo ""
    info "After sentinel completes, generate the E2E report:"
    echo "  cd $TEST_DIR"
    echo "  wt-e2e-report --project-dir $TEST_DIR"
    echo ""
    info "When done, cleanup:"
    echo "  rm -rf $TEST_DIR"
    echo "  rm -rf ~/.local/share/wt-tools/memory/$PROJECT_NAME"
    echo "  wt-project remove $PROJECT_NAME"
}

# ── Main ──

preflight
check_history_guard
check_existing
init_project
show_completion
