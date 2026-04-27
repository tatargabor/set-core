# merge-worktree Specification

## Purpose
Merge worktree branches to target with multi-layer automatic conflict resolution (generated files, JSON deep merge, LLM resolution).
## Requirements
### Requirement: Merge worktree branch to target
The `set-merge` command SHALL merge a worktree's branch into a target branch with multi-layer automatic conflict resolution.

#### Scenario: Basic merge
- **WHEN** user runs `set-merge <change-id>`
- **THEN** the system SHALL resolve the project and worktree path
- **AND** determine the source branch from the worktree HEAD
- **AND** auto-detect the target branch (main)
- **AND** fetch, checkout target, pull latest, then merge the source branch

#### Scenario: Squash merge
- **WHEN** user runs `set-merge <change-id> --squash`
- **THEN** the system SHALL squash all commits into one merge commit

#### Scenario: Custom target branch
- **WHEN** user runs `set-merge <change-id> --to develop`
- **THEN** the system SHALL merge into the `develop` branch instead of main

#### Scenario: No push after merge
- **WHEN** user runs `set-merge <change-id> --no-push`
- **THEN** the system SHALL NOT push to origin after merge

#### Scenario: Keep source branch
- **WHEN** user runs `set-merge <change-id> --no-delete`
- **THEN** the source branch SHALL NOT be deleted after merge

### Requirement: Multi-layer conflict resolution
The merge command SHALL attempt conflict resolution in a specific order, escalating from cheapest to most expensive.

#### Scenario: Resolution order
- **WHEN** a merge produces conflicts
- **THEN** the system SHALL attempt resolution in this order:
  1. Auto-resolve generated/build files (accept "ours")
  2. Programmatic package.json deep merge (jq-based)
  3. Programmatic JSON file deep merge (translation/config files)
  4. LLM-based conflict resolution (only with `--llm-resolve` flag)
- **AND** after each step, check if conflicts remain before proceeding to the next

### Requirement: Generated file auto-resolution
The system SHALL auto-resolve conflicts in generated/build files by accepting the target branch version ("ours").

#### Scenario: Generated file patterns
- **WHEN** a conflicted file matches a generated file pattern (tsconfig.tsbuildinfo, lock files, dist/**, build/**, .next/**, .claude/reflection.md)
- **THEN** the conflict SHALL be resolved with `git checkout --ours` and staged

#### Scenario: Partial mode with LLM resolve
- **WHEN** `--llm-resolve` is active and conflicts include both generated and non-generated files
- **THEN** generated files SHALL be auto-resolved even though non-generated conflicts remain

### Requirement: Programmatic package.json deep merge
The system SHALL resolve package.json conflicts using jq-based recursive deep merge.

#### Scenario: Additive dependency conflict
- **WHEN** both branches add different dependencies to package.json
- **THEN** the deep merge SHALL keep entries from both sides
- **AND** for scalar conflicts, prefer the source branch (feature being merged)

#### Scenario: Invalid JSON
- **WHEN** either branch's package.json is not valid JSON
- **THEN** the programmatic merge SHALL skip and fall through to the next resolution layer

### Requirement: Programmatic JSON file deep merge
The system SHALL resolve conflicts in non-package.json JSON files (translation files, config files) using the same jq deep merge strategy.

#### Scenario: Translation file conflict
- **WHEN** a `.json` file (not package.json) has merge conflicts
- **THEN** the system SHALL attempt jq deep merge with the same additive strategy

### Requirement: LLM-based conflict resolution
When `--llm-resolve` flag is active, the system SHALL use Claude to resolve remaining conflicts.

#### Scenario: LLM prompt construction
- **WHEN** LLM resolution is attempted
- **THEN** the system SHALL extract only conflict hunks with 3 lines of context (not entire files) to minimize prompt size
- **AND** include additive pattern guidance in the prompt

#### Scenario: Model escalation
- **WHEN** total conflict lines exceed 200
- **THEN** the system SHALL use opus directly (skip sonnet)
- **WHEN** total conflict lines are 200 or fewer
- **THEN** the system SHALL try sonnet first, escalate to opus on failure

#### Scenario: LLM output parsing
- **WHEN** LLM returns resolved files
- **THEN** the system SHALL parse `--- FILE: <path> ---` headers and write each file's content
- **AND** verify no conflict markers remain after resolution

### Requirement: Pre-merge state management
The system SHALL handle uncommitted changes in both worktree and main repo before merging.

#### Scenario: Uncommitted non-generated changes in worktree
- **WHEN** the worktree has uncommitted changes in non-generated files
- **THEN** the system SHALL auto-commit them with message "chore: auto-commit remaining changes before merge"

#### Scenario: Uncommitted generated changes in worktree
- **WHEN** the worktree has uncommitted changes only in generated files
- **THEN** the system SHALL auto-stash them

#### Scenario: Uncommitted changes in main repo
- **WHEN** the main repo has uncommitted tracked changes
- **THEN** the system SHALL stash them before merge and restore after

### Requirement: Untracked file handling
The system SHALL handle untracked files that block merge.

#### Scenario: Untracked files would be overwritten
- **WHEN** git merge fails because untracked working tree files would be overwritten
- **THEN** the system SHALL remove the blocking untracked files
- **AND** retry the merge

### Requirement: Post-merge cleanup
The system SHALL push and clean up after successful merge.

#### Scenario: Push to origin
- **WHEN** merge succeeds and `--no-push` is not set
- **THEN** the system SHALL push the target branch to origin

#### Scenario: Delete source branch
- **WHEN** merge succeeds and `--no-delete` is not set
- **THEN** the system SHALL delete the source branch (force-delete for squash case)
- **AND** if branch is still checked out in worktree, inform user to run `set-close`

### Requirement: set-merge accepts explicit worktree path

The `set-merge` command SHALL accept a `--worktree <path>` option. When provided, the command SHALL use that path directly and skip name-based discovery.

#### Scenario: Explicit worktree path accepted
- **WHEN** user runs `set-merge foo --worktree /repos/acme-wt-foo-2`
- **THEN** `set-merge` SHALL use `/repos/acme-wt-foo-2` as the worktree path
- **AND** SHALL NOT call `find_existing_worktree`

#### Scenario: Explicit path does not exist
- **WHEN** `--worktree /some/missing/path` is given
- **AND** the path does not exist or is not a directory
- **THEN** the command SHALL exit with a non-zero status and an error message naming the bad path

#### Scenario: Explicit path is not a registered git worktree
- **WHEN** `--worktree <path>` points at a directory that is not listed by `git worktree list --porcelain`
- **THEN** the command SHALL exit with a non-zero status and an error message clarifying that the directory is not a worktree

#### Scenario: No --worktree flag — discovery fallback
- **WHEN** user runs `set-merge foo` without `--worktree`
- **THEN** `find_existing_worktree` SHALL be called as before
- **AND** the discovery result SHALL be used to locate the worktree

### Requirement: set-merge help documents --worktree

The `set-merge --help` output SHALL list `--worktree <path>` among the options with a one-line description.

#### Scenario: Help lists the flag
- **WHEN** user runs `set-merge --help`
- **THEN** the output SHALL include `--worktree <path>` and a short description such as "use this explicit worktree path instead of discovering by name"

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
