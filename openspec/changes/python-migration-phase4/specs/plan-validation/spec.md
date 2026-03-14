## ADDED Requirements

### Requirement: Plan JSON structure validation
`validate_plan(plan_path)` SHALL validate the plan JSON file and return a `ValidationResult` with a list of errors. It SHALL check:
- Valid JSON structure
- Required fields present: `plan_version`, `brief_hash`, `changes`
- Each change has required fields: `name`, `scope`, `complexity`

#### Scenario: Valid plan passes validation
- **WHEN** `validate_plan("plan.json")` is called with a well-formed plan
- **THEN** the result has zero errors

#### Scenario: Invalid JSON
- **WHEN** the plan file contains invalid JSON
- **THEN** the result contains an error "Plan file is not valid JSON"

#### Scenario: Missing required fields
- **WHEN** the plan JSON lacks `brief_hash`
- **THEN** the result contains an error "Plan missing required field: brief_hash"

### Requirement: Change name kebab-case enforcement
`validate_plan()` SHALL verify all change names match the pattern `^[a-z][a-z0-9-]*$`.

#### Scenario: Valid kebab-case names
- **WHEN** all change names are like "add-auth", "fix-login-bug"
- **THEN** no name-related errors are returned

#### Scenario: Invalid change names
- **WHEN** a change name is "AddAuth" or "add_auth"
- **THEN** the result contains an error listing the invalid names

### Requirement: Dependency reference validation
`validate_plan()` SHALL verify all `depends_on` references point to existing change names in the same plan.

#### Scenario: Valid dependency references
- **WHEN** change "b" has `depends_on: ["a"]` and change "a" exists
- **THEN** no dependency-related errors are returned

#### Scenario: Missing dependency target
- **WHEN** change "b" has `depends_on: ["nonexistent"]`
- **THEN** the result contains an error "depends_on references non-existent changes: nonexistent"

### Requirement: Circular dependency detection
`validate_plan()` SHALL detect circular dependencies using topological sort from `state.py`.

#### Scenario: Circular dependency
- **WHEN** change "a" depends on "b" and "b" depends on "a"
- **THEN** the result contains an error "Circular dependency detected in change graph"

#### Scenario: No circular dependency
- **WHEN** the dependency graph is a valid DAG
- **THEN** no circularity errors are returned

### Requirement: Scope overlap detection
`check_scope_overlap(plan_path, state_path=None, pk_path=None)` SHALL compute pairwise Jaccard similarity between change scopes using keyword extraction (3+ char lowercase words). It SHALL warn when similarity >= 40%.

#### Scenario: No overlap between distinct scopes
- **WHEN** change "add-auth" has scope "authentication login JWT" and "add-export" has scope "CSV data export download"
- **THEN** no overlap warnings are returned

#### Scenario: High overlap detected
- **WHEN** two changes have scope keyword similarity >= 40%
- **THEN** a warning is returned with the change names and similarity percentage

#### Scenario: Overlap with active worktree changes
- **WHEN** a state file is provided with running/dispatched changes
- **THEN** scope overlap is also checked between new plan changes and active changes

#### Scenario: Cross-cutting file hazard detection
- **WHEN** a project-knowledge.yaml is provided with cross_cutting_files
- **AND** multiple changes mention the same cross-cutting file in their scope
- **THEN** a warning is returned listing the file and touching changes

#### Scenario: Insufficient keywords skipped
- **WHEN** a change scope has fewer than 3 words of 3+ characters
- **THEN** that change is excluded from pairwise comparison

### Requirement: Digest-mode requirement coverage validation
`validate_plan()` SHALL, in digest mode, verify that plan change requirements and also_affects_reqs reference valid requirement IDs from the digest's requirements.json.

#### Scenario: Valid requirement references
- **WHEN** all requirement IDs in the plan exist in requirements.json
- **THEN** no coverage-related warnings are returned

#### Scenario: Invalid requirement reference
- **WHEN** a plan change references requirement ID "REQ-999" not in requirements.json
- **THEN** a warning is returned (non-fatal) noting the invalid reference

#### Scenario: also_affects_reqs without primary owner
- **WHEN** a requirement ID appears in also_affects_reqs but not in any change's primary requirements
- **THEN** a warning is returned noting the missing primary owner

### Requirement: Test infrastructure detection
`detect_test_infra(project_dir)` SHALL scan the project directory and return a `TestInfra` dataclass with: framework (vitest/jest/pytest/mocha/""), config_exists (bool), test_file_count (int), has_helpers (bool), test_command (str).

#### Scenario: Vitest project detected
- **WHEN** the project has a `vitest.config.ts` file
- **THEN** framework is "vitest", config_exists is true

#### Scenario: Pytest project detected
- **WHEN** `pyproject.toml` contains `[tool.pytest`
- **THEN** framework is "pytest", config_exists is true

#### Scenario: Test command from package.json
- **WHEN** package.json has `scripts.test: "vitest"`
- **THEN** test_command is detected using package manager from lockfile (e.g., "pnpm run test")

#### Scenario: No test infrastructure
- **WHEN** no framework config, no test files found
- **THEN** framework is "", config_exists is false, test_file_count is 0
