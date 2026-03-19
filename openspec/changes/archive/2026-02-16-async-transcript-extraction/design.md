## Context

`wt-hook-memory-save` is a Claude Code Stop hook that extracts insights from session transcripts using haiku LLM. Currently it runs synchronously, blocking the next user interaction for 5-15 seconds. The commit-based path (Path 2) is fast (<1s) and stays synchronous.

## Goals / Non-Goals

**Goals:**
- Eliminate blocking on transcript extraction (haiku call)
- Prevent concurrent extraction runs (lockfile)
- Clean up temp files reliably

**Non-Goals:**
- Changing the extraction prompt or logic
- Adding Ollama/local model support (separate change)
- Making Path 2 (commit-based) async (it's already fast)

## Decisions

### Fork before extraction
**Choice**: Use `&` + `disown` to background the entire `extract_from_transcript` call, wrapped in a helper that handles lockfile and cleanup.

**Rationale**: Simplest approach. The extraction function is self-contained — it reads the transcript, calls haiku, saves memories. No shared state with Path 2.

### Lockfile to prevent concurrent runs
**Choice**: Use `.set-core/.transcript-extraction.lock` with PID check. If lock exists and PID is alive, skip. Otherwise, take lock.

**Rationale**: wt-loop iterations can be fast — if extraction from iter N is still running when iter N+1's Stop hook fires, we don't want two haiku calls competing. A lockfile with PID validation handles stale locks from crashed processes.

### Temp file cleanup in background process
**Choice**: The backgrounded process owns its own tmpfile and cleans up via trap on exit.

**Rationale**: The current `trap "rm -f $tmpfile" EXIT` on the main script would fire when the hook exits (immediately), not when extraction finishes. Moving cleanup into the background function ensures it happens at the right time.

## Risks / Trade-offs

- **Memory writes may lag by a few seconds**: The next iteration starts before memories are saved. For recall hooks that fire on the NEXT user prompt, this is fine — the extraction should complete well before the next Stop event.
- **Lockfile stale detection**: If bash crashes without cleanup, the lockfile persists. PID check mitigates this — if the PID is dead, the lock is stale and gets overwritten.
- **Log visibility**: Background process errors are harder to debug. We'll redirect stderr to `.set-core/transcript-extraction.log`.
