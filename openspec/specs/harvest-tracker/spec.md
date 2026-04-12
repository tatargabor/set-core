# Spec: Harvest Tracker

## ADDED Requirements

## IN SCOPE
- Per-project tracking of last harvested commit SHA
- Persistent storage in set-project registry
- Per-commit reviewed/adopted/skipped state

## OUT OF SCOPE
- Cross-run deduplication of similar fixes (future enhancement)
- Automatic merging of adopted changes into set-core

### Requirement: Track harvest state per project

The system SHALL persist the last harvested commit SHA for each registered project so that subsequent harvests only show new changes.

#### Scenario: First harvest on a project
- **WHEN** `set-harvest` scans a project with no `last_harvested_sha`
- **THEN** all commits since the initial `set-project init` commit are shown
- **AND** after the harvest session, `last_harvested_sha` is set to the project's current HEAD

#### Scenario: Incremental harvest
- **WHEN** `set-harvest` scans a project with `last_harvested_sha` set to commit ABC
- **AND** the project has 5 new commits since ABC
- **THEN** only those 5 commits are shown
- **AND** `last_harvested_sha` is updated to the new HEAD after review

#### Scenario: Harvest state survives project re-registration
- **WHEN** a project is removed and re-registered at the same path
- **THEN** the `last_harvested_sha` is preserved if the git history is intact
- **AND** reset to None if the git history has changed (different initial commit)
