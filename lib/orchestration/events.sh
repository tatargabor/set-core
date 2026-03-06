#!/usr/bin/env bash
# lib/orchestration/events.sh — Append-only event log for orchestration audit trail
#
# Sourced by bin/wt-orchestrate. All functions run in the orchestrator's global scope.
# Must be sourced FIRST — other modules emit events.

# ─── Event Configuration ─────────────────────────────────────────────

EVENTS_LOG_FILE=""           # Set by init after STATE_FILENAME is resolved
EVENTS_MAX_SIZE=1048576      # 1MB default rotation threshold
EVENTS_ENABLED=true          # Toggled by events_log directive
EVENTS_POLL_COUNT=0          # Tracks polls for periodic rotation check

# ─── Core Event Emission ─────────────────────────────────────────────

# Emit a structured event to the JSONL log.
# Usage: emit_event "TYPE" "change_name" '{"key":"value"}'
#   change_name can be "" for orchestrator-level events
emit_event() {
    [[ "$EVENTS_ENABLED" != "true" ]] && return 0

    local type="$1"
    local change_name="${2:-}"
    local data="${3:-{}}"
    local ts
    ts=$(date -Iseconds)

    # Lazy init: derive log path from STATE_FILENAME
    if [[ -z "$EVENTS_LOG_FILE" ]]; then
        if [[ -n "${STATE_FILENAME:-}" ]]; then
            EVENTS_LOG_FILE="${STATE_FILENAME%.json}-events.jsonl"
        else
            EVENTS_LOG_FILE="orchestration-events.jsonl"
        fi
    fi

    # Build JSON line
    local json_line
    if [[ -n "$change_name" ]]; then
        json_line=$(jq -cn \
            --arg ts "$ts" \
            --arg type "$type" \
            --arg change "$change_name" \
            --argjson data "$data" \
            '{ts:$ts, type:$type, change:$change, data:$data}')
    else
        json_line=$(jq -cn \
            --arg ts "$ts" \
            --arg type "$type" \
            --argjson data "$data" \
            '{ts:$ts, type:$type, data:$data}')
    fi

    echo "$json_line" >> "$EVENTS_LOG_FILE"

    # Periodic rotation check (every 100 emissions)
    EVENTS_POLL_COUNT=$((EVENTS_POLL_COUNT + 1))
    if (( EVENTS_POLL_COUNT % 100 == 0 )); then
        rotate_events_log
    fi
}

# ─── Event Log Rotation ──────────────────────────────────────────────

# Archive events log when it exceeds EVENTS_MAX_SIZE. Keep last 3 archives.
rotate_events_log() {
    [[ -z "$EVENTS_LOG_FILE" || ! -f "$EVENTS_LOG_FILE" ]] && return 0

    local size
    size=$(stat -c %s "$EVENTS_LOG_FILE" 2>/dev/null || stat -f %z "$EVENTS_LOG_FILE" 2>/dev/null || echo 0)

    if [[ "$size" -gt "$EVENTS_MAX_SIZE" ]]; then
        local archive_name="${EVENTS_LOG_FILE%.jsonl}-$(date +%Y%m%d%H%M%S).jsonl"
        mv "$EVENTS_LOG_FILE" "$archive_name"
        touch "$EVENTS_LOG_FILE"
        log_info "Events log rotated: $archive_name ($size bytes)"

        # Keep only last 3 archives
        local base_pattern="${EVENTS_LOG_FILE%.jsonl}-"
        local archives
        archives=$(ls -1t "${base_pattern}"*.jsonl 2>/dev/null | tail -n +4)
        if [[ -n "$archives" ]]; then
            echo "$archives" | xargs rm -f
        fi
    fi
}

# ─── Event Query ──────────────────────────────────────────────────────

# Query events from the log. Called by cmd_events().
# Args: [--type TYPE] [--change NAME] [--since TIMESTAMP] [--last N] [--json]
query_events() {
    [[ -z "$EVENTS_LOG_FILE" || ! -f "$EVENTS_LOG_FILE" ]] && return 0

    local filter_type="" filter_change="" filter_since="" last_n="" json_mode=false

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --type)    filter_type="$2"; shift 2 ;;
            --change)  filter_change="$2"; shift 2 ;;
            --since)   filter_since="$2"; shift 2 ;;
            --last)    last_n="$2"; shift 2 ;;
            --json)    json_mode=true; shift ;;
            *)         shift ;;
        esac
    done

    local jq_filter="."
    [[ -n "$filter_type" ]] && jq_filter="$jq_filter | select(.type == \"$filter_type\")"
    [[ -n "$filter_change" ]] && jq_filter="$jq_filter | select(.change == \"$filter_change\")"
    [[ -n "$filter_since" ]] && jq_filter="$jq_filter | select(.ts >= \"$filter_since\")"

    local events
    if [[ -n "$last_n" ]]; then
        events=$(tail -n "$last_n" "$EVENTS_LOG_FILE" | jq -c "$jq_filter" 2>/dev/null)
    else
        events=$(jq -c "$jq_filter" "$EVENTS_LOG_FILE" 2>/dev/null)
    fi

    if $json_mode; then
        echo "$events" | jq -s '.'
    else
        # Formatted table output
        if [[ -z "$events" ]]; then
            echo "No events found."
            return 0
        fi
        printf "%-25s %-20s %-25s %s\n" "Timestamp" "Type" "Change" "Data"
        printf "%-25s %-20s %-25s %s\n" "─────────────────────────" "────────────────────" "─────────────────────────" "────"
        echo "$events" | while IFS= read -r line; do
            local ts type change data
            ts=$(echo "$line" | jq -r '.ts // ""')
            type=$(echo "$line" | jq -r '.type // ""')
            change=$(echo "$line" | jq -r '.change // "-"')
            data=$(echo "$line" | jq -c '.data // {}')
            printf "%-25s %-20s %-25s %s\n" "${ts:0:25}" "$type" "$change" "$data"
        done
    fi
}

# ─── cmd_events subcommand ────────────────────────────────────────────

cmd_events() {
    # Lazy init events log path
    if [[ -z "$EVENTS_LOG_FILE" && -n "${STATE_FILENAME:-}" ]]; then
        EVENTS_LOG_FILE="${STATE_FILENAME%.json}-events.jsonl"
    fi

    if [[ ! -f "$EVENTS_LOG_FILE" ]]; then
        info "No events log found."
        return 0
    fi

    query_events "$@"
}
