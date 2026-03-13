## ADDED Requirements

### Requirement: Visual phase timeline for changes
Each change displays a horizontal timeline bar showing its progression through orchestration phases.

#### Scenario: Running change timeline
- **WHEN** a change is in progress (running/verifying)
- **THEN** a horizontal bar shows completed phases in color and the current phase with a pulse animation
- **THEN** phases include: Dispatch → Implement → Build → Test → Review → Smoke → Merge

#### Scenario: Completed change timeline
- **WHEN** a change has status "done" or "merged"
- **THEN** all phases show as completed with their duration
- **THEN** failed-then-retried phases show the retry count

#### Scenario: Timeline data sources
- **WHEN** rendering the timeline
- **THEN** use `started_at`/`completed_at` for overall duration
- **THEN** use `gate_build_ms`, `gate_test_ms`, `gate_review_ms`, `gate_verify_ms` for gate phase durations
- **THEN** use `gate_total_ms` for total gate time

#### Scenario: Timeline in change detail
- **WHEN** a change row is expanded (via gate detail click or dedicated expand)
- **THEN** the timeline is shown at the top of the expanded area
