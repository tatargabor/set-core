## Why

The `wt-hook-memory-save` Stop hook fires on **every Claude response** (not just session end), causing PATH 1 (transcript extraction) to re-process the same transcript 20-30 times per session. Each call invokes Haiku LLM, creating near-duplicate memories. This results in memory store pollution (231/336 memories are hook-generated, many duplicates) and 23x higher cost than designed ($0.07 vs $0.003 per session).

## What Changes

- **Staging pattern**: Instead of saving extracted insights directly to `set-memory`, write them to a staging file (`.set-core/.staged-extract-{transcript-id}`). Each Stop event overwrites the same staging file, so only the latest (most complete) extraction persists.
- **Commit on next session**: When the hook detects a **different** transcript than the staged one, it commits the staged file's contents to `set-memory` and starts staging for the new transcript. Staged files older than 1 hour are also auto-committed (handles "last session in project" edge case).
- **Debounce**: Skip Haiku extraction if the staging file was written less than 5 minutes ago for the same transcript. This reduces Haiku calls from ~25/session to ~6-10/session.
- **Tests**: Add bash-based integration tests covering: staging write, commit-on-switch, debounce skip, stale commit, and no-duplicate-memories.

## Capabilities

### New Capabilities
- `save-hook-staging`: Staging + debounce mechanism for transcript extraction in wt-hook-memory-save, with integration tests

### Modified Capabilities

(none — the hook's external interface stays the same)

## Impact

- **File modified**: `bin/wt-hook-memory-save` (PATH 1 transcript extraction section)
- **Files created**: `tests/test_save_hook_staging.sh` (integration tests)
- **Marker files**: `.set-core/.staged-extract-*` (new staging files), `.set-core/.staged-extract-*.ts` (debounce timestamps)
- **No API changes**: Hook input/output contract unchanged
- **No dependency changes**: Still uses `claude` CLI with haiku, `set-memory remember`
