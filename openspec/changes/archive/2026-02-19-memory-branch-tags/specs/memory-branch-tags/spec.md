## ADDED Requirements

### Requirement: Auto-tag memories with current branch
`set-memory remember` SHALL automatically append a `branch:<current-branch>` tag to every new memory, using `git branch --show-current` to detect the branch name. This tag is added in addition to any user-provided tags.

#### Scenario: Remember on a named branch
- **WHEN** user runs `echo "insight" | set-memory remember --type Learning --tags source:user` on branch `change/feature-xyz`
- **THEN** the memory is stored with tags `["source:user", "branch:change/feature-xyz"]`

#### Scenario: Remember on master
- **WHEN** user runs `echo "insight" | set-memory remember --type Decision` on branch `master`
- **THEN** the memory is stored with tags `["branch:master"]`

#### Scenario: Remember in detached HEAD state
- **WHEN** user runs `echo "insight" | set-memory remember --type Learning` in detached HEAD state (no current branch)
- **THEN** the memory is stored without a `branch:*` tag (auto-tag silently skipped)

#### Scenario: Remember outside a git repository
- **WHEN** user runs `echo "insight" | set-memory remember --type Learning` outside any git repo
- **THEN** the memory is stored without a `branch:*` tag (auto-tag silently skipped)

#### Scenario: User already provides a branch tag
- **WHEN** user runs `echo "insight" | set-memory remember --type Learning --tags branch:custom`
- **THEN** the memory is stored with tags `["branch:custom"]` (no duplicate auto-tag added)

### Requirement: Branch-boosted recall
`set-memory recall` SHALL prioritize memories tagged with the current branch while still returning cross-branch results. It does this by issuing two queries: a branch-filtered query and an unfiltered query, then merging results with branch matches first.

#### Scenario: Recall on a named branch
- **WHEN** user runs `set-memory recall "cache strategy" --limit 5` on branch `change/feature-xyz`
- **THEN** results tagged with `branch:change/feature-xyz` appear before other results
- **AND** total results do not exceed 5

#### Scenario: Recall with no branch-specific memories
- **WHEN** user runs `set-memory recall "auth patterns" --limit 5` on branch `change/new-feature`
- **AND** no memories have the `branch:change/new-feature` tag
- **THEN** all 5 results come from the unfiltered query (same as current behavior)

#### Scenario: Recall with explicit --tags overrides branch boost
- **WHEN** user runs `set-memory recall "query" --tags change:old-feature`
- **THEN** the explicit tag filter is used as-is (branch boost is NOT applied on top of explicit tag filtering)

#### Scenario: Recall outside a git repository
- **WHEN** user runs `set-memory recall "query"` outside any git repo
- **THEN** recall behaves as current (no branch boost applied)

#### Scenario: Recall on detached HEAD
- **WHEN** user runs `set-memory recall "query"` in detached HEAD state
- **THEN** recall behaves as current (no branch boost applied)
