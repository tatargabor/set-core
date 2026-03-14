#!/usr/bin/env bash
# lib/orchestration/merger.sh — Merge, cleanup, archive operations
#
# The merge pipeline (merge_change, retry_merge_queue, smoke tests) runs in
# Python via lib/wt_orch/merger.py, called from the Python monitor loop.
#
# This file retains thin bash wrappers used by other bash code:
# - archive_change() — delegated to Python
# - cleanup_worktree() — used by bash callers (cmd_start recovery, etc.)
# - cleanup_all_worktrees() — delegated to Python

# ─── Archive (delegated to Python) ──────────────────────────────────

archive_change() {
    # Migrated to: wt_orch/merger.py archive_change()
    local change_name="$1"
    wt-orch-core merge archive --change "$change_name" 2>/dev/null || {
        log_warn "Failed to archive $change_name (non-blocking)"
    }
}

# ─── Worktree Cleanup ────────────────────────────────────────────────

_archive_worktree_logs() {
    local change_name="$1"
    local wt_path="$2"
    local logs_src="$wt_path/.claude/logs"
    [[ -d "$logs_src" ]] || return 0

    local archive_dir="wt/orchestration/logs/$change_name"
    mkdir -p "$archive_dir"
    cp -n "$logs_src"/*.log "$archive_dir/" 2>/dev/null || true
    local count
    count=$(find "$archive_dir" -name "*.log" 2>/dev/null | wc -l)
    log_info "Archived $count log files for $change_name to $archive_dir"
}

cleanup_worktree() {
    local change_name="$1"
    local wt_path="$2"

    # Archive agent logs before removing the worktree
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        _archive_worktree_logs "$change_name" "$wt_path"
    fi

    # Try wt-close first (handles both worktree removal and branch deletion)
    if wt-close "$change_name" 2>/dev/null; then
        log_info "Cleaned up worktree for $change_name"
        return 0
    fi

    # Fallback: manual cleanup if wt-close fails
    if [[ -n "$wt_path" && -d "$wt_path" ]]; then
        git worktree remove "$wt_path" --force 2>/dev/null || true
        log_info "Force-removed worktree $wt_path"
    fi

    local branch="change/$change_name"
    if git show-ref --verify --quiet "refs/heads/$branch" 2>/dev/null; then
        git branch -D "$branch" 2>/dev/null || true
        log_info "Deleted branch $branch"
    fi
}

cleanup_all_worktrees() {
    # Migrated to: wt_orch/merger.py cleanup_all_worktrees()
    wt-orch-core merge cleanup-all --state "$STATE_FILENAME" 2>/dev/null || {
        # Fallback: inline cleanup for backward compat
        log_info "Cleaning up worktrees for merged/done changes..."
        local cleaned=0
        while IFS= read -r line; do
            [[ -z "$line" ]] && continue
            local name wt_path status
            name=$(echo "$line" | jq -r '.name')
            wt_path=$(echo "$line" | jq -r '.worktree_path // empty')
            status=$(echo "$line" | jq -r '.status')
            [[ "$status" != "merged" && "$status" != "done" ]] && continue
            [[ -z "$wt_path" ]] && continue
            [[ ! -d "$wt_path" ]] && continue
            cleanup_worktree "$name" "$wt_path"
            cleaned=$((cleaned + 1))
        done < <(jq -c '.changes[]' "$STATE_FILENAME" 2>/dev/null)
        if [[ $cleaned -gt 0 ]]; then
            log_info "Cleaned up $cleaned worktree(s)"
            info "Cleaned up $cleaned worktree(s)"
        fi
    }

    # Clean up milestone servers and worktrees if milestones were used
    if type cleanup_milestone_servers &>/dev/null; then
        cleanup_milestone_servers
        cleanup_milestone_worktrees
    fi
}
