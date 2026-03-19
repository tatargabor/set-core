## Context

`wt-hook-memory-save` is a Claude Code Stop hook that fires after **every response**. PATH 1 (transcript-based extraction) calls Haiku LLM to extract insights, then saves them directly to `set-memory`. Since the Stop event fires ~25 times per session, the same transcript is processed repeatedly, creating near-duplicate memories (231/336 hook-generated) and wasting Haiku calls ($0.07 vs target $0.003/session).

The hook is a bash script at `bin/wt-hook-memory-save`. It already has:
- A lockfile mechanism to prevent concurrent extractions
- A background `&disown` pattern for async execution
- Dedup detection for agent-saved memories (`[Memory saved:` in transcript)
- PATH 2 (commit-based) with proper git-hash dedup

PATH 1 lacks any mechanism to avoid re-processing the same transcript.

## Goals / Non-Goals

**Goals:**
- Eliminate duplicate memories from repeated extraction of the same transcript
- Reduce Haiku LLM calls per session (from ~25 to ~6-10 with debounce)
- Ensure the **last** (most complete) extraction is the one that gets committed to memory
- Add integration tests verifying staging, commit, debounce, and edge cases

**Non-Goals:**
- Changing the Haiku → Sonnet model (staying with Haiku)
- Modifying PATH 2 (commit-based extraction — already has dedup)
- Changing the hook's external interface (stdin JSON, exit codes)
- Deduplicating existing memories already in the store

## Decisions

### Decision 1: Staging file pattern (overwrite, not append)

**Choice**: Write extraction results to `.set-core/.staged-extract-{transcript-basename}` instead of directly calling `set-memory remember`. Each extraction overwrites the previous staged file for the same transcript.

**Alternatives considered:**
- Per-memory dedup via `set-memory recall` before save → adds latency, complex, semantic matching unreliable
- Single-fire (extract only once per transcript) → loses content from later in the session
- Accumulate in file + dedup at commit → complex, still needs similarity matching

**Rationale**: The last extraction always sees the full transcript, so it's strictly superior to all prior extractions. Overwrite is simple and correct.

### Decision 2: Commit trigger — next-session detection

**Choice**: At the start of each hook invocation (before PATH 1 extraction), check for staged files from **other** transcripts. If found, commit those to `set-memory` and delete them. This means a session's staged extraction gets committed when the **next** session starts.

**Alternatives considered:**
- Timer/cron-based commit → external dependency, complexity
- Commit after N minutes of inactivity → can't detect inactivity from a Stop hook
- Commit on PATH 2 (commit-based) → couples the two paths unnecessarily

**Rationale**: Session switch is a natural commit point. The staged file ensures we always commit the latest extraction.

### Decision 3: Stale file auto-commit (1 hour threshold)

**Choice**: Staged files older than 1 hour are committed regardless, even if the transcript matches the current session. This handles the "last session in project" edge case.

**Rationale**: Without this, if a user never returns to the project, the staged extraction would be lost forever. 1 hour is generous enough to not trigger during normal sessions.

### Decision 4: Debounce via timestamp file

**Choice**: Write a timestamp to `.set-core/.staged-extract-{id}.ts` on each extraction. Before running Haiku, check if the timestamp is less than 5 minutes old — if so, skip the LLM call entirely.

**Alternatives considered:**
- File modification time of staged file → `stat` format differs across Linux/macOS
- Inline in the staged file → parsing complexity
- No debounce → works with staging but wastes Haiku calls

**Rationale**: Separate `.ts` file with epoch seconds is portable and simple. 5 minutes balances cost reduction with content freshness.

### Decision 5: Test approach — bash integration tests with mocked set-memory

**Choice**: Create `tests/test_save_hook_staging.sh` that tests the hook's staging logic by:
1. Mocking `set-memory` and `claude` CLI with shell functions/scripts
2. Creating fake transcript files with known content
3. Running the hook multiple times and asserting staged file state
4. Simulating session switch and asserting commit behavior

**Rationale**: The hook is a bash script — testing it with bash is the most natural approach. Mocking externals lets us test logic without API calls or real memory state.

## Risks / Trade-offs

- **[Lost staged file]** → If the process crashes between Haiku call and file write, the staged file is stale or missing. Mitigation: atomic write via `mv` from temp file.
- **[Never committed]** → User abandons project permanently. Mitigation: 1-hour stale auto-commit handles most cases. Ultimate fallback: data was never critical (it's just LLM-extracted insights).
- **[Debounce misses important content]** → A critical user correction at minute 3 won't trigger extraction until minute 5. Mitigation: 5 minutes is short; the correction will be captured in the next extraction cycle.
- **[Concurrent sessions]** → Two Claude sessions in same project simultaneously. Mitigation: existing lockfile mechanism prevents concurrent extraction; staged files are per-transcript so no collision.
