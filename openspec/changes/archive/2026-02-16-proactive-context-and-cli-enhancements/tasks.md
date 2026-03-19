## 1. Extended remember command

- [x] 1.1 Add `--metadata`, `--failure`, `--anomaly` flag parsing to `cmd_remember()` argument loop
- [x] 1.2 Pass metadata (JSON string → dict via env var), is_failure, is_anomaly to the inline Python `m.remember()` call
- [x] 1.3 Add JSON validation for `--metadata` with clear error message on invalid input

## 2. Extended recall command

- [x] 2.1 Add `--tags-only` and `--min-importance` flag parsing to `cmd_recall()` argument loop
- [x] 2.2 Implement `--tags-only` path: call `recall_by_tags()` with hasattr fallback to `recall(tags=...)`
- [x] 2.3 Implement `--min-importance` post-filter: filter results where importance < threshold

## 3. Proactive context command

- [x] 3.1 Add `cmd_proactive()` function calling `proactive_context()` with context string and limit
- [x] 3.2 Add hasattr fallback to `recall(mode='hybrid')` when proactive_context is unavailable
- [x] 3.3 Register `proactive` in main dispatch and update usage text

## 4. Stats command

- [x] 4.1 Add `cmd_stats()` function: call `list_memories()` + `get_stats()`, compute type/tag/importance distributions in Python
- [x] 4.2 Support `--json` flag for machine-readable output, human-readable default
- [x] 4.3 Register `stats` in main dispatch and update usage text

## 5. Cleanup command

- [x] 5.1 Add `cmd_cleanup()` function: try `forget_by_importance(threshold)`, fallback to list+filter+forget loop
- [x] 5.2 Support `--threshold` (default 0.2) and `--dry-run` flags
- [x] 5.3 Register `cleanup` in main dispatch and update usage text

## 6. Hook upgrade

- [x] 6.1 Replace `set-memory recall "$QUERY" --limit 8 --mode hybrid` with `set-memory proactive "<context>" --limit 8` in wt-hook-memory-recall
- [x] 6.2 Build proactive context string from change name + revision notes + REREAD_FILES context
- [x] 6.3 Add relevance_score filtering (< 0.3) in the Python formatting block
- [x] 6.4 Add fallback: if `set-memory proactive` exits non-zero, fall back to `set-memory recall` (preserves current behavior)
