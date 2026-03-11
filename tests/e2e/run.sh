#!/usr/bin/env bash
# MiniShop E2E Test Runner
# Sets up a test project for wt-tools end-to-end testing.
# The scaffold is a single file (docs/v1-minishop.md). Agents build everything from the spec.
#
# Usage:
#   ./tests/e2e/run.sh              # Use default dir ($TMPDIR/minishop-e2e or /tmp/minishop-e2e)
#   ./tests/e2e/run.sh /path/to/dir # Use specified dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SPEC_FILE="$SCRIPT_DIR/scaffold/docs/v1-minishop.md"
DEFAULT_DIR="${TMPDIR:-/tmp}/minishop-e2e"
TEST_DIR="${1:-$DEFAULT_DIR}"
PROJECT_NAME="minishop-e2e"

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

    if ! wt-project list-types 2>/dev/null | grep -q "web"; then
        die "wt-project-web plugin not installed (wt-project list-types does not show 'web')"
    fi

    [[ -f "$SPEC_FILE" ]] || die "Spec file not found: $SPEC_FILE"

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
        echo "  cd $TEST_DIR && wt-sentinel --spec docs/v1-minishop.md"
        echo ""
        info "To reset from a checkpoint:"
        echo "  cd $TEST_DIR"
        echo "  git worktree list  # remove any worktrees"
        echo "  git checkout -b resume-<tag> <tag>"
        echo "  wt-project init --name $PROJECT_NAME --project-type web"
        echo "  rm -f orchestration-state.json orchestration-plan.json"
        echo "  wt-sentinel --spec docs/v1-minishop.md"
        exit 0
    fi
}

# ── Main initialization ──

init_project() {
    step "Copy spec"
    mkdir -p "$TEST_DIR/docs"
    cp "$SPEC_FILE" "$TEST_DIR/docs/"
    success "Spec copied to $TEST_DIR/docs/v1-minishop.md"

    cd "$TEST_DIR"

    step "Git init"
    git init
    git add -A
    git commit -m "initial: minishop spec"
    git tag v0-spec
    success "Git initialized, tagged v0-spec"

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

    step "Orchestration config"
    mkdir -p wt/orchestration
    cat > wt/orchestration/config.yaml <<YAML
# Orchestration config for MiniShop E2E test
test_command: pnpm test
e2e_command: npx playwright test
e2e_timeout: 120
smoke_command: pnpm test
smoke_blocking: true
max_parallel: 2
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
YAML
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
    info "Git tags: $(cd "$TEST_DIR" && git tag | tr '\n' ' ')"
    echo ""
    info "To start the E2E test:"
    echo "  cd $TEST_DIR"
    echo "  wt-sentinel --spec docs/v1-minishop.md"
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
