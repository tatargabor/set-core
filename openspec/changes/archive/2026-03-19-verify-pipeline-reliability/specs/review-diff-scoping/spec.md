# Spec: review-diff-scoping

## ADDED Requirements

## IN SCOPE
- Computing the correct merge-base for review diffs using `git merge-base`
- Ensuring review diffs only contain files modified by the change branch
- Eliminating the `HEAD~5` fallback that includes unrelated scaffold files

## OUT OF SCOPE
- Changing the review prompt template or review criteria
- Modifying how review results are parsed or acted upon
- Adding file-level exclusion patterns for specific file types

### Requirement: Review diff uses true fork point

The verify gate's code review SHALL compute the diff using `git merge-base HEAD main` to determine the true fork point, not a fallback chain that may resolve to an incorrect base.

#### Scenario: Worktree branched before scaffold addition
- **WHEN** a worktree branch was created before scaffold files were added to main
- **AND** the review diff is computed
- **THEN** the diff SHALL NOT include scaffold files that were added to main after the branch was created

#### Scenario: Merge-base resolution failure
- **WHEN** `git merge-base HEAD main` fails (e.g., orphan branch, shallow clone)
- **THEN** the system SHALL fall back to `HEAD~10` and log a warning, not silently use an incorrect base

### Requirement: Review diff excludes unchanged files

The review diff SHALL only include files that differ between the change branch HEAD and the merge-base, excluding files that are identical on both sides.

#### Scenario: Scaffold file identical on branch and main
- **WHEN** a file exists on both the change branch and main with identical content
- **THEN** the file SHALL NOT appear in the review diff
