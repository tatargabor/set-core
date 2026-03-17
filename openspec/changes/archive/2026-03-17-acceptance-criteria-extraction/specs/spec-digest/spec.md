## MODIFIED Requirements

### Requirement: Requirement extraction
The digest LLM SHALL extract discrete, independently testable requirements from feature spec files. Each extracted requirement SHALL include: `id`, `title`, `source`, `source_section`, `domain`, `brief`, and `acceptance_criteria`.

The `acceptance_criteria` field SHALL be an array of concrete, verifiable condition strings — HTTP contracts, state assertions, error responses, or behavioral outcomes. Maximum 5 items per requirement. If the spec has no explicit testable conditions for a requirement, the array SHALL be empty.

#### Scenario: AC extracted from explicit spec scenarios
- **WHEN** a spec file contains explicit WHEN/THEN scenarios or acceptance conditions for a requirement
- **THEN** each distinct testable outcome SHALL become one AC string in `acceptance_criteria`
- **AND** AC items SHALL be concrete (e.g., `"POST /api/cart/items → 201 with cartItemId"`) not vague descriptions

#### Scenario: AC array empty when spec is vague
- **WHEN** a spec file describes a requirement without explicit testable conditions
- **THEN** `acceptance_criteria` SHALL be `[]`
- **AND** the requirement SHALL still be extracted with `brief` populated

#### Scenario: AC capped at 5 items
- **WHEN** a requirement has more than 5 distinct testable behaviors
- **THEN** the LLM SHALL extract the 5 most critical AC items
- **AND** the requirement SHOULD be flagged as a candidate for splitting in the `brief`

#### Scenario: Old digest files without AC field
- **WHEN** an existing `requirements.json` was generated before this change and lacks `acceptance_criteria`
- **THEN** consumers SHALL treat the missing field as `[]` and fall back to `brief`
- **AND** no migration or re-digest is required for existing projects
