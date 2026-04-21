# phase-continuity Specification

## Purpose
TBD - created by archiving change run-history-and-phase-continuity. Update Purpose after archive.
## Requirements
### Requirement: Spec lineage identity derived from input path
The orchestration state SHALL carry a `spec_lineage_id` field, computed as the normalised input spec path (the value passed as `--spec` when the sentinel started, equivalent to `orchestration-plan.json::input_path`). Every `Change`, every archive entry, every rotated event file, every history JSONL line, and every sentinel-session record SHALL be tagged with this identifier so downstream consumers can filter by lineage without guesswork.

#### Scenario: Sentinel started with spec-v1.md
- **WHEN** the sentinel is started via `set-sentinel start --spec docs/spec-v1.md`
- **THEN** `state.spec_lineage_id` SHALL be set to `"docs/spec-v1.md"` (or the equivalent canonical path)
- **AND** every Change subsequently created in this state SHALL carry `spec_lineage_id = "docs/spec-v1.md"`
- **AND** every archive entry written while this sentinel runs SHALL carry the same `spec_lineage_id`

#### Scenario: Operator switches to spec-v2.md
- **WHEN** the sentinel is stopped and restarted with `--spec docs/spec-v2.md`
- **THEN** the new state's `spec_lineage_id` SHALL be `"docs/spec-v2.md"`
- **AND** the previous lineage's archive entries SHALL remain tagged with the v1 lineage id (not retagged)

#### Scenario: Path canonicalisation
- **WHEN** the operator passes a relative path (`docs/spec.md`) and later an absolute path (`/home/.../docs/spec.md`) for the same file
- **THEN** both SHALL resolve to the same canonical `spec_lineage_id` (relative-to-project path, POSIX separators)

### Requirement: Phase offset within a lineage
When the planner generates a plan during replan OR at the start of a sentinel session whose `spec_lineage_id` matches an existing lineage in the project, the plan's phase numbers SHALL be offset so the smallest new phase is greater than every phase already present (in live state + archive) **for that lineage**. Phases belonging to OTHER lineages SHALL NOT contribute to the offset computation.

#### Scenario: Replan continues a lineage
- **WHEN** the v1 lineage has archived phases 0, 1, 2 and the replan output has phases 1, 2
- **THEN** the offset SHALL shift them to 3, 4
- **AND** the new changes SHALL carry `spec_lineage_id = v1`

#### Scenario: Restart-same-spec continues numbering
- **WHEN** the v1 lineage has archived phases 0, 1, 2 and the sentinel is stopped and restarted with the same spec
- **AND** the initial plan of the restart uses phases 1, 2
- **THEN** the offset SHALL shift them to 3, 4 (same rule as replan)

#### Scenario: Other lineage's phases are ignored
- **WHEN** the v1 lineage has archived phases 0, 1, 2, and a new sentinel starts with `--spec v2.md`
- **AND** the initial plan for v2 uses phases 1, 2
- **THEN** the offset SHALL be 0 (no shift) because the v2 lineage has no prior phases
- **AND** the v1 lineage's archived phases SHALL NOT leak into v2's numbering

### Requirement: Fresh phase numbering for a new lineage
When a new sentinel session opens a lineage that does not yet appear in the project's state or archive, phase numbering SHALL start from the planner's native output with no offset applied.

#### Scenario: First-ever session on a new spec
- **WHEN** the project archive has lineages `{v1}` only and the sentinel starts with `--spec v2.md`
- **THEN** `state.spec_lineage_id = v2`
- **AND** the first plan's phases are used verbatim (no offset)

### Requirement: Sentinel session id as sub-dimension
The orchestrator SHALL still track `sentinel_session_id` (UUIDv4 per sentinel start) and `sentinel_session_started_at` (ISO-8601) for within-lineage restart visibility, but lineage SHALL be the primary grouping key in every UI and API response.

#### Scenario: Multiple restarts on the same lineage
- **WHEN** the sentinel runs on v1.md, is stopped, and restarted on v1.md again
- **THEN** both sessions share `spec_lineage_id = v1`
- **AND** each session carries its own `sentinel_session_id`
- **AND** lineage-level UI panels group both sessions together under "v1"
- **AND** session-level UI panels (if any) can still distinguish restarts via `sentinel_session_id`

#### Scenario: Session id survives replan
- **WHEN** a replan fires mid-session
- **THEN** `sentinel_session_id` SHALL be preserved on all newly generated changes (not regenerated)

### Requirement: Plan-version propagation on archive
The archive writer SHALL include the current `state.plan_version` on every entry it writes, so the UI can differentiate cycles that share a phase number within the same lineage.

#### Scenario: Same-phase collision within a lineage
- **WHEN** replan cycle A wrote phase-1 changes under lineage v1 and cycle B also writes phase-1 changes under v1 (offset not triggered because cycle A's changes were dropped before archive)
- **THEN** archive entries from cycle A carry `plan_version = X`, cycle B's live changes carry `plan_version = X + 1`
- **AND** the UI SHALL render "Phase 1 (plan v<X>)" and "Phase 1 (plan v<X+1>)" as separate subheaders under the v1 lineage view

