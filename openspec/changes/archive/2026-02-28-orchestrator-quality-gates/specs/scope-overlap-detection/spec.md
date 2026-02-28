## ADDED Requirements

### Requirement: Detect scope overlap between planned changes
`validate_plan` SHALL compare the scope text of all changes in a plan using keyword jaccard similarity and warn if any pair exceeds 40% overlap.

#### Scenario: Two changes with overlapping scopes
- **WHEN** a plan has changes `email-compliance` (scope: "add GDPR footer, RFC 8058 headers, suppression list") and `email-gdpr-footer` (scope: "add GDPR compliance footer to emails")
- **THEN** a warning is logged: "Scope overlap detected: 'email-compliance' <-> 'email-gdpr-footer' (N% keyword similarity)"
- **AND** a notification is sent with the overlap count

#### Scenario: Changes with distinct scopes
- **WHEN** a plan has changes with <40% keyword overlap
- **THEN** no overlap warning is emitted

#### Scenario: Very short scopes skipped
- **WHEN** a change scope has fewer than 3 words (3+ chars each)
- **THEN** it is excluded from overlap comparison to avoid false positives

### Requirement: Detect overlap with active worktrees
`validate_plan` SHALL also compare new plan change scopes against changes currently in `running`, `dispatched`, or `done` status in the state file.

#### Scenario: New change overlaps with running worktree
- **WHEN** a planned change has >40% keyword similarity with an active worktree's scope
- **THEN** a warning is logged: "New change 'X' overlaps with ACTIVE change 'Y' (N% similarity)"
