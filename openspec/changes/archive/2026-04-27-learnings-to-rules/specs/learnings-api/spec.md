## ADDED Requirements

### Requirement: Rule candidates API endpoint
The server SHALL expose `GET /api/{project}/rule-candidates` returning generated rule candidates from the learnings analyzer.

#### Scenario: Candidates available
- **WHEN** the analyzer finds recurring patterns meeting the minimum threshold
- **THEN** the response SHALL include `candidates` array with each entry containing: id, title, classification, confidence, occurrence_count, affected_changes, suggested_rule_text, and status (pending/accepted/dismissed)

#### Scenario: No candidates
- **WHEN** no patterns meet the threshold
- **THEN** the response SHALL return `{ "candidates": [] }`

### Requirement: Accept/dismiss rule candidate endpoint
The server SHALL expose `POST /api/{project}/rule-candidates/{id}/action` to accept or dismiss a candidate.

#### Scenario: Accept action
- **WHEN** the client sends `{ "action": "accept" }`
- **THEN** the server SHALL write the rule file to the appropriate location based on classification and return `{ "status": "accepted", "path": "<written-file-path>" }`

#### Scenario: Dismiss action
- **WHEN** the client sends `{ "action": "dismiss" }`
- **THEN** the server SHALL save the dismissal to memory and return `{ "status": "dismissed" }`
