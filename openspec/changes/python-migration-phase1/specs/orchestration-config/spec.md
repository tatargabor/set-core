## ADDED Requirements

### Requirement: Duration parsing
The system SHALL provide a `parse_duration()` function that converts human-readable duration strings to seconds. Migrated from: `utils.sh:parse_duration()` L46-73.

#### Scenario: Plain number as minutes
- **WHEN** `parse_duration("30")` is called
- **THEN** it returns `1800` (30 * 60)

#### Scenario: Hours and minutes
- **WHEN** `parse_duration("1h30m")` is called
- **THEN** it returns `5400`

#### Scenario: Hours only
- **WHEN** `parse_duration("2h")` is called
- **THEN** it returns `7200`

#### Scenario: Invalid input
- **WHEN** `parse_duration("abc")` is called
- **THEN** it returns `0` and raises no exception

### Requirement: Duration formatting
The system SHALL provide a `format_duration()` function that formats seconds to human-readable strings. Migrated from: `utils.sh:format_duration()` L119-130.

#### Scenario: Hours and minutes
- **WHEN** `format_duration(5400)` is called
- **THEN** it returns `"1h30m"`

#### Scenario: Hours only
- **WHEN** `format_duration(7200)` is called
- **THEN** it returns `"2h"`

#### Scenario: Minutes only
- **WHEN** `format_duration(300)` is called
- **THEN** it returns `"5m"`

#### Scenario: Zero
- **WHEN** `format_duration(0)` is called
- **THEN** it returns `"0m"`

### Requirement: File hash computation
The system SHALL provide a `brief_hash()` function that computes SHA-256 hash of a file. Migrated from: `utils.sh:brief_hash()` L732-737.

#### Scenario: Hash a file
- **WHEN** `brief_hash("/path/to/file")` is called
- **THEN** it returns the lowercase hex SHA-256 digest of the file contents

#### Scenario: File not found
- **WHEN** `brief_hash("/nonexistent")` is called
- **THEN** it returns `"unknown"`

### Requirement: Brief next items parsing
The system SHALL provide a `parse_next_items()` function that extracts items from the `### Next` section of a brief file. Migrated from: `utils.sh:parse_next_items()` L227-261.

#### Scenario: Brief with Next section
- **WHEN** a brief file contains `### Next` followed by `- item1` and `- item2`
- **THEN** `parse_next_items()` returns `["item1", "item2"]`

#### Scenario: Brief without Next section
- **WHEN** a brief file has no `### Next` header
- **THEN** `parse_next_items()` returns `[]`

#### Scenario: Next section terminated by another header
- **WHEN** `### Next` is followed by items then `### Done`
- **THEN** only items between `### Next` and `### Done` are returned

### Requirement: Directive parsing from document
The system SHALL provide a `parse_directives()` function that extracts orchestrator directives from a brief/spec document. Migrated from: `utils.sh:parse_directives()` L266-729.

The function SHALL parse the `## Orchestrator Directives` section and extract key-value pairs with validation.

#### Scenario: Valid directives
- **WHEN** a document contains `## Orchestrator Directives` with `max_parallel: 3` and `merge_policy: eager`
- **THEN** the returned dict contains `{"max_parallel": 3, "merge_policy": "eager"}`

#### Scenario: Invalid directive value
- **WHEN** `max_parallel: abc` is found
- **THEN** the default value is used and a warning is logged

#### Scenario: Unknown directive
- **WHEN** an unrecognized key is found
- **THEN** a warning is logged and the key is ignored

