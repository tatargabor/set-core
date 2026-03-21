## ADDED Requirements

## IN SCOPE
- Merger loads plugin merge strategies via profile method
- Strategies define file-pattern to merge-behavior mappings
- Protected files get special handling during merge

## OUT OF SCOPE
- Changing the merge_strategies() interface (already defined in NullProfile)
- Adding new merge strategy types beyond theirs/ours

### Requirement: Merger calls profile merge_strategies
`merger.py` SHALL call `profile.merge_strategies()` before executing merge operations and apply the returned strategies to file-level merge decisions.

#### Scenario: Lockfile gets theirs-wins strategy
- **WHEN** the profile returns a strategy `{"patterns": ["*.lock", "pnpm-lock.yaml"], "strategy": "theirs"}`
- **AND** a merge conflict occurs in `pnpm-lock.yaml`
- **THEN** the merger resolves the conflict using the remote (theirs) version

#### Scenario: Schema file gets ours-wins strategy
- **WHEN** the profile returns a strategy `{"patterns": ["prisma/schema.prisma"], "strategy": "ours"}`
- **AND** a merge conflict occurs in `prisma/schema.prisma`
- **THEN** the merger resolves the conflict using the local (ours) version

#### Scenario: No strategies defined
- **WHEN** `profile.merge_strategies()` returns `[]`
- **THEN** the merger uses default merge behavior for all files (no special handling)
