#!/usr/bin/env bash
# MiniShop E2E Test Runner
# Sets up a test project for set-core end-to-end testing.
# The scaffold is a single file (docs/v1-minishop.md). Agents build everything from the spec.
#
# Usage:
#   ./tests/e2e/runners/run-minishop.sh                              # Auto-increment: ~/.local/share/set-core/e2e-runs/minishop-run9, ...
#   ./tests/e2e/runners/run-minishop.sh /path/to/dir                 # Use specified dir
#   ./tests/e2e/runners/run-minishop.sh --project-dir ~/other-dir    # Override base dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/../scaffolds/minishop"
SPEC_FILE="$SCAFFOLD_DIR/docs/v1-minishop.md"
E2E_RUNS_DIR="${HOME}/.local/share/set-core/e2e-runs"
BASE_DIR="${WT_E2E_DIR:-$E2E_RUNS_DIR}"
mkdir -p "$BASE_DIR"

# Auto-increment run number: find highest existing minishop-runN, use N+1
next_run_number() {
    local max=0
    for d in "$BASE_DIR"/minishop-run*; do
        [[ -d "$d" ]] || continue
        local n="${d##*minishop-run}"
        n="${n%%-*}"  # strip worktree suffixes like -wt-cart-feature
        [[ "$n" =~ ^[0-9]+$ ]] && (( n > max )) && max=$n
    done
    echo $(( max + 1 ))
}

# Parse --project-dir flag
if [[ "${1:-}" == "--project-dir" ]]; then
    if [[ -z "${2:-}" ]]; then
        error "--project-dir requires a directory argument"
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
    TEST_DIR="$BASE_DIR/minishop-run${RUN_NUM}"
    PROJECT_NAME="minishop-run${RUN_NUM}"
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

    if ! set-project list-types 2>/dev/null | grep -q "web"; then
        die "set-project-web plugin not installed (set-project list-types does not show 'web')"
    fi

    [[ -f "$SPEC_FILE" ]] || die "Spec file not found: $SPEC_FILE"

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
        info "To continue with sentinel:"
        echo "  cd $TEST_DIR && set-sentinel --spec docs/v1-minishop.md"
        echo ""
        info "To reset from a checkpoint:"
        echo "  cd $TEST_DIR"
        echo "  git worktree list  # remove any worktrees"
        echo "  git checkout -b resume-<tag> <tag>"
        echo "  set-project init --name $PROJECT_NAME --project-type web"
        echo "  rm -f orchestration-state.json orchestration-plan.json"
        echo "  set-sentinel --spec docs/v1-minishop.md"
        exit 0
    fi
}

# ── Main initialization ──

init_project() {
    step "Copy spec and design assets"
    mkdir -p "$TEST_DIR/docs"
    cp -r "$SCAFFOLD_DIR/docs/"* "$TEST_DIR/docs/"
    success "Spec + design assets copied to $TEST_DIR/docs/"

    cd "$TEST_DIR"

    step "Git init"
    git init
    git checkout -b main 2>/dev/null || true

    # .gitattributes — prevent lockfile and runtime file conflicts at git level.
    # merge=ours: on conflict, silently keep current branch version.
    # Lockfile regeneration happens via set-merge's regenerate_lockfile() and
    # merger.py's _post_merge_deps_install() — NOT via git hook (hooks leave
    # dirty working tree state that blocks subsequent merges).
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
    git commit -m "initial: minishop spec"
    git tag v0-spec
    success "Git initialized, tagged v0-spec (merge drivers + post-merge hook configured)"

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

    # NOTE: Figma MCP registration removed — OAuth requires interactive auth
    # which blocks `claude -p` (pipe mode) used by the orchestrator.
    # Design data is available via static design-snapshot.md files.

    step "Orchestration config"
    # Overwrite template config.yaml with E2E-specific values
    cat > set/orchestration/config.yaml <<YAML
# Orchestration config for MiniShop E2E test
default_model: opus
max_parallel: 2
auto_replan: true
review_before_merge: true
max_verify_retries: 2
e2e_timeout: 120
env_vars:
  DATABASE_URL: "file:./dev.db"
discord:
  enabled: true
  channel_name: minishop
YAML

    # Extract Figma design URL from spec if present
    local design_file_url=""
    if [[ -f "docs/v1-minishop.md" ]]; then
        design_file_url=$(grep -oP 'https://www\.figma\.com/(design|make)/[^\s)]+' docs/v1-minishop.md | head -1 || true)
    fi
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
    echo ""
    info "To start the E2E test:"
    echo "  cd $TEST_DIR"
    echo "  set-sentinel --spec docs/v1-minishop.md"
    echo ""
    info "After sentinel completes, generate the E2E report:"
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
