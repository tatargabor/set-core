## IN SCOPE
- Lint gate: skip comment lines in diff matching
- Review gate: fix-verification mode on retry rounds
- Review gate: reduce extra_retries default from 3 to 1

## OUT OF SCOPE
- Changing lint patterns themselves (dangerouslySetInnerHTML stays as forbidden)
- Restructuring the review gate executor
- Changing the GatePipeline retry mechanism

### Requirement: Lint gate shall skip comment lines
The lint gate's `_extract_added_lines()` SHALL filter out lines that are comments (starting with `//`, `*`, `#`, `/**`, `* `) before pattern matching. This prevents false positives when agents mention forbidden patterns in fix comments.

#### Scenario: Comment mentioning forbidden pattern passes
- **GIVEN** a diff with added line `// Replaced dangerouslySetInnerHTML with safe approach`
- **WHEN** lint gate runs with `dangerouslySetInnerHTML` pattern
- **THEN** the comment line SHALL NOT trigger a match

#### Scenario: Actual code usage still caught
- **GIVEN** a diff with added line `<div dangerouslySetInnerHTML={{__html: content}} />`
- **WHEN** lint gate runs
- **THEN** the code line SHALL trigger a CRITICAL match

### Requirement: Review gate shall use fix-verification mode on retries
When `verify_retry_count > 0`, the review gate SHALL instruct the reviewer to ONLY verify whether previous findings were fixed — not scan for new issues. Only NOT_FIXED items SHALL be reported as CRITICAL.

#### Scenario: First review finds issues, retry verifies fixes
- **GIVEN** first review found 3 CRITICAL issues
- **AND** agent fixed them
- **WHEN** retry review runs
- **THEN** reviewer SHALL only check those 3 issues, not find new ones

### Requirement: Review extra_retries default shall be 1
The default `review_extra_retries` SHALL be 1 (total 3 review attempts with max_retries=2), not 3 (which gave 5 total attempts).
