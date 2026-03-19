#!/usr/bin/env bash
# lib/orchestration/orch-memory.sh — Memory helpers (remember, recall, audit, gate stats)
# Sourced by bin/set-orchestrate after state.sh

orch_remember() {
    local content="$1"
    local type="${2:-Learning}"
    local tags="$3"
    command -v set-memory &>/dev/null || return 0
    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))
    echo "$content" | set-memory remember --type "$type" --tags "source:orchestrator${tags:+,$tags}" 2>/dev/null || true
    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))
    _MEM_OPS_COUNT=$((_MEM_OPS_COUNT + 1))
    _MEM_OPS_TOTAL_MS=$((_MEM_OPS_TOTAL_MS + elapsed_ms))
    log_info "Memory save: ${elapsed_ms}ms (type=$type, tags=source:orchestrator${tags:+,$tags})"
}

# Recall memories with optional tag filtering.
# Usage: orch_recall "query" [limit] [tags]
orch_recall() {
    local query="$1"
    local limit="${2:-3}"
    local tags="${3:-source:orchestrator}"
    command -v set-memory &>/dev/null || return 0
    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))
    local cutoff_iso
    cutoff_iso=$(date -u -d '24 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || date -u -v-24H '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null || echo "1970-01-01T00:00:00Z")
    local result
    result=$(set-memory recall "$query" --limit "$limit" --tags "$tags" --mode hybrid 2>/dev/null | \
        jq -r --arg cutoff "$cutoff_iso" '[.[] | select(.tags // "" | test("stale:true") | not) | select(if (.tags // "" | test("volatile")) then ((.created_at // "9999") > $cutoff) else true end)] | .[].content' 2>/dev/null | head -c 2000 || true)
    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))
    local result_len=${#result}
    _MEM_RECALL_COUNT=$((_MEM_RECALL_COUNT + 1))
    _MEM_RECALL_TOTAL_MS=$((_MEM_RECALL_TOTAL_MS + elapsed_ms))
    log_info "Memory recall: ${elapsed_ms}ms, ${result_len} chars (query='${query:0:60}', limit=$limit)"
    echo "$result"
}

# Pre-decomposition memory hygiene — lightweight health check before planning.
# Best-effort: failure does not block planning.
plan_memory_hygiene() {
    command -v set-memory &>/dev/null || return 0

    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))

    # 1. Dedup dry-run — log duplicate count
    local dedup_output dedup_count=0
    dedup_output=$(set-memory dedup --dry-run 2>/dev/null || true)
    dedup_count=$(echo "$dedup_output" | grep -oE '[0-9]+ duplicates' | grep -oE '[0-9]+' || echo "0")

    # 2. Memory stats — total count
    local mem_count=0
    mem_count=$(set-memory list --limit 1 2>/dev/null | jq 'length' 2>/dev/null || echo "0")
    local stats_output
    stats_output=$(set-memory stats --json 2>/dev/null || true)
    local total_memories=0
    if [[ -n "$stats_output" ]]; then
        total_memories=$(echo "$stats_output" | jq -r '.total_memories // 0' 2>/dev/null || echo "0")
    fi

    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))

    log_info "Memory hygiene: ${elapsed_ms}ms — $total_memories memories, $dedup_count duplicates found (dry-run)"
    emit_event "MEMORY_HYGIENE" "" "{\"total\":$total_memories,\"duplicates\":$dedup_count,\"elapsed_ms\":$elapsed_ms}"
}

# Log cumulative memory stats. Called periodically from monitor loop.
orch_memory_stats() {
    local total_ops=$((_MEM_OPS_COUNT + _MEM_RECALL_COUNT))
    [[ "$total_ops" -eq 0 ]] && return 0
    local total_ms=$((_MEM_OPS_TOTAL_MS + _MEM_RECALL_TOTAL_MS))
    local avg_save_ms=0 avg_recall_ms=0
    [[ "$_MEM_OPS_COUNT" -gt 0 ]] && avg_save_ms=$((_MEM_OPS_TOTAL_MS / _MEM_OPS_COUNT))
    [[ "$_MEM_RECALL_COUNT" -gt 0 ]] && avg_recall_ms=$((_MEM_RECALL_TOTAL_MS / _MEM_RECALL_COUNT))
    log_info "Memory stats: ${total_ops} ops (${_MEM_OPS_COUNT} saves, ${_MEM_RECALL_COUNT} recalls), total ${total_ms}ms (save avg ${avg_save_ms}ms, recall avg ${avg_recall_ms}ms)"
    info "Memory: ${total_ops} ops, ${total_ms}ms total (save avg ${avg_save_ms}ms, recall avg ${avg_recall_ms}ms)"
}

