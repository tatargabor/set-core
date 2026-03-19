## Context

The shodh-memory audit revealed we use ~35% of the Python API surface. The `set-memory` CLI (`bin/set-memory`) is a bash script that invokes inline Python via `run_shodh_python`. The `cmd_remember()` function passes only 3 of 7 available `remember()` parameters. The `cmd_recall()` function uses `recall()` but never exposes `proactive_context()` or `recall_by_tags()`. The recall hook (`bin/wt-hook-memory-recall`) builds change-specific queries manually, which `proactive_context()` could replace with relevance-scored automatic retrieval.

Confirmed working during audit: `proactive_context()` returns results in ~84ms with `relevance_score` (float) and `relevance_reason` (string). The import code (`cmd_import`, line 786-794) already demonstrates passing the full API surface (entities, metadata, is_failure, is_anomaly).

## Goals / Non-Goals

**Goals:**
- Expose `proactive_context()` as `set-memory proactive` command
- Extend `remember` with `--metadata`, `--failure`, `--anomaly` flags
- Extend `recall` with `--tags-only` and `--min-importance` options
- Add `stats` and `cleanup` commands for memory quality maintenance
- Upgrade recall hook to use proactive instead of recall

**Non-Goals:**
- Changing the storage backend or project resolution logic
- Fixing the empty knowledge graph (NER requires server mode, out of scope)
- Exposing `record_decision()` or `reinforce()` APIs (deferred to future change)
- Changing the 4-layer hook architecture
- Adding entities parameter to remember CLI (NER doesn't populate graph in library mode, so manual entities have limited value)

## Decisions

### D1: Inline Python pattern for new commands
**Decision**: Follow the existing pattern of inline Python via `run_shodh_python -c "..."` with env vars for data passing.
**Rationale**: Consistency with all existing commands. Avoids introducing a separate Python script layer. The import code already proves this pattern works for the full API surface.
**Alternatives**: (a) Separate Python module — rejected because it adds a dependency management layer for a simple CLI. (b) REST API — rejected because set-memory uses the library directly, not the server.

### D2: proactive_context() as primary recall for hooks
**Decision**: Replace `set-memory recall` with `set-memory proactive` in the recall hook. Keep the change-context mapping (stock-rethink → "revising shopping-cart...") but pass it as conversation context to proactive_context() instead of as a recall query.
**Rationale**: proactive_context() was designed for exactly this use case — auto-surfacing relevant memories from conversation context. It returns relevance scores, enabling the hook to filter low-relevance noise (score < 0.3).
**Alternatives**: (a) Keep recall + add proactive as separate command only — rejected because the hook is the primary consumer and benefits most. (b) Use proactive everywhere immediately — rejected because recall is still useful for direct searches from skill hooks.

### D3: Fallback strategy for unavailable APIs
**Decision**: Each new command checks for the API method with `hasattr(m, 'method_name')` and falls back gracefully: proactive→recall(hybrid), recall_by_tags→recall(tags=...), forget_by_importance→list+filter+forget.
**Rationale**: Different shodh-memory versions may not have all methods. Graceful fallback preserves the CLI's "never break" contract. Warnings go to the log file, not stdout (preserving JSON output contracts).

### D4: Stats computed client-side from list_memories()
**Decision**: The `stats` command calls `list_memories()` to get all records, then computes distributions in Python. It also calls `get_stats()` for total count.
**Rationale**: No single shodh-memory API returns all the diagnostic data we want (type/tag/importance distributions). `list_memories()` returns all fields needed. For <500 memories this is fast enough. `get_stats()` provides the official total_memories count.
**Alternatives**: (a) Use `get_stats()` alone — rejected because it only returns total count, not distributions. (b) Add custom shodh-memory API — rejected as out of scope.

### D5: cleanup uses forget_by_importance when available, else client-side filter
**Decision**: Try `forget_by_importance(threshold)` first. If not available (AttributeError), fall back to listing all memories, filtering by importance, and calling `forget(id)` for each.
**Rationale**: `forget_by_importance()` is more efficient (single Rust call). The fallback ensures the command works on any shodh-memory version. Both paths produce the same result.

### D6: --metadata passed as raw JSON string, validated client-side
**Decision**: `--metadata` accepts a JSON string. The bash layer passes it as an env var. The inline Python layer does `json.loads()` and validates it's a dict before passing to `remember()`.
**Rationale**: Consistent with how tags are already passed (JSON via env var). Client-side validation avoids cryptic Python errors from the library.

## Risks / Trade-offs

- **[Risk] proactive_context() relevance scores may vary**: The API is relatively new. Relevance thresholds (e.g., filtering < 0.3) may need tuning.
  → Mitigation: Make the threshold a parameter, not hardcoded in the hook.

- **[Risk] Stats computation scales linearly with memory count**: For projects with >1000 memories, `list_memories()` could be slow.
  → Mitigation: Acceptable for now. 500 memories takes <100ms. Can optimize later with server-side aggregation.

- **[Trade-off] Hook upgrade changes recall behavior**: The proactive_context API may return different memories than the current carefully-tuned change-specific queries.
  → Mitigation: The change-context strings still guide proactive_context(). The relevance_score filter removes noise. Can always revert the hook independently.

- **[Risk] --metadata JSON parsing in bash**: Shell quoting of JSON is error-prone.
  → Mitigation: Pass via env var (already proven pattern). Python-side validation with clear error message on parse failure.
