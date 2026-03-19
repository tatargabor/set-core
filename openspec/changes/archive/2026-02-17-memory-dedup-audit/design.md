## Context

`set-memory` has 348+ memories accumulated over benchmark runs and development sessions. Hooks (especially transcript extraction on Stop events) create near-duplicate memories. The existing `cleanup` command only removes low-importance entries — there's no way to detect or remove semantic duplicates, and no health audit command.

The shodh-memory Rust engine uses MiniLM-L6 embeddings (384-dim) for recall, but these embeddings are not exposed for pairwise comparison via CLI. The Python API (`Memory.list_memories()`) returns content strings, so similarity must be computed in Python using `difflib.SequenceMatcher`.

All commands follow the established `cmd_*` pattern in `bin/set-memory`: bash function wrapping an inline Python script run via `run_with_lock run_shodh_python -c "..."`, passing parameters through environment variables.

## Goals / Non-Goals

**Goals:**
- `set-memory audit` — diagnostic report showing total count, duplicate clusters, redundant entry count, and the largest clusters
- `set-memory dedup` — remove duplicate memories with configurable similarity threshold, dry-run mode, and interactive mode
- Dedup resolution keeps the "best" memory per cluster (highest access_count, importance, longest content) and merges tags from deleted entries into the survivor
- `--interactive` mode presents each cluster for user confirmation before deleting

**Non-Goals:**
- Contradiction detection (shodh handles via recency-weighted recall; manual review is sufficient for now)
- Using vector embeddings for similarity (would require exposing cosine similarity from the Rust engine — too much for this change)
- Automatic scheduled dedup (user-triggered only)

## Decisions

### D1: Similarity algorithm — SequenceMatcher at 75% threshold

Use `difflib.SequenceMatcher.ratio()` for pairwise similarity. Default threshold: 0.75 (75%).

**Why not vector cosine similarity?** The shodh-memory Python bindings don't expose raw embeddings or pairwise similarity. Adding that would require changes to the Rust engine. SequenceMatcher is available in stdlib, handles the near-duplicate case well (reformulated sentences, minor word changes), and our earlier analysis confirmed it catches the real duplicates.

**Why 75%?** At 75%, we caught 13 clusters / 20 redundant entries in production data. At 70%, it went to 31 pairs with some false positives. 75% is a good default; the `--threshold` flag lets users tune it.

### D2: Union-find clustering for scalability

Pairwise comparison is O(n²) which is fine for hundreds of memories but not thousands. Use union-find to cluster similar memories transitively. This groups `A~B` and `B~C` into one cluster `{A,B,C}` even if `A` and `C` are below threshold individually.

For current scale (~350 memories), this runs in under 2 seconds. If scale grows significantly, we can add a `--limit` to only process recent memories.

### D3: Survivor selection — multi-factor scoring

For each cluster, keep the memory with the highest composite score:
1. `access_count` (higher = more useful)
2. `importance` (higher = more valuable)
3. `len(content)` (longer = more detailed)

Tiebreaker: most recent `created_at`.

### D4: Tag merging via delete+recreate

Shodh-memory has no `update()` method. To merge tags from deleted cluster members into the survivor, we must `forget(survivor_id)` and `remember()` with the merged tag set. The new memory gets a fresh UUID but preserves content, type, and merged tags.

### D5: Interactive mode uses stdin prompts

`--interactive` shows each cluster with numbered entries and asks `[k]eep best / [s]kip / [q]uit`. This works in terminal but not in piped/non-interactive contexts. The command detects `isatty(stdin)` and falls back to dry-run if not interactive.

### D6: Audit output — human-readable by default, `--json` for machine

`set-memory audit` prints a formatted report by default. With `--json`, outputs a structured JSON object for scripting.

## Risks / Trade-offs

- **[O(n²) pairwise comparison]** → Acceptable for <1000 memories. Add `--limit` later if needed.
- **[SequenceMatcher misses semantic duplicates]** → "fires on every Stop event" vs "fires ~25x per session" might score <75%. These are caught at lower thresholds. Users can tune `--threshold`.
- **[Tag merge recreates memory with new ID]** → Breaks any external references to the old ID. Acceptable since nothing references memory IDs externally.
- **[Interactive mode requires terminal]** → Falls back gracefully to dry-run when stdin is not a TTY.
