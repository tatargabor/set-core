# Issue Registry

## ADDED Requirements

## IN SCOPE
- Persistent JSON storage for issues, groups, and mute patterns
- CRUD operations for issues
- Deduplication via fingerprinting
- Query by state, severity, environment, group
- Atomic writes with file locking
- Auto-sequential ID generation (ISS-001, GRP-001, MUTE-001)

## OUT OF SCOPE
- Database backend (JSON files only)
- Full-text search across error details
- Issue archival/rotation (future change)

### Requirement: Issue persistence
The registry SHALL store issues as a JSON file at `.set/issues/registry.json` within each project's directory. The file SHALL contain issues and groups in a single document. Writes SHALL be atomic (write to temp file, rename).

#### Scenario: Create and retrieve issue
- **WHEN** a new issue is registered with source, error_summary, and environment
- **THEN** the registry assigns an auto-incremented ID (ISS-NNN format) and persists it to disk

#### Scenario: Registry survives process restart
- **WHEN** the set-manager service restarts
- **THEN** all previously registered issues are loaded from registry.json with correct state

### Requirement: Issue deduplication
The registry SHALL compute a fingerprint for each new issue by normalizing the error_summary (stripping timestamps, PIDs, temp paths) and hashing with source + affected_change. If an active issue with the same fingerprint exists, the occurrence_count SHALL be incremented instead of creating a duplicate.

#### Scenario: Duplicate error suppressed
- **WHEN** an error is registered that matches the fingerprint of an existing non-resolved issue
- **THEN** the existing issue's occurrence_count is incremented and no new issue is created

#### Scenario: Resolved issue allows re-registration
- **WHEN** an error matches the fingerprint of a resolved/dismissed issue
- **THEN** a new issue is created (resolved issues don't block new registration)

### Requirement: Issue queries
The registry SHALL support querying issues by state, severity, source, environment, and group_id. It SHALL support counting issues by state for stats endpoints.

#### Scenario: Filter by state
- **WHEN** querying with state="investigating"
- **THEN** only issues in INVESTIGATING state are returned

#### Scenario: Active issues query
- **WHEN** querying for active issues
- **THEN** issues in terminal states (RESOLVED, DISMISSED) are excluded

### Requirement: Group management
The registry SHALL support creating groups (GRP-NNN format) that link multiple issues. Issues in a group SHALL have their group_id set. A group SHALL track its own state independently.

#### Scenario: Create group from issues
- **WHEN** issues ISS-001, ISS-003 are grouped as "db-setup-sequence"
- **THEN** a GRP-NNN is created, both issues' group_id is set, and the group state is NEW

### Requirement: Mute pattern storage
The registry SHALL store mute patterns in `.set/issues/mutes.json`. Each pattern SHALL have an ID, regex pattern, reason, TTL, and match counter. Expired patterns (past expires_at) SHALL be ignored during matching.

#### Scenario: Mute pattern matches
- **WHEN** a new error's summary matches a mute pattern regex
- **THEN** the pattern's match_count is incremented and the issue is registered with MUTED state

#### Scenario: Expired mute pattern ignored
- **WHEN** a mute pattern's expires_at is in the past
- **THEN** it does not suppress matching errors
