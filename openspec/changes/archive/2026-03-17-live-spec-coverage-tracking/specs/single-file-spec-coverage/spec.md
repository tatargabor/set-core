## NEW Requirements

### Requirement: Source item extraction for single-file specs
When the decompose agent processes a single-file spec (no digest directory), the generated `orchestration-plan.json` SHALL include a `source_items` array at the plan level. Each entry SHALL have: `id` (sequential `SI-N`), `text` (the spec item description), and `change` (the assigned change name, or `null` if intentionally excluded).

#### Scenario: Source items extracted from single-file spec
- **WHEN** the decompose agent processes a single-file spec
- **THEN** `orchestration-plan.json` SHALL contain a `source_items` array
- **AND** each identifiable spec item (feature, requirement, task, checkbox) SHALL have a corresponding entry
- **AND** entries with an assigned change SHALL have `change` set to that change's name
- **AND** entries intentionally excluded SHALL have `change: null`

#### Scenario: Source items absent in digest mode
- **WHEN** the decompose agent processes a spec with an existing digest (`wt/orchestration/digest/`)
- **THEN** `source_items` SHALL be omitted from the plan (digest mode uses `requirements.json` instead)

#### Scenario: Validate source items in non-digest mode
- **WHEN** `validate_plan()` runs on a plan with `source_items` and no `digest_dir`
- **THEN** entries with `change: null` SHALL produce warnings (not errors)
- **AND** entries referencing a non-existent change name SHALL produce errors
- **AND** if `source_items` is absent in non-digest mode, a warning SHALL be emitted

## IN SCOPE
- `source_items` array schema and generation instruction in decompose SKILL.md
- `validate_plan()` validation for `source_items` in non-digest mode
- Plan JSON schema extension

## OUT OF SCOPE
- Digest pipeline changes (uses `requirements.json`, unaffected)
- Source item ID stability across replans
- Automatic spec annotation (modifying the original markdown file)
