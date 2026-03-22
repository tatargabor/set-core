#!/usr/bin/env bash
# Micro Web E2E Test Runner
# Minimal Next.js app (5 pages) for validating gate enforcement pipeline.
# Tests: e2e autodetect, lint gate, spec verify, profile resolution.
#
# Usage:
#   ./tests/e2e/run-micro.sh                    # Auto-increment run number
#   ./tests/e2e/run-micro.sh /path/to/dir       # Use specified dir

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCAFFOLD_DIR="$SCRIPT_DIR/../scaffolds/micro-web"
SPEC_FILE="$SCAFFOLD_DIR/docs/spec.md"
E2E_RUNS_DIR="${HOME}/.local/share/set-core/e2e-runs"
mkdir -p "$E2E_RUNS_DIR"

# ── Colors ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()    { echo -e "${BLUE}[info]${NC} $*"; }
success() { echo -e "${GREEN}[ok]${NC} $*"; }
warn()    { echo -e "${YELLOW}[warn]${NC} $*"; }
error()   { echo -e "${RED}[error]${NC} $*"; }

# Auto-increment run number
next_run_number() {
    local max=0
    for d in "$E2E_RUNS_DIR"/micro-web-run*; do
        [[ -d "$d" ]] || continue
        local n="${d##*micro-web-run}"
        n="${n%%-*}"
        [[ "$n" =~ ^[0-9]+$ ]] && (( n > max )) && max=$n
    done
    echo $(( max + 1 ))
}

if [[ -n "${1:-}" ]]; then
    TEST_DIR="$1"
    PROJECT_NAME="$(basename "$TEST_DIR")"
else
    RUN_NUM=$(next_run_number)
    TEST_DIR="$E2E_RUNS_DIR/micro-web-run${RUN_NUM}"
    PROJECT_NAME="micro-web-run${RUN_NUM}"
fi

# ── Setup ──

if [[ -d "$TEST_DIR/.git" ]]; then
    info "Reusing existing project at $TEST_DIR"
else
    info "Creating $PROJECT_NAME at $TEST_DIR"
    mkdir -p "$TEST_DIR/docs"
    cd "$TEST_DIR"
    git init
    git checkout -b main 2>/dev/null || true

    # Copy spec
    cp "$SPEC_FILE" docs/spec.md
    git add -A
    git commit -m "add micro-web spec"

    # Deploy set-core + web profile
    info "Deploying set-core..."
    set-project init --project-type web --template nextjs

    # Add orchestration config (engine reads from wt/orchestration/config.yaml)
    mkdir -p wt/orchestration
    cat > wt/orchestration/config.yaml << 'ORCH'
default_model: sonnet
test_command: pnpm test
e2e_command: npx playwright test
e2e_timeout: 120
max_parallel: 2
merge_policy: eager
review_before_merge: true
env_vars:
  DATABASE_URL: "file:./dev.db"
discord:
  enabled: true
  channel_name: micro-web
ORCH

    git add -A
    git commit -m "set-project init: web/nextjs + orchestration config"
    success "Project scaffolded"
fi

cd "$TEST_DIR"

# ── Validate ──

info "Validating gate enforcement..."

PYTHONPATH="${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}/lib:${SET_TOOLS_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}/modules/web:${PYTHONPATH:-}" \
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

# ── Launch ──

info "Starting sentinel for $PROJECT_NAME..."
info "Spec: docs/spec.md"
info "Dir: $TEST_DIR"
echo ""

exec set-sentinel --project-dir "$TEST_DIR" --spec docs/spec.md
