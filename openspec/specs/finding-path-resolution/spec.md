# finding-path-resolution Specification

## Purpose
TBD - created by archiving change findings-path-resolvable. Update Purpose after archive.

## Requirements

### Requirement: A stored finding path declares its base
An artifact that stores a finding's file path SHALL declare, in the artifact itself, what
that path is relative to. The declaration SHALL be symbolic — a named base such as the
repository root — and SHALL NOT contain an absolute filesystem path, because these
artifacts are committed and an absolute path publishes the local username and directory
layout.

#### Scenario: JSONL entry carries the base
- **WHEN** a review-findings JSONL entry is appended for a change
- **THEN** the entry SHALL carry a field naming the symbolic base its `issues[].file` values
  resolve against
- **AND** neither that field nor any `issues[].file` value SHALL be an absolute path

#### Scenario: The committed markdown states the base
- **WHEN** `.claude/review-findings.md` is created or appended to
- **THEN** the file SHALL state, once, that the paths it lists are relative to the
  repository root
- **AND** the file SHALL contain no absolute filesystem path

#### Scenario: Stored paths are unchanged
- **WHEN** a finding is written with a relative file path
- **THEN** the stored `file` value SHALL be byte-identical to what the same input produced
  before this capability existed
- **AND** the finding's fingerprint SHALL be unchanged

### Requirement: A declared base resolves a stored path to an absolute one
The system SHALL provide one resolution function that joins a stored finding path to a
concrete root directory and returns a normalized absolute path. All display surfaces SHALL
use it, so the stored form and the displayed form cannot drift apart in one caller.

#### Scenario: Relative path is joined to the root
- **WHEN** resolution is asked for a relative path and a root directory
- **THEN** it SHALL return the normalized absolute path formed by joining the two

#### Scenario: Already-absolute path is returned unchanged
- **WHEN** resolution is asked for a path that is already absolute
- **THEN** it SHALL return that path normalized, without joining the root to it

#### Scenario: Nothing to resolve
- **WHEN** resolution is asked for an empty path, or the root is empty or unknown
- **THEN** it SHALL return an empty string rather than a path built from a guessed base

#### Scenario: A path from before this change
- **WHEN** a stored artifact carries no base declaration
- **THEN** resolution SHALL treat the base as the repository root rather than failing, so a
  historical finding keeps a resolvable path
