## MODIFIED Requirements

### Requirement: Snapshot caching in state directory

The system SHALL cache the snapshot at `$DESIGN_SNAPSHOT_DIR/design-snapshot.md` (typically project root for spec-mode orchestration), scoped to the current orchestration run. The snapshot SHALL also be accessible to dispatched agents via the project root copy. The Python planner SHALL use the same caching logic: if `design-snapshot.md` exists and contains `## Design Tokens`, skip re-fetching unless `force=True`.

#### Scenario: Snapshot file created after successful fetch
- **WHEN** `fetch_design_snapshot()` completes successfully (called from Python planner via bash subprocess)
- **THEN** the snapshot is written to `$DESIGN_SNAPSHOT_DIR/design-snapshot.md`
- **AND** if `$DESIGN_SNAPSHOT_DIR` differs from the project root, a copy is placed at `$PROJECT_ROOT/design-snapshot.md`
- **AND** the function returns 0

#### Scenario: Cached snapshot exists on subsequent call
- **WHEN** `_fetch_design_context()` is called in the Python planner
- **AND** `design-snapshot.md` already exists with `## Design Tokens` content
- **AND** `force` is `False`
- **THEN** the Python planner reads the cached file without invoking bash bridge
- **AND** returns the snapshot content

#### Scenario: Replan forces re-fetch
- **WHEN** `_fetch_design_context(force=True)` is called during a replan cycle
- **AND** a cached snapshot exists
- **THEN** `fetch_design_snapshot "force"` is called via bash subprocess
- **AND** the cached file is overwritten with a fresh snapshot
