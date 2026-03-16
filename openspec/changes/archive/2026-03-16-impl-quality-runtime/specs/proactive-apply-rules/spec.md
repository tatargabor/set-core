## ADDED Requirements

### Requirement: Dispatcher injects relevant rules into agent context
The dispatcher SHALL scan task descriptions for keyword patterns and inject matching rule file contents from `.claude/rules/` into the agent's scope enrichment at dispatch time. Rule injection SHALL happen before the agent starts implementation, not reactively during review retries.

#### Scenario: Task with auth keywords triggers auth rule injection
- **WHEN** the dispatcher processes a change whose tasks contain keywords matching the "auth" category (e.g., "login", "session", "middleware", "cookie")
- **THEN** the dispatcher SHALL append the contents of auth-related rule files from `.claude/rules/` to the agent's scope block
- **AND** the injected content SHALL be labeled with a clear section header (e.g., "## Relevant Patterns")

#### Scenario: Task with API keywords triggers API rule injection
- **WHEN** the dispatcher processes a change whose tasks contain keywords matching the "api" category (e.g., "route", "endpoint", "handler", "mutation")
- **THEN** the dispatcher SHALL append API design and security pattern rule files to the agent's scope block

#### Scenario: Task with no matching keywords skips rule injection
- **WHEN** the dispatcher processes a change whose tasks contain no keywords matching any rule category
- **THEN** no rule files SHALL be injected
- **AND** the dispatch SHALL proceed normally without error

#### Scenario: Project without rules directory degrades gracefully
- **WHEN** the dispatcher processes a change in a project that has no `.claude/rules/` directory
- **THEN** rule injection SHALL be skipped without error
- **AND** dispatch SHALL proceed normally

### Requirement: Rule keyword mapping is configurable via profile
The keyword-to-rule-category mapping SHALL be configurable through the profile system, allowing per-project customization of which keywords trigger which rule files.

#### Scenario: Profile provides custom keyword mapping
- **WHEN** the project profile defines a `rule_keyword_mapping()` method
- **THEN** the dispatcher SHALL use the profile's mapping instead of the built-in default

#### Scenario: Profile does not provide keyword mapping
- **WHEN** the project profile does not define a `rule_keyword_mapping()` method
- **THEN** the dispatcher SHALL use the built-in default mapping with categories: auth, api, database
