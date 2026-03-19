## ADDED Requirements

### Requirement: Add Existing Git Repository
The system SHALL allow users to register any existing git repository (worktree or standalone clone) with set-core via `wt-add`.

#### Scenario: Add a git worktree
- **WHEN** user runs `wt-add /path/to/worktree` where the path is a git worktree (`.git` is a file)
- **THEN** the worktree is registered in projects.json with `is_worktree: true`
- **AND** the main repo is resolved from the `.git` file's gitdir pointer

#### Scenario: Add a standalone git repository
- **WHEN** user runs `wt-add /path/to/repo` where the path is a regular git repo (`.git` is a directory)
- **THEN** the repository is registered in projects.json with `is_worktree: false`
- **AND** the repo itself is treated as its own main repo for project detection

#### Scenario: Add with explicit change-id
- **WHEN** user runs `wt-add /path/to/repo --as my-change`
- **THEN** the repository is registered with "my-change" as the change-id

#### Scenario: Add with explicit project
- **WHEN** user runs `wt-add /path/to/repo -p myproject`
- **THEN** the repository is registered under the "myproject" project

#### Scenario: Change-id derivation for standalone repo
- **WHEN** user runs `wt-add /path/to/repo` without `--as` flag on a standalone git repo
- **THEN** change-id is derived from branch name patterns (`change/X`, `feature/X`) or directory name as fallback

#### Scenario: Directory is not a git repository
- **WHEN** user runs `wt-add /path/to/non-git-dir` where the directory is not a git repository
- **THEN** an error is displayed: "Not a git repository"
- **AND** the directory is NOT registered

#### Scenario: Bare repository rejected
- **WHEN** user runs `wt-add /path/to/bare-repo` where the directory is a bare git repository (no working tree)
- **THEN** an error is displayed indicating bare repositories are not supported

#### Scenario: Already registered
- **WHEN** user runs `wt-add /path/to/repo` and the path is already registered with the same change-id
- **THEN** a warning is shown that it's already registered
- **AND** no duplicate entry is created

### Requirement: GUI Add Button Accepts Git Repositories
The GUI "Add" button SHALL accept any valid git repository, not just worktrees.

#### Scenario: Add button opens folder browser
- **WHEN** user clicks the "Add" button in Control Center
- **THEN** a folder browser dialog opens with title "Select Git Repository"

#### Scenario: Add button tooltip
- **WHEN** user hovers over the "Add" button
- **THEN** the tooltip reads "Add existing repository or worktree"

#### Scenario: Successfully add a non-worktree repo via GUI
- **WHEN** user selects a standalone git repository directory in the folder browser
- **THEN** `wt-add` is called with the selected path
- **AND** the repo appears in the Control Center table after refresh

## MODIFIED Requirements

### Requirement: Worktree Removal
The system SHALL remove a worktree and optionally its branch. For non-worktree repositories, the system SHALL only deregister them.

#### Scenario: Remove worktree
- **WHEN** user runs `wt-close <change-id>` on an entry with `is_worktree: true`
- **THEN** the worktree is removed via `git worktree remove`
- **AND** user is prompted whether to delete the branch

#### Scenario: Remove with force
- **WHEN** user runs `wt-close <change-id> --force` on an entry with `is_worktree: true`
- **THEN** the worktree and branch are removed without prompts

#### Scenario: Deregister non-worktree repository
- **WHEN** user runs `wt-close <change-id>` on an entry with `is_worktree: false`
- **THEN** the entry is removed from projects.json
- **AND** the repository directory is NOT deleted
- **AND** `git worktree remove` is NOT called
