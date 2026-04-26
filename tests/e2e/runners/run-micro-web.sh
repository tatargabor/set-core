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

# Generate timestamp-based run ID (e.g., micro-web-run-20260407-2246)
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
    TEST_DIR="$BASE_DIR/micro-web-run-${RUN_TS}"
    PROJECT_NAME="micro-web-run-${RUN_TS}"
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
    step "Materialize v0 design source into scaffold (if declared)"
    # scaffold.yaml may declare a v0-git design source. Mirrors run-craftbrew.
    # If the URL is the placeholder (PLACEHOLDER/v0-micro-web-design.git), the
    # import is skipped — the run continues without v0-export, which means the
    # design-fidelity gate has nothing to validate against (skipped, not failed).
    # Update scaffold.yaml::design_source.repo with the real URL once you've
    # pushed the v0 design to GitHub.
    if grep -q '^design_source:' "$SCAFFOLD_DIR/scaffold.yaml"; then
        local repo_url
        repo_url=$(grep -E '^\s+repo:' "$SCAFFOLD_DIR/scaffold.yaml" | head -1 | awk '{print $2}')
        if [[ "$repo_url" == *PLACEHOLDER* ]]; then
            warn "scaffold.yaml::design_source.repo is the placeholder; skipping v0 import"
            warn "Update scaffold.yaml with the real v0-micro-web-design URL to enable design-fidelity"
        elif ! command -v set-design-import &>/dev/null; then
            warn "set-design-import not in PATH — skipping v0 import (install modules/web)"
        elif [[ ! -d "$SCAFFOLD_DIR/v0-export" ]]; then
            info "Running set-design-import against scaffold..."
            if set-design-import --scaffold "$SCAFFOLD_DIR" --force; then
                success "v0 design source ready at $SCAFFOLD_DIR"
            else
                warn "set-design-import failed — continuing without v0-export (design-fidelity skipped)"
            fi
        else
            info "v0-export/ already materialized at scaffold; skipping import"
        fi
    fi

    step "Create project"
    info "Creating $PROJECT_NAME at $TEST_DIR"
    mkdir -p "$TEST_DIR/docs"
    cd "$TEST_DIR"
    git init
    git checkout -b main 2>/dev/null || true

    # Copy spec + design files
    cp "$SPEC_FILE" docs/spec.md
    for df in "$SCAFFOLD_DIR"/docs/design-*.md; do
        [[ -f "$df" ]] && cp "$df" docs/ && info "Deployed $(basename "$df")"
    done

    # Deploy materialized v0-export/ to the consumer project (the fidelity
    # gate needs it locally for reference rendering and primitive parity).
    if [[ -d "$SCAFFOLD_DIR/v0-export" ]]; then
        info "Deploying v0-export/ to consumer project..."
        cp -r "$SCAFFOLD_DIR/v0-export" "$TEST_DIR/v0-export"
        success "v0-export/ deployed"
    fi

    # Deploy design-manifest.yaml if generated by set-design-import
    if [[ -f "$SCAFFOLD_DIR/docs/design-manifest.yaml" ]]; then
        cp "$SCAFFOLD_DIR/docs/design-manifest.yaml" "$TEST_DIR/docs/design-manifest.yaml"
        info "design-manifest.yaml deployed"
    fi

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

    # .gitignore for v0-export — the dispatcher creates per-worktree
    # symlinks to project-root v0-export/. Pattern without trailing slash so
    # both the project-root directory AND worktree symlinks are ignored.
    if [[ -f .gitignore ]]; then
        grep -qxF "v0-export" .gitignore || echo "v0-export" >> .gitignore
    else
        echo "v0-export" > .gitignore
    fi

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

    # Deploy scaffold design assets (globals.css with shadcn theme)
    if [[ -f "$SCAFFOLD_DIR/src/app/globals.css" ]]; then
        cp "$SCAFFOLD_DIR/src/app/globals.css" "$TEST_DIR/src/app/globals.css"
        info "Scaffold globals.css deployed (shadcn theme)"
    fi

    # Deploy shadcn/ui overlay (if scaffold opts in via shadcn/ dir)
    source "$SCRIPT_DIR/lib/deploy-shadcn.sh"
    deploy_shadcn_overlay "$SCAFFOLD_DIR" "$TEST_DIR"

    step "Orchestration config"
    # `set-project init` already deployed the web template default
    # config.yaml. We don't overwrite it — defaults are good for a small
    # scaffold like this. Only thing we add is discord wiring for run
    # observability (the default has it commented out).
    if [[ -f set/orchestration/config.yaml ]] && ! grep -q "^discord:" set/orchestration/config.yaml; then
        cat >> set/orchestration/config.yaml <<'YAML'

discord:
  enabled: true
  channel_name: micro-web
YAML
        info "Appended discord wiring to set/orchestration/config.yaml"
    fi

    git add -A
    git commit -m "chore: set-project init + orchestration config"
    git tag v1-ready
    success "Tagged v1-ready"
}

# ── Validate gate enforcement ──

validate_gates() {
    step "Validate gate enforcement"

    # Find a Python that can import set_orch (prefer python3.12, then python3)
    local _py=""
    for _candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "$_candidate" &>/dev/null && "$_candidate" -c "import set_orch" 2>/dev/null; then
            _py="$_candidate"
            break
        fi
    done
    [[ -n "$_py" ]] || die "No Python with set_orch found"

    PYTHONPATH="${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}/lib:${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../../.." && pwd)}/modules/web:${PYTHONPATH:-}" \
    "$_py" -c "
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
validate_gates
show_completion
