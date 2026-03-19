#!/usr/bin/env bash
# Level 3 End-to-end test: single change through full lifecycle
# Requires: Claude CLI, set-new, set-loop, set-merge available
# Cost: ~20-50k tokens (one Ralph session)
# Run with: ./tests/orchestrator/test-e2e.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"

source "$PROJECT_DIR/bin/set-common.sh"

# ============================================================
# Setup: create a real git project with trivial brief
# ============================================================

TMPDIR=$(mktemp -d)
cleanup() {
    info "Cleaning up..."
    # Kill any leftover Ralph loops
    pkill -f "set-loop.*hello-world" 2>/dev/null || true
    # Clean up worktrees
    if [[ -d "$TMPDIR/test-project-hello-world" ]]; then
        cd "$TMPDIR/test-project"
        git worktree remove "$TMPDIR/test-project-hello-world" --force 2>/dev/null || true
    fi
    rm -rf "$TMPDIR"
}
trap cleanup EXIT

PROJECT_PATH="$TMPDIR/test-project"
mkdir -p "$PROJECT_PATH"
cd "$PROJECT_PATH"

git init -q
git commit --allow-empty -q -m "init"

# Initialize openspec structure
mkdir -p openspec/specs openspec/changes

# Create a trivial brief with one simple feature
cat > openspec/project-brief.md <<'BRIEF'
# Project Brief

## Purpose

Test project for e2e orchestration validation.

## Tech Stack

- Plain text files

## Feature Roadmap

### Done

### Next
- Hello world: Create a file named hello.txt containing "Hello, World!"

### Ideas

## Orchestrator Directives
- max_parallel: 1
- merge_policy: eager
- checkpoint_every: 1
- test_command: test -f hello.txt
- notification: none
- token_budget: 100000
- pause_on_exit: false
BRIEF

git add -A && git commit -q -m "add project brief"

info "Test project created at $PROJECT_PATH"

# ============================================================
# Step 1: Generate plan
# ============================================================

info "Step 1: Generating plan..."

"$PROJECT_DIR/bin/set-orchestrate" plan 2>&1 || {
    error "Plan generation failed"
    exit 1
}

if [[ ! -f orchestration-plan.json ]]; then
    error "No plan file generated"
    exit 1
fi

change_count=$(jq '.changes | length' orchestration-plan.json)
info "Plan generated with $change_count change(s)"

# Should have at least 1 change
if [[ "$change_count" -lt 1 ]]; then
    error "Expected at least 1 change, got $change_count"
    exit 1
fi
success "Plan has $change_count change(s)"

# Get first change name
first_change=$(jq -r '.changes[0].name' orchestration-plan.json)
info "First change: $first_change"

# ============================================================
# Step 2: Start orchestration
# ============================================================

info "Step 2: Starting orchestration..."
info "This will run a full Ralph loop cycle. May take several minutes."

# Run orchestrator in background with timeout
timeout 600 "$PROJECT_DIR/bin/set-orchestrate" start 2>&1 &
ORCH_PID=$!

# Wait with progress updates
elapsed=0
while kill -0 "$ORCH_PID" 2>/dev/null; do
    sleep 15
    elapsed=$((elapsed + 15))

    if [[ -f orchestration-state.json ]]; then
        status=$(jq -r '.status' orchestration-state.json 2>/dev/null || echo "?")
        changes_status=$(jq -r '.changes[0].status // "?"' orchestration-state.json 2>/dev/null)
        info "  [${elapsed}s] orchestrator=$status change=$changes_status"

        # If orchestrator reached checkpoint, auto-approve
        if [[ "$status" == "checkpoint" ]]; then
            info "  Auto-approving checkpoint..."
            "$PROJECT_DIR/bin/set-orchestrate" approve --merge 2>/dev/null || true
        fi
    else
        info "  [${elapsed}s] waiting for state file..."
    fi

    # Safety timeout
    if [[ "$elapsed" -gt 540 ]]; then
        warn "Approaching timeout, stopping..."
        kill "$ORCH_PID" 2>/dev/null || true
        break
    fi
done

wait "$ORCH_PID" 2>/dev/null || true

# ============================================================
# Step 3: Verify results
# ============================================================

info "Step 3: Verifying results..."

if [[ ! -f orchestration-state.json ]]; then
    error "No state file — orchestrator may not have started"
    exit 1
fi

final_status=$(jq -r '.status' orchestration-state.json)
info "Final orchestrator status: $final_status"

# Check change went through lifecycle
first_change_status=$(jq -r ".changes[0].status" orchestration-state.json)
info "First change final status: $first_change_status"

if [[ "$first_change_status" == "merged" ]]; then
    success "Change reached 'merged' status"
elif [[ "$first_change_status" == "done" ]]; then
    warn "Change is 'done' but not merged (may need manual merge)"
else
    warn "Change status is '$first_change_status' (expected merged or done)"
fi

# Check if hello.txt exists on main branch
if [[ -f "hello.txt" ]]; then
    success "hello.txt exists on main branch"
    info "Content: $(cat hello.txt)"
else
    # Check if it exists on the change branch
    if git show "$first_change:hello.txt" &>/dev/null; then
        warn "hello.txt exists on branch '$first_change' but not yet on main"
    else
        warn "hello.txt not found (change may not have completed fully)"
    fi
fi

# Show final state summary
echo ""
info "=== Final State ==="
jq -r '.changes[] | "  \(.name): \(.status) (tokens: \(.tokens_used))"' orchestration-state.json
total_tokens=$(jq '[.changes[].tokens_used] | add // 0' orchestration-state.json)
info "Total tokens: $total_tokens"

echo ""
if [[ "$first_change_status" == "merged" || "$first_change_status" == "done" ]]; then
    success "E2E test passed: change completed the orchestration lifecycle"
else
    error "E2E test incomplete: change status is '$first_change_status'"
    exit 1
fi
