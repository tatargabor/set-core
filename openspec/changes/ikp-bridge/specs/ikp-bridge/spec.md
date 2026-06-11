## ADDED Requirements

## IN SCOPE
- IKP project config loading (`.ikp.yaml`)
- Pack availability checking (`_ikp_available()`)
- Pipeline activation detection (`has_ikp_pipeline()`)
- Phase-based layer loading (decompose → L1+L2, dispatch → L1+L3, verify → L1+L4)
- Rule file injection into worktree `.claude/rules/`
- Graceful degradation when ikp package not installed

## OUT OF SCOPE
- IKP pack authoring, generation, or validation
- Remote pack registry support
- MCP server integration
- L5 Operations/deploy layer consumption
- Automatic pack detection from spec text (that's ikp-decomposer-dispatch)

### Requirement: IKP config loading
The system SHALL load IKP configuration from `.ikp.yaml` at the project root. The config file SHALL declare pack names, pack source directory, and default implementation language. The system SHALL expand `~` in `packs_dir` paths. The system SHALL return None if no `.ikp.yaml` exists.

#### Scenario: Valid config file
- **WHEN** `.ikp.yaml` exists at project root with `packs`, `packs_dir`, and `language` fields
- **THEN** the system SHALL return an `IkpConfig` with parsed values and expanded `packs_dir` path

#### Scenario: Missing config file
- **WHEN** no `.ikp.yaml` exists at project root
- **THEN** the system SHALL return None
- **AND** SHALL NOT log an error (absence is expected for non-IKP projects)

#### Scenario: Config with tilde in packs_dir
- **WHEN** `packs_dir` is `~/code2/ikp/packs`
- **THEN** the system SHALL expand to the user's home directory absolute path

### Requirement: IKP pipeline detection
The system SHALL determine whether the IKP pipeline is active via `has_ikp_pipeline()`. The function SHALL check: (1) the `ikp_pipeline` directive is not `"none"`, (2) the ikp Python package is importable, (3) a valid `.ikp.yaml` exists with at least one pack declared.

#### Scenario: All conditions met
- **WHEN** `ikp_pipeline` directive is `"auto"` and ikp package is installed and `.ikp.yaml` declares packs
- **THEN** `has_ikp_pipeline()` SHALL return True

#### Scenario: Directive disabled
- **WHEN** `ikp_pipeline` directive is `"none"`
- **THEN** `has_ikp_pipeline()` SHALL return False without checking package or config

#### Scenario: Package not installed
- **WHEN** `ikp_pipeline` directive is `"auto"` but ikp package cannot be imported
- **THEN** `has_ikp_pipeline()` SHALL return False
- **AND** SHALL log a debug message (not warning — absence is expected on some machines)

#### Scenario: No packs declared
- **WHEN** `.ikp.yaml` exists but `packs` list is empty
- **THEN** `has_ikp_pipeline()` SHALL return False

### Requirement: Phase-based context loading
The system SHALL provide `get_context_for_phase()` that loads the appropriate IKP layers based on the orchestration phase. The function SHALL accept a phase name, list of pack names, and IkpConfig.

#### Scenario: Decompose phase
- **WHEN** phase is `"decompose"` and packs are `["billingo", "wise-payments"]`
- **THEN** the system SHALL load L1 (knowledge) + L2 (planning) for each pack
- **AND** SHALL return a markdown string with per-pack sections including capabilities, complexity, and pitfalls

#### Scenario: Dispatch phase
- **WHEN** phase is `"dispatch"` and packs are `["billingo"]` and language is `"typescript"`
- **THEN** the system SHALL load L1 (auth, errors) + L3 (implementation, filtered to typescript)
- **AND** SHALL return the combined content

#### Scenario: Verify phase
- **WHEN** phase is `"verify"` and packs are `["billingo"]`
- **THEN** the system SHALL load L4 (testing) + L1 (error catalog)
- **AND** SHALL return content with sandbox setup, mock strategies, test fixtures, and edge cases

#### Scenario: Pack not found
- **WHEN** a requested pack name does not exist in `packs_dir`
- **THEN** the system SHALL log a warning and skip that pack
- **AND** SHALL NOT raise an exception

### Requirement: Rule file injection
The system SHALL provide `inject_rules_for_change()` that writes IKP implementation layers as rule files into a worktree's `.claude/rules/` directory. Each pack SHALL produce one rule file named `ikp-<pack-name>.md`.

#### Scenario: Single pack injection
- **WHEN** `inject_rules_for_change()` is called with pack `"billingo"`, phase `"implement"`, language `"typescript"`
- **THEN** the system SHALL create `<wt>/.claude/rules/ikp-billingo.md`
- **AND** the file SHALL contain pack metadata (version, env vars, capabilities) and L3 implementation content

#### Scenario: Multiple packs
- **WHEN** called with packs `["billingo", "wise-payments"]`
- **THEN** the system SHALL create both `ikp-billingo.md` and `ikp-wise-payments.md`

#### Scenario: Rules directory does not exist
- **WHEN** `<wt>/.claude/rules/` does not exist
- **THEN** the system SHALL create the directory before writing files

### Requirement: Graceful degradation
The system SHALL never crash or block orchestration due to IKP-related issues. All IKP bridge functions SHALL catch import errors and pack loading errors, log them, and return empty/default values.

#### Scenario: Import error during operation
- **WHEN** the ikp package raises ImportError during a bridge function call
- **THEN** the function SHALL return its default value (empty string, None, or False)
- **AND** SHALL log the error at WARNING level

#### Scenario: Corrupted pack file
- **WHEN** a pack's `pack.yaml` is malformed
- **THEN** the system SHALL log a warning with pack name and skip it
- **AND** other packs SHALL continue loading normally
