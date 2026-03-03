## MODIFIED Requirements

### Requirement: Multi-account session storage
The system SHALL store multiple Claude account session keys in a single configuration file with backward compatibility. Each account entry MAY include metadata fields (`org_name`, `source`) for cache and provenance tracking.

#### Scenario: New format with multiple accounts
- **WHEN** `claude-session.json` contains `{"accounts": [{"name": "Personal", "sessionKey": "sk-ant-..."}, {"name": "Work", "sessionKey": "sk-ant-..."}]}`
- **THEN** the system SHALL load all accounts and fetch usage for each

#### Scenario: Backward compatible migration from old format
- **WHEN** `claude-session.json` contains `{"sessionKey": "sk-ant-..."}`
- **THEN** the system SHALL treat it as a single account named "Default"
- **AND** usage fetching SHALL work identically to the old behavior

#### Scenario: No session file exists
- **WHEN** `claude-session.json` does not exist or contains no accounts
- **THEN** the system SHALL fall back to local JSONL parsing for a single unnamed account

#### Scenario: Write always uses new format
- **WHEN** the system saves account data
- **THEN** it SHALL always write the `{"accounts": [...]}` format
- **AND** SHALL never write the old `{"sessionKey": "..."}` format

#### Scenario: Chrome-scanned accounts include metadata
- **WHEN** an account is saved by the Chrome session scanner
- **THEN** the entry SHALL include `"source": "chrome-scan"` and `"org_name": "<cached>"` fields
- **AND** these fields SHALL be preserved across saves

#### Scenario: Manually-added accounts have no scan metadata
- **WHEN** an account is added via the "Add Account" dialog
- **THEN** the entry SHALL include `"source": "manual"`
- **AND** no `org_name` field SHALL be present

#### Scenario: Scan merges with existing manual accounts
- **WHEN** the Chrome scanner saves results
- **THEN** existing accounts with `"source": "manual"` SHALL be preserved
- **AND** accounts with `"source": "chrome-scan"` SHALL be updated or added based on scan results
