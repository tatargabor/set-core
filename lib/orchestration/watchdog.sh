#!/usr/bin/env bash
# lib/orchestration/watchdog.sh — Thin wrapper: logic lives in lib/set_orch/watchdog.py
#
# Sourced by bin/set-orchestrate for backward compatibility.
# All functions delegate to set-orch-core watchdog subcommands.
# Python implementation: lib/set_orch/watchdog.py, cli.py:cmd_watchdog()

# Per-change watchdog check. Called from Python engine.py via CLI.
watchdog_check() {
    local change_name="$1"
    local result
    result=$(set-orch-core watchdog check --state "$STATE_FILENAME" --change "$change_name" 2>/dev/null) || return 0
    local action
    action=$(echo "$result" | jq -r '.action // "ok"')
    case "$action" in
        warn)       emit_event "WATCHDOG_WARN" "$change_name" "$result" ;;
        restart)    resume_change "$change_name" || true ;;
        redispatch) redispatch_change "$change_name" "watchdog" ;;
        fail)
            _watchdog_salvage_partial_work "$change_name"
            update_change_field "$change_name" "status" '"failed"'
            send_notification "set-orchestrate" "Watchdog: '$change_name' failed" "critical"
            ;;
    esac
}

# watchdog_heartbeat() — removed, runs in Python via watchdog.py:heartbeat_data()

# Salvage partial work from a failing change's worktree.
_watchdog_salvage_partial_work() {
    local change_name="$1"
    local wt_path
    wt_path=$(jq -r --arg n "$change_name" '.changes[] | select(.name == $n) | .worktree_path // empty' "$STATE_FILENAME")
    [[ -z "$wt_path" || ! -d "$wt_path" ]] && return 0

    local diff_output
    diff_output=$(cd "$wt_path" && git diff HEAD 2>/dev/null || true)
    [[ -z "$diff_output" ]] && return 0

    local patch_file="$wt_path/partial-diff.patch"
    echo "$diff_output" > "$patch_file"

    local modified_files
    modified_files=$(cd "$wt_path" && git diff HEAD --name-only 2>/dev/null | jq -R -s 'split("\n") | map(select(length > 0))' || echo '[]')
    safe_jq_update "$STATE_FILENAME" --arg n "$change_name" --argjson files "$modified_files" --arg patch "$patch_file" \
        '(.changes[] | select(.name == $n)) |= (.partial_diff_patch = $patch | .partial_diff_files = $files)'

    local file_count
    file_count=$(echo "$modified_files" | jq 'length')
    log_info "Watchdog: salvaged partial work for $change_name ($file_count files)"
    emit_event "WATCHDOG_SALVAGE" "$change_name" "{\"files\":$file_count,\"patch\":\"$patch_file\"}"
}
