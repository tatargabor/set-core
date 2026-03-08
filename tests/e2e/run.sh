#!/usr/bin/env bash
# MiniShop E2E Test Runner
# Sets up a test project for wt-tools end-to-end testing.
#
# Usage:
#   ./tests/e2e/run.sh              # Use default dir ($TMPDIR/minishop-e2e or /tmp/minishop-e2e)
#   ./tests/e2e/run.sh /path/to/dir # Use specified dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/scaffold"
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
    command -v npm &>/dev/null || die "npm not found in PATH"

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
    step "Scaffold copy"
    mkdir -p "$TEST_DIR"
    cp -r "$SCAFFOLD_DIR"/. "$TEST_DIR/"
    # Create .env from example
    if [[ -f "$TEST_DIR/.env.example" && ! -f "$TEST_DIR/.env" ]]; then
        cp "$TEST_DIR/.env.example" "$TEST_DIR/.env"
    fi
    # Inject Resend email credentials from wt-tools .env (for E2E email reports)
    local wt_env="$SCRIPT_DIR/../../.env"
    if [[ -f "$wt_env" ]]; then
        local resend_key resend_from resend_to
        resend_key=$(grep '^RESEND_API_KEY=' "$wt_env" | cut -d= -f2-)
        resend_from=$(grep '^RESEND_FROM=' "$wt_env" | cut -d= -f2-)
        resend_to=$(grep '^RESEND_TO=' "$wt_env" | cut -d= -f2-)
        if [[ -n "$resend_key" && -n "$resend_to" ]]; then
            {
                echo ""
                echo "# Email notifications (injected from wt-tools)"
                echo "RESEND_API_KEY=$resend_key"
                [[ -n "$resend_from" ]] && echo "RESEND_FROM=$resend_from"
                echo "RESEND_TO=$resend_to"
            } >> "$TEST_DIR/.env"
            success "Injected Resend email config into .env"
        fi
    fi
    success "Scaffold copied to $TEST_DIR"

    cd "$TEST_DIR"

    step "Git init"
    git init
    git add -A
    git commit -m "initial: minishop scaffold"
    git tag v0-scaffold
    success "Git initialized, tagged v0-scaffold"

    step "wt-project init"
    handle_name_conflict
    # wt-project init may return non-zero due to deploy warnings (MCP, legacy files)
    # so we check for .claude/ directory instead of exit code
    wt-project init --name "$PROJECT_NAME" --project-type web || true

    if [[ ! -d ".claude" ]]; then
        die ".claude/ directory not created by wt-project init"
    fi
    success "wt-project initialized"

    # Create orchestration config BEFORE the v1-initialized commit
    step "Orchestration config"
    mkdir -p wt/orchestration
    # Determine notification channel based on whether Resend is configured
    local notif_channel="desktop"
    if [[ -f ".env" ]] && grep -q '^RESEND_API_KEY=' ".env" 2>/dev/null; then
        notif_channel="desktop+email"
    fi
    cat > wt/orchestration/config.yaml <<YAML
# Orchestration config for MiniShop E2E test
smoke_command: npm test
smoke_blocking: true
test_command: npm test
max_parallel: 2
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
notification: $notif_channel
YAML
    success "Created wt/orchestration/config.yaml"

    git add -A
    git commit -m "chore: wt-project init + orchestration config"
    git tag v1-initialized
    success "Tagged v1-initialized"

    step "npm install"
    npm install || die "npm install failed"

    step "npm test (smoke check)"
    npm test || die "npm test failed — scaffold tests broken"

    git add -A
    git commit -m "chore: npm install"
    git tag v2-ready
    success "Tagged v2-ready"
}

# ── Cleanup info ──

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
    info "When done, cleanup:"
    echo "  rm -rf $TEST_DIR"
    echo "  wt-project remove $PROJECT_NAME"
}

# ── Main ──

preflight
check_existing
init_project
show_completion
