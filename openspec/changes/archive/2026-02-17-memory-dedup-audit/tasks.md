## 1. Core Dedup Engine (shared Python logic)

- [x] 1.1 Add inline Python function for pairwise SequenceMatcher similarity + union-find clustering (used by both audit and dedup)
- [x] 1.2 Add survivor selection logic: composite score (access_count * 10 + importance * 5 + len(content) / 100), tiebreak by created_at
- [x] 1.3 Add tag merge logic: union of all tags in cluster, delete+recreate survivor with merged tags

## 2. Audit Command

- [x] 2.1 Add `cmd_audit` function to `bin/set-memory` with `--threshold` (default 0.75) and `--json` flags
- [x] 2.2 Human-readable output: total, clusters, redundant, unique, dedup ratio, top clusters with previews
- [x] 2.3 JSON output mode: structured object with `total`, `clusters`, `redundant`, `unique`, `dedup_ratio`, `top_clusters`
- [x] 2.4 Graceful degradation: exit 0 with empty output if shodh-memory not installed

## 3. Dedup Command

- [x] 3.1 Add `cmd_dedup` function to `bin/set-memory` with `--threshold`, `--dry-run`, and `--interactive` flags
- [x] 3.2 Dry-run mode: print what would be deleted without modifying store
- [x] 3.3 Interactive mode: show cluster details, prompt `[k]eep/[s]kip/[q]uit` per cluster, detect TTY fallback
- [x] 3.4 Execute mode: delete redundant memories, merge tags into survivor, print JSON summary
- [x] 3.5 Graceful degradation: exit 0 with `{"deleted_count": 0}` if shodh-memory not installed

## 4. CLI Integration

- [x] 4.1 Add `audit` and `dedup` to main dispatch (`case` statement) in `bin/set-memory`
- [x] 4.2 Add `audit` and `dedup` to usage text under Diagnostics section
