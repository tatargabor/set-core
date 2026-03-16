## ADDED Requirements

### Requirement: Archive stages source deletion
When archiving a change, the git staging SHALL include both the new archive location AND the deletion of the source directory.

#### Scenario: Archive commit includes source deletion
- **WHEN** `archive_change("cart-actions")` runs
- **THEN** `openspec/changes/cart-actions/` SHALL be removed from the git index
- **AND** `openspec/changes/archive/2026-03-16-cart-actions/` SHALL be added to the git index
- **AND** a single commit SHALL contain both changes
- **AND** after merging, `openspec/changes/cart-actions/` SHALL NOT reappear in the main branch

#### Scenario: Archive with git add -A scoped to openspec/changes/
- **WHEN** `archive_change()` runs
- **THEN** the git stage command SHALL be scoped to `openspec/changes/` only
- **AND** SHALL NOT stage unrelated changes from the working tree

### Requirement: Archive triggers spec sync
When archiving a change, delta specs from the change directory SHALL be merged into the main `openspec/specs/` directory.

#### Scenario: Delta spec merged into main specs
- **WHEN** `archive_change("auth-foundation")` runs
- **AND** `openspec/changes/auth-foundation/specs/auth-foundation/spec.md` exists
- **THEN** the spec content SHALL be applied to `openspec/specs/auth-foundation/spec.md`
- **AND** if `openspec/specs/auth-foundation/spec.md` does not exist, it SHALL be created
- **AND** the merge commit SHALL include both the archived change AND the updated main spec

#### Scenario: Multiple delta specs in one change
- **WHEN** a change has specs in `specs/capability-a/spec.md` and `specs/capability-b/spec.md`
- **THEN** both SHALL be synced to `openspec/specs/capability-a/spec.md` and `openspec/specs/capability-b/spec.md`

#### Scenario: No delta specs in change
- **WHEN** `archive_change("test-infrastructure-setup")` runs
- **AND** `openspec/changes/test-infrastructure-setup/specs/` is empty or does not exist
- **THEN** archive proceeds without spec sync (no error)
- **AND** `openspec/specs/` is unchanged

#### Scenario: Change with only proposal.md (incomplete artifact set)
- **WHEN** `archive_change("admin-product-list-crud")` runs
- **AND** the change has only `proposal.md` (no specs/, design.md, tasks.md)
- **THEN** archive proceeds, the incomplete artifact set is archived as-is
- **AND** no spec sync attempt is made (no specs/ directory to sync from)
