## MODIFIED Requirements

### Requirement: Worktree Creation
The system SHALL create a git worktree for a specified change-id in a standardized location with full project bootstrapping.

#### Scenario: Create worktree for new change
- **WHEN** user runs `wt-new <change-id>` (uses default project or current directory)
- **THEN** a new git worktree is created at `../<repo-name>-wt-<change-id>`
- **AND** a new branch `change/<change-id>` is created if it doesn't exist
- **AND** the worktree path is printed to stdout

#### Scenario: Create worktree for specific project
- **WHEN** user runs `wt-new <change-id> -p <project-name>`
- **THEN** a worktree is created for the specified registered project

#### Scenario: Worktree already exists
- **WHEN** user runs `wt-new <change-id>` and worktree already exists
- **THEN** the existing worktree path is printed
- **AND** no error is raised

#### Scenario: Invalid change-id
- **WHEN** user runs `wt-new` without change-id
- **THEN** an error message is displayed with usage instructions

#### Scenario: Custom branch name
- **WHEN** user runs `wt-new <change-id> --branch <name>`
- **THEN** the system SHALL use `<name>` as branch name instead of `change/<change-id>`

#### Scenario: Skip git fetch
- **WHEN** user runs `wt-new <change-id> --skip-fetch`
- **THEN** the system SHALL skip `git fetch` before creating the worktree

#### Scenario: Force new branch
- **WHEN** user runs `wt-new <change-id> --new`
- **THEN** the system SHALL create a new branch even if a remote branch with the same name exists

#### Scenario: Environment file bootstrap
- **WHEN** a worktree is created
- **THEN** the system SHALL copy `.env`, `.env.local`, `.env.development`, `.env.development.local` from the main project if they exist

#### Scenario: Dependency bootstrap
- **WHEN** a worktree is created
- **THEN** the system SHALL auto-detect the package manager (npm, pnpm, yarn, bun) and install dependencies

#### Scenario: Editor configuration setup
- **WHEN** a worktree is created
- **THEN** the system SHALL create editor-specific task files (`.zed/tasks.json` for Zed, `.vscode/tasks.json` for VS Code/Cursor/Windsurf)

#### Scenario: Hook deployment
- **WHEN** a worktree is created
- **THEN** the system SHALL call `wt-deploy-hooks` to deploy Claude Code hooks to the new worktree

#### Scenario: CLAUDE.md creation
- **WHEN** a worktree is created for an OpenSpec change
- **THEN** the system SHALL create a `CLAUDE.md` file with change context information

#### Scenario: Auto-open editor
- **WHEN** a worktree is created and `--skip-open` is NOT set
- **THEN** the system SHALL automatically call `wt-work` to open the editor

### Requirement: Worktree Listing
The system SHALL list all active worktrees for projects.

#### Scenario: List worktrees for default project
- **WHEN** user runs `wt-list`
- **THEN** all worktrees for the default project are listed
- **AND** each entry shows the change-id and path

#### Scenario: List all worktrees across projects
- **WHEN** user runs `wt-list --all`
- **THEN** all worktrees for all registered projects are listed
- **AND** each entry shows the project name, change-id and path

#### Scenario: List worktrees for specific project
- **WHEN** user runs `wt-list -p <project-name>`
- **THEN** worktrees for the specified project are listed

#### Scenario: No worktrees exist
- **WHEN** user runs `wt-list` and no worktrees exist
- **THEN** an informative message is displayed

#### Scenario: List remote branches
- **WHEN** user runs `wt-list --remote`
- **THEN** remote `change/*` branches are listed
- **AND** branches with local worktrees are distinguished from "remote only" branches

### Requirement: Worktree Removal
The system SHALL remove a worktree and optionally its branch. For non-worktree repositories, the system SHALL only deregister them.

#### Scenario: Remove worktree
- **WHEN** user runs `wt-close <change-id>` on an entry with `is_worktree: true`
- **THEN** the worktree is removed via `git worktree remove`
- **AND** user is prompted whether to delete the branch

#### Scenario: Remove with force
- **WHEN** user runs `wt-close <change-id> --force` on an entry with `is_worktree: true`
- **THEN** the worktree and branch are removed without prompts

#### Scenario: Keep branch after removal
- **WHEN** user runs `wt-close <change-id> --keep-branch`
- **THEN** the worktree is removed but the branch is preserved

#### Scenario: Delete remote branch
- **WHEN** user runs `wt-close <change-id> --delete-remote`
- **THEN** the remote branch is also deleted after local removal

#### Scenario: Non-TTY context
- **WHEN** `wt-close` is run in a non-TTY context (piped, scripted)
- **THEN** the system SHALL auto-select "delete local branch only" without interactive prompts

#### Scenario: Uncommitted changes detection
- **WHEN** user runs `wt-close <change-id>` and the worktree has uncommitted changes
- **THEN** the system SHALL block removal unless `--force` is used

#### Scenario: Deregister non-worktree repository
- **WHEN** user runs `wt-close <change-id>` on an entry with `is_worktree: false`
- **THEN** the entry is removed from projects.json
- **AND** the repository directory is NOT deleted
- **AND** `git worktree remove` is NOT called

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

#### Scenario: Change-id derivation
- **WHEN** user runs `wt-add /path/to/repo` without `--as` flag
- **THEN** change-id is derived using multi-pattern matching:
  1. `*-wt-<change-id>` directory naming pattern
  2. `*-<change-id>` with repo name stripping
  3. Branch name patterns (`change/X`, `feature/X`)
  4. Directory name as fallback

#### Scenario: Directory is not a git repository
- **WHEN** user runs `wt-add /path/to/non-git-dir` where the directory is not a git repository
- **THEN** an error is displayed: "Not a git repository"
- **AND** the directory is NOT registered

#### Scenario: Hook deployment after add
- **WHEN** a repository is successfully added
- **THEN** the system SHALL call `wt-deploy-hooks` to deploy hooks

#### Scenario: Already registered
- **WHEN** user runs `wt-add /path/to/repo` and the path is already registered with the same change-id
- **THEN** a warning is shown that it's already registered
- **AND** no duplicate entry is created

## REMOVED Requirements

### Requirement: Bare repository rejection (from Add Existing Git Repository)
**Reason**: Never implemented in code. The `git rev-parse --is-inside-work-tree` check handles non-repo directories; bare repos are not a practical use case.
**Migration**: No action needed.

### Requirement: openspec init in new worktree (from Worktree Creation)
**Reason**: Not implemented. OpenSpec initialization is handled by the Ralph loop prompt or user-initiated skills, not by wt-new.
**Migration**: No action needed — openspec is initialized when needed by workflow tools.
