## IN SCOPE
- New lint gate in the verify pipeline scanning diff for forbidden patterns
- Pattern sources: profile plugin + project-knowledge.yaml
- Gate profile integration (skip/run/warn per change_type)
- Retry context with matched pattern details

## OUT OF SCOPE
- Running full linters (eslint, ruff) — covered by test_command
- Cross-file semantic analysis
- Required patterns (only forbidden patterns in this change)

### Requirement: Lint gate shall scan diff for forbidden patterns
The verify pipeline SHALL include a lint gate that extracts added lines from `git diff <merge_base>..HEAD` and matches each forbidden pattern regex against them. CRITICAL matches SHALL cause gate failure. WARNING matches SHALL be logged but not block.

#### Scenario: CRITICAL pattern match blocks merge
- **GIVEN** a forbidden pattern with severity "critical" is configured
- **AND** the diff contains an added line matching the pattern
- **WHEN** the lint gate executes
- **THEN** it SHALL return GateResult("fail")
- **AND** retry_context SHALL include the matched file, line, pattern, and message

#### Scenario: WARNING pattern match does not block
- **GIVEN** a forbidden pattern with severity "warning" is configured
- **AND** the diff contains an added line matching the pattern
- **WHEN** the lint gate executes
- **THEN** it SHALL return GateResult("pass")
- **AND** output SHALL include the warning details

#### Scenario: No pattern matches — pass
- **GIVEN** forbidden patterns are configured
- **AND** no added lines in the diff match any pattern
- **WHEN** the lint gate executes
- **THEN** it SHALL return GateResult("pass")

#### Scenario: No patterns configured — pass
- **GIVEN** profile returns empty list AND project-knowledge.yaml has no forbidden_patterns
- **WHEN** the lint gate executes
- **THEN** it SHALL return GateResult("pass") immediately

### Requirement: Lint patterns shall come from profile and project-knowledge
The lint gate SHALL collect patterns from two sources: `profile.get_forbidden_patterns()` returning a list of pattern dicts, and `project-knowledge.yaml` `verification.forbidden_patterns` section. Both sources SHALL be merged (profile first, then project-knowledge appended).

#### Scenario: Profile provides patterns
- **GIVEN** profile.get_forbidden_patterns() returns `[{pattern: "prisma:\\s*any", severity: "critical", message: "..."}]`
- **WHEN** the lint gate loads patterns
- **THEN** the pattern SHALL be included in the scan

#### Scenario: project-knowledge.yaml provides patterns
- **GIVEN** project-knowledge.yaml contains `verification.forbidden_patterns` with entries
- **WHEN** the lint gate loads patterns
- **THEN** those patterns SHALL be appended after profile patterns

### Requirement: Lint gate shall integrate with gate profiles
GateConfig SHALL include a `lint` field (str: "run", "warn", "skip") with defaults per change_type. The lint gate SHALL respect skip/run/warn semantics like other gates.

#### Scenario: Infrastructure change — lint skipped
- **GIVEN** change_type is "infrastructure"
- **AND** gate profile has lint="skip"
- **WHEN** the lint gate is evaluated
- **THEN** it SHALL be skipped without executing

### Requirement: NullProfile shall provide get_forbidden_patterns interface
NullProfile SHALL define `get_forbidden_patterns() -> list` returning an empty list. Project-type plugins MAY override to provide framework-specific patterns.
