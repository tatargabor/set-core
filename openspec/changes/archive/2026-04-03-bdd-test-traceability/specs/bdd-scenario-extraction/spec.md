## ADDED Requirements

## IN SCOPE
- Parsing `#### Scenario:` blocks from spec files into structured DigestScenario objects
- Extracting WHEN/THEN lines as separate fields
- Generating stable slugs for scenario matching
- Adding scenarios to digest requirement data alongside existing acceptance_criteria

## OUT OF SCOPE
- Modifying how specs are written (existing format is the input)
- Gherkin tooling integration (Cucumber, SpecFlow)
- Parsing Given clauses (specs use WHEN/THEN, not Given/When/Then)
- Removing the existing acceptance_criteria string array (backward compat)

### Requirement: Digest parses scenarios from spec files
The digest parser SHALL extract `#### Scenario:` blocks from spec requirement sections, producing structured `DigestScenario` objects with name, when, then, and slug fields.

#### Scenario: Spec with WHEN/THEN scenarios
- **WHEN** a spec file contains a `### Requirement:` section with one or more `#### Scenario:` subsections using `WHEN`/`THEN` format
- **THEN** the digest SHALL produce a `scenarios` list on the requirement with one `DigestScenario` per scenario block
- **AND** each scenario SHALL have `name` (from heading), `when` (from WHEN line), `then` (from THEN line), and `slug` (kebab-case of name)

#### Scenario: Spec without WHEN/THEN format
- **WHEN** a spec file contains requirements without `#### Scenario:` blocks or without WHEN/THEN format
- **THEN** the `scenarios` list SHALL be empty
- **AND** the existing `acceptance_criteria` string array SHALL still be populated as before

#### Scenario: Multi-line WHEN/THEN
- **WHEN** a scenario has WHEN or THEN spanning multiple lines (with AND continuations)
- **THEN** the parser SHALL concatenate all lines into a single when/then string, joining with "; "

#### Scenario: Scenario slug generation
- **WHEN** a scenario has name "Add single item to cart"
- **THEN** the slug SHALL be "add-single-item-to-cart"
- **AND** slugs SHALL be unique within a requirement (append `-2`, `-3` if duplicates)

### Requirement: Digest API includes scenarios
The digest API endpoint SHALL include the scenarios field in requirement data so the web UI can display them.

#### Scenario: API response with scenarios
- **WHEN** the frontend fetches `/api/{project}/digest`
- **THEN** each requirement in the response SHALL include a `scenarios` array
- **AND** each scenario SHALL have `name`, `when`, `then`, `slug` fields
