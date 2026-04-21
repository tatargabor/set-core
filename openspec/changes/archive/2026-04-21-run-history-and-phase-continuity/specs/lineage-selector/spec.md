## ADDED Requirements

### Requirement: Lineages listing endpoint
The API SHALL expose `/api/<project>/lineages`, returning every distinct `spec_lineage_id` discovered in the project's live state + archive + history JSONLs, with enough metadata for the UI to render a selector.

#### Scenario: Two lineages present
- **WHEN** the project archive contains entries tagged `v1.md` and the live state is tagged `v2.md`
- **THEN** `GET /api/<project>/lineages` SHALL return a JSON object `{"lineages": [...]}` with two entries
- **AND** each entry SHALL include: `spec_lineage_id` (string), `display_name` (file basename without path), `first_seen_at` (ISO-8601, earliest timestamp from any tagged record), `last_seen_at` (ISO-8601, latest timestamp), `is_live` (bool — true when it matches the current `state.spec_lineage_id` AND the sentinel is running), `change_count` (int), `merged_count` (int)

#### Scenario: Single lineage project
- **WHEN** the project has only ever run one spec
- **THEN** the response SHALL contain exactly one lineage entry with `is_live = true` when the sentinel is running, `false` otherwise

#### Scenario: Unrecoverable historic records
- **WHEN** archive entries exist that have neither `spec_lineage_id` nor a recoverable `input_path` in the project's historic plan files (after backfill migration ran)
- **THEN** those entries SHALL be surfaced under a single `spec_lineage_id = "__unknown__"` entry with `display_name = "Unknown (unrecoverable)"`
- **AND** the response SHALL include a `diagnostic` note explaining that backfill could not attribute these records
- **AND** the UI SHALL NOT show `__unknown__` in the sidebar unless the user expands a "show unattributed" affordance (opt-in, not default-visible)

### Requirement: Data endpoints accept an optional lineage filter
Every orchestration data endpoint that returns per-change or per-event records SHALL accept an optional `?lineage=<id>` query parameter; when supplied, the response SHALL include only records tagged with that lineage. When omitted, the response defaults to the live lineage (`state.spec_lineage_id`). Backend accepts the legacy `?lineage=__all__` sentinel for backwards compatibility with any external consumer, but the dashboard UI no longer exposes an "All lineages" selection — mixing cycles with shared phase numbers from runs that may be days apart proved more confusing than useful.

#### Scenario: Filtered /state
- **WHEN** the client calls `GET /api/<project>/state?lineage=v1.md`
- **THEN** `data.changes` SHALL contain only changes tagged `v1.md` (live + archived)
- **AND** `data.phases` SHALL be restricted to phases that have at least one v1-tagged change

#### Scenario: Filtered activity timeline
- **WHEN** the client calls `GET /api/<project>/activity-timeline?lineage=v1.md`
- **THEN** the returned spans SHALL be derived only from events tagged v1 via the rotated cycle file's `CYCLE_HEADER`
- **AND** sentinel-session boundary spans SHALL be emitted only for v1 session transitions

#### Scenario: Filtered LLM calls
- **WHEN** the client calls `GET /api/<project>/llm-calls?lineage=v1.md`
- **THEN** calls SHALL be limited to v1-tagged events plus session files whose change's lineage is v1

#### Scenario: Filter omitted — default to live
- **WHEN** the client calls `GET /api/<project>/state` without a `lineage` parameter
- **THEN** the response SHALL be equivalent to `?lineage=<state.spec_lineage_id>` when the sentinel is running
- **AND** equivalent to the most-recently-active lineage otherwise (the one with the newest `last_seen_at` among all discovered lineages)

#### Scenario: All-lineages merged view (backend-only compatibility shim)
- **WHEN** an external consumer calls `GET /api/<project>/state?lineage=__all__`
- **THEN** every lineage's records SHALL be returned in a single response, each record retaining its `spec_lineage_id`
- **AND** the dashboard UI SHALL NOT emit this request from any user-facing control — the sentinel is always viewed through exactly one lineage

### Requirement: Left-sidebar lineage list
The existing project sidebar (the menu that currently shows the project name header followed by Orchestration / Issues / Memory / Settings items) SHALL render a `Lineages` section between the project name and the existing menu items, listing every lineage returned by `/api/<project>/lineages` as a clickable entry.

#### Scenario: Sidebar renders the lineage list
- **WHEN** the project has two lineages (v1 archived, v2 live)
- **THEN** the sidebar SHALL render under the project name header:
  - One entry per lineage with the lineage `display_name`
  - A small green dot on the entry whose `is_live = true`
  - The existing `Orchestration / Issues / Memory / Settings` entries BELOW the lineage list

#### Scenario: Default selection on first load
- **WHEN** the dashboard loads a project for the first time (no saved selection in localStorage)
- **AND** exactly one lineage has `is_live = true`
- **THEN** that lineage SHALL be selected by default
- **AND** its sidebar entry SHALL be visually highlighted (matching the current active-item style)

#### Scenario: Default when no lineage is live
- **WHEN** the dashboard loads and no lineage is `is_live` (sentinel idle across the board)
- **THEN** the lineage with the newest `last_seen_at` SHALL be selected by default

#### Scenario: Switching lineage
- **WHEN** the operator clicks another lineage entry in the sidebar
- **THEN** the selected lineage SHALL change and every data tab SHALL refetch with `?lineage=<newly selected>`
- **AND** the sentinel's execution SHALL NOT be affected — sidebar navigation is purely a view switch
- **AND** the live-indicator dot SHALL stay on whichever lineage is genuinely running (not on the one the operator just clicked, unless they are the same lineage)

#### Scenario: Selector persistence
- **WHEN** the operator selects `v1.md` and reloads the page
- **THEN** on reload the selection SHALL restore `v1.md` from `localStorage` under key `set-lineage-<project>`
- **AND** if that lineage no longer exists (e.g., project cleanup), the selector SHALL fall back to the default-selection rule silently

#### Scenario: Live-badge decouples from view
- **WHEN** the operator is viewing `v1.md` while the sentinel runs `v2.md`
- **THEN** the StatusHeader's status badge (running / stopped / etc.) SHALL reflect the LIVE lineage (v2), not the viewed lineage (v1)
- **AND** a text hint ("Viewing v1.md — sentinel running v2.md") SHALL appear next to the badge so the operator cannot confuse the two
