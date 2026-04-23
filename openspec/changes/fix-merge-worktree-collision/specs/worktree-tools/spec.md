## ADDED Requirements

### Requirement: find_existing_worktree resolves ambiguity deterministically

The bash `find_existing_worktree` helper in `bin/set-common.sh` SHALL collect all candidate matches across every name-pattern variant (`{change_id}`, `{repo}-{change_id}`, `{repo}-wt-{change_id}`, `{repo}-{change_id}-N`, `{repo}-wt-{change_id}-N`), then return a deterministic single path and emit a WARNING when multiple candidates exist so operators can audit the resolution.

#### Scenario: Single unambiguous match
- **WHEN** only one worktree matches `<change-id>` across all name-pattern variants
- **THEN** `find_existing_worktree` SHALL return that path
- **AND** SHALL NOT emit a WARNING

#### Scenario: Multiple bash-convention suffixes — highest wins
- **WHEN** both `<project>-wt-<change>` and `<project>-wt-<change>-2` exist as worktrees
- **THEN** `find_existing_worktree` SHALL return the `-2` variant
- **AND** SHALL emit a WARNING listing all candidate paths and noting which was selected

#### Scenario: Multiple Python-convention suffixes — highest wins
- **WHEN** both `<project>-<change>` (no `-wt-` infix) and `<project>-<change>-2` exist as worktrees (e.g. created by the Python dispatcher's direct `git worktree add`)
- **THEN** `find_existing_worktree` SHALL recognise both as matches
- **AND** return the `-2` variant
- **AND** emit a WARNING with all candidates

#### Scenario: Mixed-convention ambiguity
- **WHEN** both `<project>-wt-<change>` (bash convention) and `<project>-<change>` (Python convention) exist
- **THEN** `find_existing_worktree` SHALL treat them as ambiguous candidates
- **AND** emit a WARNING listing both
- **AND** prefer the one matching the current project's creation convention (as configured or detected), falling back to the bash convention if undetermined

#### Scenario: Three-level suffix ranking
- **WHEN** `<change>-2` and `<change>-3` both exist as worktrees
- **THEN** the `-3` variant SHALL be returned
- **AND** the WARNING SHALL list all candidates

#### Scenario: No matches
- **WHEN** no worktree matches any pattern variant
- **THEN** `find_existing_worktree` SHALL echo an empty string (existing behavior preserved)

#### Scenario: WARNING is idempotent and non-fatal
- **WHEN** ambiguity is detected and a WARNING is emitted
- **THEN** the command SHALL still return a valid path (not fail)
- **AND** the caller's exit status SHALL be 0 (ambiguity is not an error to the caller)

### Requirement: Python _find_existing_worktree uses exact basename match

The dispatcher's Python `_find_existing_worktree` (`lib/set_orch/dispatcher.py`) SHALL match worktree basenames exactly against both naming conventions, not by substring.

#### Scenario: Exact match against both conventions
- **WHEN** `_find_existing_worktree(project, "foo")` is called
- **THEN** it SHALL match a worktree whose basename equals `{project_name}-foo` OR `{project_name}-wt-foo`
- **AND** it SHALL NOT match `{project_name}-foobar` or `{project_name}-wt-foobar-2` (substring false-positives)

#### Scenario: Suffix variants recognised by same rule as bash helper
- **WHEN** multiple suffix variants match the basename rule (e.g., `{project}-foo-2` AND `{project}-wt-foo-3` both exist)
- **THEN** the highest-numbered suffix across both conventions SHALL be returned
- **AND** the function SHALL log at DEBUG listing all considered candidates
