#!/usr/bin/env bash
# lib/orchestration/milestone.sh — Milestone checkpoint: tag, worktree, dev server, email
#
# Python implementation: lib/wt_orch/milestone.py
# This file contains thin wrappers that delegate to wt-orch-core milestone *
# Provides: run_milestone_checkpoint(), cleanup_milestone_servers(), cleanup_milestone_worktrees()

MILESTONE_WORKTREE_DIR=".claude/milestones"

# Run milestone checkpoint for a completed phase.
# Args: phase_number base_port max_worktrees [milestone_dev_server]
run_milestone_checkpoint() {
    # Migrated to: wt_orch/milestone.py run_milestone_checkpoint()
    local phase="$1"
    local base_port="${2:-3100}"
    local max_worktrees="${3:-3}"
    local milestone_dev_server="${4:-}"

    wt-orch-core milestone checkpoint \
        --phase "$phase" \
        --state "$STATE_FILENAME" \
        --base-port "$base_port" \
        --max-worktrees "$max_worktrees" \
        --dev-server "$milestone_dev_server" \
        2>/dev/null || {
        log_warn "Milestone checkpoint failed for phase $phase (non-blocking)"
    }
}

# Kill all milestone dev server processes
cleanup_milestone_servers() {
    # Migrated to: wt_orch/milestone.py cleanup_milestone_servers()
    [[ ! -f "$STATE_FILENAME" ]] && return 0
    wt-orch-core milestone cleanup-servers --state "$STATE_FILENAME" 2>/dev/null || true
}

# Remove all milestone worktrees
cleanup_milestone_worktrees() {
    # Migrated to: wt_orch/milestone.py cleanup_milestone_worktrees()
    [[ ! -d "$MILESTONE_WORKTREE_DIR" ]] && return 0
    wt-orch-core milestone cleanup-worktrees 2>/dev/null || true
}
