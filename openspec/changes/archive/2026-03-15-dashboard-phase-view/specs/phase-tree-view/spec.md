## ADDED Requirements

### Requirement: Phase grouping
The PhaseView component SHALL group changes by their `phase` field and display each phase as a collapsible section with a header.

#### Scenario: Multi-phase run
- **WHEN** the state contains changes with phase values 1, 2, and 3
- **THEN** PhaseView renders three phase sections in ascending order (Phase 1, Phase 2, Phase 3)

#### Scenario: Single-phase run
- **WHEN** all changes have phase=1 (or phase is undefined)
- **THEN** PhaseView renders a single "Phase 1" section containing all changes

### Requirement: Phase header summary
Each phase section header SHALL display: phase number, phase status indicator, progress (done/total changes), aggregated token count, and aggregated duration.

#### Scenario: Completed phase header
- **WHEN** Phase 1 has 3 changes all with terminal status (merged/done/skipped)
- **THEN** the header shows a completed indicator, "3/3", summed tokens across all 3 changes, and summed duration

#### Scenario: Running phase header
- **WHEN** Phase 2 has 1 running and 2 pending changes with 89k tokens used so far
- **THEN** the header shows a running indicator, "0/3" (only terminal counts as done), "89k" tokens, and elapsed duration

#### Scenario: Pending phase header
- **WHEN** Phase 3 has no changes started yet
- **THEN** the header shows a pending indicator, "0/2", no token or duration values

### Requirement: Phase status derivation
The phase status SHALL be derived from `state.extras.phases[N].status` when available. When `extras.phases` is not present (single-phase runs), the status SHALL be derived from change statuses: all terminal = completed, any running/implementing/verifying = running, otherwise pending.

#### Scenario: Multi-phase status from extras
- **WHEN** `state.extras.phases` exists with `{"1": {"status": "completed"}, "2": {"status": "running"}}`
- **THEN** Phase 1 shows completed, Phase 2 shows running

#### Scenario: Single-phase status derived from changes
- **WHEN** `state.extras.phases` is undefined and changes include 2 merged and 1 running
- **THEN** Phase 1 shows running status

### Requirement: Dependency tree nesting
Within each phase, changes SHALL be rendered as a tree based on `depends_on` relationships. Root changes (no intra-phase dependencies) appear at the top level. A change whose `depends_on` target is in the same phase appears nested under that target.

#### Scenario: Linear chain within phase
- **WHEN** Phase 1 has changes A (no deps), B (depends on A), C (depends on B)
- **THEN** the tree renders as A → B → C nested three levels deep

#### Scenario: Multiple roots within phase
- **WHEN** Phase 2 has changes X (no deps), Y (depends on X), Z (no deps)
- **THEN** X and Z are top-level roots, Y is nested under X

#### Scenario: Cross-phase dependency treated as root
- **WHEN** Phase 2 has change D whose `depends_on` lists change A which is in Phase 1
- **THEN** change D appears as a root in Phase 2 (cross-phase deps are implicit from phase ordering)

### Requirement: Change row display
Each change row in the tree SHALL display: indentation reflecting tree depth, change name (monospace), status with color coding, duration, token count (input/output), and gate results bar.

#### Scenario: Running change row
- **WHEN** change "add-products" is running with 8m duration and 89k tokens
- **THEN** the row shows the name, green "running" status, "8m" duration, "89k" tokens, and gate bar with partial progress

#### Scenario: Blocked change row
- **WHEN** change "cart-system" is pending and its `depends_on` target "add-products" is still running
- **THEN** the row shows "blocked" status with the dependency name indicated

### Requirement: TypeScript type extensions
`ChangeInfo` SHALL include `phase` (number) and `depends_on` (string array) fields. `StateData` SHALL include `current_phase` (number) and `phases` (record) fields. These fields already exist in the API JSON response.

#### Scenario: Type declarations match API response
- **WHEN** the API returns a state with `current_phase: 2` and changes with `phase` and `depends_on` fields
- **THEN** the TypeScript types allow accessing these fields without type assertions

### Requirement: Dashboard tab integration
PhaseView SHALL be accessible as a "Phases" tab in the dashboard, positioned after the "Changes" tab.

#### Scenario: Tab visibility
- **WHEN** the dashboard loads with orchestration state
- **THEN** a "Phases" tab appears in the tab bar after "Changes"

#### Scenario: Tab renders PhaseView
- **WHEN** user clicks the "Phases" tab
- **THEN** the PhaseView component renders with the current state's changes
