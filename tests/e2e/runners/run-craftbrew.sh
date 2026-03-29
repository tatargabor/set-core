#!/usr/bin/env bash
# CraftBrew E2E Test Runner
# Clones the CraftBrew spec repo, initializes it as a set-project, and prepares
# it for orchestration. The spec is a multi-file business specification (docs/)
# with 17+ files. The orchestrator auto-triggers digest before planning, then agents
# build from the structured digest.
#
# Usage:
#   ./tests/e2e/runners/run-craftbrew.sh                              # Auto-increment: ~/.local/share/set-core/e2e-runs/craftbrew-run1, ...
#   ./tests/e2e/runners/run-craftbrew.sh /path/to/dir                 # Clone to specified dir
#   ./tests/e2e/runners/run-craftbrew.sh --project-dir ~/other-dir    # Override base dir
#
# The spec source repo: https://github.com/tatargabor/craftbrew

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/../scaffolds/craftbrew"
CRAFTBREW_REPO="https://github.com/tatargabor/craftbrew.git"
CRAFTBREW_BRANCH="spec-only"
E2E_RUNS_DIR="${HOME}/.local/share/set-core/e2e-runs"
BASE_DIR="${WT_E2E_DIR:-$E2E_RUNS_DIR}"
mkdir -p "$BASE_DIR"

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

# Parse --project-dir flag
if [[ "${1:-}" == "--project-dir" ]]; then
    if [[ -z "${2:-}" ]]; then
        echo "[error] --project-dir requires a directory argument" >&2
        exit 1
    fi
    BASE_DIR="$2"
    mkdir -p "$BASE_DIR"
    shift 2
fi

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

    command -v set-project &>/dev/null || die "set-project not found in PATH"
    command -v node &>/dev/null || die "node not found in PATH"
    command -v pnpm &>/dev/null || die "pnpm not found in PATH"
    command -v git &>/dev/null || die "git not found in PATH"

    if ! set-project list-types 2>/dev/null | grep -q "web"; then
        die "set-project-web plugin not installed (set-project list-types does not show 'web')"
    fi

    success "All prerequisites met"
}

# ── Name conflict handling ──

handle_name_conflict() {
    local existing_path
    existing_path=$(set-project list 2>/dev/null | grep "$PROJECT_NAME" | sed 's/.*-> //' || true)

    if [[ -n "$existing_path" ]]; then
        local abs_test_dir
        abs_test_dir=$(cd "$TEST_DIR" 2>/dev/null && pwd || echo "$TEST_DIR")

        if [[ "$existing_path" != "$abs_test_dir" ]]; then
            warn "Project '$PROJECT_NAME' already registered at: $existing_path"
            info "Removing old registration..."
            set-project remove "$PROJECT_NAME" 2>/dev/null || true
        fi
    fi
}

# ── History protection guard ──

check_history_guard() {
    local registered_path
    registered_path=$(set-project list 2>/dev/null | grep "$PROJECT_NAME" | sed 's/.*-> //' || true)

    if [[ -n "$registered_path" && -d "$registered_path" && ! -d "$registered_path/.git" ]]; then
        error "HISTORY PROTECTION: Project '$PROJECT_NAME' is registered at $registered_path"
        error "but .git directory is MISSING. The git history was likely deleted externally."
        error ""
        error "This guard prevents accidental loss of orchestration work."
        error "If the previous run had orch/* tags, they are now lost."
        error ""
        error "To force a fresh start, first unregister:"
        error "  set-project remove $PROJECT_NAME"
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
        info "To continue with orchestrator:"
        echo "  cd $TEST_DIR && set-orchestrate start --spec docs/"
        echo ""
        info "To reset from a checkpoint:"
        echo "  cd $TEST_DIR"
        echo "  git worktree list  # remove any worktrees"
        echo "  git checkout -b resume-<tag> <tag>"
        echo "  set-project init --name $PROJECT_NAME --project-type web"
        echo "  rm -f orchestration-state.json orchestration-plan.json"
        echo "  rm -rf set/orchestration/digest/"
        echo "  set-orchestrate start --spec docs/"
        exit 0
    fi
}

