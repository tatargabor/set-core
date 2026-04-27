# Sentinel Findings Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Structured findings storage in `.wt/sentinel/findings.json`
- Finding types: bug, observation, pattern, regression
- Assessment records (phase-level or run-level summaries)
- Finding lifecycle: open → fixed/dismissed
- Python API and CLI for CRUD operations
- Rotation on new run (archive old findings)

### Out of scope
- Rendering findings in set-web (covered by sentinel-dashboard)
- Converting findings to E2E run report markdown (manual or separate tooling)
- Correlation with git commits (optional metadata, not enforced)

## Requirements

### Requirement: Structured findings storage
The system SHALL store sentinel findings in `.wt/sentinel/findings.json` as a JSON object with `run_id`, `findings` array, and `assessments` array.

#### Scenario: Finding added
- **WHEN** a new finding is added via API or CLI
- **THEN** it SHALL be appended to the `findings` array with auto-generated `id` (F001, F002...), `severity`, `change`, `summary`, `detail`, `discovered_at` (ISO timestamp), `status` ("open"), and `iteration`

#### Scenario: Finding updated
- **WHEN** a finding is updated (e.g., status changed to "fixed")
- **THEN** the matching finding in `findings.json` SHALL be updated in place, preserving all other fields

#### Scenario: Assessment added
- **WHEN** an assessment is added
- **THEN** it SHALL be appended to the `assessments` array with `scope` (e.g., "phase-2"), `timestamp`, `summary`, and `recommendation`

### Requirement: Findings Python API
The system SHALL provide `lib/set_orch/sentinel/findings.py` with a `SentinelFindings` class for managing findings.

#### Scenario: Add finding
- **WHEN** `findings.add(severity="bug", change="add-cart", summary="IDOR vulnerability", detail="...")` is called
- **THEN** a new finding with the next sequential ID is added to `findings.json` and an event with `type: "finding"` is emitted to events.jsonl

#### Scenario: List open findings
- **WHEN** `findings.list(status="open")` is called
- **THEN** only findings with `status: "open"` SHALL be returned

### Requirement: Findings CLI
The system SHALL provide CLI commands for findings management.

#### Scenario: Add finding via CLI
- **WHEN** `set-sentinel-finding add --severity bug --change add-cart --summary "IDOR issue"` is executed
- **THEN** a new finding is added to findings.json

#### Scenario: Update finding via CLI
- **WHEN** `set-sentinel-finding update F001 --status fixed --commit abc123` is executed
- **THEN** finding F001 is updated with the new status and commit reference

#### Scenario: List findings via CLI
- **WHEN** `set-sentinel-finding list --open-only` is executed
- **THEN** only open findings are printed to stdout

### Requirement: Findings rotation on new run
The system SHALL archive findings when a new run starts.

#### Scenario: Rotation archives findings
- **WHEN** rotation is triggered
- **THEN** current `findings.json` SHALL be moved to `.wt/sentinel/archive/findings-{ISO-date}.json` and a fresh `findings.json` with empty arrays SHALL be created
