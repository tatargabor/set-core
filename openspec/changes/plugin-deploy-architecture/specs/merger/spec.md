## MODIFIED Requirements

### Requirement: Merger applies plugin merge strategies
`merger.py` SHALL call `profile.merge_strategies()` before merge operations and apply the returned file-protection strategies to conflict resolution.

#### Scenario: Merge strategies applied
- **WHEN** a merge starts and the profile returns strategies for lockfiles and schema files
- **THEN** conflicting lockfiles are resolved with theirs-wins and schema files with ours-wins

#### Scenario: No merge strategies defined
- **WHEN** `profile.merge_strategies()` returns `[]`
- **THEN** all files use default merge behavior (existing behavior preserved)