# ── Main initialization ──

init_project() {
    step "Clone CraftBrew spec repo"
    git clone --branch "$CRAFTBREW_BRANCH" "$CRAFTBREW_REPO" "$TEST_DIR"
    cd "$TEST_DIR"

    # Remove origin remote to prevent merge pipeline from pulling upstream code
    # (the upstream repo may have full implementation on main which contaminates merges)
    git remote remove origin 2>/dev/null || true

    local file_count
    file_count=$(find "$TEST_DIR/docs" -name '*.md' | wc -l)
    success "Cloned CraftBrew repo ($file_count spec files in docs/)"

    step "Copy scaffold extras (design snapshot, figma-raw)"
    # The scaffold-complex dir contains pre-fetched Figma assets that aren't in the
    # GitHub repo. Copy them over so the design bridge works without live Figma fetch.
    if [[ -d "$SCAFFOLD_DIR" ]]; then
        # Copy design-snapshot.md if present
        if [[ -f "$SCAFFOLD_DIR/docs/design-snapshot.md" ]]; then
            cp "$SCAFFOLD_DIR/docs/design-snapshot.md" "$TEST_DIR/docs/"
        fi
        # Copy figma-raw directory if present
        if [[ -d "$SCAFFOLD_DIR/docs/figma-raw" ]]; then
            cp -r "$SCAFFOLD_DIR/docs/figma-raw" "$TEST_DIR/docs/"
        fi
        # Copy figma.md to project root if present
        if [[ -f "$SCAFFOLD_DIR/figma.md" ]]; then
            cp "$SCAFFOLD_DIR/figma.md" "$TEST_DIR/"
        fi
        success "Scaffold extras copied (design snapshot + figma-raw)"
    else
        warn "No scaffold-complex directory found at $SCAFFOLD_DIR — skipping design assets"
    fi

    step "Tag spec baseline"

    # .gitattributes — prevent lockfile and runtime file conflicts at git level.
    # merge=ours: on conflict, silently keep current branch version.
    # Lockfile regeneration happens via set-merge's regenerate_lockfile() and
    # merger.py's _post_merge_deps_install() — NOT via git hook.
    cat > .gitattributes << 'ATTRS'
# set-core: generated/runtime files — always prefer ours on conflict
pnpm-lock.yaml    merge=ours
yarn.lock         merge=ours
package-lock.json merge=ours
*.tsbuildinfo     merge=ours
next-env.d.ts     merge=ours
.claude/**        merge=ours
wt/**             merge=ours
ATTRS
    git config merge.ours.driver true

    git tag v0-spec
    success "Tagged v0-spec (merge drivers configured)"

    step "Clean stale memory"
    local mem_storage="${SHODH_STORAGE:-${HOME}/.local/share/set-core/memory}/${PROJECT_NAME}"
    if [[ -d "$mem_storage" ]]; then
        info "Removing stale memory storage: $mem_storage"
        rm -rf "$mem_storage"
        success "Memory storage cleaned"
    fi

    step "set-project init"
    handle_name_conflict
    set-project init --name "$PROJECT_NAME" --project-type web --template nextjs || true

    if [[ ! -d ".claude" ]]; then
        die ".claude/ directory not created by set-project init"
    fi
    success "set-project initialized (configs, rules, CLAUDE.md deployed)"

    # Deploy scaffold-specific templates (rules, overrides)
    if [[ -d "$SCAFFOLD_DIR/templates/rules" ]]; then
        info "Deploying scaffold templates..."
        cp "$SCAFFOLD_DIR/templates/rules/"*.md "$TEST_DIR/.claude/rules/" 2>/dev/null && \
            success "Scaffold rules deployed" || true
    fi

    # NOTE: Figma MCP registration removed — OAuth requires interactive auth
    # which blocks `claude -p` (pipe mode) used by the orchestrator.
    # Design data is available via static design-snapshot.md + figma-raw/ files
    # copied from scaffold-complex/. The planner reads these directly.

    step "Orchestration config"
    mkdir -p set/orchestration
    # Read design_file from docs/design/design-system.md if it exists
    local design_file_url=""
    local design_system="docs/design/design-system.md"
    if [[ -f "$design_system" ]]; then
        # Extract first figma.com URL (Design or Make)
        design_file_url=$(grep -oP 'https://www\.figma\.com/(design|make)/[^\s)]+' "$design_system" | head -1 || true)
    fi

    cat > set/orchestration/config.yaml <<YAML
# Orchestration config for CraftBrew E2E
default_model: opus-1m
test_command: pnpm test
e2e_command: npx playwright test
e2e_timeout: 180
max_parallel: 2
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
max_replan_cycles: 3
review_before_merge: true
max_verify_retries: 2
env_vars:
  DATABASE_URL: "file:./dev.db"
discord:
  enabled: true
  channel_name: craftbrew
YAML

    if [[ -n "$design_file_url" ]]; then
        echo "design_file: \"$design_file_url\"" >> set/orchestration/config.yaml
        success "Design file reference: $design_file_url"
    else
        # Check if Figma MCP is registered but no URL was extracted
        if jq -e '.mcpServers.figma' .claude/settings.json &>/dev/null 2>&1; then
            warn "Figma MCP is registered but no design_file URL found in $design_system"
            warn "Add a Figma URL to docs/design/design-system.md for design token injection"
            warn "Format: **Figma Make:** https://www.figma.com/make/XXXX/Name"
        fi
    fi
    success "Created set/orchestration/config.yaml"

    git add -A
    git commit -m "chore: set-project init + orchestration config"
    git tag v1-ready
    git branch -m spec-only main
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
    echo "  set-orchestrate start --spec docs/"
    echo ""
    info "The orchestrator will:"
    echo "  1. Detect directory spec → auto-trigger digest"
    echo "  2. Generate set/orchestration/digest/ (requirements, domains, conventions)"
    echo "  3. Plan changes from structured digest"
    echo "  4. Dispatch agents with spec-context per worktree"
    echo "  5. Track requirement coverage through execution"
    echo ""
    warn "IMPORTANT: Mid-run set-core fixes"
    echo "  Symlinks are NOT enough — .claude/ files must be real copies."
    echo "  After fixing a bug in set-core during a run:"
    echo "    1. set-project init --name $PROJECT_NAME   # re-deploy to main worktree"
    echo "    2. Sync to active agent worktrees:"
    echo "       for wt in \$(git worktree list --porcelain | grep '^worktree ' | awk '{print \$2}'); do"
    echo "         cp -r .claude/commands/ \"\$wt/.claude/commands/\""
    echo "         cp -r .claude/skills/ \"\$wt/.claude/skills/\""
    echo "         cp .claude/CLAUDE.md \"\$wt/.claude/CLAUDE.md\" 2>/dev/null || true"
    echo "       done"
    echo "  Running agents pick up the new files on their next iteration."
    echo ""
    info "To check requirement coverage during/after run:"
    echo "  cd $TEST_DIR && set-orchestrate coverage"
    echo ""
    info "After orchestration completes, generate the E2E report:"
    echo "  cd $TEST_DIR"
    echo "  set-e2e-report --project-dir $TEST_DIR"
    echo ""
    info "When done, cleanup:"
    echo "  rm -rf $TEST_DIR"
    echo "  rm -rf ~/.local/share/set-core/memory/$PROJECT_NAME"
    echo "  set-project remove $PROJECT_NAME"
}

# ── Main ──

preflight
check_history_guard
check_existing
init_project
show_completion
