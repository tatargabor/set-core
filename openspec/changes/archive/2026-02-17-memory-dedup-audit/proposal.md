## Why

Memory hooks (especially transcript extraction) fire multiple times per session, creating near-duplicate memories. Currently 348 memories with ~5.7% redundancy (13 duplicate clusters, 20 redundant entries). Without periodic maintenance this compounds over time, polluting vector search results. There's no way to assess memory health or clean up duplicates — `set-memory cleanup` only handles low-importance entries, not semantic duplicates.

## What Changes

- Add `set-memory audit` command that reports memory health: total count, duplicate clusters (exact + near), largest clusters, and optionally flags potential contradictions
- Add `set-memory dedup` command that removes duplicate memories, keeping the best entry per cluster (highest access count, importance, most detail). Supports `--dry-run`, `--interactive`, and configurable `--threshold`
- Dedup resolution merges tags from all cluster members into the survivor before deleting others (using delete+recreate since shodh has no update API)

## Capabilities

### New Capabilities
- `memory-dedup`: Duplicate detection and removal for set-memory, including audit reporting, interactive review, and automatic dedup with configurable similarity threshold

### Modified Capabilities
- `memory-cli`: Adding two new subcommands (`audit`, `dedup`) to the existing CLI

## Impact

- `bin/set-memory`: New `cmd_audit` and `cmd_dedup` functions added to the CLI script
- Uses Python + `difflib.SequenceMatcher` for similarity computation (already available, no new dependencies)
- No breaking changes — purely additive commands
