# Orch Digest Python Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Python digest orchestration
The system SHALL provide a Python implementation of the full spec digestion pipeline in `lib/set_orch/digest.py`, callable via `set-orch-core digest run`. The implementation SHALL replicate all behavior of `cmd_digest()` in `digest.sh`.

#### Scenario: Full digest run
- **WHEN** `set-orch-core digest run --state-file <path> --spec-dir <dir>` is invoked
- **THEN** the system scans the spec directory, calls Claude API for analysis, writes digest output files (index.json, requirements.json), and updates state

#### Scenario: Freshness check skips re-digest
- **WHEN** digest is invoked and spec files have not changed since last digest (hash match)
- **THEN** the system skips API calls and returns the cached digest

### Requirement: Python spec directory scanning
The system SHALL provide `scan_spec_directory()` in `digest.py` that replicates the bash `scan_spec_directory()` function — classifying files by type (spec, config, brief, etc.).

#### Scenario: Scan with mixed file types
- **WHEN** a directory contains .md specs, .yaml configs, and .json files
- **THEN** each file is classified and returned with its type, path, and content hash

### Requirement: Python digest API invocation
The system SHALL provide `call_digest_api()` in `digest.py` that calls Claude via `subprocess_utils.run_claude()` with the digest prompt and returns structured JSON output.

#### Scenario: Successful API call
- **WHEN** the digest prompt is sent to Claude
- **THEN** the response is parsed as JSON containing requirements, ambiguities, and coverage data

#### Scenario: API failure
- **WHEN** the Claude API call fails or returns non-JSON
- **THEN** the system logs the error and returns a failure status without crashing

### Requirement: Python triage pipeline
The system SHALL provide triage functions in `digest.py`: `generate_triage_md()`, `parse_triage_md()`, `merge_triage_to_ambiguities()`, and `merge_planner_resolutions()`.

#### Scenario: Triage document generation
- **WHEN** digest identifies ambiguities in specs
- **THEN** a triage markdown document is generated listing each ambiguity with resolution options

#### Scenario: Triage resolution merge
- **WHEN** a triage document has been edited with resolutions
- **THEN** resolutions are parsed and merged back into the digest ambiguities data

### Requirement: Python coverage mapping
The system SHALL provide `populate_coverage()`, `check_coverage_gaps()`, and `update_coverage_status()` in `digest.py` for requirement-to-change coverage tracking.

#### Scenario: Coverage population
- **WHEN** a plan exists with changes mapped to requirements
- **THEN** coverage data is populated showing which requirements are covered by which changes

#### Scenario: Gap detection
- **WHEN** coverage is checked and requirements exist without assigned changes
- **THEN** the gaps are reported with requirement IDs and descriptions

### Requirement: Bash digest.sh becomes thin wrapper
After migration, `digest.sh` SHALL contain only a source guard and delegation to `set-orch-core digest run`, passing through all arguments. All active logic SHALL be removed.

#### Scenario: Thin wrapper delegation
- **WHEN** `cmd_digest()` is called in bash
- **THEN** it delegates to `set-orch-core digest run` with equivalent arguments
