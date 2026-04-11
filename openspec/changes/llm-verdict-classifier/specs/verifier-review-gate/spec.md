## ADDED Requirements

### Requirement: Review gate verdict is format-agnostic
The review gate SHALL derive its verdict from a combination of a deterministic fast-path parser and an LLM verdict classifier fallback so that a review finding any CRITICAL issue in any output format blocks the merge.

#### Scenario: First-round review with inline ISSUE format passes fast-path
- **GIVEN** a primary review output containing `ISSUE: [CRITICAL] Missing validation` inline
- **WHEN** the review gate runs
- **THEN** `_parse_review_issues` returns at least one CRITICAL finding
- **AND** the classifier is NOT invoked (fast-path already succeeded)
- **AND** the gate returns FAIL

#### Scenario: Retry review with header format triggers classifier fallback
- **GIVEN** a primary review output containing `### Finding 1: ... **NOT_FIXED** [CRITICAL]` and `**Summary: 0/3 fixed, 3 NOT_FIXED [CRITICAL].**`
- **AND** the directive `llm_verdict_classifier_enabled` is True (default)
- **WHEN** the review gate runs
- **THEN** the fast-path returns zero findings
- **AND** the classifier is invoked because the output size is ≥ 500 chars
- **AND** the classifier returns `critical_count >= 1`
- **AND** the gate returns FAIL
- **AND** an ERROR log line is emitted identifying that the classifier overrode the fast-path

#### Scenario: Clean review passes both fast-path and classifier
- **GIVEN** a primary review output with no issues and `REVIEW PASS` narrative text
- **WHEN** the review gate runs
- **THEN** the fast-path returns zero findings
- **AND** the classifier runs and returns `critical_count: 0`
- **AND** the gate returns PASS

### Requirement: Review gate no longer short-circuits on `REVIEW PASS` regex
The review gate SHALL NOT use `re.search(r"REVIEW\s+PASS", review_output)` to short-circuit verdict derivation. The phrase `REVIEW PASS` may appear legitimately in quoted prior reviews, acknowledgements of resolved findings, or narrative explanations, and matching on its presence has historically produced false positives.

#### Scenario: `REVIEW PASS` in quoted text does not trigger pass
- **GIVEN** a primary review output containing `The previous review said "REVIEW PASS" but I now find 2 new CRITICAL issues: ISSUE: [CRITICAL] ...`
- **WHEN** the review gate runs
- **THEN** the gate does NOT return pass on the `REVIEW PASS` phrase alone
- **AND** the fast-path detects the inline `ISSUE: [CRITICAL]` and returns FAIL

### Requirement: Review gate severity has a single source of truth
The review gate's `_parse_review_issues` SHALL derive each finding's severity from exactly one source: the inline `[LOW|MEDIUM|HIGH|CRITICAL]` tag on the `ISSUE:` line. A secondary summary scan or body regex SHALL NOT contribute to the severity assignment.

#### Scenario: Inline tag is the only severity source
- **GIVEN** a review finding with the line `ISSUE: [MEDIUM] Summary text that mentions "critical" somewhere`
- **WHEN** `_parse_review_issues` parses the review output
- **THEN** the finding has `severity == "MEDIUM"`
- **AND** the word "critical" in the summary does NOT upgrade it to CRITICAL

#### Scenario: Severity drift between inline tag and narrative is resolved by tag
- **GIVEN** a review output where the inline tag says `[LOW]` but the narrative body says "this is a critical concern"
- **WHEN** `_parse_review_issues` parses the review output
- **THEN** the finding has `severity == "LOW"`
