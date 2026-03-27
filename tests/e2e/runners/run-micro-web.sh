#!/usr/bin/env bash
# Micro Web E2E Test Runner
# Minimal Next.js app (5 pages) for validating gate enforcement pipeline.
# Tests: e2e autodetect, lint gate, spec verify, profile resolution.
#
# Usage:
#   ./tests/e2e/runners/run-micro-web.sh                              # Auto-increment
#   ./tests/e2e/runners/run-micro-web.sh /path/to/dir                 # Use specified dir
#   ./tests/e2e/runners/run-micro-web.sh --project-dir ~/other-dir    # Override base dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/../scaffolds/micro-web"
SPEC_FILE="$SCAFFOLD_DIR/docs/spec.md"
E2E_RUNS_DIR="${HOME}/.local/share/set-core/e2e-runs"
BASE_DIR="${WT_E2E_DIR:-$E2E_RUNS_DIR}"
mkdir -p "$BASE_DIR"

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
die()     { error "$*"; echo "  Test dir: $TEST_DIR"; exit 1; }

# Auto-increment run number
next_run_number() {
    local max=0
    for d in "$BASE_DIR"/micro-web-run*; do
        [[ -d "$d" ]] || continue
        local n="${d##*micro-web-run}"
        n="${n%%-*}"
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
    TEST_DIR="$BASE_DIR/micro-web-run${RUN_NUM}"
    PROJECT_NAME="micro-web-run${RUN_NUM}"
fi

# ── Preflight checks ──

preflight() {
    step "Preflight checks"

    command -v set-project &>/dev/null || die "set-project not found in PATH"
    command -v node &>/dev/null || die "node not found in PATH"
    command -v pnpm &>/dev/null || die "pnpm not found in PATH"
    command -v git &>/dev/null || die "git not found in PATH"

    [[ -f "$SPEC_FILE" ]] || die "Spec file not found: $SPEC_FILE"

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
        error "but .git directory is MISSING."
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
        echo "  cd $TEST_DIR && set-orchestrate start --spec docs/spec.md"
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
    step "Create project"
    info "Creating $PROJECT_NAME at $TEST_DIR"
    mkdir -p "$TEST_DIR/docs"
    cd "$TEST_DIR"
    git init
    git checkout -b main 2>/dev/null || true

    # Copy spec
    cp "$SPEC_FILE" docs/spec.md

    # .gitattributes — prevent lockfile conflicts
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
    git commit -m "add micro-web spec"
    git tag v0-spec
    success "Spec committed (tagged v0-spec)"

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
    success "set-core deployed (configs, rules, CLAUDE.md)"

    # Deploy scaffold-specific templates (rules, overrides)
    if [[ -d "$SCAFFOLD_DIR/templates/rules" ]]; then
        info "Deploying scaffold templates..."
        cp "$SCAFFOLD_DIR/templates/rules/"*.md "$TEST_DIR/.claude/rules/" 2>/dev/null && \
            success "Scaffold rules deployed" || true
    fi

    step "Orchestration config"
    mkdir -p set/orchestration
    cat > set/orchestration/config.yaml << 'YAML'
# Orchestration config for Micro-Web E2E
default_model: sonnet
test_command: pnpm test
e2e_command: npx playwright test
e2e_timeout: 120
max_parallel: 2
merge_policy: checkpoint
checkpoint_auto_approve: true
auto_replan: true
max_replan_cycles: 2
review_before_merge: true
max_verify_retries: 2
env_vars:
  DATABASE_URL: "file:./dev.db"
discord:
  enabled: true
  channel_name: micro-web
YAML
    success "Created set/orchestration/config.yaml"

    git add -A
    git commit -m "chore: set-project init + orchestration config"
    git tag v1-ready
    success "Tagged v1-ready"
}

# ── Validate gate enforcement ──

validate_gates() {
    step "Validate gate enforcement"

    PYTHONPATH="${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}/lib:${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}/modules/web:${PYTHONPATH:-}" \
    python3 -c "
import sys, os
wt = '$TEST_DIR'

from set_orch.profile_loader import load_profile, reset_cache
reset_cache()
p = load_profile(wt)
assert p.info.name == 'web', f'Expected web profile, got {p.info.name}'
print(f'  Profile: {p.info.name} v{p.info.version}')

cmd = p.detect_e2e_command(wt)
print(f'  E2E command: {cmd or \"(none)\"}')

patterns = p.get_forbidden_patterns()
print(f'  Forbidden patterns: {len(patterns)}')

rules = p.get_verification_rules()
core = sum(1 for r in rules if r.id in ('file-size-limit','no-secrets-in-source','todo-tracking'))
print(f'  Rules: {len(rules)} ({core} core + {len(rules)-core} web)')
print('  All checks passed')
"
    success "Gate enforcement validated"
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
    echo "  set-orchestrate start --spec docs/spec.md"
    echo ""
    info "The orchestrator will:"
    echo "  1. Digest spec → structured requirements"
    echo "  2. Decompose → change plan with dependencies"
    echo "  3. Dispatch agents (parallel worktrees)"
    echo "  4. Verify gates: build → test → e2e → lint → review → rules"
    echo "  5. Merge verified changes to main"
    echo ""
    warn "Mid-run set-core fixes:"
    echo "  1. set-project init --name $PROJECT_NAME   # re-deploy"
    echo "  2. Sync to active worktrees:"
    echo "     for wt in \$(git worktree list --porcelain | grep '^worktree ' | awk '{print \$2}'); do"
    echo "       cp -r .claude/commands/ \"\$wt/.claude/commands/\""
    echo "       cp -r .claude/skills/ \"\$wt/.claude/skills/\""
    echo "     done"
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
validate_gates
show_completion
