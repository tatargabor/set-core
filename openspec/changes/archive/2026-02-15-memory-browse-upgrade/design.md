## Context

The Memory Browse dialog (`gui/dialogs/memory_dialog.py`) opens with `_load_all()` which runs `set-memory list` → returns ALL memories as JSON → renders one QFrame card per memory. This is O(n) on both data and widgets.

Shodh-memory v0.1.75 added two APIs we can leverage:
- `list_memories(limit=N, memory_type=None)` — paginated listing
- `context_summary(max_items=5, include_decisions=True, include_learnings=True, include_context=True)` — condensed category overview

The CLI wrapper `bin/set-memory` currently has no `--limit` flag on `list` and no `context` command.

## Goals / Non-Goals

**Goals:**
- Dialog opens instantly regardless of memory count
- Default view gives a useful overview (context summary)
- Users can browse all memories with pagination
- CLI supports `set-memory list --limit N` and `set-memory context`

**Non-Goals:**
- Virtual scrolling or lazy widget rendering (over-engineering for current scale)
- Changing the search/recall flow (already limited to 20)
- Adding delete/forget UI (separate change, see shodh-upgrade-briefing.md)
- Type filter tabs or advanced filtering

## Decisions

### Decision 1: Context Summary as default view, not paginated list

**Choice**: Open dialog shows `context_summary()` output — a few items per category.

**Alternatives**:
- *Load first 50*: Still renders 50 cards at open. Not as meaningful as a summary.
- *Empty + search only*: Loses the "browse" feeling entirely.

**Rationale**: `context_summary()` is O(1) response size (max_items per category), always fast, and gives the most useful at-a-glance overview. Paginated list available via "Show All" button.

### Decision 2: Page size of 50 with "Load More"

**Choice**: `set-memory list --limit 50` for first page, "Load More" appends next 50.

**Rationale**: 50 QFrame cards render comfortably (<100ms). Offset-based pagination isn't available in native shodh API, so we use `list_memories(limit=N)` and slice client-side from cached full list on subsequent pages. Since `list_memories()` returns sorted by time, this works naturally.

**Implementation detail**: First call fetches all IDs/metadata, but we only render 50 cards at a time. The data is cached in the dialog instance. "Load More" renders the next batch from cache without a new subprocess call.

Actually — simpler approach: just call `set-memory list` once (same as now), cache the full result, but only render 50 cards initially. "Load More" renders next 50 from the cached list. The bottleneck is widget rendering, not data loading. A JSON list of 2000 memories is ~1MB, fast to parse.

### Decision 3: Two-mode dialog (Summary / List)

**Choice**: Dialog has two states toggled by a button:
- **Summary mode** (default): shows `context_summary` output
- **List mode**: shows paginated card list

Search always shows card results (from `recall`), regardless of mode.

## Risks / Trade-offs

- **[Risk] context_summary() may not exist in older shodh-memory versions** → Mitigation: health check + fallback to paginated list if context_summary fails
- **[Risk] Caching full list in memory for large memory counts** → Mitigation: At 2000 memories × ~500 bytes = 1MB, this is fine. Could add a hard cap at 10000 with a warning.
- **[Trade-off] Two CLI calls at dialog open (context + list count)** → Accept: both are fast, and context_summary provides real value
