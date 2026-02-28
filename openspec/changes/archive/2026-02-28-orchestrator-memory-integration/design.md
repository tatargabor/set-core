## Context

The orchestrator (`wt-orchestrate`) manages multi-change workflows: planning decomposition from a spec/brief, dispatching changes to worktrees with Ralph loops, monitoring progress, running tests, reviewing code, and merging. While agents inside worktrees have full memory integration via hooks (SessionStart recall, PostToolUse recall, Stop extraction), the orchestrator layer itself has minimal memory usage — one generic recall during planning and nothing else.

Key functions and their current memory status:
- `cmd_plan()` — single generic recall: `"project architecture and features"`
- `dispatch_change()` — writes proposal.md from plan scope only, no memory
- `auto_replan_cycle()` — reads spec + `_REPLAN_COMPLETED` env var, no memory
- `merge_change()` — logs success/conflict, no memory save
- `handle_change_done()` — runs tests, review; results stored in state JSON only, no memory save
- `poll_change()` — detects stall/stuck, no memory save

The shared shodh-memory database means all worktrees and the orchestrator can read/write the same memories. The `wt-memory` CLI is already on PATH for any project with memory enabled.

## Goals / Non-Goals

**Goals:**
- Save orchestrator operational events (merge outcomes, test results, review findings, stalls) as memories so future cycles can learn from them
- Enrich dispatched proposals with change-specific memory recall so agents start with relevant context
- Inform replanning with recalled orchestrator memories (past failures, conflicts) for better decomposition
- Use per-roadmap-item recall during planning for more targeted context

**Non-Goals:**
- Loop prompt memory injection (agent hooks already handle in-session recall)
- Modifying the hook system (wt-hook-memory) — that layer is complete
- Cross-worktree messaging via memory (agent-messaging handles this)
- Changing the memory tag schema beyond adding `source:orchestrator` variants

## Decisions

### **Choice**: Helper function `orch_remember` for all saves

All memory saves go through a single helper that checks `wt-memory` availability, formats tags consistently, and handles failures gracefully:

```bash
orch_remember() {
    local content="$1"
    local type="${2:-Learning}"
    local tags="$3"
    command -v wt-memory &>/dev/null || return 0
    echo "$content" | wt-memory remember --type "$type" --tags "source:orchestrator,$tags" 2>/dev/null || true
}
```

**Why:** Avoids repeating the availability check and tag prefix in every call site. The `|| true` ensures memory failures never break orchestration flow.

### **Choice**: Helper function `orch_recall` for all reads

```bash
orch_recall() {
    local query="$1"
    local limit="${2:-3}"
    local tags="${3:-source:orchestrator}"
    command -v wt-memory &>/dev/null || return 0
    wt-memory recall "$query" --limit "$limit" --tags "$tags" --mode hybrid 2>/dev/null | \
        jq -r '.[].content' 2>/dev/null | head -c 2000 || true
}
```

**Why:** Consistent recall interface with tag filtering. The `--tags source:orchestrator` default ensures orchestrator reads its own memories unless overridden. Character limit prevents huge context injection.

### **Choice**: Tag strategy `source:orchestrator,phase:<phase>,change:<name>`

Tags follow the pattern:
- `source:orchestrator` — always present, distinguishes from agent-generated memories
- `phase:merge` / `phase:test` / `phase:review` / `phase:plan` / `phase:dispatch` / `phase:replan` — which orchestrator phase generated this
- `change:<name>` — which change this relates to (when applicable)
- Type mapping: merge conflict → `Decision`, test failure → `Learning`, review outcome → `Learning`, successful merge → `Context`, plan context → `Context`

**Why:** Structured tags enable precise recall — replan can query `source:orchestrator,phase:merge` to find past merge conflicts; dispatch can query `change:<name>` to find everything about a specific change.

### **Choice**: Save at event time, not batch

Each event (merge conflict, test pass, review result) saves immediately when it happens, not in a batch at the end. This ensures memories are available even if the orchestrator crashes mid-cycle.

**Why:** The orchestrator runs long cycles (hours). Batching at cycle end risks losing all insights on crash. Individual saves also have clearer context.

### **Choice**: Dispatch recall uses change scope as query, not change name

When enriching proposal.md, the recall query uses the scope text (e.g., "GDPR email footer with unsubscribe link") rather than the kebab-case change name (e.g., "email-gdpr-footer"). The scope text produces better semantic matches.

**Why:** Change names are identifiers, not descriptions. Semantic recall works better with natural language queries.

### **Choice**: Replan injects memory as a dedicated section in the prompt

The `auto_replan_cycle()` function recalls orchestrator memories and injects them as a `## Orchestration History` section in the planning prompt, alongside the existing `_REPLAN_COMPLETED` context.

**Why:** Keeps memory context separate from spec content. The LLM can use it as advisory context without confusing it with requirements.

### **Choice**: Gate cost timing uses epoch milliseconds, not SECONDS builtin

Each gate step is timed with `$(date +%s%N) / 1000000` before/after, yielding millisecond precision. Results are stored per-change in state JSON as `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`.

**Why:** The bash `SECONDS` builtin only has 1-second resolution and is shared across the entire script. Millisecond-level `date +%s%N` gives meaningful data even for fast test runs.

### **Choice**: Retry token cost tracked via loop-state.json diff

When a retry is triggered, the current `total_tokens` from the worktree's `.claude/loop-state.json` is snapshotted as `retry_tokens_start`. When the change comes back through `handle_change_done()` after the retry, the diff is computed and accumulated in `gate_retry_tokens`.

**Why:** Ralph loop tracks tokens per iteration in loop-state.json. The diff between pre-retry and post-retry snapshots gives exact retry cost without modifying wt-loop.

### **Choice**: Gate costs stored flat in change state, not nested

Instead of a `gate_costs: {}` sub-object (which complicates jq updates), gate fields are stored flat: `gate_test_ms`, `gate_review_ms`, `gate_verify_ms`, `gate_retry_tokens`, `gate_retry_count`, `gate_total_ms`. Aggregation computed on read.

**Why:** `update_change_field` uses `jq --arg` on flat paths. Nested objects would require different jq syntax for each update. Flat fields are simpler and consistent with existing `test_result`, `review_result` etc.

### **Choice**: cmd_status gate column shows compact format

Gate cost in the status table is shown as `23.7s` (total gate time) with retry info like `+45k tok, 1 retry` on the same line. Keeps the table scannable.

**Why:** Operators glance at status output during long runs. Compact format prevents table width explosion while still surfacing the key cost data.

## Risks / Trade-offs

**[Latency]** Each recall adds ~100-200ms per `wt-memory` CLI invocation. Planning has 1 recall per roadmap item (typically 3-8 items), dispatch has 1, replan has 1. Total added latency: ~0.5-2s per cycle.
→ Acceptable given cycles run for minutes/hours. All recalls are `|| true` so timeouts don't block.

**[Memory volume]** Active orchestration generates ~5-15 memories per cycle (one per merge/test/review event). Over many cycles, this accumulates.
→ The existing dedup and cleanup mechanisms handle this. Tags enable targeted pruning if needed.

**[Stale context]** Memories from old cycles may provide outdated advice (e.g., "X conflicts with Y" when Y has since been refactored).
→ Acceptable risk. Temporal decay in shodh-memory scoring naturally deprioritizes older memories. The LLM can judge relevance.

**[Dispatch proposal bloat]** Adding memory context to proposal.md increases its size. Large proposals slow down the agent's first read.
→ Mitigated by limiting recalled content to 1000 chars and placing it in a clearly marked section that the agent can skim.