#### Scenario: All supported directives
- **WHEN** directives are parsed
- **THEN** the following keys are recognized: `max_parallel`, `merge_policy`, `checkpoint_every`, `test_command`, `notification`, `token_budget`, `token_hard_limit`, `pause_on_exit`, `auto_replan`, `review_before_merge`, `test_timeout`, `max_verify_retries`, `summarize_model`, `review_model`, `default_model`, `smoke_command`, `smoke_timeout`, `smoke_blocking`, `smoke_fix_token_budget`, `smoke_fix_max_turns`, `smoke_fix_max_retries`, `smoke_health_check_url`, `smoke_health_check_timeout`, `smoke_dev_server_command`, `monitor_idle_timeout`, `merge_timeout`, `post_merge_command`, `events_log`, `events_max_size`, `watchdog_timeout`, `watchdog_loop_threshold`, `max_tokens_per_change`, `context_pruning`, `plan_approval`, `checkpoint_auto_approve`, `plan_method`, `model_routing`, `team_mode`, `post_phase_audit`, `hook_pre_dispatch`, `hook_post_verify`, `hook_pre_merge`, `hook_post_merge`, `hook_on_fail`, `milestones_enabled`, `milestones_dev_server`, `milestones_base_port`, `milestones_max_worktrees`, `e2e_port_base`

#### Scenario: Output JSON format
- **WHEN** directives are parsed
- **THEN** the output JSON format is identical to the existing bash implementation (same keys, same types, same null handling)

### Requirement: Config file loading
The system SHALL provide a `load_config_file()` function that loads directives from YAML config. Migrated from: `utils.sh:load_config_file()` L743-784.

#### Scenario: YAML config with PyYAML
- **WHEN** PyYAML is available and config file exists
- **THEN** the file is parsed via `yaml.safe_load()` and returned as dict

#### Scenario: YAML config without PyYAML
- **WHEN** PyYAML is not available
- **THEN** a simple `key: value` parser is used as fallback

#### Scenario: No config file
- **WHEN** config file path is empty or file doesn't exist
- **THEN** an empty dict is returned

### Requirement: Directive resolution with precedence
The system SHALL provide a `resolve_directives()` function that merges directives from multiple sources. Migrated from: `utils.sh:resolve_directives()` L788-819.

Precedence (highest to lowest): CLI flags > config file > in-document directives > defaults.

#### Scenario: CLI override
- **WHEN** CLI provides `max_parallel=5` and config file has `max_parallel: 3`
- **THEN** the resolved value is `5`

#### Scenario: Config overrides document
- **WHEN** config file has `merge_policy: manual` and document has `merge_policy: eager`
- **THEN** the resolved value is `"manual"`

#### Scenario: Directory spec input
- **WHEN** the input is a directory (not a file)
- **THEN** document-level directives are skipped (parse with empty/null input)

### Requirement: Input resolution
The system SHALL provide a `find_input()` function that resolves the orchestration input source. Migrated from: `utils.sh:find_input()` L160-213.

#### Scenario: Spec override (directory)
- **WHEN** `--spec` points to a directory
- **THEN** mode is `"digest"` and path is the absolute directory path

#### Scenario: Spec override (file)
- **WHEN** `--spec` points to a file
- **THEN** mode is `"digest"` and path is the absolute file path

#### Scenario: Brief with Next items
- **WHEN** no `--spec` and brief file exists with non-empty `### Next`
- **THEN** mode is `"brief"` and path is the brief file path

#### Scenario: Short-name spec resolution
- **WHEN** `--spec v6-smoke` is given and `wt/orchestration/specs/v6-smoke.md` exists
- **THEN** mode is `"digest"` and path resolves to that file

### Requirement: Test command auto-detection
The system SHALL provide an `auto_detect_test_command()` function. Migrated from: `utils.sh:auto_detect_test_command()`.

#### Scenario: Node project with test script
- **WHEN** `package.json` contains a `"test"` script
- **THEN** the detected command uses the appropriate package manager (`npm test`, `pnpm test`, etc.)

#### Scenario: No test command found
- **WHEN** no test configuration is found
- **THEN** an empty string is returned

### Requirement: CLI integration
The config module SHALL be callable via `wt-orch-core config` subcommand.

#### Scenario: Parse directives via CLI
- **WHEN** `wt-orch-core config parse-directives --input-file brief.md` is called
- **THEN** it outputs the parsed directives JSON to stdout

#### Scenario: Resolve directives via CLI
- **WHEN** `wt-orch-core config resolve-directives --input-file brief.md` is called
- **THEN** it outputs the resolved directives JSON (with all precedence levels merged) to stdout
