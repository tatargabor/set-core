## MODIFIED Requirements

### Requirement: Per-phase token usage in summary
The orchestration summary (email + HTML report + cmd_status) SHALL include per-phase token breakdown when milestones are enabled.

#### Scenario: Phase token breakdown
- **WHEN** orchestration completes with 3 phases
- **THEN** the summary SHALL show token usage per phase (e.g., "Phase 1: 1.2M, Phase 2: 2.0M, Phase 3: 0.8M")
- **AND** cumulative total SHALL still be displayed

#### Scenario: Single phase
- **WHEN** all changes are in phase 1 (milestones disabled or small spec)
- **THEN** per-phase breakdown SHALL be omitted (only total shown)
