## ADDED Requirements

### Requirement: Review finding responses carry a resolved absolute path
Every review-finding issue the server returns SHALL carry, alongside its stored relative
`file` value, a resolved absolute path in a separate field. The stored `file` field SHALL be
returned unchanged. The server resolves it because it knows the project root and its
response is never committed, so no absolute path is persisted by doing so.

#### Scenario: Issue with a file path
- **WHEN** `GET /api/{project}/review-findings` returns an issue whose `file` is a non-empty
  relative path
- **THEN** the issue SHALL also carry a field holding the absolute path formed from the
  project root and that value
- **AND** the issue's `file` field SHALL still hold the stored relative value

#### Scenario: Issue with no file path
- **WHEN** an issue carries an empty or missing `file`
- **THEN** the resolved field SHALL be an empty string, not the project root on its own

#### Scenario: Unified learnings endpoint
- **WHEN** the unified learnings endpoint returns its `review_findings` section
- **THEN** its issues SHALL carry the resolved field on the same terms as the
  review-findings endpoint
