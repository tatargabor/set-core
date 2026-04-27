# Spec Context Dispatch Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

## Requirements

### Requirement: Spec base directory resolution
The dispatcher SHALL resolve the spec base directory from `index.json`'s `spec_base_dir` field. This absolute path is used to locate raw spec files for copying.

#### Scenario: Spec base dir read from index.json
- **WHEN** `dispatch_change()` runs and `set/orchestration/digest/index.json` exists
- **THEN** `spec_base_dir` is read via `jq -r '.spec_base_dir' set/orchestration/digest/index.json`
- **AND** it is used as the root for resolving `spec_files[]` relative paths

#### Scenario: Missing spec file at dispatch time
- **WHEN** a `spec_files[]` entry does not resolve to an existing file under `spec_base_dir`
- **THEN** the dispatcher logs a warning: "Spec file not found: <path>" and continues (non-fatal)

### Requirement: Spec files copied to worktree
When dispatching a change, the dispatcher SHALL copy the raw spec files listed in the change's `spec_files[]` from the plan to `.claude/spec-context/` in the worktree, preserving directory structure.

#### Scenario: Spec files available in worktree
- **WHEN** `dispatch_change("cart-feature")` runs and plan has `spec_files: ["features/cart-checkout.md", "features/promotions.md"]`
- **THEN** `.claude/spec-context/features/cart-checkout.md` and `.claude/spec-context/features/promotions.md` exist in the worktree
- **AND** file contents are identical to the original spec files

#### Scenario: No spec files in plan (backward compat)
- **WHEN** a change has no `spec_files` field (legacy plan without digest)
- **THEN** dispatch proceeds as before, no `.claude/spec-context/` directory is created

### Requirement: Proposal references spec context
The pre-created `proposal.md` in the worktree SHALL include a "Source Specifications" section listing the copied spec files with their paths.

#### Scenario: Proposal includes spec references
- **WHEN** dispatcher creates `proposal.md` for `cart-feature` with 2 spec files
- **THEN** proposal.md contains a "Source Specifications" section with paths to `.claude/spec-context/features/*.md` files

### Requirement: Spec context directory cleanup
The `.claude/spec-context/` directory SHALL be treated as read-only reference material. It SHALL be excluded from git via `.gitignore`.

#### Scenario: Spec context not committed
- **WHEN** the agent commits implementation changes
- **THEN** `.claude/spec-context/` files are not included in the commit

#### Scenario: Gitignore entry added
- **WHEN** dispatcher copies spec files to `.claude/spec-context/`
- **THEN** `.claude/spec-context/` is present in the worktree's `.gitignore`

### Requirement: Conventions dispatched to all worktrees
The dispatcher SHALL copy `conventions.json` and `data-definitions.md` from the digest directory to `.claude/spec-context/` in **every** dispatched worktree, regardless of the change's `spec_files[]` contents.

#### Scenario: Conventions available in all worktrees
- **WHEN** `dispatch_change()` runs for any change and `set/orchestration/digest/conventions.json` exists
- **THEN** `.claude/spec-context/conventions.json` exists in the worktree
- **AND** `.claude/spec-context/data-definitions.md` exists in the worktree (if present in digest)

#### Scenario: No conventions in digest (simple spec)
- **WHEN** `dispatch_change()` runs and `set/orchestration/digest/conventions.json` does not exist
- **THEN** dispatch proceeds without copying conventions (no error)

### Requirement: Cross-cutting requirements in proposal
The pre-created `proposal.md` SHALL include cross-cutting requirements from `also_affects_reqs[]` in a separate section, so the agent knows which project-wide constraints it must incorporate.

#### Scenario: Cross-cutting requirements listed in proposal
- **WHEN** dispatcher creates proposal.md for `user-auth` with `also_affects_reqs: ["REQ-I18N-003"]`
- **THEN** proposal.md contains a "Cross-Cutting Requirements" section listing `REQ-I18N-003` with its title, brief, and a note: "This requirement is owned by another change — incorporate its constraints, do not re-implement from scratch."

### Requirement: Requirements summary in proposal
The pre-created `proposal.md` SHALL include the requirement IDs assigned to this change from coverage.json, so the agent knows exactly which requirements it must implement.

#### Scenario: Requirement IDs in proposal
- **WHEN** dispatcher creates proposal.md for `cart-feature` with `requirements: ["REQ-CART-001", "REQ-CART-002", "REQ-PROMO-001"]`
- **THEN** proposal.md contains a "Requirements" section listing these IDs with their titles and briefs from requirements.json
