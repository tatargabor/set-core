## MODIFIED Requirements

### Requirement: Phase progress in cmd_status output
`cmd_status()` SHALL display current phase progress when milestones are enabled. The display SHALL include: current phase number, per-phase summary (status, change count, server URL if running), and overall phase progress (e.g., "Phase 2/4").

#### Scenario: Status with milestones
- **WHEN** user runs `set-orchestrate status` with milestones enabled
- **THEN** output SHALL include a "Milestones" section between progress summary and change table
- **AND** the section SHALL show each phase with its status and dev server URL if running

#### Scenario: Status without milestones
- **WHEN** milestones are not enabled or state has no phase data
- **THEN** output SHALL remain unchanged from current format
