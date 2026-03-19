## Why

Benchmark v5 revealed 37% memory noise rate (up from v4's 15%) and missing tags on 31/83 memories. The root cause is `proactive_context(auto_ingest=True)` silently saving working-state strings as permanent `Conversation` memories, plus transcript extraction not including `change:` tags. These issues degrade recall precision and pollute the memory store.

## What Changes

- **Disable auto-ingest in proactive context**: Pass `auto_ingest=False` to `proactive_context()` in `set-memory proactive` command. Eliminates 21 noise entries (~25% of all memories).
- **Add change: tag to transcript extraction**: Ensure all hook-saved memories include `change:<name>` tag so they can be associated with specific changes during recall.
- **Add convention extraction to save hook**: After transcript extraction, scan the change definition for convention patterns ("use X utility", "all queries must Y") and save them as explicit Learning memories.
- **Improve code map safety net**: Make code-map generation unconditional (don't skip if commit-based detection misses the change) and scan all recent commits, not just the latest.
- **Fix TRAP-F in benchmark**: Add explicit coupon `currentUses` increment requirement to `07-stock-rethink.md` change definition.
- **Hook test script**: Isolated test for all hook fixes using temp memory storage — validates auto_ingest, tags, code-maps, convention extraction without running a full benchmark.
- **Pre-flight check**: Infrastructure validation script that catches misconfigurations (missing hooks, broken globs, port conflicts) before committing to a multi-hour benchmark run.
- **Single-change smoke test**: Run C01 end-to-end with memory, verify memory quality metrics before full 12-change run.

## Capabilities

### New Capabilities
- `convention-extraction`: Hook extracts convention patterns from change definitions and saves them as memories
- `benchmark-testing`: Hook test script, pre-flight check, and single-change smoke test for validating fixes before full benchmark runs

### Modified Capabilities
- `memory-save-hook`: Fix tag propagation, disable auto-ingest noise, improve code-map coverage

## Impact

- `bin/set-memory` — `cmd_proactive()` function (add `auto_ingest=False`)
- `bin/wt-hook-memory-save` — transcript extraction tags, convention extraction, code-map safety net
- `benchmark/changes/07-stock-rethink.md` — TRAP-F explicit requirement
