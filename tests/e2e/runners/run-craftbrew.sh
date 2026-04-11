#!/usr/bin/env bash
# CraftBrew E2E Test Runner
# Sets up a test project for set-core end-to-end testing.
# The scaffold is a multi-file business specification (docs/) with 17+ files.
# The orchestrator auto-triggers digest before planning, then agents build from
# the structured digest.
#
# Usage:
#   ./tests/e2e/runners/run-craftbrew.sh                              # Auto-increment: ~/.local/share/set-core/e2e-runs/craftbrew-run1, ...
#   ./tests/e2e/runners/run-craftbrew.sh /path/to/dir                 # Use specified dir
#   ./tests/e2e/runners/run-craftbrew.sh --project-dir ~/other-dir    # Override base dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/../scaffolds/craftbrew"
E2E_RUNS_DIR="${HOME}/.local/share/set-core/e2e-runs"
BASE_DIR="${WT_E2E_DIR:-$E2E_RUNS_DIR}"
mkdir -p "$BASE_DIR"

# Generate timestamp-based run ID (e.g., craftbrew-run-20260407-2246)
run_timestamp() {
    date +%Y%m%d-%H%M
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
    RUN_TS=$(run_timestamp)
    TEST_DIR="$BASE_DIR/craftbrew-run-${RUN_TS}"
    PROJECT_NAME="craftbrew-run-${RUN_TS}"
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

    [[ -d "$SCAFFOLD_DIR/docs" ]] || die "Scaffold docs not found: $SCAFFOLD_DIR/docs"

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
        info "To force fresh start:"
        echo "  rm -rf $TEST_DIR"
        echo "  set-project remove $PROJECT_NAME 2>/dev/null || true"
        echo "  $0"
        exit 0
    fi
}

# ── Main initialization ──

init_project() {
    step "Copy spec and design assets"
    mkdir -p "$TEST_DIR/docs"
    cp -r "$SCAFFOLD_DIR/docs/"* "$TEST_DIR/docs/"

    # Copy figma.md to project root if present
    if [[ -f "$SCAFFOLD_DIR/figma.md" ]]; then
        cp "$SCAFFOLD_DIR/figma.md" "$TEST_DIR/"
    fi

    # Generate design-brief.md from figma.md if not already in scaffold
    if [[ -f "$TEST_DIR/figma.md" && ! -f "$TEST_DIR/docs/design-brief.md" ]]; then
        info "Generating design-brief.md from figma.md..."
        if command -v set-design-sync &>/dev/null; then
            set-design-sync --input "$TEST_DIR/figma.md" --spec-dir "$TEST_DIR/docs/" --output "$TEST_DIR/docs/design-system.md" 2>/dev/null || true
            [[ -f "$TEST_DIR/docs/design-brief.md" ]] && success "design-brief.md generated" || warn "design-brief.md generation failed"
        else
            warn "set-design-sync not found — design-brief.md not generated"
        fi
    fi

    local file_count
    file_count=$(find "$TEST_DIR/docs" -name '*.md' -o -name '*.make' | wc -l)
    success "Spec + design assets copied ($file_count files in docs/)"

    cd "$TEST_DIR"

    step "Git init"
    git init
    git checkout -b main 2>/dev/null || true

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

    git add -A
    git commit -m "initial: craftbrew spec"
    git tag v0-spec
    success "Git initialized, tagged v0-spec (merge drivers configured)"

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

    # Deploy scaffold design assets (globals.css with shadcn theme)
    if [[ -f "$SCAFFOLD_DIR/src/app/globals.css" ]]; then
        mkdir -p "$TEST_DIR/src/app"
        cp "$SCAFFOLD_DIR/src/app/globals.css" "$TEST_DIR/src/app/globals.css"
        info "Scaffold globals.css deployed (shadcn theme)"
    fi

    # Deploy shadcn/ui overlay (if scaffold opts in via shadcn/ dir)
    source "$SCRIPT_DIR/lib/deploy-shadcn.sh"
    deploy_shadcn_overlay "$SCAFFOLD_DIR" "$TEST_DIR"

    # NOTE: Figma MCP registration removed — OAuth requires interactive auth
    # which blocks `claude -p` (pipe mode) used by the orchestrator.
    # Design data is available via static design-snapshot.md + figma-raw/ files
    # copied from scaffold. The planner reads these directly.

    step "Orchestration config"
    mkdir -p set/orchestration
    # Read design_file from docs/design-system.md if it exists
    local design_file_url=""
    local design_system="docs/design-system.md"
    if [[ -f "$design_system" ]]; then
        # Extract first figma.com URL (Design or Make)
        design_file_url=$(grep -oP 'https://www\.figma\.com/(design|make)/[^\s)]+' "$design_system" | head -1 || true)
    fi

    cat > set/orchestration/config.yaml <<YAML
# Orchestration config for CraftBrew E2E
default_model: opus
e2e_command: npx playwright test
e2e_timeout: 600
max_parallel: 1
merge_policy: eager
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
    fi
    success "Created set/orchestration/config.yaml"

    git add -A
    git commit -m "chore: set-project init + orchestration config"
    git tag v1-ready
    success "Tagged v1-ready"
}

# ── Completion info ──

show_completion() {
    step "Ready!"
    echo ""
    info "Test project: $TEST_DIR"
    info "Git tags: $(cd "$TEST_DIR" && git tag | tr '\n' ' ')"
    info "Spec files: $(find "$TEST_DIR/docs" -name '*.md' -o -name '*.make' | wc -l)"
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
    warn "Mid-run set-core fixes:"
    echo "  1. set-project init --name $PROJECT_NAME   # re-deploy"
    echo "  2. Sync to active worktrees:"
    echo "     for wt in \$(git worktree list --porcelain | grep '^worktree ' | awk '{print \$2}'); do"
    echo "       cp -r .claude/commands/ \"\$wt/.claude/commands/\""
    echo "       cp -r .claude/skills/ \"\$wt/.claude/skills/\""
    echo "       cp .claude/CLAUDE.md \"\$wt/.claude/CLAUDE.md\" 2>/dev/null || true"
    echo "     done"
    echo ""
    warn "After run completes — harvest framework fixes:"
    echo "  set-harvest --project $PROJECT_NAME"
    echo ""
    info "Cleanup:"
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
