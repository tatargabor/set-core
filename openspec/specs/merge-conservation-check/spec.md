# Merge Conservation Check Specification

## Purpose

TBD — restored after delta-sync structural cleanup. Update Purpose with a one-line statement of what this capability owns.

### In scope
- Post-LLM diff-based conservation check on every conflicted file
- Detecting additions lost from either side of a merge
- Hard-blocking merges where conservation check fails
- Logging exactly which lines/additions were lost
- Tracking which files were LLM-resolved (passed from resolver to check)
- `--no-conservation-check` escape hatch flag

### Out of scope
- Automatic repair of failed merges (block only, no auto-fix)
- Non-conflicted files (only files that went through LLM resolution)
- Whitespace-only or formatting-only differences
- Binary files (detected via `git diff --numstat` null markers)

## Requirements

### Requirement: Diff-based conservation check after LLM merge
After `llm_resolve_conflicts()` resolves conflicted files and BEFORE `git commit`, `set-merge` SHALL run a conservation check on every file that was LLM-resolved. The check SHALL verify that additions from both sides of the merge are present in the resolved output. The `llm_resolve_conflicts()` function SHALL record which files it resolved (via a bash array or temp file) so the conservation check knows which files to verify.

#### Scenario: Both sides add content and LLM preserves all
- **WHEN** file F has conflict between branch A (adds lines LA) and branch B (adds lines LB) relative to merge-base
- **AND** the LLM-resolved version of F contains all lines from LA and all lines from LB
- **THEN** the conservation check SHALL pass for file F

#### Scenario: LLM drops additions from one side
- **WHEN** file F has conflict between branch A (adds lines LA) and branch B (adds lines LB) relative to merge-base
- **AND** the LLM-resolved version of F is missing one or more lines from LA or LB
- **THEN** the conservation check SHALL fail for file F
- **AND** the check SHALL log which lines were lost and from which side

#### Scenario: Conservation check failure blocks merge
- **WHEN** the conservation check fails for any file
- **THEN** `set-merge` SHALL abort the in-progress merge (the check runs BEFORE `git commit --no-edit`, so the merge is still uncommitted; use `git reset --merge` to abort)
- **AND** exit with non-zero status
- **AND** log a message: "MERGE BLOCKED: conservation check failed — additions lost in {file}"

#### Scenario: Additions comparison uses semantic line matching
- **WHEN** comparing additions between the pre-merge versions and the LLM-resolved output
- **THEN** the check SHALL use line-content matching (ignoring leading/trailing whitespace)
- **AND** SHALL NOT require lines to appear in the same order
- **AND** SHALL ignore blank lines and comment-only lines in the diff

#### Scenario: Bypass via flag
- **WHEN** `set-merge` is called with `--no-conservation-check`
- **THEN** the conservation check SHALL be skipped entirely
- **AND** the merge SHALL proceed as if no conservation check exists

### Requirement: Conservation check computes additions from merge-base
The conservation check SHALL compute "additions" as lines present in a branch version but not in the merge-base version, ensuring only genuinely new content is checked.

#### Scenario: Computing additions relative to merge-base
- **WHEN** running conservation check on file F
- **THEN** the check SHALL retrieve the merge-base version of F via `git show <merge-base>:F`
- **AND** compute ours_added = lines in ours but not in base
- **AND** compute theirs_added = lines in theirs but not in base
- **AND** verify both ours_added and theirs_added are present in the merged result

#### Scenario: File is new on one side only
- **WHEN** file F exists only on one branch (not in merge-base or other branch)
- **THEN** the conservation check SHALL pass (no additions to lose from the non-existent side)

#### Scenario: File is new on both sides
- **WHEN** file F does not exist in merge-base but exists on both branches with conflicting content
- **THEN** the conservation check SHALL treat the merge-base version as empty
- **AND** compute ours_added = all lines in ours, theirs_added = all lines in theirs
- **AND** verify both are present in the merged result

#### Scenario: Binary files are skipped
- **WHEN** file F is a binary file (detected via `git diff --numstat` showing `-` for additions/deletions)
- **THEN** the conservation check SHALL skip F (no line-based comparison possible)

#### Scenario: Delete/modify conflict
- **WHEN** file F is deleted on one side and modified on the other
- **THEN** the conservation check SHALL skip F (deletion is an intentional action, not data loss)

### Requirement: Conservation check logs detailed report
When the conservation check fails, it SHALL produce a detailed report showing exactly what was lost.

#### Scenario: Detailed loss report
- **WHEN** conservation check fails for file F
- **THEN** the log SHALL include:
  - File path
  - Number of additions from each side (ours: N, theirs: M)
  - Number of missing additions (lost from ours: X, lost from theirs: Y)
  - Up to 10 sample lost lines from each side
