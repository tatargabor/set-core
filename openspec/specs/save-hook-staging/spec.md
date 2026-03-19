# save-hook-staging Specification

## Purpose
Staging and debounce mechanism for wt-hook-memory-save transcript extraction, preventing duplicate memories by writing to staging files and committing on session switch.

## Removed

### Requirement: Staging file write instead of direct memory save
**Reason**: Raw filter saves directly to set-memory (no LLM to debounce). Staging files are no longer needed.
**Migration**: The new raw filter in `_stop_extract_from_transcript()` calls `set-memory remember` directly. Any existing staged files from previous Haiku sessions are committed as a one-time migration during the first Stop event after upgrade.

### Requirement: Commit staged extractions on session switch
**Reason**: No staging files to commit. Direct save eliminates the two-phase commit pattern.
**Migration**: One-time migration commits all existing `.set-core/.staged-extract-*` files, then the staging logic is removed.

### Requirement: Stale staged file auto-commit
**Reason**: No staging files exist in the new flow.
**Migration**: Handled by the one-time migration described above.

### Requirement: Debounce extraction via timestamp
**Reason**: Raw filter runs in <100ms with no LLM cost. Debounce was only needed to avoid redundant Haiku calls. The existing per-transcript dedup (checking if same transcript was already processed) is sufficient.
**Migration**: The `.ts` timestamp files and 5-minute debounce check are removed. Dedup is handled by checking if the transcript ID was already processed in this session (lightweight check).
