## ADDED Requirements

### Requirement: Review findings JSONL included in retry context
`_build_unified_retry_context()` (verifier.py:411) SHALL accept new optional parameters `change_name: str = ""` and `findings_path: str = ""`. When both are provided and the JSONL file exists, it SHALL read prior findings for the change and include them in the retry context.

#### Scenario: Prior review findings exist for change
- **WHEN** building a retry context with `change_name` and `findings_path` provided
- **AND** `review-findings.jsonl` at `findings_path` contains entries where `entry["change"] == change_name`
- **THEN** the retry context SHALL include a "### Prior Review Findings" section listing each finding's severity, file, line, and summary from the most recent matching entry

#### Scenario: No prior findings
- **WHEN** building a retry context with `findings_path` provided
- **AND** no entries in the JSONL match `change_name`
- **THEN** the retry context SHALL not include a prior findings section

#### Scenario: No findings_path provided (backward compatibility)
- **WHEN** building a retry context without `findings_path` parameter (existing callers)
- **THEN** behavior SHALL be identical to current implementation (no JSONL lookup)