# Periodic memory audit — check health + validate recent orchestrator memories.
orch_memory_audit() {
    command -v set-memory &>/dev/null || return 0

    local start_ms
    start_ms=$(($(date +%s%N) / 1000000))

    # 1. Health check
    if ! set-memory health &>/dev/null 2>&1; then
        log_error "Memory audit: set-memory health check FAILED"
        return 1
    fi

    # 2. Count orchestrator memories
    local orch_mems
    orch_mems=$(set-memory recall "orchestration" --limit 20 --tags "source:orchestrator" --mode hybrid 2>/dev/null | jq 'length' 2>/dev/null || echo "0")

    # 3. Spot-check: most recent orchestrator memory has content
    local latest_content
    latest_content=$(set-memory recall "orchestration" --limit 1 --tags "source:orchestrator" --mode hybrid 2>/dev/null | jq -r '.[0].content // ""' 2>/dev/null || true)
    local latest_len=${#latest_content}

    local elapsed_ms=$(( $(date +%s%N) / 1000000 - start_ms ))

    if [[ "$orch_mems" -eq 0 ]]; then
        log_info "Memory audit: OK (${elapsed_ms}ms) — no orchestrator memories yet"
    elif [[ "$latest_len" -lt 10 ]]; then
        log_warn "Memory audit: WARN (${elapsed_ms}ms) — $orch_mems memories exist but latest has only $latest_len chars"
    else
        log_info "Memory audit: OK (${elapsed_ms}ms) — $orch_mems orchestrator memories, latest: ${latest_content:0:80}..."
    fi
}

# Aggregate quality gate cost summary across all changes.
orch_gate_stats() {
    [[ ! -f "$STATE_FILENAME" ]] && return 0

    local total_gate_ms=0 total_retry_tokens=0 total_retry_count=0 changes_with_gate=0

    while IFS=$'\t' read -r name gate_ms retry_tok retry_cnt; do
        [[ -z "$name" || "$gate_ms" == "null" || "$gate_ms" == "0" ]] && continue
        total_gate_ms=$((total_gate_ms + gate_ms))
        total_retry_tokens=$((total_retry_tokens + ${retry_tok:-0}))
        total_retry_count=$((total_retry_count + ${retry_cnt:-0}))
        changes_with_gate=$((changes_with_gate + 1))
    done < <(jq -r '.changes[] | [.name, (.gate_total_ms // 0), (.gate_retry_tokens // 0), (.gate_retry_count // 0)] | @tsv' "$STATE_FILENAME" 2>/dev/null)

    [[ "$changes_with_gate" -eq 0 ]] && return 0

    local active_seconds
    active_seconds=$(jq -r '.active_seconds // 1' "$STATE_FILENAME")
    local active_ms=$((active_seconds * 1000))
    local gate_pct=0
    [[ "$active_ms" -gt 0 ]] && gate_pct=$((total_gate_ms * 100 / active_ms))

    local gate_secs=$((total_gate_ms / 1000))
    local retry_tok_k=$((total_retry_tokens / 1000))

    log_info "Gate stats: ${changes_with_gate} changes gated, total ${gate_secs}s (${gate_pct}% of active time), ${total_retry_count} retries (+${retry_tok_k}k tokens)"
    info "Quality Gate: ${gate_secs}s across ${changes_with_gate} changes (${gate_pct}% of active), ${total_retry_count} retries (+${retry_tok_k}k tokens)"
}

# ─── Subcommands: status, approve ────────────────────────────────────

