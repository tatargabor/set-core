# Design: Memory Hook Optimization

## Context

The hook pipeline (`lib/set_hooks/`) has 5 active injection layers. Telemetry from production runs shows:
- 36,587 PostToolUse recalls vs 8,829 proactive calls — PostToolUse is 80% of volume
- PostToolUse queries are often garbage (task IDs, shell commands) yielding irrelevant results
- Same content injected repeatedly under different MEM# IDs
- ~48% of agent session tokens consumed by memory injection

All changes are in `lib/set_hooks/` (Layer 1 core). No module changes needed.

## Goals / Non-Goals

**Goals:**
- Reduce memory injection token overhead by 50-70%
- Make hook aggressiveness configurable without code changes
- Preserve useful injections (session context, known error fixes)
- Enable data-driven tuning via hit-rate metrics
- Testable before deploying to production E2E runs

**Non-Goals:**
- Changing the shodh-memory recall algorithm or embedding model
- Modifying the Stop hook pipeline (transcript extraction is unaffected)
- Building a UI for memory metrics (metrics are JSONL files, analyzed offline)

## Decisions

### D1: Default to `lite` mode, not `full`

PostToolUse (Read/Bash) fires on every tool call — highest volume, lowest value. Disabling it by default eliminates 80% of recall calls.

**Alternative considered:** Keep PostToolUse but raise its relevance threshold higher (0.7+). Rejected because the queries themselves are garbage (bash command strings), so even perfect relevance scoring can't help.

**Alternative considered:** Smart query extraction (only recall for meaningful file paths, skip shell commands). Too complex for the benefit — PostToolUse is rarely useful even with good queries.

### D2: Content-hash dedup, not prefix dedup

Current dedup uses `c[:50]` as key — but the same memory content can arrive with different formatting or whitespace. Use `hashlib.md5(content[:100])` for more robust matching. Track seen content hashes in session cache alongside existing dedup keys.

### D3: Token budget per hook, not per memory

A per-memory cap (truncation to 300 chars) plus a per-hook cap (800 tokens) provides two-layer protection. The per-memory cap keeps individual entries readable; the per-hook cap prevents 3 large memories from flooding the context.

### D4: Env var, not config file

`SET_MEMORY_HOOKS=lite|full|off` is simplest to set per-session or per-orchestration-run. No need for a config file — the hook system already reads env vars for debug mode.

### D5: Test harness via unit tests + dry-run log analysis

Unit tests: mock the daemon client, feed synthetic memories, assert output size/format.
Integration test: replay hook log entries through the new pipeline, compare before/after token estimates.

## Risks / Trade-offs

- **[Risk] Useful PostToolUse context lost in lite mode** → Mitigation: Users can set `SET_MEMORY_HOOKS=full` to restore. Hit-rate metrics will show if this matters.
- **[Risk] Relevance threshold 0.55 too aggressive** → Mitigation: Tunable constant, easy to adjust. Current 0.3 allows clearly garbage through.
- **[Risk] Token budget 800 too low for complex topics** → Mitigation: 800 tokens ≈ 3 memories × ~250 tokens each. Adequate for context hints; full details should come from explicit recall, not automatic injection.

## Open Questions

None — the explore session and log analysis provided sufficient data for all decisions.
