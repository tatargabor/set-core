## ADDED Requirements

## IN SCOPE
- Profile interface gains decompose_hints() method
- Hints are natural language strings appended to planning prompt
- Plugin fully controls hint content

## OUT OF SCOPE
- Structured hint types or registries in core
- Changing the planning_rules() mechanism (complementary, not replacement)

### Requirement: NullProfile defines decompose_hints
`NullProfile` in `profile_loader.py` SHALL define `decompose_hints()` returning an empty list.

#### Scenario: NullProfile returns no hints
- **WHEN** no plugin is loaded and NullProfile is active
- **THEN** `profile.decompose_hints()` returns `[]`

### Requirement: Planner appends hints to decompose prompt
`templates.py` SHALL call `profile.decompose_hints()` and append the returned strings to the planning prompt after the planning rules section.

#### Scenario: Plugin hints appear in planning prompt
- **WHEN** the profile returns `["For each product category in the schema enum, create a separate listing page task."]`
- **THEN** the planning prompt includes this text after the planning rules section

#### Scenario: Multiple hints concatenated
- **WHEN** the profile returns 3 hint strings
- **THEN** all 3 are included in the planning prompt, each as a separate paragraph

### Requirement: Hints are self-describing plain text
Each hint SHALL be a complete natural language instruction that the planner can use without additional context. The core does not interpret, filter, or transform hints.

#### Scenario: Hint used as-is
- **WHEN** the plugin returns `"Every new user-facing route must have a corresponding i18n key task."`
- **THEN** the planner sees exactly this text in the prompt — no wrapping, no metadata added
